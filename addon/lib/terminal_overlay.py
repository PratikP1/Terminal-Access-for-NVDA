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
import unicodedata
import weakref

import api
import config
from NVDAObjects.behaviors import EnhancedTermTypedCharSupport

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
        self._init_typing_echo()

    def initOverlayClass(self):
        """Called by NVDA after overlay class construction."""
        if not hasattr(self, "_errorDetector"):
            self._errorDetector = ErrorLineDetector()
        self._init_typing_echo()

    def _init_typing_echo(self):
        """Keep unconfirmed input on its terminal, never on the plugin."""
        self._pending_typing_echo = []
        self._confirmed_word_chars = []
        self._echo_plugin_ref = None
        self._echo_owned = None

    def _clear_pending_echo(self, plugin=None):
        """Discard input across the same boundaries as native word echo."""
        self._pending_typing_echo = []
        self._confirmed_word_chars = []
        if isinstance(self, EnhancedTermTypedCharSupport):
            self._queuedChars = []
        active = self._get_plugin()
        if (active is not None and active._boundTerminal == self) or api.getFocusObject() == self:
            speech.clearTypedWordBuffer()
        if plugin is not None and (plugin._boundTerminal is None or plugin._boundTerminal == self):
            plugin._clear_typing_echo_state()

    def _sync_echo_owner(self, plugin):
        """Do not deliver a previous owner's queued input after a switch."""
        previous = self._echo_plugin_ref() if self._echo_plugin_ref is not None else None
        owned = bool(plugin is not None and plugin._ownsTypingEcho())
        owner_collected = self._echo_plugin_ref is not None and previous is None
        if previous is not plugin or owned != self._echo_owned or owner_collected:
            self._clear_pending_echo(previous)
            self._echo_plugin_ref = weakref.ref(plugin) if plugin is not None else None
            self._echo_owned = owned
        return owned

    def _dispatch_typing_echo(self, plugin):
        """Release native and add-on typing only after terminal output."""
        owned = self._sync_echo_owner(plugin)
        if plugin is not None and (plugin._getEffective("quietMode") or plugin._boundTerminal != self):
            self._clear_pending_echo(plugin)
            return
        if isinstance(self, EnhancedTermTypedCharSupport):
            self._dispatchQueue()
        pending, self._pending_typing_echo = self._pending_typing_echo, []
        if not owned or plugin._boundTerminal != self or plugin._isTypingProtected():
            self._confirmed_word_chars = []
            return
        for ch in pending:
            self._track_echoed_character(ch)
            plugin._terminalTypedCharacter(self, ch, lambda: None)

    def _track_echoed_character(self, ch):
        """Mirror native word length for its typed-fragment output filter."""
        if ch == "\b":
            del self._confirmed_word_chars[-1:]
        elif ch == "\x7f":
            pass
        elif ch and unicodedata.category(ch)[0] in "LMN":
            self._confirmed_word_chars.append(ch)
        else:
            self._confirmed_word_chars = []

    def _reportNewLines(self, lines):
        """Override LiveText._reportNewLines with coalescing and audio cues.

        Small output (<=3 lines): speak all, with error/warning tones.
        Moderate output (4-20 lines): activity tone, speak last 3.
        Bulk output (21+ lines): announce count, no per-line speech.
        Blank/whitespace lines are always suppressed.
        """
        plugin = self._get_plugin()
        self._sync_echo_owner(plugin)
        if isinstance(self, EnhancedTermTypedCharSupport):
            # Preserve EnhancedTermTypedCharSupport's typed-fragment filter
            # before our reporter replaces its superclass output delivery.
            word_length = max(len(speech.speech._curWordChars), len(self._confirmed_word_chars))
            if len(lines) == 1 and not self._hasTab and len(lines[0].strip()) < max(word_length + 1, 3):
                return
            self._clear_pending_echo(plugin)
        # Filter blanks
        content_lines = [line for line in lines if line and not line.isspace()]
        if not content_lines:
            return

        error_cues_enabled = True
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
        self._dispatch_typing_echo(plugin)
        if plugin is None:
            # Not wired yet: keep NVDA's default behavior (speak output).
            self._wake_monitor()
            return
        if plugin._handleTerminalTextChange(self):
            self._wake_monitor()

    def event_caret(self):
        """Caret moved.

        The plugin owns terminal caret announcement (debounced cursor
        tracking, blank suppression, error cues), so NVDA's native caret
        handling is intentionally suppressed here (no super call).
        """
        plugin = self._get_plugin()
        if plugin is None:
            try:
                super(TerminalAccessTerminal, self).event_caret()
            except AttributeError:
                pass
            return
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
        owned = self._sync_echo_owner(plugin)
        if plugin is None:
            speak_default()
            return
        if owned and isinstance(self, EnhancedTermTypedCharSupport):
            self._hasTab = ch == "\t"
            if self._hasTab:
                speech.clearTypedWordBuffer()
                plugin._clear_typing_echo_state()
            if plugin._isTypingProtected():
                self._clear_pending_echo(plugin)
            elif self._supportsTextChange and not config.conf["terminals"]["speakPasswords"]:
                # Match native no-output suppression even when NVDA's own
                # typing settings are off. Do not change those settings.
                plugin._lastTypedCharTime = time.time()
                plugin._updateBrailleCaret(self)
                self._pending_typing_echo.append(ch)
                return
            else:
                self._track_echoed_character(ch)
        plugin._terminalTypedCharacter(self, ch, speak_default)

    def script_flush_queuedChars(self, gesture):
        """Inherited Enter/Tab/interrupt bindings also discard our input."""
        self._clear_pending_echo(self._get_plugin())
        native_flush = getattr(super(TerminalAccessTerminal, self), "script_flush_queuedChars", None)
        if native_flush is not None:
            native_flush(gesture)
        else:
            gesture.send()

    def _caretScriptPostMovedHelper(self, speakUnit, gesture, info=None):
        """Caret navigation invalidates a partially typed add-on word."""
        self._clear_pending_echo(self._get_plugin())
        native_move = getattr(super(TerminalAccessTerminal, self), "_caretScriptPostMovedHelper", None)
        if native_move is not None:
            native_move(speakUnit, gesture, info)

    def event_loseFocus(self):
        """Unconfirmed input must not survive leaving this terminal."""
        self._clear_pending_echo(self._get_plugin())
        native_focus = getattr(super(TerminalAccessTerminal, self), "event_loseFocus", None)
        if native_focus is not None:
            native_focus()
