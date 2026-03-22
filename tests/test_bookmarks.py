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
	"""Test listing bookmarks returns structured data with name, label, bookmark."""
	from globalPlugins.terminalAccess import BookmarkManager

	terminal = Mock()
	manager = BookmarkManager(terminal)

	# Create mock TextInfos with text content
	mock_textinfo1 = Mock()
	mock_textinfo1.bookmark = "bookmark1"
	mock_textinfo1.text = "First line content"
	mock_textinfo2 = Mock()
	mock_textinfo2.bookmark = "bookmark2"
	mock_textinfo2.text = "Second line content"

	# Set multiple bookmarks
	with patch('api.getReviewPosition', return_value=mock_textinfo1):
		manager.set_bookmark("1")

	with patch('api.getReviewPosition', return_value=mock_textinfo2):
		manager.set_bookmark("2")

	# List bookmarks - now returns list of dicts
	bookmarks = manager.list_bookmarks()
	assert len(bookmarks) == 2
	names = [bm["name"] for bm in bookmarks]
	assert "1" in names
	assert "2" in names


def test_bookmark_manager_no_terminal():
	"""Test that BookmarkManager handles missing terminal gracefully."""
	from globalPlugins.terminalAccess import BookmarkManager

	manager = BookmarkManager(None)

	# Should fail gracefully
	assert manager.set_bookmark("1") is False
	assert manager.jump_to_bookmark("1") is False
	assert manager.list_bookmarks() == []


# --- Enhanced bookmark label tests (TDD) ---


def test_bookmark_stores_line_content_as_label():
	"""When a bookmark is set, it captures the current line text as its label."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm_obj"
	mock_pos.text = "    ERROR: Connection refused to database server"

	with patch('api.getReviewPosition', return_value=mock_pos):
		result = manager.set_bookmark("1")

	assert result is True
	bookmarks = manager.list_bookmarks()
	assert len(bookmarks) == 1
	assert bookmarks[0]["name"] == "1"
	assert "ERROR: Connection refused" in bookmarks[0]["label"]


def test_bookmark_label_trimmed_to_50_chars():
	"""Long line text should be truncated to 50 characters."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm_obj"
	mock_pos.text = "A" * 100

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	bookmarks = manager.list_bookmarks()
	assert len(bookmarks[0]["label"]) <= 50


def test_bookmark_label_for_blank_line():
	"""Blank lines should get a descriptive label."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm_obj"
	mock_pos.text = "   \t  "

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	bookmarks = manager.list_bookmarks()
	assert bookmarks[0]["label"]  # Should not be empty
	assert "blank" in bookmarks[0]["label"].lower()


def test_list_bookmarks_returns_structured_data():
	"""list_bookmarks should return list of dicts with name, label, bookmark keys."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos1 = Mock()
	mock_pos1.bookmark = "bm1"
	mock_pos1.text = "First line"
	mock_pos2 = Mock()
	mock_pos2.bookmark = "bm2"
	mock_pos2.text = "Second line"

	with patch('api.getReviewPosition', return_value=mock_pos1):
		manager.set_bookmark("1")
	with patch('api.getReviewPosition', return_value=mock_pos2):
		manager.set_bookmark("2")

	bookmarks = manager.list_bookmarks()
	assert len(bookmarks) == 2
	for bm in bookmarks:
		assert "name" in bm
		assert "label" in bm
		assert "bookmark" in bm


def test_overwriting_bookmark_updates_label():
	"""Setting a bookmark to a slot that already has one should update the label."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos1 = Mock()
	mock_pos1.bookmark = "bm1"
	mock_pos1.text = "Old content"
	mock_pos2 = Mock()
	mock_pos2.bookmark = "bm2"
	mock_pos2.text = "New content"

	with patch('api.getReviewPosition', return_value=mock_pos1):
		manager.set_bookmark("1")
	with patch('api.getReviewPosition', return_value=mock_pos2):
		manager.set_bookmark("1")

	bookmarks = manager.list_bookmarks()
	assert len(bookmarks) == 1
	assert "New content" in bookmarks[0]["label"]


def test_remove_bookmark_with_labels():
	"""Removing a bookmark should work with the new label structure."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm1"
	mock_pos.text = "Some line"

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	assert manager.remove_bookmark("1") is True
	assert manager.list_bookmarks() == []


def test_jump_still_works_with_labels():
	"""jump_to_bookmark should still work correctly after the label enhancement."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	mock_ti = Mock()
	terminal.makeTextInfo = Mock(return_value=mock_ti)
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm_obj"
	mock_pos.text = "Error line"

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	with patch('api.setReviewPosition') as mock_set:
		result = manager.jump_to_bookmark("1")

	assert result is True
	mock_set.assert_called_once()


def test_has_bookmark_still_works():
	"""has_bookmark should work with the new structure."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm1"
	mock_pos.text = "Line"

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	assert manager.has_bookmark("1") is True
	assert manager.has_bookmark("2") is False


def test_get_bookmark_count_works():
	"""get_bookmark_count should work with the new structure."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	assert manager.get_bookmark_count() == 0

	mock_pos = Mock()
	mock_pos.bookmark = "bm1"
	mock_pos.text = "Line"

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	assert manager.get_bookmark_count() == 1


def test_clear_all_works():
	"""clear_all should clear all bookmarks."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm1"
	mock_pos.text = "Line"

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")
		manager.set_bookmark("2")

	manager.clear_all()
	assert manager.get_bookmark_count() == 0


def test_tab_aware_bookmarks_with_labels():
	"""Tab-aware storage should work with the new label structure."""
	from lib.navigation import BookmarkManager, TabManager
	terminal = Mock()
	terminal.windowHandle = 12345
	terminal.windowText = "Tab 1"
	tab_mgr = TabManager(terminal)
	manager = BookmarkManager(terminal, tab_manager=tab_mgr)

	mock_pos = Mock()
	mock_pos.bookmark = "bm1"
	mock_pos.text = "Tab 1 bookmark"

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	bookmarks = manager.list_bookmarks()
	assert len(bookmarks) == 1
	assert "Tab 1 bookmark" in bookmarks[0]["label"]


def test_bookmark_label_strips_whitespace():
	"""Bookmark label should strip leading/trailing whitespace from line text."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm_obj"
	mock_pos.text = "   hello world   "

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	bookmarks = manager.list_bookmarks()
	assert bookmarks[0]["label"] == "hello world"


def test_bookmark_get_label():
	"""get_bookmark_label returns the label for a given bookmark name."""
	from lib.navigation import BookmarkManager
	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = "bm_obj"
	mock_pos.text = "Important error message"

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("3")

	assert manager.get_bookmark_label("3") == "Important error message"
	assert manager.get_bookmark_label("5") is None


def test_bookmark_label_captures_full_line_not_review_unit():
	"""Bookmark label must capture the full line text, not just the review unit.

	When the review cursor is on a single character, getReviewPosition().text
	returns that character. set_bookmark must expand to the full line to get
	a meaningful label.
	"""
	from globalPlugins.terminalAccess import BookmarkManager

	terminal = Mock()

	# Simulate NVDA review position: text is just one character (review unit)
	# but the line has full content accessible via expand(UNIT_LINE)
	mock_pos = Mock()
	mock_pos.bookmark = "bm_char"
	mock_pos.text = "e"  # Single character at review cursor

	# copy() returns a new TextInfo; expand() updates its text to full line
	expanded_copy = Mock()
	expanded_copy.text = "e"  # Before expand
	def fake_expand(unit):
		expanded_copy.text = "error: something failed on line 42"
	expanded_copy.expand = fake_expand
	mock_pos.copy = Mock(return_value=expanded_copy)

	import textInfos
	manager = BookmarkManager(terminal)

	with patch('api.getReviewPosition', return_value=mock_pos):
		result = manager.set_bookmark("1")

	assert result is True
	label = manager.get_bookmark_label("1")
	# Label should be the full line, not just "e"
	assert label == "error: something failed on line 42", (
		f"Expected full line text, got: '{label}'"
	)


def test_bookmark_label_not_blank_for_non_empty_line():
	"""A bookmark on a non-empty line must never have a blank label."""
	from globalPlugins.terminalAccess import BookmarkManager

	terminal = Mock()

	# Review position has empty text (single char position on whitespace)
	# but the line has actual content
	mock_pos = Mock()
	mock_pos.bookmark = "bm_ws"
	mock_pos.text = " "  # Whitespace at cursor position

	expanded_copy = Mock()
	expanded_copy.text = " "  # Before expand
	def fake_expand(unit):
		expanded_copy.text = "    indented code line"
	expanded_copy.expand = fake_expand
	mock_pos.copy = Mock(return_value=expanded_copy)

	import textInfos
	manager = BookmarkManager(terminal)

	with patch('api.getReviewPosition', return_value=mock_pos):
		result = manager.set_bookmark("2")

	assert result is True
	label = manager.get_bookmark_label("2")
	assert label != "(blank line)", (
		f"Bookmark label should not be blank when line has content"
	)
	assert "indented code line" in label


def test_jump_to_bookmark_with_none_bookmark_uses_line_number():
	"""Jump must work even when bookmark object is None.

	Many terminal UIA implementations don't support bookmarks, so
	pos.bookmark returns None. jump_to_bookmark must fall back to
	navigating by line number using POSITION_FIRST + move(UNIT_LINE).
	"""
	from lib.navigation import BookmarkManager
	import textInfos

	terminal = Mock()
	manager = BookmarkManager(terminal)

	# Set a bookmark where pos.bookmark is None (common in terminals)
	mock_pos = Mock()
	mock_pos.bookmark = None
	mock_pos.text = "error on line 42"
	# Make expand a no-op so text stays as-is (already a full line)
	mock_pos.expand = Mock()
	# For _resolve_line_number: collapse is fine, move(-1) succeeds 4 times
	mock_pos.collapse = Mock()
	move_count = [0]
	def fake_move_back(unit, count):
		if count == -1 and move_count[0] < 4:
			move_count[0] += 1
			return -1
		return 0
	mock_pos.move = fake_move_back
	# copy() returns the same mock (for both expand and resolve paths)
	mock_pos.copy = Mock(return_value=mock_pos)

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("1")

	# Verify bookmark has line_num
	bookmarks_dict = manager._get_bookmark_dict()
	assert bookmarks_dict["1"]["line_num"] == 5
	assert bookmarks_dict["1"]["bookmark"] is None

	# Now jump — makeTextInfo(None) should NOT be called.
	# Only makeTextInfo(POSITION_FIRST) should be called.
	jump_target = Mock()
	jump_target.expand = Mock()
	terminal.makeTextInfo = Mock(return_value=jump_target)

	with patch('api.setReviewPosition') as mock_set:
		result = manager.jump_to_bookmark("1")

	assert result is True, "Jump should succeed with None bookmark by using line number"
	mock_set.assert_called_once()
	terminal.makeTextInfo.assert_called_once_with(textInfos.POSITION_FIRST)
	# Should have moved 4 lines (to line 5)
	jump_target.move.assert_called_with(textInfos.UNIT_LINE, 4)


def test_jump_to_bookmark_does_not_silently_delete():
	"""Jump must not silently delete a bookmark when bookmark obj is None.

	Previous behavior: makeTextInfo(None) throws, exception handler
	deletes the bookmark. User's bookmark disappears without explanation.
	"""
	from lib.navigation import BookmarkManager

	terminal = Mock()
	manager = BookmarkManager(terminal)

	mock_pos = Mock()
	mock_pos.bookmark = None
	mock_pos.text = "important line"
	mock_pos.copy = Mock(return_value=mock_pos)
	mock_pos.expand = Mock()

	with patch('api.getReviewPosition', return_value=mock_pos):
		manager.set_bookmark("5")

	assert manager.has_bookmark("5")

	# Jump — even if it fails, bookmark must survive
	terminal.makeTextInfo = Mock(side_effect=Exception("no bookmark support"))

	with patch('api.setReviewPosition'):
		manager.jump_to_bookmark("5")

	assert manager.has_bookmark("5"), (
		"Bookmark was silently deleted after failed jump. "
		"Bookmarks must persist even when jump fails."
	)
