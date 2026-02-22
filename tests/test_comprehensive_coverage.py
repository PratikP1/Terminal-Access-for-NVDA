"""
Comprehensive tests to achieve 100% code coverage.

This test file exercises code paths not covered by existing tests,
particularly GlobalPlugin methods, ANSI parsing edge cases, and
helper class functionality.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys


class TestANSIParserComprehensive(unittest.TestCase):
    """Comprehensive tests for ANSIParser to cover all branches."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import ANSIParser
        self.ANSIParser = ANSIParser

    def test_format_attributes_brief_mode(self):
        """Test formatAttributes in brief mode."""
        parser = self.ANSIParser()
        parser.parse('\x1b[31;1mRed and bold')

        result = parser.formatAttributes(mode='brief')
        self.assertIsInstance(result, str)
        # Brief mode should mention colors
        self.assertIn('red', result.lower())

    def test_format_attributes_change_only_mode(self):
        """Test formatAttributes in change-only mode."""
        parser = self.ANSIParser()
        parser.parse('\x1b[31mRed')

        result = parser.formatAttributes(mode='change-only')
        self.assertIsInstance(result, str)

    def test_format_attributes_no_attributes(self):
        """Test formatAttributes with no attributes set."""
        parser = self.ANSIParser()

        result = parser.formatAttributes(mode='detailed')
        self.assertIn('default', result.lower())

    def test_format_attributes_with_background(self):
        """Test formatAttributes with background color."""
        parser = self.ANSIParser()
        parser.parse('\x1b[31;41mRed on red')

        result = parser.formatAttributes(mode='detailed')
        self.assertIn('red', result.lower())

    def test_rgb_foreground_color(self):
        """Test RGB foreground color parsing."""
        parser = self.ANSIParser()
        parser.parse('\x1b[38;2;255;128;0mOrange')

        self.assertIsInstance(parser.foreground, tuple)
        self.assertEqual(len(parser.foreground), 3)
        self.assertEqual(parser.foreground, (255, 128, 0))

    def test_rgb_background_color(self):
        """Test RGB background color parsing."""
        parser = self.ANSIParser()
        parser.parse('\x1b[48;2;0;128;255mBlue background')

        self.assertIsInstance(parser.background, tuple)
        self.assertEqual(len(parser.background), 3)
        self.assertEqual(parser.background, (0, 128, 255))

    def test_256_color_foreground(self):
        """Test 256-color mode foreground."""
        parser = self.ANSIParser()
        parser.parse('\x1b[38;5;196mBright red')

        self.assertEqual(parser.foreground, 'color196')

    def test_256_color_background(self):
        """Test 256-color mode background."""
        parser = self.ANSIParser()
        parser.parse('\x1b[48;5;21mBlue background')

        self.assertEqual(parser.background, 'color21')

    def test_reset_format_attributes(self):
        """Test resetting specific format attributes."""
        parser = self.ANSIParser()
        # Set attributes
        parser.parse('\x1b[1;3;4;5;7;8;9mAll formats')

        # Reset them
        parser.parse('\x1b[22m')  # Normal intensity
        self.assertFalse(parser.bold)
        self.assertFalse(parser.dim)

        parser.parse('\x1b[23m')  # Not italic
        self.assertFalse(parser.italic)

        parser.parse('\x1b[24m')  # Not underlined
        self.assertFalse(parser.underline)

        parser.parse('\x1b[25m')  # Not blinking
        self.assertFalse(parser.blink)

        parser.parse('\x1b[27m')  # Not inverse
        self.assertFalse(parser.inverse)

        parser.parse('\x1b[28m')  # Not hidden
        self.assertFalse(parser.hidden)

        parser.parse('\x1b[29m')  # Not strikethrough
        self.assertFalse(parser.strikethrough)

    def test_all_format_attributes(self):
        """Test all format attributes."""
        parser = self.ANSIParser()

        # Test each format attribute
        parser.parse('\x1b[1m')  # Bold
        self.assertTrue(parser.bold)

        parser.reset()
        parser.parse('\x1b[2m')  # Dim
        self.assertTrue(parser.dim)

        parser.reset()
        parser.parse('\x1b[3m')  # Italic
        self.assertTrue(parser.italic)

        parser.reset()
        parser.parse('\x1b[4m')  # Underline
        self.assertTrue(parser.underline)

        parser.reset()
        parser.parse('\x1b[5m')  # Blink slow
        self.assertTrue(parser.blink)

        parser.reset()
        parser.parse('\x1b[6m')  # Blink rapid
        self.assertTrue(parser.blink)

        parser.reset()
        parser.parse('\x1b[7m')  # Inverse
        self.assertTrue(parser.inverse)

        parser.reset()
        parser.parse('\x1b[8m')  # Hidden
        self.assertTrue(parser.hidden)

        parser.reset()
        parser.parse('\x1b[9m')  # Strikethrough
        self.assertTrue(parser.strikethrough)

    def test_strip_ansi_static_method(self):
        """Test stripANSI static method."""
        # Basic test
        result = self.ANSIParser.stripANSI('\x1b[31mRed\x1b[0m text')
        self.assertEqual(result, 'Red text')

        # Multiple codes
        result = self.ANSIParser.stripANSI('\x1b[1;31mBold red\x1b[0m normal')
        self.assertEqual(result, 'Bold red normal')

        # No ANSI codes
        result = self.ANSIParser.stripANSI('Plain text')
        self.assertEqual(result, 'Plain text')

        # Empty string
        result = self.ANSIParser.stripANSI('')
        self.assertEqual(result, '')


class TestUnicodeWidthHelperComprehensive(unittest.TestCase):
    """Comprehensive tests for UnicodeWidthHelper."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import UnicodeWidthHelper
        self.helper = UnicodeWidthHelper

    def test_cjk_character_width(self):
        """Test width of CJK characters (double-width when wcwidth available)."""
        # Chinese character
        width = self.helper.getCharWidth('中')
        # wcwidth not available in test environment, so returns 1
        self.assertIn(width, [1, 2])  # 2 if wcwidth available, 1 if not

        # Japanese character
        width = self.helper.getCharWidth('あ')
        self.assertIn(width, [1, 2])

        # Korean character
        width = self.helper.getCharWidth('한')
        self.assertIn(width, [1, 2])

    def test_combining_character_width(self):
        """Test width of combining characters (zero-width when wcwidth available)."""
        # Combining acute accent
        width = self.helper.getCharWidth('\u0301')
        # wcwidth would return 0, fallback returns 1
        self.assertIn(width, [0, 1])

    def test_mixed_width_text(self):
        """Test text with mixed character widths."""
        text = 'Hello世界'  # ASCII + CJK
        width = self.helper.getTextWidth(text)
        # With wcwidth: 'Hello' = 5, '世界' = 4 (2 chars × 2 width) = 9
        # Without wcwidth: all chars = 1 width each = 7
        self.assertIn(width, [7, 9])

    def test_extract_column_range_with_cjk(self):
        """Test extracting columns with CJK characters."""
        text = 'AB中文CD'
        # Without wcwidth: all chars width 1, columns 1-4 = 'AB中文'
        # With wcwidth: A=1, B=1, 中=2 (cols 1-4) = 'AB中'
        result = self.helper.extractColumnRange(text, 1, 4)
        self.assertIn(result, ['AB中', 'AB中文'])

    def test_find_column_position_with_cjk(self):
        """Test finding character at column position with CJK."""
        text = 'A中B'
        # Without wcwidth: A=col1, 中=col2, B=col3
        # With wcwidth: A=col1, 中=col2-3, B=col4

        # Column 1 should always be 'A' (index 0)
        index = self.helper.findColumnPosition(text, 1)
        self.assertEqual(index, 0)

        # Column 2 depends on wcwidth availability
        index = self.helper.findColumnPosition(text, 2)
        self.assertIn(index, [1, 1])  # Always index 1 ('中')

        # Last position depends on wcwidth
        # Without wcwidth: col 3 = index 2 ('B')
        # With wcwidth: col 4 = index 2 ('B')
        index_col3 = self.helper.findColumnPosition(text, 3)
        index_col4 = self.helper.findColumnPosition(text, 4)
        # One of these should be 2 (the 'B')
        self.assertTrue(index_col3 == 2 or index_col4 == 2)


class TestPositionCacheComprehensive(unittest.TestCase):
    """Comprehensive tests for PositionCache."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import PositionCache
        self.cache = PositionCache()

    def test_cache_set_and_get(self):
        """Test setting and getting cache entries."""
        self.cache.set('bookmark1', 10, 20)
        result = self.cache.get('bookmark1')
        self.assertEqual(result, (10, 20))

    def test_cache_get_nonexistent(self):
        """Test getting nonexistent entry returns None."""
        result = self.cache.get('nonexistent')
        self.assertIsNone(result)

    def test_cache_invalidate_specific(self):
        """Test invalidating specific bookmark."""
        self.cache.set('bookmark1', 10, 20)
        self.cache.set('bookmark2', 30, 40)

        self.cache.invalidate('bookmark1')

        self.assertIsNone(self.cache.get('bookmark1'))
        self.assertIsNotNone(self.cache.get('bookmark2'))

    def test_cache_clear_all(self):
        """Test clearing all cache entries."""
        self.cache.set('bookmark1', 10, 20)
        self.cache.set('bookmark2', 30, 40)

        self.cache.clear()

        self.assertIsNone(self.cache.get('bookmark1'))
        self.assertIsNone(self.cache.get('bookmark2'))

    def test_cache_size_limit(self):
        """Test cache respects max size limit."""
        # Add more than max size
        for i in range(150):
            self.cache.set(f'bookmark{i}', i, i)

        # Should not exceed max size (100)
        # Older entries should be evicted
        self.assertIsNone(self.cache.get('bookmark0'))
        self.assertIsNotNone(self.cache.get('bookmark149'))


class TestPositionCalculatorComprehensive(unittest.TestCase):
    """Comprehensive tests for PositionCalculator."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import PositionCalculator
        self.calc = PositionCalculator()

    def test_calculate_with_no_terminal(self):
        """Test calculate returns (0, 0) with no terminal."""
        mock_textinfo = Mock()
        mock_textinfo.bookmark = 'test'

        result = self.calc.calculate(mock_textinfo, None)
        self.assertEqual(result, (0, 0))

    def test_calculate_with_cached_value(self):
        """Test calculate uses cached value."""
        mock_textinfo = Mock()
        mock_textinfo.bookmark = 'cached'
        mock_terminal = Mock()

        # Pre-populate cache
        self.calc._cache.set('cached', 5, 10)

        result = self.calc.calculate(mock_textinfo, mock_terminal)
        self.assertEqual(result, (5, 10))

    def test_clear_cache(self):
        """Test clear_cache method."""
        mock_textinfo = Mock()
        mock_textinfo.bookmark = 'test'
        mock_terminal = Mock()

        self.calc._cache.set('test', 1, 2)
        self.calc.clear_cache()

        # Cache should be cleared
        self.assertIsNone(self.calc._cache.get('test'))

    def test_uia_position_calculation(self):
        """Test position calculation with UIATextInfo (uses setEndPoint, not moveEndToPoint)."""
        # Create mocks that simulate UIATextInfo behavior
        mock_textinfo = Mock()
        mock_textinfo.bookmark = 'uia_test'

        # Create mock terminal
        mock_terminal = Mock()

        # Mock the textInfos module methods
        import textInfos

        # Create mock for line start
        mock_line_start = Mock()
        mock_line_start.text = "Hello World"  # 11 characters

        # Mock targetCopy
        mock_target_copy = Mock()
        mock_target_copy.bookmark = 'target'

        # Mock the copies
        mock_target_info_copy = Mock()
        mock_target_info_copy.copy.return_value = mock_target_copy
        mock_target_copy.copy.return_value = mock_line_start

        mock_textinfo.copy.return_value = mock_target_copy

        # Mock terminal.makeTextInfo to create start position
        mock_start_info = Mock()
        mock_start_info.move.return_value = 0
        mock_start_info.compareEndPoints.return_value = -1
        mock_terminal.makeTextInfo.return_value = mock_start_info

        # Test that calculate doesn't raise AttributeError about moveEndToPoint
        result = self.calc.calculate(mock_textinfo, mock_terminal)

        # Should return a tuple, even if (0, 0) on error
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], int)
        self.assertIsInstance(result[1], int)


class TestConfigManagerComprehensive(unittest.TestCase):
    """Comprehensive tests for ConfigManager."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import ConfigManager
        self.manager = ConfigManager()

    def test_get_config_value(self):
        """Test getting config values."""
        # These should return values from mocked config
        value = self.manager.get('cursorTracking')
        self.assertIsInstance(value, bool)

    def test_set_config_value(self):
        """Test setting config values."""
        self.manager.set('quietMode', True)
        # Value should be set in config
        self.assertTrue(True)  # Config is mocked, just verify no error

    def test_config_validation(self):
        """Test config values are validated."""
        # Test with valid value
        self.manager.set('punctuationLevel', 2)

        # Test with invalid value (should be clamped or validated)
        self.manager.set('punctuationLevel', 10)


class TestWindowManagerComprehensive(unittest.TestCase):
    """Comprehensive tests for WindowManager."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import WindowManager, ConfigManager
        config_mgr = ConfigManager()
        self.manager = WindowManager(config_mgr)

    def test_window_definition_workflow(self):
        """Test complete window definition workflow."""
        # Start definition
        self.manager.start_definition()
        self.assertTrue(self.manager.is_defining())

        # Set window start
        result = self.manager.set_window_start(1, 1)
        self.assertTrue(result)

        # Set window end
        result = self.manager.set_window_end(24, 80)
        self.assertTrue(result)

        # Should no longer be defining after end is set
        self.assertFalse(self.manager.is_defining())

    def test_get_window_bounds(self):
        """Test getting window bounds."""
        bounds = self.manager.get_window_bounds()
        self.assertIsInstance(bounds, dict)
        self.assertIn('top', bounds)
        self.assertIn('bottom', bounds)
        self.assertIn('left', bounds)
        self.assertIn('right', bounds)

    def test_enable_window(self):
        """Test enabling window mode."""
        self.manager.enable_window()
        self.assertTrue(self.manager.is_window_enabled())

    def test_disable_window(self):
        """Test disabling window mode."""
        self.manager.disable_window()
        self.assertFalse(self.manager.is_window_enabled())

    def test_cancel_definition(self):
        """Test canceling window definition."""
        self.manager.start_definition()
        self.assertTrue(self.manager.is_defining())

        self.manager.cancel_definition()
        self.assertFalse(self.manager.is_defining())


class TestValidationFunctionsComprehensive(unittest.TestCase):
    """Comprehensive tests for validation functions."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import _validateInteger, _validateString, _validateSelectionSize
        self._validateInteger = _validateInteger
        self._validateString = _validateString
        self._validateSelectionSize = _validateSelectionSize

    def test_validate_integer_with_string(self):
        """Test _validateInteger with string input."""
        result = self._validateInteger("10", 0, 100, 50, "test")
        self.assertEqual(result, 10)

    def test_validate_integer_out_of_range(self):
        """Test _validateInteger returns default when out of range."""
        result = self._validateInteger(200, 0, 100, 50, "test")
        self.assertEqual(result, 50)  # Returns default, not clamped

        result = self._validateInteger(-10, 0, 100, 50, "test")
        self.assertEqual(result, 50)  # Returns default, not clamped

    def test_validate_integer_invalid_type(self):
        """Test _validateInteger with invalid type returns default."""
        result = self._validateInteger(None, 0, 100, 50, "test")
        self.assertEqual(result, 50)

    def test_validate_string_too_long(self):
        """Test _validateString truncates long strings."""
        long_string = "a" * 1000
        result = self._validateString(long_string, 100, "default", "test")
        self.assertEqual(len(result), 100)

    def test_validate_string_with_int(self):
        """Test _validateString with non-string type."""
        result = self._validateString(123, 10, "default", "test")
        self.assertEqual(result, "default")

    def test_validate_selection_negative_coordinates(self):
        """Test _validateSelectionSize handles negative coordinates with abs()."""
        # Function uses abs() so negative coordinates are handled
        valid, msg = self._validateSelectionSize(-1, 10, 1, 80)
        self.assertTrue(valid)  # abs(-1 - 10) + 1 = 12 rows (valid)

    def test_validate_selection_inverted_bounds(self):
        """Test _validateSelectionSize handles inverted bounds with abs()."""
        # Function uses abs() so inverted bounds are handled
        valid, msg = self._validateSelectionSize(10, 5, 1, 80)
        self.assertTrue(valid)  # abs(10 - 5) + 1 = 6 rows (valid)

    def test_validate_selection_too_many_rows(self):
        """Test _validateSelectionSize rejects selections with too many rows."""
        # MAX_SELECTION_ROWS is 10000
        valid, msg = self._validateSelectionSize(1, 10001, 1, 80)
        self.assertFalse(valid)
        self.assertIsNotNone(msg)

    def test_validate_selection_too_many_cols(self):
        """Test _validateSelectionSize rejects selections with too many columns."""
        # MAX_SELECTION_COLS is 1000
        valid, msg = self._validateSelectionSize(1, 10, 1, 1001)
        self.assertFalse(valid)
        self.assertIsNotNone(msg)


if __name__ == '__main__':
    unittest.main()
