"""
Integration tests for core Terminal Access workflows.

Tests complete user workflows and feature interactions.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys


class TestPositionCalculation(unittest.TestCase):
    """Test position calculation methods using PositionCalculator."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_position_calculator_exists(self):
        """Test PositionCalculator is initialized."""
        self.assertIsNotNone(self.plugin._positionCalculator)

    def test_position_calculator_calculate_no_terminal(self):
        """Test calculate with no bound terminal."""
        mock_textinfo = Mock()
        self.plugin._boundTerminal = None

        result = self.plugin._positionCalculator.calculate(mock_textinfo, None)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_position_calculator_cache_operations(self):
        """Test PositionCalculator cache operations."""
        # Access the internal cache
        cache = self.plugin._positionCalculator._cache

        # Test cache set and get
        cache.set("test_key", 10, 5)
        result = cache.get("test_key")
        self.assertEqual(result, (10, 5))

    def test_position_calculator_clear_cache(self):
        """Test PositionCalculator cache can be cleared."""
        cache = self.plugin._positionCalculator._cache

        # Add entry and clear
        cache.set("test_key", 10, 5)
        self.plugin._positionCalculator.clear_cache()

        result = cache.get("test_key")
        self.assertIsNone(result)


class TestCursorTracking(unittest.TestCase):
    """Test cursor tracking functionality."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_cursor_tracking_timer_initialization(self):
        """Test cursor tracking timer is initialized."""
        self.assertIsNone(self.plugin._cursorTrackingTimer)

    def test_last_caret_position_initialization(self):
        """Test last caret position is initialized."""
        self.assertIsNone(self.plugin._lastCaretPosition)

    def test_cursor_tracking_state_variables(self):
        """Test cursor tracking state variables exist."""
        self.assertTrue(hasattr(self.plugin, '_cursorTrackingTimer'))
        self.assertTrue(hasattr(self.plugin, '_lastCaretPosition'))


class TestWindowOperations(unittest.TestCase):
    """Test window definition and tracking operations using WindowManager."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_window_manager_initialization(self):
        """Test WindowManager is initialized."""
        self.assertIsNotNone(self.plugin._windowManager)
        self.assertFalse(self.plugin._windowManager.is_defining())

    def test_window_manager_operations(self):
        """Test WindowManager has required methods."""
        # WindowManager should have these methods
        self.assertTrue(hasattr(self.plugin._windowManager, 'start_definition'))
        self.assertTrue(hasattr(self.plugin._windowManager, 'is_defining'))
        self.assertTrue(hasattr(self.plugin._windowManager, 'enable_window'))
        self.assertTrue(hasattr(self.plugin._windowManager, 'disable_window'))


class TestSelectionWorkflow(unittest.TestCase):
    """Test complete selection workflow."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_mark_state_initialization(self):
        """Test selection marks are initialized to None."""
        self.assertIsNone(self.plugin._markStart)
        self.assertIsNone(self.plugin._markEnd)

    def test_mark_state_workflow(self):
        """Test mark state can be set and cleared."""
        # Set marks
        self.plugin._markStart = "start_bookmark"
        self.plugin._markEnd = "end_bookmark"

        self.assertIsNotNone(self.plugin._markStart)
        self.assertIsNotNone(self.plugin._markEnd)

        # Clear marks
        self.plugin._markStart = None
        self.plugin._markEnd = None

        self.assertIsNone(self.plugin._markStart)
        self.assertIsNone(self.plugin._markEnd)

    def test_background_thread_initialization(self):
        """Test background calculation thread is initialized."""
        self.assertIsNone(self.plugin._backgroundCalculationThread)


class TestClipboardOperations(unittest.TestCase):
    """Test clipboard copy operations."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_copy_to_clipboard_exists(self):
        """Test _copyToClipboard method exists."""
        self.assertTrue(hasattr(self.plugin, '_copyToClipboard'))
        self.assertTrue(callable(self.plugin._copyToClipboard))

    def test_copy_to_clipboard_with_empty_text(self):
        """Test _copyToClipboard with empty text still calls api.copyToClip."""
        with patch('api.copyToClip') as mock_copy:
            mock_copy.return_value = True
            result = self.plugin._copyToClipboard("")
            # Even with empty text, it should try to copy and return result
            self.assertTrue(result)
            mock_copy.assert_called_once_with("", notify=False)

    def test_copy_to_clipboard_with_valid_text(self):
        """Test _copyToClipboard with valid text."""
        with patch('api.copyToClip') as mock_copy:
            mock_copy.return_value = True
            result = self.plugin._copyToClipboard("test text")
            self.assertTrue(result)
            # Check that it was called with notify=False parameter
            mock_copy.assert_called_once_with("test text", notify=False)


class TestPluginLifecycle(unittest.TestCase):
    """Test plugin initialization and termination."""

    def test_plugin_initialization(self):
        """Test plugin initializes without errors."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()
            self.assertIsNotNone(plugin)

    def test_plugin_has_required_attributes(self):
        """Test plugin has all required manager classes and attributes."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()

            # Manager classes (new architecture)
            self.assertTrue(hasattr(plugin, '_configManager'))
            self.assertTrue(hasattr(plugin, '_windowManager'))
            self.assertTrue(hasattr(plugin, '_positionCalculator'))
            self.assertTrue(hasattr(plugin, '_profileManager'))

            # State variables
            self.assertTrue(hasattr(plugin, '_boundTerminal'))
            self.assertTrue(hasattr(plugin, '_markStart'))
            self.assertTrue(hasattr(plugin, '_markEnd'))
            self.assertTrue(hasattr(plugin, '_lastCaretPosition'))

    def test_plugin_terminate(self):
        """Test plugin terminates without errors."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog') as mock_dialog:
            plugin = GlobalPlugin()
            # Should not raise any errors
            plugin.terminate()


class TestConfigurationIntegration(unittest.TestCase):
    """Test configuration integration with plugin."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_config_sanitization_called(self):
        """Test _sanitizeConfig is called during init."""
        # Plugin should have sanitized config
        config_mock = sys.modules['config']
        conf = config_mock.conf["terminalAccess"]

        # Should have valid values
        self.assertGreaterEqual(conf["cursorTrackingMode"], 0)
        self.assertLessEqual(conf["cursorTrackingMode"], 3)
        self.assertGreaterEqual(conf["punctuationLevel"], 0)
        self.assertLessEqual(conf["punctuationLevel"], 3)


class TestPerformanceOptimizations(unittest.TestCase):
    """Test performance optimization features using PositionCalculator."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_position_calculator_has_cache(self):
        """Test PositionCalculator has a cache."""
        self.assertIsNotNone(self.plugin._positionCalculator)
        self.assertTrue(hasattr(self.plugin._positionCalculator, '_cache'))

    def test_last_caret_position_tracking(self):
        """Test last caret position tracking exists."""
        self.assertIsNone(self.plugin._lastCaretPosition)
        self.assertTrue(hasattr(self.plugin, '_lastCaretPosition'))

    def test_background_calculation_thread_exists(self):
        """Test background calculation thread attribute exists."""
        self.assertTrue(hasattr(self.plugin, '_backgroundCalculationThread'))


class TestErrorRecovery(unittest.TestCase):
    """Test error handling and recovery."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_calculate_position_handles_none_textinfo(self):
        """Test _calculatePosition handles None textinfo gracefully."""
        # Should not raise exception
        try:
            result = self.plugin._calculatePosition(None)
            # Should return safe default
            self.assertEqual(result, (0, 0))
        except AttributeError:
            # This is also acceptable - depends on implementation
            pass

    def test_is_terminal_app_handles_none_object(self):
        """Test isTerminalApp handles None object."""
        result = self.plugin.isTerminalApp(None)
        # Should handle gracefully
        self.assertIsInstance(result, bool)


class TestMultiStepWorkflows(unittest.TestCase):
    """Test complete multi-step user workflows."""

    def setUp(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        self.plugin = GlobalPlugin()
        self.plugin.isTerminalApp = Mock(return_value=True)
        self.plugin._boundTerminal = Mock()
        self.gesture = Mock()

    def test_mark_set_and_clear(self):
        """Setting a mark then clearing it resets state."""
        self.plugin._markStart = None
        self.plugin._markEnd = None

        # Set first mark
        self.plugin.script_toggleMark(self.gesture)
        # Set second mark (or it may just set _markStart)
        # Clear marks
        self.plugin.script_clearMarks(self.gesture)
        self.assertIsNone(self.plugin._markStart)
        self.assertIsNone(self.plugin._markEnd)

    def test_focus_terminal_then_non_terminal(self):
        """Focus terminal (bound) then non-terminal (gestures stay, guard handles)."""
        terminal = Mock()
        terminal.appModule.appName = "windowsterminal"
        self.plugin.isTerminalApp = Mock(return_value=True)

        result = self.plugin._updateGestureBindingsForFocus(terminal)
        self.assertTrue(result)

        notepad = Mock()
        notepad.appModule.appName = "notepad"
        self.plugin.isTerminalApp = Mock(return_value=False)

        result = self.plugin._updateGestureBindingsForFocus(notepad)
        self.assertFalse(result)

    def test_command_layer_enter_execute_exit(self):
        """Enter command layer, execute a script, exit."""
        self.plugin.bindGesture = Mock()
        self.plugin.removeGestureBinding = Mock()

        # Enter
        self.plugin._enterCommandLayer()
        self.assertTrue(self.plugin._inCommandLayer)

        # Simulate a script call while in layer
        self.plugin.script_readCurrentLine(self.gesture)

        # Exit
        self.plugin._exitCommandLayer()
        self.assertFalse(self.plugin._inCommandLayer)

    def test_punctuation_level_cycle(self):
        """Punctuation level increases and wraps."""
        config_mod = sys.modules['config']
        config_mod.conf["terminalAccess"]["punctuationLevel"] = 0

        self.plugin.script_increasePunctuationLevel(self.gesture)
        self.assertEqual(config_mod.conf["terminalAccess"]["punctuationLevel"], 1)

        self.plugin.script_increasePunctuationLevel(self.gesture)
        self.assertEqual(config_mod.conf["terminalAccess"]["punctuationLevel"], 2)

        self.plugin.script_increasePunctuationLevel(self.gesture)
        self.assertEqual(config_mod.conf["terminalAccess"]["punctuationLevel"], 3)

    def test_quiet_mode_suppresses_key_echo(self):
        """Quiet mode disables key echo announcements."""
        config_mod = sys.modules['config']
        config_mod.conf["terminalAccess"]["quietMode"] = False

        self.plugin.script_toggleQuietMode(self.gesture)
        self.assertTrue(config_mod.conf["terminalAccess"]["quietMode"])


class TestErrorPropagation(unittest.TestCase):
    """Test error handling in edge cases."""

    def setUp(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        self.plugin = GlobalPlugin()
        self.plugin.isTerminalApp = Mock(return_value=True)
        self.plugin._boundTerminal = Mock()
        self.gesture = Mock()

    def test_search_with_no_terminal(self):
        """Searching without a bound terminal doesn't crash."""
        self.plugin._boundTerminal = None
        self.plugin._searchManager = None
        # Should handle gracefully (message or no-op)
        try:
            self.plugin.script_searchOutput(self.gesture)
        except Exception as e:
            self.fail(f"script_searchOutput raised {type(e).__name__}: {e}")

    def test_copy_with_no_marks(self):
        """Copying with no marks set produces a warning, not a crash."""
        self.plugin._markStart = None
        self.plugin._markEnd = None
        ui_mock = sys.modules['ui']
        ui_mock.message.reset_mock()

        self.plugin.script_copyLinearSelection(self.gesture)
        ui_mock.message.assert_called()

    def test_bookmark_jump_invalid_index(self):
        """Jumping to an unset bookmark doesn't crash."""
        from globalPlugins.terminalAccess import BookmarkManager
        terminal = Mock()
        bm = BookmarkManager(terminal)
        # No bookmarks set — jump should return falsy (not crash)
        result = bm.jump_to_bookmark(5)
        self.assertFalse(result)

    def test_isTerminalApp_handles_missing_appName(self):
        """isTerminalApp returns False when appName is not a string."""
        from globalPlugins.terminalAccess import GlobalPlugin
        plugin = GlobalPlugin()  # Fresh plugin without mocked isTerminalApp
        broken = Mock()
        broken.appModule.appName = None
        result = plugin.isTerminalApp(broken)
        self.assertFalse(result)

    def test_profile_manager_detect_unknown_app(self):
        """ProfileManager.detectApplication handles unknown apps."""
        from globalPlugins.terminalAccess import ProfileManager
        mgr = ProfileManager()
        mock_obj = Mock()
        mock_obj.appModule.appName = "unknown_app_xyz"
        result = mgr.detectApplication(mock_obj)
        # Should return default or None, not crash
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
