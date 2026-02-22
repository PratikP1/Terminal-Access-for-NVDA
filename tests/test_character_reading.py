"""
Tests for Terminal Access character reading functionality.

Tests cover the direct implementation of review cursor character reading
to ensure comma and period gestures don't type characters.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys


class TestCharacterReading(unittest.TestCase):
	"""Test character reading scripts."""

	def test_readReviewCharacter_helper_exists(self):
		"""Test that _readReviewCharacter helper function exists."""
		from globalPlugins.terminalAccess import GlobalPlugin

		self.assertTrue(hasattr(GlobalPlugin, '_readReviewCharacter'))
		method = getattr(GlobalPlugin, '_readReviewCharacter')
		self.assertTrue(callable(method))

	@patch('globalPlugins.terminalAccess.api')
	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.ui')
	def test_readReviewCharacter_current_character(self, mock_ui, mock_speech, mock_api):
		"""Test reading current character without movement."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()

		# Mock review position
		mock_info = MagicMock()
		mock_info.copy.return_value = mock_info
		mock_info.text = 'a'
		mock_api.getReviewPosition.return_value = mock_info

		# Call the helper
		plugin._readReviewCharacter(movement=0, phonetic=False)

		# Verify speech was called
		mock_speech.speakTextInfo.assert_called_once()

	@patch('globalPlugins.terminalAccess.api')
	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.ui')
	def test_readReviewCharacter_phonetic(self, mock_ui, mock_speech, mock_api):
		"""Test reading character with phonetic spelling."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()

		# Mock review position
		mock_info = MagicMock()
		mock_info.copy.return_value = mock_info
		mock_info.text = 'a'
		mock_api.getReviewPosition.return_value = mock_info

		# Call the helper with phonetic mode
		plugin._readReviewCharacter(movement=0, phonetic=True)

		# Verify spelling was used
		mock_speech.speakSpelling.assert_called_once_with('a')

	@patch('globalPlugins.terminalAccess.api')
	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.ui')
	def test_readReviewCharacter_next_character(self, mock_ui, mock_speech, mock_api):
		"""Test reading next character with movement."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()

		# Mock review position and movement
		mock_info = MagicMock()
		mock_copy = MagicMock()
		mock_copy.move.return_value = 1  # Successful move
		mock_copy.text = 'b'
		mock_info.copy.return_value = mock_copy
		mock_api.getReviewPosition.return_value = mock_info

		# Call the helper with forward movement
		plugin._readReviewCharacter(movement=1, phonetic=False)

		# Verify movement was attempted
		mock_copy.move.assert_called_once()
		# Verify setReviewPosition was called to update position
		mock_api.setReviewPosition.assert_called()

	@patch('globalPlugins.terminalAccess.api')
	@patch('globalPlugins.terminalAccess.ui')
	def test_readReviewCharacter_no_review_position(self, mock_ui, mock_api):
		"""Test behavior when no review position available."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()

		# Mock no review position
		mock_api.getReviewPosition.return_value = None
		plugin._boundTerminal = None

		# Call the helper
		plugin._readReviewCharacter(movement=0)

		# Verify error message was shown
		mock_ui.message.assert_called_once()

	def test_script_readCurrentChar_uses_helper(self):
		"""Test that script_readCurrentChar uses _readReviewCharacter."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		# Mock scriptHandler to simulate single press
		with patch('globalPlugins.terminalAccess.scriptHandler.getLastScriptRepeatCount', return_value=0):
			plugin.script_readCurrentChar(mock_gesture)

		# Verify helper was called with correct parameters
		plugin._readReviewCharacter.assert_called_once_with(movement=0)

	def test_script_readNextChar_uses_helper(self):
		"""Test that script_readNextChar uses _readReviewCharacter."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		plugin.script_readNextChar(mock_gesture)

		# Verify helper was called with forward movement
		plugin._readReviewCharacter.assert_called_once_with(movement=1)

	def test_script_readPreviousChar_uses_helper(self):
		"""Test that script_readPreviousChar uses _readReviewCharacter."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		plugin.script_readPreviousChar(mock_gesture)

		# Verify helper was called with backward movement
		plugin._readReviewCharacter.assert_called_once_with(movement=-1)

	def test_script_readCurrentChar_phonetic_on_double_press(self):
		"""Test that double-press triggers phonetic reading."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		# Mock scriptHandler to simulate double press
		with patch('globalPlugins.terminalAccess.scriptHandler.getLastScriptRepeatCount', return_value=1):
			plugin.script_readCurrentChar(mock_gesture)

		# Verify helper was called with phonetic=True
		plugin._readReviewCharacter.assert_called_once_with(movement=0, phonetic=True)

	def test_script_readCurrentChar_character_code_on_triple_press(self):
		"""Test that triple-press triggers character code announcement."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._announceCharacterCode = MagicMock()

		# Mock scriptHandler to simulate triple press
		with patch('globalPlugins.terminalAccess.scriptHandler.getLastScriptRepeatCount', return_value=2):
			plugin.script_readCurrentChar(mock_gesture)

		# Verify character code function was called
		plugin._announceCharacterCode.assert_called_once()

	def test_gestures_dont_propagate_to_globalCommands(self):
		"""Test that comma and period gestures don't call globalCommands."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		# Mock globalCommands to ensure it's not called
		with patch('globalPlugins.terminalAccess.globalCommands') as mock_globalCommands:
			# Test comma gesture (current character)
			with patch('globalPlugins.terminalAccess.scriptHandler.getLastScriptRepeatCount', return_value=0):
				plugin.script_readCurrentChar(mock_gesture)

			# Test period gesture (next character)
			plugin.script_readNextChar(mock_gesture)

			# Verify globalCommands was never accessed for review functions
			mock_globalCommands.commands.script_review_currentCharacter.assert_not_called()
			mock_globalCommands.commands.script_review_nextCharacter.assert_not_called()


if __name__ == '__main__':
	unittest.main()
