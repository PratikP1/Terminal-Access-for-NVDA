"""
Tests for the TerminalAccessTerminal overlay class.

This overlay replaces NVDA's LiveText-based terminal handling by hooking
into chooseNVDAObjectOverlayClasses. It overrides _reportNewLines,
event_textChange, and event_typedCharacter at the NVDAObject level
instead of intercepting events at the GlobalPlugin level.
"""
import sys
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call

import pytest


# --- Mock infrastructure for NVDAObject overlay testing ---

class MockTextInfo:
    """Minimal TextInfo mock for overlay tests."""
    def __init__(self, text=""):
        self.text = text
        self.bookmark = Mock()

    def copy(self):
        m = MockTextInfo(self.text)
        m.bookmark = self.bookmark
        return m

    def expand(self, unit):
        pass


class MockNVDAObject:
    """Minimal NVDAObject for overlay class testing.

    Simulates the LiveText monitor pattern: a background thread that
    calls _getText(), diffs, and calls _reportNewLines().
    """
    def __init__(self):
        self._event = threading.Event()
        self._monitorThread = None
        self._keepMonitoring = False
        self.appModule = Mock()
        self.appModule.appName = "windowsterminal"

    def initOverlayClass(self):
        pass

    def startMonitoring(self):
        if self._monitorThread:
            return
        self._keepMonitoring = True
        self._event.clear()
        self._monitorThread = threading.Thread(
            target=self._monitor, daemon=True
        )
        self._monitorThread.start()

    def stopMonitoring(self):
        if not self._monitorThread:
            return
        self._keepMonitoring = False
        self._event.set()
        self._monitorThread = None

    def _monitor(self):
        """Base LiveText monitor loop."""
        try:
            oldText = self._getText()
        except Exception:
            oldText = ""
        while self._keepMonitoring:
            self._event.wait()
            if not self._keepMonitoring:
                break
            self._event.clear()
            try:
                newText = self._getText()
                outLines = self._calculateNewText(newText, oldText)
                if outLines:
                    self._reportNewLines(outLines)
                oldText = newText
            except Exception:
                pass

    def _getText(self):
        return ""

    def _calculateNewText(self, newText, oldText):
        """Simple line-based diff."""
        old = set(oldText.splitlines())
        return [line for line in newText.splitlines() if line not in old]

    def _reportNewLines(self, lines):
        for line in lines:
            self._reportNewText(line)

    def _reportNewText(self, line):
        pass

    def event_textChange(self):
        self._event.set()

    def event_typedCharacter(self, ch):
        pass

    def makeTextInfo(self, position):
        return MockTextInfo("")


# ---------------------------------------------------------------------------
# RED: Tests for TerminalAccessTerminal overlay class
# These should FAIL until we implement the overlay in addon/lib/terminal_overlay.py
# ---------------------------------------------------------------------------

class TestOverlayClassExists:
    """The overlay class module and class must exist."""

    def test_module_importable(self):
        """lib.terminal_overlay module must be importable."""
        from lib import terminal_overlay
        assert terminal_overlay is not None

    def test_class_exists(self):
        """TerminalAccessTerminal class must exist."""
        from lib.terminal_overlay import TerminalAccessTerminal
        assert TerminalAccessTerminal is not None


class TestOverlayReportNewLines:
    """_reportNewLines should add error/warning audio cues."""

    def test_error_line_plays_low_tone(self):
        """Error lines produce a 220 Hz beep."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "errorAudioCues": True,
        }.get(k, d))

        mock_tones = MagicMock()
        with patch("lib.terminal_overlay.tones", mock_tones):
            obj._reportNewLines(["main.c:5:12: error: expected ';'"])
            mock_tones.beep.assert_any_call(220, 50)

    def test_warning_line_plays_mid_tone(self):
        """Warning lines produce a 440 Hz beep."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "errorAudioCues": True,
        }.get(k, d))

        mock_tones = MagicMock()
        with patch("lib.terminal_overlay.tones", mock_tones):
            obj._reportNewLines(["main.c:5: warning: unused variable"])
            mock_tones.beep.assert_any_call(440, 30)

    def test_normal_line_no_tone(self):
        """Normal output lines produce no beep."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "errorAudioCues": True,
        }.get(k, d))

        mock_tones = MagicMock()
        with patch("lib.terminal_overlay.tones", mock_tones):
            obj._reportNewLines(["total 48"])
            mock_tones.beep.assert_not_called()

    def test_error_cues_disabled(self):
        """No beep when error audio cues are disabled."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "errorAudioCues": False,
        }.get(k, d))

        mock_tones = MagicMock()
        with patch("lib.terminal_overlay.tones", mock_tones):
            obj._reportNewLines(["main.c:5:12: error: expected ';'"])
            mock_tones.beep.assert_not_called()


class TestOverlayOutputCoalescing:
    """Large output should be coalesced, not spoken line-by-line."""

    def test_small_output_speaks_all_lines(self):
        """3 or fewer lines are spoken individually."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(return_value=True)
        obj._reportNewText = Mock()

        lines = ["line 1", "line 2", "line 3"]
        obj._reportNewLines(lines)

        assert obj._reportNewText.call_count == 3

    def test_moderate_output_speaks_last_lines(self):
        """4-20 lines: play activity tone, speak only last 3."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(return_value=True)
        obj._reportNewText = Mock()

        lines = [f"line {i}" for i in range(10)]
        obj._reportNewLines(lines)

        # Should speak only last 3
        assert obj._reportNewText.call_count == 3
        obj._reportNewText.assert_any_call("line 7")
        obj._reportNewText.assert_any_call("line 8")
        obj._reportNewText.assert_any_call("line 9")

    def test_bulk_output_announces_count(self):
        """21+ lines: announce count, don't speak individual lines."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(return_value=True)
        obj._reportNewText = Mock()

        lines = [f"line {i}" for i in range(50)]
        obj._reportNewLines(lines)

        # Should NOT speak all 50 lines
        assert obj._reportNewText.call_count <= 3


class TestOverlayQuietMode:
    """Quiet mode should prevent the monitor thread from waking."""

    def test_quiet_mode_skips_event_set(self):
        """event_textChange in quiet mode does not wake monitor thread."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._event = Mock()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "quietMode": True,
            "errorAudioCues": False,
            "errorAudioCuesInQuietMode": False,
            "outputActivityTones": False,
        }.get(k, d))

        obj.event_textChange()
        obj._event.set.assert_not_called()

    def test_normal_mode_wakes_monitor(self):
        """event_textChange in normal mode wakes the monitor thread."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._event = Mock()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "quietMode": False,
        }.get(k, d))

        obj.event_textChange()
        obj._event.set.assert_called_once()


class TestOverlayBlankSuppression:
    """Blank lines immediately after Enter should not be spoken."""

    def test_blank_line_suppressed_after_enter(self):
        """A blank or whitespace-only line is not spoken."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(return_value=True)
        obj._reportNewText = Mock()

        obj._reportNewLines(["", "  ", "\t"])
        obj._reportNewText.assert_not_called()

    def test_non_blank_line_spoken(self):
        """A line with actual content IS spoken."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._configManager = Mock()
        obj._configManager.get = Mock(return_value=True)
        obj._reportNewText = Mock()

        obj._reportNewLines(["drwxr-xr-x  2 user user 4096 Mar 21 readme.md"])
        obj._reportNewText.assert_called_once()


class TestOverlayActivityTones:
    """Activity tones should fire from event_textChange, not event_caret."""

    def test_activity_tone_on_text_change(self):
        """When outputActivityTones enabled, event_textChange plays tones."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._event = Mock()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "quietMode": False,
            "outputActivityTones": True,
            "outputActivityDebounce": 1000,
        }.get(k, d))
        obj._lastActivityToneTime = 0
        obj._lastTypedCharTime = 0

        mock_tones = MagicMock()
        with patch("lib.terminal_overlay.tones", mock_tones):
            obj.event_textChange()
            assert mock_tones.beep.call_count >= 2  # Two ascending tones

    def test_activity_tone_debounced(self):
        """Activity tones respect debounce interval."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._event = Mock()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "quietMode": False,
            "outputActivityTones": True,
            "outputActivityDebounce": 1000,
        }.get(k, d))
        obj._lastActivityToneTime = time.time()  # Just played
        obj._lastTypedCharTime = 0

        mock_tones = MagicMock()
        with patch("lib.terminal_overlay.tones", mock_tones):
            obj.event_textChange()
            mock_tones.beep.assert_not_called()  # Debounced

    def test_no_activity_tone_during_typing(self):
        """Activity tones don't play for typed character echo."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._event = Mock()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "quietMode": False,
            "outputActivityTones": True,
            "outputActivityDebounce": 1000,
        }.get(k, d))
        obj._lastActivityToneTime = 0
        obj._lastTypedCharTime = time.time()  # Just typed

        mock_tones = MagicMock()
        with patch("lib.terminal_overlay.tones", mock_tones):
            obj.event_textChange()
            mock_tones.beep.assert_not_called()


class TestOverlayQuietModeErrorCues:
    """Error cues in quiet mode should fire from event_textChange."""

    def test_error_cue_in_quiet_mode(self):
        """With errorAudioCuesInQuietMode on, error beep fires in quiet mode."""
        from lib.terminal_overlay import TerminalAccessTerminal

        obj = TerminalAccessTerminal()
        obj._event = Mock()
        obj._configManager = Mock()
        obj._configManager.get = Mock(side_effect=lambda k, d=None: {
            "quietMode": True,
            "errorAudioCues": True,
            "errorAudioCuesInQuietMode": True,
            "outputActivityTones": False,
        }.get(k, d))
        # Mock the method that checks the current line for errors
        obj._checkErrorAudioCue = Mock()

        obj.event_textChange()

        obj._checkErrorAudioCue.assert_called_once()
        # Monitor thread should NOT be woken
        obj._event.set.assert_not_called()


class TestChooseOverlayClasses:
    """GlobalPlugin.chooseNVDAObjectOverlayClasses inserts our overlay."""

    def test_inserts_overlay_for_terminal_object(self):
        """When clsList contains a Terminal subclass, insert our overlay first."""
        from lib.terminal_overlay import TerminalAccessTerminal

        # Simulate NVDA's clsList with a Terminal-like class
        class FakeTerminal:
            pass

        clsList = [FakeTerminal]

        # The function should insert TerminalAccessTerminal at position 0
        # We test the logic, not the GlobalPlugin method itself
        from lib.terminal_overlay import should_apply_overlay
        result = should_apply_overlay("windowsterminal")
        assert result is True

    def test_does_not_insert_for_non_terminal(self):
        """Non-terminal apps should not get the overlay."""
        from lib.terminal_overlay import should_apply_overlay
        result = should_apply_overlay("notepad")
        assert result is False
