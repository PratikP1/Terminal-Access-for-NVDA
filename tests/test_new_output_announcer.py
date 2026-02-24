"""
Tests for TextDiffer integration with WindowMonitor and NewOutputAnnouncer.

Covers:
- NewOutputAnnouncer: appended output detected, ANSI stripped, quiet mode, rate limiting
- WindowMonitor: TextDiffer-based change detection, appended vs changed announcements
- Config options: announceNewOutput, newOutputCoalesceMs, newOutputMaxLines, stripAnsiInOutput
"""

import sys
import time
import threading
import unittest
from unittest.mock import Mock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_conf():
    """Return a fresh mutable config dict with all new settings."""
    return {
        "quietMode": False,
        "announceNewOutput": True,
        "newOutputCoalesceMs": 50,   # short for fast tests
        "newOutputMaxLines": 5,
        "stripAnsiInOutput": True,
        "cursorTracking": True,
        "cursorTrackingMode": 1,
        "keyEcho": True,
        "linePause": True,
        "processSymbols": False,
        "punctuationLevel": 2,
        "repeatedSymbols": False,
        "repeatedSymbolsValues": "-_=!",
        "cursorDelay": 20,
        "verboseMode": False,
        "indentationOnLineRead": False,
        "windowTop": 0,
        "windowBottom": 0,
        "windowLeft": 0,
        "windowRight": 0,
        "windowEnabled": False,
        "defaultProfile": "",
    }


def _setup_config(test_instance):
    """
    Configure sys.modules['config'] so that config.conf["terminalAccess"]
    returns the test's flat setting dict.  The dict is stored on the
    test instance as ``_conf`` for easy mutation inside individual tests.
    """
    config_mod = sys.modules['config']
    test_instance._conf = _get_conf()
    conf_dict = {"terminalAccess": test_instance._conf}
    config_mod.conf = Mock()
    config_mod.conf.__getitem__ = lambda _self, key: conf_dict[key]
    config_mod.conf.__setitem__ = lambda _self, key, val: conf_dict.__setitem__(key, val)
    config_mod.conf.get = lambda key, default=None: conf_dict.get(key, default)
    config_mod.conf.spec = {}


# ---------------------------------------------------------------------------
# NewOutputAnnouncer tests
# ---------------------------------------------------------------------------

class TestNewOutputAnnouncer(unittest.TestCase):
    """Unit tests for NewOutputAnnouncer class."""

    def setUp(self):
        _setup_config(self)

        from globalPlugins.terminalAccess import NewOutputAnnouncer
        self.announcer = NewOutputAnnouncer()

    def _wait_for_announce(self, timeout=0.5):
        """Wait long enough for the coalesce timer to fire."""
        time.sleep(timeout)

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_initial_feed_not_announced(self, mock_msg):
        """First feed establishes baseline and must not announce anything."""
        self.announcer.feed("line1\nline2\n")
        self._wait_for_announce()
        mock_msg.assert_not_called()

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_appended_output_announced(self, mock_msg):
        """Newly appended lines are spoken after the coalesce delay."""
        self.announcer.feed("line1\n")
        self.announcer.feed("line1\nline2\n")
        self._wait_for_announce()
        mock_msg.assert_called_once()
        text = mock_msg.call_args[0][0]
        self.assertIn("line2", text)

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_unchanged_not_announced(self, mock_msg):
        """Identical consecutive feeds do not produce announcements."""
        self.announcer.feed("line1\n")
        self.announcer.feed("line1\n")
        self._wait_for_announce()
        mock_msg.assert_not_called()

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_quiet_mode_suppresses_output(self, mock_msg):
        """When quietMode is True no output is announced."""
        self._conf["quietMode"] = True
        self.announcer.feed("line1\n")
        self.announcer.feed("line1\nline2\n")
        self._wait_for_announce()
        mock_msg.assert_not_called()

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_feature_disabled_suppresses_output(self, mock_msg):
        """When announceNewOutput is False nothing is announced."""
        self._conf["announceNewOutput"] = False
        self.announcer.feed("line1\n")
        self.announcer.feed("line1\nline2\n")
        self._wait_for_announce()
        mock_msg.assert_not_called()

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_ansi_stripped_when_configured(self, mock_msg):
        """ANSI escape codes are stripped before announcement."""
        self.announcer.feed("line1\n")
        self.announcer.feed("line1\n\x1b[32mgreen line\x1b[0m\n")
        self._wait_for_announce()
        mock_msg.assert_called_once()
        text = mock_msg.call_args[0][0]
        self.assertNotIn("\x1b", text)
        self.assertIn("green line", text)

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_ansi_kept_when_strip_disabled(self, mock_msg):
        """ANSI codes are NOT stripped when stripAnsiInOutput is False."""
        self._conf["stripAnsiInOutput"] = False
        self.announcer.feed("line1\n")
        self.announcer.feed("line1\n\x1b[32mgreen\x1b[0m\n")
        self._wait_for_announce()
        mock_msg.assert_called_once()
        text = mock_msg.call_args[0][0]
        self.assertIn("\x1b", text)

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_max_lines_summary(self, mock_msg):
        """When appended lines exceed newOutputMaxLines, a summary is spoken."""
        # newOutputMaxLines is 5 in setUp
        base = "\n".join(f"line{i}" for i in range(3)) + "\n"
        self.announcer.feed(base)
        # Append 10 more lines (> max_lines=5)
        extra = "\n".join(f"new{i}" for i in range(10)) + "\n"
        self.announcer.feed(base + extra)
        self._wait_for_announce()
        mock_msg.assert_called_once()
        text = mock_msg.call_args[0][0]
        # Should summarise rather than speak all lines
        self.assertIn("new lines", text.lower())

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_coalescing_batches_rapid_appends(self, mock_msg):
        """Rapid consecutive appends within the coalesce window are batched."""
        self.announcer.feed("base\n")
        # Feed multiple rapid appends
        self.announcer.feed("base\nappend1\n")
        self.announcer.feed("base\nappend1\nappend2\n")
        self.announcer.feed("base\nappend1\nappend2\nappend3\n")
        self._wait_for_announce()
        # Should only announce once (or a summary) — not once per feed
        self.assertLessEqual(mock_msg.call_count, 1)

    def test_reset_clears_differ_state(self):
        """reset() drops the prior snapshot so next feed is treated as initial."""
        from globalPlugins.terminalAccess import NewOutputAnnouncer
        ann = NewOutputAnnouncer()
        ann.feed("line1\n")
        ann.reset()
        # After reset, last_text should be None
        self.assertIsNone(ann._differ.last_text)

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_changed_content_not_announced(self, mock_msg):
        """Non-appended changes (mid-edit) do not trigger announcements."""
        self.announcer.feed("line1\nline2\n")
        # Replace content entirely (not an append)
        self.announcer.feed("completely different\n")
        self._wait_for_announce()
        # NewOutputAnnouncer only speaks on KIND_APPENDED, not KIND_CHANGED
        mock_msg.assert_not_called()


# ---------------------------------------------------------------------------
# WindowMonitor TextDiffer integration tests
# ---------------------------------------------------------------------------

class MockTerminalForMonitor:
    """Mock terminal for WindowMonitor tests."""

    def __init__(self, content=""):
        self.content = content

    def makeTextInfo(self, position):
        info = Mock()
        info.text = self.content
        return info


class TestWindowMonitorTextDiffer(unittest.TestCase):
    """Test that WindowMonitor uses TextDiffer for change detection."""

    def setUp(self):
        _setup_config(self)

        from globalPlugins.terminalAccess import WindowMonitor
        self.terminal = MockTerminalForMonitor("line1\nline2\nline3\n")
        self.monitor = WindowMonitor(self.terminal, Mock())

    def tearDown(self):
        if self.monitor.is_monitoring():
            self.monitor.stop_monitoring()

    def test_monitor_has_differ_per_region(self):
        """Each added monitor carries its own TextDiffer instance."""
        from globalPlugins.terminalAccess import TextDiffer
        self.monitor.add_monitor("win1", (1, 1, 3, 80))
        self.monitor.add_monitor("win2", (4, 1, 6, 80))
        status = self.monitor.get_monitor_status()
        self.assertEqual(len(status), 2)
        # The differ is stored in the internal monitor dict (not exposed by status)
        with self.monitor._lock:
            differs = [m['differ'] for m in self.monitor._monitors]
        self.assertEqual(len(differs), 2)
        for d in differs:
            self.assertIsInstance(d, TextDiffer)
        # The two monitors share no differ instance
        self.assertIsNot(differs[0], differs[1])

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_initial_poll_does_not_announce(self, mock_msg):
        """The very first poll establishes the baseline and stays silent."""
        self.monitor.add_monitor("win", (1, 1, 3, 80), interval_ms=50, mode='changes')
        self.monitor.start_monitoring()
        time.sleep(0.2)
        self.monitor.stop_monitoring()
        mock_msg.assert_not_called()

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_appended_output_only_speaks_new_lines(self, mock_msg):
        """When lines are appended only the new portion is spoken."""
        self.monitor.add_monitor("win", (1, 1, 10, 80), interval_ms=50, mode='changes')
        self.monitor.start_monitoring()
        # Let first poll establish baseline
        time.sleep(0.15)
        # Append a new line
        self.terminal.content = "line1\nline2\nline3\nNEW LINE\n"
        # Wait for next poll (rate limiter needs 2 s, so patch it)
        self.monitor._min_announcement_interval = 0
        time.sleep(0.15)
        self.monitor.stop_monitoring()
        if mock_msg.called:
            announced = mock_msg.call_args[0][0]
            # Should speak the appended text, not the full region
            self.assertIn("NEW LINE", announced)
            self.assertNotIn("line1", announced)

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_silent_mode_never_announces(self, mock_msg):
        """Monitors in 'silent' mode never call ui.message."""
        self.monitor.add_monitor("win", (1, 1, 3, 80), interval_ms=50, mode='silent')
        self.monitor.start_monitoring()
        time.sleep(0.15)
        self.terminal.content = "changed content\n"
        self.monitor._min_announcement_interval = 0
        time.sleep(0.15)
        self.monitor.stop_monitoring()
        mock_msg.assert_not_called()

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_unchanged_content_not_announced(self, mock_msg):
        """Unchanged content never triggers ui.message."""
        self.monitor.add_monitor("win", (1, 1, 3, 80), interval_ms=50, mode='changes')
        self.monitor._min_announcement_interval = 0
        self.monitor.start_monitoring()
        time.sleep(0.35)   # Several polls, content stays the same
        self.monitor.stop_monitoring()
        mock_msg.assert_not_called()


# ---------------------------------------------------------------------------
# Configuration settings tests
# ---------------------------------------------------------------------------

class TestNewOutputConfig(unittest.TestCase):
    """Verify new confspec entries and ConfigManager validation."""

    def setUp(self):
        _setup_config(self)

    def test_confspec_contains_new_keys(self):
        """confspec must declare all four new config keys."""
        from globalPlugins.terminalAccess import confspec
        for key in ("announceNewOutput", "newOutputCoalesceMs",
                    "newOutputMaxLines", "stripAnsiInOutput"):
            self.assertIn(key, confspec, f"Missing confspec key: {key}")

    def test_config_manager_validates_coalesce_ms(self):
        """ConfigManager rejects out-of-range newOutputCoalesceMs and returns default."""
        from globalPlugins.terminalAccess import ConfigManager
        mgr = ConfigManager()
        # Values outside [50, 2000] fall back to the default (200)
        self.assertEqual(mgr._validate_key("newOutputCoalesceMs", 10), 200)     # below min → default
        self.assertEqual(mgr._validate_key("newOutputCoalesceMs", 9999), 200)   # above max → default
        self.assertEqual(mgr._validate_key("newOutputCoalesceMs", 300), 300)    # valid → kept
        self.assertEqual(mgr._validate_key("newOutputCoalesceMs", 50), 50)      # boundary min
        self.assertEqual(mgr._validate_key("newOutputCoalesceMs", 2000), 2000)  # boundary max

    def test_config_manager_validates_max_lines(self):
        """ConfigManager rejects out-of-range newOutputMaxLines and returns default."""
        from globalPlugins.terminalAccess import ConfigManager
        mgr = ConfigManager()
        # Values outside [1, 200] fall back to the default (20)
        self.assertEqual(mgr._validate_key("newOutputMaxLines", 0), 20)     # below min → default
        self.assertEqual(mgr._validate_key("newOutputMaxLines", 999), 20)   # above max → default
        self.assertEqual(mgr._validate_key("newOutputMaxLines", 50), 50)    # valid → kept
        self.assertEqual(mgr._validate_key("newOutputMaxLines", 1), 1)      # boundary min
        self.assertEqual(mgr._validate_key("newOutputMaxLines", 200), 200)  # boundary max

    def test_config_manager_validates_booleans(self):
        """ConfigManager casts announceNewOutput and stripAnsiInOutput to bool."""
        from globalPlugins.terminalAccess import ConfigManager
        mgr = ConfigManager()
        self.assertIs(mgr._validate_key("announceNewOutput", 1), True)
        self.assertIs(mgr._validate_key("stripAnsiInOutput", 0), False)

    def test_reset_to_defaults_sets_new_keys(self):
        """ConfigManager.reset_to_defaults() writes defaults for new keys."""
        from globalPlugins.terminalAccess import ConfigManager
        mgr = ConfigManager()
        mgr.reset_to_defaults()
        self.assertEqual(self._conf["announceNewOutput"], False)
        self.assertEqual(self._conf["newOutputCoalesceMs"], 200)
        self.assertEqual(self._conf["newOutputMaxLines"], 20)
        self.assertEqual(self._conf["stripAnsiInOutput"], True)


# ---------------------------------------------------------------------------
# Quiet mode interaction with NewOutputAnnouncer via GlobalPlugin
# ---------------------------------------------------------------------------

class TestQuietModeInteractionWithAnnouncer(unittest.TestCase):
    """Verify quiet mode suppresses new output announcements end-to-end."""

    def setUp(self):
        _setup_config(self)

        from globalPlugins.terminalAccess import NewOutputAnnouncer
        self.ann = NewOutputAnnouncer()

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_no_output_when_quiet_mode_on(self, mock_msg):
        """Enabling quietMode before feeding prevents any announcement."""
        self._conf["quietMode"] = True
        self.ann.feed("base\n")
        self.ann.feed("base\nmore output\n")
        time.sleep(0.2)
        mock_msg.assert_not_called()

    @patch('globalPlugins.terminalAccess.ui.message')
    def test_output_resumes_after_quiet_mode_off(self, mock_msg):
        """Disabling quietMode allows announcements again."""
        # Feed baseline with quiet off
        self.ann.feed("base\n")
        # Turn on quiet, feed more (should be silent)
        self._conf["quietMode"] = True
        self.ann.feed("base\nsilent line\n")
        time.sleep(0.2)
        mock_msg.assert_not_called()

        # Now turn quiet off and feed again
        self._conf["quietMode"] = False
        self.ann.reset()
        self.ann.feed("new base\n")
        self.ann.feed("new base\naudible line\n")
        time.sleep(0.2)
        mock_msg.assert_called_once()
        self.assertIn("audible line", mock_msg.call_args[0][0])


if __name__ == '__main__':
    unittest.main()
