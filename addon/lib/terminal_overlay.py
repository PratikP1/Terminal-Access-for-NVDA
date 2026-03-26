"""
NVDAObject overlay class for terminal windows.

Replaces NVDA's LiveText-based terminal handling by hooking into
chooseNVDAObjectOverlayClasses. Overrides _reportNewLines and
event_textChange at the NVDAObject level instead of intercepting
events at the GlobalPlugin level.

This gives us control over the output pipeline: error/warning
audio cues, output coalescing, blank suppression, quiet mode,
and activity tones all live here.
"""
import time

try:
    import tones
except ImportError:
    tones = None

try:
    import ui
except ImportError:
    ui = None

try:
    import speech
except ImportError:
    speech = None

from lib.text_processing import ErrorLineDetector
from lib.profiles import _SUPPORTED_TERMINALS


def should_apply_overlay(app_name):
    """Check whether an app should get the terminal overlay.

    Args:
        app_name: The appModule.appName string.

    Returns:
        True if the app is a supported terminal.
    """
    return app_name in _SUPPORTED_TERMINALS


class TerminalAccessTerminal:
    """NVDAObject overlay that replaces NVDA's LiveText output handling.

    Insert this at position 0 in clsList via chooseNVDAObjectOverlayClasses
    so its methods take priority over NVDA's Terminal/LiveText classes.
    """

    # Coalescing thresholds
    _BULK_THRESHOLD = 20
    _MODERATE_THRESHOLD = 4
    _TAIL_LINES = 3

    def __init__(self, *args, **kwargs):
        """Initialize overlay state.

        Works both as standalone (tests) and as NVDA overlay
        (where initOverlayClass is also called).
        """
        self._errorDetector = ErrorLineDetector()
        self._lastActivityToneTime = 0
        self._lastTypedCharTime = 0
        self._configManager = None  # Set by GlobalPlugin on gainFocus

    def initOverlayClass(self):
        """Called by NVDA after overlay class construction."""
        if not hasattr(self, "_errorDetector"):
            self._errorDetector = ErrorLineDetector()
            self._lastActivityToneTime = 0
            self._lastTypedCharTime = 0
            self._configManager = None

    def _reportNewLines(self, lines):
        """Override LiveText._reportNewLines with coalescing and audio cues.

        Small output (<=3 lines): speak all, with error/warning tones.
        Moderate output (4-20 lines): activity tone, speak last 3.
        Bulk output (21+ lines): announce count, no per-line speech.
        Blank/whitespace lines are always suppressed.
        """
        # Filter blanks
        content_lines = [line for line in lines if line and not line.isspace()]
        if not content_lines:
            return

        error_cues_enabled = True
        if self._configManager:
            error_cues_enabled = self._configManager.get("errorAudioCues", True)

        count = len(content_lines)

        if count > self._BULK_THRESHOLD:
            # Bulk: announce count, skip per-line speech
            if tones:
                tones.beep(600, 30)
                tones.beep(800, 30)
            if ui:
                # Translators: Announced when many lines of output appear at once.
                ui.message(_("{count} new lines").format(count=count))
            # Still check last line for errors
            if error_cues_enabled:
                self._beepForClassification(content_lines[-1])
        elif count >= self._MODERATE_THRESHOLD:
            # Moderate: activity tone, speak tail
            if tones:
                tones.beep(600, 30)
            for line in content_lines[-self._TAIL_LINES:]:
                if error_cues_enabled:
                    self._beepForClassification(line)
                self._reportNewText(line)
        else:
            # Small: speak all
            for line in content_lines:
                if error_cues_enabled:
                    self._beepForClassification(line)
                self._reportNewText(line)

    def _reportNewText(self, line):
        """Speak a single line of text."""
        if speech:
            speech.speakText(line)

    def _beepForClassification(self, text):
        """Play error/warning tone if the line matches a pattern."""
        classification = self._errorDetector.classify(text)
        if classification == "error" and tones:
            tones.beep(220, 50)
        elif classification == "warning" and tones:
            tones.beep(440, 30)

    def event_textChange(self):
        """Override Terminal.event_textChange.

        In quiet mode: don't wake the monitor thread (no speech).
        Optionally play error cues and activity tones.
        In normal mode: wake the monitor thread, play activity tones.
        """
        is_quiet = False
        if self._configManager:
            is_quiet = self._configManager.get("quietMode", False)

        if is_quiet:
            # Quiet mode: no speech, but optionally check for errors
            if self._configManager:
                if (self._configManager.get("errorAudioCues", True)
                        and self._configManager.get("errorAudioCuesInQuietMode", False)):
                    self._checkErrorAudioCue()
                if self._configManager.get("outputActivityTones", False):
                    self._playActivityTone()
            # Do NOT call super or set _event (silence)
            return

        # Normal mode: play activity tones, then wake monitor
        if self._configManager and self._configManager.get("outputActivityTones", False):
            self._playActivityTone()

        # Wake the monitor thread (equivalent to super().event_textChange())
        if hasattr(self, "_event"):
            self._event.set()

    def _playActivityTone(self):
        """Play two ascending tones, debounced and not during typing."""
        now = time.time()

        # Don't play during typing
        if now - self._lastTypedCharTime < 0.3:
            return

        # Debounce
        debounce_ms = 1000
        if self._configManager:
            debounce_ms = self._configManager.get("outputActivityDebounce", 1000)
        if now - self._lastActivityToneTime < debounce_ms / 1000.0:
            return

        self._lastActivityToneTime = now
        if tones:
            tones.beep(600, 30)
            tones.beep(800, 30)

    def _checkErrorAudioCue(self):
        """Check current line for error/warning and beep."""
        try:
            import textInfos
            info = self.makeTextInfo(textInfos.POSITION_CARET)
            info.expand(textInfos.UNIT_LINE)
            text = getattr(info, "text", "")
            if isinstance(text, str):
                self._beepForClassification(text)
        except Exception:
            pass
