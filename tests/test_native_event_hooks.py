"""Terminal events retain native accessibility effects without native speech.

The native caret contract below matches NVDA release-2026.2,
source/NVDAObjects/__init__.py:1427 (GPL-2.0-or-later, NV Access).
Only platform state and output devices are replaced; overlay and plugin
event methods execute unchanged.
"""
import threading
from types import SimpleNamespace

import pytest


@pytest.fixture
def event_context(monkeypatch):
    """Supply the native caret guard and observable accessibility state."""
    from globalPlugins import terminalAccess as plugin_module
    from lib import terminal_overlay

    state = SimpleNamespace(
        focus=None, pending_focus=False, review=None, vision=None,
        braille_input=None, display_updates=[], output_updates=[], speech=[],
    )
    native_api = SimpleNamespace(getFocusObject=lambda: state.focus)
    native_events = SimpleNamespace(isPendingEvents=lambda event: state.pending_focus)
    native_braille = SimpleNamespace(handler=SimpleNamespace(
        handleCaretMove=lambda obj: state.display_updates.append(obj),
    ))
    native_braille_input = SimpleNamespace(handler=SimpleNamespace(
        handleCaretMove=lambda obj: setattr(state, "braille_input", obj),
    ))
    native_vision = SimpleNamespace(handler=SimpleNamespace(
        handleCaretMove=lambda obj: setattr(state, "vision", obj),
    ))
    native_review = SimpleNamespace(handleCaretMove=lambda obj: setattr(state, "review", obj))

    class NativeNVDAObject:
        """The real NVDA 2026.2 non-speech caret method and its guards."""

        def event_caret(self):
            if self is native_api.getFocusObject() and not native_events.isPendingEvents("gainFocus"):
                native_braille.handler.handleCaretMove(self)
                native_braille_input.handler.handleCaretMove(self)
                native_vision.handler.handleCaretMove(self)
                native_review.handleCaretMove(self)

    monkeypatch.setattr(terminal_overlay, "NVDAObject", NativeNVDAObject, raising=False)
    monkeypatch.setattr(plugin_module.braille.handler, "handleCaretMove", native_braille.handler.handleCaretMove)
    monkeypatch.setattr(plugin_module.braille.handler, "handleUpdate", lambda obj: state.output_updates.append(obj))
    monkeypatch.setattr(plugin_module.ui, "message", state.speech.append)
    monkeypatch.setattr(plugin_module.speech, "speakText", state.speech.append)
    monkeypatch.setattr(plugin_module.speech, "speakTextInfo", lambda *a, **kw: state.speech.append("text info"))
    plugin_module.braille.handler.displaySize = 40
    return state


def _terminal(settings):
    """Wire actual event methods to controlled settings and a monitor event."""
    from globalPlugins.terminalAccess import GlobalPlugin
    from lib.terminal_overlay import TerminalAccessTerminal, set_active_plugin

    plugin = GlobalPlugin()
    values = {"quietMode": False, "cursorTracking": False, "progressMilestones": False,
              "outputActivityTones": False, "errorAudioCues": False}
    values.update(settings)
    plugin._configManager = SimpleNamespace(get=lambda key, default=None: values.get(key, default))
    set_active_plugin(plugin)
    terminal = TerminalAccessTerminal()
    terminal._event = threading.Event()
    return terminal


@pytest.mark.parametrize("settings", [
    {"quietMode": True},
    {"cursorTracking": False},
    {"cursorTracking": True, "streamingSuppression": True},
])
def test_focused_caret_updates_native_accessibility_state_without_speech(event_context, settings):
    """Dropping the native hook must strand review, vision and braille input."""
    terminal = _terminal(settings)
    event_context.focus = terminal
    terminal.event_caret()
    assert event_context.review is terminal
    assert event_context.vision is terminal
    assert event_context.braille_input is terminal
    assert event_context.display_updates == [terminal]
    assert event_context.speech == []


@pytest.mark.parametrize("pending_focus", [False, True])
def test_background_caret_does_not_move_native_accessibility_state(event_context, pending_focus):
    """An event from another terminal must respect native focus ownership."""
    terminal = _terminal({"quietMode": True})
    event_context.focus = object()
    event_context.pending_focus = pending_focus
    terminal.event_caret()
    assert event_context.review is None
    assert event_context.vision is None
    assert event_context.braille_input is None
    assert event_context.display_updates == []


def test_pending_focus_preserves_native_accessibility_state(event_context):
    """Pending focus must suppress native hooks even on the current object."""
    terminal = _terminal({"quietMode": True})
    event_context.focus = terminal
    event_context.pending_focus = True
    terminal.event_caret()
    assert event_context.review is None
    assert event_context.vision is None
    assert event_context.braille_input is None
    assert event_context.display_updates == []


@pytest.mark.parametrize("quiet_mode", [False, True])
def test_output_repaint_refreshes_braille_independently_of_monitor_speech(event_context, quiet_mode):
    """Dropping handleUpdate must leave output-only repaints unrefreshed."""
    terminal = _terminal({"quietMode": quiet_mode})
    terminal.event_textChange()
    assert event_context.output_updates == [terminal]
    assert terminal._event.is_set() is (not quiet_mode)
    assert event_context.speech == []


def test_unwired_output_repaint_refreshes_braille_and_wakes_monitor(event_context):
    """The startup fallback preserves both native text-change effects."""
    from lib.terminal_overlay import set_active_plugin

    terminal = _terminal({})
    set_active_plugin(None)
    terminal.event_textChange()
    assert event_context.output_updates == [terminal]
    assert terminal._event.is_set()
