"""
Tests for third-party terminal emulator support.

Tests cover:
- Terminal detection for third-party emulators
- Default profile creation for third-party terminals
- Profile application and settings

Section Reference: FUTURE_ENHANCEMENTS.md Section 5.1 (lines 618-677)
"""

import unittest
from unittest.mock import Mock, MagicMock


class TestThirdPartyTerminalDetection(unittest.TestCase):
	"""Test terminal detection for third-party emulators."""

	def setUp(self):
		"""Set up test fixtures."""
		from globalPlugins.terminalAccess import GlobalPlugin
		self.plugin = GlobalPlugin()

	def test_cmder_detection(self):
		"""Test Cmder terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "cmder"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "Cmder should be detected as terminal")

	def test_conemu_detection(self):
		"""Test ConEmu terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "conemu"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "ConEmu should be detected as terminal")

	def test_conemu64_detection(self):
		"""Test ConEmu 64-bit terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "conemu64"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "ConEmu64 should be detected as terminal")

	def test_mintty_detection(self):
		"""Test mintty (Git Bash) terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "mintty"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "mintty should be detected as terminal")

	def test_putty_detection(self):
		"""Test PuTTY terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "putty"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "PuTTY should be detected as terminal")

	def test_kitty_detection(self):
		"""Test KiTTY terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "kitty"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "KiTTY should be detected as terminal")

	def test_terminus_detection(self):
		"""Test Terminus terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "terminus"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "Terminus should be detected as terminal")

	def test_hyper_detection(self):
		"""Test Hyper terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "hyper"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "Hyper should be detected as terminal")

	def test_alacritty_detection(self):
		"""Test Alacritty terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "alacritty"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "Alacritty should be detected as terminal")

	def test_wezterm_detection(self):
		"""Test WezTerm terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "wezterm"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "WezTerm should be detected as terminal")

	def test_wezterm_gui_detection(self):
		"""Test WezTerm GUI terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "wezterm-gui"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "WezTerm GUI should be detected as terminal")

	def test_tabby_detection(self):
		"""Test Tabby terminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "tabby"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "Tabby should be detected as terminal")

	def test_fluent_detection(self):
		"""Test FluentTerminal detection."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "fluent"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "FluentTerminal should be detected as terminal")

	def test_builtin_terminal_still_works(self):
		"""Test that built-in terminals still work after adding third-party support."""
		builtin_terminals = [
			"windowsterminal",
			"cmd",
			"powershell",
			"pwsh",
			"conhost"
		]

		for terminal in builtin_terminals:
			mock_obj = Mock()
			mock_obj.appModule.appName = terminal
			result = self.plugin.isTerminalApp(mock_obj)
			self.assertTrue(result, f"Built-in terminal {terminal} should still be detected")

	def test_non_terminal_app_rejected(self):
		"""Test that non-terminal apps are not detected as terminals."""
		mock_obj = Mock()
		mock_obj.appModule.appName = "notepad"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertFalse(result, "Notepad should not be detected as terminal")

	def test_case_insensitive_detection(self):
		"""Test that terminal detection is case-insensitive."""
		# Test with uppercase
		mock_obj = Mock()
		mock_obj.appModule.appName = "CMDER"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "Detection should be case-insensitive (uppercase)")

		# Test with mixed case
		mock_obj.appModule.appName = "ConEmu"
		result = self.plugin.isTerminalApp(mock_obj)
		self.assertTrue(result, "Detection should be case-insensitive (mixed)")


class TestThirdPartyTerminalProfiles(unittest.TestCase):
	"""Test default profile creation for third-party terminals."""

	def setUp(self):
		"""Set up test fixtures."""
		from globalPlugins.terminalAccess import ProfileManager
		self.manager = ProfileManager()

	def test_cmder_profile_exists(self):
		"""Test Cmder profile is created."""
		self.assertIn('cmder', self.manager.profiles)
		profile = self.manager.profiles['cmder']
		self.assertEqual(profile.displayName, 'Cmder')

	def test_conemu_profile_exists(self):
		"""Test ConEmu profile is created."""
		self.assertIn('conemu', self.manager.profiles)
		profile = self.manager.profiles['conemu']
		self.assertEqual(profile.displayName, 'ConEmu')

	def test_conemu64_profile_exists(self):
		"""Test ConEmu64 profile is created."""
		self.assertIn('conemu64', self.manager.profiles)

	def test_mintty_profile_exists(self):
		"""Test mintty profile is created."""
		self.assertIn('mintty', self.manager.profiles)
		profile = self.manager.profiles['mintty']
		self.assertEqual(profile.displayName, 'Git Bash (mintty)')

	def test_putty_profile_exists(self):
		"""Test PuTTY profile is created."""
		self.assertIn('putty', self.manager.profiles)
		profile = self.manager.profiles['putty']
		self.assertEqual(profile.displayName, 'PuTTY')

	def test_kitty_profile_exists(self):
		"""Test KiTTY profile is created."""
		self.assertIn('kitty', self.manager.profiles)

	def test_terminus_profile_exists(self):
		"""Test Terminus profile is created."""
		self.assertIn('terminus', self.manager.profiles)
		profile = self.manager.profiles['terminus']
		self.assertEqual(profile.displayName, 'Terminus')

	def test_hyper_profile_exists(self):
		"""Test Hyper profile is created."""
		self.assertIn('hyper', self.manager.profiles)
		profile = self.manager.profiles['hyper']
		self.assertEqual(profile.displayName, 'Hyper')

	def test_alacritty_profile_exists(self):
		"""Test Alacritty profile is created."""
		self.assertIn('alacritty', self.manager.profiles)
		profile = self.manager.profiles['alacritty']
		self.assertEqual(profile.displayName, 'Alacritty')

	def test_wezterm_profile_exists(self):
		"""Test WezTerm profile is created."""
		self.assertIn('wezterm', self.manager.profiles)
		profile = self.manager.profiles['wezterm']
		self.assertEqual(profile.displayName, 'WezTerm')

	def test_wezterm_gui_profile_exists(self):
		"""Test WezTerm GUI profile is created."""
		self.assertIn('wezterm-gui', self.manager.profiles)

	def test_tabby_profile_exists(self):
		"""Test Tabby profile is created."""
		self.assertIn('tabby', self.manager.profiles)
		profile = self.manager.profiles['tabby']
		self.assertEqual(profile.displayName, 'Tabby')

	def test_fluent_profile_exists(self):
		"""Test FluentTerminal profile is created."""
		self.assertIn('fluent', self.manager.profiles)
		profile = self.manager.profiles['fluent']
		self.assertEqual(profile.displayName, 'FluentTerminal')

	def test_builtin_profiles_still_exist(self):
		"""Test that built-in profiles still exist after adding third-party profiles."""
		builtin_profiles = ['vim', 'nvim', 'tmux', 'htop', 'less', 'more', 'git', 'nano', 'irssi']

		for profile_name in builtin_profiles:
			self.assertIn(profile_name, self.manager.profiles,
						  f"Built-in profile {profile_name} should still exist")

	def test_third_party_profile_settings(self):
		"""Test that third-party profiles have reasonable default settings."""
		third_party_profiles = [
			'cmder', 'conemu', 'mintty', 'putty', 'terminus',
			'hyper', 'alacritty', 'wezterm', 'tabby', 'fluent'
		]

		for profile_name in third_party_profiles:
			profile = self.manager.profiles[profile_name]

			# All should have punctuation level set
			self.assertIsNotNone(profile.punctuationLevel,
								 f"{profile_name} should have punctuation level")

			# All should have cursor tracking mode set
			self.assertIsNotNone(profile.cursorTrackingMode,
								 f"{profile_name} should have cursor tracking mode")

	def test_profile_count_increased(self):
		"""Test that total profile count includes third-party terminals."""
		# Original 7 default profiles + 13 third-party = at least 20 profiles
		# (Some share profiles like conemu64->conemu, kitty->putty, etc.)
		self.assertGreaterEqual(len(self.manager.profiles), 18,
								"Should have at least 18 profiles including third-party")


class TestProfileManagerIntegration(unittest.TestCase):
	"""Test ProfileManager integration with third-party terminals."""

	def setUp(self):
		"""Set up test fixtures."""
		from globalPlugins.terminalAccess import ProfileManager
		self.manager = ProfileManager()

	def test_get_third_party_profile(self):
		"""Test getting a third-party terminal profile."""
		profile = self.manager.getProfile('cmder')
		self.assertIsNotNone(profile)
		self.assertEqual(profile.appName, 'cmder')

	def test_set_active_third_party_profile(self):
		"""Test setting a third-party terminal as active profile."""
		self.manager.setActiveProfile('mintty')
		self.assertIsNotNone(self.manager.activeProfile)
		self.assertEqual(self.manager.activeProfile.appName, 'mintty')


if __name__ == '__main__':
	unittest.main()
