"""
Unit tests for selection and copy operations.

Tests selection functionality and resource limit validation.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys


class TestSelectionOperations(unittest.TestCase):
    """Test selection operation functions."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_validate_selection_within_limits(self):
        """Test selection validation for normal-sized selections."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 100, 1, 80)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)

    def test_validate_selection_single_line(self):
        """Test selection validation for single line."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(5, 5, 1, 80)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)

    def test_validate_selection_single_column(self):
        """Test selection validation for single column."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 100, 10, 10)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)

    def test_validate_selection_exceeds_row_limit(self):
        """Test selection validation when exceeding row limit."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 10001, 1, 80)
        self.assertFalse(is_valid)
        self.assertIsNotNone(msg)
        self.assertIn("row", msg.lower())

    def test_validate_selection_exceeds_col_limit(self):
        """Test selection validation when exceeding column limit."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 100, 1, 1001)
        self.assertFalse(is_valid)
        self.assertIsNotNone(msg)
        self.assertIn("col", msg.lower())

    def test_validate_selection_large_valid(self):
        """Test selection validation for large but valid selection."""
        is_valid, msg = self.terminalAccess._validateSelectionSize(1, 9999, 1, 999)
        self.assertTrue(is_valid)
        self.assertIsNone(msg)


class TestPunctuationProcessing(unittest.TestCase):
    """Test punctuation level system."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_punctuation_sets_structure(self):
        """Test punctuation sets are properly structured."""
        self.assertIsInstance(self.terminalAccess.PUNCTUATION_SETS, dict)
        self.assertEqual(len(self.terminalAccess.PUNCTUATION_SETS), 4)

    def test_punctuation_none_empty(self):
        """Test PUNCT_NONE has empty set."""
        punct_set = self.terminalAccess.PUNCTUATION_SETS[self.terminalAccess.PUNCT_NONE]
        self.assertIsInstance(punct_set, set)
        self.assertEqual(len(punct_set), 0)

    def test_punctuation_some_basic(self):
        """Test PUNCT_SOME has basic punctuation."""
        punct_set = self.terminalAccess.PUNCTUATION_SETS[self.terminalAccess.PUNCT_SOME]
        self.assertIsInstance(punct_set, set)
        self.assertIn('.', punct_set)
        self.assertIn(',', punct_set)
        self.assertIn('?', punct_set)
        self.assertIn('!', punct_set)

    def test_punctuation_most_extended(self):
        """Test PUNCT_MOST has extended punctuation."""
        punct_set = self.terminalAccess.PUNCTUATION_SETS[self.terminalAccess.PUNCT_MOST]
        self.assertIsInstance(punct_set, set)

        # Should include PUNCT_SOME
        self.assertIn('.', punct_set)
        self.assertIn(',', punct_set)

        # Plus additional symbols
        self.assertIn('@', punct_set)
        self.assertIn('#', punct_set)
        self.assertIn('$', punct_set)
        self.assertIn('(', punct_set)
        self.assertIn(')', punct_set)

    def test_punctuation_all_none(self):
        """Test PUNCT_ALL is None (process everything)."""
        punct_set = self.terminalAccess.PUNCTUATION_SETS[self.terminalAccess.PUNCT_ALL]
        self.assertIsNone(punct_set)


class TestTerminalDetection(unittest.TestCase):
    """Test terminal application detection."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins.terminalAccess import GlobalPlugin
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            self.plugin = GlobalPlugin()

    def test_is_terminal_app_windows_terminal(self):
        """Test detection of Windows Terminal."""
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = "windowsterminal"

        result = self.plugin.isTerminalApp(obj)
        self.assertTrue(result)

    def test_is_terminal_app_cmd(self):
        """Test detection of Command Prompt."""
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = "cmd"

        result = self.plugin.isTerminalApp(obj)
        self.assertTrue(result)

    def test_is_terminal_app_powershell(self):
        """Test detection of PowerShell."""
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = "powershell"

        result = self.plugin.isTerminalApp(obj)
        self.assertTrue(result)

    def test_is_terminal_app_pwsh(self):
        """Test detection of PowerShell Core."""
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = "pwsh"

        result = self.plugin.isTerminalApp(obj)
        self.assertTrue(result)

    def test_is_terminal_app_conhost(self):
        """Test detection of Console Host."""
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = "conhost"

        result = self.plugin.isTerminalApp(obj)
        self.assertTrue(result)

    def test_is_terminal_app_non_terminal(self):
        """Test non-terminal application is not detected."""
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = "notepad"

        result = self.plugin.isTerminalApp(obj)
        self.assertFalse(result)

    def test_is_terminal_app_no_appmodule(self):
        """Test object without appModule is not detected."""
        obj = Mock()
        obj.appModule = None

        result = self.plugin.isTerminalApp(obj)
        self.assertFalse(result)

    def test_is_terminal_app_case_insensitive(self):
        """Test terminal detection is case-insensitive."""
        obj = Mock()
        obj.appModule = Mock()
        obj.appModule.appName = "WindowsTerminal"  # Mixed case

        result = self.plugin.isTerminalApp(obj)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
