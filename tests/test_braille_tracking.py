"""Braille must follow the terminal caret, independently of speech.

Shipped bug (reported against 2.0.3): typing in a terminal never
updated the braille display. The character appeared in the terminal,
but braille kept showing stale content until the user panned away and
back, and the display never auto-tethered to the cursor while typing.

Cause: the overlay's event_caret deliberately never calls super(), so
NVDA's own braille caret tracking never runs; and every speech-
suppression early return in the caret path (typing-induced echo
suppression, blank-after-typing) returned BEFORE the single
handleCaretMove call at the bottom. Speech and braille are separate
output channels, and suppressing one must not silence the other.
"""
from unittest.mock import MagicMock, patch

import pytest


def _plugin(cfg):
    from globalPlugins.terminalAccess import GlobalPlugin
    with patch("gui.settingsDialogs.NVDASettingsDialog"):
        plugin = GlobalPlugin()
    plugin._configManager = MagicMock()
    plugin._configManager.get = MagicMock(side_effect=lambda k, d=None: cfg.get(k, d))
    plugin._getEffective = MagicMock(side_effect=lambda k, d=None: cfg.get(k, d))
    return plugin


@pytest.fixture(autouse=True)
def _reset_braille():
    import braille
    braille.handler.handleCaretMove.reset_mock()
    braille.handler.displaySize = 40
    yield
    braille.handler.displaySize = 40


class TestTypingUpdatesBraille:
    """The reported symptom: type a key, braille shows nothing."""

    def test_typed_character_updates_braille_when_nvda_echoes(self):
        """The default config: NVDA speaks typed characters, so the
        add-on's key echo stands down. Braille must STILL update; this
        is the exact path the user hit."""
        import braille
        plugin = _plugin({"quietMode": False, "keyEcho": False})
        plugin._isKeyEchoActive = MagicMock(return_value=False)

        plugin._terminalTypedCharacter(MagicMock(), "a", lambda: None)

        braille.handler.handleCaretMove.assert_called()

    def test_typed_character_updates_braille_when_addon_echoes(self):
        import braille
        plugin = _plugin({"quietMode": False, "keyEcho": True})
        plugin._isKeyEchoActive = MagicMock(return_value=True)
        plugin._speakCharacter = MagicMock()

        plugin._terminalTypedCharacter(MagicMock(), "b", lambda: None)

        braille.handler.handleCaretMove.assert_called()

    def test_typed_character_updates_braille_in_quiet_mode(self):
        """Quiet mode silences SPEECH. A braille user who turns it on to
        stop chatter still needs the display to follow the cursor."""
        import braille
        plugin = _plugin({"quietMode": True})

        plugin._terminalTypedCharacter(MagicMock(), "c", lambda: None)

        braille.handler.handleCaretMove.assert_called()


class TestBrailleUpdateIsSafe:
    """Never raise into NVDA's event chain over an optional display."""

    def test_no_display_connected_is_a_no_op(self):
        import braille
        braille.handler.displaySize = 0
        plugin = _plugin({"quietMode": False})

        plugin._terminalTypedCharacter(MagicMock(), "a", lambda: None)

        braille.handler.handleCaretMove.assert_not_called()

    def test_braille_handler_failure_is_swallowed(self):
        import braille
        braille.handler.handleCaretMove.side_effect = RuntimeError("display gone")
        plugin = _plugin({"quietMode": False})
        try:
            plugin._terminalTypedCharacter(MagicMock(), "a", lambda: None)
        finally:
            braille.handler.handleCaretMove.side_effect = None
