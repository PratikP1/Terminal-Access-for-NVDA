"""Saving settings persists user choices and applies gesture exclusions."""

from types import SimpleNamespace

import pytest

from lib import settings_panel as module


class ValueControl:
	def __init__(self, value):
		self.value = value

	def GetValue(self):
		return self.value

	def GetSelection(self):
		return self.value


@pytest.fixture
def settings(monkeypatch):
	panel = module.TerminalAccessSettingsPanel()
	# A deliberate mix of enabled/disabled controls catches swapped settings.
	values = {
		"cursorTrackingCheckBox": True, "cursorTrackingModeChoice": 2,
		"keyEchoCheckBox": True, "wordEchoCheckBox": False,
		"linePauseCheckBox": False, "repeatedSymbolsCheckBox": True,
		"quietModeCheckBox": True, "verboseModeCheckBox": False,
		"indentationOnLineReadCheckBox": True, "punctuationLevelChoice": 3,
		"repeatedSymbolsValuesText": "~=", "cursorDelaySpinner": 75,
		"defaultProfileChoice": 1, "summarizationCheckBox": False,
		"codeBlockExplainCheckBox": True, "aiTurnParseCheckBox": False,
		"privacyAnnounceCheckBox": True, "streamingSuppressionCheckBox": False,
		"progressMilestonesCheckBox": True, "errorAudioCuesCheckBox": True,
		"errorCuesQuietModeCheckBox": False, "outputActivityTonesCheckBox": False,
		"outputDebounceSpinner": 350, "earconVolumeSpinner": 40, "earconPitchSpinner": 150,
	}
	for name, value in values.items():
		setattr(panel, name, ValueControl(value))
	panel._getProfileNames = lambda: ["shell", "editor"]
	panel._gestureItems = [("kb:alt+n", "nextSection"), ("kb:alt+p", "prevSection")]
	panel.gestureCheckList = SimpleNamespace(IsChecked=lambda index: index == 1)
	conf = {"terminalAccess": {"unrelated": "preserved"}, "keyboard": {"speakTypedWords": 0}}
	monkeypatch.setattr(module.config, "conf", conf)
	monkeypatch.setattr(module.globalPluginHandler, "runningPlugins", [])
	return panel, conf


def test_save_persists_choices_and_reloads_live_gestures(settings, make_plugin, monkeypatch):
	panel, conf = settings
	plugin = make_plugin()
	# The test NVDA base does not install decorator bindings automatically.
	plugin.bindGesture("kb:alt+n", "nextSection")
	monkeypatch.setattr(module.globalPluginHandler, "runningPlugins", [plugin])
	panel.onSave()
	saved = conf["terminalAccess"]
	assert {key: saved[key] for key in (
		"cursorTracking", "cursorTrackingMode", "keyEcho", "wordEcho", "linePause",
		"repeatedSymbols", "quietMode", "verboseMode", "indentationOnLineRead",
		"punctuationLevel", "repeatedSymbolsValues", "cursorDelay", "defaultProfile",
		"summarizationEnabled", "codeBlockExplain", "aiTurnParseEnabled", "privacyAnnounce",
		"streamingSuppression", "progressMilestones", "errorAudioCues", "errorAudioCuesInQuietMode",
		"outputActivityTones", "outputActivityDebounce", "earconVolume", "earconPitchShift",
		"unboundGestures", "unrelated",
	)} == {
		"cursorTracking": True, "cursorTrackingMode": 2, "keyEcho": True, "wordEcho": False,
		"linePause": False, "repeatedSymbols": True, "quietMode": True, "verboseMode": False,
		"indentationOnLineRead": True, "punctuationLevel": 3, "repeatedSymbolsValues": "~=",
		"cursorDelay": 75, "defaultProfile": "shell", "summarizationEnabled": False,
		"codeBlockExplain": True, "aiTurnParseEnabled": False, "privacyAnnounce": True,
		"streamingSuppression": False, "progressMilestones": True, "errorAudioCues": True,
		"errorAudioCuesInQuietMode": False, "outputActivityTones": False, "outputActivityDebounce": 350,
		"earconVolume": 40, "earconPitchShift": 150, "unboundGestures": "kb:alt+n", "unrelated": "preserved",
	}
	assert "kb:alt+n" not in plugin._gestureMap
	assert plugin._gestureMap["kb:NVDA+alt+s"] == "summarizeLastCommand"


@pytest.mark.parametrize("profile_index", [0, 99])
def test_save_invalid_numeric_values_uses_safe_defaults(settings, profile_index):
	panel, conf = settings
	for name in ("cursorTrackingModeChoice", "punctuationLevelChoice", "cursorDelaySpinner",
		"outputDebounceSpinner", "earconVolumeSpinner", "earconPitchSpinner"):
		getattr(panel, name).value = -1
	panel.defaultProfileChoice.value = profile_index
	panel.repeatedSymbolsValuesText.value = None
	panel.onSave()
	saved = conf["terminalAccess"]
	assert [saved[key] for key in ("cursorTrackingMode", "punctuationLevel", "cursorDelay",
		"outputActivityDebounce", "earconVolume", "earconPitchShift")] == [1, 2, 20, 1000, 100, 100]
	assert saved["defaultProfile"] == ""
	assert saved["repeatedSymbolsValues"] == "-_=!"


def test_save_warns_when_native_word_echo_owns_typing(settings, monkeypatch):
	panel, conf = settings
	conf["keyboard"]["speakTypedWords"] = 1
	import ui
	messages = []
	monkeypatch.setattr(ui, "message", messages.append)
	panel.onSave()
	assert len(messages) == 1
	assert "NVDA's speak typed words" in messages[0]
	assert conf["terminalAccess"]["keyEcho"] is True
