"""
Unit tests for input validation functions.

Tests the security hardening validation helpers added in v1.0.16.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys


class TestValidationFunctions(unittest.TestCase):
    """Test input validation helper functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Import the module after mocks are set up
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_validate_integer_valid_value(self):
        """Test _validateInteger with valid value."""
        result = self.terminalAccess._validateInteger(5, 0, 10, 0, "test_field")
        self.assertEqual(result, 5)

    def test_validate_integer_at_min_boundary(self):
        """Test _validateInteger at minimum boundary."""
        result = self.terminalAccess._validateInteger(0, 0, 10, 5, "test_field")
        self.assertEqual(result, 0)

    def test_validate_integer_at_max_boundary(self):
        """Test _validateInteger at maximum boundary."""
        result = self.terminalAccess._validateInteger(10, 0, 10, 5, "test_field")
        self.assertEqual(result, 10)

    def test_validate_integer_below_min(self):
        """Test _validateInteger with value below minimum."""
        result = self.terminalAccess._validateInteger(-5, 0, 10, 5, "test_field")
        self.assertEqual(result, 5)  # Should return default

    def test_validate_integer_above_max(self):
        """Test _validateInteger with value above maximum."""
        result = self.terminalAccess._validateInteger(15, 0, 10, 5, "test_field")
        self.assertEqual(result, 5)  # Should return default

    def test_validate_integer_invalid_type(self):
        """Test _validateInteger with invalid type."""
        result = self.terminalAccess._validateInteger("invalid", 0, 10, 5, "test_field")
        self.assertEqual(result, 5)  # Should return default

    def test_validate_integer_string_convertible(self):
        """Test _validateInteger with string that can be converted."""
        result = self.terminalAccess._validateInteger("7", 0, 10, 5, "test_field")
        self.assertEqual(result, 7)

    def test_validate_string_valid_value(self):
        """Test _validateString with valid value."""
        result = self.terminalAccess._validateString("test", 10, "default", "test_field")
        self.assertEqual(result, "test")

    def test_validate_string_at_max_length(self):
        """Test _validateString at maximum length."""
        result = self.terminalAccess._validateString("1234567890", 10, "default", "test_field")
        self.assertEqual(result, "1234567890")

    def test_validate_string_exceeds_max_length(self):
        """Test _validateString exceeding maximum length."""
        result = self.terminalAccess._validateString("12345678901", 10, "default", "test_field")
        self.assertEqual(result, "1234567890")  # Should truncate

    def test_validate_string_empty(self):
        """Test _validateString with empty string."""
        result = self.terminalAccess._validateString("", 10, "default", "test_field")
        self.assertEqual(result, "")

    def test_validate_string_invalid_type(self):
        """Test _validateString with invalid type."""
        result = self.terminalAccess._validateString(None, 10, "default", "test_field")
        self.assertEqual(result, "default")

    def test_validate_selection_size_valid(self):
        """Test _validateSelectionSize with valid dimensions."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 100, 1, 80)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)

    def test_validate_selection_size_max_rows_boundary(self):
        """Test _validateSelectionSize at max rows boundary."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 10000, 1, 80)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)

    def test_validate_selection_size_exceeds_max_rows(self):
        """Test _validateSelectionSize exceeding max rows."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 10001, 1, 80)
        self.assertFalse(is_valid)
        self.assertIn("10001", msg)
        self.assertIn("10000", msg)

    def test_validate_selection_size_max_cols_boundary(self):
        """Test _validateSelectionSize at max columns boundary."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 100, 1, 1000)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)

    def test_validate_selection_size_exceeds_max_cols(self):
        """Test _validateSelectionSize exceeding max columns."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 100, 1, 1001)
        self.assertFalse(is_valid)
        self.assertIn("1001", msg)
        self.assertIn("1000", msg)

    def test_validate_selection_size_reversed_rows(self):
        """Test _validateSelectionSize with reversed row order."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(100, 1, 1, 80)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)

    def test_validate_selection_size_reversed_cols(self):
        """Test _validateSelectionSize with reversed column order."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 100, 80, 1)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)


class TestResourceLimits(unittest.TestCase):
    """Test resource limit constants."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_max_selection_rows_defined(self):
        """Test MAX_SELECTION_ROWS constant is defined."""
        self.assertTrue(hasattr(self.terminalAccess, 'MAX_SELECTION_ROWS'))
        self.assertEqual(self.terminalAccess.MAX_SELECTION_ROWS, 10000)

    def test_max_selection_cols_defined(self):
        """Test MAX_SELECTION_COLS constant is defined."""
        self.assertTrue(hasattr(self.terminalAccess, 'MAX_SELECTION_COLS'))
        self.assertEqual(self.terminalAccess.MAX_SELECTION_COLS, 1000)

    def test_max_window_dimension_defined(self):
        """Test MAX_WINDOW_DIMENSION constant is defined."""
        self.assertTrue(hasattr(self.terminalAccess, 'MAX_WINDOW_DIMENSION'))
        self.assertEqual(self.terminalAccess.MAX_WINDOW_DIMENSION, 10000)

    def test_max_repeated_symbols_length_defined(self):
        """Test MAX_REPEATED_SYMBOLS_LENGTH constant is defined."""
        self.assertTrue(hasattr(self.terminalAccess, 'MAX_REPEATED_SYMBOLS_LENGTH'))
        self.assertEqual(self.terminalAccess.MAX_REPEATED_SYMBOLS_LENGTH, 50)


if __name__ == '__main__':
    unittest.main()
