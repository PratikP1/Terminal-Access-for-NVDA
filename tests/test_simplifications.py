"""Tests for code simplifications in terminalAccess.py.

Tests the extracted shared methods:
- _readDirectional(): shared logic for readToLeft/Right/Top/Bottom
- _navigateSearch(): shared logic for findNext/findPrevious
- _initializeManagers(): loop-based manager initialization
- _copyAndAnnounce(): shared copy-and-message helper
- ConfigManager-based config access
"""

import sys
import pytest
from unittest.mock import MagicMock, Mock, patch, PropertyMock


class TestReadDirectional:
	"""Tests for _readDirectional shared method."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		return plugin

	def _make_review_position(self, text="hello world"):
		pos = MagicMock()
		copy = MagicMock()
		copy.text = text
		pos.copy.return_value = copy
		return pos

	# --- left direction: truncates line FROM cursor to start ---

	def test_readDirectional_left_calls_setEndPoint_endToEnd(self):
		"""'left' should truncate line end to cursor via setEndPoint(reviewPos, 'endToEnd')."""
		plugin = self._make_plugin()
		pos = self._make_review_position("hello")
		plugin._getReviewPosition = MagicMock(return_value=pos)
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("left")

		line_copy = pos.copy.return_value
		line_copy.setEndPoint.assert_called_once_with(pos, "endToEnd")

	def test_readDirectional_left_speaks_correct_text(self):
		"""'left' should speak the text from the truncated line range."""
		plugin = self._make_plugin()
		pos = self._make_review_position()
		line_copy = pos.copy.return_value
		line_copy.text = "left-of-cursor"
		plugin._getReviewPosition = MagicMock(return_value=pos)
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("left")
		speech.speakText.assert_called_once_with("left-of-cursor")

	# --- right direction: truncates line FROM start to cursor ---

	def test_readDirectional_right_calls_setEndPoint_startToStart(self):
		"""'right' should truncate line start to cursor via setEndPoint(reviewPos, 'startToStart')."""
		plugin = self._make_plugin()
		pos = self._make_review_position("world")
		plugin._getReviewPosition = MagicMock(return_value=pos)
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("right")

		line_copy = pos.copy.return_value
		line_copy.setEndPoint.assert_called_once_with(pos, "startToStart")

	def test_readDirectional_right_speaks_correct_text(self):
		"""'right' should speak the text from cursor to line end."""
		plugin = self._make_plugin()
		pos = self._make_review_position()
		line_copy = pos.copy.return_value
		line_copy.text = "right-of-cursor"
		plugin._getReviewPosition = MagicMock(return_value=pos)
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("right")
		speech.speakText.assert_called_once_with("right-of-cursor")

	# --- top direction: uses POSITION_FIRST ---

	def test_readDirectional_top_uses_POSITION_FIRST(self):
		"""'top' should call terminal.makeTextInfo(textInfos.POSITION_FIRST)."""
		import textInfos
		plugin = self._make_plugin()
		pos = self._make_review_position()
		plugin._getReviewPosition = MagicMock(return_value=pos)
		terminal = MagicMock()
		range_info = MagicMock()
		range_info.text = "buffer text from top"
		terminal.makeTextInfo.return_value = range_info
		plugin._boundTerminal = terminal
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("top")
		terminal.makeTextInfo.assert_called_once_with(textInfos.POSITION_FIRST)

	def test_readDirectional_top_sets_endpoint_endToEnd(self):
		"""'top' should set the range end to cursor position."""
		plugin = self._make_plugin()
		pos = self._make_review_position()
		plugin._getReviewPosition = MagicMock(return_value=pos)
		terminal = MagicMock()
		range_info = MagicMock()
		range_info.text = "buffer text from top"
		terminal.makeTextInfo.return_value = range_info
		plugin._boundTerminal = terminal
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("top")
		range_info.setEndPoint.assert_called_once_with(pos, "endToEnd")

	def test_readDirectional_top_speaks_correct_text(self):
		"""'top' should speak the text from buffer start to cursor."""
		plugin = self._make_plugin()
		pos = self._make_review_position()
		plugin._getReviewPosition = MagicMock(return_value=pos)
		terminal = MagicMock()
		range_info = MagicMock()
		range_info.text = "all text above cursor"
		terminal.makeTextInfo.return_value = range_info
		plugin._boundTerminal = terminal
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("top")
		speech.speakText.assert_called_once_with("all text above cursor")

	# --- bottom direction: uses POSITION_LAST ---

	def test_readDirectional_bottom_uses_POSITION_LAST(self):
		"""'bottom' should call terminal.makeTextInfo(textInfos.POSITION_LAST)."""
		import textInfos
		plugin = self._make_plugin()
		pos = MagicMock()
		pos.text = "cursor to end text"
		plugin._getReviewPosition = MagicMock(return_value=pos)
		terminal = MagicMock()
		end_info = MagicMock()
		terminal.makeTextInfo.return_value = end_info
		plugin._boundTerminal = terminal
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("bottom")
		terminal.makeTextInfo.assert_called_once_with(textInfos.POSITION_LAST)

	def test_readDirectional_bottom_sets_endpoint_on_reviewPos(self):
		"""'bottom' should extend reviewPos end to buffer end via setEndPoint(endInfo, 'endToEnd')."""
		plugin = self._make_plugin()
		pos = MagicMock()
		pos.text = "cursor to end text"
		plugin._getReviewPosition = MagicMock(return_value=pos)
		terminal = MagicMock()
		end_info = MagicMock()
		terminal.makeTextInfo.return_value = end_info
		plugin._boundTerminal = terminal
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("bottom")
		pos.setEndPoint.assert_called_once_with(end_info, "endToEnd")

	def test_readDirectional_bottom_speaks_correct_text(self):
		"""'bottom' should speak text from cursor to buffer end."""
		plugin = self._make_plugin()
		pos = MagicMock()
		pos.text = "remaining buffer content"
		plugin._getReviewPosition = MagicMock(return_value=pos)
		terminal = MagicMock()
		end_info = MagicMock()
		terminal.makeTextInfo.return_value = end_info
		plugin._boundTerminal = terminal
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("bottom")
		speech.speakText.assert_called_once_with("remaining buffer content")

	# --- left expands the line before truncating ---

	def test_readDirectional_left_expands_line(self):
		"""'left' should expand the copied range to UNIT_LINE before truncating."""
		import textInfos
		plugin = self._make_plugin()
		pos = self._make_review_position("hello")
		plugin._getReviewPosition = MagicMock(return_value=pos)
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("left")
		line_copy = pos.copy.return_value
		line_copy.expand.assert_called_once_with(textInfos.UNIT_LINE)

	def test_readDirectional_right_expands_line(self):
		"""'right' should expand the copied range to UNIT_LINE before truncating."""
		import textInfos
		plugin = self._make_plugin()
		pos = self._make_review_position("world")
		plugin._getReviewPosition = MagicMock(return_value=pos)
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("right")
		line_copy = pos.copy.return_value
		line_copy.expand.assert_called_once_with(textInfos.UNIT_LINE)

	# --- edge cases ---

	def test_readDirectional_no_review_position_announces_unable(self):
		"""_readDirectional should announce 'Unable to read' when no review position."""
		plugin = self._make_plugin()
		plugin._getReviewPosition = MagicMock(return_value=None)
		import ui
		ui.message = MagicMock()

		plugin._readDirectional("left")
		ui.message.assert_called_once_with("Unable to read")

	def test_readDirectional_empty_text_announces_nothing(self):
		"""_readDirectional should announce 'Nothing' when text is empty."""
		plugin = self._make_plugin()
		pos = self._make_review_position("")
		copy = pos.copy.return_value
		copy.text = ""
		plugin._getReviewPosition = MagicMock(return_value=pos)
		import ui
		ui.message = MagicMock()

		plugin._readDirectional("left")
		ui.message.assert_called_once_with("Nothing")

	def test_readDirectional_whitespace_only_announces_nothing(self):
		"""_readDirectional should announce 'Nothing' when text is whitespace only."""
		plugin = self._make_plugin()
		pos = self._make_review_position()
		copy = pos.copy.return_value
		copy.text = "   \t  "
		plugin._getReviewPosition = MagicMock(return_value=pos)
		import ui
		ui.message = MagicMock()

		plugin._readDirectional("left")
		ui.message.assert_called_once_with("Nothing")

	def test_readDirectional_sends_to_braille(self):
		"""_readDirectional should send the same text to braille display."""
		plugin = self._make_plugin()
		pos = self._make_review_position()
		copy = pos.copy.return_value
		copy.text = "braille text"
		plugin._getReviewPosition = MagicMock(return_value=pos)
		plugin._brailleMessage = MagicMock()
		import speech
		speech.speakText = MagicMock()

		plugin._readDirectional("left")
		plugin._brailleMessage.assert_called_once_with("braille text")

	def test_readDirectional_top_no_terminal_announces_unable(self):
		"""_readDirectional('top') should announce error when no terminal bound."""
		plugin = self._make_plugin()
		pos = self._make_review_position("text")
		plugin._getReviewPosition = MagicMock(return_value=pos)
		plugin._boundTerminal = None
		import ui
		ui.message = MagicMock()

		plugin._readDirectional("top")
		ui.message.assert_called_once_with("Unable to read")

	def test_readDirectional_bottom_no_terminal_announces_unable(self):
		"""_readDirectional('bottom') should announce error when no terminal bound."""
		plugin = self._make_plugin()
		pos = self._make_review_position("text")
		plugin._getReviewPosition = MagicMock(return_value=pos)
		plugin._boundTerminal = None
		import ui
		ui.message = MagicMock()

		plugin._readDirectional("bottom")
		ui.message.assert_called_once_with("Unable to read")

	# --- script delegation tests ---

	def test_script_readToLeft_delegates_to_readDirectional(self):
		"""script_readToLeft should call _readDirectional('left')."""
		plugin = self._make_plugin()
		plugin._readDirectional = MagicMock()
		gesture = MagicMock()

		plugin.script_readToLeft(gesture)
		plugin._readDirectional.assert_called_once_with("left")

	def test_script_readToRight_delegates_to_readDirectional(self):
		"""script_readToRight should call _readDirectional('right')."""
		plugin = self._make_plugin()
		plugin._readDirectional = MagicMock()
		gesture = MagicMock()

		plugin.script_readToRight(gesture)
		plugin._readDirectional.assert_called_once_with("right")

	def test_script_readToTop_delegates_to_readDirectional(self):
		"""script_readToTop should call _readDirectional('top')."""
		plugin = self._make_plugin()
		plugin._readDirectional = MagicMock()
		gesture = MagicMock()

		plugin.script_readToTop(gesture)
		plugin._readDirectional.assert_called_once_with("top")

	def test_script_readToBottom_delegates_to_readDirectional(self):
		"""script_readToBottom should call _readDirectional('bottom')."""
		plugin = self._make_plugin()
		plugin._readDirectional = MagicMock()
		gesture = MagicMock()

		plugin.script_readToBottom(gesture)
		plugin._readDirectional.assert_called_once_with("bottom")

	def test_script_readToLeft_sends_gesture_when_not_terminal(self):
		"""script_readToLeft should pass-through gesture when not in terminal."""
		plugin = self._make_plugin()
		plugin.isTerminalApp = MagicMock(return_value=False)
		gesture = MagicMock()

		plugin.script_readToLeft(gesture)
		gesture.send.assert_called_once()


class TestNavigateSearch:
	"""Tests for _navigateSearch shared method."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		return plugin

	def test_navigateSearch_next_calls_next_match(self):
		"""_navigateSearch('next') should call searchManager.next_match()."""
		plugin = self._make_plugin()
		plugin._searchManager = MagicMock()
		plugin._searchManager.get_match_count.return_value = 5
		plugin._searchManager.next_match.return_value = True
		plugin._searchManager.get_current_match_info.return_value = (1, 5, "line text", 3)

		import ui
		ui.message = MagicMock()

		plugin._navigateSearch("next")
		plugin._searchManager.next_match.assert_called_once()

	def test_navigateSearch_previous_calls_previous_match(self):
		"""_navigateSearch('previous') should call searchManager.previous_match()."""
		plugin = self._make_plugin()
		plugin._searchManager = MagicMock()
		plugin._searchManager.get_match_count.return_value = 5
		plugin._searchManager.previous_match.return_value = True
		plugin._searchManager.get_current_match_info.return_value = (1, 5, "line text", 3)

		import ui
		ui.message = MagicMock()

		plugin._navigateSearch("previous")
		plugin._searchManager.previous_match.assert_called_once()

	def test_navigateSearch_no_matches_announces_message(self):
		"""_navigateSearch should announce when there are no search results."""
		plugin = self._make_plugin()
		plugin._searchManager = MagicMock()
		plugin._searchManager.get_match_count.return_value = 0

		import ui
		ui.message = MagicMock()

		plugin._navigateSearch("next")
		ui.message.assert_called()

	def test_navigateSearch_no_manager_returns_early(self):
		"""_navigateSearch should return early when no search manager."""
		plugin = self._make_plugin()
		plugin._searchManager = None

		# Should not raise
		plugin._navigateSearch("next")

	def test_navigateSearch_announces_line_text(self):
		"""_navigateSearch should announce the matched line text."""
		plugin = self._make_plugin()
		plugin._searchManager = MagicMock()
		plugin._searchManager.get_match_count.return_value = 5
		plugin._searchManager.next_match.return_value = True
		plugin._searchManager.get_current_match_info.return_value = (2, 5, "found line", 7)

		import ui
		ui.message = MagicMock()

		plugin._navigateSearch("next")
		ui.message.assert_called_with("found line")

	def test_navigateSearch_failed_jump_announces_error(self):
		"""_navigateSearch should announce error when jump fails."""
		plugin = self._make_plugin()
		plugin._searchManager = MagicMock()
		plugin._searchManager.get_match_count.return_value = 5
		plugin._searchManager.next_match.return_value = False

		import ui
		ui.message = MagicMock()

		plugin._navigateSearch("next")
		ui.message.assert_called()

	def test_script_findNext_delegates_to_navigateSearch(self):
		"""script_findNext should call _navigateSearch('next')."""
		plugin = self._make_plugin()
		plugin._navigateSearch = MagicMock()
		gesture = MagicMock()

		plugin.script_findNext(gesture)
		plugin._navigateSearch.assert_called_once_with("next")

	def test_script_findPrevious_delegates_to_navigateSearch(self):
		"""script_findPrevious should call _navigateSearch('previous')."""
		plugin = self._make_plugin()
		plugin._navigateSearch = MagicMock()
		gesture = MagicMock()

		plugin.script_findPrevious(gesture)
		plugin._navigateSearch.assert_called_once_with("previous")


class TestInitializeManagersLoop:
	"""Tests for loop-based _initializeManagers."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		return plugin

	def _make_terminal(self, app_name='windowsterminal'):
		terminal = MagicMock()
		terminal.appModule.appName = app_name
		return terminal

	def test_creates_all_five_managers(self):
		"""_initializeManagers should create all 5 managers."""
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._initializeManagers(terminal)
		assert plugin._tabManager is not None
		assert plugin._bookmarkManager is not None
		assert plugin._searchManager is not None
		assert plugin._commandHistoryManager is not None
		assert plugin._urlExtractorManager is not None

	def test_updates_existing_managers(self):
		"""_initializeManagers should update (not recreate) existing managers."""
		plugin = self._make_plugin()
		terminal1 = self._make_terminal()
		plugin._initializeManagers(terminal1)
		tab_mgr = plugin._tabManager
		bookmark_mgr = plugin._bookmarkManager
		search_mgr = plugin._searchManager
		history_mgr = plugin._commandHistoryManager
		url_mgr = plugin._urlExtractorManager

		terminal2 = self._make_terminal()
		plugin._initializeManagers(terminal2)

		# Same instances, just updated
		assert plugin._tabManager is tab_mgr
		assert plugin._bookmarkManager is bookmark_mgr
		assert plugin._searchManager is search_mgr
		assert plugin._commandHistoryManager is history_mgr
		assert plugin._urlExtractorManager is url_mgr

	def test_update_terminal_called_on_existing(self):
		"""_initializeManagers should call update_terminal on existing managers."""
		plugin = self._make_plugin()
		terminal1 = self._make_terminal()
		plugin._initializeManagers(terminal1)

		terminal2 = self._make_terminal()
		plugin._tabManager.update_terminal = MagicMock()
		plugin._bookmarkManager.update_terminal = MagicMock()
		plugin._searchManager.update_terminal = MagicMock()
		plugin._commandHistoryManager.update_terminal = MagicMock()
		plugin._urlExtractorManager.update_terminal = MagicMock()

		plugin._initializeManagers(terminal2)

		plugin._tabManager.update_terminal.assert_called_once_with(terminal2)
		plugin._bookmarkManager.update_terminal.assert_called_once_with(terminal2)
		plugin._searchManager.update_terminal.assert_called_once_with(terminal2)
		plugin._commandHistoryManager.update_terminal.assert_called_once_with(terminal2)
		plugin._urlExtractorManager.update_terminal.assert_called_once_with(terminal2)


class TestCopyAndAnnounce:
	"""Tests for _copyAndAnnounce helper."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		return plugin

	def test_copy_success_announces_message(self):
		"""_copyAndAnnounce should announce success message on successful copy."""
		plugin = self._make_plugin()
		plugin._copyToClipboard = MagicMock(return_value=True)

		import ui
		ui.message = MagicMock()

		result = plugin._copyAndAnnounce("hello world", "Copied")
		assert result is True
		ui.message.assert_called_once()

	def test_copy_failure_announces_unable(self):
		"""_copyAndAnnounce should announce failure when copy fails."""
		plugin = self._make_plugin()
		plugin._copyToClipboard = MagicMock(return_value=False)

		import ui
		ui.message = MagicMock()

		result = plugin._copyAndAnnounce("hello world", "Copied")
		assert result is False
		ui.message.assert_called_once()

	def test_empty_text_announces_unable(self):
		"""_copyAndAnnounce should announce failure for empty text."""
		plugin = self._make_plugin()
		plugin._copyToClipboard = MagicMock()

		import ui
		ui.message = MagicMock()

		result = plugin._copyAndAnnounce("", "Copied")
		assert result is False
		plugin._copyToClipboard.assert_not_called()

	def test_none_text_announces_unable(self):
		"""_copyAndAnnounce should announce failure for None text."""
		plugin = self._make_plugin()
		plugin._copyToClipboard = MagicMock()

		import ui
		ui.message = MagicMock()

		result = plugin._copyAndAnnounce(None, "Copied")
		assert result is False

	def test_custom_success_message(self):
		"""_copyAndAnnounce should use the custom success message."""
		plugin = self._make_plugin()
		plugin._copyToClipboard = MagicMock(return_value=True)

		import ui
		ui.message = MagicMock()

		plugin._copyAndAnnounce("text", "Line copied")
		# The success message should match what was passed
		call_args = ui.message.call_args[0][0]
		assert "copied" in call_args.lower() or "Line" in call_args


class TestConfigAccessStandardization:
	"""Tests that config access uses ConfigManager where appropriate."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		return plugin

	def test_getExcludedGestures_uses_config_manager(self):
		"""_getExcludedGestures should use self._configManager.get()."""
		plugin = self._make_plugin()
		plugin._configManager = MagicMock()
		plugin._configManager.get.return_value = ""

		plugin._getExcludedGestures()
		plugin._configManager.get.assert_called()

	def test_detectAndApplyProfile_uses_config_manager_for_default(self):
		"""_detectAndApplyProfile should use self._configManager for defaultProfile."""
		plugin = self._make_plugin()
		terminal = MagicMock()
		terminal.appModule.appName = 'windowsterminal'
		plugin._profileManager.detect_application = MagicMock(return_value='default')
		plugin._configManager = MagicMock()
		plugin._configManager.get.return_value = ""

		plugin._detectAndApplyProfile(terminal)
		plugin._configManager.get.assert_called()
