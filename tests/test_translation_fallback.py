"""
Test translation fallback functionality.

This test verifies that the plugin initializes correctly even when
addonHandler.initTranslation() fails.
"""
import sys
import importlib
from unittest.mock import patch, MagicMock


def test_translation_fallback_when_init_fails():
	"""Test that translation fallback is defined when initTranslation fails."""
	# Remove the module if it was already imported
	if 'globalPlugins.terminalAccess' in sys.modules:
		del sys.modules['globalPlugins.terminalAccess']

	# Mock addonHandler to make initTranslation fail
	addon_handler_mock = MagicMock()
	addon_handler_mock.initTranslation.side_effect = ImportError("Simulating failure")

	with patch.dict('sys.modules', {'addonHandler': addon_handler_mock}):
		# Import the module - this should not raise NameError
		from globalPlugins import terminalAccess

		# Verify SCRCAT_TERMINALACCESS was set
		assert hasattr(terminalAccess, 'SCRCAT_TERMINALACCESS')
		assert terminalAccess.SCRCAT_TERMINALACCESS == "Terminal Access"


def test_translation_fallback_function():
	"""Test that the fallback translation function works correctly."""
	# Remove the module if it was already imported
	if 'globalPlugins.terminalAccess' in sys.modules:
		del sys.modules['globalPlugins.terminalAccess']

	# Mock addonHandler to make initTranslation fail
	addon_handler_mock = MagicMock()
	addon_handler_mock.initTranslation.side_effect = ImportError("Simulating failure")

	with patch.dict('sys.modules', {'addonHandler': addon_handler_mock}):
		# Import the module
		from globalPlugins import terminalAccess

		# The fallback function should be defined in builtins
		import builtins
		assert hasattr(builtins, '_')

		# The fallback function should return text as-is
		assert _("test string") == "test string"


def test_plugin_initialization_with_translation_failure():
	"""Test that GlobalPlugin can be instantiated when translation initialization fails."""
	# Remove the module if it was already imported
	if 'globalPlugins.terminalAccess' in sys.modules:
		del sys.modules['globalPlugins.terminalAccess']

	# Mock addonHandler to make initTranslation fail
	addon_handler_mock = MagicMock()
	addon_handler_mock.initTranslation.side_effect = ImportError("Simulating failure")

	with patch.dict('sys.modules', {'addonHandler': addon_handler_mock}):
		# Import the module
		from globalPlugins import terminalAccess

		# Attempt to instantiate GlobalPlugin - should not raise NameError
		try:
			plugin = terminalAccess.GlobalPlugin()
			assert plugin is not None
			# Clean up
			plugin.terminate()
		except NameError as e:
			# This should not happen with the fix
			raise AssertionError(f"NameError should not occur with fallback: {e}")
