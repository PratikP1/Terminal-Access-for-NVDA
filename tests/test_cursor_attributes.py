"""
Tests for cursor attribute reading functionality.

Tests cover the script_readAttributes function and related text range extraction.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys


class TestCursorAttributes(unittest.TestCase):
	"""Test cursor attribute reading."""

	@patch('globalPlugins.terminalAccess.ui')
	@patch('globalPlugins.terminalAccess.textInfos')
	def test_script_readAttributes_gets_text_range_correctly(self, mock_textInfos, mock_ui):
		"""Test that script_readAttributes constructs the text range correctly."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()
		plugin._boundTerminal = Mock()

		# Mock gesture
		mock_gesture = Mock()

		# Setup mock text info objects
		mock_reviewPos = MagicMock()
		mock_lineStart = MagicMock()
		mock_textToCursor = MagicMock()
		mock_cursorChar = MagicMock()

		# Configure the mock chain
		mock_reviewPos.copy.side_effect = [mock_lineStart, mock_cursorChar]
		mock_lineStart.copy.return_value = mock_textToCursor
		mock_textToCursor.text = '\x1b[31mRed text'  # Text with ANSI codes

		# Mock the review position
		with patch.object(plugin, '_getReviewPosition', return_value=mock_reviewPos):
			with patch.object(plugin, 'isTerminalApp', return_value=True):
				# Call the script
				plugin.script_readAttributes(mock_gesture)

		# Verify the text range construction sequence
		# 1. reviewPos.copy() to create lineStart
		assert mock_reviewPos.copy.call_count >= 2

		# 2. lineStart.expand(UNIT_LINE) to expand to full line
		mock_lineStart.expand.assert_called_once()

		# 3. lineStart.collapse() to collapse to start
		mock_lineStart.collapse.assert_called_once()

		# 4. lineStart.copy() to create textToCursor
		mock_lineStart.copy.assert_called_once()

		# 5. cursorChar.expand(UNIT_CHARACTER) to expand to character
		mock_cursorChar.expand.assert_called_once()

		# 6. textToCursor.setEndPoint(cursorChar, "endToEnd") to set end point
		mock_textToCursor.setEndPoint.assert_called_once_with(mock_cursorChar, "endToEnd")

		# 7. Verify ui.message was called with formatted attributes
		mock_ui.message.assert_called_once()
		# The message should contain color information
		message = mock_ui.message.call_args[0][0]
		self.assertIn('red', message.lower())

	@patch('globalPlugins.terminalAccess.ui')
	def test_script_readAttributes_with_no_terminal(self, mock_ui):
		"""Test that script_readAttributes sends gesture when not in terminal."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		mock_gesture = Mock()

		with patch.object(plugin, 'isTerminalApp', return_value=False):
			plugin.script_readAttributes(mock_gesture)

		# Verify gesture was sent through
		mock_gesture.send.assert_called_once()

	@patch('globalPlugins.terminalAccess.ui')
	def test_script_readAttributes_with_no_review_position(self, mock_ui):
		"""Test script_readAttributes handles missing review position."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		mock_gesture = Mock()

		with patch.object(plugin, 'isTerminalApp', return_value=True):
			with patch.object(plugin, '_getReviewPosition', return_value=None):
				plugin.script_readAttributes(mock_gesture)

		# Verify error message was shown
		mock_ui.message.assert_called_once()
		message = mock_ui.message.call_args[0][0]
		self.assertIn('Unable', message)

	@patch('globalPlugins.terminalAccess.ui')
	@patch('globalPlugins.terminalAccess.textInfos')
	def test_script_readAttributes_with_empty_text(self, mock_textInfos, mock_ui):
		"""Test script_readAttributes handles empty text at cursor."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._boundTerminal = Mock()
		mock_gesture = Mock()

		# Setup mock with empty text
		mock_reviewPos = MagicMock()
		mock_lineStart = MagicMock()
		mock_textToCursor = MagicMock()
		mock_cursorChar = MagicMock()

		mock_reviewPos.copy.side_effect = [mock_lineStart, mock_cursorChar]
		mock_lineStart.copy.return_value = mock_textToCursor
		mock_textToCursor.text = ''  # Empty text

		with patch.object(plugin, '_getReviewPosition', return_value=mock_reviewPos):
			with patch.object(plugin, 'isTerminalApp', return_value=True):
				plugin.script_readAttributes(mock_gesture)

		# Verify "No text at cursor" message was shown
		mock_ui.message.assert_called_once()
		message = mock_ui.message.call_args[0][0]
		self.assertIn('No text', message)

	@patch('globalPlugins.terminalAccess.ui')
	@patch('globalPlugins.terminalAccess.textInfos')
	def test_script_readAttributes_with_bold_text(self, mock_textInfos, mock_ui):
		"""Test script_readAttributes detects bold formatting."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._boundTerminal = Mock()
		mock_gesture = Mock()

		# Setup mock with bold ANSI code
		mock_reviewPos = MagicMock()
		mock_lineStart = MagicMock()
		mock_textToCursor = MagicMock()
		mock_cursorChar = MagicMock()

		mock_reviewPos.copy.side_effect = [mock_lineStart, mock_cursorChar]
		mock_lineStart.copy.return_value = mock_textToCursor
		mock_textToCursor.text = '\x1b[1mBold text'  # Bold ANSI code

		with patch.object(plugin, '_getReviewPosition', return_value=mock_reviewPos):
			with patch.object(plugin, 'isTerminalApp', return_value=True):
				plugin.script_readAttributes(mock_gesture)

		# Verify bold was detected
		mock_ui.message.assert_called_once()
		message = mock_ui.message.call_args[0][0]
		self.assertIn('bold', message.lower())


class TestTextRangeExtraction(unittest.TestCase):
	"""Test text range extraction in various reading functions."""

	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.textInfos')
	def test_script_readToLeft_text_range(self, mock_textInfos, mock_speech):
		"""Test that script_readToLeft creates correct text range."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._boundTerminal = Mock()
		mock_gesture = Mock()

		# Setup mocks
		mock_reviewPos = MagicMock()
		mock_lineInfo = MagicMock()
		mock_reviewPos.copy.return_value = mock_lineInfo
		mock_lineInfo.text = 'text from left'

		with patch.object(plugin, '_getReviewPosition', return_value=mock_reviewPos):
			with patch.object(plugin, 'isTerminalApp', return_value=True):
				plugin.script_readToLeft(mock_gesture)

		# Verify setEndPoint was called with correct parameters
		mock_lineInfo.setEndPoint.assert_called_once_with(mock_reviewPos, "endToEnd")
		mock_speech.speakText.assert_called_once()

	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.textInfos')
	def test_script_readToTop_text_range(self, mock_textInfos, mock_speech):
		"""Test that script_readToTop creates correct text range."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		terminal = Mock()
		plugin._boundTerminal = terminal
		mock_gesture = Mock()

		# Setup mocks
		mock_reviewPos = MagicMock()
		mock_startInfo = MagicMock()
		mock_startInfo.text = 'text from top'
		terminal.makeTextInfo.return_value = mock_startInfo

		with patch.object(plugin, '_getReviewPosition', return_value=mock_reviewPos):
			with patch.object(plugin, 'isTerminalApp', return_value=True):
				plugin.script_readToTop(mock_gesture)

		# Verify setEndPoint was called with correct parameters
		mock_startInfo.setEndPoint.assert_called_once_with(mock_reviewPos, "endToEnd")
		mock_speech.speakText.assert_called_once()


if __name__ == '__main__':
	unittest.main()
