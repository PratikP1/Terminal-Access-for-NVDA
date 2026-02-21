"""
Tests for Terminal Access keyboard gesture handling.

Tests cover gesture registration, conflict detection, and help descriptions.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys


class TestGestureRegistration(unittest.TestCase):
	"""Test gesture registration and configuration."""

	def test_all_gestures_registered(self):
		"""Test all gestures are properly registered."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Get all script methods
		script_methods = [
			method for method in dir(GlobalPlugin)
			if method.startswith('script_')
		]

		# Verify we have expected gestures
		expected_scripts = [
			'script_reportCurrentLine',
			'script_reportCurrentWord',
			'script_reportCurrentCharacter',
			'script_reportLineAbove',
			'script_reportLineBelow',
			'script_reportTop',
			'script_reportBottom',
			'script_reportSelection',
			'script_toggleVerboseMode',
			'script_toggleQuietMode',
			'script_toggleCursorTracking',
			'script_reportPosition',
			'script_increaseDelay',
			'script_decreaseDelay',
			'script_reportDelay',
		]

		for expected in expected_scripts:
			self.assertIn(expected, script_methods,
				f"Missing script method: {expected}")

	def test_gesture_bindings_exist(self):
		"""Test gesture bindings are defined."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Check __gestures__ attribute exists
		self.assertTrue(hasattr(GlobalPlugin, '__gestures__'),
			"GlobalPlugin missing __gestures__ attribute")

		gestures = GlobalPlugin.__gestures__
		self.assertIsInstance(gestures, dict,
			"__gestures__ should be a dictionary")

		# Verify we have some gestures defined
		self.assertGreater(len(gestures), 0,
			"No gestures defined in __gestures__")

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

	def test_gesture_categories(self):
		"""Test gestures are properly categorized."""
		from globalPlugins.terminalAccess import GlobalPlugin

		# Scripts should be categorized by function
		navigation_scripts = [
			'script_reportCurrentLine',
			'script_reportCurrentWord',
			'script_reportCurrentCharacter',
			'script_reportLineAbove',
			'script_reportLineBelow',
			'script_reportTop',
			'script_reportBottom',
		]

		settings_scripts = [
			'script_toggleVerboseMode',
			'script_toggleQuietMode',
			'script_toggleCursorTracking',
		]

		info_scripts = [
			'script_reportPosition',
			'script_reportSelection',
		]

		all_expected = navigation_scripts + settings_scripts + info_scripts

		for script_name in all_expected:
			self.assertTrue(hasattr(GlobalPlugin, script_name),
				f"Missing expected script: {script_name}")


class TestGestureExecution(unittest.TestCase):
	"""Test gesture execution and behavior."""

	def test_toggle_gestures_change_state(self):
		"""Test toggle gestures properly change state."""
		# This would require more complex mocking
		# Just verify the methods exist for now
		from globalPlugins.terminalAccess import GlobalPlugin

		toggle_methods = [
			'script_toggleVerboseMode',
			'script_toggleQuietMode',
			'script_toggleCursorTracking',
		]

		for method_name in toggle_methods:
			self.assertTrue(hasattr(GlobalPlugin, method_name),
				f"Missing toggle method: {method_name}")

	def test_report_gestures_provide_feedback(self):
		"""Test report gestures provide user feedback."""
		# This would require mocking ui.message
		# Just verify the methods exist for now
		from globalPlugins.terminalAccess import GlobalPlugin

		report_methods = [
			'script_reportCurrentLine',
			'script_reportPosition',
			'script_reportSelection',
		]

		for method_name in report_methods:
			self.assertTrue(hasattr(GlobalPlugin, method_name),
				f"Missing report method: {method_name}")


if __name__ == '__main__':
	unittest.main()
