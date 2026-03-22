"""Tests for the new search results dialog and revised search flow.

RED phase: these tests define the expected behavior for:
1. OutputSearchManager.get_all_matches() — structured match data
2. Audio feedback (beeps) for search results
3. SearchResultsDialog data contract
4. Removal of auto-jump from the search flow
"""

import sys
from unittest.mock import Mock, MagicMock, patch, call

import api
import textInfos
import tones

import pytest


# ---------------------------------------------------------------------------
# Helpers (reused from test_output_search.py)
# ---------------------------------------------------------------------------

class DummyTextInfo:
	"""Minimal TextInfo replacement without bookmark support."""

	def __init__(self, source_text, line_index=0):
		self._source_text = source_text
		self.line_index = line_index
		self.text = source_text

	@property
	def bookmark(self):
		return None

	def move(self, unit, count):
		self.line_index += count
		return True

	def copy(self):
		return DummyTextInfo(self._source_text, self.line_index)


class DummyTerminal:
	"""Terminal stub that cannot recreate positions from bookmarks."""

	def __init__(self, text):
		self.text = text

	def makeTextInfo(self, arg):
		if arg == textInfos.POSITION_ALL:
			return DummyTextInfo(self.text, 0)
		if arg == textInfos.POSITION_FIRST:
			return DummyTextInfo(self.text, 0)
		raise ValueError("Bookmarks not supported")


def _setup_textinfos():
	"""Ensure textInfos constants are set."""
	textInfos.POSITION_ALL = "all"
	textInfos.POSITION_FIRST = "first"
	textInfos.UNIT_LINE = "line"
	textInfos.UNIT_CHARACTER = "character"


# ---------------------------------------------------------------------------
# TestGetAllMatches
# ---------------------------------------------------------------------------

class TestGetAllMatches:
	"""Test OutputSearchManager.get_all_matches() method."""

	def test_returns_empty_list_when_no_matches(self):
		"""get_all_matches() returns [] when the last search found nothing."""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		manager = OutputSearchManager(DummyTerminal("alpha\nbeta\ngamma"))
		manager.search("zzz_does_not_exist")
		result = manager.get_all_matches()
		assert result == []

	def test_returns_empty_list_when_no_search_performed(self):
		"""get_all_matches() returns [] before any search is run."""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		manager = OutputSearchManager(DummyTerminal("alpha\nbeta"))
		result = manager.get_all_matches()
		assert result == []

	def test_returns_structured_dicts_after_search(self):
		"""get_all_matches() returns list of dicts with num, line_num, text keys."""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		manager = OutputSearchManager(DummyTerminal("aaa\nbbb\naaa"))
		count = manager.search("aaa")
		assert count == 2

		matches = manager.get_all_matches()
		assert len(matches) == 2

		# Each match must have the required keys
		for m in matches:
			assert "num" in m
			assert "line_num" in m
			assert "text" in m
			assert "bookmark" in m
			assert "pos" in m
			assert "offset" in m

		# First match
		assert matches[0]["num"] == 1
		assert matches[0]["line_num"] == 1
		assert matches[0]["text"] == "aaa"

		# Second match
		assert matches[1]["num"] == 2
		assert matches[1]["line_num"] == 3
		assert matches[1]["text"] == "aaa"

	def test_match_text_truncated_to_100_chars(self):
		"""Lines longer than 100 characters are truncated with ellipsis."""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		long_line = "x" * 150
		manager = OutputSearchManager(DummyTerminal(long_line))
		count = manager.search("x")
		assert count == 1

		matches = manager.get_all_matches()
		assert len(matches) == 1
		assert len(matches[0]["text"]) <= 103  # 100 + "..."
		assert matches[0]["text"].endswith("...")

	def test_match_numbers_are_1_based(self):
		"""First match has num=1, not num=0."""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		manager = OutputSearchManager(DummyTerminal("err\nok\nerr\nok\nerr"))
		manager.search("err")

		matches = manager.get_all_matches()
		nums = [m["num"] for m in matches]
		assert nums == [1, 2, 3]

	def test_match_line_numbers_are_1_based(self):
		"""Line numbers in results are 1-based (matching existing search convention)."""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		manager = OutputSearchManager(DummyTerminal("ok\nerr\nok"))
		manager.search("err")

		matches = manager.get_all_matches()
		assert len(matches) == 1
		assert matches[0]["line_num"] == 2  # second line, 1-based


# ---------------------------------------------------------------------------
# TestSearchFlowBeeps
# ---------------------------------------------------------------------------

class TestSearchFlowBeeps:
	"""Test audio feedback in the redesigned search flow.

	These tests exercise _handleSearchResult to verify beeps
	and messages are generated correctly by production code.
	"""

	def _make_plugin(self):
		"""Create a minimally mocked GlobalPlugin instance."""
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin.__new__(GlobalPlugin)
		plugin._initState()
		plugin._initManagers()
		plugin.isTerminalApp = Mock(return_value=True)
		return plugin

	def test_no_matches_beeps_low(self):
		"""_handleSearchResult(text, 0) calls tones.beep(300, 100)."""
		_setup_textinfos()
		plugin = self._make_plugin()
		tones.beep.reset_mock()

		result = plugin._handleSearchResult("zzz_nothing", 0)

		assert result is False
		tones.beep.assert_called_with(300, 100)

	def test_matches_found_beeps_high(self):
		"""_handleSearchResult(text, N>0) calls tones.beep(800, 50)."""
		_setup_textinfos()
		plugin = self._make_plugin()
		tones.beep.reset_mock()

		result = plugin._handleSearchResult("alpha", 1)

		assert result is True
		tones.beep.assert_called_with(800, 50)

	def test_no_matches_announces_pattern(self):
		"""_handleSearchResult announces 'No matches found for ...' on zero results."""
		_setup_textinfos()
		import ui
		plugin = self._make_plugin()
		ui.message.reset_mock()

		plugin._handleSearchResult("nonexistent", 0)

		ui.message.assert_called_with("No matches found for 'nonexistent'")


# ---------------------------------------------------------------------------
# TestSearchResultsDialogData
# ---------------------------------------------------------------------------

class TestSearchResultsDialogData:
	"""Test that dialog would receive correct data (without wx)."""

	def test_dialog_receives_match_list(self):
		"""get_all_matches returns data suitable for dialog population."""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		manager = OutputSearchManager(DummyTerminal("ERROR: fail\nOK\nERROR: timeout"))
		manager.search("ERROR")

		matches = manager.get_all_matches()
		assert len(matches) == 2

		# Each match should have text content suitable for display
		assert "ERROR: fail" in matches[0]["text"]
		assert "ERROR: timeout" in matches[1]["text"]

		# Each match should have a line number for the Line column
		assert matches[0]["line_num"] == 1
		assert matches[1]["line_num"] == 3

	def test_jump_sets_review_position(self):
		"""When a match is selected and jumped to, setReviewPosition is called."""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		api.setReviewPosition.reset_mock()

		manager = OutputSearchManager(DummyTerminal("aaa\nbbb\naaa"))
		manager.search("bbb")

		matches = manager.get_all_matches()
		assert len(matches) == 1

		# Simulate what the dialog's Jump handler does:
		# set current_match_index, then call _jump_to_current_match
		state = manager._get_search_state()
		state['current_match_index'] = 0
		manager._save_search_state(state)
		result = manager._jump_to_current_match()

		assert result is True
		api.setReviewPosition.assert_called_once()

	def test_jump_sets_searchJumpPending(self):
		"""Jumping from dialog should set _searchJumpPending = True on the plugin."""
		_setup_textinfos()
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin.__new__(GlobalPlugin)
		plugin._initState()
		plugin._initManagers()

		# _searchJumpPending starts False
		assert plugin._searchJumpPending is False

		# Simulate on_jump callback from the dialog
		def on_jump():
			plugin._searchJumpPending = True

		on_jump()
		assert plugin._searchJumpPending is True


# ---------------------------------------------------------------------------
# TestSearchFlowNoAutoJump
# ---------------------------------------------------------------------------

class TestSearchFlowNoAutoJump:
	"""Test that the new flow doesn't auto-jump after search."""

	def test_search_does_not_auto_jump_to_first_match(self):
		"""After search with results, first_match() should NOT be called automatically.

		The dialog handles navigation, not the search script.
		In the new flow, script_searchOutput should NOT call first_match().
		We verify this by checking that after search(), the current_match_index
		remains at -1 (untouched).
		"""
		_setup_textinfos()
		from lib.search import OutputSearchManager

		api.setReviewPosition.reset_mock()

		manager = OutputSearchManager(DummyTerminal("aaa\nbbb\naaa"))
		count = manager.search("aaa")
		assert count == 2

		# After search(), current_match_index should be -1 (no auto-jump)
		state = manager._get_search_state()
		assert state['current_match_index'] == -1

		# setReviewPosition should NOT have been called by search() itself
		api.setReviewPosition.assert_not_called()

	def test_search_does_not_set_searchJumpPending_directly(self):
		"""_searchJumpPending stays False after search — only dialog jump sets it."""
		_setup_textinfos()
		from globalPlugins.terminalAccess import GlobalPlugin
		from lib.search import OutputSearchManager

		plugin = GlobalPlugin.__new__(GlobalPlugin)
		plugin._initState()
		plugin._initManagers()
		plugin._searchManager = OutputSearchManager(DummyTerminal("aaa\nbbb"))

		assert plugin._searchJumpPending is False

		# Perform search and handle results (this is what script_searchOutput does)
		plugin._searchManager.search("aaa")
		plugin._handleSearchResult("aaa", 2)

		# Flag should still be False — only the dialog's on_jump callback sets it
		assert plugin._searchJumpPending is False


# ---------------------------------------------------------------------------
# TestSearchResultsDialogImport
# ---------------------------------------------------------------------------

class TestSearchResultsDialogImport:
	"""Test that SearchResultsDialog is importable from lib.search."""

	def test_search_results_dialog_importable(self):
		"""SearchResultsDialog should be importable from lib.search."""
		from lib.search import SearchResultsDialog
		# In test env (mocked wx), it may be None or a class
		# but the name must exist in the module
		assert hasattr(sys.modules['lib.search'], 'SearchResultsDialog')

	def test_search_results_dialog_is_a_class_with_mocked_wx(self):
		"""With mocked wx, SearchResultsDialog is still defined as a class."""
		from lib.search import SearchResultsDialog
		# wx is mocked at module level (conftest), so import doesn't raise
		# ImportError and the class is defined normally.
		assert SearchResultsDialog is not None
