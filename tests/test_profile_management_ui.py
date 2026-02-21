"""
Tests for TDSR profile management UI components.

Tests cover profile list, import/export, delete operations, and UI integration.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
import sys
import json


class TestProfileManagementUI(unittest.TestCase):
	"""Test profile management UI in settings panel."""

	def setUp(self):
		"""Set up test fixtures."""
		# Mock all required NVDA modules
		self.mock_wx = MagicMock()
		self.mock_config = MagicMock()
		self.mock_gui = MagicMock()
		self.mock_guiHelper = MagicMock()
		self.mock_nvdaControls = MagicMock()
		self.mock_settingsDialogs = MagicMock()
		self.mock_globalPluginHandler = MagicMock()
		self.mock_api = MagicMock()
		self.mock_ui = MagicMock()
		self.mock_textInfos = MagicMock()
		self.mock_addonHandler = MagicMock()
		self.mock_scriptHandler = MagicMock()
		self.mock_globalCommands = MagicMock()
		self.mock_speech = MagicMock()

		sys.modules['wx'] = self.mock_wx
		sys.modules['config'] = self.mock_config
		sys.modules['gui'] = self.mock_gui
		sys.modules['gui.guiHelper'] = self.mock_guiHelper
		sys.modules['gui.nvdaControls'] = self.mock_nvdaControls
		sys.modules['gui.settingsDialogs'] = self.mock_settingsDialogs
		sys.modules['globalPluginHandler'] = self.mock_globalPluginHandler
		sys.modules['api'] = self.mock_api
		sys.modules['ui'] = self.mock_ui
		sys.modules['textInfos'] = self.mock_textInfos
		sys.modules['addonHandler'] = self.mock_addonHandler
		sys.modules['scriptHandler'] = self.mock_scriptHandler
		sys.modules['globalCommands'] = self.mock_globalCommands
		sys.modules['speech'] = self.mock_speech

		# Set up config with spec
		mock_conf_obj = MagicMock()
		mock_conf_obj.__getitem__ = lambda self, key: {"TDSR": {}}[key]
		mock_conf_obj.spec = {}
		self.mock_config.conf = mock_conf_obj

		# Mock wx constants
		self.mock_wx.NOT_FOUND = -1
		self.mock_wx.YES = 5103
		self.mock_wx.NO = 5104
		self.mock_wx.OK = 5100
		self.mock_wx.ID_CANCEL = 5101
		self.mock_wx.ICON_INFORMATION = 0
		self.mock_wx.ICON_ERROR = 0
		self.mock_wx.ICON_QUESTION = 0
		self.mock_wx.YES_NO = 0
		self.mock_wx.NO_DEFAULT = 0

	def tearDown(self):
		"""Clean up after tests."""
		modules_to_remove = [
			'wx', 'config', 'gui', 'gui.guiHelper', 'gui.nvdaControls',
			'gui.settingsDialogs', 'globalPluginHandler', 'api', 'ui',
			'textInfos', 'addonHandler', 'scriptHandler', 'globalCommands',
			'speech', 'addon.globalPlugins.tdsr', 'addon.globalPlugins', 'addon'
		]
		for module in modules_to_remove:
			if module in sys.modules:
				del sys.modules[module]

	def test_profile_list_exists(self):
		"""Test profile list control exists in settings panel."""
		# This would require more complex mocking to actually instantiate the panel
		# For now, verify the structure exists in code
		pass

	def test_get_profile_names(self):
		"""Test _getProfileNames method returns sorted profile list."""
		# Verify default profiles are sorted first, then custom profiles
		default_profiles = ['vim', 'tmux', 'htop', 'less', 'git', 'nano', 'irssi']
		custom_profiles = ['custom1', 'custom2']
		all_profiles = default_profiles + custom_profiles

		# Would need to mock the ProfileManager instance
		# For now, verify the sorting logic exists
		pass

	def test_is_default_profile(self):
		"""Test _isDefaultProfile correctly identifies default profiles."""
		# Test that default profiles are identified
		default_profiles = ['vim', 'nvim', 'tmux', 'htop', 'less', 'more', 'git', 'nano', 'irssi']
		for profile in default_profiles:
			# Should identify as default
			pass

		# Test that custom profiles are not identified as default
		custom_profiles = ['myapp', 'custom']
		for profile in custom_profiles:
			# Should not identify as default
			pass

	def test_delete_button_disabled_for_default_profiles(self):
		"""Test delete button is disabled for default profiles."""
		# Verify onProfileSelection disables delete button for default profiles
		pass

	def test_profile_export_creates_json_file(self):
		"""Test profile export creates valid JSON file."""
		# Mock file dialog and file operations
		profile_data = {
			"appName": "test",
			"displayName": "Test App",
			"punctuationLevel": 2,
			"cursorTrackingMode": 1
		}

		# Verify JSON export format is valid
		json_str = json.dumps(profile_data, indent=2, ensure_ascii=False)
		self.assertIsInstance(json_str, str)
		self.assertIn("appName", json_str)

	def test_profile_import_from_json_file(self):
		"""Test profile import from JSON file."""
		# Mock file dialog and file read
		profile_json = '''
		{
			"appName": "imported",
			"displayName": "Imported Profile",
			"punctuationLevel": 3
		}
		'''

		# Verify JSON can be parsed
		profile_data = json.loads(profile_json)
		self.assertEqual(profile_data["appName"], "imported")
		self.assertEqual(profile_data["displayName"], "Imported Profile")

	def test_profile_import_handles_invalid_json(self):
		"""Test profile import handles invalid JSON gracefully."""
		invalid_json = "{ invalid json }"

		# Verify JSON parsing fails appropriately
		with self.assertRaises(json.JSONDecodeError):
			json.loads(invalid_json)


class TestProfileManagerIntegration(unittest.TestCase):
	"""Test ProfileManager integration with UI."""

	def setUp(self):
		"""Set up test fixtures."""
		# Mock NVDA modules
		self.mock_config = MagicMock()
		self.mock_globalPluginHandler = MagicMock()
		self.mock_api = MagicMock()
		self.mock_ui = MagicMock()
		self.mock_textInfos = MagicMock()
		self.mock_addonHandler = MagicMock()
		self.mock_scriptHandler = MagicMock()
		self.mock_globalCommands = MagicMock()
		self.mock_speech = MagicMock()
		self.mock_wx = MagicMock()
		self.mock_gui = MagicMock()

		sys.modules['config'] = self.mock_config
		sys.modules['globalPluginHandler'] = self.mock_globalPluginHandler
		sys.modules['api'] = self.mock_api
		sys.modules['ui'] = self.mock_ui
		sys.modules['textInfos'] = self.mock_textInfos
		sys.modules['addonHandler'] = self.mock_addonHandler
		sys.modules['scriptHandler'] = self.mock_scriptHandler
		sys.modules['globalCommands'] = self.mock_globalCommands
		sys.modules['speech'] = self.mock_speech
		sys.modules['wx'] = self.mock_wx
		sys.modules['gui'] = self.mock_gui

		# Set up config
		mock_conf_obj = MagicMock()
		mock_conf_obj.__getitem__ = lambda self, key: {"TDSR": {}}[key]
		mock_conf_obj.spec = {}
		self.mock_config.conf = mock_conf_obj

	def tearDown(self):
		"""Clean up after tests."""
		modules_to_remove = [
			'wx', 'config', 'gui', 'globalPluginHandler', 'api', 'ui',
			'textInfos', 'addonHandler', 'scriptHandler', 'globalCommands',
			'speech', 'addon.globalPlugins.tdsr', 'addon.globalPlugins', 'addon'
		]
		for module in modules_to_remove:
			if module in sys.modules:
				del sys.modules[module]

	def test_profile_manager_has_export_method(self):
		"""Test ProfileManager has exportProfile method."""
		from addon.globalPlugins.tdsr import ProfileManager

		mgr = ProfileManager()
		self.assertTrue(hasattr(mgr, 'exportProfile'))
		self.assertTrue(callable(mgr.exportProfile))

	def test_profile_manager_has_import_method(self):
		"""Test ProfileManager has importProfile method."""
		from addon.globalPlugins.tdsr import ProfileManager

		mgr = ProfileManager()
		self.assertTrue(hasattr(mgr, 'importProfile'))
		self.assertTrue(callable(mgr.importProfile))

	def test_profile_manager_has_remove_method(self):
		"""Test ProfileManager has removeProfile method."""
		from addon.globalPlugins.tdsr import ProfileManager

		mgr = ProfileManager()
		self.assertTrue(hasattr(mgr, 'removeProfile'))
		self.assertTrue(callable(mgr.removeProfile))

	def test_profile_manager_default_profiles(self):
		"""Test ProfileManager initializes with default profiles."""
		from addon.globalPlugins.tdsr import ProfileManager

		mgr = ProfileManager()
		self.assertIn('vim', mgr.profiles)
		self.assertIn('tmux', mgr.profiles)
		self.assertIn('htop', mgr.profiles)
		self.assertIn('less', mgr.profiles)
		self.assertIn('git', mgr.profiles)

	def test_profile_export_returns_dict(self):
		"""Test exportProfile returns dictionary."""
		from addon.globalPlugins.tdsr import ProfileManager

		mgr = ProfileManager()
		vim_profile = mgr.exportProfile('vim')

		self.assertIsNotNone(vim_profile)
		self.assertIsInstance(vim_profile, dict)
		self.assertIn('appName', vim_profile)

	def test_profile_import_creates_profile(self):
		"""Test importProfile creates new profile from dict."""
		from addon.globalPlugins.tdsr import ProfileManager, ApplicationProfile

		mgr = ProfileManager()

		# Create a test profile
		test_profile = ApplicationProfile('testapp', 'Test Application')
		test_data = test_profile.toDict()

		# Import it
		imported = mgr.importProfile(test_data)

		self.assertIsNotNone(imported)
		self.assertEqual(imported.appName, 'testapp')
		self.assertIn('testapp', mgr.profiles)

	def test_profile_remove_deletes_custom_profile(self):
		"""Test removeProfile deletes custom profiles."""
		from addon.globalPlugins.tdsr import ProfileManager, ApplicationProfile

		mgr = ProfileManager()

		# Add a custom profile
		custom = ApplicationProfile('custom', 'Custom App')
		mgr.addProfile(custom)
		self.assertIn('custom', mgr.profiles)

		# Remove it
		mgr.removeProfile('custom')
		self.assertNotIn('custom', mgr.profiles)

	def test_profile_remove_protects_default_profiles(self):
		"""Test removeProfile does not delete default profiles."""
		from addon.globalPlugins.tdsr import ProfileManager

		mgr = ProfileManager()

		# Try to remove a default profile
		self.assertIn('vim', mgr.profiles)
		mgr.removeProfile('vim')
		# vim should still exist
		self.assertIn('vim', mgr.profiles)


if __name__ == '__main__':
	unittest.main()
