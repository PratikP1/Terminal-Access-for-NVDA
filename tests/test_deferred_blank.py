"""
Tests for the typing-based blank suppression in _announceStandardCursor.

When the caret lands on an empty / newline position:
  - If the user recently typed a character (within _BLANK_AFTER_TYPING_GRACE
    seconds), the "Blank" announcement is suppressed entirely.  The real
    output will be announced by the NewOutputAnnouncer.
  - If the blank results from navigation (arrow keys, page up/down), "Blank"
    is announced immediately — this is meaningful feedback for the user.

Normal (non-blank) characters and spaces are always announced immediately
regardless of typing history.
"""

import time
import unittest
from unittest.mock import MagicMock, patch


class TestBlankSuppression(unittest.TestCase):
	"""Tests for the typing-based blank suppression mechanism."""

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _make_plugin_with_cursor(self, char_at_caret, caret_offset=100):
		"""
		Build a GlobalPlugin instance whose _announceStandardCursor will
		report *char_at_caret* for the character under the caret.

		Returns (plugin, mock_obj) so tests can call
		plugin._announceStandardCursor(mock_obj) directly.
		"""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Ensure cache miss so the code always reads the character.
		plugin._lastLineText = None
		plugin._lastCaretPosition = None  # force position change detection

		# Expand to UNIT_CHARACTER yields the test character.
		def expand_side_effect(unit):
			info_ref[0].text = char_at_caret

		# Factory for makeTextInfo – each call returns a fresh MagicMock
		# that expands to the test character.
		info_ref = [None]  # mutable reference

		def make_text_info(pos):
			info = MagicMock()
			info.bookmark.startOffset = caret_offset
			info.bookmark.endOffset = caret_offset + 1
			info.expand.side_effect = expand_side_effect
			info.text = char_at_caret
			info_ref[0] = info
			return info

		mock_obj = MagicMock()
		mock_obj.makeTextInfo.side_effect = make_text_info

		return plugin, mock_obj

	# ------------------------------------------------------------------
	# _lastTypedTime initialization
	# ------------------------------------------------------------------

	def test_last_typed_time_initialized_zero(self):
		"""_lastTypedTime must start as 0.0 (no recent typing)."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		self.assertEqual(plugin._lastTypedTime, 0.0)

	# ------------------------------------------------------------------
	# Blank suppressed after recent typing (e.g. pressing Enter)
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_blank_suppressed_after_recent_typing(self, mock_ui):
		"""Blank must be suppressed when the user typed recently."""
		plugin, mock_obj = self._make_plugin_with_cursor('')

		# Simulate that the user just typed (e.g. pressed Enter).
		plugin._lastTypedTime = time.time()

		plugin._announceStandardCursor(mock_obj)

		# "Blank" must NOT be spoken.
		mock_ui.message.assert_not_called()

	@patch('globalPlugins.terminalAccess.ui')
	def test_newline_suppressed_after_recent_typing(self, mock_ui):
		"""Newline at caret must be suppressed when the user typed recently."""
		plugin, mock_obj = self._make_plugin_with_cursor('\n')

		plugin._lastTypedTime = time.time()
		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_not_called()

	@patch('globalPlugins.terminalAccess.ui')
	def test_cr_suppressed_after_recent_typing(self, mock_ui):
		"""Carriage return at caret must be suppressed when the user typed recently."""
		plugin, mock_obj = self._make_plugin_with_cursor('\r')

		plugin._lastTypedTime = time.time()
		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_not_called()

	# ------------------------------------------------------------------
	# Blank announced for navigation (no recent typing)
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_blank_announced_for_navigation(self, mock_ui):
		"""Blank must be announced when there was no recent typing (navigation)."""
		plugin, mock_obj = self._make_plugin_with_cursor('')

		# _lastTypedTime is 0.0 (default) — long in the past.
		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()
		args = mock_ui.message.call_args[0]
		self.assertIn("blank", args[0].lower())

	@patch('globalPlugins.terminalAccess.ui')
	def test_newline_announced_for_navigation(self, mock_ui):
		"""Newline at caret must announce Blank when no recent typing."""
		plugin, mock_obj = self._make_plugin_with_cursor('\n')

		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()
		args = mock_ui.message.call_args[0]
		self.assertIn("blank", args[0].lower())

	@patch('globalPlugins.terminalAccess.ui')
	def test_cr_announced_for_navigation(self, mock_ui):
		"""Carriage return at caret must announce Blank when no recent typing."""
		plugin, mock_obj = self._make_plugin_with_cursor('\r')

		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()
		args = mock_ui.message.call_args[0]
		self.assertIn("blank", args[0].lower())

	# ------------------------------------------------------------------
	# Grace period expiry — blank announced after grace period
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_blank_announced_after_grace_period(self, mock_ui):
		"""Blank must be announced once the typing grace period has expired."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin, mock_obj = self._make_plugin_with_cursor('')

		# Simulate typing that happened well beyond the grace period.
		plugin._lastTypedTime = time.time() - (GlobalPlugin._BLANK_AFTER_TYPING_GRACE + 0.1)

		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()
		args = mock_ui.message.call_args[0]
		self.assertIn("blank", args[0].lower())

	# ------------------------------------------------------------------
	# Normal characters always announced regardless of typing history
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_normal_char_always_announced(self, mock_ui):
		"""A printable character at the caret must always be announced."""
		plugin, mock_obj = self._make_plugin_with_cursor('a')

		# Even with recent typing, normal characters are announced.
		plugin._lastTypedTime = time.time()
		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()
		self.assertEqual(mock_ui.message.call_args[0][0], 'a')

	@patch('globalPlugins.terminalAccess.ui')
	def test_space_always_announced(self, mock_ui):
		"""Space at the caret must always be announced."""
		plugin, mock_obj = self._make_plugin_with_cursor(' ')

		plugin._lastTypedTime = time.time()
		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()

	@patch('globalPlugins.terminalAccess.ui')
	def test_normal_char_announced_without_recent_typing(self, mock_ui):
		"""A printable character at the caret is announced even without recent typing."""
		plugin, mock_obj = self._make_plugin_with_cursor('x')

		# _lastTypedTime = 0.0 (default, no recent typing).
		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()
		self.assertEqual(mock_ui.message.call_args[0][0], 'x')

	# ------------------------------------------------------------------
	# Grace period constant
	# ------------------------------------------------------------------

	def test_grace_period_is_reasonable(self):
		"""The grace period should be between 0.1 and 2.0 seconds."""
		from globalPlugins.terminalAccess import GlobalPlugin

		grace = GlobalPlugin._BLANK_AFTER_TYPING_GRACE
		self.assertGreaterEqual(grace, 0.1)
		self.assertLessEqual(grace, 2.0)


if __name__ == '__main__':
	unittest.main()
