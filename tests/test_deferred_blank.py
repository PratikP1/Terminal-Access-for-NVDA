"""
Tests for the deferred blank announcement mechanism in _announceStandardCursor.

When the caret lands on an empty / newline position, _announceStandardCursor
does NOT announce "Blank" immediately.  Instead it schedules a deferred timer
(wx.CallLater) that re-verifies the character at the caret when it fires.  If
content has appeared (e.g. terminal rendered command output), the announcement
is silently discarded.

Normal (non-blank) characters and spaces are always announced immediately.
Navigation scripts (script_moveTo*) are NOT affected by this deferral.
"""

import unittest
from unittest.mock import MagicMock, patch, call


class TestDeferredBlank(unittest.TestCase):
	"""Tests for the deferred blank announcement mechanism."""

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

	def _make_plugin_with_changing_cursor(self, first_char, second_char, caret_offset=100):
		"""
		Build a GlobalPlugin whose first call to makeTextInfo returns
		*first_char* and subsequent calls return *second_char*.

		Used to simulate content appearing between the initial blank
		detection and the deferred re-check.
		"""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._lastLineText = None
		plugin._lastCaretPosition = None

		call_count = [0]

		def make_text_info(pos):
			call_count[0] += 1
			char = first_char if call_count[0] <= 2 else second_char
			# call_count <= 2: the first makeTextInfo call within
			# _announceStandardCursor (caret pos + expand), and the line-cache
			# refresh call.  Subsequent calls come from _checkDeferredBlank.

			info = MagicMock()
			info.bookmark.startOffset = caret_offset
			info.bookmark.endOffset = caret_offset + 1

			def expand_side_effect(unit):
				info.text = char

			info.expand.side_effect = expand_side_effect
			info.text = char
			return info

		mock_obj = MagicMock()
		mock_obj.makeTextInfo.side_effect = make_text_info

		return plugin, mock_obj

	# ------------------------------------------------------------------
	# _deferredBlankTimer initialization
	# ------------------------------------------------------------------

	def test_deferred_blank_timer_initialized_none(self):
		"""_deferredBlankTimer must start as None."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		self.assertIsNone(plugin._deferredBlankTimer)

	# ------------------------------------------------------------------
	# Blank is deferred, NOT announced immediately
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_blank_deferred_not_immediate(self, mock_ui):
		"""When caret lands on a blank, ui.message must NOT be called immediately."""
		plugin, mock_obj = self._make_plugin_with_cursor('')

		plugin._announceStandardCursor(mock_obj)

		# "Blank" must NOT have been spoken synchronously.
		mock_ui.message.assert_not_called()

	@patch('globalPlugins.terminalAccess.ui')
	def test_newline_deferred_not_immediate(self, mock_ui):
		"""When caret lands on \\n, ui.message must NOT be called immediately."""
		plugin, mock_obj = self._make_plugin_with_cursor('\n')

		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_not_called()

	@patch('globalPlugins.terminalAccess.ui')
	def test_cr_deferred_not_immediate(self, mock_ui):
		"""When caret lands on \\r, ui.message must NOT be called immediately."""
		plugin, mock_obj = self._make_plugin_with_cursor('\r')

		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_not_called()

	# ------------------------------------------------------------------
	# Deferred blank announces after timer fires (char still blank)
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_deferred_blank_announced_after_delay(self, mock_ui):
		"""_checkDeferredBlank must announce 'Blank' when the position is still empty."""
		plugin, mock_obj = self._make_plugin_with_cursor('')

		# Invoke the deferred check directly (simulates timer firing).
		plugin._checkDeferredBlank(mock_obj, 100)

		mock_ui.message.assert_called_once()
		args = mock_ui.message.call_args[0]
		self.assertIn("blank", args[0].lower())

	# ------------------------------------------------------------------
	# Deferred blank suppressed when content appears
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_deferred_blank_suppressed_when_content_appears(self, mock_ui):
		"""If content has appeared at the position, _checkDeferredBlank must NOT announce."""
		plugin, mock_obj = self._make_plugin_with_changing_cursor(
			first_char='', second_char='$'
		)

		# First, trigger the blank detection (which schedules the timer).
		plugin._announceStandardCursor(mock_obj)
		mock_ui.message.assert_not_called()

		# Now simulate the timer firing – _checkDeferredBlank will re-read
		# the character and find '$' instead of blank.
		plugin._checkDeferredBlank(mock_obj, 100)

		mock_ui.message.assert_not_called()

	# ------------------------------------------------------------------
	# Deferred blank suppressed when caret has moved
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_deferred_blank_suppressed_when_caret_moved(self, mock_ui):
		"""If caret moved to a different position, _checkDeferredBlank must NOT announce."""
		plugin, mock_obj = self._make_plugin_with_cursor('')

		# Simulate the timer firing, but with a different expectedPos than
		# the current caret position (100).
		plugin._checkDeferredBlank(mock_obj, 200)  # expectedPos=200 != currentPos=100

		mock_ui.message.assert_not_called()

	# ------------------------------------------------------------------
	# Cancellation: non-blank char cancels deferred blank
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_deferred_blank_cancelled_on_nonblank_char(self, mock_ui):
		"""Announcing a normal character must cancel any pending deferred blank."""
		plugin, mock_obj = self._make_plugin_with_cursor('a')

		# Simulate a pending deferred blank timer.
		mock_timer = MagicMock()
		plugin._deferredBlankTimer = mock_timer

		plugin._announceStandardCursor(mock_obj)

		# The timer should have been cancelled.
		mock_timer.Stop.assert_called_once()
		self.assertIsNone(plugin._deferredBlankTimer)

		# 'a' should still be announced.
		mock_ui.message.assert_called_once()
		self.assertEqual(mock_ui.message.call_args[0][0], 'a')

	@patch('globalPlugins.terminalAccess.ui')
	def test_deferred_blank_cancelled_on_space(self, mock_ui):
		"""Announcing space must cancel any pending deferred blank."""
		plugin, mock_obj = self._make_plugin_with_cursor(' ')

		mock_timer = MagicMock()
		plugin._deferredBlankTimer = mock_timer

		plugin._announceStandardCursor(mock_obj)

		mock_timer.Stop.assert_called_once()
		self.assertIsNone(plugin._deferredBlankTimer)
		mock_ui.message.assert_called_once()

	# ------------------------------------------------------------------
	# Normal characters always announced immediately
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.ui')
	def test_normal_char_always_announced(self, mock_ui):
		"""A printable character at the caret must always be announced immediately."""
		plugin, mock_obj = self._make_plugin_with_cursor('a')

		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()
		self.assertEqual(mock_ui.message.call_args[0][0], 'a')

	@patch('globalPlugins.terminalAccess.ui')
	def test_space_always_announced(self, mock_ui):
		"""Space at the caret must always be announced immediately."""
		plugin, mock_obj = self._make_plugin_with_cursor(' ')

		plugin._announceStandardCursor(mock_obj)

		mock_ui.message.assert_called_once()

	# ------------------------------------------------------------------
	# _scheduleDeferredBlank creates a timer
	# ------------------------------------------------------------------

	@patch('globalPlugins.terminalAccess.wx')
	def test_schedule_creates_call_later_timer(self, mock_wx):
		"""_scheduleDeferredBlank must create a wx.CallLater timer."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		mock_obj = MagicMock()

		plugin._scheduleDeferredBlank(mock_obj, 100)

		mock_wx.CallLater.assert_called_once()
		args = mock_wx.CallLater.call_args
		# First argument is the delay in milliseconds.
		self.assertEqual(args[0][0], plugin._BLANK_ANNOUNCE_DELAY)
		# Second argument is the callback.
		self.assertEqual(args[0][1], plugin._checkDeferredBlank)

	# ------------------------------------------------------------------
	# _cancelDeferredBlank stops existing timer
	# ------------------------------------------------------------------

	def test_cancel_stops_timer(self):
		"""_cancelDeferredBlank must Stop() the timer and set it to None."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		mock_timer = MagicMock()
		plugin._deferredBlankTimer = mock_timer

		plugin._cancelDeferredBlank()

		mock_timer.Stop.assert_called_once()
		self.assertIsNone(plugin._deferredBlankTimer)

	def test_cancel_noop_when_no_timer(self):
		"""_cancelDeferredBlank must be safe to call when no timer is pending."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._deferredBlankTimer = None

		# Should not raise.
		plugin._cancelDeferredBlank()
		self.assertIsNone(plugin._deferredBlankTimer)


if __name__ == '__main__':
	unittest.main()
