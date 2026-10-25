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

import braille
from NVDAObjects import NVDAObject

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


def has_terminal_class(clsList):
    """True if NVDA already classified this object as a terminal.

    NVDA inserts a Terminal SUBCLASS into clsList, never Terminal
    itself: WinConsoleUIA for the modern console, and
    KeyboardHandlerBasedTypedCharSupport for PuTTY and mintty. So this
    tests issubclass; a literal ``Terminal in clsList`` would never
    match anything in practice.

    Used together with the app-name list, not instead of it: about half
    the supported names (ConEmu, Cmder, Alacritty, WezTerm, MobaXterm,
    Tera Term...) have no NVDA appModule, so whether NVDA classes them
    as terminals is unproven. The union widens coverage to terminals we
    never enumerated, including ones released after this code, without
    dropping anything that works today.
    """
    from NVDAObjects.behaviors import Terminal
    return any(
        isinstance(cls, type) and issubclass(cls, Terminal)
        for cls in clsList
    )


# The running GlobalPlugin, registered once at plugin start via
# set_active_plugin. The overlay delegates terminal events to it and reads
# config through its config manager. This replaces the earlier pattern of
# the plugin pushing _plugin/_configManager onto each overlay object on
# focus, which could be unset before the first focus event.
_active_plugin = None


def set_active_plugin(plugin):
    """Register (or clear, with None) the running GlobalPlugin."""
    global _active_plugin
    _active_plugin = plugin


def get_active_plugin():
    """Return the running GlobalPlugin, or None if not started."""
    return _active_plugin


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

    def initOverlayClass(self):
        """Called by NVDA after overlay class construction."""
        if not hasattr(self, "_errorDetector"):
            self._errorDetector = ErrorLineDetector()

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
        plugin = self._get_plugin()
        if plugin is not None and getattr(plugin, "_configManager", None) is not None:
            error_cues_enabled = plugin._configManager.get("errorAudioCues", True)

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
        if classification:
            from lib.audio_cues import play_cue
            play_cue(classification)

    def _get_plugin(self):
        """Return the running GlobalPlugin (registered at plugin start)."""
        return _active_plugin

    def _wake_monitor(self):
        """Wake the LiveText monitor thread so it speaks the new output.

        This is what NVDA's LiveText.event_textChange does; done here so the
        overlay controls exactly when the monitor runs.
        """
        event = getattr(self, "_event", None)
        if event is not None:
            event.set()

    def event_textChange(self):
        """Terminal buffer content changed.

        The plugin owns activity tones, progress milestones, and quiet-mode
        error detection (its state drives them). It returns whether to wake
        the monitor thread, which then speaks the new output via
        _reportNewLines. In quiet mode the monitor is not woken (silence).
        """
        plugin = self._get_plugin()
        if plugin is None or plugin._handleTerminalTextChange(self):
            self._wake_monitor()
        # Terminal.event_textChange also refreshes braille, including when
        # output repaints without moving the caret. Keep that independent
        # of whether the monitor is allowed to speak.
        braille.handler.handleUpdate(self)

    def event_caret(self):
        """Caret moved.

        Keep NVDAObject's guarded non-speech hooks for review, vision,
        braille input and the braille display. The plugin handles its
        own announcements; EditableText selection reporting is not run.
        """
        plugin = self._get_plugin()
        if plugin is None:
            try:
                super(TerminalAccessTerminal, self).event_caret()
            except AttributeError:
                pass
            return
        NVDAObject.event_caret(self)
        plugin._handleTerminalCaret(self)

    def event_typedCharacter(self, ch):
        """A character was typed.

        The plugin decides whether NVDA echoes (via the speak_default
        callback), whether the add-on adds its own echo, and quiet-mode
        suppression.
        """
        def speak_default():
            try:
                super(TerminalAccessTerminal, self).event_typedCharacter(ch)
            except AttributeError:
                pass

        plugin = self._get_plugin()
        if plugin is None:
            speak_default()
            return
        plugin._terminalTypedCharacter(self, ch, speak_default)
