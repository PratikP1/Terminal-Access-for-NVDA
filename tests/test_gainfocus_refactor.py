"""Tests for event_gainFocus refactoring and profile announcement."""

import sys
import pytest
from unittest.mock import MagicMock, Mock, patch


class TestOnTerminalFocus:
	"""Test _onTerminalFocus and its extracted helper methods."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		return plugin

	def _make_terminal(self, app_name='windowsterminal'):
		terminal = MagicMock()
		terminal.appModule.appName = app_name
		return terminal

	def test_onTerminalFocus_sets_bound_terminal(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._onTerminalFocus(terminal)
		assert plugin._boundTerminal is terminal

	def test_onTerminalFocus_bad_appmodule_returns_early(self):
		plugin = self._make_plugin()
		terminal = MagicMock()
		terminal.appModule = None
		type(terminal).appModule = property(lambda self: (_ for _ in ()).throw(AttributeError))
		# Should not raise
		plugin._onTerminalFocus(terminal)

	def test_startHelperIfNeeded_does_not_raise(self):
		plugin = self._make_plugin()
		# _startHelperIfNeeded should swallow exceptions
		plugin._startHelperIfNeeded()

	def test_handleSearchJumpSuppression_clears_flag(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._searchJumpPending = True
		plugin._handleSearchJumpSuppression(terminal)
		assert plugin._searchJumpPending is False

	def test_handleSearchJumpSuppression_sets_navigator_when_no_jump(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._searchJumpPending = False
		import api
		api.setNavigatorObject = MagicMock()
		plugin._handleSearchJumpSuppression(terminal)
		api.setNavigatorObject.assert_called_once_with(terminal)

	def test_initializeManagers_creates_all_managers(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		assert plugin._tabManager is None
		assert plugin._bookmarkManager is None
		assert plugin._searchManager is None
		assert plugin._commandHistoryManager is None
		assert plugin._urlExtractorManager is None
		plugin._initializeManagers(terminal)
		assert plugin._tabManager is not None
		assert plugin._bookmarkManager is not None
		assert plugin._searchManager is not None
		assert plugin._commandHistoryManager is not None
		assert plugin._urlExtractorManager is not None

	def test_initializeManagers_updates_existing(self):
		plugin = self._make_plugin()
		terminal1 = self._make_terminal()
		plugin._initializeManagers(terminal1)
		tab_mgr = plugin._tabManager
		terminal2 = self._make_terminal()
		plugin._initializeManagers(terminal2)
		# Same manager instance, updated
		assert plugin._tabManager is tab_mgr

	def test_detectAndApplyProfile_sets_profile(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		mock_profile = MagicMock()
		mock_profile.displayName = "vim"
		plugin._profileManager.detect_application = MagicMock(return_value='vim')
		plugin._profileManager.get_profile = MagicMock(return_value=mock_profile)
		plugin._detectAndApplyProfile(terminal)
		assert plugin._currentProfile is mock_profile

	def test_detectAndApplyProfile_default_when_no_app(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._profileManager.detect_application = MagicMock(return_value='default')
		import config
		config.conf = MagicMock()
		config.conf.__getitem__ = MagicMock(return_value={"defaultProfile": ""})
		plugin._detectAndApplyProfile(terminal)
		assert plugin._currentProfile is None

	def test_bindReviewCursor_uses_caret(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		mock_info = MagicMock()
		terminal.makeTextInfo = MagicMock(return_value=mock_info)
		import api
		api.setReviewPosition = MagicMock()
		plugin._bindReviewCursor(terminal)
		api.setReviewPosition.assert_called_once_with(mock_info)

	def test_bindReviewCursor_falls_back_to_last(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		import textInfos
		mock_info = MagicMock()
		call_count = [0]
		def side_effect(pos):
			call_count[0] += 1
			if call_count[0] == 1:
				raise RuntimeError("no caret")
			return mock_info
		terminal.makeTextInfo = side_effect
		import api
		api.setReviewPosition = MagicMock()
		plugin._bindReviewCursor(terminal)
		api.setReviewPosition.assert_called_once_with(mock_info)

	def test_announceHelpIfNeeded_announces_first_time(self):
		plugin = self._make_plugin()
		import ui
		ui.message = MagicMock()
		plugin.announcedHelp = False
		plugin._announceHelpIfNeeded('windowsterminal')
		ui.message.assert_called()
		assert plugin.announcedHelp is True
		assert plugin.lastTerminalAppName == 'windowsterminal'

	def test_announceHelpIfNeeded_announces_new_app(self):
		plugin = self._make_plugin()
		import ui
		ui.message = MagicMock()
		plugin.announcedHelp = True
		plugin.lastTerminalAppName = 'putty'
		plugin._announceHelpIfNeeded('windowsterminal')
		ui.message.assert_called()

	def test_announceHelpIfNeeded_silent_same_app(self):
		plugin = self._make_plugin()
		import ui
		ui.message = MagicMock()
		plugin.announcedHelp = True
		plugin.lastTerminalAppName = 'windowsterminal'
		plugin._announceHelpIfNeeded('windowsterminal')
		ui.message.assert_not_called()

	def test_event_gainFocus_delegates_to_onTerminalFocus(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._updateGestureBindingsForFocus = MagicMock(return_value=True)
		plugin._onTerminalFocus = MagicMock()
		next_handler = MagicMock()
		plugin.event_gainFocus(terminal, next_handler)
		next_handler.assert_called_once()
		plugin._onTerminalFocus.assert_called_once_with(terminal)

	def test_event_gainFocus_non_terminal_clears_bound(self):
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._updateGestureBindingsForFocus = MagicMock(return_value=False)
		next_handler = MagicMock()
		plugin.event_gainFocus(terminal, next_handler)
		assert plugin._boundTerminal is None


class TestAnnounceProfileIfNew:
	"""Test _announceProfileIfNew — profile detection transparency."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		return GlobalPlugin()

	def test_announces_profile_on_new_app(self):
		plugin = self._make_plugin()
		import ui
		ui.message = MagicMock()
		mock_profile = MagicMock()
		mock_profile.displayName = "vim"
		plugin._currentProfile = mock_profile
		plugin.lastTerminalAppName = 'putty'
		plugin._announceProfileIfNew(MagicMock(), 'windowsterminal')
		ui.message.assert_called_with("vim")

	def test_silent_on_same_app(self):
		plugin = self._make_plugin()
		import ui
		ui.message = MagicMock()
		mock_profile = MagicMock()
		mock_profile.displayName = "vim"
		plugin._currentProfile = mock_profile
		plugin.lastTerminalAppName = 'windowsterminal'
		plugin._announceProfileIfNew(MagicMock(), 'windowsterminal')
		ui.message.assert_not_called()

	def test_silent_when_no_profile(self):
		plugin = self._make_plugin()
		import ui
		ui.message = MagicMock()
		plugin._currentProfile = None
		plugin.lastTerminalAppName = 'putty'
		plugin._announceProfileIfNew(MagicMock(), 'windowsterminal')
		ui.message.assert_not_called()


class TestOnTerminalFocusEndToEnd:
	"""End-to-end tests for _onTerminalFocus calling its helper chain."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		return GlobalPlugin()

	def _make_terminal(self, app_name='windowsterminal'):
		terminal = MagicMock()
		terminal.appModule.appName = app_name
		return terminal

	def test_onTerminalFocus_calls_announceProfileIfNew(self):
		"""_onTerminalFocus should call _announceProfileIfNew."""
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._announceProfileIfNew = MagicMock()

		plugin._onTerminalFocus(terminal)

		plugin._announceProfileIfNew.assert_called_once_with(terminal, 'windowsterminal')

	def test_onTerminalFocus_calls_announceHelpIfNeeded(self):
		"""_onTerminalFocus should call _announceHelpIfNeeded with appName."""
		plugin = self._make_plugin()
		terminal = self._make_terminal('cmd')
		plugin._announceHelpIfNeeded = MagicMock()

		plugin._onTerminalFocus(terminal)

		plugin._announceHelpIfNeeded.assert_called_once_with('cmd')

	def test_onTerminalFocus_calls_detectAndApplyProfile(self):
		"""_onTerminalFocus should call _detectAndApplyProfile."""
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._detectAndApplyProfile = MagicMock()

		plugin._onTerminalFocus(terminal)

		plugin._detectAndApplyProfile.assert_called_once_with(terminal)

	def test_onTerminalFocus_calls_bindReviewCursor(self):
		"""_onTerminalFocus should call _bindReviewCursor."""
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._bindReviewCursor = MagicMock()

		plugin._onTerminalFocus(terminal)

		plugin._bindReviewCursor.assert_called_once_with(terminal)

	def test_onTerminalFocus_calls_initializeManagers(self):
		"""_onTerminalFocus should call _initializeManagers."""
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._initializeManagers = MagicMock()

		plugin._onTerminalFocus(terminal)

		plugin._initializeManagers.assert_called_once_with(terminal)

	def test_onTerminalFocus_clears_position_cache(self):
		"""_onTerminalFocus should clear the position calculator cache."""
		plugin = self._make_plugin()
		terminal = self._make_terminal()
		plugin._positionCalculator.clear_cache = MagicMock()

		plugin._onTerminalFocus(terminal)

		plugin._positionCalculator.clear_cache.assert_called_once()
