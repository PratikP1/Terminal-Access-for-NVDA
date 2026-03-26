"""Tests for scoped search, search history, and fuzzy matching.

RED/GREEN TDD: these tests are written first to drive the implementation
of scoped search (buffer vs section), search history (last 10 patterns),
and fuzzy matching fallback (Levenshtein distance 1).
"""

import re
from unittest.mock import Mock, MagicMock, patch

import pytest

from lib.search import OutputSearchManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_terminal_with_lines(lines):
    """Build a mock terminal whose makeTextInfo returns joined lines."""
    terminal = Mock()
    text = "\n".join(lines)
    info = Mock()
    info.text = text
    terminal.makeTextInfo = Mock(return_value=info)
    return terminal


# ---------------------------------------------------------------------------
# Scoped search
# ---------------------------------------------------------------------------

class TestScopedSearch:
    """Scoped search: buffer (default) vs section."""

    def test_search_whole_buffer(self):
        """search(pattern) with scope='buffer' finds all matches across
        the entire terminal buffer."""
        lines = [
            "$ make build",
            "compiling main.c",
            "error: undefined reference",
            "compiling util.c",
            "error: missing header",
        ]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        count = mgr.search("error", scope="buffer")
        assert count == 2

    def test_search_scoped_to_section(self):
        """search(pattern, scope='section') limits results to the current
        section as determined by SectionTokenizer."""
        lines = [
            "$ make build",
            "compiling main.c",
            "error: undefined reference",
            "$ make test",
            "compiling test.c",
            "error: assertion failed",
            "error: test aborted",
        ]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        # Simulate cursor on line 5 (inside the second command section).
        # The section tokenizer should identify the span containing line 5,
        # so only errors within that span are returned.
        count = mgr.search("error", scope="section", current_line=5)

        # Lines 5 and 6 contain "error" in the second section.
        assert count == 2

    def test_search_scope_default_buffer(self):
        """When scope is omitted, search defaults to 'buffer'."""
        lines = [
            "hello world",
            "hello again",
        ]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        count = mgr.search("hello")
        assert count == 2


# ---------------------------------------------------------------------------
# Search history
# ---------------------------------------------------------------------------

class TestSearchHistory:
    """Search history: stores recent patterns for reuse."""

    def test_search_history_stores_patterns(self):
        """Patterns are recorded after a search is performed."""
        terminal = _make_terminal_with_lines(["error here"])
        mgr = OutputSearchManager(terminal)

        mgr.search("error")
        assert "error" in mgr.get_history()

    def test_search_history_max_10(self):
        """Only the last 10 patterns are kept."""
        terminal = _make_terminal_with_lines(["x"])
        mgr = OutputSearchManager(terminal)

        for i in range(15):
            mgr.search(f"pattern{i}")

        history = mgr.get_history()
        assert len(history) == 10
        # The oldest 5 should have been evicted.
        assert "pattern0" not in history
        assert "pattern14" in history

    def test_search_history_no_duplicates(self):
        """Searching for the same pattern again does not create a
        duplicate entry; the existing entry is moved to the front."""
        terminal = _make_terminal_with_lines(["hello world"])
        mgr = OutputSearchManager(terminal)

        mgr.search("hello")
        mgr.search("world")
        mgr.search("hello")

        history = mgr.get_history()
        assert history.count("hello") == 1
        # "hello" should be the most recent (first element).
        assert history[0] == "hello"

    def test_search_history_most_recent_first(self):
        """History is ordered newest to oldest."""
        terminal = _make_terminal_with_lines(["abc def ghi"])
        mgr = OutputSearchManager(terminal)

        mgr.search("abc")
        mgr.search("def")
        mgr.search("ghi")

        history = mgr.get_history()
        assert history == ["ghi", "def", "abc"]


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

class TestFuzzyMatch:
    """Fuzzy matching: automatic fallback when exact search finds nothing."""

    def test_fuzzy_match_simple_typo(self):
        """'erorr' (transposition) matches lines containing 'error'
        when exact search fails."""
        lines = [
            "build complete",
            "error: file not found",
            "done",
        ]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        results = mgr.fuzzy_search("erorr", lines)
        assert len(results) > 0
        assert any("error" in r.lower() for r in results)

    def test_fuzzy_match_case_insensitive(self):
        """Fuzzy matching is case-insensitive: 'ERROR' matches 'error'."""
        lines = ["error: something broke"]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        results = mgr.fuzzy_search("ERROR", lines)
        assert len(results) > 0

    def test_fuzzy_match_not_triggered_on_exact(self):
        """When exact search finds matches, fuzzy fallback does not
        trigger and the search returns only exact results."""
        lines = [
            "error: real error",
            "warning: not an error",
        ]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        count = mgr.search("error")
        # Both lines contain "error", so exact match works.
        assert count == 2
        # The result count should be exactly 2 (no extra fuzzy hits).

    def test_fuzzy_match_levenshtein_1(self):
        """A single character difference (insertion, deletion, or
        substitution) produces a Levenshtein distance of 1 and matches."""
        terminal = _make_terminal_with_lines([])
        mgr = OutputSearchManager(terminal)

        # Substitution: "cat" vs "bat"
        assert mgr._levenshtein_distance("cat", "bat") == 1
        # Insertion: "cat" vs "cats"
        assert mgr._levenshtein_distance("cat", "cats") == 1
        # Deletion: "cats" vs "cat"
        assert mgr._levenshtein_distance("cats", "cat") == 1

    def test_fuzzy_match_levenshtein_2_rejected(self):
        """Two or more character differences are rejected by fuzzy search."""
        lines = ["something completely different"]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        # "errrr" has distance >= 2 from every word in the line.
        results = mgr.fuzzy_search("errrr", lines)
        assert len(results) == 0

    def test_fuzzy_announces_fallback(self):
        """When fuzzy matching triggers as a fallback, the search method
        stores a message containing 'fuzzy match' for the caller."""
        lines = [
            "build started",
            "error: failed",
            "build complete",
        ]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        # "erorr" will not match exactly but should fuzzy-match "error".
        count = mgr.search("erorr")
        assert count > 0
        msg = mgr.get_last_search_message()
        assert "fuzzy" in msg.lower()

    def test_search_empty_pattern(self):
        """An empty search pattern returns 0 without errors."""
        terminal = _make_terminal_with_lines(["anything"])
        mgr = OutputSearchManager(terminal)

        count = mgr.search("")
        assert count == 0

    def test_search_in_empty_section(self):
        """Searching with scope='section' on a section with no lines
        returns 0 without crashing."""
        # Build a terminal with only a prompt (no output section).
        lines = ["$ echo hello"]
        terminal = _make_terminal_with_lines(lines)
        mgr = OutputSearchManager(terminal)

        count = mgr.search("anything", scope="section", current_line=0)
        assert count == 0
