"""
Tests for Terminal Access application profile system.

Tests cover profile detection, activation, window definitions, and persistence.
"""

import unittest
from unittest.mock import Mock, MagicMock
import sys


class TestProfileDetection(unittest.TestCase):
	"""Test automatic profile detection via isTerminalApp."""

	def test_terminal_detection(self):
		"""WindowsTerminal is recognized as a terminal application."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		mock_obj = MagicMock()
		mock_obj.appModule.appName = 'windowsterminal'
		self.assertTrue(plugin.isTerminalApp(mock_obj))

	def test_powershell_detection(self):
		"""PowerShell is recognized as a terminal application."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		mock_obj = MagicMock()
		mock_obj.appModule.appName = 'powershell'
		self.assertTrue(plugin.isTerminalApp(mock_obj))

	def test_cmd_detection(self):
		"""cmd.exe is recognized as a terminal application."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		mock_obj = MagicMock()
		mock_obj.appModule.appName = 'cmd'
		self.assertTrue(plugin.isTerminalApp(mock_obj))

	def test_non_terminal_rejected(self):
		"""Non-terminal apps like notepad are not recognized."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		mock_obj = MagicMock()
		mock_obj.appModule.appName = 'notepad'
		self.assertFalse(plugin.isTerminalApp(mock_obj))

	def test_supported_terminals_constant(self):
		"""_SUPPORTED_TERMINALS contains expected terminal app names."""
		from globalPlugins.terminalAccess import _SUPPORTED_TERMINALS

		for expected in ['windowsterminal', 'powershell', 'cmd', 'conhost',
						 'putty', 'alacritty', 'mintty']:
			self.assertIn(expected, _SUPPORTED_TERMINALS,
				f"{expected} should be in _SUPPORTED_TERMINALS")


class TestProfileActivation(unittest.TestCase):
	"""Test profile activation on focus."""

	def test_profile_loads_on_focus(self):
		"""ProfileManager detects application from focus object."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		terminal = MagicMock()
		terminal.appModule.appName = 'windowsterminal'
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._updateGestureBindingsForFocus(terminal)
		# Profile manager should have been consulted
		self.assertIsNotNone(plugin._profileManager)

	def test_profile_unloads_on_blur(self):
		"""Profile state resets when focus leaves terminal."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		# Simulate terminal focus
		terminal = MagicMock()
		terminal.appModule.appName = 'windowsterminal'
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._updateGestureBindingsForFocus(terminal)

		# Now simulate focus leaving
		notepad = MagicMock()
		notepad.appModule.appName = 'notepad'
		plugin.isTerminalApp = MagicMock(return_value=False)
		result = plugin._updateGestureBindingsForFocus(notepad)
		self.assertFalse(result)

	def test_profile_settings_apply(self):
		"""Profile-specific settings override globals via _getEffective."""
		from globalPlugins.terminalAccess import ApplicationProfile, PUNCT_MOST

		profile = ApplicationProfile('vim', 'Vim/Neovim')
		profile.punctuationLevel = PUNCT_MOST
		self.assertEqual(profile.punctuationLevel, PUNCT_MOST)


class TestWindowDefinitions(unittest.TestCase):
	"""Test WindowDefinition class."""

	def test_contains_inside(self):
		"""Position inside window returns True."""
		from globalPlugins.terminalAccess import WindowDefinition

		wd = WindowDefinition('test', top=1, bottom=10, left=1, right=80)
		self.assertTrue(wd.contains(5, 40))

	def test_contains_outside(self):
		"""Position outside window returns False."""
		from globalPlugins.terminalAccess import WindowDefinition

		wd = WindowDefinition('test', top=1, bottom=10, left=1, right=80)
		self.assertFalse(wd.contains(11, 40))
		self.assertFalse(wd.contains(5, 81))
		self.assertFalse(wd.contains(0, 40))

	def test_contains_boundary(self):
		"""Positions on boundaries are inside."""
		from globalPlugins.terminalAccess import WindowDefinition

		wd = WindowDefinition('test', top=5, bottom=20, left=10, right=70)
		self.assertTrue(wd.contains(5, 10))
		self.assertTrue(wd.contains(20, 70))

	def test_disabled_window_never_contains(self):
		"""Disabled window returns False for all positions."""
		from globalPlugins.terminalAccess import WindowDefinition

		wd = WindowDefinition('test', top=1, bottom=100, left=1, right=100, enabled=False)
		self.assertFalse(wd.contains(50, 50))

	def test_window_class_matching(self):
		"""Terminal class names are in _SUPPORTED_TERMINALS."""
		from globalPlugins.terminalAccess import _SUPPORTED_TERMINALS

		for app in ['windowsterminal', 'conhost', 'powershell', 'cmd']:
			self.assertIn(app, _SUPPORTED_TERMINALS)

	def test_app_module_detection(self):
		"""All built-in terminal apps are recognized by isTerminalApp."""
		from globalPlugins.terminalAccess import GlobalPlugin, _SUPPORTED_TERMINALS

		plugin = GlobalPlugin()
		for app_name in list(_SUPPORTED_TERMINALS)[:5]:
			mock_obj = MagicMock()
			mock_obj.appModule.appName = app_name
			self.assertTrue(plugin.isTerminalApp(mock_obj),
				f"{app_name} should be recognized as terminal")


class TestWindowManager(unittest.TestCase):
	"""Test WindowManager class functionality."""

	def test_window_manager_exists(self):
		"""WindowManager class exists."""
		from globalPlugins.terminalAccess import WindowManager
		self.assertTrue(callable(WindowManager))

	def test_window_bounds_validation(self):
		"""Window bounds are validated."""
		from globalPlugins.terminalAccess import WindowManager, ConfigManager

		config_mgr = ConfigManager()
		mgr = WindowManager(config_mgr)

		mgr.start_definition()
		result = mgr.set_window_start(1, 1)
		self.assertTrue(result)
		result = mgr.set_window_end(24, 80)
		self.assertTrue(result)

	def test_window_enabled_state(self):
		"""Window enabled state toggles correctly."""
		from globalPlugins.terminalAccess import WindowManager, ConfigManager

		config_mgr = ConfigManager()
		mgr = WindowManager(config_mgr)

		mgr.enable_window()
		self.assertTrue(mgr.is_window_enabled())
		mgr.disable_window()
		self.assertFalse(mgr.is_window_enabled())

	def test_position_in_window(self):
		"""Position containment works with set bounds."""
		from globalPlugins.terminalAccess import WindowManager, ConfigManager

		config_mgr = ConfigManager()
		mgr = WindowManager(config_mgr)

		mgr.start_definition()
		mgr.set_window_start(5, 10)
		mgr.set_window_end(20, 70)
		mgr.enable_window()

		self.assertTrue(mgr.is_position_in_window(10, 30))
		self.assertFalse(mgr.is_position_in_window(3, 30))
		self.assertFalse(mgr.is_position_in_window(25, 30))
		self.assertFalse(mgr.is_position_in_window(10, 5))
		self.assertFalse(mgr.is_position_in_window(10, 75))


class TestProfilePersistence(unittest.TestCase):
	"""Test profile serialization and deserialization."""

	def test_profile_toDict(self):
		"""ApplicationProfile.toDict() returns expected keys."""
		from globalPlugins.terminalAccess import ApplicationProfile

		profile = ApplicationProfile('test', 'Test App')
		data = profile.toDict()
		self.assertIn('appName', data)
		self.assertIn('displayName', data)
		self.assertEqual(data['appName'], 'test')

	def test_profile_fromDict_roundtrip(self):
		"""ApplicationProfile survives toDict/fromDict roundtrip."""
		from globalPlugins.terminalAccess import ApplicationProfile, PUNCT_MOST

		profile = ApplicationProfile('test', 'Test App')
		profile.punctuationLevel = PUNCT_MOST
		data = profile.toDict()
		restored = ApplicationProfile.fromDict(data)
		self.assertEqual(restored.appName, 'test')
		self.assertEqual(restored.punctuationLevel, PUNCT_MOST)

	def test_windowDefinition_toDict(self):
		"""WindowDefinition.toDict() returns correct keys."""
		from globalPlugins.terminalAccess import WindowDefinition

		wd = WindowDefinition('status', top=24, bottom=24, left=1, right=80, mode='silent')
		data = wd.toDict()
		self.assertEqual(data['name'], 'status')
		self.assertEqual(data['mode'], 'silent')
		self.assertEqual(data['top'], 24)

	def test_windowDefinition_fromDict_roundtrip(self):
		"""WindowDefinition survives toDict/fromDict roundtrip."""
		from globalPlugins.terminalAccess import WindowDefinition

		wd = WindowDefinition('main', top=1, bottom=23, left=1, right=80, mode='announce')
		data = wd.toDict()
		restored = WindowDefinition.fromDict(data)
		self.assertEqual(restored.name, 'main')
		self.assertTrue(restored.contains(12, 40))
		self.assertFalse(restored.contains(24, 40))


class TestProfileSelectionFeatures(unittest.TestCase):
	"""Tests for profile selection dialog support."""

	def test_get_profile_names_returns_sorted_unique(self):
		"""get_profile_names returns sorted, deduplicated app names."""
		from lib.profiles import ProfileManager

		pm = ProfileManager()
		names = pm.get_profile_names()
		# Should be sorted
		self.assertEqual(names, sorted(names))
		# Should not have duplicates (vim and nvim share a profile)
		display_names = [pm.get_profile(n).displayName for n in names]
		self.assertEqual(len(display_names), len(set(display_names)))

	def test_get_profile_names_includes_builtins(self):
		"""get_profile_names includes all built-in profiles."""
		from lib.profiles import ProfileManager

		pm = ProfileManager()
		names = pm.get_profile_names()
		# At minimum, vim and tmux should be present
		self.assertTrue(any(pm.get_profile(n).appName in ('vim', 'nvim') for n in names))
		self.assertTrue(any(pm.get_profile(n).appName == 'tmux' for n in names))

	def test_double_press_profile_announce_single_press(self):
		"""Single press of announceActiveProfile announces profile name."""
		from unittest.mock import patch
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._currentProfile = MagicMock()
		plugin._currentProfile.displayName = "Vim"

		gesture = MagicMock()
		scriptHandler = sys.modules['scriptHandler']
		scriptHandler.getLastScriptRepeatCount.return_value = 0

		with patch.object(plugin, 'isTerminalApp', return_value=True):
			plugin.script_announceActiveProfile(gesture)

		ui = sys.modules['ui']
		ui.message.assert_called()
		msg = ui.message.call_args[0][0]
		self.assertIn("Vim", msg)


if __name__ == '__main__':
	unittest.main()
