"""Tests for output search behavior."""

import api
import textInfos


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummyTextInfo:
	"""Minimal TextInfo replacement without bookmark support."""

	def __init__(self, source_text, line_index=0):
		self._source_text = source_text
		self.line_index = line_index
		self.text = source_text

	@property
	def bookmark(self):
		return None

	def move(self, unit, count):
		self.line_index += count
		return True

	def copy(self):
		return DummyTextInfo(self._source_text, self.line_index)


class DummyTerminal:
	"""Terminal stub that cannot recreate positions from bookmarks."""

	def __init__(self, text):
		self.text = text

	def makeTextInfo(self, arg):
		if arg == textInfos.POSITION_ALL:
			return DummyTextInfo(self.text, 0)
		if arg == textInfos.POSITION_FIRST:
			return DummyTextInfo(self.text, 0)
		# Simulate bookmark-based retrieval not being supported
		raise ValueError("Bookmarks not supported")


def _setup_textinfos():
	"""Ensure textInfos constants are set."""
	textInfos.POSITION_ALL = "all"
	textInfos.POSITION_FIRST = "first"
	textInfos.UNIT_LINE = "line"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_search_moves_review_without_bookmarks():
	"""Ensure search moves the review cursor even when bookmarks aren't supported."""
	_setup_textinfos()

	from globalPlugins.terminalAccess import OutputSearchManager

	api.setReviewPosition.reset_mock()

	manager = OutputSearchManager(DummyTerminal("alpha\nbeta\ngamma"))

	assert manager.search("beta") == 1
	assert manager.first_match() is True
	api.setReviewPosition.assert_called_once()
	position = api.setReviewPosition.call_args[0][0]
	assert getattr(position, "line_index", None) == 1
	assert manager.get_current_match_info() == (1, 1, "beta", 2)


def test_search_strips_ansi_codes():
	"""Search must find text even when the terminal buffer contains ANSI escape sequences."""
	_setup_textinfos()

	from globalPlugins.terminalAccess import OutputSearchManager

	# Terminal text with ANSI color codes wrapping the word "error"
	ansi_text = "line1\n\x1b[31merror\x1b[0m occurred\nline3"
	manager = OutputSearchManager(DummyTerminal(ansi_text))

	# The user searches for plain "error" — must match despite ANSI codes
	assert manager.search("error") == 1
	assert manager.first_match() is True
	info = manager.get_current_match_info()
	# After stripping, line text should be "error occurred" (no ANSI)
	assert info is not None
	match_num, total, line_text, line_num = info
	assert "error" in line_text
	assert "\x1b" not in line_text  # No ANSI codes in stored text


def test_search_strips_osc_sequences():
	"""Search must strip OSC sequences (hyperlinks, window titles) before matching."""
	_setup_textinfos()

	from globalPlugins.terminalAccess import OutputSearchManager

	# OSC hyperlink wrapping a filename
	osc_text = "see \x1b]8;;http://example.com\x07readme.md\x1b]8;;\x07 for details"
	manager = OutputSearchManager(DummyTerminal(osc_text))

	assert manager.search("readme.md") == 1
	assert manager.first_match() is True
	info = manager.get_current_match_info()
	assert info is not None
	_, _, line_text, _ = info
	assert "readme.md" in line_text
	assert "\x1b" not in line_text


def test_search_case_insensitive():
	"""Case-insensitive search must match regardless of casing."""
	_setup_textinfos()

	from globalPlugins.terminalAccess import OutputSearchManager

	manager = OutputSearchManager(DummyTerminal("Hello World\nGOODBYE WORLD"))

	assert manager.search("hello", case_sensitive=False) == 1
	assert manager.search("goodbye", case_sensitive=False) == 1
	assert manager.search("HELLO", case_sensitive=True) == 0


def test_search_next_and_previous():
	"""Next and previous match navigation must cycle through results."""
	_setup_textinfos()

	from globalPlugins.terminalAccess import OutputSearchManager

	api.setReviewPosition.reset_mock()

	manager = OutputSearchManager(DummyTerminal("aaa\nbbb\naaa\nccc\naaa"))

	assert manager.search("aaa") == 3

	# first_match → index 0
	assert manager.first_match() is True
	info = manager.get_current_match_info()
	assert info[0] == 1  # match 1 of 3

	# next_match → index 1
	assert manager.next_match() is True
	info = manager.get_current_match_info()
	assert info[0] == 2  # match 2 of 3

	# next_match → index 2
	assert manager.next_match() is True
	info = manager.get_current_match_info()
	assert info[0] == 3  # match 3 of 3

	# next_match wraps → index 0
	assert manager.next_match() is True
	info = manager.get_current_match_info()
	assert info[0] == 1  # wrapped to match 1

	# previous_match wraps → index 2
	assert manager.previous_match() is True
	info = manager.get_current_match_info()
	assert info[0] == 3  # wrapped to match 3
