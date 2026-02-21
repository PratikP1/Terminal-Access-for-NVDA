"""
Tests for global plugin initialization error handling.
"""
import sys
import pytest
from unittest.mock import MagicMock, Mock


def test_global_plugin_initialization_without_gui():
    """Test that GlobalPlugin.__init__ handles missing GUI gracefully."""
    # Save the original gui module
    original_gui = sys.modules.get('gui')

    try:
        # Replace gui.settingsDialogs with a mock that raises AttributeError
        gui_mock = MagicMock()
        gui_mock.settingsDialogs.NVDASettingsDialog.categoryClasses = MagicMock()
        gui_mock.settingsDialogs.NVDASettingsDialog.categoryClasses.append = MagicMock(
            side_effect=AttributeError("GUI not initialized")
        )
        sys.modules['gui'] = gui_mock

        # Import should still succeed despite the AttributeError
        from globalPlugins import terminalAccess

        # Create the plugin - this should not raise an exception
        plugin = terminalAccess.GlobalPlugin()

        # Verify plugin was created successfully
        assert plugin is not None
        assert hasattr(plugin, '_configManager')
        assert hasattr(plugin, '_windowManager')
        assert hasattr(plugin, '_positionCalculator')

    finally:
        # Restore original gui module
        if original_gui is not None:
            sys.modules['gui'] = original_gui


def test_global_plugin_initialization_with_gui():
    """Test that GlobalPlugin.__init__ works correctly when GUI is available."""
    # The module is already imported in conftest, so we test with existing setup
    from globalPlugins import terminalAccess

    # Create plugin - this should succeed
    plugin = terminalAccess.GlobalPlugin()

    # Verify plugin was created successfully
    assert plugin is not None
    assert hasattr(plugin, '_configManager')
    assert hasattr(plugin, '_windowManager')
    assert hasattr(plugin, '_positionCalculator')


def test_global_plugin_initialization_with_type_error():
    """Test that GlobalPlugin.__init__ handles TypeError from GUI."""
    # Save the original gui module
    original_gui = sys.modules.get('gui')

    try:
        # Replace gui.settingsDialogs with a mock that raises TypeError
        gui_mock = MagicMock()
        gui_mock.settingsDialogs.NVDASettingsDialog.categoryClasses = MagicMock()
        gui_mock.settingsDialogs.NVDASettingsDialog.categoryClasses.append = MagicMock(
            side_effect=TypeError("Invalid operation")
        )
        sys.modules['gui'] = gui_mock

        # Import and create plugin - should not raise
        from globalPlugins import terminalAccess
        plugin = terminalAccess.GlobalPlugin()

        # Verify plugin was created successfully
        assert plugin is not None

    finally:
        # Restore original gui module
        if original_gui is not None:
            sys.modules['gui'] = original_gui


def test_global_plugin_initialization_with_runtime_error():
    """Test that GlobalPlugin.__init__ handles RuntimeError from GUI."""
    # Save the original gui module
    original_gui = sys.modules.get('gui')

    try:
        # Replace gui.settingsDialogs with a mock that raises RuntimeError
        gui_mock = MagicMock()
        gui_mock.settingsDialogs.NVDASettingsDialog.categoryClasses = MagicMock()
        gui_mock.settingsDialogs.NVDASettingsDialog.categoryClasses.append = MagicMock(
            side_effect=RuntimeError("Runtime error during initialization")
        )
        sys.modules['gui'] = gui_mock

        # Import and create plugin - should not raise
        from globalPlugins import terminalAccess
        plugin = terminalAccess.GlobalPlugin()

        # Verify plugin was created successfully
        assert plugin is not None

    finally:
        # Restore original gui module
        if original_gui is not None:
            sys.modules['gui'] = original_gui


def test_script_open_settings_with_gui_error():
    """Test that script_openSettings handles GUI errors gracefully."""
    from globalPlugins import terminalAccess

    # Get existing mocks
    wx_mock = sys.modules['wx']

    # Store original CallAfter
    original_call_after = wx_mock.CallAfter

    try:
        # Make CallAfter raise an error
        wx_mock.CallAfter = MagicMock(side_effect=AttributeError("GUI not available"))

        # Create plugin
        plugin = terminalAccess.GlobalPlugin()

        # Create a mock gesture
        gesture = Mock()
        gesture.send = Mock()

        # Mock isTerminalApp to return True
        plugin.isTerminalApp = Mock(return_value=True)

        # Call script_openSettings - should not raise an exception
        try:
            plugin.script_openSettings(gesture)
            # If we get here without exception, the error handling works
            assert True
        except (AttributeError, TypeError, RuntimeError):
            # If an exception is raised, the error handling is not working
            pytest.fail("script_openSettings should handle GUI errors gracefully")

    finally:
        # Restore CallAfter
        wx_mock.CallAfter = original_call_after
