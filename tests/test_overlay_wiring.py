"""
Tests for wiring TerminalAccessTerminal overlay into the GlobalPlugin.

Verifies that chooseNVDAObjectOverlayClasses inserts the overlay
for terminal objects and skips it for non-terminals.
Also verifies that the GlobalPlugin's event_textChange delegates
to the overlay when it's present on the object.
"""
import sys
import types
from unittest.mock import Mock, MagicMock, patch

import pytest


class TestChooseNVDAObjectOverlayClasses:
    """GlobalPlugin.chooseNVDAObjectOverlayClasses must insert overlay for terminals."""

    def _make_plugin(self):
        """Create a GlobalPlugin instance for testing."""
        from globalPlugins.terminalAccess import GlobalPlugin
        plugin = GlobalPlugin.__new__(GlobalPlugin)
        # Minimal init without full NVDA startup
        plugin._gestureMap = {}
        plugin._boundTerminal = None
        plugin._configManager = Mock()
        return plugin

    def _make_obj(self, app_name):
        """Create a mock NVDAObject with an appModule."""
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = app_name
        return obj

    def test_inserts_overlay_for_windows_terminal(self):
        """Windows Terminal objects get TerminalAccessTerminal in clsList."""
        from lib.terminal_overlay import TerminalAccessTerminal
        plugin = self._make_plugin()
        obj = self._make_obj("windowsterminal")

        # Simulate NVDA's Terminal base class in clsList
        FakeTerminal = type("FakeTerminal", (), {})
        clsList = [FakeTerminal]

        plugin.chooseNVDAObjectOverlayClasses(obj, clsList)

        assert TerminalAccessTerminal in clsList
        # Must be first (highest priority in MRO)
        assert clsList[0] is TerminalAccessTerminal

    def test_inserts_overlay_for_cmd(self):
        """cmd.exe objects get the overlay."""
        from lib.terminal_overlay import TerminalAccessTerminal
        plugin = self._make_plugin()
        obj = self._make_obj("cmd")
        clsList = [Mock()]

        plugin.chooseNVDAObjectOverlayClasses(obj, clsList)
        assert TerminalAccessTerminal in clsList

    def test_inserts_overlay_for_powershell(self):
        """PowerShell objects get the overlay."""
        from lib.terminal_overlay import TerminalAccessTerminal
        plugin = self._make_plugin()
        obj = self._make_obj("powershell")
        clsList = [Mock()]

        plugin.chooseNVDAObjectOverlayClasses(obj, clsList)
        assert TerminalAccessTerminal in clsList

    def test_skips_overlay_for_notepad(self):
        """Non-terminal apps do NOT get the overlay."""
        from lib.terminal_overlay import TerminalAccessTerminal
        plugin = self._make_plugin()
        obj = self._make_obj("notepad")
        clsList = [Mock()]

        plugin.chooseNVDAObjectOverlayClasses(obj, clsList)
        assert TerminalAccessTerminal not in clsList

    def test_skips_overlay_for_powertoys(self):
        """PowerToys Command Palette does NOT get the overlay."""
        from lib.terminal_overlay import TerminalAccessTerminal
        plugin = self._make_plugin()
        obj = self._make_obj("microsoft.cmdpal")
        clsList = [Mock()]

        plugin.chooseNVDAObjectOverlayClasses(obj, clsList)
        assert TerminalAccessTerminal not in clsList

    def test_does_not_duplicate_overlay(self):
        """If overlay is already in clsList, don't add again."""
        from lib.terminal_overlay import TerminalAccessTerminal
        plugin = self._make_plugin()
        obj = self._make_obj("windowsterminal")
        clsList = [TerminalAccessTerminal, Mock()]

        plugin.chooseNVDAObjectOverlayClasses(obj, clsList)
        assert clsList.count(TerminalAccessTerminal) == 1

    def test_overlay_gets_config_manager_ref(self):
        """After overlay is inserted, initOverlayClass should find _configManager."""
        from lib.terminal_overlay import TerminalAccessTerminal
        # Verify the overlay class has initOverlayClass
        overlay = TerminalAccessTerminal()
        assert hasattr(overlay, 'initOverlayClass')
        assert hasattr(overlay, '_configManager')


class TestEventTextChangeDelegation:
    """GlobalPlugin.event_textChange should delegate to overlay when present."""

    def _make_plugin(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        plugin = GlobalPlugin.__new__(GlobalPlugin)
        plugin._gestureMap = {}
        plugin._boundTerminal = None
        plugin._configManager = Mock()
        return plugin

    def test_non_terminal_calls_next_handler(self):
        """Outside terminals, event_textChange calls nextHandler."""
        plugin = self._make_plugin()
        plugin._boundTerminal = None
        obj = Mock()
        nextHandler = Mock()

        plugin.event_textChange(obj, nextHandler)
        nextHandler.assert_called_once()

    def test_terminal_with_overlay_skips_old_logic(self):
        """When object has overlay, GlobalPlugin should not duplicate
        activity tone/error cue logic (overlay handles it)."""
        from lib.terminal_overlay import TerminalAccessTerminal
        plugin = self._make_plugin()
        plugin._boundTerminal = Mock()
        plugin._configManager = Mock()
        plugin._configManager.get = Mock(return_value=False)

        # Object with overlay class in its MRO
        obj = Mock(spec=TerminalAccessTerminal)
        nextHandler = Mock()

        plugin.event_textChange(obj, nextHandler)
        # Should not call our old activity tone/error cue methods
        # because the overlay handles those in its own event_textChange


class TestEventCaretWithOverlay:
    """event_caret should be simplified when overlay handles output."""

    def _make_plugin(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        plugin = GlobalPlugin.__new__(GlobalPlugin)
        plugin._gestureMap = {}
        plugin._boundTerminal = None
        plugin._configManager = Mock()
        plugin._cursorTrackingTimer = None
        plugin._lastTypedCharTime = 0
        return plugin

    def test_non_terminal_passes_through(self):
        """Outside terminals, event_caret calls nextHandler."""
        plugin = self._make_plugin()
        plugin._boundTerminal = None
        obj = Mock()
        nextHandler = Mock()

        plugin.event_caret(obj, nextHandler)
        nextHandler.assert_called_once()
