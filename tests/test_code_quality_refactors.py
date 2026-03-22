"""
Tests for code quality refactoring changes.

Covers:
- _announceIndentation delegates to _getIndentationInfo/_formatIndentation
- _changePunctuationLevel shared helper
- _PUNCT_LEVEL_NAMES module-level constant
- _announceCharAtPosition helper
- _isDefaultProfile uses _BUILTIN_PROFILE_NAMES
- Data-driven third-party profile initialization
"""

import sys
import time
import unittest
from unittest.mock import Mock, MagicMock, patch, call


class TestAnnounceIndentationDelegates(unittest.TestCase):
	"""_announceIndentation should delegate to _getIndentationInfo + _formatIndentation."""

	def setUp(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		self.plugin = GlobalPlugin()

	@patch('globalPlugins.terminalAccess.ui')
	def test_calls_getIndentationInfo(self, mock_ui):
		"""_announceIndentation must call _getIndentationInfo internally."""
		mock_review = MagicMock()
		mock_info = MagicMock()
		mock_review.copy.return_value = mock_info
		mock_info.text = "    hello"
		self.plugin._getReviewPosition = Mock(return_value=mock_review)

		# Spy on _getIndentationInfo
		original = self.plugin._getIndentationInfo
		calls = []
		def spy(text):
			calls.append(text)
			return original(text)
		self.plugin._getIndentationInfo = spy

		self.plugin._announceIndentation()
		self.assertEqual(len(calls), 1)

	@patch('globalPlugins.terminalAccess.ui')
	def test_calls_formatIndentation(self, mock_ui):
		"""_announceIndentation must call _formatIndentation internally."""
		mock_review = MagicMock()
		mock_info = MagicMock()
		mock_review.copy.return_value = mock_info
		mock_info.text = "\thello"
		self.plugin._getReviewPosition = Mock(return_value=mock_review)

		original = self.plugin._formatIndentation
		calls = []
		def spy(spaces, tabs):
			calls.append((spaces, tabs))
			return original(spaces, tabs)
		self.plugin._formatIndentation = spy

		self.plugin._announceIndentation()
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0], (0, 1))


class TestPunctuationLevelConstant(unittest.TestCase):
	"""_PUNCT_LEVEL_NAMES should be a module-level constant."""

	def test_module_level_constant_exists(self):
		"""_PUNCT_LEVEL_NAMES must exist at module level."""
		import globalPlugins.terminalAccess as mod
		self.assertTrue(hasattr(mod, '_PUNCT_LEVEL_NAMES'))
		self.assertIsInstance(mod._PUNCT_LEVEL_NAMES, dict)
		self.assertEqual(len(mod._PUNCT_LEVEL_NAMES), 4)

	def test_changePunctuationLevel_method_exists(self):
		"""_changePunctuationLevel helper must exist on GlobalPlugin."""
		from globalPlugins.terminalAccess import GlobalPlugin
		self.assertTrue(hasattr(GlobalPlugin, '_changePunctuationLevel'))


class TestAnnounceCharAtPosition(unittest.TestCase):
	"""_announceCharAtPosition helper must exist and handle blank/content."""

	def test_method_exists(self):
		"""_announceCharAtPosition must exist on GlobalPlugin."""
		from globalPlugins.terminalAccess import GlobalPlugin
		self.assertTrue(hasattr(GlobalPlugin, '_announceCharAtPosition'))

	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.ui')
	def test_blank_character(self, mock_ui, mock_speech):
		"""_announceCharAtPosition announces Blank for newline/empty."""
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		info = MagicMock()
		info.text = '\n'
		plugin._announceCharAtPosition(info)
		mock_ui.message.assert_called_with("Blank")

	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.ui')
	def test_normal_character(self, mock_ui, mock_speech):
		"""_announceCharAtPosition speaks regular characters."""
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		info = MagicMock()
		info.text = 'A'
		plugin._announceCharAtPosition(info)
		mock_speech.speakText.assert_called_with('A')


class TestBuiltinProfileNames(unittest.TestCase):
	"""Settings panel must use _BUILTIN_PROFILE_NAMES, not hardcoded lists."""

	def test_isDefaultProfile_uses_builtin_constant(self):
		"""_isDefaultProfile should recognise all _BUILTIN_PROFILE_NAMES members."""
		from lib.settings_panel import TerminalAccessSettingsPanel
		from lib.profiles import _BUILTIN_PROFILE_NAMES

		panel = MagicMock(spec=TerminalAccessSettingsPanel)
		# Call the unbound method
		for name in _BUILTIN_PROFILE_NAMES:
			result = TerminalAccessSettingsPanel._isDefaultProfile(panel, name)
			self.assertTrue(result, f"{name} should be recognised as default")

	def test_isDefaultProfile_rejects_custom(self):
		"""_isDefaultProfile must reject names not in _BUILTIN_PROFILE_NAMES."""
		from lib.settings_panel import TerminalAccessSettingsPanel
		panel = MagicMock(spec=TerminalAccessSettingsPanel)
		self.assertFalse(
			TerminalAccessSettingsPanel._isDefaultProfile(panel, 'my_custom_profile')
		)


class TestDataDrivenProfiles(unittest.TestCase):
	"""Third-party terminal profiles should be data-driven."""

	def test_all_simple_profiles_created(self):
		"""All PUNCT_SOME + CT_STANDARD profiles should be present."""
		from lib.profiles import ProfileManager
		pm = ProfileManager()
		simple_names = [
			'cmder', 'conemu', 'conemu64', 'putty', 'kitty',
			'terminus', 'hyper', 'alacritty', 'wezterm', 'wezterm-gui',
			'tabby', 'fluent', 'ghostty', 'rio', 'waveterm', 'contour',
			'cool-retro-term', 'mobaxterm', 'securecrt', 'ttermpro',
			'mremoteng', 'royalts',
		]
		for name in simple_names:
			self.assertIn(name, pm.profiles, f"Profile '{name}' should exist")

	def test_simple_profiles_have_correct_settings(self):
		"""Data-driven profiles should have PUNCT_SOME + CT_STANDARD."""
		from lib.profiles import ProfileManager
		from lib.config import PUNCT_SOME, CT_STANDARD
		pm = ProfileManager()
		# Pick a representative subset
		for name in ('cmder', 'terminus', 'ghostty', 'royalts'):
			profile = pm.profiles[name]
			self.assertEqual(profile.punctuationLevel, PUNCT_SOME,
				f"{name} should have PUNCT_SOME")
			self.assertEqual(profile.cursorTrackingMode, CT_STANDARD,
				f"{name} should have CT_STANDARD")
