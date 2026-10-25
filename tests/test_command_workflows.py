"""Command behavior at the NVDA boundary, using real parsers and summaries."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from globalPlugins import terminalAccess as module


@pytest.fixture
def commands(make_plugin, monkeypatch):
	plugin = make_plugin()
	plugin.isTerminalApp = lambda: True
	plugin._configManager = {"summarizationEnabled": True, "codeBlockExplain": True, "privacyAnnounce": True}
	messages, speech, braille, beeps = [], [], [], []
	monkeypatch.setattr(module.ui, "message", messages.append)
	monkeypatch.setattr(module.speech, "speakText", speech.append)
	monkeypatch.setattr(module.tones, "beep", lambda *args: beeps.append(args))
	plugin._brailleMessage = braille.append
	return SimpleNamespace(plugin=plugin, messages=messages, speech=speech, braille=braille, beeps=beeps)


@pytest.mark.parametrize("command", ["summarizeLastCommand", "summarizeSelection", "explainCodeBlock"])
@pytest.mark.parametrize("announce", [False, True])
def test_disabled_processing_never_reads_terminal(commands, command, announce):
	p = commands.plugin
	p._configManager.update(summarizationEnabled=False, codeBlockExplain=False, privacyAnnounce=announce)
	p._getBufferLines = Mock(side_effect=AssertionError("privacy gate must precede buffer access"))
	p._boundTerminal = SimpleNamespace(makeTextInfo=Mock(side_effect=AssertionError("selection must stay private")))
	p._markStart, p._markEnd = "start", "end"
	getattr(p, "script_" + command)(Mock())
	assert bool(commands.messages) is announce
	if announce:
		assert "disabled" in commands.messages[0].lower()
	assert commands.speech == commands.braille == commands.beeps == []


@pytest.mark.parametrize("lines,current,expected", [
	(["$ old", "error: old secret", "$ build", "error: new failure", "later output"], 3, "error: new failure"),
	(["first output", "error: failure", "later output"], 1, "first output\nerror: failure"),
	(["$ old", "done", "$ next"], 2, "No output to summarize"),
	(["$ run", "", " "], 2, "No significant output found"),
])
def test_last_command_summary_respects_prompt_and_cursor(commands, lines, current, expected):
	p = commands.plugin
	p._getBufferLines = lambda: lines
	p._getCurrentLineNumber = lambda: current
	p.script_summarizeLastCommand(Mock())
	assert commands.messages == [expected]


class SelectionRange:
	"""Only the endpoint operation needed to join two selection marks."""
	def __init__(self, text, end=False):
		self._text = text
		self.end = end
		self.joined = False

	def setEndPoint(self, other, relation):
		assert other.end and relation == "endToEnd"
		self.joined = True

	@property
	def text(self):
		assert self.joined, "reading before joining marks would summarize the wrong range"
		return self._text


@pytest.mark.parametrize("text,expected", [("error: selected\n2 failures", "error: selected\n2 failures"),
	("", "No significant output found")])
def test_selection_summary_joins_saved_endpoints(commands, text, expected):
	p = commands.plugin
	p._markStart, p._markEnd = "start", "end"
	ranges = {"start": SelectionRange(text), "end": SelectionRange("", end=True)}
	p._boundTerminal = SimpleNamespace(makeTextInfo=ranges.__getitem__)
	p.script_summarizeSelection(Mock())
	assert commands.messages == [expected]


def test_selection_failure_is_announced_without_summary(commands):
	p = commands.plugin
	p._markStart, p._markEnd = "start", "end"
	p._boundTerminal = SimpleNamespace(makeTextInfo=Mock(side_effect=RuntimeError("provider unavailable")))
	p.script_summarizeSelection(Mock())
	assert commands.messages == ["Unable to read selection"]


@pytest.mark.parametrize("command", ["announceCodeBlock", "explainCodeBlock", "copyCodeBlock"])
def test_code_commands_report_missing_block(commands, command):
	p = commands.plugin
	p._getBufferLines = lambda: ["ordinary terminal output"]
	p._getCurrentLineNumber = lambda: 0
	getattr(p, "script_" + command)(Mock())
	assert commands.messages == ["Not inside a code block"]


def test_code_commands_use_detected_contents(commands):
	p = commands.plugin
	p._getBufferLines = lambda: ["outside", "```python", "import os", "def greet():", "    pass", "```"]
	p._getCurrentLineNumber = lambda: 3
	clipboard = []
	p._copyToClipboard = lambda text: clipboard.append(text) or True
	p.script_announceCodeBlock(Mock())
	p.script_explainCodeBlock(Mock())
	p.script_copyCodeBlock(Mock())
	assert commands.messages[0] == "Python block, 3 lines"
	assert "import" in commands.messages[1].lower() and "greet" in commands.messages[1]
	assert commands.messages[2] == "Code block copied"
	assert clipboard == ["import os\ndef greet():\n    pass"]


@pytest.mark.parametrize("command,start,target,category", [
	("nextSection", 0, 1, "output"), ("prevSection", 2, 1, "output"),
	("nextError", 0, 2, "error"), ("prevError", 4, 2, "error"),
	("nextPrompt", 0, 4, "prompt"), ("prevPrompt", 4, 0, "prompt"),
])
def test_section_commands_choose_semantic_destination(commands, command, start, target, category):
	p = commands.plugin
	p._getBufferLines = lambda: ["$ build", "compiling", "error: failed", "done", "$ next"]
	p._getCurrentLineNumber = lambda: start
	destinations = []
	p._navigateToSection = destinations.append
	getattr(p, "script_" + command)(Mock())
	assert [(s.line_num, s.category) for s in destinations] == [(target, category)]


@pytest.mark.parametrize("command", ["nextSection", "prevSection", "nextError", "prevError", "nextPrompt",
	"prevPrompt", "nextTurn", "prevTurn", "summarizeLastCommand", "announceCodeBlock", "explainCodeBlock"])
def test_navigation_and_read_commands_handle_empty_or_nonterminal(commands, command):
	p = commands.plugin
	p._getBufferLines = lambda: []
	gesture = Mock()
	getattr(p, "script_" + command)(gesture)
	assert commands.beeps == [(200, 100)]
	assert commands.messages == commands.speech == []
	p.isTerminalApp = lambda: False
	p._getBufferLines = Mock(side_effect=AssertionError("must not read a nonterminal"))
	getattr(p, "script_" + command)(gesture)
	gesture.send.assert_called_once_with()
	assert commands.beeps == [(200, 100)]


class LineRange:
	def __init__(self, lines):
		self.lines, self.line = lines, 0

	def move(self, unit, count):
		assert unit == module.textInfos.UNIT_LINE
		self.line += count
		return count

	def expand(self, unit):
		assert unit == module.textInfos.UNIT_LINE

	@property
	def text(self):
		return self.lines[self.line]


def test_ai_navigation_moves_review_and_announces_destination(commands, monkeypatch):
	p = commands.plugin
	lines = ["User: explain", "Assistant: " + "a" * 60, "continuation"]
	p._getBufferLines = lambda: lines
	p._getCurrentLineNumber = lambda: 0
	info = LineRange(lines)
	p._boundTerminal = SimpleNamespace(makeTextInfo=lambda position: info)
	review = []
	monkeypatch.setattr(module.api, "setReviewPosition", lambda value: review.append(value.line))
	p.script_nextTurn(Mock())
	assert review == [1]
	assert commands.speech == ["assistant: " + lines[1][:40] + "..."]
	assert commands.braille == [commands.speech[0][:30]]
	assert commands.beeps == [(660, 30)]


def test_ai_navigation_end_and_provider_failure(commands):
	p = commands.plugin
	p._getBufferLines = lambda: ["User: hello", "Assistant: response"]
	p._getCurrentLineNumber = lambda: 1
	p.script_nextTurn(Mock())
	assert commands.beeps == [(200, 100)]
	p._boundTerminal = SimpleNamespace(makeTextInfo=Mock(side_effect=RuntimeError("provider unavailable")))
	p.script_prevTurn(Mock())
	assert commands.messages == ["user"]
	assert commands.speech == commands.braille == []


@pytest.mark.parametrize("outcome", ["save", "cancel", "unwritable"])
def test_export_dialog_writes_utf8_and_releases_popup(commands, monkeypatch, tmp_path, outcome):
	p = commands.plugin
	path = tmp_path / "transcript.txt"
	if outcome == "unwritable":
		path.mkdir()
	lifecycle = []
	dialog = SimpleNamespace(ShowModal=lambda: module.wx.ID_OK if outcome != "cancel" else -1,
		GetPath=lambda: str(path), Destroy=lambda: lifecycle.append("destroy"))
	monkeypatch.setattr(module.wx, "FileDialog", lambda *args, **kwargs: dialog)
	monkeypatch.setattr(module.gui.mainFrame, "prePopup", lambda: lifecycle.append("open"))
	monkeypatch.setattr(module.gui.mainFrame, "postPopup", lambda: lifecycle.append("close"))
	p._showExportTranscriptDialog(["\x1b[31merror: café\x1b[0m", "second line"])
	assert lifecycle == ["open", "destroy", "close"]
	if outcome == "save":
		assert path.read_text(encoding="utf-8") == "error: café\nsecond line"
		assert commands.messages == ["Transcript saved"]
	elif outcome == "cancel":
		assert not path.exists() and commands.messages == []
	else:
		assert commands.messages == ["Unable to save transcript"]
