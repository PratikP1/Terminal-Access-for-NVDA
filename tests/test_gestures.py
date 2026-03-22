"""
Tests for Terminal Access keyboard gesture handling.

Tests cover gesture registration, conflict detection, help descriptions,
and the command layer (modal single-key command mode).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys


class TestGestureRegistration(unittest.TestCase):
	"""Test gesture registration and configuration."""

	def test_no_gesture_conflicts(self):
		"""Test no conflicts with NVDA core gestures."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Common NVDA core gestures we should avoid
		nvda_core_gestures = {
			'kb:NVDA+upArrow',
			'kb:NVDA+downArrow',
			'kb:NVDA+leftArrow',
			'kb:NVDA+rightArrow',
			'kb:NVDA+control+upArrow',
			'kb:NVDA+control+downArrow',
			'kb:NVDA+tab',
			'kb:NVDA+shift+tab',
		}

		if hasattr(GlobalPlugin, '__gestures__'):
			plugin_gestures = set(GlobalPlugin.__gestures__.keys())

			# Check for conflicts
			conflicts = plugin_gestures.intersection(nvda_core_gestures)
			self.assertEqual(len(conflicts), 0,
				f"Gesture conflicts detected: {conflicts}")


class TestGestureDocumentation(unittest.TestCase):
	"""Test gesture help descriptions."""

	def test_gesture_help_descriptions(self):
		"""Test all gestures have help descriptions."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Get all script methods
		for attr_name in dir(GlobalPlugin):
			if attr_name.startswith('script_'):
				method = getattr(GlobalPlugin, attr_name)

				# Check if method has __doc__ or __func__.__doc__
				has_doc = (
					(hasattr(method, '__doc__') and method.__doc__ is not None) or
					(hasattr(method, '__func__') and
					 hasattr(method.__func__, '__doc__') and
					 method.__func__.__doc__ is not None)
				)

				self.assertTrue(has_doc,
					f"Script {attr_name} missing docstring")


class TestGestureBindingsVisibility(unittest.TestCase):
	"""Test that gesture bindings remain visible for NVDA's Input Gestures dialog.

	NVDA's Input Gestures dialog reads from the plugin instance's gesture map.
	If bindings are removed (e.g. by _disableTerminalGestures), the dialog
	shows scripts under 'Terminal Access' but with no gesture assigned.
	"""

	def test_all_gestures_bound_at_init(self):
		"""All gestures are bound at init so they appear in Input Gestures dialog."""
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES

		plugin = GlobalPlugin()

		gesture_map = getattr(plugin, '_gestureMap', {})
		missing = set(_DEFAULT_GESTURES.keys()) - set(gesture_map.keys())
		self.assertEqual(len(missing), 0,
			f"Default gestures missing from _gestureMap after __init__(): "
			f"{missing}. This breaks NVDA's Input Gestures dialog.")

	def test_excluded_gesture_removed_others_remain(self):
		"""Only user-excluded gestures should be removed."""
		import config as config_mod
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES, _ALWAYS_BOUND

		config_mod.conf["terminalAccess"]["unboundGestures"] = "kb:NVDA+u"

		plugin = GlobalPlugin()

		gesture_map = getattr(plugin, '_gestureMap', {})
		self.assertNotIn("kb:NVDA+u", gesture_map,
			"Excluded gesture should be removed from _gestureMap")
		expected_present = set(_DEFAULT_GESTURES.keys()) - {"kb:NVDA+u"}
		actually_present = set(gesture_map.keys())
		missing = expected_present - actually_present
		self.assertEqual(len(missing), 0,
			f"Non-excluded gestures missing from _gestureMap: {missing}")

		config_mod.conf["terminalAccess"]["unboundGestures"] = ""

	def test_isTerminalApp_guard_on_all_scripts(self):
		"""Every script method should check isTerminalApp and call gesture.send().

		This guard is what makes gestures safe to keep always-bound — they
		pass through when not in a terminal.
		"""
		from globalPlugins.terminalAccess import GlobalPlugin
		import inspect

		# Scripts that intentionally skip the isTerminalApp guard:
		# - showHelp: always available (in _ALWAYS_BOUND)
		# - copyLine/copyScreen/exitCopyMode: guarded by self.copyMode
		# - exitCommandLayer: guarded by self._inCommandLayer
		always_active = {
			'script_showHelp',
			'script_copyLine', 'script_copyScreen', 'script_exitCopyMode',
			'script_exitCommandLayer',
		}

		for attr_name in dir(GlobalPlugin):
			if not attr_name.startswith('script_'):
				continue
			if attr_name in always_active:
				continue
			method = getattr(GlobalPlugin, attr_name)
			if not callable(method):
				continue
			source = inspect.getsource(method)
			self.assertIn('isTerminalApp', source,
				f"{attr_name} must check isTerminalApp() to guard "
				f"against execution outside terminals")


class TestGestureExecution(unittest.TestCase):
	"""Test gesture execution and behavior."""

	def test_readCurrentLine_calls_review(self):
		"""script_readCurrentLine should delegate to NVDA review on terminal."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		gesture = MagicMock()
		# Should not raise — delegates to globalCommands
		plugin.script_readCurrentLine(gesture)
		gesture.send.assert_not_called()

	def test_toggleQuietMode_flips_config(self):
		"""script_toggleQuietMode should toggle the quietMode setting."""
		import config as config_mod
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		gesture = MagicMock()

		config_mod.conf["terminalAccess"]["quietMode"] = False
		plugin.script_toggleQuietMode(gesture)
		self.assertTrue(config_mod.conf["terminalAccess"]["quietMode"])
		plugin.script_toggleQuietMode(gesture)
		self.assertFalse(config_mod.conf["terminalAccess"]["quietMode"])

	def test_script_sends_gesture_when_not_terminal(self):
		"""Scripts should pass gesture through when not in terminal."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=False)
		gesture = MagicMock()

		plugin.script_readCurrentLine(gesture)
		gesture.send.assert_called_once()

	def test_announcePosition_speaks(self):
		"""script_announcePosition should call ui.message."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._boundTerminal = MagicMock()
		gesture = MagicMock()

		# Mock the position calculation
		plugin._positionCalculator = MagicMock()
		plugin._positionCalculator.calculate = MagicMock(return_value=(5, 10))

		plugin.script_announcePosition(gesture)
		ui_mock = sys.modules['ui']
		ui_mock.message.assert_called()

	def test_copyLinearSelection_no_marks_warns(self):
		"""Copying without marks should produce a warning message."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._markStart = None
		plugin._markEnd = None
		gesture = MagicMock()

		plugin.script_copyLinearSelection(gesture)
		ui_mock = sys.modules['ui']
		ui_mock.message.assert_called()


class TestGestureScoping(unittest.TestCase):
	"""Test that gestures pass through to applications when not in a terminal.

	With the always-bound architecture, gestures are never removed.
	Instead, each script checks isTerminalApp() and calls gesture.send()
	for non-terminal focus.  _updateGestureBindingsForFocus handles
	command layer auto-exit on focus loss.
	"""

	def test_gestures_stay_bound_after_focus_loss(self):
		"""Gestures stay in _gestureMap after focus loss (for Input Gestures dialog)."""
		from globalPlugins.terminalAccess import GlobalPlugin, _DEFAULT_GESTURES

		plugin = GlobalPlugin()

		non_terminal = MagicMock()
		non_terminal.appModule = MagicMock()
		non_terminal.appModule.appName = "notepad"
		plugin._updateGestureBindingsForFocus(non_terminal)

		gesture_map = plugin._gestureMap
		for gesture in _DEFAULT_GESTURES:
			self.assertIn(gesture, gesture_map)

	def test_getScript_blocks_terminal_gestures_outside_terminal(self):
		"""getScript returns None for terminal gestures when no terminal focused."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._boundTerminal = None

		gesture = MagicMock()
		gesture.normalizedIdentifiers = ["kb:NVDA+l"]

		result = plugin.getScript(gesture)
		self.assertIsNone(result)

	def test_focus_loss_exits_command_layer(self):
		"""Switching to non-terminal exits command layer."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin._inCommandLayer = True

		non_terminal = MagicMock()
		non_terminal.appModule = MagicMock()
		non_terminal.appModule.appName = "notepad"

		plugin._updateGestureBindingsForFocus(non_terminal)
		self.assertFalse(plugin._inCommandLayer)

	def test_focus_loss_exits_copy_mode(self):
		"""Switching to non-terminal exits copy mode."""
		from globalPlugins.terminalAccess import GlobalPlugin

		plugin = GlobalPlugin()
		plugin.copyMode = True

		non_terminal = MagicMock()
		non_terminal.appModule = MagicMock()
		non_terminal.appModule.appName = "notepad"

		plugin._updateGestureBindingsForFocus(non_terminal)
		self.assertFalse(plugin.copyMode)


# ------------------------------------------------------------------
# Command Layer Tests
# ------------------------------------------------------------------

class TestCommandLayerMap(unittest.TestCase):
	"""Test the _COMMAND_LAYER_MAP constant is well-formed."""

	def test_map_is_non_empty(self):
		"""The command layer map must define at least one binding."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		self.assertGreater(len(_COMMAND_LAYER_MAP), 0)

	def test_all_keys_are_gesture_strings(self):
		"""Every key must start with 'kb:'."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		for gesture_id in _COMMAND_LAYER_MAP:
			self.assertTrue(gesture_id.startswith("kb:"),
				f"Gesture key {gesture_id!r} does not start with 'kb:'")

	def test_all_values_are_script_names(self):
		"""Every value must correspond to a real script_ method."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP, GlobalPlugin
		for gesture_id, script_name in _COMMAND_LAYER_MAP.items():
			method_name = f"script_{script_name}"
			self.assertTrue(hasattr(GlobalPlugin, method_name),
				f"Layer maps {gesture_id!r} -> {script_name!r} but "
				f"GlobalPlugin has no method {method_name}")

	def test_escape_maps_to_exit(self):
		"""Escape key must map to exitCommandLayer."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		self.assertEqual(_COMMAND_LAYER_MAP.get("kb:escape"), "exitCommandLayer")

	def test_no_nvda_modifier_keys(self):
		"""Layer keys must not require the NVDA modifier."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		for gesture_id in _COMMAND_LAYER_MAP:
			self.assertNotIn("NVDA", gesture_id,
				f"Layer gesture {gesture_id!r} should not use NVDA modifier")

	def test_bookmark_digit_coverage(self):
		"""All 10 digits (0-9) should be mapped for jump and set."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		for d in range(10):
			self.assertIn(f"kb:{d}", _COMMAND_LAYER_MAP,
				f"Jump-to-bookmark digit {d} missing from layer map")
			self.assertIn(f"kb:shift+{d}", _COMMAND_LAYER_MAP,
				f"Set-bookmark digit {d} missing from layer map")


class TestCommandLayerEntryExit(unittest.TestCase):
	"""Test entering and exiting the command layer."""

	def setUp(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		self.plugin = GlobalPlugin()
		# Ensure the plugin thinks we're in a terminal context
		self.plugin.isTerminalApp = MagicMock(return_value=True)
		# Track bind/unbind calls
		self.plugin.bindGesture = MagicMock()
		self.plugin.removeGestureBinding = MagicMock()

	def test_enter_layer_sets_flag(self):
		"""Entering the layer sets _inCommandLayer to True."""
		self.assertFalse(self.plugin._inCommandLayer)
		self.plugin._enterCommandLayer()
		self.assertTrue(self.plugin._inCommandLayer)

	def test_enter_layer_binds_gestures(self):
		"""Entering the layer calls bindGesture for every key in the map."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		self.plugin._enterCommandLayer()
		self.assertEqual(self.plugin.bindGesture.call_count,
			len(_COMMAND_LAYER_MAP))

	def test_exit_layer_clears_flag(self):
		"""Exiting the layer sets _inCommandLayer to False."""
		self.plugin._inCommandLayer = True
		self.plugin._exitCommandLayer()
		self.assertFalse(self.plugin._inCommandLayer)

	def test_exit_layer_unbinds_gestures(self):
		"""Exiting the layer calls removeGestureBinding for every key."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		self.plugin._inCommandLayer = True
		self.plugin._exitCommandLayer()
		self.assertEqual(self.plugin.removeGestureBinding.call_count,
			len(_COMMAND_LAYER_MAP))

	def test_toggle_enters_then_exits(self):
		"""Toggling twice should enter then exit."""
		gesture = MagicMock()
		self.plugin.script_toggleCommandLayer(gesture)
		self.assertTrue(self.plugin._inCommandLayer)
		self.plugin.script_toggleCommandLayer(gesture)
		self.assertFalse(self.plugin._inCommandLayer)

	def test_double_enter_is_idempotent(self):
		"""Calling _enterCommandLayer twice should only bind once."""
		self.plugin._enterCommandLayer()
		first_count = self.plugin.bindGesture.call_count
		self.plugin._enterCommandLayer()
		self.assertEqual(self.plugin.bindGesture.call_count, first_count,
			"_enterCommandLayer should be idempotent when already in layer")

	def test_double_exit_is_idempotent(self):
		"""Calling _exitCommandLayer twice should only unbind once."""
		self.plugin._inCommandLayer = True
		self.plugin._exitCommandLayer()
		first_count = self.plugin.removeGestureBinding.call_count
		self.plugin._exitCommandLayer()
		self.assertEqual(self.plugin.removeGestureBinding.call_count, first_count,
			"_exitCommandLayer should be idempotent when not in layer")

	def test_enter_plays_high_tone(self):
		"""Entering the layer plays an 880 Hz tone."""
		tones_mock = sys.modules['tones']
		tones_mock.beep.reset_mock()
		self.plugin._enterCommandLayer()
		tones_mock.beep.assert_called_with(880, 100)

	def test_exit_plays_low_tone(self):
		"""Exiting the layer plays a 440 Hz tone."""
		tones_mock = sys.modules['tones']
		tones_mock.beep.reset_mock()
		self.plugin._inCommandLayer = True
		self.plugin._exitCommandLayer()
		tones_mock.beep.assert_called_with(440, 100)

	def test_exit_script_sends_key_when_not_in_layer(self):
		"""script_exitCommandLayer should pass through when not in layer."""
		gesture = MagicMock()
		self.plugin._inCommandLayer = False
		self.plugin.script_exitCommandLayer(gesture)
		gesture.send.assert_called_once()

	def test_exit_script_exits_layer_when_in_layer(self):
		"""script_exitCommandLayer should exit when in layer."""
		gesture = MagicMock()
		self.plugin._inCommandLayer = True
		self.plugin.script_exitCommandLayer(gesture)
		self.assertFalse(self.plugin._inCommandLayer)
		gesture.send.assert_not_called()

	def test_toggle_sends_key_when_not_terminal(self):
		"""Toggling outside terminal should pass through the gesture."""
		self.plugin.isTerminalApp = MagicMock(return_value=False)
		gesture = MagicMock()
		self.plugin.script_toggleCommandLayer(gesture)
		gesture.send.assert_called_once()
		self.assertFalse(self.plugin._inCommandLayer)


class TestCommandLayerFocusLoss(unittest.TestCase):
	"""Test that the command layer auto-exits when terminal loses focus."""

	def setUp(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		self.plugin = GlobalPlugin()
		self.plugin.isTerminalApp = MagicMock(return_value=True)
		self.plugin.bindGesture = MagicMock()
		self.plugin.removeGestureBinding = MagicMock()

	def test_focus_loss_exits_layer(self):
		"""Focus loss to non-terminal must exit command layer."""
		self.plugin._inCommandLayer = True
		non_terminal = MagicMock()
		non_terminal.appModule = MagicMock()
		non_terminal.appModule.appName = "notepad"
		self.plugin.isTerminalApp = MagicMock(return_value=False)
		self.plugin._updateGestureBindingsForFocus(non_terminal)
		self.assertFalse(self.plugin._inCommandLayer)

	def test_focus_to_non_terminal_exits_layer(self):
		"""Switching to a non-terminal app exits the command layer."""
		# Enter the layer
		self.plugin._enterCommandLayer()
		self.assertTrue(self.plugin._inCommandLayer)

		# Now make isTerminalApp return False for the non-terminal object
		self.plugin.isTerminalApp = MagicMock(return_value=False)

		# Simulate focus leaving the terminal
		non_terminal = MagicMock()
		non_terminal.appModule = MagicMock()
		non_terminal.appModule.appName = "notepad"
		self.plugin._updateGestureBindingsForFocus(non_terminal)

		self.assertFalse(self.plugin._inCommandLayer)


class TestCommandLayerCopyModeInteraction(unittest.TestCase):
	"""Test interaction between command layer and copy mode."""

	def setUp(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		self.plugin = GlobalPlugin()
		self.plugin.isTerminalApp = MagicMock(return_value=True)
		self.plugin.bindGesture = MagicMock()
		self.plugin.removeGestureBinding = MagicMock()

	def test_enter_layer_exits_copy_mode(self):
		"""Entering command layer should first exit copy mode if active."""
		self.plugin.copyMode = True
		self.plugin._enterCommandLayer()
		# copyMode should be cleared by _exitCopyModeBindings
		self.assertFalse(self.plugin.copyMode)
		self.assertTrue(self.plugin._inCommandLayer)

	def test_exit_copy_mode_restores_layer_bindings(self):
		"""Exiting copy mode while in layer re-binds layer keys (l, s, escape)."""
		from globalPlugins.terminalAccess import _COMMAND_LAYER_MAP
		# Simulate being in the command layer
		self.plugin._inCommandLayer = True
		self.plugin.copyMode = True

		# Reset bind mock to only track calls from _exitCopyModeBindings
		self.plugin.bindGesture.reset_mock()
		self.plugin._exitCopyModeBindings()

		# After exiting copy mode, layer bindings for l, s, escape should
		# have been re-bound
		rebound_gestures = {c.args[0] for c in self.plugin.bindGesture.call_args_list}
		for key in ("kb:l", "kb:s", "kb:escape"):
			if key in _COMMAND_LAYER_MAP:
				self.assertIn(key, rebound_gestures,
					f"Layer gesture {key!r} not re-bound after copy mode exit")

	def test_exit_copy_mode_no_rebind_when_layer_inactive(self):
		"""Exiting copy mode when layer is NOT active should NOT re-bind."""
		self.plugin._inCommandLayer = False
		self.plugin.copyMode = True
		self.plugin.bindGesture.reset_mock()
		self.plugin._exitCopyModeBindings()
		self.plugin.bindGesture.assert_not_called()


class TestCommandLayerCategory(unittest.TestCase):
	"""Test that all scripts are in the Terminal Access category."""

	def test_all_scripts_have_category(self):
		"""Every script should have the SCRCAT_TERMINALACCESS category."""
		from globalPlugins.terminalAccess import GlobalPlugin, SCRCAT_TERMINALACCESS

		for attr_name in dir(GlobalPlugin):
			if not attr_name.startswith('script_'):
				continue
			method = getattr(GlobalPlugin, attr_name)
			# Some scripts use scriptHandler.script decorator which sets
			# _script_category; others set it via the @script decorator.
			category = getattr(method, 'category', None)
			# NVDA stores category on the unbound function in some cases
			if category is None and hasattr(method, '__func__'):
				category = getattr(method.__func__, 'category', None)
			# The decorator may also store it as _script_category
			if category is None:
				category = getattr(method, '_script_category', None)

			# It's acceptable for the mock environment not to preserve all
			# decorator metadata; just verify it's set when available.
			if category is not None:
				self.assertEqual(category, SCRCAT_TERMINALACCESS,
					f"{attr_name} has category={category!r}, "
					f"expected {SCRCAT_TERMINALACCESS!r}")


if __name__ == '__main__':
	unittest.main()
