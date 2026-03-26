"""Tests for braille-first affordances, audio cues, verbosity presets, and what-changed."""
import sys
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# 1. Audio cue tests (play_cue)
# ---------------------------------------------------------------------------

class TestPlayCue:
    """Tests for the play_cue function in lib/audio_cues.py."""

    def test_play_cue_error(self):
        """play_cue('error') plays 220 Hz for 50 ms."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("error")
        tones.beep.assert_called_once_with(220, 50)

    def test_play_cue_warning(self):
        """play_cue('warning') plays 440 Hz for 30 ms."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("warning")
        tones.beep.assert_called_once_with(440, 30)

    def test_play_cue_bookmark_set(self):
        """play_cue('bookmark_set') plays an ascending pair: 1000 Hz 20 ms then 1200 Hz 20 ms."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("bookmark_set")
        assert tones.beep.call_count == 2
        tones.beep.assert_any_call(1000, 20)
        tones.beep.assert_any_call(1200, 20)
        # Verify ascending order
        calls = tones.beep.call_args_list
        assert calls[0] == call(1000, 20)
        assert calls[1] == call(1200, 20)

    def test_play_cue_search_match(self):
        """play_cue('search_match') plays 550 Hz for 20 ms."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("search_match")
        tones.beep.assert_called_once_with(550, 20)

    def test_play_cue_unknown_event(self):
        """play_cue with an unknown event name does not crash."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("nonexistent_event")
        tones.beep.assert_not_called()

    def test_play_cue_section_start(self):
        """play_cue('section_start') plays 660 Hz for 30 ms."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("section_start")
        tones.beep.assert_called_once_with(660, 30)

    def test_play_cue_bookmark_jump(self):
        """play_cue('bookmark_jump') plays 800 Hz for 30 ms."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("bookmark_jump")
        tones.beep.assert_called_once_with(800, 30)

    def test_play_cue_no_match(self):
        """play_cue('no_match') plays 200 Hz for 100 ms (low long)."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("no_match")
        tones.beep.assert_called_once_with(200, 100)

    def test_play_cue_command_layer_enter(self):
        """play_cue('command_layer_enter') plays 880 Hz for 50 ms."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("command_layer_enter")
        tones.beep.assert_called_once_with(880, 50)

    def test_play_cue_command_layer_exit(self):
        """play_cue('command_layer_exit') plays 440 Hz for 50 ms."""
        tones = sys.modules['tones']
        tones.beep.reset_mock()
        from lib.audio_cues import play_cue
        play_cue("command_layer_exit")
        tones.beep.assert_called_once_with(440, 50)


# ---------------------------------------------------------------------------
# 2. Braille message format tests
# ---------------------------------------------------------------------------

class TestBrailleMessages:
    """Tests for braille message formatting helpers in lib/audio_cues.py."""

    def test_braille_section_jump(self):
        """Section jump braille message follows 'sec: <type>' format."""
        from lib.audio_cues import format_braille_section
        assert format_braille_section("error") == "sec: error"
        assert format_braille_section("prompt") == "sec: prompt"
        assert format_braille_section("output") == "sec: output"

    def test_braille_search_result(self):
        """Search result braille message follows 'match N/T: line L' format."""
        from lib.audio_cues import format_braille_search
        assert format_braille_search(3, 15, 42) == "match 3/15: line 42"
        assert format_braille_search(1, 1, 1) == "match 1/1: line 1"

    def test_braille_bookmark_set(self):
        """Bookmark set braille message follows 'bmN set' format."""
        from lib.audio_cues import format_braille_bookmark
        assert format_braille_bookmark("1", None) == "bm1 set"

    def test_braille_bookmark_with_label(self):
        """Bookmark braille with content follows 'bmN: <first 20 chars>' format."""
        from lib.audio_cues import format_braille_bookmark
        assert format_braille_bookmark("1", "short label") == "bm1: short label"
        long_label = "this is a very long label that exceeds twenty characters"
        result = format_braille_bookmark("1", long_label)
        assert result == "bm1: this is a very long"
        assert len(result.split(": ", 1)[1]) <= 20

    def test_braille_profile_change(self):
        """Profile change braille message follows 'prof: <name>' format."""
        from lib.audio_cues import format_braille_profile
        assert format_braille_profile("vim") == "prof: vim"
        assert format_braille_profile("default") == "prof: default"

    def test_braille_error_detection(self):
        """Error detection braille message is 'ERR'."""
        from lib.audio_cues import format_braille_error
        assert format_braille_error() == "ERR"


# ---------------------------------------------------------------------------
# 3. Verbosity preset tests
# ---------------------------------------------------------------------------

class TestVerbosity:
    """Tests for the verbosity level setting and cycling."""

    def test_verbosity_setting_exists(self):
        """confspec includes verbosityLevel with range 0-2, default 1."""
        from lib.config import confspec
        assert "verbosityLevel" in confspec
        spec = confspec["verbosityLevel"]
        assert "default=1" in spec
        assert "min=0" in spec
        assert "max=2" in spec

    def test_verbosity_cycle(self):
        """Cycling verbosity goes 0->1->2->0."""
        from lib.audio_cues import cycle_verbosity
        assert cycle_verbosity(0) == 1
        assert cycle_verbosity(1) == 2
        assert cycle_verbosity(2) == 0

    def test_verbosity_label(self):
        """Each verbosity level has a human-readable label."""
        from lib.audio_cues import verbosity_label
        assert verbosity_label(0) == "quiet"
        assert verbosity_label(1) == "normal"
        assert verbosity_label(2) == "verbose"

    def test_verbosity_quiet_suppresses(self):
        """Quiet verbosity (0) suppresses extra speech via should_speak."""
        from lib.audio_cues import should_speak
        # In quiet mode, only "essential" events should speak
        assert should_speak(0, "error") is True
        assert should_speak(0, "navigation") is True
        assert should_speak(0, "section_context") is False
        assert should_speak(0, "search_count") is False

    def test_verbosity_verbose_adds_context(self):
        """Verbose verbosity (2) enables all speech categories."""
        from lib.audio_cues import should_speak
        assert should_speak(2, "error") is True
        assert should_speak(2, "navigation") is True
        assert should_speak(2, "section_context") is True
        assert should_speak(2, "search_count") is True
        assert should_speak(2, "profile_detail") is True


# ---------------------------------------------------------------------------
# 4. What-changed tests
# ---------------------------------------------------------------------------

class TestWhatChanged:
    """Tests for the what-changed diff reporting."""

    def test_what_changed_no_changes(self):
        """When buffer is unchanged, reports 'No changes'."""
        from lib.audio_cues import describe_changes
        result = describe_changes("line1\nline2\n", "line1\nline2\n")
        assert result == "No changes"

    def test_what_changed_few_lines(self):
        """When 1-3 lines changed, returns the changed lines."""
        from lib.audio_cues import describe_changes
        old = "line1\nline2\nline3\n"
        new = "line1\nline2\nline3\nline4\n"
        result = describe_changes(old, new)
        assert "line4" in result
        # Should include the actual changed content
        assert "1 line" in result.lower() or "line4" in result

    def test_what_changed_many_lines(self):
        """When more than 3 lines changed, reports count only."""
        from lib.audio_cues import describe_changes
        old = "line1\n"
        new = "line1\nline2\nline3\nline4\nline5\nline6\n"
        result = describe_changes(old, new)
        assert "5 lines" in result
        # Should not contain every individual line
        assert "line6" not in result

    def test_what_changed_none_old(self):
        """When there is no previous buffer, reports no changes."""
        from lib.audio_cues import describe_changes
        result = describe_changes(None, "line1\nline2\n")
        assert result == "No changes"
