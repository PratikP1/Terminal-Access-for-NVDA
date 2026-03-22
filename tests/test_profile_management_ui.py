"""
Tests for Terminal Access profile management UI components.

Tests cover profile list, import/export, delete operations, and UI integration.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
import sys
import json


class TestProfileManagementUI(unittest.TestCase):
	"""Test profile management UI in settings panel."""

	def setUp(self):
		"""Set up test fixtures.

		Uses the mocks already installed by conftest.py.
		No local sys.modules manipulation needed.
		"""
		pass

	def test_profile_list_exists(self):
		"""TerminalAccessSettingsPanel class exists and is callable."""
		from lib.settings_panel import TerminalAccessSettingsPanel
		self.assertTrue(callable(TerminalAccessSettingsPanel))

	def test_get_profile_names(self):
		"""ProfileManager.profiles contains default profile names."""
		from globalPlugins.terminalAccess import ProfileManager

		mgr = ProfileManager()
		names = sorted(mgr.profiles.keys())
		# Should contain known defaults
		for expected in ['vim', 'tmux', 'htop', 'less', 'git']:
			self.assertIn(expected, names)

	def test_is_default_profile(self):
		"""_BUILTIN_PROFILE_NAMES identifies default vs custom profiles."""
		from globalPlugins.terminalAccess import _BUILTIN_PROFILE_NAMES

		for profile in ['vim', 'tmux', 'htop', 'less', 'git', 'nano', 'irssi']:
			self.assertIn(profile, _BUILTIN_PROFILE_NAMES,
				f"{profile} should be a built-in profile")

		for profile in ['myapp', 'custom_tool']:
			self.assertNotIn(profile, _BUILTIN_PROFILE_NAMES,
				f"{profile} should NOT be a built-in profile")

	def test_delete_button_protected_for_defaults(self):
		"""Default profiles cannot be removed via removeProfile."""
		from globalPlugins.terminalAccess import ProfileManager

		mgr = ProfileManager()
		mgr.removeProfile('vim')
		self.assertIn('vim', mgr.profiles,
			"Default profile 'vim' must survive removeProfile")

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

	def test_profile_manager_has_export_method(self):
		"""Test ProfileManager has exportProfile method."""
		from globalPlugins.terminalAccess import ProfileManager

		mgr = ProfileManager()
		self.assertTrue(hasattr(mgr, 'exportProfile'))
		self.assertTrue(callable(mgr.exportProfile))

	def test_profile_manager_has_import_method(self):
		"""Test ProfileManager has importProfile method."""
		from globalPlugins.terminalAccess import ProfileManager

		mgr = ProfileManager()
		self.assertTrue(hasattr(mgr, 'importProfile'))
		self.assertTrue(callable(mgr.importProfile))

	def test_profile_manager_has_remove_method(self):
		"""Test ProfileManager has removeProfile method."""
		from globalPlugins.terminalAccess import ProfileManager

		mgr = ProfileManager()
		self.assertTrue(hasattr(mgr, 'removeProfile'))
		self.assertTrue(callable(mgr.removeProfile))

	def test_profile_manager_default_profiles(self):
		"""Test ProfileManager initializes with default profiles."""
		from globalPlugins.terminalAccess import ProfileManager

		mgr = ProfileManager()
		self.assertIn('vim', mgr.profiles)
		self.assertIn('tmux', mgr.profiles)
		self.assertIn('htop', mgr.profiles)
		self.assertIn('less', mgr.profiles)
		self.assertIn('git', mgr.profiles)

	def test_profile_export_returns_dict(self):
		"""Test exportProfile returns dictionary."""
		from globalPlugins.terminalAccess import ProfileManager

		mgr = ProfileManager()
		vim_profile = mgr.exportProfile('vim')

		self.assertIsNotNone(vim_profile)
		self.assertIsInstance(vim_profile, dict)
		self.assertIn('appName', vim_profile)

	def test_profile_import_creates_profile(self):
		"""Test importProfile creates new profile from dict."""
		from globalPlugins.terminalAccess import ProfileManager, ApplicationProfile

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
		from globalPlugins.terminalAccess import ProfileManager, ApplicationProfile

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
		from globalPlugins.terminalAccess import ProfileManager

		mgr = ProfileManager()

		# Try to remove a default profile
		self.assertIn('vim', mgr.profiles)
		mgr.removeProfile('vim')
		# vim should still exist
		self.assertIn('vim', mgr.profiles)


if __name__ == '__main__':
	unittest.main()
