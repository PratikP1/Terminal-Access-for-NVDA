"""
Tests for ANSI parsing, Unicode support, and Application Profiles.

Tests the new features added in v1.0.18:
- ANSIParser class for color and formatting detection
- UnicodeWidthHelper for CJK character width calculation
- ApplicationProfile and ProfileManager for app-specific settings
- WindowDefinition for multiple window regions
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import Mock, patch


class TestANSIParser(unittest.TestCase):
	"""Test the ANSIParser class."""

	def setUp(self):
		"""Import ANSIParser for testing."""
		# Import the module
		import importlib.util
		spec = importlib.util.spec_from_file_location(
			"tdsr",
			os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins', 'tdsr.py')
		)
		tdsr = importlib.util.module_from_spec(spec)
		self.ANSIParser = tdsr.ANSIParser

	def test_parser_initialization(self):
		"""Test ANSIParser initializes correctly."""
		parser = self.ANSIParser()
		self.assertIsNone(parser.foreground)
		self.assertIsNone(parser.background)
		self.assertFalse(parser.bold)

	def test_standard_colors(self):
		"""Test parsing of standard ANSI colors."""
		parser = self.ANSIParser()

		# Test red foreground
		parser.parse('\x1b[31mRed text\x1b[0m')
		self.assertEqual(parser.foreground, 'red')

	def test_bright_colors(self):
		"""Test parsing of bright ANSI colors."""
		parser = self.ANSIParser()

		# Test bright red
		parser.parse('\x1b[91mBright red\x1b[0m')
		self.assertEqual(parser.foreground, 'bright red')

	def test_format_attributes(self):
		"""Test parsing of format attributes."""
		parser = self.ANSIParser()

		# Test bold
		parser.parse('\x1b[1mBold text\x1b[0m')
		self.assertTrue(parser.bold)

		# Reset and test underline
		parser.reset()
		parser.parse('\x1b[4mUnderlined\x1b[0m')
		self.assertTrue(parser.underline)

	def test_reset_code(self):
		"""Test reset code clears all attributes."""
		parser = self.ANSIParser()

		# Set some attributes
		parser.parse('\x1b[31;1;4mRed, bold, underlined\x1b[0m')
		self.assertEqual(parser.foreground, 'red')
		self.assertTrue(parser.bold)
		self.assertTrue(parser.underline)

		# Parse reset
		parser.parse('\x1b[0m')
		self.assertIsNone(parser.foreground)
		self.assertFalse(parser.bold)
		self.assertFalse(parser.underline)

	def test_strip_ansi(self):
		"""Test ANSI code stripping."""
		text = '\x1b[31mRed text\x1b[0m'
		clean = self.ANSIParser.stripANSI(text)
		self.assertEqual(clean, 'Red text')

	def test_format_attributes_detailed(self):
		"""Test formatting attributes in detailed mode."""
		parser = self.ANSIParser()
		parser.parse('\x1b[31;1mRed and bold\x1b[0m')

		formatted = parser.formatAttributes(mode='detailed')
		self.assertIn('red', formatted.lower())
		self.assertIn('bold', formatted.lower())


class TestUnicodeWidthHelper(unittest.TestCase):
	"""Test the UnicodeWidthHelper class."""

	def setUp(self):
		"""Import UnicodeWidthHelper for testing."""
		import importlib.util
		spec = importlib.util.spec_from_file_location(
			"tdsr",
			os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins', 'tdsr.py')
		)
		tdsr = importlib.util.module_from_spec(spec)
		self.UnicodeWidthHelper = tdsr.UnicodeWidthHelper

	def test_ascii_character_width(self):
		"""Test width of ASCII characters."""
		width = self.UnicodeWidthHelper.getCharWidth('A')
		self.assertEqual(width, 1)

	def test_text_width_ascii(self):
		"""Test total width of ASCII text."""
		width = self.UnicodeWidthHelper.getTextWidth('Hello')
		self.assertEqual(width, 5)

	def test_extract_column_range_ascii(self):
		"""Test column range extraction with ASCII text."""
		text = 'Hello World'
		# Extract columns 1-5 (1-based)
		result = self.UnicodeWidthHelper.extractColumnRange(text, 1, 5)
		self.assertEqual(result, 'Hello')

	def test_extract_column_range_middle(self):
		"""Test extracting from middle of text."""
		text = 'Hello World'
		# Extract columns 7-11 (1-based) - "World"
		result = self.UnicodeWidthHelper.extractColumnRange(text, 7, 11)
		self.assertEqual(result, 'World')

	def test_empty_text(self):
		"""Test handling of empty text."""
		result = self.UnicodeWidthHelper.extractColumnRange('', 1, 5)
		self.assertEqual(result, '')

	def test_find_column_position(self):
		"""Test finding string index for column position."""
		text = 'Hello'
		# Column 3 should be at index 2 (0-based index)
		index = self.UnicodeWidthHelper.findColumnPosition(text, 3)
		self.assertEqual(index, 2)


class TestApplicationProfile(unittest.TestCase):
	"""Test the ApplicationProfile and ProfileManager classes."""

	def setUp(self):
		"""Import profile classes for testing."""
		import importlib.util
		spec = importlib.util.spec_from_file_location(
			"tdsr",
			os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins', 'tdsr.py')
		)
		tdsr = importlib.util.module_from_spec(spec)
		self.ApplicationProfile = tdsr.ApplicationProfile
		self.ProfileManager = tdsr.ProfileManager
		self.WindowDefinition = tdsr.WindowDefinition

	def test_profile_creation(self):
		"""Test creating an application profile."""
		profile = self.ApplicationProfile('test', 'Test App')
		self.assertEqual(profile.appName, 'test')
		self.assertEqual(profile.displayName, 'Test App')
		self.assertEqual(len(profile.windows), 0)

	def test_add_window_to_profile(self):
		"""Test adding a window definition to profile."""
		profile = self.ApplicationProfile('test')
		window = profile.addWindow('main', 1, 10, 1, 80, mode='announce')

		self.assertEqual(len(profile.windows), 1)
		self.assertEqual(window.name, 'main')
		self.assertEqual(window.mode, 'announce')

	def test_window_contains_position(self):
		"""Test window position checking."""
		window = self.WindowDefinition('test', 1, 10, 1, 80, mode='announce')

		# Position inside window
		self.assertTrue(window.contains(5, 40))

		# Position outside window
		self.assertFalse(window.contains(15, 40))
		self.assertFalse(window.contains(5, 100))

	def test_profile_manager_initialization(self):
		"""Test ProfileManager initializes with default profiles."""
		manager = self.ProfileManager()

		# Should have default profiles
		self.assertIn('vim', manager.profiles)
		self.assertIn('tmux', manager.profiles)
		self.assertIn('htop', manager.profiles)

	def test_profile_detection_default(self):
		"""Test profile detection returns default when no match."""
		manager = self.ProfileManager()

		# Mock focus object with unknown app
		mock_obj = Mock()
		mock_obj.appModule = Mock()
		mock_obj.appModule.appName = 'unknown_app'
		mock_obj.name = 'Unknown App Window'

		detected = manager.detectApplication(mock_obj)
		self.assertEqual(detected, 'default')

	def test_profile_serialization(self):
		"""Test profile can be serialized and deserialized."""
		profile = self.ApplicationProfile('test', 'Test App')
		profile.punctuationLevel = 2
		profile.addWindow('main', 1, 10, 1, 80)

		# Serialize
		data = profile.toDict()
		self.assertEqual(data['appName'], 'test')
		self.assertEqual(data['punctuationLevel'], 2)
		self.assertEqual(len(data['windows']), 1)

		# Deserialize
		restored = self.ApplicationProfile.fromDict(data)
		self.assertEqual(restored.appName, 'test')
		self.assertEqual(restored.punctuationLevel, 2)
		self.assertEqual(len(restored.windows), 1)

	def test_get_window_at_position(self):
		"""Test getting window at specific position."""
		profile = self.ApplicationProfile('test')
		profile.addWindow('top', 1, 5, 1, 80, mode='announce')
		profile.addWindow('bottom', 6, 10, 1, 80, mode='silent')

		# Position in top window
		window = profile.getWindowAtPosition(3, 40)
		self.assertEqual(window.name, 'top')
		self.assertEqual(window.mode, 'announce')

		# Position in bottom window
		window = profile.getWindowAtPosition(8, 40)
		self.assertEqual(window.name, 'bottom')
		self.assertEqual(window.mode, 'silent')

		# Position outside any window
		window = profile.getWindowAtPosition(15, 40)
		self.assertIsNone(window)


if __name__ == '__main__':
	unittest.main()
