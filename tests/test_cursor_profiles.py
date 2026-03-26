"""Tests for cursor tracking, window monitoring debounce, and application profiles."""
import time
from unittest.mock import Mock, MagicMock, patch

import pytest

from lib.profiles import ProfileManager, ApplicationProfile, _BUILTIN_PROFILE_NAMES
from lib.config import CT_STANDARD, CT_WINDOW, CT_OFF, PUNCT_MOST


# ---------------------------------------------------------------------------
# WindowMonitor debouncing
# ---------------------------------------------------------------------------

class TestWindowMonitorDebounce:
    """Tests for WindowMonitor debounce behavior."""

    def _make_monitor(self, debounce_ms=100):
        from lib.window_management import WindowMonitor
        terminal = Mock()
        pos_calc = Mock()
        monitor = WindowMonitor(terminal, pos_calc, debounce_ms=debounce_ms)
        return monitor

    def test_window_monitor_debounce(self):
        """Rapid updates within the debounce interval should be coalesced."""
        monitor = self._make_monitor(debounce_ms=200)
        announced = []
        monitor._announce_change = lambda name, content, old: announced.append(content)

        # Simulate rapid updates that arrive faster than debounce interval
        monitor.debounce_update("build", "line 1")
        monitor.debounce_update("build", "line 2")
        monitor.debounce_update("build", "line 3")

        # Only the last update should be pending (not all three)
        assert len(announced) <= 1, "Rapid updates should be coalesced by debounce"

    def test_window_monitor_different_content(self):
        """Different content arriving after debounce interval should be announced."""
        monitor = self._make_monitor(debounce_ms=10)
        announced = []
        monitor._announce_change = lambda name, content, old: announced.append(content)

        monitor.debounce_update("build", "output A")
        time.sleep(0.05)  # Wait past debounce
        monitor.debounce_update("build", "output B")
        time.sleep(0.05)  # Wait past debounce

        assert len(announced) >= 2, "Different content after debounce should each be announced"

    def test_window_monitor_same_content_suppressed(self):
        """Identical content should be suppressed even after debounce interval."""
        monitor = self._make_monitor(debounce_ms=10)
        announced = []
        monitor._announce_change = lambda name, content, old: announced.append(content)

        monitor.debounce_update("build", "same output")
        time.sleep(0.05)
        monitor.debounce_update("build", "same output")
        time.sleep(0.05)

        # The second identical update should be suppressed
        assert announced.count("same output") <= 1, "Same content should not be announced twice"


# ---------------------------------------------------------------------------
# Focused pane prioritization for multiplexers
# ---------------------------------------------------------------------------

class TestFocusedPanePrioritization:
    """Tests for tmux/screen focused pane filtering."""

    def test_tmux_focused_pane_only(self):
        """tmux profile should have focusedPaneOnly setting, default True."""
        pm = ProfileManager()
        tmux = pm.get_profile('tmux')
        assert tmux is not None, "tmux profile must exist"
        assert hasattr(tmux, 'focusedPaneOnly'), "tmux profile must have focusedPaneOnly attribute"
        assert tmux.focusedPaneOnly is True, "focusedPaneOnly should default to True for tmux"


# ---------------------------------------------------------------------------
# Profile existence and configuration
# ---------------------------------------------------------------------------

class TestProfileTemplates:
    """Tests for new built-in profile templates."""

    def setup_method(self):
        self.pm = ProfileManager()

    def test_kubectl_profile_exists(self):
        """kubectl profile should exist in built-in profiles."""
        profile = self.pm.get_profile('kubectl')
        assert profile is not None, "kubectl profile must exist"
        assert profile.appName == 'kubectl'

    def test_npm_profile_exists(self):
        """npm profile should exist in built-in profiles."""
        profile = self.pm.get_profile('npm')
        assert profile is not None, "npm profile must exist"
        assert profile.appName == 'npm'

    def test_pytest_profile_exists(self):
        """pytest profile should exist in built-in profiles."""
        profile = self.pm.get_profile('pytest')
        assert profile is not None, "pytest profile must exist"
        assert profile.appName == 'pytest'

    def test_docker_profile_exists(self):
        """docker profile should exist in built-in profiles."""
        profile = self.pm.get_profile('docker')
        assert profile is not None, "docker profile must exist"
        assert profile.appName == 'docker'

    def test_kubectl_profile_punctuation(self):
        """kubectl profile should use MOST punctuation for log parsing."""
        profile = self.pm.get_profile('kubectl')
        assert profile is not None
        assert profile.punctuationLevel == PUNCT_MOST

    def test_cargo_profile_enhanced(self):
        """cargo profile should exist and have error-aware settings."""
        profile = self.pm.get_profile('cargo')
        assert profile is not None, "cargo profile must exist"
        assert profile.punctuationLevel == PUNCT_MOST, "cargo should use MOST punctuation for compiler output"


# ---------------------------------------------------------------------------
# Profile detection from window title
# ---------------------------------------------------------------------------

class TestProfileDetection:
    """Tests for detecting profiles from window title patterns."""

    def setup_method(self):
        self.pm = ProfileManager()

    def _make_focus(self, title, app_name="windowsterminal"):
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = app_name
        obj.name = title
        return obj

    def test_pytest_profile_detection(self):
        """Window title containing 'pytest' should trigger pytest profile."""
        focus = self._make_focus("pytest tests/test_foo.py")
        detected = self.pm.detect_application(focus)
        assert detected == 'pytest'

    def test_profile_detection_kubectl_logs(self):
        """Window title containing 'kubectl logs' should trigger kubectl profile."""
        focus = self._make_focus("kubectl logs my-pod")
        detected = self.pm.detect_application(focus)
        assert detected == 'kubectl'

    def test_profile_detection_npm_run(self):
        """Window title containing 'npm run' should trigger npm profile."""
        focus = self._make_focus("npm run dev")
        detected = self.pm.detect_application(focus)
        assert detected == 'npm'


# ---------------------------------------------------------------------------
# Cursor tracking mode names
# ---------------------------------------------------------------------------

class TestCursorModeNames:
    """Tests for cursor tracking mode display names."""

    def test_cursor_mode_names(self):
        """Mode names should be clear, user-friendly strings."""
        from lib.config import CURSOR_MODE_NAMES

        assert CT_OFF in CURSOR_MODE_NAMES
        assert CT_STANDARD in CURSOR_MODE_NAMES
        assert CT_WINDOW in CURSOR_MODE_NAMES

        # Names should follow the pattern "Cursor tracking: <Mode>"
        assert "Off" in CURSOR_MODE_NAMES[CT_OFF]
        assert "Standard" in CURSOR_MODE_NAMES[CT_STANDARD]
        assert "Window" in CURSOR_MODE_NAMES[CT_WINDOW]
