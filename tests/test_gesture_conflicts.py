"""Tests for gesture conflict detection."""
import sys
from unittest.mock import Mock, MagicMock, patch, call
import pytest


class TestGestureConflictDetector:
    """Test the GestureConflictDetector utility class."""

    def test_no_conflicts_when_no_other_plugins(self):
        """No conflicts when Terminal Access is the only global plugin."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()
        # With no other plugins loaded, there should be no conflicts
        conflicts = detector.detect_conflicts(
            our_gestures={"kb:NVDA+k": "readCurrentWord"},
            other_plugins=[]
        )
        assert conflicts == []

    def test_detects_conflict_with_other_plugin(self):
        """Detects when another plugin binds the same gesture."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()

        other_plugin = Mock()
        other_plugin.__class__.__name__ = "BrailleExtender"
        other_plugin._gestureMap = {"kb:NVDA+k": "someBrailleFunction"}

        conflicts = detector.detect_conflicts(
            our_gestures={"kb:NVDA+k": "readCurrentWord"},
            other_plugins=[other_plugin]
        )
        assert len(conflicts) == 1
        assert conflicts[0]["gesture"] == "kb:NVDA+k"
        assert conflicts[0]["our_script"] == "readCurrentWord"
        assert conflicts[0]["other_plugin"] == "BrailleExtender"

    def test_no_conflict_when_different_gestures(self):
        """No conflict when plugins bind different gestures."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()

        other_plugin = Mock()
        other_plugin.__class__.__name__ = "SomeAddon"
        other_plugin._gestureMap = {"kb:NVDA+z": "someFunction"}

        conflicts = detector.detect_conflicts(
            our_gestures={"kb:NVDA+k": "readCurrentWord"},
            other_plugins=[other_plugin]
        )
        assert conflicts == []

    def test_multiple_conflicts_detected(self):
        """Detects multiple conflicts at once."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()

        other = Mock()
        other.__class__.__name__ = "OtherAddon"
        other._gestureMap = {
            "kb:NVDA+k": "otherFunc1",
            "kb:NVDA+h": "otherFunc2",
        }

        conflicts = detector.detect_conflicts(
            our_gestures={
                "kb:NVDA+k": "readCurrentWord",
                "kb:NVDA+h": "previousCommand",
                "kb:NVDA+u": "readPreviousLine",
            },
            other_plugins=[other]
        )
        assert len(conflicts) == 2

    def test_conflict_with_multiple_plugins(self):
        """Detects conflicts across multiple other plugins."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()

        plugin1 = Mock()
        plugin1.__class__.__name__ = "Addon1"
        plugin1._gestureMap = {"kb:NVDA+k": "func1"}

        plugin2 = Mock()
        plugin2.__class__.__name__ = "Addon2"
        plugin2._gestureMap = {"kb:NVDA+h": "func2"}

        conflicts = detector.detect_conflicts(
            our_gestures={
                "kb:NVDA+k": "readCurrentWord",
                "kb:NVDA+h": "previousCommand",
            },
            other_plugins=[plugin1, plugin2]
        )
        assert len(conflicts) == 2

    def test_format_conflict_report(self):
        """Format conflicts into a readable report string."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()

        conflicts = [
            {"gesture": "kb:NVDA+k", "our_script": "readCurrentWord",
             "other_plugin": "BrailleExtender", "other_script": "toggleBraille"},
        ]
        report = detector.format_report(conflicts)
        assert "NVDA+K" in report or "NVDA+k" in report
        assert "BrailleExtender" in report
        assert "readCurrentWord" in report

    def test_format_report_empty_when_no_conflicts(self):
        """Empty report when no conflicts."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()
        report = detector.format_report([])
        assert report == ""

    def test_handles_plugin_without_gesture_map(self):
        """Gracefully handles plugins that don't have _gestureMap."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()

        other = Mock(spec=[])  # No attributes at all
        other.__class__ = type("SimplePlugin", (), {})

        conflicts = detector.detect_conflicts(
            our_gestures={"kb:NVDA+k": "readCurrentWord"},
            other_plugins=[other]
        )
        assert conflicts == []

    def test_skips_self_in_plugin_list(self):
        """Doesn't report conflicts with ourselves."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()

        our_plugin = Mock()
        our_plugin.__class__.__name__ = "GlobalPlugin"  # Our own class name
        our_plugin._gestureMap = {"kb:NVDA+k": "readCurrentWord"}

        conflicts = detector.detect_conflicts(
            our_gestures={"kb:NVDA+k": "readCurrentWord"},
            other_plugins=[our_plugin],
            our_class_name="GlobalPlugin"
        )
        assert conflicts == []

    def test_excluded_gestures_not_reported(self):
        """Gestures the user has already excluded don't show as conflicts."""
        from lib.gesture_conflicts import GestureConflictDetector
        detector = GestureConflictDetector()

        other = Mock()
        other.__class__.__name__ = "OtherAddon"
        other._gestureMap = {"kb:NVDA+k": "otherFunc"}

        conflicts = detector.detect_conflicts(
            our_gestures={"kb:NVDA+k": "readCurrentWord"},
            other_plugins=[other],
            excluded_gestures={"kb:NVDA+k"}
        )
        assert conflicts == []


class TestGestureConflictIntegration:
    """Test that conflict detection is wired into the plugin lifecycle."""

    def _make_plugin(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        return GlobalPlugin()

    def test_announceHelpIfNeeded_calls_checkConflictsSilently(self):
        """First terminal focus should trigger silent conflict check."""
        plugin = self._make_plugin()
        plugin._checkConflictsSilently = MagicMock()
        plugin.announcedHelp = False
        import ui
        ui.message = MagicMock()

        plugin._announceHelpIfNeeded('windowsterminal')

        plugin._checkConflictsSilently.assert_called_once()

    def test_announceHelpIfNeeded_new_app_triggers_conflict_check(self):
        """Switching to a new terminal app should re-trigger conflict check."""
        plugin = self._make_plugin()
        plugin._checkConflictsSilently = MagicMock()
        plugin.announcedHelp = True
        plugin.lastTerminalAppName = 'putty'
        import ui
        ui.message = MagicMock()

        plugin._announceHelpIfNeeded('windowsterminal')

        plugin._checkConflictsSilently.assert_called_once()

    def test_announceHelpIfNeeded_same_app_no_conflict_check(self):
        """Re-focusing the same terminal should NOT trigger conflict check."""
        plugin = self._make_plugin()
        plugin._checkConflictsSilently = MagicMock()
        plugin.announcedHelp = True
        plugin.lastTerminalAppName = 'windowsterminal'

        plugin._announceHelpIfNeeded('windowsterminal')

        plugin._checkConflictsSilently.assert_not_called()

    def test_checkConflictsSilently_no_conflicts_no_warning(self):
        """Silent check with no conflicts should NOT schedule a warning."""
        import globalPluginHandler
        globalPluginHandler.runningPlugins = []
        import wx
        wx.CallLater = MagicMock()
        plugin = self._make_plugin()
        plugin._conflictDetector = MagicMock()
        plugin._conflictDetector.detect_conflicts.return_value = []

        plugin._checkConflictsSilently()

        wx.CallLater.assert_not_called()

    def test_checkConflictsSilently_with_conflicts_schedules_warning(self):
        """Silent check with conflicts should schedule a wx.CallLater warning."""
        import globalPluginHandler
        globalPluginHandler.runningPlugins = []
        import wx
        call_later_mock = MagicMock()
        wx.CallLater = call_later_mock
        import ui
        plugin = self._make_plugin()
        plugin._conflictDetector = MagicMock()
        plugin._conflictDetector.detect_conflicts.return_value = [
            {"gesture": "kb:NVDA+k", "our_script": "readCurrentWord",
             "other_plugin": "OtherAddon", "other_script": "someFunc"},
        ]

        plugin._checkConflictsSilently()

        call_later_mock.assert_called_once()
        call_args = call_later_mock.call_args
        assert call_args[0][0] == 2000  # delay in ms
        assert call_args[0][1] is ui.message  # callback is ui.message
