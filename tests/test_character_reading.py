"""
Tests for Terminal Access character reading functionality.

Tests cover the direct implementation of review cursor character reading
to ensure comma and period gestures don't type characters.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys


class TestCharacterReading(unittest.TestCase):
	"""Test character reading scripts."""

	def test_readReviewCharacter_helper_exists(self):
		"""Test that _readReviewCharacter helper function exists."""
		from globalPlugins.terminalAccess import GlobalPlugin

		self.assertTrue(hasattr(GlobalPlugin, '_readReviewCharacter'))
		method = getattr(GlobalPlugin, '_readReviewCharacter')
		self.assertTrue(callable(method))

	@patch('globalPlugins.terminalAccess.api')
	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.ui')
	def test_readReviewCharacter_current_character(self, mock_ui, mock_speech, mock_api):
		"""Test reading current character without movement."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()

		# Mock review position
		mock_info = MagicMock()
		mock_info.copy.return_value = mock_info
		mock_info.text = 'a'
		mock_api.getReviewPosition.return_value = mock_info

		# Call the helper
		plugin._readReviewCharacter(movement=0, phonetic=False)

		# Verify speech was called
		mock_speech.speakTextInfo.assert_called_once()

	@patch('globalPlugins.terminalAccess.api')
	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.ui')
	def test_readReviewCharacter_phonetic(self, mock_ui, mock_speech, mock_api):
		"""Test reading character with phonetic spelling."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()

		# Mock review position
		mock_info = MagicMock()
		mock_info.copy.return_value = mock_info
		mock_info.text = 'a'
		mock_api.getReviewPosition.return_value = mock_info

		# Call the helper with phonetic mode
		plugin._readReviewCharacter(movement=0, phonetic=True)

		# Verify spelling was used
		mock_speech.speakSpelling.assert_called_once_with('a')

	@patch('globalPlugins.terminalAccess.api')
	@patch('globalPlugins.terminalAccess.speech')
	@patch('globalPlugins.terminalAccess.ui')
	def test_readReviewCharacter_next_character(self, mock_ui, mock_speech, mock_api):
		"""Test reading next character with movement."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()

		# Mock review position and movement
		mock_info = MagicMock()
		mock_copy = MagicMock()
		mock_copy.move.return_value = 1  # Successful move
		mock_copy.text = 'b'
		mock_copy.compareEndPoints.return_value = -1
		mock_info.copy.return_value = mock_copy
		mock_api.getReviewPosition.return_value = mock_info

		# Call the helper with forward movement
		plugin._readReviewCharacter(movement=1, phonetic=False)

		# Verify movement was attempted
		mock_copy.move.assert_called_once()
		# Verify setReviewPosition was called to update position
		mock_api.setReviewPosition.assert_called()

	@patch('globalPlugins.terminalAccess.api')
	@patch('globalPlugins.terminalAccess.ui')
	def test_readReviewCharacter_no_review_position(self, mock_ui, mock_api):
		"""Test behavior when no review position available."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Create plugin instance
		plugin = GlobalPlugin()

		# Mock no review position
		mock_api.getReviewPosition.return_value = None
		plugin._boundTerminal = None

		# Call the helper
		plugin._readReviewCharacter(movement=0)

		# Verify error message was shown
		mock_ui.message.assert_called_once()

	def test_script_readCurrentChar_uses_helper(self):
		"""Test that script_readCurrentChar uses _readReviewCharacter."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		# Mock scriptHandler to simulate single press
		with patch('globalPlugins.terminalAccess.scriptHandler.getLastScriptRepeatCount', return_value=0):
			plugin.script_readCurrentChar(mock_gesture)

		# Verify helper was called with correct parameters
		plugin._readReviewCharacter.assert_called_once_with(movement=0)

	def test_script_readNextChar_uses_helper(self):
		"""Test that script_readNextChar uses _readReviewCharacter."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		plugin.script_readNextChar(mock_gesture)

		# Verify helper was called with forward movement
		plugin._readReviewCharacter.assert_called_once_with(movement=1)

	def test_script_readPreviousChar_uses_helper(self):
		"""Test that script_readPreviousChar uses _readReviewCharacter."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		plugin.script_readPreviousChar(mock_gesture)

		# Verify helper was called with backward movement
		plugin._readReviewCharacter.assert_called_once_with(movement=-1)

	def test_script_readCurrentChar_phonetic_on_double_press(self):
		"""Test that double-press triggers phonetic reading."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		# Mock scriptHandler to simulate double press
		with patch('globalPlugins.terminalAccess.scriptHandler.getLastScriptRepeatCount', return_value=1):
			plugin.script_readCurrentChar(mock_gesture)

		# Verify helper was called with phonetic=True
		plugin._readReviewCharacter.assert_called_once_with(movement=0, phonetic=True)

	def test_script_readCurrentChar_character_code_on_triple_press(self):
		"""Test that triple-press triggers character code announcement."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture and helper
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._announceCharacterCode = MagicMock()

		# Mock scriptHandler to simulate triple press
		with patch('globalPlugins.terminalAccess.scriptHandler.getLastScriptRepeatCount', return_value=2):
			plugin.script_readCurrentChar(mock_gesture)

		# Verify character code function was called
		plugin._announceCharacterCode.assert_called_once()

	@patch('globalPlugins.terminalAccess.ui')
	def test_processSymbol_uses_nvda_character_processing(self, mock_ui):
		"""Ensure _processSymbol delegates to NVDA's characterProcessing for locale-aware names."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _get_symbol_description

		# Clear the lru_cache so our mock takes effect
		_get_symbol_description.cache_clear()

		# Configure mock to return a locale-specific name
		cp_mock = sys.modules['characterProcessing']
		original_fn = cp_mock.processSpeechSymbol
		cp_mock.processSpeechSymbol = lambda locale, sym: {'.': 'dot', '!': 'bang'}.get(sym, sym)

		try:
			plugin = GlobalPlugin()
			self.assertEqual(plugin._processSymbol('.'), 'dot')
			self.assertEqual(plugin._processSymbol('!'), 'bang')
			self.assertEqual(plugin._processSymbol('a'), 'a')
		finally:
			cp_mock.processSpeechSymbol = original_fn
			_get_symbol_description.cache_clear()

	@patch('globalPlugins.terminalAccess.ui')
	def test_processSymbol_falls_back_to_unicode_name(self, mock_ui):
		"""When NVDA has no mapping, _processSymbol falls back to Unicode name."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _get_symbol_description

		_get_symbol_description.cache_clear()

		# Configure mock to return symbol unchanged (no mapping)
		cp_mock = sys.modules['characterProcessing']
		original_fn = cp_mock.processSpeechSymbol
		cp_mock.processSpeechSymbol = lambda locale, sym: sym

		try:
			plugin = GlobalPlugin()
			# Falls back to unicodedata.name: "!" → "exclamation mark"
			self.assertEqual(plugin._processSymbol('!'), 'exclamation mark')
		finally:
			cp_mock.processSpeechSymbol = original_fn
			_get_symbol_description.cache_clear()

	@patch('globalPlugins.terminalAccess.ui')
	def test_event_typedCharacter_speaks_symbol_name(self, mock_ui):
		"""Typed punctuation should speak symbol names via NVDA character processing."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _get_symbol_description

		_get_symbol_description.cache_clear()

		# Configure mock to return locale-aware name
		cp_mock = sys.modules['characterProcessing']
		original_fn = cp_mock.processSpeechSymbol
		cp_mock.processSpeechSymbol = lambda locale, sym: {'.': 'dot', '!': 'bang'}.get(sym, sym)

		try:
			plugin = GlobalPlugin()
			plugin.isTerminalApp = MagicMock(return_value=True)
			plugin._positionCalculator = MagicMock()

			plugin.event_typedCharacter(Mock(), lambda: None, '!')

			mock_ui.message.assert_called_with('bang')
		finally:
			cp_mock.processSpeechSymbol = original_fn
			_get_symbol_description.cache_clear()

	# -- _getEffective and profile override tests --

	def test_getEffective_returns_profile_override(self):
		"""_getEffective returns profile value when explicitly set."""
		from globalPlugins.terminalAccess import GlobalPlugin, ApplicationProfile

		plugin = GlobalPlugin()
		profile = ApplicationProfile('lazygit', 'Lazygit')
		profile.keyEcho = False
		profile.punctuationLevel = 3  # PUNCT_ALL
		profile.cursorTrackingMode = 3  # CT_WINDOW
		plugin._currentProfile = profile

		self.assertFalse(plugin._getEffective("keyEcho"))
		self.assertEqual(plugin._getEffective("punctuationLevel"), 3)
		self.assertEqual(plugin._getEffective("cursorTrackingMode"), 3)

	def test_getEffective_falls_back_to_global_when_none(self):
		"""_getEffective falls back to global config when profile attr is None."""
		from globalPlugins.terminalAccess import GlobalPlugin, ApplicationProfile

		plugin = GlobalPlugin()
		profile = ApplicationProfile('someapp', 'Some App')
		# All settings default to None on new profiles
		self.assertIsNone(profile.keyEcho)
		self.assertIsNone(profile.punctuationLevel)
		plugin._currentProfile = profile

		# Should return global values (from conftest defaults)
		self.assertTrue(plugin._getEffective("keyEcho"))
		self.assertEqual(plugin._getEffective("punctuationLevel"), 2)  # PUNCT_MOST

	def test_getEffective_falls_back_to_global_without_profile(self):
		"""_getEffective reads global config when no profile is active."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._currentProfile = None

		self.assertTrue(plugin._getEffective("keyEcho"))
		self.assertEqual(plugin._getEffective("cursorTrackingMode"), 1)  # CT_STANDARD

	def test_getEffective_profile_overrides_global(self):
		"""Profile value wins even when it differs from global config."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, ApplicationProfile

		plugin = GlobalPlugin()
		config_mock = sys.modules['config']
		original = config_mock.conf["terminalAccess"]["keyEcho"]
		config_mock.conf["terminalAccess"]["keyEcho"] = False

		try:
			profile = ApplicationProfile('myapp', 'My App')
			profile.keyEcho = True
			plugin._currentProfile = profile

			# Profile says True, global says False → True wins
			self.assertTrue(plugin._getEffective("keyEcho"))
		finally:
			config_mock.conf["terminalAccess"]["keyEcho"] = original

	def test_isKeyEchoActive_profile_disables(self):
		"""_isKeyEchoActive returns False when profile sets keyEcho=False."""
		from globalPlugins.terminalAccess import GlobalPlugin, ApplicationProfile

		plugin = GlobalPlugin()
		profile = ApplicationProfile('lazygit', 'Lazygit')
		profile.keyEcho = False
		plugin._currentProfile = profile

		self.assertFalse(plugin._isKeyEchoActive())

	def test_isKeyEchoActive_profile_quietMode_disables(self):
		"""_isKeyEchoActive returns False when profile sets quietMode=True."""
		from globalPlugins.terminalAccess import GlobalPlugin, ApplicationProfile

		plugin = GlobalPlugin()
		profile = ApplicationProfile('less', 'less')
		profile.quietMode = True
		plugin._currentProfile = profile

		self.assertFalse(plugin._isKeyEchoActive())

	def test_isKeyEchoActive_no_profile_uses_global(self):
		"""Without a profile, _isKeyEchoActive reads global config."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._currentProfile = None
		self.assertTrue(plugin._isKeyEchoActive())

	@patch('globalPlugins.terminalAccess.ui')
	def test_event_typedCharacter_suppressed_by_profile(self, mock_ui):
		"""Typing in a TUI app with keyEcho=False profile should produce no echo."""
		from globalPlugins.terminalAccess import GlobalPlugin, ApplicationProfile

		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._positionCalculator = MagicMock()

		profile = ApplicationProfile('lazygit', 'Lazygit')
		profile.keyEcho = False
		plugin._currentProfile = profile

		plugin.event_typedCharacter(Mock(), lambda: None, 'q')
		mock_ui.message.assert_not_called()

	def test_shouldProcessSymbol_uses_profile_punctuation(self):
		"""_shouldProcessSymbol uses profile punctuationLevel override."""
		from globalPlugins.terminalAccess import GlobalPlugin, ApplicationProfile, PUNCT_ALL, PUNCT_NONE

		plugin = GlobalPlugin()

		# Profile with PUNCT_ALL → every symbol should be processed
		profile = ApplicationProfile('git', 'Git')
		profile.punctuationLevel = PUNCT_ALL
		plugin._currentProfile = profile
		self.assertTrue(plugin._shouldProcessSymbol('!'))
		self.assertTrue(plugin._shouldProcessSymbol('.'))

		# Profile with PUNCT_NONE → no symbols processed
		profile.punctuationLevel = PUNCT_NONE
		# Reset cached level so it picks up the change
		plugin._cachedPunctLevel = -1
		self.assertFalse(plugin._shouldProcessSymbol('!'))
		self.assertFalse(plugin._shouldProcessSymbol('.'))

	def test_gestures_dont_propagate_to_globalCommands(self):
		"""Test that comma and period gestures don't call globalCommands."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()

		# Mock gesture
		mock_gesture = MagicMock()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._readReviewCharacter = MagicMock()

		# Mock globalCommands to ensure it's not called
		with patch('globalPlugins.terminalAccess.globalCommands') as mock_globalCommands:
			# Test comma gesture (current character)
			with patch('globalPlugins.terminalAccess.scriptHandler.getLastScriptRepeatCount', return_value=0):
				plugin.script_readCurrentChar(mock_gesture)

			# Test period gesture (next character)
			plugin.script_readNextChar(mock_gesture)

			# Verify globalCommands was never accessed for review functions
			mock_globalCommands.commands.script_review_currentCharacter.assert_not_called()
			mock_globalCommands.commands.script_review_nextCharacter.assert_not_called()


	# -- Per-gesture unbinding tests --

	def test_collectTerminalGestures_excludes_unbound(self):
		"""Excluded gestures are filtered from _terminalGestures."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES

		config_mock = sys.modules['config']
		config_mock.conf["terminalAccess"]["unboundGestures"] = "kb:NVDA+c,kb:NVDA+r"

		try:
			plugin = GlobalPlugin()
			gestures = plugin._collectTerminalGestures()
			self.assertNotIn("kb:NVDA+c", gestures)
			self.assertNotIn("kb:NVDA+r", gestures)
			# A gesture not in the exclusion list should still be present
			self.assertIn("kb:NVDA+u", gestures)
		finally:
			config_mock.conf["terminalAccess"]["unboundGestures"] = ""

	def test_collectTerminalGestures_always_bound_cannot_exclude(self):
		"""_ALWAYS_BOUND gestures survive even if in unboundGestures."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _ALWAYS_BOUND

		config_mock = sys.modules['config']
		config_mock.conf["terminalAccess"]["unboundGestures"] = "kb:NVDA+'"

		try:
			plugin = GlobalPlugin()
			gestures = plugin._collectTerminalGestures()
			self.assertIn("kb:NVDA+'", gestures)
		finally:
			config_mock.conf["terminalAccess"]["unboundGestures"] = ""

	def test_collectTerminalGestures_empty_config(self):
		"""Empty unboundGestures returns the full set."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES

		config_mock = sys.modules['config']
		config_mock.conf["terminalAccess"]["unboundGestures"] = ""

		plugin = GlobalPlugin()
		gestures = plugin._collectTerminalGestures()
		self.assertEqual(len(gestures), len(_DEFAULT_GESTURES))

	def test_reloadGestures_rebuilds_bindings(self):
		"""_reloadGestures rebuilds _terminalGestures from config."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES

		config_mock = sys.modules['config']
		config_mock.conf["terminalAccess"]["unboundGestures"] = ""

		plugin = GlobalPlugin()
		original_count = len(plugin._terminalGestures)
		self.assertEqual(original_count, len(_DEFAULT_GESTURES))

		# Exclude two gestures and reload
		config_mock.conf["terminalAccess"]["unboundGestures"] = "kb:NVDA+c,kb:NVDA+r"
		plugin._reloadGestures()

		self.assertEqual(len(plugin._terminalGestures), original_count - 2)
		self.assertNotIn("kb:NVDA+c", plugin._terminalGestures)
		self.assertNotIn("kb:NVDA+r", plugin._terminalGestures)

		# Restore and verify
		config_mock.conf["terminalAccess"]["unboundGestures"] = ""
		plugin._reloadGestures()
		self.assertEqual(len(plugin._terminalGestures), original_count)

	def test_gestureLabel_formatting(self):
		"""_gestureLabel formats gesture and script name correctly."""
		from globalPlugins.terminalAccess import _gestureLabel

		label = _gestureLabel("kb:NVDA+shift+c", "copyRectangularSelection")
		self.assertIn("NVDA", label)
		self.assertIn("Shift", label)
		self.assertIn("C", label)
		self.assertIn("\u2014", label)  # em dash
		self.assertIn("Copy", label)

	def test_gestureLabel_single_key(self):
		"""_gestureLabel handles single modifier+key correctly."""
		from globalPlugins.terminalAccess import _gestureLabel

		label = _gestureLabel("kb:NVDA+u", "readCurrentLine")
		self.assertEqual(label, "NVDA+U \u2014 Read Current Line")


if __name__ == '__main__':
	unittest.main()
