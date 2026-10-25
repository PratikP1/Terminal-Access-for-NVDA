"""Manual profile selection must survive the dialog's return to the terminal."""
from types import SimpleNamespace
from unittest.mock import patch
import sys

import pytest

from globalPlugins import terminalAccess as ta
from lib.profiles import ProfileManager
from NVDAObjects.behaviors import Terminal


class TerminalControl(Terminal):
	"""Model provider equality independently of HWND and mutable title."""
	def __init__(self, identity=1, name="PowerShell"):
		self.identity = identity
		self.name = name
		self.appModule = SimpleNamespace(appName="windowsterminal")
		self.windowHandle = 42

	def __eq__(self, other):
		return isinstance(other, TerminalControl) and self.identity == other.identity


@pytest.fixture
def plugin(monkeypatch):
	monkeypatch.setitem(sys.modules, "controlTypes", SimpleNamespace(
		Role=SimpleNamespace(TERMINAL="terminal", EDITABLETEXT="edit"),
	))
	plugin = ta.GlobalPlugin.__new__(ta.GlobalPlugin)
	plugin._initState()
	plugin._profileManager = ProfileManager()
	plugin._configManager = SimpleNamespace(get=lambda key, default=None: default)
	plugin._currentProfile = None
	plugin._manualProfileSelection = None
	plugin._boundTerminal = TerminalControl()
	return plugin


def select_profile(plugin, name="vim"):
	"""Drive the real dialog callback while substituting only the modal UI."""
	class Dialog:
		def __init__(self, parent, manager, on_activate):
			self.on_activate = on_activate

		def ShowModal(self):
			# NVDA clears the bound terminal while the dialog has focus.
			plugin._boundTerminal = None
			if name is not None:
				self.on_activate(name)

		def Destroy(self):
			pass

	with patch("lib.profiles.ProfileSelectionDialog", Dialog), patch.object(
		ta.wx, "CallAfter", side_effect=lambda callback: callback(),
	):
		plugin._showProfileSelectionDialog()


def test_selection_survives_dialog_return_and_later_refocus(plugin):
	terminal = plugin._boundTerminal
	select_profile(plugin)
	for _ in range(2):
		plugin._detectAndApplyProfile(terminal)
		assert plugin._getEffective("punctuationLevel") == 2
		assert plugin._currentProfile.appName == "vim"


def test_manual_selection_takes_priority_over_title_detection(plugin):
	terminal = plugin._boundTerminal
	terminal.name = "Claude Code"
	select_profile(plugin)
	plugin._detectAndApplyProfile(terminal)
	assert plugin._currentProfile.appName == "vim"


def test_other_terminal_with_same_handle_uses_automatic_profile(plugin):
	first = plugin._boundTerminal
	select_profile(plugin)
	other = TerminalControl(identity=2, name="Claude Code")
	plugin._detectAndApplyProfile(other)
	assert plugin._currentProfile.appName == "claude"
	plugin._detectAndApplyProfile(first)
	assert plugin._currentProfile is None


def test_cancel_leaves_automatic_detection_unchanged(plugin):
	terminal = plugin._boundTerminal
	select_profile(plugin, None)
	plugin._detectAndApplyProfile(terminal)
	assert plugin._currentProfile is None


def test_removed_selected_profile_falls_back_to_detection(plugin):
	terminal = plugin._boundTerminal
	select_profile(plugin)
	del plugin._profileManager.profiles["vim"]
	plugin._detectAndApplyProfile(terminal)
	assert plugin._currentProfile is None


def test_invalid_selection_does_not_override_detection(plugin):
	terminal = plugin._boundTerminal
	select_profile(plugin, "missing")
	plugin._detectAndApplyProfile(terminal)
	assert plugin._currentProfile is None


def test_new_wrapper_for_same_control_keeps_selection(plugin):
	select_profile(plugin)
	plugin._detectAndApplyProfile(TerminalControl(name="Changed title"))
	assert plugin._currentProfile.appName == "vim"


def test_identically_named_other_tab_does_not_inherit_selection(plugin):
	select_profile(plugin)
	plugin._detectAndApplyProfile(TerminalControl(identity=2))
	assert plugin._currentProfile is None


def test_terminal_host_search_box_does_not_clear_selection(plugin):
	terminal = plugin._boundTerminal
	select_profile(plugin)
	search_box = SimpleNamespace(
		appModule=terminal.appModule, name="Find", role="edit",
	)
	plugin._detectAndApplyProfile(search_box)
	plugin._detectAndApplyProfile(terminal)
	assert plugin._currentProfile.appName == "vim"


def test_dialog_uses_focus_when_terminal_has_not_been_bound(plugin):
	terminal = plugin._boundTerminal
	plugin._boundTerminal = None
	with patch.object(ta.api, "getFocusObject", return_value=terminal):
		select_profile(plugin)
	plugin._detectAndApplyProfile(terminal)
	assert plugin._currentProfile.appName == "vim"
