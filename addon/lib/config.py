# Terminal Access configuration management.
# Extracted from terminalAccess.py for modularization.

import config as _config_module
from typing import Any

def _get_config():
	"""Get the config module, respecting test mocks.

	During testing the conftest may replace sys.modules['config'] after
	lib/config.py has already been imported.  Fetching through sys.modules
	at call time ensures we always use the current (possibly re-mocked)
	instance.
	"""
	import sys
	return sys.modules.get('config', _config_module)

class _ConfigProxy:
	"""Proxy that delegates attribute access to the current config module."""
	@property
	def conf(self):
		return _get_config().conf

config = _ConfigProxy()

# Cursor tracking mode constants
CT_OFF = 0
CT_STANDARD = 1
# DEPRECATED: Scheduled for removal in v2.0
CT_HIGHLIGHT = 2
CT_WINDOW = 3

# Human-readable cursor tracking mode names
CURSOR_MODE_NAMES = {
	CT_OFF: "Cursor tracking: Off",
	CT_STANDARD: "Cursor tracking: Standard",
	CT_HIGHLIGHT: "Cursor tracking: Highlight (deprecated)",
	CT_WINDOW: "Cursor tracking: Window",
}

# Punctuation level constants and sets
PUNCT_NONE = 0
PUNCT_SOME = 1
PUNCT_MOST = 2
PUNCT_ALL = 3

# Punctuation character sets for each level
PUNCTUATION_SETS = {
	PUNCT_NONE: set(),  # No punctuation
	PUNCT_SOME: set('.,?!;:'),  # Basic punctuation
	PUNCT_MOST: set('.,?!;:@#$%^&*()_+=[]{}\\|<>/'),  # Most punctuation
	PUNCT_ALL: None  # All punctuation (process everything)
}

# Resource limits for security and stability
MAX_SELECTION_ROWS = 10000  # Maximum rows for selection operations
MAX_SELECTION_COLS = 1000   # Maximum columns for selection operations
MAX_WINDOW_DIMENSION = 10000  # Maximum window boundary value
MAX_REPEATED_SYMBOLS_LENGTH = 50  # Maximum length for repeated symbols string

# Configuration spec for Terminal Access settings
confspec = {
	"cursorTracking": "boolean(default=True)",
	"cursorTrackingMode": "integer(default=1, min=0, max=3)",  # 0=Off, 1=Standard, 2=Highlight, 3=Window
	"keyEcho": "boolean(default=True)",
	"linePause": "boolean(default=True)",
	"processSymbols": "boolean(default=False)",  # Deprecated — kept for migration from pre-v1.0.10 configs
	"punctuationLevel": "integer(default=2, min=0, max=3)",  # 0=None, 1=Some, 2=Most, 3=All
	"repeatedSymbols": "boolean(default=False)",
	"repeatedSymbolsValues": "string(default='-_=!')",
	"cursorDelay": "integer(default=20, min=0, max=1000)",
	"quietMode": "boolean(default=False)",
	"verboseMode": "boolean(default=False)",  # Phase 6: Verbose feedback with context
	"announceIndentation": "boolean(default=False)",  # Announce indentation when reading lines
	"indentationOnLineRead": "boolean(default=False)",  # Automatically announce indentation on line navigation
	"windowTop": "integer(default=0, min=0)",
	"windowBottom": "integer(default=0, min=0)",
	"windowLeft": "integer(default=0, min=0)",
	"windowRight": "integer(default=0, min=0)",
	"windowEnabled": "boolean(default=False)",
	"defaultProfile": "string(default='')",  # Default profile to use when no app profile is detected
	"unboundGestures": "string(default='')",  # Comma-separated gestures excluded from direct binding
	"errorAudioCues": "boolean(default=True)",  # Play tones on error/warning lines during navigation
	"errorAudioCuesInQuietMode": "boolean(default=False)",  # Play error/warning tones even in quiet mode (on caret events)
	"outputActivityTones": "boolean(default=False)",  # Play ascending two-tone when new output appears on screen
	"outputActivityDebounce": "integer(default=1000, min=100, max=10000)",  # Milliseconds between activity tone repeats
	"verbosityLevel": "integer(default=1, min=0, max=2)",  # 0=Quiet, 1=Normal, 2=Verbose
	"urlOpenWarning": "boolean(default=True)",  # Show confirmation dialog before opening URLs from terminal output
	"summarizationEnabled": "boolean(default=False)",  # Enable offline extractive summarization of terminal output (opt-in)
}


# Input validation helper functions for security hardening
def _validateInteger(value: Any, minValue: int, maxValue: int, default: int, fieldName: str) -> int:
	"""
	Validate and sanitize an integer configuration value.

	Args:
		value: The value to validate
		minValue: Minimum allowed value
		maxValue: Maximum allowed value
		default: Default value if validation fails
		fieldName: Name of the field for logging

	Returns:
		int: Validated value or default if invalid
	"""
	try:
		intValue = int(value)
		if minValue <= intValue <= maxValue:
			return intValue
		else:
			import logHandler
			logHandler.log.warning(
				f"Terminal Access: {fieldName} value {intValue} out of range [{minValue}, {maxValue}], using default {default}"
			)
			return default
	except (ValueError, TypeError):
		import logHandler
		logHandler.log.warning(
			f"Terminal Access: Invalid {fieldName} value {value}, using default {default}"
		)
		return default


def _validateString(value: Any, maxLength: int, default: str, fieldName: str) -> str:
	"""
	Validate and sanitize a string configuration value.

	Args:
		value: The value to validate
		maxLength: Maximum allowed length
		default: Default value if validation fails
		fieldName: Name of the field for logging

	Returns:
		str: Validated value or default if invalid
	"""
	# Check for None or non-string types
	if value is None or not isinstance(value, str):
		import logHandler
		logHandler.log.warning(
			f"Terminal Access: Invalid {fieldName} value (got {type(value).__name__}), using default"
		)
		return default

	try:
		if len(value) <= maxLength:
			return value
		else:
			import logHandler
			logHandler.log.warning(
				f"Terminal Access: {fieldName} exceeds max length {maxLength}, truncating"
			)
			return value[:maxLength]
	except (ValueError, TypeError):
		import logHandler
		logHandler.log.warning(
			f"Terminal Access: Invalid {fieldName} value, using default"
		)
		return default


def _validateSelectionSize(startRow: int, endRow: int, startCol: int, endCol: int) -> tuple[bool, str | None]:
	"""
	Validate selection size against resource limits.

	Args:
		startRow: Starting row (1-based)
		endRow: Ending row (1-based)
		startCol: Starting column (1-based)
		endCol: Ending column (1-based)

	Returns:
		tuple: (isValid, errorMessage) where isValid is bool and errorMessage is str or None
	"""
	rowCount = abs(endRow - startRow) + 1
	colCount = abs(endCol - startCol) + 1

	if rowCount > MAX_SELECTION_ROWS:
		try:
			msg = _("Selection too large: {rows} rows exceeds maximum of {max}").format(
				rows=rowCount, max=MAX_SELECTION_ROWS
			)
		except NameError:
			msg = f"Selection too large: {rowCount} rows exceeds maximum of {MAX_SELECTION_ROWS}"
		return (False, msg)

	if colCount > MAX_SELECTION_COLS:
		try:
			msg = _("Selection too wide: {cols} columns exceeds maximum of {max}").format(
				cols=colCount, max=MAX_SELECTION_COLS
			)
		except NameError:
			msg = f"Selection too wide: {colCount} columns exceeds maximum of {MAX_SELECTION_COLS}"
		return (False, msg)

	return (True, None)


class ConfigManager:
	"""
	Centralized configuration management for Terminal Access settings.

	Handles all interactions with config.conf["terminalAccess"], including:
	- Getting and setting configuration values
	- Validation and sanitization
	- Default value management
	- Configuration migration

	Example usage:
		>>> config_mgr = ConfigManager()
		>>>
		>>> # Get a setting value
		>>> tracking_mode = config_mgr.get("cursorTrackingMode")
		>>> print(tracking_mode)  # 1 (CT_STANDARD)
		>>>
		>>> # Set a setting value (with validation)
		>>> config_mgr.set("cursorTrackingMode", 2)  # CT_HIGHLIGHT
		>>>
		>>> # Check a boolean setting
		>>> if config_mgr.get("keyEcho"):
		>>>     print("Key echo is enabled")
		>>>
		>>> # Validate all settings
		>>> config_mgr.validate_all()

	Thread Safety:
		All operations are thread-safe. Config access is synchronized by NVDA.

	Validation:
		All set() operations automatically validate values against configured ranges.
		Invalid values are rejected and logged.
	"""

	def __init__(self) -> None:
		"""Initialize the configuration manager and perform initial validation."""
		self._migrate_legacy_settings()
		self.validate_all()

	def _migrate_legacy_settings(self) -> None:
		"""Migrate old configuration keys to new format (one-time migration)."""
		# Migrate processSymbols to punctuationLevel
		# Note: We don't remove the old key as it's still in the config spec (deprecated)
		# and NVDA's config objects don't support deletion
		if "processSymbols" in config.conf["terminalAccess"]:
			if "punctuationLevel" not in config.conf["terminalAccess"]:
				old_value = config.conf["terminalAccess"]["processSymbols"]
				# True -> Level 2 (most), False -> Level 0 (none)
				config.conf["terminalAccess"]["punctuationLevel"] = PUNCT_MOST if old_value else PUNCT_NONE

	def get(self, key: str, default: Any = None) -> Any:
		"""
		Get a configuration value.

		Args:
			key: Configuration key name
			default: Default value if key doesn't exist

		Returns:
			The configuration value or default if not found
		"""
		try:
			return config.conf["terminalAccess"].get(key, default)
		except Exception:
			return default

	def set(self, key: str, value: Any) -> bool:
		"""
		Set a configuration value with validation.

		Args:
			key: Configuration key name
			value: Value to set

		Returns:
			True if set successfully, False if validation failed
		"""
		try:
			# Validate based on key type
			validated_value = self._validate_key(key, value)
			if validated_value is None:
				return False

			config.conf["terminalAccess"][key] = validated_value
			return True
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access ConfigManager: Failed to set {key}={value}: {e}")
			return False

	def _validate_key(self, key: str, value: Any) -> Any:
		"""
		Validate a configuration value based on its key.

		Args:
			key: Configuration key name
			value: Value to validate

		Returns:
			Validated value, or None if validation fails
		"""
		# Integer validations
		if key == "cursorTrackingMode":
			return _validateInteger(value, 0, 3, 1, key)
		elif key == "punctuationLevel":
			return _validateInteger(value, 0, 3, 2, key)
		elif key == "cursorDelay":
			return _validateInteger(value, 0, 1000, 20, key)
		elif key in ["windowTop", "windowBottom", "windowLeft", "windowRight"]:
			return _validateInteger(value, 0, MAX_WINDOW_DIMENSION, 0, key)

		# String validations
		elif key == "repeatedSymbolsValues":
			return _validateString(value, MAX_REPEATED_SYMBOLS_LENGTH, "-_=!", key)

		# Boolean values - no validation needed
		elif key in ["cursorTracking", "keyEcho", "linePause", "repeatedSymbols",
					 "quietMode", "verboseMode", "windowEnabled"]:
			return bool(value)

		# Unknown key - return as-is (for forward compatibility)
		return value

	def validate_all(self) -> None:
		"""Validate and sanitize all configuration values."""
		# Validate all integer settings
		self.set("cursorTrackingMode", self.get("cursorTrackingMode", 1))
		self.set("punctuationLevel", self.get("punctuationLevel", 2))
		self.set("cursorDelay", self.get("cursorDelay", 20))
		self.set("windowTop", self.get("windowTop", 0))
		self.set("windowBottom", self.get("windowBottom", 0))
		self.set("windowLeft", self.get("windowLeft", 0))
		self.set("windowRight", self.get("windowRight", 0))

		# Validate string settings
		self.set("repeatedSymbolsValues", self.get("repeatedSymbolsValues", "-_=!"))

	def reset_to_defaults(self) -> None:
		"""Reset all configuration values to their defaults."""
		config.conf["terminalAccess"]["cursorTracking"] = True
		config.conf["terminalAccess"]["cursorTrackingMode"] = CT_STANDARD
		config.conf["terminalAccess"]["keyEcho"] = True
		config.conf["terminalAccess"]["linePause"] = True
		config.conf["terminalAccess"]["punctuationLevel"] = PUNCT_MOST
		config.conf["terminalAccess"]["repeatedSymbols"] = False
		config.conf["terminalAccess"]["repeatedSymbolsValues"] = "-_=!"
		config.conf["terminalAccess"]["cursorDelay"] = 20
		config.conf["terminalAccess"]["quietMode"] = False
		config.conf["terminalAccess"]["verboseMode"] = False
		config.conf["terminalAccess"]["indentationOnLineRead"] = False
		config.conf["terminalAccess"]["windowTop"] = 0
		config.conf["terminalAccess"]["windowBottom"] = 0
		config.conf["terminalAccess"]["windowLeft"] = 0
		config.conf["terminalAccess"]["windowRight"] = 0
		config.conf["terminalAccess"]["windowEnabled"] = False
