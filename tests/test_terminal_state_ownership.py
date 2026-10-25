"""Transient typing and modal commands belong to one focused terminal."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


class Terminal:
    """Two wrappers can represent the same control, regardless of its title."""

    def __init__(self, identity):
        self.identity = identity
        self.appModule = SimpleNamespace(appName="windowsterminal")
        self.windowHandle = 10
        self.windowText = self.name = "PowerShell"

    def __eq__(self, other):
        return isinstance(other, Terminal) and self.identity == other.identity

    def makeTextInfo(self, position):
        raise NotImplementedError


@pytest.fixture
def session(monkeypatch):
    import api
    import config
    import globalPlugins.terminalAccess as ta

    plugin = ta.GlobalPlugin()
    settings = {
        "keyEcho": False, "wordEcho": True, "quietMode": False,
        "repeatedSymbols": True, "repeatedSymbolsValues": "-",
        "cursorTracking": True, "cursorTrackingMode": 1,
        "streamingSuppression": False,
    }
    plugin._configManager = SimpleNamespace(get=settings.get)
    plugin._getEffective = settings.get
    monkeypatch.setattr(config, "conf", {
        "keyboard": {"speakTypedCharacters": 0, "speakTypedWords": 0},
        "terminalAccess": settings,
    })
    monkeypatch.setattr(api, "isTypingProtected", lambda: False)
    monkeypatch.setattr(plugin, "isTerminalApp",
                        lambda obj=None: obj is None or isinstance(obj, Terminal))
    plugin.announcedHelp = True
    plugin.lastTerminalAppName = "windowsterminal"
    terminal = Terminal(1)
    plugin.event_gainFocus(terminal, lambda: None)
    return plugin, terminal, settings


def type_text(plugin, terminal, text):
    for char in text:
        plugin._terminalTypedCharacter(terminal, char, lambda: None)


@pytest.mark.parametrize("leave_app", [False, True])
def test_words_do_not_join_across_focus_changes(session, leave_app):
    import ui

    plugin, first, _ = session
    type_text(plugin, first, "alpha")
    if leave_app:
        plugin.event_gainFocus(SimpleNamespace(), lambda: None)
    second = Terminal(2)
    plugin.event_gainFocus(second, lambda: None)
    with patch.object(ui, "message") as speak:
        type_text(plugin, second, "beta ")
    assert [call.args[0] for call in speak.call_args_list] == ["beta"]


def test_equivalent_terminal_wrapper_preserves_unfinished_word(session):
    import ui

    plugin, first, _ = session
    type_text(plugin, first, "al")
    same = Terminal(1)
    plugin.event_gainFocus(same, lambda: None)
    with patch.object(ui, "message") as speak:
        type_text(plugin, same, "pha ")
    assert [call.args[0] for call in speak.call_args_list] == ["alpha"]


def test_symbol_runs_do_not_join_between_controls_with_same_title(session):
    import ui

    plugin, first, settings = session
    settings.update(keyEcho=True, wordEcho=False)
    type_text(plugin, first, "-")
    second = Terminal(2)
    plugin.event_gainFocus(second, lambda: None)
    with patch.object(ui, "message") as speak, patch.object(plugin, "_speakCharacter"):
        type_text(plugin, second, "-x")
    assert len(speak.call_args_list) == 1
    assert not speak.call_args.args[0].startswith("2 ")


@pytest.mark.parametrize("mode,key", [("table", "downArrow"), ("copy", "l"), ("command", "g")])
@pytest.mark.parametrize("same_control", [False, True])
def test_modal_commands_follow_control_identity(session, mode, key, same_control):
    plugin, _, _ = session
    if mode == "table":
        with patch.object(plugin, "_getBufferLines", return_value=[
            "| Name | Status |", "| ---- | ------ |", "| old | running |",
        ]), patch.object(plugin, "_getCurrentLineNumber", return_value=1):
            plugin.script_toggleTableMode(Mock())
    elif mode == "copy":
        plugin.script_copyMode(Mock())
    else:
        plugin.script_toggleCommandLayer(Mock())
    gesture = SimpleNamespace(normalizedIdentifiers=[f"kb:{key}"])
    assert plugin.getScript(gesture) is not None
    plugin.event_gainFocus(Terminal(1 if same_control else 2), lambda: None)
    assert (plugin.getScript(gesture) is not None) == same_control
    if mode == "table" and not same_control:
        passthrough = Mock()
        plugin.script_tableNextRow(passthrough)
        passthrough.send.assert_called_once()


def test_old_cursor_callback_cannot_speak_after_focus_returns(session):
    import globalPlugins.terminalAccess as ta

    plugin, first, _ = session
    with patch.object(ta.wx, "CallLater") as later:
        plugin._handleTerminalCaret(first)
        callback, *args = later.call_args.args[1:]
        timer = later.return_value
    plugin.event_gainFocus(Terminal(2), lambda: None)
    timer.Stop.assert_called_once()
    plugin.event_gainFocus(first, lambda: None)
    with patch.object(plugin, "_announceStandardCursor") as speak:
        callback(*args)
    speak.assert_not_called()


def test_unloading_discards_scheduled_cursor_speech(session):
    import globalPlugins.terminalAccess as ta

    plugin, terminal, _ = session
    with patch.object(ta.wx, "CallLater") as later:
        plugin._handleTerminalCaret(terminal)
        callback, *args = later.call_args.args[1:]
        timer = later.return_value
    plugin.terminate()
    timer.Stop.assert_called_once()
    with patch.object(plugin, "_announceStandardCursor") as speak:
        callback(*args)
    speak.assert_not_called()


def test_blank_retry_does_not_read_a_terminal_after_focus_changed(session):
    import globalPlugins.terminalAccess as ta

    plugin, first, settings = session
    settings["keyEcho"] = True
    info = SimpleNamespace(bookmark=SimpleNamespace(startOffset=1, endOffset=2),
                           text="", expand=lambda unit: None)
    first.makeTextInfo = Mock(return_value=info)
    with patch.object(ta.time, "time", return_value=10), patch.object(ta.wx, "CallLater") as later:
        plugin._lastTypedCharTime = 10
        plugin._announceStandardCursor(first)
        assert len(later.call_args_list) == 2
        callbacks = [call.args[1:] for call in later.call_args_list]
    plugin.event_gainFocus(Terminal(2), lambda: None)
    plugin.event_gainFocus(first, lambda: None)
    first.makeTextInfo.reset_mock()
    for callback, *args in callbacks:
        callback(*args)
    first.makeTextInfo.assert_not_called()


@pytest.mark.parametrize("same_control", [False, True])
def test_late_caret_event_only_speaks_for_the_focused_control(session, same_control):
    import globalPlugins.terminalAccess as ta

    plugin, first, _ = session
    plugin.event_gainFocus(Terminal(1 if same_control else 2), lambda: None)
    with patch.object(ta.wx, "CallLater") as later:
        plugin._handleTerminalCaret(first)
        callback, *args = later.call_args.args[1:]
    with patch.object(plugin, "_announceStandardCursor") as speak:
        callback(*args)
    assert speak.called == same_control
