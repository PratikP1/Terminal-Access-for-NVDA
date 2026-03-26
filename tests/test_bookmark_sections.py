"""
Tests for bookmark auto-labeling and section list dialog.

RED phase: all tests written before implementation.
"""
import sys
from unittest.mock import Mock, MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager_with_buffer(buffer_lines, cursor_line_idx=0):
    """Create a BookmarkManager with a mock terminal whose buffer is buffer_lines.

    The mock api.getReviewPosition() returns a TextInfo on the line at
    cursor_line_idx. The SectionTokenizer is available via import.

    Returns (manager, mock_pos) so the caller can patch api.getReviewPosition.
    """
    from lib.navigation import BookmarkManager

    terminal = Mock()
    manager = BookmarkManager(terminal)

    line_text = buffer_lines[cursor_line_idx] if cursor_line_idx < len(buffer_lines) else ""
    mock_pos = Mock()
    mock_pos.bookmark = "bm_obj"
    mock_pos.text = line_text

    # _resolve_line_number calls pos.copy(), then collapse/move on the copy.
    # We need the copy to have proper move behavior too.
    move_count = [0]
    def fake_move_back(unit, count):
        if count == -1 and move_count[0] < cursor_line_idx:
            move_count[0] += 1
            return -1
        return 0

    # expand(UNIT_LINE) returns the full line
    expanded_copy = Mock()
    expanded_copy.text = line_text
    def fake_expand(unit):
        expanded_copy.text = line_text
    expanded_copy.expand = fake_expand
    expanded_copy.collapse = Mock()
    expanded_copy.move = fake_move_back

    mock_pos.copy = Mock(return_value=expanded_copy)
    mock_pos.collapse = Mock()
    mock_pos.move = fake_move_back

    # Store buffer lines on the manager for _auto_label to use
    manager._buffer_lines = buffer_lines

    return manager, mock_pos


# ---------------------------------------------------------------------------
# 1. Auto-label: prompt line
# ---------------------------------------------------------------------------


def test_auto_label_prompt_line():
    """Bookmark on a prompt line gets label 'prompt: <command text>'."""
    from lib.navigation import BookmarkManager

    buffer = [
        "user@host:~/project$ cargo build",
        "   Compiling myproject v0.1.0",
        "   Finished dev target",
    ]
    manager, mock_pos = _make_manager_with_buffer(buffer, cursor_line_idx=0)

    with patch('api.getReviewPosition', return_value=mock_pos):
        result = manager.set_bookmark("1")

    assert result is True
    label = manager.get_bookmark_label("1")
    assert label.startswith("prompt:"), f"Expected 'prompt:' prefix, got: {label!r}"
    assert "cargo build" in label


# ---------------------------------------------------------------------------
# 2. Auto-label: error line
# ---------------------------------------------------------------------------


def test_auto_label_error_line():
    """Bookmark on an error line gets label 'error: <first 40 chars>'."""
    from lib.navigation import BookmarkManager

    buffer = [
        "$ make",
        "error: cannot find module 'foo' in the specified path location",
        "make: *** [Makefile:10: all] Error 1",
    ]
    manager, mock_pos = _make_manager_with_buffer(buffer, cursor_line_idx=1)

    with patch('api.getReviewPosition', return_value=mock_pos):
        result = manager.set_bookmark("1")

    assert result is True
    label = manager.get_bookmark_label("1")
    assert label.startswith("error:"), f"Expected 'error:' prefix, got: {label!r}"


# ---------------------------------------------------------------------------
# 3. Auto-label: heading line
# ---------------------------------------------------------------------------


def test_auto_label_heading_line():
    """Bookmark on a heading line gets label 'heading: <heading text>'."""
    from lib.navigation import BookmarkManager

    buffer = [
        "BUILD RESULTS",
        "=============",
        "All tests passed.",
    ]
    manager, mock_pos = _make_manager_with_buffer(buffer, cursor_line_idx=0)

    with patch('api.getReviewPosition', return_value=mock_pos):
        result = manager.set_bookmark("1")

    assert result is True
    label = manager.get_bookmark_label("1")
    assert label.startswith("heading:"), f"Expected 'heading:' prefix, got: {label!r}"
    assert "BUILD RESULTS" in label


# ---------------------------------------------------------------------------
# 4. Auto-label: near prompt (within 5 lines)
# ---------------------------------------------------------------------------


def test_auto_label_near_prompt():
    """Bookmark near a prompt (within 5 lines) includes the command name."""
    from lib.navigation import BookmarkManager

    buffer = [
        "user@host:~/project$ cargo build",
        "   Compiling myproject v0.1.0",
        "   Compiling dependency v0.2.0",
        "   Finished dev target",
        "warning: unused variable `x`",
    ]
    # Cursor on line 3, which is 3 lines after the prompt at line 0
    manager, mock_pos = _make_manager_with_buffer(buffer, cursor_line_idx=3)

    with patch('api.getReviewPosition', return_value=mock_pos):
        result = manager.set_bookmark("1")

    assert result is True
    label = manager.get_bookmark_label("1")
    assert "cargo build" in label, f"Expected command name in label, got: {label!r}"


# ---------------------------------------------------------------------------
# 5. Auto-label: fallback to line text
# ---------------------------------------------------------------------------


def test_auto_label_fallback_line_text():
    """When no context detected, fall back to first 50 chars of line text."""
    from lib.navigation import BookmarkManager

    buffer = [
        "some random output that is not a prompt or error",
    ]
    manager, mock_pos = _make_manager_with_buffer(buffer, cursor_line_idx=0)

    with patch('api.getReviewPosition', return_value=mock_pos):
        result = manager.set_bookmark("1")

    assert result is True
    label = manager.get_bookmark_label("1")
    # Should be the line text itself (trimmed), not prefixed
    assert label == "some random output that is not a prompt or error"


# ---------------------------------------------------------------------------
# 6. Auto-label: truncated at 50 chars
# ---------------------------------------------------------------------------


def test_auto_label_truncated():
    """Auto-generated labels over 50 chars are truncated."""
    from lib.navigation import BookmarkManager

    long_line = "A" * 100
    buffer = [long_line]
    manager, mock_pos = _make_manager_with_buffer(buffer, cursor_line_idx=0)

    with patch('api.getReviewPosition', return_value=mock_pos):
        result = manager.set_bookmark("1")

    assert result is True
    label = manager.get_bookmark_label("1")
    assert len(label) <= 50, f"Label should be <= 50 chars, got {len(label)}"


# ---------------------------------------------------------------------------
# 7. Section list: returns sections
# ---------------------------------------------------------------------------


def test_section_list_returns_sections():
    """list_sections returns all detected sections in the buffer."""
    from lib.navigation import BookmarkManager

    buffer = [
        "user@host:~$ ls",
        "file1.txt  file2.txt",
        "error: permission denied",
        "BUILD RESULTS",
    ]
    manager, _ = _make_manager_with_buffer(buffer)
    sections = manager.list_sections(buffer)

    assert len(sections) > 0, "Should return at least one section"


# ---------------------------------------------------------------------------
# 8. Section list: has type column
# ---------------------------------------------------------------------------


def test_section_list_has_type_column():
    """Each section entry has a 'type' field."""
    from lib.navigation import BookmarkManager

    buffer = [
        "user@host:~$ ls",
        "file1.txt",
        "error: something failed",
    ]
    manager, _ = _make_manager_with_buffer(buffer)
    sections = manager.list_sections(buffer)

    for section in sections:
        assert "type" in section, f"Section missing 'type' key: {section}"


# ---------------------------------------------------------------------------
# 9. Section list: has line number
# ---------------------------------------------------------------------------


def test_section_list_has_line_number():
    """Each section entry has a 'line_num' field."""
    from lib.navigation import BookmarkManager

    buffer = [
        "user@host:~$ ls",
        "file1.txt",
    ]
    manager, _ = _make_manager_with_buffer(buffer)
    sections = manager.list_sections(buffer)

    for section in sections:
        assert "line_num" in section, f"Section missing 'line_num' key: {section}"


# ---------------------------------------------------------------------------
# 10. Section list: has preview
# ---------------------------------------------------------------------------


def test_section_list_has_preview():
    """Each section entry has a 'preview' field with first 50 chars."""
    from lib.navigation import BookmarkManager

    long_line = "x" * 100
    buffer = [long_line]
    manager, _ = _make_manager_with_buffer(buffer)
    sections = manager.list_sections(buffer)

    for section in sections:
        assert "preview" in section, f"Section missing 'preview' key: {section}"
        assert len(section["preview"]) <= 50


# ---------------------------------------------------------------------------
# 11. Section list: filter by type
# ---------------------------------------------------------------------------


def test_section_list_filter_by_type():
    """list_sections can filter to a specific section type."""
    from lib.navigation import BookmarkManager

    buffer = [
        "user@host:~$ ls",
        "file1.txt",
        "error: something failed",
        "another output line",
        "error: another error",
    ]
    manager, _ = _make_manager_with_buffer(buffer)
    errors_only = manager.list_sections(buffer, category="error")

    assert len(errors_only) > 0
    for section in errors_only:
        assert section["type"] == "error", f"Expected only errors, got: {section['type']}"


# ---------------------------------------------------------------------------
# 12. Existing bookmarks still work (regression)
# ---------------------------------------------------------------------------


def test_existing_bookmarks_still_work():
    """Regression: set/jump/list bookmarks work exactly as before."""
    from lib.navigation import BookmarkManager

    terminal = Mock()
    mock_ti = Mock()
    terminal.makeTextInfo = Mock(return_value=mock_ti)
    manager = BookmarkManager(terminal)

    mock_pos = Mock()
    mock_pos.bookmark = "bm_obj"
    mock_pos.text = "some output line"
    expanded_copy = Mock()
    expanded_copy.text = "some output line"
    expanded_copy.expand = Mock()
    mock_pos.copy = Mock(return_value=expanded_copy)

    with patch('api.getReviewPosition', return_value=mock_pos):
        assert manager.set_bookmark("1") is True

    assert manager.has_bookmark("1")

    bookmarks = manager.list_bookmarks()
    assert len(bookmarks) == 1
    assert bookmarks[0]["name"] == "1"
    assert "label" in bookmarks[0]

    with patch('api.setReviewPosition') as mock_set:
        result = manager.jump_to_bookmark("1")
    assert result is True
    mock_set.assert_called_once()


# ---------------------------------------------------------------------------
# 13. Bookmark label overridable
# ---------------------------------------------------------------------------


def test_bookmark_label_overridable():
    """User can change the auto-generated label via rename_bookmark."""
    from lib.navigation import BookmarkManager

    buffer = [
        "user@host:~$ cargo build",
    ]
    manager, mock_pos = _make_manager_with_buffer(buffer, cursor_line_idx=0)

    with patch('api.getReviewPosition', return_value=mock_pos):
        manager.set_bookmark("1")

    # Auto-label should be set
    original_label = manager.get_bookmark_label("1")
    assert original_label is not None

    # Rename it
    result = manager.rename_bookmark("1", "my custom label")
    assert result is True
    assert manager.get_bookmark_label("1") == "my custom label"
