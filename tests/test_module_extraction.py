"""
Tests verifying that extracted modules are importable and re-exported
from terminalAccess.py for backward compatibility.

Each test class covers one extraction phase.
"""

import unittest


class TestTextProcessingModule(unittest.TestCase):
	"""Phase 5a: lib.text_processing module."""

	def test_import_from_lib(self):
		"""Classes are importable from lib.text_processing."""
		from lib.text_processing import ANSIParser, UnicodeWidthHelper
		from lib.text_processing import BidiHelper, EmojiHelper
		from lib.text_processing import _get_symbol_description
		self.assertTrue(callable(ANSIParser))
		self.assertTrue(callable(UnicodeWidthHelper))

	def test_reexport_from_terminalAccess(self):
		"""Classes are still importable from globalPlugins.terminalAccess."""
		from globalPlugins.terminalAccess import ANSIParser, UnicodeWidthHelper
		from globalPlugins.terminalAccess import BidiHelper, EmojiHelper
		self.assertTrue(callable(ANSIParser))

	def test_ansi_strip_works(self):
		"""ANSIParser.stripANSI works after extraction."""
		from lib.text_processing import ANSIParser
		result = ANSIParser.stripANSI("\x1b[31mRed\x1b[0m")
		self.assertEqual(result, "Red")

	def test_unicode_width_works(self):
		"""UnicodeWidthHelper.getTextWidth works after extraction."""
		from lib.text_processing import UnicodeWidthHelper
		helper = UnicodeWidthHelper()
		# ASCII character = width 1
		self.assertEqual(helper.getCharWidth('A'), 1)


class TestCachingModule(unittest.TestCase):
	"""Phase 5b: lib.caching module."""

	def test_import_from_lib(self):
		from lib.caching import PositionCache, TextDiffer
		self.assertTrue(callable(PositionCache))
		self.assertTrue(callable(TextDiffer))

	def test_reexport_from_terminalAccess(self):
		from globalPlugins.terminalAccess import PositionCache, TextDiffer
		self.assertTrue(callable(PositionCache))

	def test_cache_set_get(self):
		from lib.caching import PositionCache
		cache = PositionCache()
		cache.set("bk1", 5, 10)
		self.assertEqual(cache.get("bk1"), (5, 10))

	def test_differ_update(self):
		from lib.caching import TextDiffer
		d = TextDiffer()
		kind, content = d.update("hello")
		self.assertIsNotNone(kind)


class TestConfigModule(unittest.TestCase):
	"""Phase 5c: lib.config module."""

	def test_import_from_lib(self):
		from lib.config import ConfigManager, confspec
		from lib.config import CT_OFF, CT_STANDARD, CT_HIGHLIGHT, CT_WINDOW
		from lib.config import PUNCT_NONE, PUNCT_SOME, PUNCT_MOST, PUNCT_ALL
		from lib.config import PUNCTUATION_SETS
		from lib.config import _validateInteger, _validateString
		self.assertTrue(callable(ConfigManager))

	def test_reexport_from_terminalAccess(self):
		from globalPlugins.terminalAccess import ConfigManager, confspec
		from globalPlugins.terminalAccess import CT_OFF, PUNCT_ALL
		self.assertTrue(callable(ConfigManager))

	def test_validate_integer(self):
		from lib.config import _validateInteger
		self.assertEqual(_validateInteger(5, 0, 10, 0, "test"), 5)
		self.assertEqual(_validateInteger(15, 0, 10, 0, "test"), 0)


class TestProfilesModule(unittest.TestCase):
	"""Phase 5d: lib.profiles module."""

	def test_import_from_lib(self):
		from lib.profiles import WindowDefinition, ApplicationProfile, ProfileManager
		self.assertTrue(callable(WindowDefinition))

	def test_reexport_from_terminalAccess(self):
		from globalPlugins.terminalAccess import WindowDefinition, ApplicationProfile, ProfileManager
		self.assertTrue(callable(WindowDefinition))

	def test_window_definition_contains(self):
		from lib.profiles import WindowDefinition
		wd = WindowDefinition('test', 1, 10, 1, 80)
		self.assertTrue(wd.contains(5, 40))
		self.assertFalse(wd.contains(11, 40))


class TestWindowManagementModule(unittest.TestCase):
	"""Phase 5e: lib.window_management module."""

	def test_import_from_lib(self):
		from lib.window_management import WindowManager, PositionCalculator, WindowMonitor
		self.assertTrue(callable(WindowManager))

	def test_reexport_from_terminalAccess(self):
		from globalPlugins.terminalAccess import WindowManager, PositionCalculator
		self.assertTrue(callable(WindowManager))


class TestOperationsModule(unittest.TestCase):
	"""Phase 5f: lib.operations module."""

	def test_import_from_lib(self):
		from lib.operations import OperationQueue
		self.assertTrue(callable(OperationQueue))

	def test_reexport_from_terminalAccess(self):
		from globalPlugins.terminalAccess import OperationQueue
		self.assertTrue(callable(OperationQueue))


class TestNavigationModule(unittest.TestCase):
	"""Phase 5g: lib.navigation module."""

	def test_import_from_lib(self):
		from lib.navigation import TabManager, BookmarkManager
		self.assertTrue(callable(TabManager))

	def test_reexport_from_terminalAccess(self):
		from globalPlugins.terminalAccess import TabManager, BookmarkManager
		self.assertTrue(callable(TabManager))


class TestSearchModule(unittest.TestCase):
	"""Phase 5h: lib.search module."""

	def test_import_from_lib(self):
		from lib.search import OutputSearchManager, CommandHistoryManager
		from lib.search import UrlExtractorManager
		self.assertTrue(callable(OutputSearchManager))

	def test_reexport_from_terminalAccess(self):
		from globalPlugins.terminalAccess import OutputSearchManager, CommandHistoryManager
		self.assertTrue(callable(OutputSearchManager))


if __name__ == '__main__':
	unittest.main()
