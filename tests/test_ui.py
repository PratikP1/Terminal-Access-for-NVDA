"""
Tests for Terminal Access settings panel UI functionality.

Tests cover settings panel loading, saving, validation, and reset functionality.
These tests rely on conftest.py for NVDA module mocking.
"""

import unittest
import sys
from unittest.mock import Mock, MagicMock, patch


class TestSettingsPanel(unittest.TestCase):
	"""Test settings panel functionality."""

	def test_settings_panel_structure(self):
		"""Test settings panel has correct structure."""
		# Import using globalPlugins (conftest.py provides mocks)
		from globalPlugins.terminalAccess import TerminalAccessSettingsPanel

		# Verify class exists and has required attributes
		self.assertTrue(hasattr(TerminalAccessSettingsPanel, 'title'))
		self.assertTrue(hasattr(TerminalAccessSettingsPanel, 'makeSettings'))
		self.assertTrue(hasattr(TerminalAccessSettingsPanel, 'onSave'))
		self.assertTrue(hasattr(TerminalAccessSettingsPanel, 'onResetToDefaults'))

	def test_verbose_mode_in_config(self):
		"""Test verbose mode setting is in configuration."""
		import config
		# Verify verboseMode is in config
		self.assertIn("verboseMode", config.conf["terminalAccess"])
		self.assertIsInstance(config.conf["terminalAccess"]["verboseMode"], bool)

	def test_quiet_mode_in_config(self):
		"""Test quiet mode setting is in configuration."""
		import config
		self.assertIn("quietMode", config.conf["terminalAccess"])
		self.assertIsInstance(config.conf["terminalAccess"]["quietMode"], bool)

	def test_default_values(self):
		"""Test all settings have appropriate default values."""
		import config
		defaults = config.conf["terminalAccess"]

		# Boolean settings
		self.assertEqual(defaults["cursorTracking"], True)
		self.assertEqual(defaults["keyEcho"], True)
		self.assertEqual(defaults["linePause"], True)
		self.assertEqual(defaults["quietMode"], False)
		self.assertEqual(defaults["verboseMode"], False)

		# Integer settings
		self.assertEqual(defaults["cursorTrackingMode"], 1)
		self.assertEqual(defaults["punctuationLevel"], 2)
		self.assertEqual(defaults["cursorDelay"], 20)

		# String settings
		self.assertEqual(defaults["repeatedSymbolsValues"], "-_=!")

	def test_window_coordinate_settings(self):
		"""Test window coordinate settings exist."""
		import config
		defaults = config.conf["terminalAccess"]

		self.assertIn("windowTop", defaults)
		self.assertIn("windowBottom", defaults)
		self.assertIn("windowLeft", defaults)
		self.assertIn("windowRight", defaults)
		self.assertIn("windowEnabled", defaults)

		# Default to 0 and disabled
		self.assertEqual(defaults["windowTop"], 0)
		self.assertEqual(defaults["windowBottom"], 0)
		self.assertEqual(defaults["windowLeft"], 0)
		self.assertEqual(defaults["windowRight"], 0)
		self.assertEqual(defaults["windowEnabled"], False)


class TestConfigManager(unittest.TestCase):
	"""Test ConfigManager class functionality."""

	def test_config_manager_exists(self):
		"""Test ConfigManager class exists."""
		from globalPlugins.terminalAccess import ConfigManager

		self.assertTrue(callable(ConfigManager))

	def test_config_manager_initialization(self):
		"""Test ConfigManager can be initialized."""
		from globalPlugins.terminalAccess import ConfigManager

		# Create instance
		config_mgr = ConfigManager()
		self.assertIsNotNone(config_mgr)

	def test_config_manager_has_methods(self):
		"""Test ConfigManager has expected methods."""
		from globalPlugins.terminalAccess import ConfigManager

		config_mgr = ConfigManager()
		# Should have get/set methods
		self.assertTrue(hasattr(config_mgr, 'get'))
		self.assertTrue(hasattr(config_mgr, 'set'))


if __name__ == '__main__':
	unittest.main()
