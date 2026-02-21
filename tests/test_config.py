"""
Unit tests for configuration management.

Tests config sanitization and validation added in v1.0.16.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys


class TestConfigurationSanitization(unittest.TestCase):
    """Test configuration sanitization on initialization."""

    def setUp(self):
        """Set up test fixtures."""
        # Get fresh config for each test
        config_mock = sys.modules['config']
        config_mock.conf = MagicMock()
        config_mock.conf.__getitem__ = MagicMock(return_value={
            "cursorTracking": True,
            "cursorTrackingMode": 1,
            "keyEcho": True,
            "linePause": True,
            "processSymbols": False,
            "punctuationLevel": 2,
            "repeatedSymbols": False,
            "repeatedSymbolsValues": "-_=!",
            "cursorDelay": 20,
            "quietMode": False,
            "windowTop": 0,
            "windowBottom": 0,
            "windowLeft": 0,
            "windowRight": 0,
            "windowEnabled": False,
        })

    def test_sanitize_config_valid_values(self):
        """Test _sanitizeConfig with all valid values."""
        from globalPlugins.terminalAccess import GlobalPlugin

        # Create mock for GUI dialog
        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()

            # Should not raise any errors
            config_mock = sys.modules['config']
            conf = config_mock.conf["terminalAccess"]

            # Values should remain unchanged
            self.assertEqual(conf["cursorTrackingMode"], 1)
            self.assertEqual(conf["punctuationLevel"], 2)
            self.assertEqual(conf["cursorDelay"], 20)

    def test_sanitize_config_invalid_tracking_mode(self):
        """Test _sanitizeConfig with invalid cursor tracking mode."""
        config_mock = sys.modules['config']
        config_dict = config_mock.conf["terminalAccess"]
        config_dict["cursorTrackingMode"] = 99  # Invalid

        from globalPlugins.terminalAccess import GlobalPlugin

        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()

            # Should be sanitized to default (1)
            self.assertEqual(config_dict["cursorTrackingMode"], 1)

    def test_sanitize_config_invalid_punctuation_level(self):
        """Test _sanitizeConfig with invalid punctuation level."""
        config_mock = sys.modules['config']
        config_dict = config_mock.conf["terminalAccess"]
        config_dict["punctuationLevel"] = -1  # Invalid

        from globalPlugins.terminalAccess import GlobalPlugin

        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()

            # Should be sanitized to default (2)
            self.assertEqual(config_dict["punctuationLevel"], 2)

    def test_sanitize_config_invalid_cursor_delay(self):
        """Test _sanitizeConfig with invalid cursor delay."""
        config_mock = sys.modules['config']
        config_dict = config_mock.conf["terminalAccess"]
        config_dict["cursorDelay"] = 5000  # Too high

        from globalPlugins.terminalAccess import GlobalPlugin

        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()

            # Should be sanitized to default (20)
            self.assertEqual(config_dict["cursorDelay"], 20)

    def test_sanitize_config_long_repeated_symbols(self):
        """Test _sanitizeConfig with too long repeated symbols string."""
        config_mock = sys.modules['config']
        config_dict = config_mock.conf["terminalAccess"]
        config_dict["repeatedSymbolsValues"] = "a" * 100  # Too long

        from globalPlugins.terminalAccess import GlobalPlugin

        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()

            # Should be truncated to MAX_REPEATED_SYMBOLS_LENGTH
            self.assertEqual(len(config_dict["repeatedSymbolsValues"]), 50)

    def test_sanitize_config_invalid_window_bounds(self):
        """Test _sanitizeConfig with invalid window bounds."""
        config_mock = sys.modules['config']
        config_dict = config_mock.conf["terminalAccess"]
        config_dict["windowTop"] = -10  # Negative
        config_dict["windowBottom"] = 20000  # Too high

        from globalPlugins.terminalAccess import GlobalPlugin

        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()

            # Should be sanitized
            self.assertEqual(config_dict["windowTop"], 0)
            self.assertEqual(config_dict["windowBottom"], 0)


class TestConfigConstants(unittest.TestCase):
    """Test configuration constants."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_cursor_tracking_constants(self):
        """Test cursor tracking mode constants are defined."""
        self.assertEqual(self.terminalAccess.CT_OFF, 0)
        self.assertEqual(self.terminalAccess.CT_STANDARD, 1)
        self.assertEqual(self.terminalAccess.CT_HIGHLIGHT, 2)
        self.assertEqual(self.terminalAccess.CT_WINDOW, 3)

    def test_punctuation_constants(self):
        """Test punctuation level constants are defined."""
        self.assertEqual(self.terminalAccess.PUNCT_NONE, 0)
        self.assertEqual(self.terminalAccess.PUNCT_SOME, 1)
        self.assertEqual(self.terminalAccess.PUNCT_MOST, 2)
        self.assertEqual(self.terminalAccess.PUNCT_ALL, 3)

    def test_punctuation_sets_defined(self):
        """Test PUNCTUATION_SETS dictionary is properly defined."""
        self.assertIsNotNone(self.terminalAccess.PUNCTUATION_SETS)
        self.assertIn(self.terminalAccess.PUNCT_NONE, self.terminalAccess.PUNCTUATION_SETS)
        self.assertIn(self.terminalAccess.PUNCT_SOME, self.terminalAccess.PUNCTUATION_SETS)
        self.assertIn(self.terminalAccess.PUNCT_MOST, self.terminalAccess.PUNCTUATION_SETS)
        self.assertIn(self.terminalAccess.PUNCT_ALL, self.terminalAccess.PUNCTUATION_SETS)

    def test_punctuation_sets_content(self):
        """Test PUNCTUATION_SETS contain expected characters."""
        punct_sets = self.terminalAccess.PUNCTUATION_SETS

        # PUNCT_NONE should be empty
        self.assertEqual(len(punct_sets[self.terminalAccess.PUNCT_NONE]), 0)

        # PUNCT_SOME should have basic punctuation
        self.assertIn('.', punct_sets[self.terminalAccess.PUNCT_SOME])
        self.assertIn(',', punct_sets[self.terminalAccess.PUNCT_SOME])

        # PUNCT_MOST should have more punctuation
        self.assertIn('@', punct_sets[self.terminalAccess.PUNCT_MOST])
        self.assertIn('#', punct_sets[self.terminalAccess.PUNCT_MOST])

        # PUNCT_ALL should be None (process everything)
        self.assertIsNone(punct_sets[self.terminalAccess.PUNCT_ALL])


class TestConfigSpec(unittest.TestCase):
    """Test configuration specification."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_confspec_defined(self):
        """Test confspec dictionary is defined."""
        self.assertIsNotNone(self.terminalAccess.confspec)

    def test_confspec_has_required_keys(self):
        """Test confspec has all required configuration keys."""
        required_keys = [
            "cursorTracking",
            "cursorTrackingMode",
            "keyEcho",
            "linePause",
            "processSymbols",
            "punctuationLevel",
            "repeatedSymbols",
            "repeatedSymbolsValues",
            "cursorDelay",
            "quietMode",
            "windowTop",
            "windowBottom",
            "windowLeft",
            "windowRight",
            "windowEnabled",
        ]

        for key in required_keys:
            self.assertIn(key, self.terminalAccess.confspec, f"Missing config key: {key}")


class TestConfigMigration(unittest.TestCase):
    """Test configuration migration from old keys to new keys."""

    def test_migrate_processSymbols_to_punctuationLevel_true(self):
        """Test migration from processSymbols=True to punctuationLevel=2."""
        from globalPlugins.terminalAccess import ConfigManager, PUNCT_MOST

        # Mock config with old processSymbols setting
        config_mock = sys.modules['config']
        config_dict = {
            "cursorTracking": True,
            "cursorTrackingMode": 1,
            "keyEcho": True,
            "linePause": True,
            "processSymbols": True,  # Old setting
            # punctuationLevel not set yet
            "repeatedSymbols": False,
            "repeatedSymbolsValues": "-_=!",
            "cursorDelay": 20,
            "quietMode": False,
            "windowTop": 0,
            "windowBottom": 0,
            "windowLeft": 0,
            "windowRight": 0,
            "windowEnabled": False,
        }
        config_mock.conf.__getitem__ = MagicMock(return_value=config_dict)

        # Create ConfigManager which should trigger migration
        manager = ConfigManager()

        # Verify migration occurred
        self.assertEqual(config_dict["punctuationLevel"], PUNCT_MOST)
        # Old key should still exist (not deleted)
        self.assertIn("processSymbols", config_dict)

    def test_migrate_processSymbols_to_punctuationLevel_false(self):
        """Test migration from processSymbols=False to punctuationLevel=0."""
        from globalPlugins.terminalAccess import ConfigManager, PUNCT_NONE

        # Mock config with old processSymbols setting
        config_mock = sys.modules['config']
        config_dict = {
            "cursorTracking": True,
            "cursorTrackingMode": 1,
            "keyEcho": True,
            "linePause": True,
            "processSymbols": False,  # Old setting
            # punctuationLevel not set yet
            "repeatedSymbols": False,
            "repeatedSymbolsValues": "-_=!",
            "cursorDelay": 20,
            "quietMode": False,
            "windowTop": 0,
            "windowBottom": 0,
            "windowLeft": 0,
            "windowRight": 0,
            "windowEnabled": False,
        }
        config_mock.conf.__getitem__ = MagicMock(return_value=config_dict)

        # Create ConfigManager which should trigger migration
        manager = ConfigManager()

        # Verify migration occurred
        self.assertEqual(config_dict["punctuationLevel"], PUNCT_NONE)
        # Old key should still exist (not deleted)
        self.assertIn("processSymbols", config_dict)

    def test_no_migration_when_punctuationLevel_exists(self):
        """Test that migration doesn't overwrite existing punctuationLevel."""
        from globalPlugins.terminalAccess import ConfigManager, PUNCT_ALL

        # Mock config with both old and new settings
        config_mock = sys.modules['config']
        config_dict = {
            "cursorTracking": True,
            "cursorTrackingMode": 1,
            "keyEcho": True,
            "linePause": True,
            "processSymbols": True,  # Old setting
            "punctuationLevel": PUNCT_ALL,  # New setting already exists
            "repeatedSymbols": False,
            "repeatedSymbolsValues": "-_=!",
            "cursorDelay": 20,
            "quietMode": False,
            "windowTop": 0,
            "windowBottom": 0,
            "windowLeft": 0,
            "windowRight": 0,
            "windowEnabled": False,
        }
        config_mock.conf.__getitem__ = MagicMock(return_value=config_dict)

        # Create ConfigManager which should trigger migration check
        manager = ConfigManager()

        # Verify existing value was preserved
        self.assertEqual(config_dict["punctuationLevel"], PUNCT_ALL)


if __name__ == '__main__':
    unittest.main()
