"""
Tests for bookmark functionality in Terminal Access.
"""
import sys
from unittest.mock import Mock, MagicMock, patch
import pytest


def test_bookmark_manager_set_and_jump():
	"""Test that bookmarks can be set and jumped to."""
	from globalPlugins.terminalAccess import BookmarkManager

	# Create mock terminal
	terminal = Mock()

	# Create mock TextInfo with a bookmark
	mock_textinfo = Mock()
	mock_textinfo.bookmark = "test_bookmark_obj"

	# Setup terminal to return TextInfo when makeTextInfo is called
	terminal.makeTextInfo = Mock(return_value=mock_textinfo)

	# Mock api.getReviewPosition to return the TextInfo
	with patch('api.getReviewPosition', return_value=mock_textinfo):
		with patch('api.setReviewPosition') as mock_set_review:
			# Create BookmarkManager
			manager = BookmarkManager(terminal)

			# Set a bookmark
			result = manager.set_bookmark("1")
			assert result is True
			assert manager.has_bookmark("1")

			# Jump to the bookmark
			result = manager.jump_to_bookmark("1")
			assert result is True

			# Verify that setReviewPosition was called
			mock_set_review.assert_called_once()


def test_bookmark_manager_terminal_rebind():
	"""Test that BookmarkManager works when terminal is rebound."""
	from globalPlugins.terminalAccess import BookmarkManager

	# Create first mock terminal
	terminal1 = Mock()
	mock_textinfo1 = Mock()
	mock_textinfo1.bookmark = "bookmark1"
	terminal1.makeTextInfo = Mock(return_value=mock_textinfo1)

	# Create BookmarkManager with first terminal
	manager = BookmarkManager(terminal1)

	# Set a bookmark with first terminal
	with patch('api.getReviewPosition', return_value=mock_textinfo1):
		result = manager.set_bookmark("1")
		assert result is True

	# Now simulate terminal rebind - create a new terminal object
	terminal2 = Mock()
	mock_textinfo2 = Mock()
	mock_textinfo2.bookmark = "bookmark1"  # Same bookmark content
	terminal2.makeTextInfo = Mock(return_value=mock_textinfo2)

	# Update the terminal reference (this is what should happen on rebind)
	manager._terminal = terminal2

	# Try to jump to bookmark with new terminal
	with patch('api.setReviewPosition') as mock_set_review:
		result = manager.jump_to_bookmark("1")
		assert result is True
		mock_set_review.assert_called_once()


def test_bookmark_manager_list_bookmarks():
	"""Test listing bookmarks."""
	from globalPlugins.terminalAccess import BookmarkManager

	terminal = Mock()
	manager = BookmarkManager(terminal)

	# Create mock TextInfos
	mock_textinfo1 = Mock()
	mock_textinfo1.bookmark = "bookmark1"
	mock_textinfo2 = Mock()
	mock_textinfo2.bookmark = "bookmark2"

	# Set multiple bookmarks
	with patch('api.getReviewPosition', return_value=mock_textinfo1):
		manager.set_bookmark("1")

	with patch('api.getReviewPosition', return_value=mock_textinfo2):
		manager.set_bookmark("2")

	# List bookmarks
	bookmarks = manager.list_bookmarks()
	assert len(bookmarks) == 2
	assert "1" in bookmarks
	assert "2" in bookmarks


def test_bookmark_manager_no_terminal():
	"""Test that BookmarkManager handles missing terminal gracefully."""
	from globalPlugins.terminalAccess import BookmarkManager

	manager = BookmarkManager(None)

	# Should fail gracefully
	assert manager.set_bookmark("1") is False
	assert manager.jump_to_bookmark("1") is False
	assert manager.list_bookmarks() == []
