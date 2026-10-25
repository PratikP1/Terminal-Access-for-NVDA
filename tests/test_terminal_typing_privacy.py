"""Privacy regressions through the unchanged native terminal queue contract."""
from enum import Enum
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from typing import Any
import unicodedata
from unittest.mock import Mock

import pytest


@pytest.fixture
def typing_terminal(monkeypatch):
    """Keep actual queue/flush/filter methods; substitute platform outputs."""
    import config
    import speech
    import ui
    from NVDAObjects.behaviors import EnhancedTermTypedCharSupport as EnhancedIdentity
    from globalPlugins.terminalAccess import GlobalPlugin
    from lib import terminal_overlay

    def build(key=True, word=False, native_chars=0, native_words=0, quiet=False):
        settings = {"keyEcho": key, "wordEcho": word, "quietMode": quiet,
                    "cursorTracking": False, "progressMilestones": False,
                    "outputActivityTones": False, "errorAudioCues": False,
                    "repeatedSymbols": False, "punctuationLevel": 0}
        config.conf["keyboard"]["speakTypedCharacters"] = native_chars
        config.conf["keyboard"]["speakTypedWords"] = native_words
        config.conf["terminals"]["speakPasswords"] = False
        received, native_spoken, addon_spoken, output_spoken = [], [], [], []
        native_word = []
        monkeypatch.setattr(speech.speech, "_curWordChars", native_word)
        monkeypatch.setattr(speech, "clearTypedWordBuffer", native_word.clear)
        monkeypatch.setattr(ui, "message", addon_spoken.append)
        monkeypatch.setattr(speech, "speakText", output_spoken.append)
        monkeypatch.setattr(speech, "speakSpelling", output_spoken.append, raising=False)
        monkeypatch.setitem(sys.modules, "inputCore",
                            SimpleNamespace(normalizeGestureIdentifier=lambda identifier: identifier))

        keyboard = runpy.run_path(str(Path(__file__).parent / "fixtures/nvda_2026_2_keyboard.py"),
            init_globals={"AutoPropertyType": type, "AutoPropertyObject": object, "Any": Any,
                          "log": Mock(), "isScriptWaiting": lambda: False,
                          "willSayAllResume": lambda gesture: False,
                          "textInfos": SimpleNamespace(POSITION_CARET="caret", UNIT_CHARACTER="character"),
                          "review": Mock(), "braille": __import__("braille"), "speech": speech,
                          "COMError": RuntimeError})

        class TextInfo:
            bookmark = 0
            text = "t"

            def copy(self):
                return TextInfo()

            def move(self, unit, count):
                return count

            def expand(self, unit):
                pass

        class NativeTerminal(EnhancedIdentity, keyboard["ScriptableObject"], keyboard["EditableText"]):
            def event_typedCharacter(self, ch):
                received.append(ch)
                if config.conf["keyboard"]["speakTypedCharacters"]:
                    native_spoken.append(ch)
                if ch == "\b":
                    del native_word[-1:]
                elif ch and unicodedata.category(ch)[0] in "LMN":
                    native_word.append(ch)
                else:
                    if native_word and config.conf["keyboard"]["speakTypedWords"]:
                        native_spoken.append("".join(native_word))
                    native_word.clear()

            def event_textChange(self):
                pass

            def event_loseFocus(self):
                native_word.clear()

            def _reportNewLines(self, lines):
                for line in lines:
                    self._reportNewText(line)

            def makeTextInfo(self, position):
                return TextInfo()

            def _hasCaretMoved(self, bookmark):
                return True, TextInfo()

        class TypingEcho(Enum):
            OFF = 0

        def script(**kwargs):
            def decorate(function):
                function.gestures = kwargs.get("gestures", [])
                return function
            return decorate

        namespace = runpy.run_path(str(Path(__file__).parent / "fixtures/nvda_2026_2_enhanced.py"),
            init_globals={"Terminal": NativeTerminal, "TypingEcho": TypingEcho,
                          "config": config, "speech": speech, "script": script})
        native = namespace["EnhancedTermTypedCharSupport"]

        class Terminal(terminal_overlay.TerminalAccessTerminal, native):
            pass

        terminal = Terminal()
        keyboard["ScriptableObject"].__init__(terminal)
        terminal._queuedChars = []
        plugin = GlobalPlugin()
        plugin._configManager = SimpleNamespace(get=lambda key, default=None: settings.get(key, default))
        plugin._boundTerminal = terminal
        terminal_overlay.set_active_plugin(plugin)
        return SimpleNamespace(terminal=terminal, plugin=plugin, settings=settings,
            received=received, native=native_spoken, addon=addon_spoken, output=output_spoken)

    return build


def _type(context, text, confirm=False):
    """Feed real overlay events; output confirmation is explicit."""
    for character in text:
        context.terminal.event_typedCharacter(character)
        if confirm:
            context.terminal.event_textChange()


@pytest.mark.parametrize("key,word", [(True, False), (False, True), (True, True)])
@pytest.mark.parametrize("native_chars,native_words", [(0, 0), (2, 0), (0, 2), (2, 2)])
def test_no_output_does_not_disclose_typed_characters_or_words(typing_terminal, key, word,
                                                            native_chars, native_words):
    context = typing_terminal(key, word, native_chars, native_words)
    _type(context, "DummySecret42 ")
    assert context.addon == []
    assert context.native == []
    assert context.plugin._typedWordChars == []


@pytest.mark.parametrize("native_chars", [0, 2])
def test_confirmed_key_echo_is_delivered_once(typing_terminal, native_chars):
    context = typing_terminal(native_chars=native_chars)
    _type(context, "x")
    assert context.addon == []
    context.terminal.event_textChange()
    context.terminal.event_textChange()
    assert context.addon == ["x"]
    assert context.native == []


def test_confirmed_word_echo_and_backspace_character_preserve_the_edited_word(typing_terminal):
    context = typing_terminal(key=False, word=True, native_words=2)
    _type(context, "cat\bs ", confirm=True)
    assert context.addon == ["cas"]
    assert context.native == []


def test_native_word_echo_keeps_native_confirmation_and_delivery(typing_terminal):
    context = typing_terminal(key=True, native_words=2)
    _type(context, "cat ")
    assert context.native == []
    context.terminal.event_textChange()
    assert context.native == ["cat"]
    assert context.addon == []
    assert context.terminal._queuedChars == []


@pytest.mark.parametrize("identifier", ["kb:enter", "kb:numpadEnter", "kb:tab", "kb:control+c",
                                        "kb:control+d", "kb:control+pause"])
def test_inherited_flush_gestures_discard_unconfirmed_input(typing_terminal, identifier):
    context = typing_terminal(key=False, word=True)
    _type(context, "DummySecret42")
    sent = []
    gesture = SimpleNamespace(normalizedIdentifiers=[identifier], send=lambda: sent.append(identifier))
    script = context.terminal.getScript(gesture)
    assert script is not None
    script(gesture)
    _type(context, " ", confirm=True)
    assert sent == [identifier]
    assert context.addon == []
    assert context.native == []


def test_caret_script_discards_partial_and_pending_addon_words(typing_terminal):
    context = typing_terminal(key=False, word=True)
    _type(context, "old", confirm=True)
    _type(context, "pending")
    context.terminal._caretScriptPostMovedHelper(None, SimpleNamespace())
    _type(context, "new ", confirm=True)
    assert context.addon == ["new"]


def test_inherited_backspace_script_preserves_native_partial_word_reset(typing_terminal):
    context = typing_terminal(key=False, word=True)
    _type(context, "cat", confirm=True)
    sent = []
    context.terminal.script_caret_backspaceCharacter(SimpleNamespace(send=lambda: sent.append(True)))
    _type(context, "s ", confirm=True)
    assert sent == [True]
    assert context.output == ["t"]
    assert context.addon == ["s"]


def test_focus_loss_discards_unconfirmed_input(typing_terminal):
    context = typing_terminal(key=False, word=True)
    _type(context, "DummySecret42")
    context.terminal.event_loseFocus()
    _type(context, " ", confirm=True)
    assert context.addon == []


@pytest.mark.parametrize("transition", ["native", "quiet", "terminated", "reloaded", "other_terminal"])
def test_queued_input_cannot_be_released_after_ownership_changes(typing_terminal, transition):
    from lib.terminal_overlay import set_active_plugin

    context = typing_terminal(key=False, word=True, native_words=2)
    _type(context, "DummySecret42")
    if transition == "native":
        context.settings["wordEcho"] = False
    elif transition == "quiet":
        context.settings["quietMode"] = True
    elif transition == "terminated":
        set_active_plugin(None)
    elif transition == "reloaded":
        replacement = typing_terminal(key=False, word=True, native_words=2)
        replacement.plugin._boundTerminal = context.terminal
    else:
        context.plugin._boundTerminal = object()
    context.terminal.event_textChange()
    assert context.addon == []
    assert context.native == []
    if transition == "reloaded":
        replacement.terminal = context.terminal
        _type(replacement, " ", confirm=True)
        assert replacement.addon == []
        assert replacement.native == []
    elif transition != "terminated":
        context.settings.update(wordEcho=True, quietMode=False)
        context.plugin._boundTerminal = context.terminal
        _type(context, " ", confirm=True)
        assert context.addon == []
        assert context.native == []


def test_native_owned_queue_cannot_speak_from_a_previous_terminal(typing_terminal):
    context = typing_terminal(key=True, word=False, native_words=2)
    _type(context, "DummySecret42 ")
    context.plugin._boundTerminal = object()
    context.terminal.event_textChange()
    assert context.native == []
    assert context.addon == []
    assert context.terminal._queuedChars == []


@pytest.mark.parametrize("transition", ["addon", "quiet", "focus"])
def test_native_partial_words_are_discarded_at_echo_boundaries(typing_terminal, transition):
    context = typing_terminal(key=False, word=False, native_words=2)
    _type(context, "old", confirm=True)
    if transition == "addon":
        context.settings["wordEcho"] = True
        _type(context, "new ", confirm=True)
        context.settings["wordEcho"] = False
    elif transition == "quiet":
        context.settings["quietMode"] = True
        _type(context, "silent ", confirm=True)
        context.settings["quietMode"] = False
    else:
        context.terminal.event_loseFocus()
    _type(context, "next ", confirm=True)
    assert context.native == ["next"]
    assert context.addon == (["new"] if transition == "addon" else [])


def test_old_overlay_cannot_clear_current_terminal_native_word(typing_terminal):
    import speech

    previous = typing_terminal(word=True)
    _type(previous, "old", confirm=True)
    current = typing_terminal(key=False, word=False, native_words=2)
    _type(current, "current", confirm=True)
    previous.terminal._sync_echo_owner(current.plugin)
    assert speech.speech._curWordChars == list("current")


@pytest.mark.parametrize("event", ["textChange", "reportNewLines"])
@pytest.mark.parametrize("active", [True, False])
def test_background_terminal_preserves_nonterminal_native_word(typing_terminal, monkeypatch, event, active):
    import api
    import speech
    from lib.terminal_overlay import set_active_plugin

    context = typing_terminal(key=False, word=False, native_words=2)
    _type(context, "old", confirm=True)
    context.terminal.event_loseFocus()
    context.plugin._boundTerminal = None
    monkeypatch.setattr(api, "getFocusObject", lambda: object())
    if not active:
        set_active_plugin(None)
    speech.speech._curWordChars[:] = list("editor")
    if event == "textChange":
        context.terminal.event_textChange()
    else:
        context.terminal._reportNewLines(["A background terminal output line"])
    assert speech.speech._curWordChars == list("editor")


def test_native_fallback_report_clears_its_own_focused_word(typing_terminal, monkeypatch):
    import api
    import speech
    from lib.terminal_overlay import set_active_plugin

    context = typing_terminal(key=False, word=False, native_words=2)
    _type(context, "old", confirm=True)
    monkeypatch.setattr(api, "getFocusObject", lambda: context.terminal)
    set_active_plugin(None)
    context.terminal._reportNewLines(["A new terminal output line"])
    assert speech.speech._curWordChars == []


def test_collected_plugin_cannot_release_native_queue_after_unload(typing_terminal):
    import gc
    import weakref
    from lib.terminal_overlay import set_active_plugin

    context = typing_terminal(key=False, word=False, native_chars=2)
    _type(context, "DummySecret42")
    reference = weakref.ref(context.plugin)
    set_active_plugin(None)
    del context.plugin
    gc.collect()
    assert reference() is None
    context.terminal.event_textChange()
    assert context.native == []
    assert context.addon == []
    assert context.terminal._queuedChars == []


@pytest.mark.parametrize("word,native_words", [(False, 0), (True, 2), (False, 2)])
def test_echoed_input_is_filtered_before_existing_output_coalescing(typing_terminal, word, native_words):
    context = typing_terminal(word=word, native_words=native_words)
    _type(context, "hello", confirm=True)
    context.terminal._reportNewLines(["hello"])
    assert context.addon == (list("hello") if native_words == 0 or word else [])
    assert context.output == []
    context.terminal._reportNewLines(["line one", "line two", "line three", "line four"])
    assert context.output == ["line two", "line three", "line four"]


def test_repeated_symbol_echo_preserves_condensing_after_confirmation(typing_terminal):
    context = typing_terminal()
    context.settings.update(repeatedSymbols=True, repeatedSymbolsValues="-")
    _type(context, "--a", confirm=True)
    assert context.addon == ["2 -", "a"]


@pytest.mark.parametrize("option", ["speakPasswords", "unreliable_text_changes"])
def test_native_explicit_password_and_provider_capabilities_are_preserved(typing_terminal, option):
    import config

    context = typing_terminal()
    if option == "speakPasswords":
        config.conf["terminals"]["speakPasswords"] = True
    else:
        context.terminal._supportsTextChange = False
    _type(context, "hello")
    assert context.addon == list("hello")
    context.terminal._reportNewLines(["hello"])
    assert context.output == []


def test_profile_word_echo_uses_confirmation_with_global_echo_disabled(typing_terminal):
    context = typing_terminal(key=False, word=False)
    context.plugin._currentProfile = SimpleNamespace(wordEcho=True)
    _type(context, "cat ")
    assert context.addon == []
    context.terminal.event_textChange()
    assert context.addon == ["cat"]


def test_protected_words_are_discarded_before_accumulation(typing_terminal, monkeypatch):
    import api

    context = typing_terminal(key=False, word=True)
    monkeypatch.setattr(api, "isTypingProtected", lambda: True)
    for character in "DummySecret42":
        context.plugin._echoTypedWord(character)
    assert context.plugin._typedWordChars == []
    monkeypatch.setattr(api, "isTypingProtected", lambda: False)
    context.plugin._echoTypedWord(" ")
    assert context.addon == []
