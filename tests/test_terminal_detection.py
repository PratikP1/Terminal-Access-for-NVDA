"""Tests verifying terminal detection works correctly end-to-end.

These tests validate the isTerminalApp logic against all supported terminals
and the event_gainFocus flow that wires up terminal features.  They serve as
a regression guard against the stale-bytecode packaging bug where NVDA loaded
old .pyc files and failed to detect terminals.
"""
from unittest.mock import MagicMock, Mock, patch
import pytest


class TestTerminalDetection:
    """Test isTerminalApp against all supported terminals."""

    def _make_plugin(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        return GlobalPlugin()

    def _make_obj(self, app_name):
        obj = MagicMock()
        obj.appModule.appName = app_name
        return obj

    @pytest.mark.parametrize("app_name", [
        "windowsterminal", "cmd", "powershell", "pwsh", "conhost",
        "alacritty", "wezterm", "wezterm-gui", "mintty", "putty",
        "kitty", "hyper", "tabby", "ghostty", "rio",
        "cmder", "conemu", "conemu64", "terminus", "fluent",
        "wsl", "bash", "waveterm", "contour", "cool-retro-term",
        "mobaxterm", "securecrt", "ttermpro", "mremoteng", "royalts",
    ])
    def test_detects_known_terminal(self, app_name):
        """isTerminalApp should return True for known terminals."""
        plugin = self._make_plugin()
        obj = self._make_obj(app_name)
        assert plugin.isTerminalApp(obj) is True, f"{app_name} not detected as terminal"

    @pytest.mark.parametrize("app_name", [
        "notepad", "firefox", "chrome", "explorer", "code",
        "word", "excel", "slack", "teams",
    ])
    def test_rejects_non_terminal(self, app_name):
        """isTerminalApp should return False for non-terminal apps."""
        plugin = self._make_plugin()
        obj = self._make_obj(app_name)
        assert plugin.isTerminalApp(obj) is False, f"{app_name} wrongly detected as terminal"

    def test_rejects_securefx(self):
        """SecureFX should NOT be detected (shares 'secure' branding with SecureCRT)."""
        plugin = self._make_plugin()
        obj = self._make_obj("securefx")
        assert plugin.isTerminalApp(obj) is False

    def test_detects_securecrt(self):
        """SecureCRT SHOULD be detected as a terminal."""
        plugin = self._make_plugin()
        obj = self._make_obj("securecrt")
        assert plugin.isTerminalApp(obj) is True

    def test_rejects_powertoys_cmdpal(self):
        """PowerToys Command Palette is not a terminal despite 'cmd' in name."""
        plugin = self._make_plugin()
        for name in ("microsoft.cmdpal.ui", "microsoft.cmdpal.ext.powertoys"):
            obj = self._make_obj(name)
            assert plugin.isTerminalApp(obj) is False, f"{name} wrongly detected as terminal"

    def test_rejects_powertoys_settings(self):
        """PowerToys utilities should not be detected as terminals."""
        plugin = self._make_plugin()
        for name in ("powertoys", "powertoys.colorpickerui", "powertoys.fancyzones"):
            obj = self._make_obj(name)
            assert plugin.isTerminalApp(obj) is False, f"{name} wrongly detected as terminal"

    def test_exact_match_no_substring_false_positives(self):
        """Detection uses exact match, not substring. Apps containing terminal
        keywords as part of a longer name should not be detected."""
        plugin = self._make_plugin()
        false_positives = [
            "cmdproxy",         # contains "cmd"
            "bashrc-editor",    # contains "bash"
            "scenario",         # contains "rio"
            "fluentui",         # contains "fluent"
            "hellobash",        # contains "bash"
            "wslconfig",        # contains "wsl"
        ]
        for name in false_positives:
            obj = self._make_obj(name)
            assert plugin.isTerminalApp(obj) is False, f"{name} wrongly detected as terminal"

    def test_case_insensitive_detection(self):
        """Detection should be case-insensitive."""
        plugin = self._make_plugin()
        obj = self._make_obj("WindowsTerminal")
        assert plugin.isTerminalApp(obj) is True

    def test_caches_result(self):
        """Second call for same app should use cache."""
        plugin = self._make_plugin()
        obj = self._make_obj("windowsterminal")
        plugin.isTerminalApp(obj)  # First call
        assert "windowsterminal" in plugin._terminalAppCache
        # Second call should return cached result
        assert plugin.isTerminalApp(obj) is True

    def test_none_object_returns_false(self):
        """None object should return False without crashing."""
        plugin = self._make_plugin()
        assert plugin.isTerminalApp(None) is False

    def test_no_appmodule_returns_false(self):
        """Object without appModule should return False."""
        plugin = self._make_plugin()
        obj = MagicMock()
        obj.appModule = None
        assert plugin.isTerminalApp(obj) is False


class TestGainFocusFlow:
    """Test event_gainFocus wiring for terminal and non-terminal apps."""

    def _make_plugin(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        return GlobalPlugin()

    def _make_obj(self, app_name):
        obj = MagicMock()
        obj.appModule.appName = app_name
        obj.windowClassName = "ConsoleWindowClass"
        obj.windowHandle = 0x12345
        obj.windowText = ""
        return obj

    def test_event_gainfocus_calls_onTerminalFocus(self):
        """When a terminal gains focus, _onTerminalFocus should be called."""
        plugin = self._make_plugin()
        obj = self._make_obj("windowsterminal")
        plugin._onTerminalFocus = MagicMock()
        next_handler = MagicMock()

        plugin.event_gainFocus(obj, next_handler)

        next_handler.assert_called_once()
        plugin._onTerminalFocus.assert_called_once_with(obj)

    def test_event_gainfocus_non_terminal_clears_bound(self):
        """When a non-terminal gains focus, _boundTerminal should be cleared."""
        plugin = self._make_plugin()
        obj = self._make_obj("notepad")
        next_handler = MagicMock()

        plugin.event_gainFocus(obj, next_handler)

        assert plugin._boundTerminal is None

    def test_help_announced_on_first_terminal_focus(self):
        """First terminal focus should announce help message."""
        import ui
        ui.message = MagicMock()

        plugin = self._make_plugin()
        plugin.announcedHelp = False

        plugin._announceHelpIfNeeded("windowsterminal")

        ui.message.assert_called()
        assert plugin.announcedHelp is True

    def test_help_not_repeated_for_same_terminal(self):
        """After initial announcement, same terminal should not re-announce."""
        import ui
        ui.message = MagicMock()

        plugin = self._make_plugin()
        plugin.announcedHelp = True
        plugin.lastTerminalAppName = "windowsterminal"

        plugin._announceHelpIfNeeded("windowsterminal")

        ui.message.assert_not_called()

    def test_help_announced_when_terminal_changes(self):
        """Switching to a different terminal should announce help again."""
        import ui
        ui.message = MagicMock()

        plugin = self._make_plugin()
        plugin.announcedHelp = True
        plugin.lastTerminalAppName = "windowsterminal"

        plugin._announceHelpIfNeeded("alacritty")

        ui.message.assert_called()


class TestEventCaretNoCrash:
    """Test that event_caret doesn't crash with NameError."""

    def _make_plugin(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        return GlobalPlugin()

    def test_event_caret_uses_configManager_not_ta_conf(self):
        """event_caret must use self._configManager.get(), not ta_conf variable."""
        import inspect
        from globalPlugins.terminalAccess import GlobalPlugin
        source = inspect.getsource(GlobalPlugin.event_caret)
        assert "ta_conf" not in source, (
            "event_caret still references 'ta_conf' which is undefined. "
            "Use self._configManager.get() instead."
        )

    def test_event_caret_schedules_cursor_tracking(self):
        """event_caret should schedule cursor tracking without crashing."""
        from unittest.mock import MagicMock
        plugin = self._make_plugin()
        plugin._boundTerminal = MagicMock()
        plugin._configManager.get = lambda key, default=None: {
            'cursorTracking': True, 'quietMode': False, 'cursorDelay': 20,
        }.get(key, default)
        plugin._cursorTrackingTimer = None

        import wx
        wx.CallLater = MagicMock()

        obj = MagicMock()
        next_handler = MagicMock()

        # Should not raise NameError. nextHandler is NOT called when
        # Terminal Access is active (we handle caret tracking ourselves).
        plugin.event_caret(obj, next_handler)
        next_handler.assert_not_called()
        wx.CallLater.assert_called_once()
        # Verify the delay value passed is 20 (from configManager)
        call_args = wx.CallLater.call_args[0]
        assert call_args[0] == 20


class TestShowHelp:
    """Test script_showHelp opens the correct doc file."""

    def test_showHelp_tries_user_language_first(self):
        """script_showHelp should try the user's NVDA language before English."""
        from globalPlugins.terminalAccess import GlobalPlugin
        from unittest.mock import MagicMock, patch
        plugin = GlobalPlugin()
        gesture = MagicMock()

        mock_addon = MagicMock()
        mock_addon.path = "/fake/addon"

        with patch('addonHandler.getCodeAddon', return_value=mock_addon):
            with patch('languageHandler.getLanguage', return_value='fr'):
                with patch('os.path.isfile', side_effect=lambda p: 'fr' in p):
                    with patch('os.startfile') as mock_start:
                        plugin.script_showHelp(gesture)
                        opened = mock_start.call_args[0][0]
                        assert '/fr/' in opened.replace('\\', '/')

    def test_showHelp_falls_back_to_base_language(self):
        """For 'pt_BR', try 'pt_BR' then 'pt' then 'en'."""
        from globalPlugins.terminalAccess import GlobalPlugin
        from unittest.mock import MagicMock, patch
        plugin = GlobalPlugin()
        gesture = MagicMock()

        mock_addon = MagicMock()
        mock_addon.path = "/fake/addon"

        def isfile(p):
            # pt_BR doesn't exist, pt does
            return '/pt/' in p.replace('\\', '/') and 'pt_BR' not in p

        with patch('addonHandler.getCodeAddon', return_value=mock_addon):
            with patch('languageHandler.getLanguage', return_value='pt_BR'):
                with patch('os.path.isfile', side_effect=isfile):
                    with patch('os.startfile') as mock_start:
                        plugin.script_showHelp(gesture)
                        opened = mock_start.call_args[0][0]
                        assert '/pt/' in opened.replace('\\', '/')

    def test_showHelp_falls_back_to_english(self):
        """If user's language not found, open English doc."""
        from globalPlugins.terminalAccess import GlobalPlugin
        from unittest.mock import MagicMock, patch
        plugin = GlobalPlugin()
        gesture = MagicMock()

        mock_addon = MagicMock()
        mock_addon.path = "/fake/addon"

        def isfile(p):
            return '/en/' in p.replace('\\', '/')

        with patch('addonHandler.getCodeAddon', return_value=mock_addon):
            with patch('languageHandler.getLanguage', return_value='xx'):
                with patch('os.path.isfile', side_effect=isfile):
                    with patch('os.startfile') as mock_start:
                        plugin.script_showHelp(gesture)
                        opened = mock_start.call_args[0][0]
                        assert '/en/' in opened.replace('\\', '/')
                        assert opened.endswith('readme.html')

    def test_showHelp_does_not_call_getDocFilePath(self):
        """script_showHelp must NOT call getDocFilePath (produces doubled paths)."""
        import inspect
        from globalPlugins.terminalAccess import GlobalPlugin
        source = inspect.getsource(GlobalPlugin.script_showHelp)
        # Strip comments before checking — the method may mention it in a comment
        code_lines = [ln for ln in source.split('\n') if not ln.strip().startswith('#')]
        code_only = '\n'.join(code_lines)
        assert '.getDocFilePath(' not in code_only, (
            "getDocFilePath() call found in script_showHelp code. "
            "It produces doubled paths. Use languageHandler.getLanguage() instead."
        )
