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
			plugin._boundTerminal = Mock()
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

	def test_excluded_gestures_removed_from_map(self):
		"""Excluded gestures are removed from _gestureMap."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES

		config_mock = sys.modules['config']
		config_mock.conf["terminalAccess"]["unboundGestures"] = "kb:NVDA+c,kb:NVDA+r"

		try:
			plugin = GlobalPlugin()
			self.assertNotIn("kb:NVDA+c", plugin._gestureMap)
			self.assertNotIn("kb:NVDA+r", plugin._gestureMap)
			# A gesture not in the exclusion list should still be present
			self.assertIn("kb:NVDA+u", plugin._gestureMap)
		finally:
			config_mock.conf["terminalAccess"]["unboundGestures"] = ""

	def test_always_bound_cannot_exclude(self):
		"""_ALWAYS_BOUND gestures survive even if in unboundGestures."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _ALWAYS_BOUND

		config_mock = sys.modules['config']
		config_mock.conf["terminalAccess"]["unboundGestures"] = "kb:NVDA+'"

		try:
			plugin = GlobalPlugin()
			self.assertIn("kb:NVDA+'", plugin._gestureMap)
		finally:
			config_mock.conf["terminalAccess"]["unboundGestures"] = ""

	def test_all_gestures_bound_at_init(self):
		"""All gestures are bound at init (visible in Input Gestures dialog)."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES

		config_mock = sys.modules['config']
		config_mock.conf["terminalAccess"]["unboundGestures"] = ""

		plugin = GlobalPlugin()
		for gesture in _DEFAULT_GESTURES:
			self.assertIn(gesture, plugin._gestureMap)

	def test_getScript_returns_none_outside_terminal(self):
		"""getScript returns None for terminal gestures when no terminal is focused."""
		from globalPlugins.terminalAccess import GlobalPlugin
		from unittest.mock import MagicMock

		plugin = GlobalPlugin()
		plugin._boundTerminal = None  # No terminal focused

		gesture = MagicMock()
		gesture.normalizedIdentifiers = ["kb:NVDA+u"]

		result = plugin.getScript(gesture)
		self.assertIsNone(result)

	def test_getScript_returns_callable_script_in_terminal(self):
		"""getScript returns a callable script when a terminal is focused."""
		from globalPlugins.terminalAccess import GlobalPlugin
		from unittest.mock import MagicMock, Mock

		plugin = GlobalPlugin()
		plugin._boundTerminal = Mock()  # Terminal is focused

		gesture = MagicMock()
		gesture.normalizedIdentifiers = ["kb:NVDA+u"]

		result = plugin.getScript(gesture)
		self.assertIsNotNone(result, "getScript should return a script in terminal")
		self.assertTrue(callable(result), "getScript result should be callable")

	def test_getScript_help_works_outside_terminal(self):
		"""Help gesture returns a callable script even outside terminals."""
		from globalPlugins.terminalAccess import GlobalPlugin
		from unittest.mock import MagicMock

		plugin = GlobalPlugin()
		plugin._boundTerminal = None  # No terminal focused

		gesture = MagicMock()
		gesture.normalizedIdentifiers = ["kb:NVDA+shift+f1"]

		result = plugin.getScript(gesture)
		self.assertIsNotNone(result, "Help should work outside terminals")
		self.assertTrue(callable(result))

	def test_getScript_command_layer_works_outside_terminal(self):
		"""Command layer toggle returns a callable script even outside terminals."""
		from globalPlugins.terminalAccess import GlobalPlugin
		from unittest.mock import MagicMock

		plugin = GlobalPlugin()
		plugin._boundTerminal = None  # No terminal focused

		gesture = MagicMock()
		gesture.normalizedIdentifiers = ["kb:NVDA+'"]

		result = plugin.getScript(gesture)
		self.assertIsNotNone(result, "Command layer toggle should work outside terminals")
		self.assertTrue(callable(result))

	def test_getScript_blocks_multiple_terminal_gestures_outside(self):
		"""All terminal-specific gestures return None outside terminals."""
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES, _ALWAYS_BOUND
		from unittest.mock import MagicMock

		plugin = GlobalPlugin()
		plugin._boundTerminal = None  # No terminal focused

		terminal_gestures = [g for g in _DEFAULT_GESTURES if g not in _ALWAYS_BOUND]
		for gesture_id in terminal_gestures[:10]:
			gesture = MagicMock()
			gesture.normalizedIdentifiers = [gesture_id]
			result = plugin.getScript(gesture)
			self.assertIsNone(result,
				f"{gesture_id} should return None outside terminal")

	def test_reloadGestures_applies_exclusions(self):
		"""_reloadGestures re-binds all defaults then re-applies exclusions."""
		import sys
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES

		config_mock = sys.modules['config']
		config_mock.conf["terminalAccess"]["unboundGestures"] = ""

		plugin = GlobalPlugin()
		original_count = len(plugin._gestureMap)

		# Exclude two gestures and reload
		config_mock.conf["terminalAccess"]["unboundGestures"] = "kb:NVDA+c,kb:NVDA+r"
		plugin._reloadGestures()

		self.assertNotIn("kb:NVDA+c", plugin._gestureMap)
		self.assertNotIn("kb:NVDA+r", plugin._gestureMap)

		# Restore and verify all come back
		config_mock.conf["terminalAccess"]["unboundGestures"] = ""
		plugin._reloadGestures()
		self.assertEqual(len(plugin._gestureMap), original_count)

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


	# -- Gesture conflict avoidance tests --

	def test_punctuation_gestures_use_minus_equals(self):
		"""Punctuation gestures use minus/equals to avoid NVDA+[/] conflicts."""
		from globalPlugins.terminalAccess import _DEFAULT_GESTURES, _COMMAND_LAYER_MAP

		# Direct gestures
		self.assertIn("kb:NVDA+-", _DEFAULT_GESTURES)
		self.assertIn("kb:NVDA+=", _DEFAULT_GESTURES)
		self.assertNotIn("kb:NVDA+[", _DEFAULT_GESTURES)
		self.assertNotIn("kb:NVDA+]", _DEFAULT_GESTURES)

		# Command layer
		self.assertIn("kb:-", _COMMAND_LAYER_MAP)
		self.assertIn("kb:=", _COMMAND_LAYER_MAP)
		self.assertNotIn("kb:[", _COMMAND_LAYER_MAP)
		self.assertNotIn("kb:]", _COMMAND_LAYER_MAP)

	def test_copy_gesture_uses_nvda_c(self):
		"""Copy gesture uses NVDA+C (conflict managed via getScript and settings)."""
		from globalPlugins.terminalAccess import _DEFAULT_GESTURES, _CONFLICTING_GESTURES

		self.assertIn("kb:NVDA+c", _DEFAULT_GESTURES)
		self.assertEqual(_DEFAULT_GESTURES["kb:NVDA+c"], "copyLinearSelection")
		self.assertIn("kb:NVDA+c", _CONFLICTING_GESTURES)

	def test_conflicting_gestures_subset_of_defaults(self):
		"""Every conflicting gesture must exist in _DEFAULT_GESTURES."""
		from globalPlugins.terminalAccess import _DEFAULT_GESTURES, _CONFLICTING_GESTURES

		for gesture in _CONFLICTING_GESTURES:
			self.assertIn(gesture, _DEFAULT_GESTURES,
				f"Conflicting gesture {gesture} not found in _DEFAULT_GESTURES")

	def test_conflicting_gestures_not_in_always_bound(self):
		"""Conflicting gestures must not overlap with _ALWAYS_BOUND."""
		from globalPlugins.terminalAccess import _CONFLICTING_GESTURES, _ALWAYS_BOUND

		overlap = _CONFLICTING_GESTURES & _ALWAYS_BOUND
		self.assertEqual(len(overlap), 0,
			f"Gestures cannot be both conflicting and always-bound: {overlap}")

	def test_gesture_label_from_runtime_matches(self):
		"""gesture_label imported from _runtime produces correct output."""
		from lib._runtime import gesture_label

		result = gesture_label("kb:NVDA+shift+c", "copyRectangularSelection")
		self.assertIn("NVDA", result)
		self.assertIn("Shift", result)
		self.assertIn("C", result)
		self.assertIn("Copy", result)

		result2 = gesture_label("kb:NVDA+u", "readCurrentLine")
		self.assertEqual(result2, "NVDA+U \u2014 Read Current Line")

	def test_gesture_label_imported_identically_in_both_modules(self):
		"""Both terminalAccess and settings_panel use the same gesture_label."""
		from globalPlugins.terminalAccess import _gestureLabel as ta_label
		from lib.settings_panel import _gestureLabel as sp_label

		self.assertIs(ta_label, sp_label,
			"Both modules should import the same function from _runtime")


if __name__ == '__main__':
	unittest.main()
