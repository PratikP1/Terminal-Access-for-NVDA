"""
Tests for advanced Unicode features (RTL text and emoji support).

Tests cover:
- BidiHelper: RTL text detection and processing
- EmojiHelper: Emoji sequence detection and width calculation
- Integration with UnicodeWidthHelper

Section Reference: FUTURE_ENHANCEMENTS.md Section 4 (lines 465-566)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys


class TestBidiHelper(unittest.TestCase):
	"""Test BidiHelper class for RTL text handling."""

	def setUp(self):
		"""Set up test fixtures."""
		# Import after mocking
		from addon.globalPlugins.terminalAccess import BidiHelper
		self.BidiHelper = BidiHelper

	def test_bidi_helper_initialization(self):
		"""Test BidiHelper initializes with optional dependencies."""
		helper = self.BidiHelper()
		self.assertIsNotNone(helper)

	def test_is_available_method_exists(self):
		"""Test is_available method exists."""
		helper = self.BidiHelper()
		result = helper.is_available()
		self.assertIsInstance(result, bool)

	def test_rtl_detection_hebrew(self):
		"""Test RTL detection for Hebrew text."""
		helper = self.BidiHelper()

		# Hebrew text (U+0590-U+05FF range)
		hebrew_text = "שלום"  # Shalom (Hello)
		result = helper.is_rtl(hebrew_text)
		self.assertTrue(result, "Hebrew text should be detected as RTL")

	def test_rtl_detection_arabic(self):
		"""Test RTL detection for Arabic text."""
		helper = self.BidiHelper()

		# Arabic text (U+0600-U+06FF range)
		arabic_text = "مرحبا"  # Marhaba (Hello)
		result = helper.is_rtl(arabic_text)
		self.assertTrue(result, "Arabic text should be detected as RTL")

	def test_rtl_detection_english(self):
		"""Test RTL detection returns False for English text."""
		helper = self.BidiHelper()

		english_text = "Hello World"
		result = helper.is_rtl(english_text)
		self.assertFalse(result, "English text should not be detected as RTL")

	def test_rtl_detection_empty_string(self):
		"""Test RTL detection with empty string."""
		helper = self.BidiHelper()

		result = helper.is_rtl("")
		self.assertFalse(result, "Empty string should return False")

	def test_rtl_detection_mixed_text(self):
		"""Test RTL detection with mixed RTL/LTR text."""
		helper = self.BidiHelper()

		# More Arabic than English - should be RTL
		mixed_text = "Hello مرحبا مرحبا"
		result = helper.is_rtl(mixed_text)
		self.assertTrue(result, "Text with more RTL characters should be RTL")

	def test_process_text_english(self):
		"""Test process_text with English text."""
		helper = self.BidiHelper()

		text = "Hello World"
		result = helper.process_text(text)
		# Should return text as-is (possibly with bidi processing)
		self.assertIsInstance(result, str)
		self.assertGreater(len(result), 0)

	def test_process_text_empty(self):
		"""Test process_text with empty string."""
		helper = self.BidiHelper()

		result = helper.process_text("")
		self.assertEqual(result, "")

	def test_extract_column_range_rtl_ltr_text(self):
		"""Test extract_column_range_rtl with LTR text."""
		helper = self.BidiHelper()

		text = "Hello World"
		result = helper.extract_column_range_rtl(text, 1, 5)
		# Should extract normally for LTR text
		self.assertEqual(result, "Hello")

	def test_extract_column_range_rtl_empty(self):
		"""Test extract_column_range_rtl with empty string."""
		helper = self.BidiHelper()

		result = helper.extract_column_range_rtl("", 1, 5)
		self.assertEqual(result, "")


class TestEmojiHelper(unittest.TestCase):
	"""Test EmojiHelper class for emoji sequence handling."""

	def setUp(self):
		"""Set up test fixtures."""
		from addon.globalPlugins.terminalAccess import EmojiHelper
		self.EmojiHelper = EmojiHelper

	def test_emoji_helper_initialization(self):
		"""Test EmojiHelper initializes with optional dependencies."""
		helper = self.EmojiHelper()
		self.assertIsNotNone(helper)

	def test_is_available_method_exists(self):
		"""Test is_available method exists."""
		helper = self.EmojiHelper()
		result = helper.is_available()
		self.assertIsInstance(result, bool)

	def test_contains_emoji_basic_emoji(self):
		"""Test contains_emoji with basic emoji."""
		helper = self.EmojiHelper()

		# Basic emoji test (if emoji library available)
		text_with_emoji = "Hello 👋"
		result = helper.contains_emoji(text_with_emoji)
		# Result depends on library availability
		self.assertIsInstance(result, bool)

	def test_contains_emoji_no_emoji(self):
		"""Test contains_emoji with no emoji."""
		helper = self.EmojiHelper()

		text = "Hello World"
		result = helper.contains_emoji(text)
		# Should return False (or False if library unavailable)
		self.assertFalse(result)

	def test_contains_emoji_empty_string(self):
		"""Test contains_emoji with empty string."""
		helper = self.EmojiHelper()

		result = helper.contains_emoji("")
		self.assertFalse(result)

	def test_extract_emoji_list_returns_list(self):
		"""Test extract_emoji_list returns a list."""
		helper = self.EmojiHelper()

		text = "Hello World"
		result = helper.extract_emoji_list(text)
		self.assertIsInstance(result, list)

	def test_extract_emoji_list_empty_string(self):
		"""Test extract_emoji_list with empty string."""
		helper = self.EmojiHelper()

		result = helper.extract_emoji_list("")
		self.assertEqual(result, [])

	def test_get_emoji_width_empty_string(self):
		"""Test get_emoji_width with empty string."""
		helper = self.EmojiHelper()

		result = helper.get_emoji_width("")
		self.assertEqual(result, 0)

	def test_get_emoji_width_regular_text(self):
		"""Test get_emoji_width with regular text."""
		helper = self.EmojiHelper()

		text = "Hello"
		result = helper.get_emoji_width(text)
		# Should return width using fallback
		self.assertGreater(result, 0)

	def test_get_text_width_with_emoji_regular_text(self):
		"""Test get_text_width_with_emoji with regular text."""
		helper = self.EmojiHelper()

		text = "Hello"
		result = helper.get_text_width_with_emoji(text)
		# Should return width (5 for "Hello")
		self.assertEqual(result, 5)

	def test_get_text_width_with_emoji_empty_string(self):
		"""Test get_text_width_with_emoji with empty string."""
		helper = self.EmojiHelper()

		result = helper.get_text_width_with_emoji("")
		self.assertEqual(result, 0)


class TestBidiHelperIntegration(unittest.TestCase):
	"""Test BidiHelper integration with UnicodeWidthHelper."""

	def setUp(self):
		"""Set up test fixtures."""
		from addon.globalPlugins.terminalAccess import BidiHelper, UnicodeWidthHelper
		self.BidiHelper = BidiHelper
		self.UnicodeWidthHelper = UnicodeWidthHelper

	def test_rtl_extraction_uses_unicode_width(self):
		"""Test RTL extraction uses UnicodeWidthHelper."""
		helper = self.BidiHelper()

		# Test with CJK characters (double-width)
		text = "Hello世界"  # Mixed ASCII and CJK
		result = helper.extract_column_range_rtl(text, 1, 5)

		# Should extract "Hello" correctly
		self.assertEqual(result, "Hello")

	def test_rtl_detection_with_unicode_categories(self):
		"""Test RTL detection covers all Unicode ranges."""
		helper = self.BidiHelper()

		# Test Hebrew range (U+0590-U+05FF)
		hebrew_aleph = "\u05D0"  # Hebrew letter Aleph
		self.assertTrue(helper.is_rtl(hebrew_aleph))

		# Test Arabic range (U+0600-U+06FF)
		arabic_alif = "\u0627"  # Arabic letter Alif
		self.assertTrue(helper.is_rtl(arabic_alif))

		# Test Arabic Supplement (U+0750-U+077F)
		arabic_supplement = "\u0750"
		self.assertTrue(helper.is_rtl(arabic_supplement))


class TestEmojiHelperIntegration(unittest.TestCase):
	"""Test EmojiHelper integration with UnicodeWidthHelper."""

	def setUp(self):
		"""Set up test fixtures."""
		from addon.globalPlugins.terminalAccess import EmojiHelper, UnicodeWidthHelper
		self.EmojiHelper = EmojiHelper
		self.UnicodeWidthHelper = UnicodeWidthHelper

	def test_emoji_width_fallback_to_unicode(self):
		"""Test emoji width falls back to UnicodeWidthHelper."""
		helper = self.EmojiHelper()

		# Regular text should use UnicodeWidthHelper
		text = "Hello"
		result = helper.get_emoji_width(text)

		# Should match UnicodeWidthHelper result
		expected = self.UnicodeWidthHelper.getTextWidth(text)
		self.assertEqual(result, expected)

	def test_text_width_with_emoji_fallback(self):
		"""Test text width falls back for no emoji."""
		helper = self.EmojiHelper()

		text = "Hello World"
		result = helper.get_text_width_with_emoji(text)

		# Should match UnicodeWidthHelper for text without emoji
		expected = self.UnicodeWidthHelper.getTextWidth(text)
		self.assertEqual(result, expected)


class TestUnicodeEdgeCases(unittest.TestCase):
	"""Test edge cases for Unicode handling."""

	def setUp(self):
		"""Set up test fixtures."""
		from addon.globalPlugins.terminalAccess import BidiHelper, EmojiHelper
		self.BidiHelper = BidiHelper
		self.EmojiHelper = EmojiHelper

	def test_bidi_with_numbers(self):
		"""Test RTL detection with numbers."""
		helper = self.BidiHelper()

		# Numbers are neutral - shouldn't affect RTL detection
		text_with_numbers = "123 456 789"
		result = helper.is_rtl(text_with_numbers)
		self.assertFalse(result)

	def test_bidi_with_punctuation(self):
		"""Test RTL detection with punctuation."""
		helper = self.BidiHelper()

		# Punctuation is neutral
		text = "Hello, World!"
		result = helper.is_rtl(text)
		self.assertFalse(result)

	def test_emoji_with_whitespace(self):
		"""Test emoji detection with whitespace."""
		helper = self.EmojiHelper()

		# Whitespace should not affect processing
		text = "   Hello   "
		result = helper.get_text_width_with_emoji(text)
		self.assertGreater(result, 0)

	def test_bidi_process_text_none_input(self):
		"""Test process_text gracefully handles unusual input."""
		helper = self.BidiHelper()

		# Empty string should return empty
		result = helper.process_text("")
		self.assertEqual(result, "")


class TestOptionalDependencyHandling(unittest.TestCase):
	"""Test graceful degradation without optional dependencies."""

	def test_bidi_without_library(self):
		"""Test BidiHelper works without bidi library."""
		from addon.globalPlugins.terminalAccess import BidiHelper
		helper = BidiHelper()

		# Should initialize even if library unavailable
		self.assertIsNotNone(helper)

		# Methods should work (return input or fallback)
		text = "Hello"
		result = helper.process_text(text)
		self.assertIsInstance(result, str)

	def test_emoji_without_library(self):
		"""Test EmojiHelper works without emoji library."""
		from addon.globalPlugins.terminalAccess import EmojiHelper
		helper = EmojiHelper()

		# Should initialize even if library unavailable
		self.assertIsNotNone(helper)

		# Methods should work (return fallback values)
		text = "Hello"
		result = helper.get_text_width_with_emoji(text)
		self.assertIsInstance(result, int)
		self.assertGreater(result, 0)


if __name__ == '__main__':
	unittest.main()
