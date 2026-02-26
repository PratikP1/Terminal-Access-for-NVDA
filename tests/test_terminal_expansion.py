"""
Tests for the terminal support expansion:
- Comprehensive ANSI escape stripping (OSC, DCS, private modes, charset, 2-char ESC)
- TextDiffer KIND_LAST_LINE_UPDATED detection
- NewOutputAnnouncer handling of KIND_LAST_LINE_UPDATED
- New terminal emulator entries and profiles
- TUI application profiles and window title detection
"""

import unittest
from unittest.mock import MagicMock, Mock, patch


class TestComprehensiveANSIStripping(unittest.TestCase):
	"""Tests for the expanded _STRIP_PATTERN regex in ANSIParser."""

	def _strip(self, text):
		"""Helper to call ANSIParser.stripANSI."""
		from globalPlugins.terminalAccess import ANSIParser
		return ANSIParser.stripANSI(text)

	def test_strip_basic_csi(self):
		"""Basic CSI sequences (colors) should be stripped."""
		self.assertEqual(self._strip('\x1b[31mRed\x1b[0m'), 'Red')

	def test_strip_private_mode_csi(self):
		"""Private mode CSI (e.g., cursor hide ?25l, show ?25h) should be stripped."""
		self.assertEqual(self._strip('\x1b[?25hVisible\x1b[?25l'), 'Visible')

	def test_strip_osc_bel_terminated(self):
		"""OSC sequences terminated by BEL (\\x07) should be stripped."""
		# Window title: ESC ] 0 ; title BEL
		self.assertEqual(self._strip('\x1b]0;My Terminal\x07Hello'), 'Hello')

	def test_strip_osc_st_terminated(self):
		"""OSC sequences terminated by ST (ESC \\\\) should be stripped."""
		self.assertEqual(self._strip('\x1b]0;My Terminal\x1b\\Hello'), 'Hello')

	def test_strip_osc_hyperlink(self):
		"""OSC 8 hyperlink sequences should be stripped."""
		# OSC 8 ; params ; uri BEL  link text  OSC 8 ; ; BEL
		text = '\x1b]8;;https://example.com\x07Link\x1b]8;;\x07'
		self.assertEqual(self._strip(text), 'Link')

	def test_strip_dcs_sequences(self):
		"""DCS sequences (ESC P ... ST) should be stripped."""
		self.assertEqual(self._strip('\x1bPq#0;2;0;0;0\x1b\\Text'), 'Text')

	def test_strip_charset_designation(self):
		"""Charset designation sequences (e.g., ESC ( B) should be stripped."""
		self.assertEqual(self._strip('\x1b(BHello\x1b)0'), 'Hello')

	def test_strip_two_char_esc_sequences(self):
		"""Two-character ESC sequences (e.g., ESC M, ESC 7, ESC 8) should be stripped."""
		self.assertEqual(self._strip('\x1bMLine\x1b7\x1b8'), 'Line')

	def test_strip_preserves_plain_text(self):
		"""Plain text without any escape sequences should be unchanged."""
		text = 'Hello, World! 123 @#$'
		self.assertEqual(self._strip(text), text)

	def test_strip_mixed_sequences(self):
		"""Mixed sequence types should all be stripped."""
		text = '\x1b[?25l\x1b]0;title\x07\x1b[1;32mGreen\x1b[0m\x1b(B\x1bM'
		self.assertEqual(self._strip(text), 'Green')

	def test_strip_csi_with_tilde(self):
		"""CSI sequences ending with ~ (e.g., key codes) should be stripped."""
		# F1 key: ESC [ 11 ~
		self.assertEqual(self._strip('\x1b[11~Text'), 'Text')


class TestTextDifferLastLineUpdated(unittest.TestCase):
	"""Tests for the KIND_LAST_LINE_UPDATED detection in TextDiffer."""

	def _make_differ(self):
		from globalPlugins.terminalAccess import TextDiffer
		return TextDiffer()

	def test_last_line_overwrite_detected(self):
		"""When only the last line changes, KIND_LAST_LINE_UPDATED should be returned."""
		from globalPlugins.terminalAccess import TextDiffer
		differ = self._make_differ()

		# Initial state
		differ.update("line1\nline2\nprogress: 50%")

		# Last line changes (progress update)
		kind, content = differ.update("line1\nline2\nprogress: 75%")
		self.assertEqual(kind, TextDiffer.KIND_LAST_LINE_UPDATED)

	def test_last_line_returns_new_tail(self):
		"""KIND_LAST_LINE_UPDATED should return the new last line content."""
		from globalPlugins.terminalAccess import TextDiffer
		differ = self._make_differ()

		differ.update("header\nstatus: loading...")
		kind, content = differ.update("header\nstatus: done!")
		self.assertEqual(kind, TextDiffer.KIND_LAST_LINE_UPDATED)
		self.assertEqual(content, "status: done!")

	def test_full_change_not_last_line(self):
		"""When prefix lines also differ, KIND_CHANGED should be returned."""
		from globalPlugins.terminalAccess import TextDiffer
		differ = self._make_differ()

		differ.update("line1\nline2\nline3")
		kind, content = differ.update("different1\nline2\nline3")
		self.assertEqual(kind, TextDiffer.KIND_CHANGED)

	def test_single_line_change_is_changed(self):
		"""A single line (no newline) change should be KIND_CHANGED, not last-line-updated."""
		from globalPlugins.terminalAccess import TextDiffer
		differ = self._make_differ()

		differ.update("hello")
		kind, content = differ.update("world")
		self.assertEqual(kind, TextDiffer.KIND_CHANGED)

	def test_append_still_works(self):
		"""Appending text should still return KIND_APPENDED."""
		from globalPlugins.terminalAccess import TextDiffer
		differ = self._make_differ()

		differ.update("line1\n")
		kind, content = differ.update("line1\nline2\n")
		self.assertEqual(kind, TextDiffer.KIND_APPENDED)
		self.assertEqual(content, "line2\n")

	def test_unchanged_still_works(self):
		"""Identical text should return KIND_UNCHANGED."""
		from globalPlugins.terminalAccess import TextDiffer
		differ = self._make_differ()

		differ.update("same\ntext")
		kind, content = differ.update("same\ntext")
		self.assertEqual(kind, TextDiffer.KIND_UNCHANGED)

	def test_spinner_overwrite(self):
		"""Simulated spinner (single char change on last line) should be detected."""
		from globalPlugins.terminalAccess import TextDiffer
		differ = self._make_differ()

		differ.update("Building...\n|")
		kind, _ = differ.update("Building...\n/")
		self.assertEqual(kind, TextDiffer.KIND_LAST_LINE_UPDATED)

		kind, _ = differ.update("Building...\n-")
		self.assertEqual(kind, TextDiffer.KIND_LAST_LINE_UPDATED)


class TestNewOutputAnnouncerLastLineUpdated(unittest.TestCase):
	"""Tests for NewOutputAnnouncer handling of KIND_LAST_LINE_UPDATED."""

	def test_feed_replaces_pending_on_last_line_update(self):
		"""KIND_LAST_LINE_UPDATED should REPLACE pending text, not accumulate."""
		from globalPlugins.terminalAccess import TextDiffer

		differ = TextDiffer()

		# Simulate the sequence that triggers last-line-updated
		differ.update("header\nstatus: loading...")
		kind, content = differ.update("header\nstatus: 50% done")
		self.assertEqual(kind, TextDiffer.KIND_LAST_LINE_UPDATED)
		self.assertEqual(content, "status: 50% done")

		# Another last-line update overwrites again
		kind, content = differ.update("header\nstatus: 100% complete")
		self.assertEqual(kind, TextDiffer.KIND_LAST_LINE_UPDATED)
		self.assertEqual(content, "status: 100% complete")
		# Content is just the new tail, not accumulated


class TestSupportedTerminals(unittest.TestCase):
	"""Tests for the expanded _SUPPORTED_TERMINALS frozenset."""

	def test_new_gpu_terminals_present(self):
		"""New GPU-accelerated terminals should be in _SUPPORTED_TERMINALS."""
		from globalPlugins.terminalAccess import _SUPPORTED_TERMINALS

		new_terminals = [
			'ghostty', 'rio', 'waveterm', 'contour', 'cool-retro-term',
		]
		for terminal in new_terminals:
			self.assertIn(terminal, _SUPPORTED_TERMINALS,
				f"'{terminal}' should be in _SUPPORTED_TERMINALS")

	def test_new_professional_terminals_present(self):
		"""New remote/professional terminals should be in _SUPPORTED_TERMINALS."""
		from globalPlugins.terminalAccess import _SUPPORTED_TERMINALS

		new_terminals = [
			'mobaxterm', 'securecrt', 'ttermpro', 'mremoteng', 'royalts',
		]
		for terminal in new_terminals:
			self.assertIn(terminal, _SUPPORTED_TERMINALS,
				f"'{terminal}' should be in _SUPPORTED_TERMINALS")

	def test_existing_terminals_still_present(self):
		"""Existing terminals should not have been removed."""
		from globalPlugins.terminalAccess import _SUPPORTED_TERMINALS

		existing = [
			'windowsterminal', 'cmd', 'powershell', 'pwsh', 'conhost',
			'cmder', 'conemu', 'conemu64', 'mintty', 'putty', 'kitty',
			'terminus', 'hyper', 'alacritty', 'wezterm', 'wezterm-gui',
			'tabby', 'fluent', 'wsl', 'bash',
		]
		for terminal in existing:
			self.assertIn(terminal, _SUPPORTED_TERMINALS,
				f"'{terminal}' should still be in _SUPPORTED_TERMINALS")

	def test_total_terminal_count(self):
		"""Total supported terminal count should be 30 (20 original + 10 new)."""
		from globalPlugins.terminalAccess import _SUPPORTED_TERMINALS
		self.assertEqual(len(_SUPPORTED_TERMINALS), 30)


class TestNewTerminalProfiles(unittest.TestCase):
	"""Tests for profiles of new terminal emulators."""

	def _get_manager(self):
		from globalPlugins.terminalAccess import ProfileManager
		return ProfileManager()

	def test_gpu_terminal_profiles_exist(self):
		"""Each new GPU terminal should have a default profile."""
		manager = self._get_manager()
		for name in ['ghostty', 'rio', 'waveterm', 'contour', 'cool-retro-term']:
			profile = manager.getProfile(name)
			self.assertIsNotNone(profile, f"Profile for '{name}' should exist")

	def test_professional_terminal_profiles_exist(self):
		"""Each new professional terminal should have a default profile."""
		manager = self._get_manager()
		for name in ['mobaxterm', 'securecrt', 'ttermpro', 'mremoteng', 'royalts']:
			profile = manager.getProfile(name)
			self.assertIsNotNone(profile, f"Profile for '{name}' should exist")

	def test_new_terminal_profiles_use_standard_tracking(self):
		"""New terminal profiles should use CT_STANDARD cursor tracking."""
		from globalPlugins.terminalAccess import CT_STANDARD
		manager = self._get_manager()
		for name in ['ghostty', 'rio', 'waveterm', 'contour', 'cool-retro-term',
					  'mobaxterm', 'securecrt', 'ttermpro', 'mremoteng', 'royalts']:
			profile = manager.getProfile(name)
			self.assertEqual(profile.cursorTrackingMode, CT_STANDARD,
				f"Profile '{name}' should use CT_STANDARD")


class TestTUIProfiles(unittest.TestCase):
	"""Tests for TUI application profiles."""

	def _get_manager(self):
		from globalPlugins.terminalAccess import ProfileManager
		return ProfileManager()

	def test_claude_profile_exists(self):
		"""Claude CLI profile should exist with expected settings."""
		from globalPlugins.terminalAccess import PUNCT_MOST
		manager = self._get_manager()
		profile = manager.getProfile('claude')
		self.assertIsNotNone(profile)
		self.assertEqual(profile.displayName, 'Claude CLI')
		self.assertEqual(profile.punctuationLevel, PUNCT_MOST)
		self.assertFalse(profile.repeatedSymbols)
		self.assertFalse(profile.linePause)
		self.assertFalse(profile.keyEcho)

	def test_lazygit_profile_exists(self):
		"""lazygit profile should exist with expected settings."""
		from globalPlugins.terminalAccess import PUNCT_MOST, CT_WINDOW
		manager = self._get_manager()
		profile = manager.getProfile('lazygit')
		self.assertIsNotNone(profile)
		self.assertEqual(profile.punctuationLevel, PUNCT_MOST)
		self.assertFalse(profile.repeatedSymbols)
		self.assertFalse(profile.keyEcho)
		self.assertEqual(profile.cursorTrackingMode, CT_WINDOW)

	def test_btop_btm_share_profile(self):
		"""btm should map to the same profile as btop."""
		manager = self._get_manager()
		btop_profile = manager.getProfile('btop')
		btm_profile = manager.getProfile('btm')
		self.assertIsNotNone(btop_profile)
		self.assertIsNotNone(btm_profile)
		self.assertIs(btop_profile, btm_profile)

	def test_yazi_profile_exists(self):
		"""yazi profile should exist."""
		manager = self._get_manager()
		profile = manager.getProfile('yazi')
		self.assertIsNotNone(profile)
		self.assertFalse(profile.keyEcho)
		self.assertFalse(profile.repeatedSymbols)

	def test_k9s_profile_exists(self):
		"""k9s profile should exist with expected settings."""
		from globalPlugins.terminalAccess import PUNCT_MOST
		manager = self._get_manager()
		profile = manager.getProfile('k9s')
		self.assertIsNotNone(profile)
		self.assertEqual(profile.punctuationLevel, PUNCT_MOST)
		self.assertFalse(profile.linePause)

	def test_tui_profiles_in_builtin_names(self):
		"""TUI profiles should be in _BUILTIN_PROFILE_NAMES (cannot be removed)."""
		from globalPlugins.terminalAccess import _BUILTIN_PROFILE_NAMES
		for name in ['claude', 'lazygit', 'btop', 'btm', 'yazi', 'k9s']:
			self.assertIn(name, _BUILTIN_PROFILE_NAMES,
				f"'{name}' should be in _BUILTIN_PROFILE_NAMES")


class TestTUIWindowTitleDetection(unittest.TestCase):
	"""Tests for window title-based TUI application detection."""

	def _get_manager(self):
		from globalPlugins.terminalAccess import ProfileManager
		return ProfileManager()

	def _make_focus(self, app_name='unknown', title=''):
		"""Create a mock focus object with given app name and window title."""
		focus = MagicMock()
		focus.appModule.appName = app_name
		focus.name = title
		return focus

	def test_detect_claude_from_title(self):
		"""Window title containing 'claude' should detect Claude CLI."""
		manager = self._get_manager()
		focus = self._make_focus(title='claude - conversation')
		self.assertEqual(manager.detectApplication(focus), 'claude')

	def test_detect_lazygit_from_title(self):
		"""Window title containing 'lazygit' should detect lazygit."""
		manager = self._get_manager()
		focus = self._make_focus(title='lazygit: myrepo')
		self.assertEqual(manager.detectApplication(focus), 'lazygit')

	def test_detect_btop_from_title(self):
		"""Window title containing 'btop' should detect btop."""
		manager = self._get_manager()
		focus = self._make_focus(title='btop++')
		self.assertEqual(manager.detectApplication(focus), 'btop')

	def test_detect_btm_from_title(self):
		"""Window title containing 'btm' should detect btop profile."""
		manager = self._get_manager()
		focus = self._make_focus(title='btm - system monitor')
		self.assertEqual(manager.detectApplication(focus), 'btop')

	def test_detect_yazi_from_title(self):
		"""Window title containing 'yazi' should detect yazi."""
		manager = self._get_manager()
		focus = self._make_focus(title='yazi /home/user')
		self.assertEqual(manager.detectApplication(focus), 'yazi')

	def test_detect_k9s_from_title(self):
		"""Window title containing 'k9s' should detect k9s."""
		manager = self._get_manager()
		focus = self._make_focus(title='k9s - default namespace')
		self.assertEqual(manager.detectApplication(focus), 'k9s')

	def test_unknown_title_returns_default(self):
		"""Unknown window title should return 'default'."""
		manager = self._get_manager()
		focus = self._make_focus(title='Some Random Application')
		self.assertEqual(manager.detectApplication(focus), 'default')


if __name__ == '__main__':
	unittest.main()
