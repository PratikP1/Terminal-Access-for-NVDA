# Terminal Access for NVDA - Global Plugin
# Copyright (C) 2024 Pratik Patel
# This add-on is covered by the GNU General Public License, version 3.
# See the file LICENSE for more details.

"""
Terminal Access Global Plugin for NVDA

This plugin provides enhanced accessibility features for Windows Terminal and PowerShell,
including navigation by line/word/character, cursor tracking, and symbol processing.

Architecture Overview:
	The plugin is organized into several key components:

	1. **PositionCache**: Performance optimization for position calculations
	   - Caches (row, col) results with timestamp-based expiration
	   - Thread-safe with O(1) lookup and update

	2. **ANSIParser**: Color and formatting detection
	   - Parses ANSI escape sequences (SGR codes)
	   - Supports standard colors, 256-color, and RGB modes
	   - Extracts bold, italic, underline, and other formatting

	3. **UnicodeWidthHelper**: CJK and combining character support
	   - Calculates display width accounting for Unicode properties
	   - Handles double-width CJK characters correctly
	   - Extracts text by column range, not character index

	4. **ApplicationProfile**: App-specific settings and window definitions
	   - Customizes behavior per application (vim, tmux, htop, etc.)
	   - Defines screen regions with different speech modes
	   - Overrides global settings on per-app basis

	5. **ProfileManager**: Profile detection and management
	   - Detects current application from focus object
	   - Loads appropriate profile automatically
	   - Manages profile creation, import, and export

	6. **GlobalPlugin**: Main NVDA plugin class
	   - Registers keyboard gestures and scripts
	   - Manages terminal detection and navigation
	   - Coordinates all components for terminal access

Key Features:
	- Navigation: Line, word, character, column, row movement
	- Selection: Linear and rectangular (column-based) text selection
	- Cursor Tracking: Standard, highlight, window, or off modes
	- Symbol Processing: Configurable punctuation levels (none/some/most/all)
	- Window Tracking: Define and track screen regions independently
	- Application Profiles: Auto-detect and apply app-specific settings
	- Color/Format: Announce ANSI colors and formatting attributes
	- Unicode Support: Proper handling of CJK and combining characters

Configuration:
	Settings are stored in NVDA config under [terminalAccess] section.
	See confspec for available settings and their defaults.

Performance:
	- Position caching reduces O(n) calculations to O(1)
	- Background threading for large selections (>1000 chars)
	- Resource limits prevent DoS from malicious terminal output

Security:
	- Input validation on all configuration values
	- Size limits on selections and window dimensions
	- Timeout-based cache invalidation
	- Safe handling of untrusted terminal content

For detailed architecture information, see ARCHITECTURE.md.
For API reference, see API_REFERENCE.md.
"""

import globalPluginHandler
import api
import ui
import config
import gui
import textInfos
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel
import addonHandler
import wx
import os
import re
import time
import threading
from scriptHandler import script
import scriptHandler
import globalCommands
import speech
from typing import Optional, Tuple, Dict, List, Union, Any

try:
	addonHandler.initTranslation()
except (ImportError, AttributeError, OSError):
	# If translation initialization fails, provide a fallback function
	def _(text):
		return text

# Script category for Terminal Access commands
SCRCAT_TERMINALACCESS = _("Terminal Access")

# Cursor tracking mode constants
CT_OFF = 0
CT_STANDARD = 1
CT_HIGHLIGHT = 2
CT_WINDOW = 3

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
	"processSymbols": "boolean(default=False)",  # Deprecated, use punctuationLevel
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
}

# Register configuration
config.conf.spec["terminalAccess"] = confspec


class PositionCache:
	"""
	Cache for terminal position calculations with timestamp-based invalidation.

	Stores bookmark→(row, col, timestamp) mappings to avoid repeated O(n) calculations.
	Cache entries expire after CACHE_TIMEOUT_MS milliseconds.

	Example usage:
		>>> cache = PositionCache()
		>>> bookmark = textInfo.bookmark
		>>>
		>>> # First calculation (cache miss)
		>>> cached_pos = cache.get(bookmark)  # Returns None
		>>> row, col = expensive_calculation(bookmark)
		>>> cache.set(bookmark, row, col)
		>>>
		>>> # Second calculation (cache hit)
		>>> cached_pos = cache.get(bookmark)  # Returns (row, col)
		>>> if cached_pos:
		>>>     row, col = cached_pos  # No expensive recalculation needed
		>>>
		>>> # After CACHE_TIMEOUT_MS milliseconds
		>>> cached_pos = cache.get(bookmark)  # Returns None (expired)

	Thread Safety:
		All operations are thread-safe using internal locking.

	Performance:
		- get(): O(1) average case
		- set(): O(1) average case
		- Space complexity: O(min(n, MAX_CACHE_SIZE)) where n = unique bookmarks
	"""

	CACHE_TIMEOUT_MS = 1000  # 1 second timeout
	MAX_CACHE_SIZE = 100  # Maximum number of cached positions

	def __init__(self) -> None:
		"""Initialize an empty position cache."""
		self._cache: Dict[str, Tuple[int, int, float]] = {}
		self._lock: threading.Lock = threading.Lock()

	def get(self, bookmark: Any) -> Optional[Tuple[int, int]]:
		"""
		Retrieve cached position for a bookmark if valid.

		Args:
			bookmark: TextInfo bookmark object

		Returns:
			tuple: (row, col) if cache hit and not expired, None otherwise
		"""
		with self._lock:
			key = str(bookmark)
			if key in self._cache:
				row, col, timestamp = self._cache[key]
				# Check if cache entry is still valid
				if (time.time() * 1000 - timestamp) < self.CACHE_TIMEOUT_MS:
					return (row, col)
				else:
					# Expired entry, remove it
					del self._cache[key]
		return None

	def set(self, bookmark: Any, row: int, col: int) -> None:
		"""
		Store position in cache with current timestamp.

		Args:
			bookmark: TextInfo bookmark object
			row: Row number
			col: Column number
		"""
		with self._lock:
			# Enforce size limit - remove oldest entry if needed
			if len(self._cache) >= self.MAX_CACHE_SIZE:
				# Remove oldest entry (simple FIFO strategy)
				oldest_key = next(iter(self._cache))
				del self._cache[oldest_key]

			key = str(bookmark)
			timestamp = time.time() * 1000  # Current time in milliseconds
			self._cache[key] = (row, col, timestamp)

	def clear(self) -> None:
		"""Clear all cached positions."""
		with self._lock:
			self._cache.clear()

	def invalidate(self, bookmark: Any) -> None:
		"""
		Invalidate a specific cached position.

		Args:
			bookmark: TextInfo bookmark to invalidate
		"""
		with self._lock:
			key = str(bookmark)
			if key in self._cache:
				del self._cache[key]


class ANSIParser:
	"""
	Robust ANSI escape sequence parser for terminal color and formatting attributes.

	Supports:
	- Standard 8 colors (30-37 foreground, 40-47 background)
	- Bright colors (90-97 foreground, 100-107 background)
	- 256-color mode (ESC[38;5;Nm and ESC[48;5;Nm)
	- RGB color mode (ESC[38;2;R;G;Bm and ESC[48;2;R;G;Bm)
	- Formatting: bold, dim, italic, underline, blink, inverse, strikethrough

	Example usage:
		>>> parser = ANSIParser()
		>>>
		>>> # Parse standard color
		>>> attrs = parser.parse('\\x1b[31mRed text\\x1b[0m')
		>>> print(attrs['foreground'])  # 'red'
		>>> print(attrs['bold'])  # False
		>>>
		>>> # Parse multiple attributes
		>>> attrs = parser.parse('\\x1b[1;4;91mBright red, bold, underlined\\x1b[0m')
		>>> print(attrs['foreground'])  # 'bright red'
		>>> print(attrs['bold'])  # True
		>>> print(attrs['underline'])  # True
		>>>
		>>> # Parse RGB color
		>>> attrs = parser.parse('\\x1b[38;2;255;128;0mOrange\\x1b[0m')
		>>> print(attrs['foreground'])  # (255, 128, 0)
		>>>
		>>> # Format attributes as human-readable text
		>>> formatted = parser.formatAttributes(mode='detailed')
		>>> # Returns: "bright red foreground, bold, underline"
		>>>
		>>> # Strip ANSI codes from text
		>>> clean = ANSIParser.stripANSI('\\x1b[31mRed\\x1b[0m')
		>>> print(clean)  # 'Red'

	State Management:
		Parser maintains internal state across parse() calls. Use reset() to clear.
		Each parse() call updates the internal state based on found codes.

	Performance:
		- parse(): O(n) where n = length of input text
		- stripANSI(): O(n) static method, no state modification
	"""

	# Standard ANSI color names
	STANDARD_COLORS = {
		30: 'black', 31: 'red', 32: 'green', 33: 'yellow',
		34: 'blue', 35: 'magenta', 36: 'cyan', 37: 'white',
		90: 'bright black', 91: 'bright red', 92: 'bright green', 93: 'bright yellow',
		94: 'bright blue', 95: 'bright magenta', 96: 'bright cyan', 97: 'bright white',
	}

	BACKGROUND_COLORS = {
		40: 'black', 41: 'red', 42: 'green', 43: 'yellow',
		44: 'blue', 45: 'magenta', 46: 'cyan', 47: 'white',
		100: 'bright black', 101: 'bright red', 102: 'bright green', 103: 'bright yellow',
		104: 'bright blue', 105: 'bright magenta', 106: 'bright cyan', 107: 'bright white',
	}

	# Format attribute codes
	FORMAT_CODES = {
		1: 'bold',
		2: 'dim',
		3: 'italic',
		4: 'underline',
		5: 'blink slow',
		6: 'blink rapid',
		7: 'inverse',
		8: 'hidden',
		9: 'strikethrough',
	}

	def __init__(self) -> None:
		"""Initialize the ANSI parser."""
		self.foreground: Optional[Union[str, Tuple[int, int, int]]] = None
		self.background: Optional[Union[str, Tuple[int, int, int]]] = None
		self.bold: bool = False
		self.dim: bool = False
		self.italic: bool = False
		self.underline: bool = False
		self.blink: bool = False
		self.inverse: bool = False
		self.hidden: bool = False
		self.strikethrough: bool = False
		self.reset()

	def reset(self) -> None:
		"""Reset parser state to defaults."""
		self.foreground = None
		self.background = None
		self.bold = False
		self.dim = False
		self.italic = False
		self.underline = False
		self.blink = False
		self.inverse = False
		self.hidden = False
		self.strikethrough = False

	def parse(self, text: str) -> Dict[str, Any]:
		"""
		Parse ANSI escape sequences from text and return attributes.

		Args:
			text: Text containing ANSI escape sequences

		Returns:
			dict: Dictionary of current attributes {
				'foreground': color name or (r, g, b) tuple,
				'background': color name or (r, g, b) tuple,
				'bold': bool, 'dim': bool, 'italic': bool, 'underline': bool,
				'blink': bool, 'inverse': bool, 'hidden': bool, 'strikethrough': bool
			}
		"""
		# Find all ANSI escape sequences
		pattern = re.compile(r'\x1b\[([0-9;]+)m')
		matches = pattern.findall(text)

		for match in matches:
			codes = [int(c) for c in match.split(';') if c]
			self._processCodes(codes)

		return self._getCurrentAttributes()

	def _processCodes(self, codes: List[int]) -> None:
		"""Process a list of ANSI codes."""
		i = 0
		while i < len(codes):
			code = codes[i]

			# Reset all attributes
			if code == 0:
				self.reset()

			# Foreground colors (standard and bright)
			elif code in self.STANDARD_COLORS:
				self.foreground = self.STANDARD_COLORS[code]

			# Background colors (standard and bright)
			elif code in self.BACKGROUND_COLORS:
				self.background = self.BACKGROUND_COLORS[code]

			# Format attributes
			elif code in self.FORMAT_CODES:
				attr = self.FORMAT_CODES[code]
				if attr == 'bold':
					self.bold = True
				elif attr == 'dim':
					self.dim = True
				elif attr == 'italic':
					self.italic = True
				elif attr == 'underline':
					self.underline = True
				elif attr in ('blink slow', 'blink rapid'):
					self.blink = True
				elif attr == 'inverse':
					self.inverse = True
				elif attr == 'hidden':
					self.hidden = True
				elif attr == 'strikethrough':
					self.strikethrough = True

			# Reset format attributes (20-29)
			elif code == 22:  # Normal intensity (not bold or dim)
				self.bold = False
				self.dim = False
			elif code == 23:  # Not italic
				self.italic = False
			elif code == 24:  # Not underlined
				self.underline = False
			elif code == 25:  # Not blinking
				self.blink = False
			elif code == 27:  # Not inverse
				self.inverse = False
			elif code == 28:  # Not hidden
				self.hidden = False
			elif code == 29:  # Not strikethrough
				self.strikethrough = False

			# 256-color mode: ESC[38;5;Nm (foreground) or ESC[48;5;Nm (background)
			elif code == 38 and i + 2 < len(codes) and codes[i + 1] == 5:
				self.foreground = f"color{codes[i + 2]}"
				i += 2
			elif code == 48 and i + 2 < len(codes) and codes[i + 1] == 5:
				self.background = f"color{codes[i + 2]}"
				i += 2

			# RGB mode: ESC[38;2;R;G;Bm (foreground) or ESC[48;2;R;G;Bm (background)
			elif code == 38 and i + 4 < len(codes) and codes[i + 1] == 2:
				self.foreground = (codes[i + 2], codes[i + 3], codes[i + 4])
				i += 4
			elif code == 48 and i + 4 < len(codes) and codes[i + 1] == 2:
				self.background = (codes[i + 2], codes[i + 3], codes[i + 4])
				i += 4

			# Default foreground/background
			elif code == 39:
				self.foreground = None
			elif code == 49:
				self.background = None

			i += 1

	def _getCurrentAttributes(self) -> Dict[str, Any]:
		"""Get current attribute state as a dictionary."""
		return {
			'foreground': self.foreground,
			'background': self.background,
			'bold': self.bold,
			'dim': self.dim,
			'italic': self.italic,
			'underline': self.underline,
			'blink': self.blink,
			'inverse': self.inverse,
			'hidden': self.hidden,
			'strikethrough': self.strikethrough,
		}

	def formatAttributes(self, mode: str = 'detailed') -> str:
		"""
		Format current attributes as human-readable text.

		Args:
			mode: 'brief', 'detailed', or 'change-only'

		Returns:
			str: Formatted attribute description
		"""
		attrs = self._getCurrentAttributes()
		parts = []

		if mode == 'brief':
			# Brief mode: just colors
			if attrs['foreground']:
				if isinstance(attrs['foreground'], tuple):
					parts.append("RGB color")
				else:
					parts.append(attrs['foreground'])
			if attrs['background']:
				if isinstance(attrs['background'], tuple):
					parts.append("background RGB")
				else:
					parts.append(f"{attrs['background']} background")

		else:  # detailed mode
			# Foreground color
			if attrs['foreground']:
				if isinstance(attrs['foreground'], tuple):
					r, g, b = attrs['foreground']
					parts.append(f"RGB({r},{g},{b}) foreground")
				else:
					parts.append(f"{attrs['foreground']} foreground")

			# Background color
			if attrs['background']:
				if isinstance(attrs['background'], tuple):
					r, g, b = attrs['background']
					parts.append(f"RGB({r},{g},{b}) background")
				else:
					parts.append(f"{attrs['background']} background")

			# Format attributes
			format_attrs = []
			if attrs['bold']:
				format_attrs.append('bold')
			if attrs['dim']:
				format_attrs.append('dim')
			if attrs['italic']:
				format_attrs.append('italic')
			if attrs['underline']:
				format_attrs.append('underline')
			if attrs['blink']:
				format_attrs.append('blink')
			if attrs['inverse']:
				format_attrs.append('inverse')
			if attrs['strikethrough']:
				format_attrs.append('strikethrough')

			if format_attrs:
				parts.append(', '.join(format_attrs))

		return ', '.join(parts) if parts else 'default attributes'

	@staticmethod
	def stripANSI(text: str) -> str:
		"""
		Remove all ANSI escape sequences from text.

		Args:
			text: Text containing ANSI codes

		Returns:
			str: Text with ANSI codes removed
		"""
		# Remove all ANSI escape sequences
		ansi_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
		return ansi_pattern.sub('', text)


class UnicodeWidthHelper:
	"""
	Helper class for calculating display width of Unicode text.

	Handles:
	- CJK characters (2 columns wide)
	- Combining characters (0 columns wide)
	- Control characters
	- Standard ASCII (1 column wide)

	Example usage:
		>>> # Single character width
		>>> width = UnicodeWidthHelper.getCharWidth('A')
		>>> print(width)  # 1
		>>>
		>>> # CJK character (double-width)
		>>> width = UnicodeWidthHelper.getCharWidth('中')
		>>> print(width)  # 2
		>>>
		>>> # Total text width
		>>> text = "Hello世界"  # 5 ASCII + 2 CJK = 5*1 + 2*2 = 9 columns
		>>> width = UnicodeWidthHelper.getTextWidth(text)
		>>> print(width)  # 9
		>>>
		>>> # Extract by column range (1-based)
		>>> text = "Hello World"
		>>> result = UnicodeWidthHelper.extractColumnRange(text, 1, 5)
		>>> print(result)  # "Hello"
		>>>
		>>> result = UnicodeWidthHelper.extractColumnRange(text, 7, 11)
		>>> print(result)  # "World"
		>>>
		>>> # Find string index for column position
		>>> text = "Hello"
		>>> index = UnicodeWidthHelper.findColumnPosition(text, 3)
		>>> print(index)  # 2 (0-based index for column 3)
		>>> print(text[index])  # 'l'

	Fallback Behavior:
		If wcwidth library is not available, assumes 1 column per character.
		This provides graceful degradation on systems without wcwidth.

	Thread Safety:
		All methods are static and thread-safe (no shared state).
	"""

	@staticmethod
	def getCharWidth(char: str) -> int:
		"""
		Get display width of a single character.

		Args:
			char: Single character string

		Returns:
			int: Display width (0, 1, or 2 columns)
		"""
		try:
			import wcwidth
			width = wcwidth.wcwidth(char)
			# wcwidth returns -1 for control characters, treat as 0
			return max(0, width) if width is not None else 1
		except ImportError:
			# Fallback if wcwidth not available: assume 1 column
			return 1
		except Exception:
			# For any other error, assume 1 column
			return 1

	@staticmethod
	def getTextWidth(text: str) -> int:
		"""
		Calculate total display width of a text string.

		Args:
			text: Text string

		Returns:
			int: Total display width in columns
		"""
		try:
			import wcwidth
			width = wcwidth.wcswidth(text)
			# wcswidth returns -1 if text contains control characters
			if width >= 0:
				return width
			# Fall back to character-by-character calculation
			total = 0
			for char in text:
				char_width = wcwidth.wcwidth(char)
				if char_width >= 0:
					total += char_width
			return total
		except ImportError:
			# Fallback if wcwidth not available: assume 1 column per char
			return len(text)
		except Exception:
			# For any other error, fall back to length
			return len(text)

	@staticmethod
	def extractColumnRange(text: str, startCol: int, endCol: int) -> str:
		"""
		Extract text from specific column range, accounting for Unicode width.

		Args:
			text: Source text string
			startCol: Starting column (1-based)
			endCol: Ending column (1-based, inclusive)

		Returns:
			str: Text within the specified column range
		"""
		if not text:
			return ""

		result = []
		currentCol = 1
		i = 0

		while i < len(text):
			char = text[i]
			charWidth = UnicodeWidthHelper.getCharWidth(char)

			# Check if character falls within the column range
			charEndCol = currentCol + charWidth - 1

			if charEndCol < startCol:
				# Character is before the range
				pass
			elif currentCol > endCol:
				# Character is after the range, we're done
				break
			else:
				# Character overlaps with the range
				result.append(char)

			currentCol += charWidth
			i += 1

		return ''.join(result)

	@staticmethod
	def findColumnPosition(text: str, targetCol: int) -> int:
		"""
		Find the string index that corresponds to a target column position.

		Args:
			text: Source text string
			targetCol: Target column position (1-based)

		Returns:
			int: String index corresponding to the column position
		"""
		if not text:
			return 0

		currentCol = 1
		for i, char in enumerate(text):
			if currentCol >= targetCol:
				return i
			charWidth = UnicodeWidthHelper.getCharWidth(char)
			currentCol += charWidth

		return len(text)


class BidiHelper:
	"""
	Helper class for bidirectional text (RTL/LTR) handling.

	Implements Unicode Bidirectional Algorithm (UAX #9) for proper handling of
	right-to-left text (Arabic, Hebrew) mixed with left-to-right text.

	Features:
	- Automatic RTL text detection
	- Bidirectional text reordering
	- Arabic character reshaping
	- Mixed RTL/LTR text support

	Example usage:
		>>> helper = BidiHelper()
		>>>
		>>> # Detect RTL text
		>>> is_rtl = helper.is_rtl("مرحبا")  # Arabic "Hello"
		>>> print(is_rtl)  # True
		>>>
		>>> # Process mixed RTL/LTR text
		>>> text = "Hello مرحبا World"
		>>> display_text = helper.process_text(text)
		>>>
		>>> # Extract column range with RTL awareness
		>>> result = helper.extract_column_range_rtl(text, 1, 5)

	Dependencies:
		Requires optional packages:
		- python-bidi>=0.4.2
		- arabic-reshaper>=2.1.3

		Gracefully degrades if packages not available.

	Thread Safety:
		All methods are thread-safe (no shared mutable state).

	Section Reference:
		FUTURE_ENHANCEMENTS.md Section 4.1 (lines 465-526)
	"""

	def __init__(self):
		"""Initialize BidiHelper with optional dependencies."""
		try:
			from bidi.algorithm import get_display
			self._get_display = get_display
			self._bidi_available = True
		except ImportError:
			self._bidi_available = False

		try:
			import arabic_reshaper
			self._reshaper = arabic_reshaper.reshape
			self._reshaper_available = True
		except ImportError:
			self._reshaper_available = False

	def is_available(self) -> bool:
		"""
		Check if bidirectional text processing is available.

		Returns:
			bool: True if bidi libraries are available
		"""
		return self._bidi_available

	def is_rtl(self, text: str) -> bool:
		"""
		Detect if text is primarily right-to-left.

		Uses Unicode character properties to determine text direction.

		Args:
			text: Text to analyze

		Returns:
			bool: True if text is primarily RTL
		"""
		if not text:
			return False

		rtl_count = 0
		ltr_count = 0

		# RTL Unicode ranges:
		# Arabic: U+0600-U+06FF, U+0750-U+077F
		# Hebrew: U+0590-U+05FF
		for char in text:
			code = ord(char)
			if (0x0590 <= code <= 0x05FF or  # Hebrew
				0x0600 <= code <= 0x06FF or  # Arabic
				0x0750 <= code <= 0x077F):   # Arabic Supplement
				rtl_count += 1
			elif char.isalpha():
				ltr_count += 1

		return rtl_count > ltr_count

	def process_text(self, text: str) -> str:
		"""
		Process text for correct bidirectional display.

		Applies Arabic reshaping and bidirectional algorithm.

		Args:
			text: Input text (may contain mixed RTL/LTR)

		Returns:
			str: Text reordered for visual display
		"""
		if not text:
			return text

		# If libraries not available, return as-is
		if not self._bidi_available:
			return text

		# Reshape Arabic characters if available
		processed = text
		if self._reshaper_available and self.is_rtl(text):
			try:
				processed = self._reshaper(text)
			except Exception:
				# If reshaping fails, continue with original
				pass

		# Apply bidirectional algorithm
		try:
			return self._get_display(processed)
		except Exception:
			# If bidi fails, return processed text
			return processed

	def extract_column_range_rtl(self, text: str, startCol: int, endCol: int) -> str:
		"""
		Extract column range with RTL awareness.

		For RTL text, reverses column indices to match visual order.

		Args:
			text: Source text string
			startCol: Starting column (1-based)
			endCol: Ending column (1-based, inclusive)

		Returns:
			str: Text within the specified column range
		"""
		if not text:
			return ""

		# Detect if text is primarily RTL
		if self.is_rtl(text):
			# Reverse column indices for RTL text
			text_width = UnicodeWidthHelper.getTextWidth(text)
			rtl_start = text_width - endCol + 1
			rtl_end = text_width - startCol + 1
			return UnicodeWidthHelper.extractColumnRange(text, rtl_start, rtl_end)
		else:
			# LTR text - normal extraction
			return UnicodeWidthHelper.extractColumnRange(text, startCol, endCol)


class EmojiHelper:
	"""
	Helper class for handling complex emoji sequences.

	Handles modern emoji features:
	- Emoji sequences (family, flags, professions)
	- Skin tone modifiers (U+1F3FB-U+1F3FF)
	- Zero-width joiners (ZWJ sequences)
	- Emoji variation selectors

	Features:
	- Accurate width calculation for emoji sequences
	- Detection of emoji vs regular text
	- Support for multi-codepoint emoji

	Example usage:
		>>> helper = EmojiHelper()
		>>>
		>>> # Detect emoji
		>>> has_emoji = helper.contains_emoji("Hello 👨‍👩‍👧‍👦")
		>>> print(has_emoji)  # True
		>>>
		>>> # Calculate width including emoji
		>>> width = helper.get_text_width_with_emoji("👨‍👩‍👧‍👦 Family")
		>>> print(width)  # 2 (emoji) + 7 (text) = 9
		>>>
		>>> # Get emoji list
		>>> emojis = helper.extract_emoji_list("Hello 👋 World 🌍")
		>>> print(emojis)  # ['👋', '🌍']

	Dependencies:
		Requires optional package:
		- emoji>=2.0.0

		Falls back to wcwidth if emoji package not available.

	Thread Safety:
		All methods are thread-safe (no shared mutable state).

	Section Reference:
		FUTURE_ENHANCEMENTS.md Section 4.2 (lines 528-566)
	"""

	def __init__(self):
		"""Initialize EmojiHelper with optional dependencies."""
		try:
			import emoji
			self._emoji = emoji
			self._available = True
		except ImportError:
			self._available = False

	def is_available(self) -> bool:
		"""
		Check if emoji processing is available.

		Returns:
			bool: True if emoji library is available
		"""
		return self._available

	def contains_emoji(self, text: str) -> bool:
		"""
		Check if text contains any emoji.

		Args:
			text: Text to check

		Returns:
			bool: True if text contains emoji
		"""
		if not text or not self._available:
			return False

		try:
			return bool(self._emoji.emoji_count(text))
		except Exception:
			return False

	def extract_emoji_list(self, text: str) -> List[str]:
		"""
		Extract all emoji from text.

		Args:
			text: Text to analyze

		Returns:
			List[str]: List of emoji found in text
		"""
		if not text or not self._available:
			return []

		try:
			# emoji_list returns list of dicts with 'emoji' key
			emoji_data = self._emoji.emoji_list(text)
			return [item['emoji'] for item in emoji_data]
		except Exception:
			return []

	def get_emoji_width(self, emoji_text: str) -> int:
		"""
		Calculate display width of emoji sequence.

		Most emoji display as 2 columns wide, including complex sequences.

		Args:
			emoji_text: Emoji or emoji sequence

		Returns:
			int: Display width (typically 2 for emoji)
		"""
		if not emoji_text:
			return 0

		# Most emoji are 2 columns wide
		# This includes complex sequences (family, flags, etc.)
		if self.contains_emoji(emoji_text):
			# Count number of emoji (not codepoints)
			emoji_count = len(self.extract_emoji_list(emoji_text))
			# Each emoji is typically 2 columns
			return emoji_count * 2

		# Not an emoji, fall back to standard width
		return UnicodeWidthHelper.getTextWidth(emoji_text)

	def get_text_width_with_emoji(self, text: str) -> int:
		"""
		Calculate total display width including emoji sequences.

		Handles both emoji and regular text accurately.

		Args:
			text: Text with potential emoji

		Returns:
			int: Total display width in columns
		"""
		if not text:
			return 0

		if not self._available or not self.contains_emoji(text):
			# No emoji or library not available - use standard calculation
			return UnicodeWidthHelper.getTextWidth(text)

		try:
			# Get emoji positions
			emoji_data = self._emoji.emoji_list(text)

			total_width = 0
			last_end = 0

			for item in emoji_data:
				# Add width of text before emoji
				start = item['match_start']
				if start > last_end:
					text_before = text[last_end:start]
					total_width += UnicodeWidthHelper.getTextWidth(text_before)

				# Add emoji width (typically 2)
				total_width += 2

				last_end = item['match_end']

			# Add any remaining text after last emoji
			if last_end < len(text):
				text_after = text[last_end:]
				total_width += UnicodeWidthHelper.getTextWidth(text_after)

			return total_width
		except Exception:
			# If processing fails, fall back to standard calculation
			return UnicodeWidthHelper.getTextWidth(text)


class WindowDefinition:
	"""
	Definition of a window region in terminal output.

	Used for tracking specific regions of terminal display (e.g., tmux panes,
	vim status line, htop process list).

	Example usage:
		>>> # Define a status line window at bottom of screen
		>>> status_window = WindowDefinition(
		>>>     name='status',
		>>>     top=24, bottom=24,  # Last line only
		>>>     left=1, right=80,   # Full width
		>>>     mode='silent'       # Don't announce content
		>>> )
		>>>
		>>> # Check if cursor position is in window
		>>> if status_window.contains(row=24, col=40):
		>>>     print("Cursor is in status window")
		>>>
		>>> # Serialize for storage
		>>> data = status_window.toDict()
		>>> # {'name': 'status', 'top': 24, 'bottom': 24, ...}
		>>>
		>>> # Deserialize from storage
		>>> restored = WindowDefinition.fromDict(data)

	Window Modes:
		- 'announce': Read content normally (default)
		- 'silent': Suppress all speech for this region
		- 'monitor': Track changes but announce differently

	Coordinate System:
		All coordinates are 1-based (row 1, col 1 is top-left).
	"""

	def __init__(self, name: str, top: int, bottom: int, left: int, right: int,
				 mode: str = 'announce', enabled: bool = True) -> None:
		"""
		Initialize a window definition.

		Args:
			name: Window name (e.g., "main pane", "status line")
			top: Top row (1-based)
			bottom: Bottom row (1-based)
			left: Left column (1-based)
			right: Right column (1-based)
			mode: Window mode ('announce', 'silent', 'monitor')
			enabled: Whether window is currently active
		"""
		self.name: str = name
		self.top: int = top
		self.bottom: int = bottom
		self.left: int = left
		self.right: int = right
		self.mode: str = mode  # 'announce' = read content, 'silent' = suppress, 'monitor' = track changes
		self.enabled: bool = enabled

	def contains(self, row: int, col: int) -> bool:
		"""
		Check if a position is within this window.

		Args:
			row: Row number (1-based)
			col: Column number (1-based)

		Returns:
			bool: True if position is within window bounds
		"""
		return (self.enabled and
				self.top <= row <= self.bottom and
				self.left <= col <= self.right)

	def toDict(self) -> Dict[str, Any]:
		"""Convert window definition to dictionary for serialization."""
		return {
			'name': self.name,
			'top': self.top,
			'bottom': self.bottom,
			'left': self.left,
			'right': self.right,
			'mode': self.mode,
			'enabled': self.enabled,
		}

	@classmethod
	def fromDict(cls, data: Dict[str, Any]) -> 'WindowDefinition':
		"""Create window definition from dictionary."""
		return cls(
			name=data.get('name', ''),
			top=data.get('top', 0),
			bottom=data.get('bottom', 0),
			left=data.get('left', 0),
			right=data.get('right', 0),
			mode=data.get('mode', 'announce'),
			enabled=data.get('enabled', True),
		)


class ApplicationProfile:
	"""
	Application-specific configuration profile for terminal applications.

	Allows customizing Terminal Access behavior for different applications (vim, tmux, htop, etc.).

	Example usage:
		>>> # Create a custom profile for Vim
		>>> vim_profile = ApplicationProfile('vim', 'Vim/Neovim')
		>>>
		>>> # Configure settings (None = use global setting)
		>>> vim_profile.punctuationLevel = PUNCT_MOST  # Read more punctuation
		>>> vim_profile.cursorTrackingMode = CT_WINDOW  # Window-based tracking
		>>>
		>>> # Define screen regions
		>>> vim_profile.addWindow('editor', 1, 9997, 1, 9999, mode='announce')
		>>> vim_profile.addWindow('status', 9998, 9999, 1, 9999, mode='silent')
		>>>
		>>> # Check which window cursor is in
		>>> window = vim_profile.getWindowAtPosition(row=10, col=40)
		>>> if window:
		>>>     print(f"In {window.name} window ({window.mode} mode)")
		>>>
		>>> # Export for storage
		>>> data = vim_profile.toDict()
		>>> import json
		>>> json.dump(data, open('vim_profile.json', 'w'))
		>>>
		>>> # Import from storage
		>>> data = json.load(open('vim_profile.json'))
		>>> restored_profile = ApplicationProfile.fromDict(data)

	Profile Inheritance:
		Settings set to None inherit from global Terminal Access settings.
		Non-None values override global settings for this application.

	Window Tracking:
		Profiles can define multiple non-overlapping windows.
		Windows are checked in order; first match wins.
	"""

	def __init__(self, appName: str, displayName: Optional[str] = None) -> None:
		"""
		Initialize an application profile.

		Args:
			appName: Application identifier (e.g., "vim", "tmux", "htop")
			displayName: Human-readable name (e.g., "Vim/Neovim")
		"""
		self.appName: str = appName
		self.displayName: str = displayName or appName

		# Settings overrides (None = use global setting)
		self.punctuationLevel: Optional[int] = None
		self.cursorTrackingMode: Optional[int] = None
		self.keyEcho: Optional[bool] = None
		self.linePause: Optional[bool] = None
		self.processSymbols: Optional[bool] = None
		self.repeatedSymbols: Optional[bool] = None
		self.repeatedSymbolsValues: Optional[str] = None
		self.cursorDelay: Optional[int] = None
		self.quietMode: Optional[bool] = None
		self.announceIndentation: Optional[bool] = None
		self.indentationOnLineRead: Optional[bool] = None

		# Window definitions (list of WindowDefinition objects)
		self.windows: List[WindowDefinition] = []

		# Custom gestures (dict of gesture -> function name)
		self.customGestures: Dict[str, str] = {}

	def addWindow(self, name: str, top: int, bottom: int, left: int, right: int,
				  mode: str = 'announce') -> WindowDefinition:
		"""Add a window definition to this profile."""
		window = WindowDefinition(name, top, bottom, left, right, mode)
		self.windows.append(window)
		return window

	def getWindowAtPosition(self, row: int, col: int) -> Optional[WindowDefinition]:
		"""Get the window containing the specified position."""
		for window in self.windows:
			if window.contains(row, col):
				return window
		return None

	def toDict(self) -> Dict[str, Any]:
		"""Convert profile to dictionary for serialization."""
		return {
			'appName': self.appName,
			'displayName': self.displayName,
			'punctuationLevel': self.punctuationLevel,
			'cursorTrackingMode': self.cursorTrackingMode,
			'keyEcho': self.keyEcho,
			'linePause': self.linePause,
			'processSymbols': self.processSymbols,
			'repeatedSymbols': self.repeatedSymbols,
			'repeatedSymbolsValues': self.repeatedSymbolsValues,
			'cursorDelay': self.cursorDelay,
			'quietMode': self.quietMode,
			'announceIndentation': self.announceIndentation,
			'indentationOnLineRead': self.indentationOnLineRead,
			'windows': [w.toDict() for w in self.windows],
			'customGestures': self.customGestures,
		}

	@classmethod
	def fromDict(cls, data: Dict[str, Any]) -> 'ApplicationProfile':
		"""Create profile from dictionary."""
		profile = cls(data.get('appName', ''), data.get('displayName'))
		profile.punctuationLevel = data.get('punctuationLevel')
		profile.cursorTrackingMode = data.get('cursorTrackingMode')
		profile.keyEcho = data.get('keyEcho')
		profile.linePause = data.get('linePause')
		profile.processSymbols = data.get('processSymbols')
		profile.repeatedSymbols = data.get('repeatedSymbols')
		profile.repeatedSymbolsValues = data.get('repeatedSymbolsValues')
		profile.cursorDelay = data.get('cursorDelay')
		profile.quietMode = data.get('quietMode')
		profile.announceIndentation = data.get('announceIndentation')
		profile.indentationOnLineRead = data.get('indentationOnLineRead')

		# Restore windows
		for winData in data.get('windows', []):
			profile.windows.append(WindowDefinition.fromDict(winData))

		profile.customGestures = data.get('customGestures', {})
		return profile


class ProfileManager:
	"""
	Manager for application-specific profiles.

	Handles profile creation, detection, loading, and application.

	Example usage:
		>>> # Initialize with default profiles (vim, tmux, htop, etc.)
		>>> manager = ProfileManager()
		>>>
		>>> # Detect application from focus object
		>>> app_name = manager.detectApplication(focus)
		>>> print(app_name)  # 'vim', 'tmux', or 'default'
		>>>
		>>> # Get profile for detected app
		>>> profile = manager.getProfile(app_name)
		>>> if profile:
		>>>     print(f"Using {profile.displayName} profile")
		>>>     print(f"Punctuation level: {profile.punctuationLevel}")
		>>>
		>>> # Set as active profile
		>>> manager.setActiveProfile('vim')
		>>> active = manager.activeProfile
		>>> print(f"Active: {active.displayName}")
		>>>
		>>> # Create custom profile
		>>> custom = ApplicationProfile('myapp', 'My Application')
		>>> custom.punctuationLevel = PUNCT_ALL
		>>> manager.addProfile(custom)
		>>>
		>>> # Export/Import profiles
		>>> vim_data = manager.exportProfile('vim')
		>>> # ... save to file ...
		>>> # ... load from file ...
		>>> imported = manager.importProfile(vim_data)

	Default Profiles:
		Includes pre-configured profiles for:
		- vim/nvim: Editor with status line suppression
		- tmux: Terminal multiplexer with status bar
		- htop: Process viewer with header/process regions
		- less/more: Pager with quiet mode
		- git: Version control with diff support
		- nano: Editor with shortcut bar suppression
		- irssi: IRC client with status bar

	Profile Detection:
		1. Check app module name (focusObject.appModule.appName)
		2. Check window title for common patterns
		3. Return 'default' if no match found
	"""

	def __init__(self) -> None:
		"""Initialize the profile manager with default profiles."""
		self.profiles: Dict[str, ApplicationProfile] = {}
		self.activeProfile: Optional[ApplicationProfile] = None
		self._initializeDefaultProfiles()

	def _initializeDefaultProfiles(self) -> None:
		"""Create default profiles for popular terminal applications."""

		# Vim/Neovim profile
		vim = ApplicationProfile('vim', 'Vim/Neovim')
		vim.punctuationLevel = PUNCT_MOST  # More punctuation for code
		vim.cursorTrackingMode = CT_WINDOW  # Use window tracking
		# Silence bottom two lines (status line and command line)
		vim.addWindow('editor', 1, 9999, 1, 9999, mode='announce')
		vim.addWindow('status', 9999, 9999, 1, 9999, mode='silent')
		self.profiles['vim'] = vim
		self.profiles['nvim'] = vim  # Same profile for neovim

		# tmux profile
		tmux = ApplicationProfile('tmux', 'tmux (Terminal Multiplexer)')
		tmux.cursorTrackingMode = CT_STANDARD
		# Status bar at bottom (typically last line)
		tmux.addWindow('status', 9999, 9999, 1, 9999, mode='silent')
		self.profiles['tmux'] = tmux

		# htop profile
		htop = ApplicationProfile('htop', 'htop (Process Viewer)')
		htop.repeatedSymbols = False  # Lots of repeated characters in bars
		# Header area (first ~4 lines with CPU/Memory meters)
		htop.addWindow('header', 1, 4, 1, 9999, mode='announce')
		# Process list (main area)
		htop.addWindow('processes', 5, 9999, 1, 9999, mode='announce')
		self.profiles['htop'] = htop

		# less/more pager profile
		less = ApplicationProfile('less', 'less/more (Pager)')
		less.quietMode = True  # Reduce verbosity for reading
		less.keyEcho = False  # Don't echo navigation keys
		self.profiles['less'] = less
		self.profiles['more'] = less

		# git profile (for git diff, log, etc.)
		git = ApplicationProfile('git', 'Git')
		git.punctuationLevel = PUNCT_MOST  # Show symbols in diffs
		git.repeatedSymbols = False  # Many dashes and equals signs
		self.profiles['git'] = git

		# nano editor profile
		nano = ApplicationProfile('nano', 'GNU nano')
		nano.cursorTrackingMode = CT_STANDARD
		# Silence bottom two lines (status and shortcuts)
		nano.addWindow('editor', 1, 9997, 1, 9999, mode='announce')
		nano.addWindow('shortcuts', 9998, 9999, 1, 9999, mode='silent')
		self.profiles['nano'] = nano

		# irssi (IRC client) profile
		irssi = ApplicationProfile('irssi', 'irssi (IRC Client)')
		irssi.punctuationLevel = PUNCT_SOME  # Basic punctuation for chat
		irssi.linePause = False  # Fast reading for chat
		# Status bar at bottom
		irssi.addWindow('status', 9999, 9999, 1, 9999, mode='silent')
		self.profiles['irssi'] = irssi

		# Section 5.1: Third-party terminal profiles (v1.0.26+)
		# These profiles optimize Terminal Access for popular third-party terminal emulators

		# Cmder profile
		cmder = ApplicationProfile('cmder', 'Cmder')
		cmder.punctuationLevel = PUNCT_SOME  # Balanced for general use
		cmder.cursorTrackingMode = CT_STANDARD
		self.profiles['cmder'] = cmder

		# ConEmu profile
		conemu = ApplicationProfile('conemu', 'ConEmu')
		conemu.punctuationLevel = PUNCT_SOME
		conemu.cursorTrackingMode = CT_STANDARD
		self.profiles['conemu'] = conemu
		self.profiles['conemu64'] = conemu  # Same profile for 64-bit

		# mintty (Git Bash) profile
		mintty = ApplicationProfile('mintty', 'Git Bash (mintty)')
		mintty.punctuationLevel = PUNCT_MOST  # Common for development
		mintty.cursorTrackingMode = CT_STANDARD
		self.profiles['mintty'] = mintty

		# PuTTY profile
		putty = ApplicationProfile('putty', 'PuTTY')
		putty.punctuationLevel = PUNCT_SOME  # SSH/remote terminal
		putty.cursorTrackingMode = CT_STANDARD
		self.profiles['putty'] = putty
		self.profiles['kitty'] = putty  # KiTTY uses same defaults

		# Terminus profile
		terminus = ApplicationProfile('terminus', 'Terminus')
		terminus.punctuationLevel = PUNCT_SOME
		terminus.cursorTrackingMode = CT_STANDARD
		self.profiles['terminus'] = terminus

		# Hyper profile
		hyper = ApplicationProfile('hyper', 'Hyper')
		hyper.punctuationLevel = PUNCT_SOME
		hyper.cursorTrackingMode = CT_STANDARD
		self.profiles['hyper'] = hyper

		# Alacritty profile
		alacritty = ApplicationProfile('alacritty', 'Alacritty')
		alacritty.punctuationLevel = PUNCT_SOME
		alacritty.cursorTrackingMode = CT_STANDARD
		self.profiles['alacritty'] = alacritty

		# WezTerm profile
		wezterm = ApplicationProfile('wezterm', 'WezTerm')
		wezterm.punctuationLevel = PUNCT_SOME
		wezterm.cursorTrackingMode = CT_STANDARD
		self.profiles['wezterm'] = wezterm
		self.profiles['wezterm-gui'] = wezterm  # Same for GUI variant

		# Tabby profile
		tabby = ApplicationProfile('tabby', 'Tabby')
		tabby.punctuationLevel = PUNCT_SOME
		tabby.cursorTrackingMode = CT_STANDARD
		self.profiles['tabby'] = tabby

		# FluentTerminal profile
		fluent = ApplicationProfile('fluent', 'FluentTerminal')
		fluent.punctuationLevel = PUNCT_SOME
		fluent.cursorTrackingMode = CT_STANDARD
		self.profiles['fluent'] = fluent

		# Section 5.2: WSL (Windows Subsystem for Linux) profile (v1.0.27+)
		# Optimized for Linux command-line environment
		wsl = ApplicationProfile('wsl', 'Windows Subsystem for Linux')
		wsl.punctuationLevel = PUNCT_MOST  # Code-friendly for Linux commands
		wsl.cursorTrackingMode = CT_STANDARD
		wsl.repeatedSymbols = False  # Common in command output (progress bars, etc.)
		self.profiles['wsl'] = wsl
		self.profiles['bash'] = wsl  # Use same profile for bash

	def detectApplication(self, focusObject: Any) -> str:
		"""
		Detect the current terminal application.

		Args:
			focusObject: NVDA focus object

		Returns:
			str: Application name or 'default'
		"""
		try:
			# Try to get app name from app module
			if hasattr(focusObject, 'appModule') and hasattr(focusObject.appModule, 'appName'):
				appName = focusObject.appModule.appName.lower()

				# Check if we have a profile for this app
				if appName in self.profiles:
					return appName

			# Try to detect from window title
			if hasattr(focusObject, 'name'):
				title = focusObject.name.lower()

				# Check for common patterns
				if 'vim' in title or 'nvim' in title:
					return 'vim'
				elif 'tmux' in title:
					return 'tmux'
				elif 'htop' in title:
					return 'htop'
				elif 'less' in title or 'more' in title:
					return 'less'
				elif 'git' in title:
					return 'git'
				elif 'nano' in title:
					return 'nano'
				elif 'irssi' in title:
					return 'irssi'

		except Exception:
			pass

		return 'default'

	def getProfile(self, appName: str) -> Optional[ApplicationProfile]:
		"""Get profile for specified application."""
		return self.profiles.get(appName)

	def setActiveProfile(self, appName: str) -> None:
		"""Set the currently active profile."""
		self.activeProfile = self.profiles.get(appName)

	def addProfile(self, profile: ApplicationProfile) -> None:
		"""Add or update a profile."""
		self.profiles[profile.appName] = profile

	def removeProfile(self, appName: str) -> None:
		"""Remove a profile."""
		if appName in self.profiles and appName not in ['vim', 'tmux', 'htop', 'less', 'git', 'nano', 'irssi']:
			del self.profiles[appName]

	def exportProfile(self, appName: str) -> Optional[Dict[str, Any]]:
		"""Export profile to dictionary."""
		profile = self.profiles.get(appName)
		if profile:
			return profile.toDict()
		return None

	def importProfile(self, data: Dict[str, Any]) -> ApplicationProfile:
		"""Import profile from dictionary."""
		profile = ApplicationProfile.fromDict(data)
		self.addProfile(profile)
		return profile


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


def _validateSelectionSize(startRow: int, endRow: int, startCol: int, endCol: int) -> Tuple[bool, Optional[str]]:
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
		return (False, _("Selection too large: {rows} rows exceeds maximum of {max}").format(
			rows=rowCount, max=MAX_SELECTION_ROWS
		))

	if colCount > MAX_SELECTION_COLS:
		return (False, _("Selection too wide: {cols} columns exceeds maximum of {max}").format(
			cols=colCount, max=MAX_SELECTION_COLS
		))

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


class WindowManager:
	"""
	Centralized window tracking and management for Terminal Access.

	Handles window definition, position tracking, and state management.
	Windows are rectangular regions of the terminal screen that can be
	tracked separately with different speech modes.

	Example usage:
		>>> win_mgr = WindowManager(config_manager)
		>>>
		>>> # Define a window
		>>> win_mgr.set_window_start(row=1, col=1)
		>>> win_mgr.set_window_end(row=24, col=80)
		>>> win_mgr.enable_window()
		>>>
		>>> # Check if position is in window
		>>> if win_mgr.is_position_in_window(row=10, col=40):
		>>>     print("Position is in window")
		>>>
		>>> # Get window bounds
		>>> bounds = win_mgr.get_window_bounds()
		>>> print(f"Window: rows {bounds['top']}-{bounds['bottom']}")

	Thread Safety:
		All operations are thread-safe through config manager.

	State Management:
		Window state is persisted via ConfigManager.
		Changes are immediately saved to NVDA configuration.
	"""

	def __init__(self, config_manager: ConfigManager) -> None:
		"""
		Initialize the window manager.

		Args:
			config_manager: ConfigManager instance for config access
		"""
		self._config = config_manager
		self._defining = False
		self._start_set = False

	def is_defining(self) -> bool:
		"""Check if currently in window definition mode."""
		return self._defining

	def start_definition(self) -> None:
		"""Start window definition mode."""
		self._defining = True
		self._start_set = False

	def cancel_definition(self) -> None:
		"""Cancel window definition mode."""
		self._defining = False
		self._start_set = False

	def set_window_start(self, row: int, col: int) -> bool:
		"""
		Set the window start position.

		Args:
			row: Starting row (1-based)
			col: Starting column (1-based)

		Returns:
			True if set successfully
		"""
		if not self._defining:
			return False

		if not self._validate_coordinates(row, col):
			return False

		self._config.set("windowTop", row)
		self._config.set("windowLeft", col)
		self._start_set = True
		return True

	def set_window_end(self, row: int, col: int) -> bool:
		"""
		Set the window end position and complete definition.

		Args:
			row: Ending row (1-based)
			col: Ending column (1-based)

		Returns:
			True if set successfully
		"""
		if not self._defining or not self._start_set:
			return False

		if not self._validate_coordinates(row, col):
			return False

		self._config.set("windowBottom", row)
		self._config.set("windowRight", col)
		self._defining = False
		return True

	def _validate_coordinates(self, row: int, col: int) -> bool:
		"""
		Validate row and column coordinates.

		Args:
			row: Row number
			col: Column number

		Returns:
			True if valid
		"""
		return (1 <= row <= MAX_WINDOW_DIMENSION and
				1 <= col <= MAX_WINDOW_DIMENSION)

	def enable_window(self) -> None:
		"""Enable window tracking."""
		self._config.set("windowEnabled", True)

	def disable_window(self) -> None:
		"""Disable window tracking."""
		self._config.set("windowEnabled", False)

	def is_window_enabled(self) -> bool:
		"""Check if window tracking is enabled."""
		return self._config.get("windowEnabled", False)

	def is_position_in_window(self, row: int, col: int) -> bool:
		"""
		Check if a position is within the defined window.

		Args:
			row: Row number (1-based)
			col: Column number (1-based)

		Returns:
			True if position is in window and window is enabled
		"""
		if not self.is_window_enabled():
			return False

		top = self._config.get("windowTop", 0)
		bottom = self._config.get("windowBottom", 0)
		left = self._config.get("windowLeft", 0)
		right = self._config.get("windowRight", 0)

		# Window not properly defined
		if top == 0 or bottom == 0 or left == 0 or right == 0:
			return False

		return (top <= row <= bottom and left <= col <= right)

	def get_window_bounds(self) -> Dict[str, int]:
		"""
		Get the current window bounds.

		Returns:
			Dictionary with 'top', 'bottom', 'left', 'right' keys
		"""
		return {
			'top': self._config.get("windowTop", 0),
			'bottom': self._config.get("windowBottom", 0),
			'left': self._config.get("windowLeft", 0),
			'right': self._config.get("windowRight", 0),
		}

	def clear_window(self) -> None:
		"""Clear window definition and disable tracking."""
		self._config.set("windowTop", 0)
		self._config.set("windowBottom", 0)
		self._config.set("windowLeft", 0)
		self._config.set("windowRight", 0)
		self._config.set("windowEnabled", False)
		self._defining = False
		self._start_set = False


class PositionCalculator:
	"""
	Centralized position calculation for terminal coordinates.

	Handles calculation of (row, col) coordinates from TextInfo objects,
	with performance optimization through caching and incremental tracking.

	Example usage:
		>>> calc = PositionCalculator()
		>>>
		>>> # Calculate position from TextInfo
		>>> row, col = calc.calculate(textInfo, terminal)
		>>> print(f"Position: row {row}, col {col}")
		>>>
		>>> # Position is automatically cached for fast repeat access
		>>> row2, col2 = calc.calculate(textInfo, terminal)  # Returns cached
		>>>
		>>> # Clear cache when terminal content changes
		>>> calc.clear_cache()

	Performance:
		- First calculation: O(n) where n = row number
		- Cached calculation: O(1)
		- Incremental calculation: O(k) where k = distance moved

	Thread Safety:
		All operations are thread-safe through PositionCache locking.

	Caching Strategy:
		- Cache entries expire after 1000ms
		- Maximum 100 cached positions
		- Automatic invalidation on content changes
	"""

	def __init__(self) -> None:
		"""Initialize the position calculator with empty cache."""
		self._cache = PositionCache()
		self._last_known_position: Optional[Tuple[Any, int, int]] = None

	def calculate(self, textInfo: Any, terminal: Any) -> Tuple[int, int]:
		"""
		Calculate row and column coordinates from TextInfo.

		Uses multi-tiered approach:
		1. Check position cache (1000ms timeout)
		2. Try incremental tracking from last position
		3. Fall back to full calculation from buffer start

		Args:
			textInfo: TextInfo object to calculate position for
			terminal: Terminal object for context

		Returns:
			Tuple of (row, col) as 1-based integers, or (0, 0) on error
		"""
		if not terminal:
			return (0, 0)

		try:
			bookmark = textInfo.bookmark

			# Check cache first
			cached = self._cache.get(bookmark)
			if cached is not None:
				return cached

			# Try incremental tracking
			if self._last_known_position is not None:
				result = self._try_incremental_calculation(
					textInfo, terminal, bookmark
				)
				if result is not None:
					return result

			# Fall back to full calculation
			return self._calculate_full(textInfo, terminal, bookmark)

		except (RuntimeError, AttributeError) as e:
			import logHandler
			logHandler.log.error(f"Terminal Access PositionCalculator: Position access error - {type(e).__name__}: {e}")
			return (0, 0)
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access PositionCalculator: Unexpected error - {type(e).__name__}: {e}")
			return (0, 0)

	def _try_incremental_calculation(self, textInfo: Any, terminal: Any,
									 bookmark: Any) -> Optional[Tuple[int, int]]:
		"""
		Try to calculate position incrementally from last known position.

		Args:
			textInfo: Target TextInfo
			terminal: Terminal object
			bookmark: TextInfo bookmark

		Returns:
			(row, col) tuple if successful, None if incremental not possible
		"""
		try:
			lastBookmark, lastRow, lastCol = self._last_known_position
			lastInfo = terminal.makeTextInfo(lastBookmark)

			# Calculate distance between positions
			comparison = lastInfo.compareEndPoints(textInfo, "startToStart")

			# If close enough (within 10 lines), use incremental
			if abs(comparison) <= 10:
				result = self._calculate_incremental(
					textInfo, lastInfo, lastRow, lastCol, comparison
				)
				if result is not None:
					row, col = result
					# Cache and store
					self._cache.set(bookmark, row, col)
					self._last_known_position = (bookmark, row, col)
					return (row, col)

		except Exception:
			pass

		return None

	def _calculate_incremental(self, targetInfo: Any, lastInfo: Any,
							   lastRow: int, lastCol: int,
							   comparison: int) -> Optional[Tuple[int, int]]:
		"""
		Calculate position incrementally from known position.

		Args:
			targetInfo: Target TextInfo
			lastInfo: Last known TextInfo
			lastRow: Last known row
			lastCol: Last known column
			comparison: Comparison result from compareEndPoints

		Returns:
			(row, col) tuple if successful, None if failed
		"""
		try:
			if comparison == 0:
				return (lastRow, lastCol)  # Same position

			# Clone the last info to avoid modifying it
			workingInfo = lastInfo.copy()

			# Move forward or backward by lines
			if comparison > 0:  # Target is after last position
				linesMovedForward = workingInfo.move(textInfos.UNIT_LINE, comparison)
				newRow = lastRow + linesMovedForward

				# Calculate column
				lineStart = workingInfo.copy()
				lineStart.collapse()
				lineStart.expand(textInfos.UNIT_LINE)
				lineStart.collapse()

				targetCopy = targetInfo.copy()
				targetCopy.collapse()

				# Create range from line start to target and count characters
				charRange = lineStart.copy()
				charRange.setEndPoint(targetCopy, "endToStart")
				charsFromLineStart = len(charRange.text) if charRange.text else 0
				newCol = charsFromLineStart + 1

				return (newRow, newCol)

			else:  # Target is before last position
				linesMovedBack = abs(workingInfo.move(textInfos.UNIT_LINE, comparison))
				newRow = max(1, lastRow - linesMovedBack)

				# Calculate column
				lineStart = workingInfo.copy()
				lineStart.collapse()
				lineStart.expand(textInfos.UNIT_LINE)
				lineStart.collapse()

				targetCopy = targetInfo.copy()
				targetCopy.collapse()

				# Create range from line start to target and count characters
				charRange = lineStart.copy()
				charRange.setEndPoint(targetCopy, "endToStart")
				charsFromLineStart = len(charRange.text) if charRange.text else 0
				newCol = charsFromLineStart + 1

				return (newRow, newCol)

		except Exception:
			return None

	def _calculate_full(self, textInfo: Any, terminal: Any,
					   bookmark: Any) -> Tuple[int, int]:
		"""
		Perform full O(n) position calculation from buffer start.

		Args:
			textInfo: TextInfo to calculate position for
			terminal: Terminal object
			bookmark: TextInfo bookmark

		Returns:
			(row, col) tuple
		"""
		# Start from beginning of buffer
		startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)

		# Calculate row by counting lines
		targetCopy = textInfo.copy()
		targetCopy.collapse()

		# Move to the end of content to get total lines
		startInfo.move(textInfos.UNIT_LINE, 999999, endPoint="end")
		startInfo.collapse(end=False)

		# Count how many lines until target
		lineCount = 0
		while startInfo.compareEndPoints(targetCopy, "startToStart") < 0:
			moved = startInfo.move(textInfos.UNIT_LINE, 1)
			if moved == 0:
				break
			lineCount += 1

		row = lineCount + 1

		# Calculate column by counting characters from line start
		lineStart = targetCopy.copy()
		lineStart.expand(textInfos.UNIT_LINE)
		lineStart.collapse()

		# Create range from line start to target and count characters
		charRange = lineStart.copy()
		charRange.setEndPoint(targetCopy, "endToStart")
		charsFromLineStart = len(charRange.text) if charRange.text else 0
		col = charsFromLineStart + 1

		# Cache and store
		self._cache.set(bookmark, row, col)
		self._last_known_position = (bookmark, row, col)

		return (row, col)

	def clear_cache(self) -> None:
		"""Clear all cached positions."""
		self._cache.clear()
		self._last_known_position = None

	def invalidate_position(self, bookmark: Any) -> None:
		"""
		Invalidate a specific cached position.

		Args:
			bookmark: TextInfo bookmark to invalidate
		"""
		self._cache.invalidate(bookmark)


class SelectionProgressDialog:
	"""
	Properly managed progress dialog with cancellation support.

	This class provides thread-safe progress dialog management for long-running
	selection operations. It handles wx threading issues by ensuring all dialog
	operations happen on the main GUI thread.

	Features:
	- Thread-safe updates using wx.CallAfter
	- User cancellation support
	- Automatic cleanup on completion or cancellation
	- Progress percentage with elapsed/remaining time
	"""

	def __init__(self, parent, title: str, maximum: int) -> None:
		"""
		Initialize progress dialog.

		Args:
			parent: Parent window (typically gui.mainFrame)
			title: Dialog title
			maximum: Maximum progress value (typically 100 for percentage)
		"""
		self._dialog: Optional[Any] = None
		self._cancelled: bool = False
		self._lock: threading.Lock = threading.Lock()
		# Create dialog on main thread
		wx.CallAfter(self._create, parent, title, maximum)
		# Give time for dialog to be created
		time.sleep(0.1)

	def _create(self, parent, title: str, maximum: int) -> None:
		"""
		Create the progress dialog (must be called on main thread).

		Args:
			parent: Parent window
			title: Dialog title
			maximum: Maximum progress value
		"""
		try:
			self._dialog = wx.ProgressDialog(
				title,
				_("Initializing..."),
				maximum=maximum,
				parent=parent,
				style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE |
				      wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME |
				      wx.PD_REMAINING_TIME
			)
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Failed to create progress dialog: {e}")

	def update(self, value: int, message: str) -> bool:
		"""
		Update progress dialog (thread-safe).

		Args:
			value: Current progress value (0 to maximum)
			message: Status message to display

		Returns:
			True if operation should continue, False if cancelled
		"""
		with self._lock:
			if self._cancelled:
				return False

			if self._dialog:
				# Schedule update on main thread
				wx.CallAfter(self._safe_update, value, message)

			return not self._cancelled

	def _safe_update(self, value: int, message: str) -> None:
		"""
		Perform the actual dialog update (called on main thread).

		Args:
			value: Current progress value
			message: Status message to display
		"""
		if self._dialog and not self._cancelled:
			try:
				cont, skip = self._dialog.Update(value, message)
				if not cont:
					# User clicked cancel
					with self._lock:
						self._cancelled = True
			except Exception as e:
				import logHandler
				logHandler.log.error(f"Terminal Access: Progress dialog update failed: {e}")
				with self._lock:
					self._cancelled = True

	def is_cancelled(self) -> bool:
		"""
		Check if operation was cancelled by user.

		Returns:
			True if cancelled, False otherwise
		"""
		with self._lock:
			return self._cancelled

	def close(self) -> None:
		"""
		Close and destroy the progress dialog (thread-safe).
		"""
		with self._lock:
			if self._dialog:
				wx.CallAfter(self._destroy)
				self._dialog = None

	def _destroy(self) -> None:
		"""
		Destroy the dialog (called on main thread).
		"""
		if self._dialog:
			try:
				self._dialog.Destroy()
			except Exception as e:
				import logHandler
				logHandler.log.error(f"Terminal Access: Failed to destroy progress dialog: {e}")


class OperationQueue:
	"""
	Queue system to prevent overlapping background operations.

	Ensures only one long-running operation executes at a time, preventing
	resource exhaustion and UI confusion from multiple simultaneous progress dialogs.
	"""

	def __init__(self) -> None:
		"""Initialize the operation queue."""
		self._active_operation: Optional[threading.Thread] = None
		self._lock: threading.Lock = threading.Lock()

	def is_busy(self) -> bool:
		"""
		Check if an operation is currently running.

		Returns:
			True if operation in progress, False otherwise
		"""
		with self._lock:
			return self._active_operation is not None and self._active_operation.is_alive()

	def start_operation(self, thread: threading.Thread) -> bool:
		"""
		Start a new operation if queue is free.

		Args:
			thread: Thread to start

		Returns:
			True if operation started, False if queue busy
		"""
		with self._lock:
			# Clean up completed thread
			if self._active_operation and not self._active_operation.is_alive():
				self._active_operation = None

			# Check if queue is free
			if self._active_operation:
				return False

			# Start new operation
			self._active_operation = thread
			thread.start()
			return True

	def clear(self) -> None:
		"""
		Clear the active operation reference.

		Note: This does not stop the thread, just clears the reference.
		The thread should complete or be cancelled naturally.
		"""
		with self._lock:
			self._active_operation = None


class WindowMonitor:
	"""
	Monitor multiple windows for content changes with background polling.

	Section 6.1: Multiple Simultaneous Window Monitoring (v1.0.28+)

	This class enables monitoring of multiple terminal windows/regions simultaneously,
	detecting changes and announcing them to the user. Useful for monitoring:
	- Build output in split panes
	- Log file tails in tmux/screen
	- System status bars
	- Chat messages in IRC clients
	- Background processes

	Features:
	- Multiple simultaneous window monitoring
	- Configurable polling intervals per window
	- Change detection with diff strategies
	- Rate limiting to prevent announcement spam
	- Background thread-based monitoring
	- Thread-safe operations

	Example usage:
		>>> monitor = WindowMonitor(terminal_obj, position_calculator)
		>>> monitor.add_monitor("build", (1, 1, 10, 80), interval_ms=1000)
		>>> monitor.add_monitor("logs", (11, 1, 20, 80), interval_ms=500)
		>>> monitor.start_monitoring()
		>>> # ... monitoring runs in background ...
		>>> monitor.stop_monitoring()
	"""

	def __init__(self, terminal_obj, position_calculator):
		"""
		Initialize the WindowMonitor.

		Args:
			terminal_obj: Terminal TextInfo object for content extraction
			position_calculator: PositionCalculator instance for coordinate mapping
		"""
		self._terminal = terminal_obj
		self._position_calculator = position_calculator
		self._monitors = []  # List of monitor configurations
		self._last_content = {}  # window_name -> content mapping
		self._last_announcement = {}  # window_name -> timestamp of last announcement
		self._monitor_thread = None
		self._monitoring_active = False
		self._lock = threading.Lock()
		self._min_announcement_interval = 2000  # Minimum 2 seconds between announcements (rate limiting)

	def add_monitor(self, name: str, window_bounds: tuple, interval_ms: int = 500, mode: str = 'changes'):
		"""
		Add a window to monitor.

		Args:
			name: Unique identifier for this monitor
			window_bounds: Tuple of (top, left, bottom, right) coordinates (1-based)
			interval_ms: Polling interval in milliseconds (default: 500ms)
			mode: Announcement mode - 'changes' (announce changes), 'silent' (track only)

		Returns:
			bool: True if monitor added successfully
		"""
		with self._lock:
			# Check if monitor with this name already exists
			if any(m['name'] == name for m in self._monitors):
				return False

			# Validate window bounds
			top, left, bottom, right = window_bounds
			if not (1 <= top <= bottom and 1 <= left <= right):
				return False

			monitor = {
				'name': name,
				'bounds': window_bounds,
				'interval': interval_ms,
				'mode': mode,
				'last_check': 0,
				'enabled': True
			}
			self._monitors.append(monitor)
			self._last_content[name] = None
			self._last_announcement[name] = 0
			return True

	def remove_monitor(self, name: str) -> bool:
		"""
		Remove a monitor by name.

		Args:
			name: Monitor identifier

		Returns:
			bool: True if monitor removed successfully
		"""
		with self._lock:
			for i, monitor in enumerate(self._monitors):
				if monitor['name'] == name:
					self._monitors.pop(i)
					self._last_content.pop(name, None)
					self._last_announcement.pop(name, None)
					return True
			return False

	def enable_monitor(self, name: str) -> bool:
		"""Enable a specific monitor."""
		with self._lock:
			for monitor in self._monitors:
				if monitor['name'] == name:
					monitor['enabled'] = True
					return True
			return False

	def disable_monitor(self, name: str) -> bool:
		"""Disable a specific monitor."""
		with self._lock:
			for monitor in self._monitors:
				if monitor['name'] == name:
					monitor['enabled'] = False
					return True
			return False

	def start_monitoring(self) -> bool:
		"""
		Start background monitoring thread.

		Returns:
			bool: True if monitoring started successfully
		"""
		with self._lock:
			if self._monitoring_active:
				return False

			if not self._monitors:
				return False

			self._monitoring_active = True
			self._monitor_thread = threading.Thread(
				target=self._monitor_loop,
				daemon=True
			)
			self._monitor_thread.start()
			return True

	def stop_monitoring(self) -> None:
		"""Stop background monitoring thread."""
		with self._lock:
			self._monitoring_active = False

		# Wait for thread to finish
		if self._monitor_thread and self._monitor_thread.is_alive():
			self._monitor_thread.join(timeout=2.0)
		self._monitor_thread = None

	def is_monitoring(self) -> bool:
		"""Check if monitoring is active."""
		with self._lock:
			return self._monitoring_active

	def _monitor_loop(self) -> None:
		"""Background monitoring loop."""
		while True:
			with self._lock:
				if not self._monitoring_active:
					break

				current_time = time.time() * 1000  # Convert to milliseconds

				# Check each monitor
				for monitor in self._monitors:
					if not monitor['enabled']:
						continue

					# Check if it's time to poll this monitor
					time_since_check = current_time - monitor['last_check']
					if time_since_check >= monitor['interval']:
						self._check_window(monitor, current_time)
						monitor['last_check'] = current_time

			# Sleep briefly to avoid busy-waiting
			time.sleep(0.1)

	def _check_window(self, monitor: dict, current_time: float) -> None:
		"""
		Check if window content changed.

		Args:
			monitor: Monitor configuration dictionary
			current_time: Current timestamp in milliseconds
		"""
		try:
			# Extract window content
			content = self._extract_window_content(monitor['bounds'])
			name = monitor['name']
			last_content = self._last_content.get(name)

			# Content changed?
			if content != last_content:
				self._last_content[name] = content

				# Should we announce this change?
				if monitor['mode'] == 'changes':
					# Rate limiting: check if enough time passed since last announcement
					time_since_announcement = current_time - self._last_announcement.get(name, 0)
					if time_since_announcement >= self._min_announcement_interval:
						self._announce_change(name, content, last_content)
						self._last_announcement[name] = current_time

		except Exception:
			# Silently ignore errors to avoid disrupting monitoring
			pass

	def _extract_window_content(self, bounds: tuple) -> str:
		"""
		Extract text content from window bounds.

		Args:
			bounds: Tuple of (top, left, bottom, right) coordinates

		Returns:
			str: Window content as text
		"""
		if not self._terminal:
			return ""

		top, left, bottom, right = bounds
		lines = []

		try:
			# Get terminal dimensions
			info = self._terminal.makeTextInfo(textInfos.POSITION_ALL)
			all_text = info.text

			# Split into lines
			all_lines = all_text.split('\n')

			# Extract lines within bounds (convert from 1-based to 0-based)
			for row_idx in range(top - 1, min(bottom, len(all_lines))):
				if row_idx < len(all_lines):
					line = all_lines[row_idx]
					# Extract columns within bounds (1-based to 0-based)
					col_start = max(0, left - 1)
					col_end = min(len(line), right)
					lines.append(line[col_start:col_end])

			return '\n'.join(lines)

		except Exception:
			return ""

	def _announce_change(self, name: str, new_content: str, old_content: str) -> None:
		"""
		Announce content change to user.

		Args:
			name: Monitor name
			new_content: New window content
			old_content: Previous window content
		"""
		# Calculate change summary
		if old_content is None:
			# First content - don't announce
			return

		# Simple announcement: just say window changed
		# More sophisticated diff could be added here
		try:
			message = _("Window {name} changed").format(name=name)
			ui.message(message)
		except Exception:
			pass

	def get_monitor_status(self) -> list:
		"""
		Get status of all monitors.

		Returns:
			list: List of monitor status dictionaries
		"""
		with self._lock:
			return [
				{
					'name': m['name'],
					'bounds': m['bounds'],
					'interval': m['interval'],
					'mode': m['mode'],
					'enabled': m['enabled']
				}
				for m in self._monitors
			]


class TabManager:
	"""
	Manage terminal tabs for quick navigation and state tracking.

	Section 9: Tab Management Functionality (v1.0.39+)

	This class enables users to detect, navigate, and manage tabs within terminal
	applications like Windows Terminal, allowing for tab-aware bookmark and search
	state management.

	Features:
	- Tab detection using window properties and content heuristics
	- Tab navigation with keyboard shortcuts
	- Per-tab state isolation for bookmarks, searches, and command history
	- Tab listing and enumeration
	- Support for multiple terminal applications

	Example usage:
		>>> manager = TabManager(terminal_obj)
		>>> tab_id = manager.get_current_tab_id()
		>>> manager.list_tabs()
		>>> manager.switch_to_tab(1)
	"""

	def __init__(self, terminal_obj):
		"""
		Initialize the TabManager.

		Args:
			terminal_obj: Terminal TextInfo object
		"""
		self._terminal = terminal_obj
		self._tabs = {}  # tab_id -> tab_info mapping
		self._current_tab_id = None
		self._last_window_title = None
		self._update_current_tab()

	def _generate_tab_id(self, terminal_obj) -> str:
		"""
		Generate a unique tab identifier based on terminal properties.

		Uses window handle, title, and content hash to create a unique ID.

		Args:
			terminal_obj: Terminal TextInfo object

		Returns:
			str: Unique tab identifier
		"""
		try:
			# Try to get window properties
			components = []

			# Add window handle if available
			if hasattr(terminal_obj, 'windowHandle'):
				components.append(str(terminal_obj.windowHandle))

			# Add window text/title if available
			if hasattr(terminal_obj, 'windowText'):
				components.append(terminal_obj.windowText or "")
			elif hasattr(terminal_obj, 'name'):
				components.append(terminal_obj.name or "")

			# Add object ID if available
			if hasattr(terminal_obj, '_get_ID'):
				try:
					obj_id = terminal_obj._get_ID()
					components.append(str(obj_id))
				except Exception:
					pass

			# Create hash from components
			import hashlib
			tab_str = "|".join(components)
			tab_hash = hashlib.md5(tab_str.encode()).hexdigest()[:12]

			return tab_hash

		except Exception:
			# Fallback to simple counter-based ID
			return f"tab_{len(self._tabs)}"

	def _update_current_tab(self):
		"""Update information about the currently focused tab."""
		try:
			tab_id = self._generate_tab_id(self._terminal)

			# Register tab if it's new
			if tab_id not in self._tabs:
				self._tabs[tab_id] = {
					'id': tab_id,
					'title': self._get_tab_title(),
					'created': None,  # Could add timestamp
					'last_accessed': None
				}

			self._current_tab_id = tab_id

			# Update title cache
			self._last_window_title = self._get_tab_title()

		except Exception:
			pass

	def _get_tab_title(self) -> str:
		"""
		Get the title of the current tab.

		Returns:
			str: Tab title or empty string
		"""
		try:
			if hasattr(self._terminal, 'windowText'):
				return self._terminal.windowText or ""
			elif hasattr(self._terminal, 'name'):
				return self._terminal.name or ""
		except Exception:
			pass
		return ""

	def get_current_tab_id(self) -> str:
		"""
		Get the identifier of the currently focused tab.

		Returns:
			str: Current tab ID or None
		"""
		return self._current_tab_id

	def list_tabs(self) -> list:
		"""
		Get list of all known tabs.

		Returns:
			list: List of tab info dictionaries
		"""
		return list(self._tabs.values())

	def get_tab_count(self) -> int:
		"""
		Get number of known tabs.

		Returns:
			int: Number of tabs
		"""
		return len(self._tabs)

	def update_terminal(self, terminal_obj):
		"""
		Update the terminal reference and check for tab changes.

		This should be called when the terminal is rebound to detect
		tab switches and update tab tracking.

		Args:
			terminal_obj: New terminal TextInfo object
		"""
		self._terminal = terminal_obj
		old_tab_id = self._current_tab_id
		self._update_current_tab()

		# Return True if tab changed
		return self._current_tab_id != old_tab_id

	def has_tab_changed(self) -> bool:
		"""
		Check if the tab has changed since last check.

		Returns:
			bool: True if tab appears to have changed
		"""
		try:
			current_title = self._get_tab_title()
			if current_title != self._last_window_title:
				self._last_window_title = current_title
				self._update_current_tab()
				return True
		except Exception:
			pass
		return False

	def clear_tab_info(self, tab_id: str) -> bool:
		"""
		Remove information about a specific tab.

		Args:
			tab_id: Tab identifier

		Returns:
			bool: True if tab was removed
		"""
		if tab_id in self._tabs:
			del self._tabs[tab_id]
			return True
		return False

	def clear_all_tabs(self):
		"""Clear all tab information."""
		self._tabs.clear()
		self._current_tab_id = None


class BookmarkManager:
	"""
	Manage bookmarks/markers in terminal output for quick navigation.

	Section 8.3: Bookmark/Marker Functionality (v1.0.29+)

	This class enables users to set named bookmarks at specific positions in
	the terminal output and quickly jump back to those positions. Useful for:
	- Marking important log entries
	- Saving positions in long output
	- Navigating back to command results
	- Quick navigation in code review sessions

	Features:
	- Named bookmarks (0-9 and custom names)
	- Quick jump to bookmarks
	- List all bookmarks
	- Remove bookmarks
	- Persistent across terminal sessions (position-relative)

	Example usage:
		>>> manager = BookmarkManager(terminal_obj)
		>>> manager.set_bookmark("1")  # Quick bookmark with number
		>>> manager.set_bookmark("build_error")  # Named bookmark
		>>> manager.jump_to_bookmark("1")
		>>> manager.list_bookmarks()
		>>> manager.remove_bookmark("1")
	"""

	def __init__(self, terminal_obj, tab_manager=None):
		"""
		Initialize the BookmarkManager.

		Args:
			terminal_obj: Terminal TextInfo object for bookmark storage
			tab_manager: Optional TabManager for tab-aware bookmark storage
		"""
		self._terminal = terminal_obj
		self._tab_manager = tab_manager
		self._bookmarks = {}  # name -> bookmark mapping (legacy single-tab mode)
		self._tab_bookmarks = {}  # tab_id -> {name -> bookmark} mapping (multi-tab mode)
		self._max_bookmarks = 50  # Maximum number of bookmarks per tab

	def _get_current_tab_id(self) -> str:
		"""Get current tab ID, or None if no tab manager."""
		if self._tab_manager:
			return self._tab_manager.get_current_tab_id()
		return None

	def _get_bookmark_dict(self):
		"""Get the appropriate bookmark dictionary for the current context."""
		tab_id = self._get_current_tab_id()
		if tab_id:
			# Multi-tab mode: use per-tab storage
			if tab_id not in self._tab_bookmarks:
				self._tab_bookmarks[tab_id] = {}
			return self._tab_bookmarks[tab_id]
		else:
			# Legacy mode: use shared storage
			return self._bookmarks

	def set_bookmark(self, name: str) -> bool:
		"""
		Set bookmark at current review position.

		Args:
			name: Bookmark name (e.g., "1", "error", "important")

		Returns:
			bool: True if bookmark set successfully
		"""
		if not self._terminal:
			return False

		# Validate bookmark name
		if not name or len(name) > 50:
			return False

		bookmarks = self._get_bookmark_dict()

		# Check max bookmarks limit
		if name not in bookmarks and len(bookmarks) >= self._max_bookmarks:
			return False

		try:
			# Get current review position
			pos = api.getReviewPosition()
			if not pos:
				return False

			# Store bookmark
			bookmarks[name] = pos.bookmark
			return True

		except Exception:
			return False

	def jump_to_bookmark(self, name: str) -> bool:
		"""
		Jump to named bookmark.

		Args:
			name: Bookmark name

		Returns:
			bool: True if jump successful
		"""
		bookmarks = self._get_bookmark_dict()
		if not self._terminal or name not in bookmarks:
			return False

		try:
			# Restore position from bookmark
			pos = self._terminal.makeTextInfo(bookmarks[name])
			if pos:
				api.setReviewPosition(pos)
				return True

		except Exception:
			# Bookmark may be invalid (terminal content changed)
			self.remove_bookmark(name)

		return False

	def remove_bookmark(self, name: str) -> bool:
		"""
		Remove named bookmark.

		Args:
			name: Bookmark name

		Returns:
			bool: True if bookmark removed
		"""
		bookmarks = self._get_bookmark_dict()
		if name in bookmarks:
			del bookmarks[name]
			return True
		return False

	def list_bookmarks(self) -> list:
		"""
		Get list of all bookmark names for the current tab.

		Returns:
			list: List of bookmark names (sorted)
		"""
		bookmarks = self._get_bookmark_dict()
		return sorted(bookmarks.keys())

	def has_bookmark(self, name: str) -> bool:
		"""
		Check if bookmark exists in the current tab.

		Args:
			name: Bookmark name

		Returns:
			bool: True if bookmark exists
		"""
		bookmarks = self._get_bookmark_dict()
		return name in bookmarks

	def clear_all(self) -> None:
		"""Clear all bookmarks for the current tab."""
		bookmarks = self._get_bookmark_dict()
		bookmarks.clear()

	def get_bookmark_count(self) -> int:
		"""Get number of bookmarks for the current tab."""
		bookmarks = self._get_bookmark_dict()
		return len(bookmarks)

	def update_terminal(self, terminal_obj):
		"""
		Update the terminal reference.

		This should be called when the terminal is rebound to ensure
		bookmarks can be properly retrieved.

		Args:
			terminal_obj: New terminal TextInfo object
		"""
		self._terminal = terminal_obj

	def set_tab_manager(self, tab_manager):
		"""
		Set or update the tab manager for tab-aware bookmark storage.

		Args:
			tab_manager: TabManager instance
		"""
		self._tab_manager = tab_manager


class OutputSearchManager:
	"""
	Search and filter terminal output with pattern matching.

	Section 8.2: Output Filtering and Search (v1.0.30+)

	This class enables users to search through terminal output using text patterns
	or regular expressions, navigate between matches, and filter output. Useful for:
	- Finding error messages in logs
	- Locating specific command output
	- Filtering build output for warnings
	- Searching through help text
	- Finding specific entries in terminal history

	Features:
	- Text search with case sensitivity option
	- Regular expression support
	- Navigate forward/backward through matches
	- Show match count
	- Jump to first/last match
	- Wrap-around search

	Example usage:
		>>> manager = OutputSearchManager(terminal_obj)
		>>> manager.search("error", case_sensitive=False)
		>>> manager.next_match()  # Jump to next occurrence
		>>> manager.previous_match()  # Jump to previous occurrence
		>>> manager.get_match_count()  # Get total matches
	"""

	def __init__(self, terminal_obj, tab_manager=None):
		"""
		Initialize the OutputSearchManager.

		Args:
			terminal_obj: Terminal TextInfo object for searching
			tab_manager: Optional TabManager for tab-aware search storage
		"""
		self._terminal = terminal_obj
		self._tab_manager = tab_manager
		# Legacy single-tab storage
		self._pattern = None
		self._matches = []  # List of (bookmark, line_text, line_num) tuples
		self._current_match_index = -1
		self._case_sensitive = False
		self._use_regex = False
		# Per-tab storage
		self._tab_searches = {}  # tab_id -> {pattern, matches, index, case_sensitive, use_regex}

	def _get_current_tab_id(self) -> str:
		"""Get current tab ID, or None if no tab manager."""
		if self._tab_manager:
			return self._tab_manager.get_current_tab_id()
		return None

	def _get_search_state(self):
		"""Get the appropriate search state dict for the current context."""
		tab_id = self._get_current_tab_id()
		if tab_id:
			# Multi-tab mode: use per-tab storage
			if tab_id not in self._tab_searches:
				self._tab_searches[tab_id] = {
					'pattern': None,
					'matches': [],
					'current_match_index': -1,
					'case_sensitive': False,
					'use_regex': False
				}
			return self._tab_searches[tab_id]
		else:
			# Legacy mode: use instance variables
			return {
				'pattern': self._pattern,
				'matches': self._matches,
				'current_match_index': self._current_match_index,
				'case_sensitive': self._case_sensitive,
				'use_regex': self._use_regex
			}

	def _save_search_state(self, state):
		"""Save search state to the appropriate storage."""
		tab_id = self._get_current_tab_id()
		if tab_id:
			# Multi-tab mode
			self._tab_searches[tab_id] = state
		else:
			# Legacy mode
			self._pattern = state['pattern']
			self._matches = state['matches']
			self._current_match_index = state['current_match_index']
			self._case_sensitive = state['case_sensitive']
			self._use_regex = state['use_regex']

	def search(self, pattern: str, case_sensitive: bool = False, use_regex: bool = False) -> int:
		"""
		Search for pattern in terminal output.

		Args:
			pattern: Search pattern (text or regex)
			case_sensitive: Case sensitive search
			use_regex: Use regular expression

		Returns:
			int: Number of matches found
		"""
		if not self._terminal or not pattern:
			return 0

		self._pattern = pattern
		self._case_sensitive = case_sensitive
		self._use_regex = use_regex
		self._matches = []
		self._current_match_index = -1

		try:
			# Get all terminal content
			info = self._terminal.makeTextInfo(textInfos.POSITION_ALL)
			all_text = info.text

			if not all_text:
				return 0

			# Split into lines
			lines = all_text.split('\n')

			# Search each line
			if use_regex:
				import re
				flags = 0 if case_sensitive else re.IGNORECASE
				regex = re.compile(pattern, flags)

				for line_num, line_text in enumerate(lines, 1):
					if regex.search(line_text):
						# Create bookmark for this line
						line_info = self._terminal.makeTextInfo(textInfos.POSITION_FIRST)
						line_info.move(textInfos.UNIT_LINE, line_num - 1)
						self._matches.append((line_info.bookmark, line_text, line_num))
			else:
				# Simple text search
				search_pattern = pattern if case_sensitive else pattern.lower()

				for line_num, line_text in enumerate(lines, 1):
					search_text = line_text if case_sensitive else line_text.lower()
					if search_pattern in search_text:
						# Create bookmark for this line
						line_info = self._terminal.makeTextInfo(textInfos.POSITION_FIRST)
						line_info.move(textInfos.UNIT_LINE, line_num - 1)
						self._matches.append((line_info.bookmark, line_text, line_num))

			return len(self._matches)

		except Exception:
			return 0

	def next_match(self) -> bool:
		"""
		Jump to next match.

		Returns:
			bool: True if jumped to next match
		"""
		if not self._matches:
			return False

		# Move to next match (wrap around)
		self._current_match_index = (self._current_match_index + 1) % len(self._matches)
		return self._jump_to_current_match()

	def previous_match(self) -> bool:
		"""
		Jump to previous match.

		Returns:
			bool: True if jumped to previous match
		"""
		if not self._matches:
			return False

		# Move to previous match (wrap around)
		self._current_match_index = (self._current_match_index - 1) % len(self._matches)
		return self._jump_to_current_match()

	def first_match(self) -> bool:
		"""
		Jump to first match.

		Returns:
			bool: True if jumped to first match
		"""
		if not self._matches:
			return False

		self._current_match_index = 0
		return self._jump_to_current_match()

	def last_match(self) -> bool:
		"""
		Jump to last match.

		Returns:
			bool: True if jumped to last match
		"""
		if not self._matches:
			return False

		self._current_match_index = len(self._matches) - 1
		return self._jump_to_current_match()

	def _jump_to_current_match(self) -> bool:
		"""
		Jump to current match index.

		Returns:
			bool: True if jump successful
		"""
		if not self._matches or self._current_match_index < 0:
			return False

		try:
			bookmark, line_text, line_num = self._matches[self._current_match_index]
			pos = self._terminal.makeTextInfo(bookmark)
			if pos:
				api.setReviewPosition(pos)
				return True
		except Exception:
			pass

		return False

	def get_match_count(self) -> int:
		"""
		Get total number of matches.

		Returns:
			int: Number of matches
		"""
		return len(self._matches)

	def get_current_match_info(self) -> tuple:
		"""
		Get information about current match.

		Returns:
			tuple: (match_number, total_matches, line_text, line_num) or None
		"""
		if not self._matches or self._current_match_index < 0:
			return None

		_, line_text, line_num = self._matches[self._current_match_index]
		return (self._current_match_index + 1, len(self._matches), line_text, line_num)

	def clear_search(self) -> None:
		"""Clear current search results."""
		self._pattern = None
		self._matches = []
		self._current_match_index = -1

	def update_terminal(self, terminal_obj):
		"""
		Update the terminal reference.

		This should be called when the terminal is rebound to ensure
		searches can be properly performed.

		Args:
			terminal_obj: New terminal TextInfo object
		"""
		self._terminal = terminal_obj
		# Clear search results when terminal changes
		self.clear_search()

	def set_tab_manager(self, tab_manager):
		"""
		Set or update the tab manager for tab-aware search storage.

		Args:
			tab_manager: TabManager instance
		"""
		self._tab_manager = tab_manager


class CommandHistoryManager:
	"""
	Navigate through command history in terminal output.

	Section 8.1: Command History Navigation (v1.0.31+)

	This class detects and stores commands from terminal output by parsing
	common shell prompts and extracting command text. Users can navigate
	through the command history to review previously executed commands.

	Features:
	- Automatic command detection from output
	- Support for multiple shell prompt formats:
	  * Bash: `$`, `#`, custom PS1
	  * PowerShell: `PS>`, `PS C:\\>`, custom prompts
	  * Windows CMD: drive letter prompts (e.g., `C:\\>`)
	  * WSL: Linux prompts
	- Navigate through command history (previous/next)
	- Jump to specific command
	- List command history
	- Configurable history size

	Example usage:
		>>> manager = CommandHistoryManager(terminal_obj)
		>>> manager.detect_and_store_commands()
		>>> manager.navigate_history(-1)  # Previous command
		>>> manager.navigate_history(1)   # Next command
		>>> manager.list_history()
	"""

	def __init__(self, terminal_obj, max_history=100, tab_manager=None):
		"""
		Initialize the CommandHistoryManager.

		Args:
			terminal_obj: Terminal TextInfo object for reading content
			max_history: Maximum number of commands to store (default: 100)
			tab_manager: Optional TabManager for tab-aware command history storage
		"""
		self._terminal = terminal_obj
		self._max_history = max_history
		self._tab_manager = tab_manager
		# Legacy single-tab storage
		self._history = []  # List of (line_num, command_text, bookmark) tuples
		self._current_index = -1  # Current position in history (-1 = not navigating)
		self._last_scan_line = 0  # Last line scanned for commands
		# Per-tab storage
		self._tab_histories = {}  # tab_id -> {history, current_index, last_scan_line}

		# Common prompt patterns (regex)
		import re
		self._prompt_patterns = [
			# Bash prompts: user@host:~$, root@host:#, simple $/#
			re.compile(r'^[\w\-\.]+@[\w\-\.]+:[^\$#]*[\$#]\s*(.+)$'),
			re.compile(r'^[\$#]\s*(.+)$'),

			# PowerShell prompts: PS>, PS C:\>, PS /home/user>
			re.compile(r'^PS\s+[A-Za-z]:[^>]*>\s*(.+)$'),
			re.compile(r'^PS\s+/[^>]*>\s*(.+)$'),
			re.compile(r'^PS>\s*(.+)$'),

			# Windows CMD prompts: C:\>, D:\Users\name>
			re.compile(r'^[A-Za-z]:[^>]*>\s*(.+)$'),

			# Generic prompt with colon or arrow
			re.compile(r'^[^\s>:]+[>:]\s*(.+)$'),
		]

	def detect_and_store_commands(self) -> int:
		"""
		Scan terminal output for new commands and store them.

		Returns:
			Number of new commands detected
		"""
		if not self._terminal:
			return 0

		try:
			# Get all terminal content
			info = self._terminal.makeTextInfo(textInfos.POSITION_ALL)
			content = info.text

			if not content:
				return 0

			lines = content.split('\n')
			new_commands = 0

			# Scan from last scan position to end
			for line_num in range(self._last_scan_line, len(lines)):
				line = lines[line_num].strip()

				if not line:
					continue

				# Try to match against prompt patterns
				for pattern in self._prompt_patterns:
					match = pattern.match(line)
					if match:
						command_text = match.group(1).strip()

						# Ignore empty commands or very short ones
						if len(command_text) < 2:
							continue

						# Check if this is a duplicate of last command
						if self._history and self._history[-1][1] == command_text:
							continue

						# Create bookmark at this line for navigation
						try:
							line_info = self._terminal.makeTextInfo(textInfos.POSITION_ALL)
							# Move to the specific line
							for _ in range(line_num):
								line_info.move(textInfos.UNIT_LINE, 1)

							bookmark = line_info.bookmark

							# Store command (line_num, command_text, bookmark)
							self._history.append((line_num, command_text, bookmark))
							new_commands += 1

							# Limit history size
							if len(self._history) > self._max_history:
								self._history.pop(0)

						except Exception:
							# Bookmark creation failed, skip this command
							pass

						break  # Found a match, no need to try other patterns

			# Update last scan position
			self._last_scan_line = len(lines)

			return new_commands

		except Exception:
			return 0

	def navigate_history(self, direction: int) -> bool:
		"""
		Navigate through command history.

		Args:
			direction: -1 for previous, 1 for next

		Returns:
			True if navigation successful, False otherwise
		"""
		if not self._history:
			return False

		# If not currently navigating, start from the end
		if self._current_index == -1:
			if direction < 0:
				self._current_index = len(self._history) - 1
			else:
				self._current_index = 0
		else:
			# Move index
			self._current_index += direction

			# Clamp to valid range
			if self._current_index < 0:
				self._current_index = 0
				return False
			elif self._current_index >= len(self._history):
				self._current_index = len(self._history) - 1
				return False

		# Jump to the command position
		return self._jump_to_command(self._current_index)

	def _jump_to_command(self, index: int) -> bool:
		"""
		Jump to a specific command in history.

		Args:
			index: Index in history list

		Returns:
			True if jump successful, False otherwise
		"""
		if index < 0 or index >= len(self._history):
			return False

		try:
			line_num, command_text, bookmark = self._history[index]

			# Move to the bookmark
			info = self._terminal.makeTextInfo(bookmark)
			api.setReviewPosition(info)

			# Announce the command
			from . import ui
			ui.message(f"Command {index + 1} of {len(self._history)}: {command_text}")

			return True

		except Exception:
			return False

	def jump_to_command(self, index: int) -> bool:
		"""
		Jump directly to a command by index (1-based).

		Args:
			index: Command number (1-based)

		Returns:
			True if jump successful, False otherwise
		"""
		if index < 1 or index > len(self._history):
			return False

		self._current_index = index - 1
		return self._jump_to_command(self._current_index)

	def list_history(self) -> list:
		"""
		Get list of all commands in history.

		Returns:
			List of (index, command_text) tuples
		"""
		return [(i + 1, cmd[1]) for i, cmd in enumerate(self._history)]

	def get_current_command(self) -> str:
		"""
		Get the currently selected command.

		Returns:
			Command text or empty string
		"""
		if self._current_index >= 0 and self._current_index < len(self._history):
			return self._history[self._current_index][1]
		return ""

	def clear_history(self) -> None:
		"""Clear all command history."""
		self._history.clear()
		self._current_index = -1
		self._last_scan_line = 0

	def get_history_count(self) -> int:
		"""Get number of commands in history."""
		return len(self._history)

	def update_terminal(self, terminal_obj):
		"""
		Update the terminal reference.

		This should be called when the terminal is rebound to ensure
		history navigation can be properly performed.

		Args:
			terminal_obj: New terminal TextInfo object
		"""
		self._terminal = terminal_obj
		# Clear history when terminal changes
		self.clear_history()

	def set_tab_manager(self, tab_manager):
		"""
		Set or update the tab manager for tab-aware command history storage.

		Args:
			tab_manager: TabManager instance
		"""
		self._tab_manager = tab_manager


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""
	Terminal Access Global Plugin for NVDA

	Provides enhanced terminal accessibility for Windows Terminal, PowerShell,
	Command Prompt, and other console applications.

	==== KEYBOARD GESTURES (Phase 7: Documented Gesture Patterns) ====

	Navigation (Line-based):
		NVDA+Alt+U - Previous line
		NVDA+Alt+I - Current line (double-press: indentation level)
		NVDA+Alt+O - Next line

	Navigation (Word-based):
		NVDA+Alt+J - Previous word
		NVDA+Alt+K - Current word (double-press: spell word)
		NVDA+Alt+L - Next word

	Navigation (Character-based):
		NVDA+Alt+M          - Previous character
		NVDA+Alt+Comma      - Current character (double: phonetic, triple: code)
		NVDA+Alt+Period     - Next character

	Navigation (Boundary Movement):
		NVDA+Alt+Home       - Move to start of current line
		NVDA+Alt+End        - Move to end of current line
		NVDA+Alt+PageUp     - Move to top of buffer
		NVDA+Alt+PageDown   - Move to bottom of buffer

	Reading (Directional):
		NVDA+Alt+Shift+Left  - Read from cursor to start of line
		NVDA+Alt+Shift+Right - Read from cursor to end of line
		NVDA+Alt+Shift+Up    - Read from cursor to top of buffer
		NVDA+Alt+Shift+Down  - Read from cursor to bottom of buffer

	Information and Attributes:
		NVDA+Alt+P           - Announce cursor position (row, column)
		NVDA+Alt+A           - Say All (continuous reading)
		NVDA+Alt+Shift+A     - Read color and formatting attributes

	Selection and Copying:
		NVDA+Alt+R           - Toggle mark (start/end/clear)
		NVDA+Alt+C           - Copy linear selection (between marks)
		NVDA+Alt+Shift+C     - Copy rectangular selection (columns)
		NVDA+Alt+X           - Clear selection marks
		NVDA+Alt+V           - Enter copy mode (line/screen)

	Window Management:
		NVDA+Alt+F2          - Define screen window (two-step)
		NVDA+Alt+F3          - Clear screen window
		NVDA+Alt+Plus        - Read window content
		NVDA+Alt+Asterisk    - Cycle cursor tracking mode

	Configuration:
		NVDA+Alt+Q           - Toggle quiet mode
		NVDA+Alt+[           - Decrease punctuation level
		NVDA+Alt+]           - Increase punctuation level
		NVDA+Alt+F5          - Toggle automatic indentation announcement
		NVDA+Alt+F10         - Announce active and default profiles

	Help:
		NVDA+Shift+F1        - Open Terminal Access user guide

	==== DESIGN PATTERNS ====
	- Base navigation: NVDA+Alt+{letter}
	- Extended operations: NVDA+Alt+Shift+{letter}
	- Line navigation: U/I/O (vertical cluster on keyboard)
	- Word navigation: J/K/L (horizontal cluster on keyboard)
	- Character navigation: M/Comma/Period (right hand cluster)
	- Boundaries: Home/End/PageUp/PageDown (standard nav keys)
	- Directional reading: Arrow keys with Shift modifier
	- Selection: R (mark), C (copy), X (clear)
	- Punctuation: Bracket keys [ and ]

	==== CURSOR TRACKING MODES ====
	0 - Off: No automatic tracking
	1 - Standard: Follow system caret
	2 - Highlight: Track highlighted/selected text
	3 - Window: Track within defined screen region
	"""
	
	def __init__(self):
		"""Initialize the Terminal Access global plugin."""
		super(GlobalPlugin, self).__init__()

		# Initialize manager classes for configuration, windows, and position tracking
		self._configManager = ConfigManager()
		self._windowManager = WindowManager(self._configManager)
		self._positionCalculator = PositionCalculator()

		# Initialize state variables
		self.lastTerminalAppName = None
		self.announcedHelp = False
		self.copyMode = False
		self._boundTerminal = None
		self._cursorTrackingTimer = None
		self._lastCaretPosition = None
		self._lastTypedChar = None
		self._repeatedCharCount = 0

		# Highlight tracking state
		self._lastHighlightedText = None
		self._lastHighlightPosition = None

		# Enhanced selection state
		self._markStart = None
		self._markEnd = None

		# Background calculation thread for long operations
		self._backgroundCalculationThread = None

		# Operation queue to prevent overlapping background operations (Section 1.3)
		self._operationQueue = OperationQueue()

		# Application profile management
		self._profileManager = ProfileManager()
		self._currentProfile = None

		# Window monitor for multi-window monitoring (Section 6.1 - v1.0.28+)
		self._windowMonitor = None  # Initialized when terminal is bound

		# Tab manager for managing terminal tabs (Section 9 - v1.0.39+)
		self._tabManager = None  # Initialized when terminal is bound

		# Bookmark manager for quick navigation (Section 8.3 - v1.0.29+)
		self._bookmarkManager = None  # Initialized when terminal is bound

		# Output search manager for filtering and search (Section 8.2 - v1.0.30+)
		self._searchManager = None  # Initialized when terminal is bound

		# Command history manager for navigation (Section 8.1 - v1.0.31+)
		self._commandHistoryManager = None  # Initialized when terminal is bound

		# Add settings panel to NVDA preferences
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(TerminalAccessSettingsPanel)
		except (AttributeError, TypeError, RuntimeError):
			# GUI may not be fully initialized yet, which is acceptable
			# Settings panel will not be available in this case
			pass

	def terminate(self):
		"""Clean up when the plugin is terminated."""
		# Stop window monitoring if active
		if self._windowMonitor and self._windowMonitor.is_monitoring():
			self._windowMonitor.stop_monitoring()

		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(TerminalAccessSettingsPanel)
		except (ValueError, AttributeError):
			pass
		super(GlobalPlugin, self).terminate()
	
	def isTerminalApp(self, obj=None):
		"""
		Check if the current application is a supported terminal.

		Supports built-in Windows terminals, popular third-party terminal
		emulators, and WSL (Windows Subsystem for Linux). Enhanced in v1.0.26
		to support additional third-party terminals and v1.0.27 for WSL.

		Args:
			obj: The object to check. If None, uses the foreground object.

		Returns:
			bool: True if in a supported terminal application.
		"""
		if obj is None:
			obj = api.getForegroundObject()

		if not obj or not obj.appModule:
			return False

		try:
			appName = obj.appModule.appName.lower()
		except (AttributeError, TypeError):
			return False

		# Ensure appName is a string
		if not isinstance(appName, str):
			return False

		# Built-in Windows terminal applications (v1.0.0+)
		builtinTerminals = [
			"windowsterminal",  # Windows Terminal
			"cmd",              # Command Prompt
			"powershell",       # Windows PowerShell
			"pwsh",             # PowerShell Core
			"conhost",          # Console Host
		]

		# Third-party terminal emulators (v1.0.26+)
		# Section 5.1: Additional Terminal Emulator Support
		thirdPartyTerminals = [
			"cmder",            # Cmder
			"conemu",           # ConEmu (32-bit)
			"conemu64",         # ConEmu (64-bit)
			"mintty",           # Git Bash (mintty)
			"putty",            # PuTTY
			"kitty",            # KiTTY (PuTTY fork)
			"terminus",         # Terminus
			"hyper",            # Hyper
			"alacritty",        # Alacritty
			"wezterm",          # WezTerm
			"wezterm-gui",      # WezTerm GUI
			"tabby",            # Tabby
			"fluent",           # FluentTerminal
		]

		# WSL (Windows Subsystem for Linux) (v1.0.27+)
		# Section 5.2: WSL Support
		wslTerminals = [
			"wsl",              # WSL executable
			"bash",             # WSL bash (may appear as this)
		]

		allSupported = builtinTerminals + thirdPartyTerminals + wslTerminals
		return any(term in appName for term in allSupported)

	def _getPositionContext(self, textInfo=None) -> str:
		"""
		Get current position context for verbose announcements.

		Args:
			textInfo: TextInfo object to get position from (optional)

		Returns:
			String with position information (e.g., "Row 5, column 10")
		"""
		try:
			if textInfo is None:
				textInfo = api.getReviewPosition()

			terminal = self._boundTerminal if self._boundTerminal else api.getForegroundObject()
			if not terminal:
				return ""

			row, col = self._positionCalculator.calculate(textInfo, terminal)
			# Translators: Position context for verbose mode
			return _("Row {row}, column {col}").format(row=row + 1, col=col + 1)
		except Exception:
			return ""

	def _announceWithContext(self, message: str, includePosition: bool = True, includeApp: bool = False):
		"""
		Announce a message with optional context information in verbose mode.

		Args:
			message: The main message to announce
			includePosition: Whether to include position information
			includeApp: Whether to include application name
		"""
		if not message:
			return

		# In quiet mode, suppress all announcements
		if self._configManager.get("quietMode"):
			return

		# Build announcement with context if verbose mode is enabled
		if self._configManager.get("verboseMode"):
			context_parts = []

			if includeApp and self._boundTerminal:
				try:
					appName = self._boundTerminal.appModule.appName
					context_parts.append(appName)
				except Exception:
					pass

			if includePosition:
				position = self._getPositionContext()
				if position:
					context_parts.append(position)

			if context_parts:
				# Translators: Format for verbose announcements with context
				full_message = _("{message}. {context}").format(
					message=message,
					context=", ".join(context_parts)
				)
				ui.message(full_message)
			else:
				ui.message(message)
		else:
			# Standard mode - just announce the message
			ui.message(message)

	def event_gainFocus(self, obj, nextHandler):
		"""
		Handle focus gain events.

		Announces help availability when entering a terminal for the first time.
		Binds the review cursor to the focused terminal window.
		Detects and activates application-specific profiles.
		"""
		nextHandler()

		if self.isTerminalApp(obj):
			try:
				appName = obj.appModule.appName
			except (AttributeError, TypeError):
				return

			# Store the terminal object and route the review cursor to it via the navigator
			self._boundTerminal = obj
			api.setNavigatorObject(obj)

			# Initialize TabManager for this terminal (Section 9 - v1.0.39+)
			if not self._tabManager:
				self._tabManager = TabManager(obj)
			else:
				# Update terminal reference and detect tab changes
				tab_changed = self._tabManager.update_terminal(obj)

			# Initialize BookmarkManager for this terminal (Section 8.3 - v1.0.29+)
			if not self._bookmarkManager:
				self._bookmarkManager = BookmarkManager(obj, self._tabManager)
			else:
				# Update terminal reference when terminal is rebound
				self._bookmarkManager.update_terminal(obj)

			# Initialize OutputSearchManager for this terminal (Section 8.2 - v1.0.30+)
			if not self._searchManager:
				self._searchManager = OutputSearchManager(obj, self._tabManager)
			else:
				# Update terminal reference when terminal is rebound
				self._searchManager.update_terminal(obj)

			# Initialize CommandHistoryManager for this terminal (Section 8.1 - v1.0.31+)
			if not self._commandHistoryManager:
				self._commandHistoryManager = CommandHistoryManager(obj, max_history=100, tab_manager=self._tabManager)
			else:
				# Update terminal reference when terminal is rebound
				self._commandHistoryManager.update_terminal(obj)

			# Clear position cache when switching terminals
			self._positionCalculator.clear_cache()

			# Detect and activate application profile
			detectedApp = self._profileManager.detectApplication(obj)
			if detectedApp != 'default':
				profile = self._profileManager.getProfile(detectedApp)
				if profile:
					self._currentProfile = profile
					import logHandler
					logHandler.log.info(f"Terminal Access: Activated profile for {profile.displayName}")
			else:
				# No app-specific profile detected, check for default profile setting
				defaultProfileName = config.conf["terminalAccess"].get("defaultProfile", "")
				if defaultProfileName and defaultProfileName in self._profileManager.profiles:
					self._currentProfile = self._profileManager.getProfile(defaultProfileName)
					import logHandler
					logHandler.log.info(f"Terminal Access: Using default profile {self._currentProfile.displayName}")
				else:
					self._currentProfile = None

			# Bind review cursor to the terminal; try caret first, fall back to last position
			try:
				info = obj.makeTextInfo(textInfos.POSITION_CARET)
				api.setReviewPosition(info)
			except Exception:
				try:
					info = obj.makeTextInfo(textInfos.POSITION_LAST)
					api.setReviewPosition(info)
				except Exception:
					pass

			# Announce help on first focus to a terminal
			if not self.announcedHelp or appName != self.lastTerminalAppName:
				self.lastTerminalAppName = appName
				self.announcedHelp = True
				# Translators: Message announced when entering a terminal application
				ui.message(_("Terminal Access support active. Press NVDA+shift+f1 for help."))

	def event_typedCharacter(self, obj, nextHandler, ch):
		"""
		Handle typed character events.

		Announces characters as they are typed if keyEcho is enabled.
		Uses punctuation level system to determine whether to speak symbol names.
		Uses repeatedSymbols to condense sequences of repeated symbols.
		"""
		nextHandler()

		# Only handle if in a terminal and keyEcho is enabled
		if not self.isTerminalApp(obj) or not config.conf["terminalAccess"]["keyEcho"]:
			return

		# Don't echo if in quiet mode
		if config.conf["terminalAccess"]["quietMode"]:
			return

		# Clear position cache on content change
		self._positionCalculator.clear_cache()

		# Process the character for speech
		if ch:
			# Check if we should condense repeated symbols
			if config.conf["terminalAccess"]["repeatedSymbols"]:
				repeatedSymbolsValues = config.conf["terminalAccess"]["repeatedSymbolsValues"]

				# Check if this character is in the list of symbols to condense
				if ch in repeatedSymbolsValues:
					# If it's the same as the last character, increment count
					if ch == self._lastTypedChar:
						self._repeatedCharCount += 1
						# Don't announce yet - wait to see if more come
						return
					else:
						# Different character - announce any pending repeated symbols
						if self._repeatedCharCount > 0:
							self._announceRepeatedSymbol(self._lastTypedChar, self._repeatedCharCount)
						# Reset for this new character
						self._lastTypedChar = ch
						self._repeatedCharCount = 1
						# Don't announce yet
						return
				else:
					# Not a symbol to condense - announce any pending repeated symbols first
					if self._repeatedCharCount > 0:
						self._announceRepeatedSymbol(self._lastTypedChar, self._repeatedCharCount)
						self._lastTypedChar = None
						self._repeatedCharCount = 0

			# Use punctuation level system to determine if we should speak symbol names
			if self._shouldProcessSymbol(ch):
				charToSpeak = self._processSymbol(ch)
			else:
				charToSpeak = ch

			# Speak space as "space" instead of silence
			if ch == ' ':
				ui.message(_("space"))
			else:
				ui.message(charToSpeak)

	def _announceRepeatedSymbol(self, char, count):
		"""
		Announce a repeated symbol with its count.

		Args:
			char: The repeated character.
			count: The number of times it was repeated.
		"""
		if count > 1:
			# Get symbol name based on punctuation level
			if self._shouldProcessSymbol(char):
				symbolName = self._processSymbol(char)
			else:
				symbolName = char

			# Translators: Message format for repeated symbols, e.g. "3 dash"
			ui.message(_("{count} {symbol}").format(count=count, symbol=symbolName))
		elif count == 1:
			# Just one - announce normally
			if self._shouldProcessSymbol(char):
				charToSpeak = self._processSymbol(char)
			else:
				charToSpeak = char
			ui.message(charToSpeak)

	def event_caret(self, obj, nextHandler):
		"""
		Handle caret movement events.

		Announces cursor position changes if cursorTracking is enabled.
		Uses cursorDelay to debounce rapid movements.
		"""
		nextHandler()

		# Only handle if in a terminal and cursor tracking is enabled
		if not self.isTerminalApp(obj) or not config.conf["terminalAccess"]["cursorTracking"]:
			return

		# Don't track if in quiet mode
		if config.conf["terminalAccess"]["quietMode"]:
			return

		# Cancel any pending cursor tracking announcement
		if self._cursorTrackingTimer:
			self._cursorTrackingTimer.Stop()
			self._cursorTrackingTimer = None

		# Get cursor delay setting
		delay = config.conf["terminalAccess"]["cursorDelay"]

		# Schedule announcement with delay
		self._cursorTrackingTimer = wx.CallLater(delay, self._announceCursorPosition, obj)

	def _announceCursorPosition(self, obj):
		"""
		Announce the current cursor position based on the tracking mode.

		Args:
			obj: The terminal object.
		"""
		try:
			# Get cursor tracking mode
			trackingMode = config.conf["terminalAccess"]["cursorTrackingMode"]

			# Handle different tracking modes
			if trackingMode == CT_OFF:
				return
			elif trackingMode == CT_STANDARD:
				self._announceStandardCursor(obj)
			elif trackingMode == CT_HIGHLIGHT:
				self._announceHighlightCursor(obj)
			elif trackingMode == CT_WINDOW:
				self._announceWindowCursor(obj)
		except Exception:
			# Silently fail - cursor tracking is a non-critical feature
			pass

	def _announceStandardCursor(self, obj):
		"""
		Standard cursor tracking - announce character at cursor position.

		Args:
			obj: The terminal object.
		"""
		# Get the current caret position
		info = obj.makeTextInfo(textInfos.POSITION_CARET)

		# Check if position has actually changed
		currentPos = (info.bookmark.startOffset if hasattr(info, 'bookmark') else None)
		if currentPos == self._lastCaretPosition:
			return

		self._lastCaretPosition = currentPos

		# Expand to get the character at cursor
		info.expand(textInfos.UNIT_CHARACTER)
		char = info.text

		if char and char.strip():
			# Use punctuation level system if enabled
			if self._shouldProcessSymbol(char):
				charToSpeak = self._processSymbol(char)
			else:
				charToSpeak = char
			ui.message(charToSpeak)
		elif char == ' ':
			ui.message(_("space"))

	def _announceHighlightCursor(self, obj):
		"""
		Highlight tracking - announce highlighted/inverse text at cursor.

		Args:
			obj: The terminal object.
		"""
		try:
			# Get the current caret position
			info = obj.makeTextInfo(textInfos.POSITION_CARET)

			# Check if position has actually changed
			currentPos = (info.bookmark.startOffset if hasattr(info, 'bookmark') else None)
			if currentPos == self._lastCaretPosition:
				return

			self._lastCaretPosition = currentPos

			# Expand to current line to detect highlighting
			info.expand(textInfos.UNIT_LINE)
			lineText = info.text

			# Try to detect ANSI escape codes for highlighting (inverse video: ESC[7m)
			# This is a simplified detection - real implementation would need more robust parsing
			if '\x1b[7m' in lineText or 'ESC[7m' in lineText:
				# Extract highlighted portion
				highlightedText = self._extractHighlightedText(lineText)
				if highlightedText and highlightedText != self._lastHighlightedText:
					self._lastHighlightedText = highlightedText
					ui.message(_("Highlighted: {text}").format(text=highlightedText))
			else:
				# Fall back to standard cursor announcement
				self._announceStandardCursor(obj)
		except Exception:
			# Fall back to standard tracking on error
			self._announceStandardCursor(obj)

	def _announceWindowCursor(self, obj):
		"""
		Window tracking - check both global window and profile-specific windows.

		Args:
			obj: The terminal object.
		"""
		try:
			# Get the current caret position
			info = obj.makeTextInfo(textInfos.POSITION_CARET)

			# Calculate current row and column
			currentRow, currentCol = self._positionCalculator.calculate(info, self._boundTerminal)

			# Check if position changed
			currentPos = (currentRow, currentCol)
			if currentPos == self._lastCaretPosition:
				return

			self._lastCaretPosition = currentPos

			# First, check if we have an active profile with window definitions
			if self._currentProfile and self._currentProfile.windows:
				window = self._currentProfile.getWindowAtPosition(currentRow, currentCol)
				if window:
					if window.mode == 'silent':
						# Silent window - don't announce
						return
					elif window.mode == 'announce':
						# Announce window - read normally
						self._announceStandardCursor(obj)
						return
					# For 'monitor' mode, could add change tracking in future

			# Check global window setting
			if config.conf["terminalAccess"]["windowEnabled"]:
				windowTop = config.conf["terminalAccess"]["windowTop"]
				windowBottom = config.conf["terminalAccess"]["windowBottom"]
				windowLeft = config.conf["terminalAccess"]["windowLeft"]
				windowRight = config.conf["terminalAccess"]["windowRight"]

				# If window is properly defined
				if windowBottom > 0 and windowRight > 0:
					# Check if within window boundaries
					if (windowTop <= currentRow <= windowBottom and
						windowLeft <= currentCol <= windowRight):
						# Within window - announce normally
						self._announceStandardCursor(obj)
					# else: Outside window - silent
					return

			# No window restrictions - announce normally
			self._announceStandardCursor(obj)

		except Exception:
			# On error, fall back to standard tracking
			self._announceStandardCursor(obj)

	def _extractHighlightedText(self, text):
		"""
		Extract highlighted text from a line containing ANSI codes.

		Args:
			text: The text to process.

		Returns:
			str: The highlighted text, or None if no highlighting detected.
		"""
		# This is a simplified implementation
		# Real implementation would need robust ANSI escape sequence parsing
		# Remove ANSI escape codes to get clean text
		ansiPattern = re.compile(r'\x1b\[[0-9;]*m')
		cleanText = ansiPattern.sub('', text)
		return cleanText.strip() if cleanText.strip() else None

	@script(
		# Translators: Description for the show help gesture
		description=_("Opens the Terminal Access user guide"),
		gesture="kb:NVDA+shift+f1"
	)
	def script_showHelp(self, gesture):
		"""Open the Terminal Access user guide."""
		# Get the add-on directory
		addon = addonHandler.getCodeAddon()
		if addon:
			# Open the user guide HTML file
			docPath = os.path.join(addon.path, "doc", "en", "readme.html")
			if os.path.exists(docPath):
				os.startfile(docPath)
			else:
				# Translators: Error message when help file is not found
				ui.message(_("Help file not found. Please reinstall the add-on."))
		else:
			# Translators: Error message when add-on is not properly installed
			ui.message(_("Terminal Access add-on not properly installed."))
	
	@script(
		# Translators: Description for reading the previous line
		description=_("Read previous line in terminal"),
		gesture="kb:NVDA+alt+u"
	)
	def script_readPreviousLine(self, gesture):
		"""Read the previous line in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Read line with optional indentation
		self._readLineWithIndentation(gesture, globalCommands.commands.script_review_previousLine)

	@script(
		# Translators: Description for reading the current line
		description=_("Read current line in terminal. Press twice for indentation level."),
		gesture="kb:NVDA+alt+i"
	)
	def script_readCurrentLine(self, gesture):
		"""Read the current line in the terminal. Double-press announces indentation level."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Check if this is a double-press for indentation
		if scriptHandler.getLastScriptRepeatCount() == 1:
			self._announceIndentation()
		else:
			# Read line with optional indentation
			self._readLineWithIndentation(gesture, globalCommands.commands.script_review_currentLine)

	@script(
		# Translators: Description for reading the next line
		description=_("Read next line in terminal"),
		gesture="kb:NVDA+alt+o"
	)
	def script_readNextLine(self, gesture):
		"""Read the next line in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Read line with optional indentation
		self._readLineWithIndentation(gesture, globalCommands.commands.script_review_nextLine)
	
	@script(
		# Translators: Description for reading the previous word
		description=_("Read previous word in terminal"),
		gesture="kb:NVDA+alt+j"
	)
	def script_readPreviousWord(self, gesture):
		"""Read the previous word in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_previousWord(gesture)

	@script(
		# Translators: Description for reading the current word
		description=_("Read current word in terminal"),
		gesture="kb:NVDA+alt+k"
	)
	def script_readCurrentWord(self, gesture):
		"""Read the current word in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_currentWord(gesture)

	@script(
		# Translators: Description for spelling the current word
		description=_("Spell current word in terminal"),
		gesture="kb:NVDA+alt+k,kb:NVDA+alt+k"
	)
	def script_spellCurrentWord(self, gesture):
		"""Spell out the current word letter by letter."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_spellingCurrentWord(gesture)

	@script(
		# Translators: Description for reading the next word
		description=_("Read next word in terminal"),
		gesture="kb:NVDA+alt+l"
	)
	def script_readNextWord(self, gesture):
		"""Read the next word in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_nextWord(gesture)
	
	@script(
		# Translators: Description for reading the previous character
		description=_("Read previous character in terminal"),
		gesture="kb:NVDA+alt+m"
	)
	def script_readPreviousChar(self, gesture):
		"""Read the previous character in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Directly implement review cursor functionality to avoid gesture propagation
		self._readReviewCharacter(movement=-1)

	@script(
		# Translators: Description for reading the current character
		description=_("Read current character in terminal. Press twice for phonetic. Press three times for character code."),
		gesture="kb:NVDA+alt+comma"
	)
	def script_readCurrentChar(self, gesture):
		"""Read the current character. Double-press for phonetic. Triple-press for character code."""
		if not self.isTerminalApp():
			gesture.send()
			return

		repeatCount = scriptHandler.getLastScriptRepeatCount()

		if repeatCount == 2:
			# Triple press - announce character code
			self._announceCharacterCode()
		elif repeatCount == 1:
			# Double press - phonetic reading
			self._readReviewCharacter(movement=0, phonetic=True)
		else:
			# Single press - read character
			self._readReviewCharacter(movement=0)

	@script(
		# Translators: Description for reading the next character
		description=_("Read next character in terminal"),
		gesture="kb:NVDA+alt+period"
	)
	def script_readNextChar(self, gesture):
		"""Read the next character in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Directly implement review cursor functionality to avoid gesture propagation
		self._readReviewCharacter(movement=1)
	
	@script(
		# Translators: Description for toggling quiet mode
		description=_("Toggle quiet mode in terminal"),
		gesture="kb:NVDA+alt+q"
	)
	def script_toggleQuietMode(self, gesture):
		"""Toggle quiet mode on/off."""
		if not self.isTerminalApp():
			gesture.send()
			return
		
		currentState = config.conf["terminalAccess"]["quietMode"]
		config.conf["terminalAccess"]["quietMode"] = not currentState
		
		if config.conf["terminalAccess"]["quietMode"]:
			# Translators: Message when quiet mode is enabled
			ui.message(_("Quiet mode on"))
		else:
			# Translators: Message when quiet mode is disabled
			ui.message(_("Quiet mode off"))

	@script(
		# Translators: Description for toggling indentation announcement
		description=_("Toggle indentation announcement on line read in terminal"),
		gesture="kb:NVDA+alt+f5"
	)
	def script_toggleIndentation(self, gesture):
		"""Toggle indentation announcement on/off."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentState = config.conf["terminalAccess"]["indentationOnLineRead"]
		config.conf["terminalAccess"]["indentationOnLineRead"] = not currentState

		if config.conf["terminalAccess"]["indentationOnLineRead"]:
			# Translators: Message when indentation announcement is enabled
			ui.message(_("Indentation announcement on"))
		else:
			# Translators: Message when indentation announcement is disabled
			ui.message(_("Indentation announcement off"))

	@script(
		# Translators: Description for copy mode
		description=_("Enter copy mode in terminal"),
		gesture="kb:NVDA+alt+v"
	)
	def script_copyMode(self, gesture):
		"""Enter copy mode to copy line or screen."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Enter copy mode
		self.copyMode = True
		# Bind keys for copy mode
		self.bindGesture("kb:l", "copyLine")
		self.bindGesture("kb:s", "copyScreen")
		self.bindGesture("kb:escape", "exitCopyMode")
		# Translators: Message entering copy mode
		ui.message(_("Copy mode. Press L to copy line, S to copy screen, or Escape to cancel."))

	@script(
		# Translators: Description for copying line
		description=_("Copy line in copy mode")
	)
	def script_copyLine(self, gesture):
		"""Copy the current line to clipboard."""
		if not self.copyMode:
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to copy"))
				self._exitCopyModeBindings()
				return
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_LINE)
			text = info.text
			if text and self._copyToClipboard(text):
				# Translators: Message when line is copied
				ui.message(_("Line copied"))
			else:
				# Translators: Error message when unable to copy
				ui.message(_("Unable to copy"))
		except Exception:
			ui.message(_("Unable to copy"))
		finally:
			self._exitCopyModeBindings()

	@script(
		# Translators: Description for copying screen
		description=_("Copy screen in copy mode")
	)
	def script_copyScreen(self, gesture):
		"""Copy the entire screen to clipboard."""
		if not self.copyMode:
			gesture.send()
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to copy"))
				return

			# Get the entire text from the terminal
			info = terminal.makeTextInfo(textInfos.POSITION_ALL)
			text = info.text
			if text and self._copyToClipboard(text):
				# Translators: Message when screen is copied
				ui.message(_("Screen copied"))
			else:
				# Translators: Error message when unable to copy
				ui.message(_("Unable to copy"))
		except Exception:
			ui.message(_("Unable to copy"))
		finally:
			self._exitCopyModeBindings()

	@script(
		# Translators: Description for exiting copy mode
		description=_("Exit copy mode")
	)
	def script_exitCopyMode(self, gesture):
		"""Exit copy mode."""
		if not self.copyMode:
			gesture.send()
			return

		# Translators: Message when copy mode is canceled
		ui.message(_("Copy mode canceled"))
		self._exitCopyModeBindings()

	def _exitCopyModeBindings(self):
		"""Exit copy mode and unbind the copy mode keys."""
		self.copyMode = False
		try:
			self.removeGestureBinding("kb:l")
			self.removeGestureBinding("kb:s")
			self.removeGestureBinding("kb:escape")
		except (KeyError, AttributeError):
			pass
	
	@script(
		# Translators: Description for opening terminal settings
		description=_("Open Terminal Access settings")
	)
	def script_openSettings(self, gesture):
		"""Open the Terminal Access settings dialog."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Open NVDA settings dialog to Terminal Access category
		try:
			wx.CallAfter(gui.mainFrame._popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, TerminalAccessSettingsPanel)
		except (AttributeError, TypeError, RuntimeError):
			# Translators: Error message when settings dialog cannot be opened
			ui.message(_("Unable to open settings dialog. Please try again."))

	@script(
		# Translators: Description for cycling cursor tracking modes
		description=_("Cycle cursor tracking mode"),
		gesture="kb:NVDA+alt+asterisk"
	)
	def script_cycleCursorTrackingMode(self, gesture):
		"""Cycle through cursor tracking modes: Off -> Standard -> Highlight -> Window -> Off."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Get current mode
		currentMode = config.conf["terminalAccess"]["cursorTrackingMode"]

		# Cycle to next mode
		nextMode = (currentMode + 1) % 4

		# Update configuration
		config.conf["terminalAccess"]["cursorTrackingMode"] = nextMode

		# Announce new mode
		modeNames = {
			CT_OFF: _("Cursor tracking off"),
			CT_STANDARD: _("Standard cursor tracking"),
			CT_HIGHLIGHT: _("Highlight tracking"),
			CT_WINDOW: _("Window tracking")
		}
		ui.message(modeNames.get(nextMode, _("Unknown mode")))

	@script(
		# Translators: Description for setting screen window
		description=_("Set screen window boundaries"),
		gesture="kb:NVDA+alt+f2"
	)
	def script_setWindow(self, gesture):
		"""Set screen window boundaries (two-step process: start position, then end position)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to set window"))
				return

			if not self._windowStartSet:
				# Set start position
				self._windowStartBookmark = reviewPos.bookmark
				self._windowStartSet = True
				# Translators: Message when window start is set
				ui.message(_("Window start set. Move to end position and press again."))
			else:
				# Set end position
				# Note: Creating TextInfo objects for window boundary calculation
				# These variables are used for validation but not needed for the current implementation
				self._boundTerminal.makeTextInfo(self._windowStartBookmark)
				reviewPos.copy()

				# Store window boundaries (simplified - storing bookmarks instead of coordinates)
				config.conf["terminalAccess"]["windowEnabled"] = True
				self._windowStartSet = False
				# Translators: Message when window is defined
				ui.message(_("Window defined"))
		except Exception:
			ui.message(_("Unable to set window"))
			self._windowStartSet = False

	@script(
		# Translators: Description for clearing screen window
		description=_("Clear screen window"),
		gesture="kb:NVDA+alt+f3"
	)
	def script_clearWindow(self, gesture):
		"""Clear the defined screen window."""
		if not self.isTerminalApp():
			gesture.send()
			return

		config.conf["terminalAccess"]["windowEnabled"] = False
		self._windowStartSet = False
		# Translators: Message when window is cleared
		ui.message(_("Window cleared"))

	@script(
		# Translators: Description for reading window content
		description=_("Read window content"),
		gesture="kb:NVDA+alt+plus"
	)
	def script_readWindow(self, gesture):
		"""Read the content within the defined window."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not config.conf["terminalAccess"]["windowEnabled"]:
			# Translators: Message when no window is defined
			ui.message(_("No window defined"))
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to read window"))
				return

			# Get window boundaries
			windowTop = config.conf["terminalAccess"]["windowTop"]
			windowBottom = config.conf["terminalAccess"]["windowBottom"]
			windowLeft = config.conf["terminalAccess"]["windowLeft"]
			windowRight = config.conf["terminalAccess"]["windowRight"]

			# Validate window definition
			if windowBottom == 0 or windowRight == 0:
				ui.message(_("Window not properly defined"))
				return

			# Extract window content line by line
			lines = []
			currentInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)

			# Move to window top
			currentInfo.move(textInfos.UNIT_LINE, windowTop - 1)

			# Extract each line in window
			for row in range(windowTop, windowBottom + 1):
				lineInfo = currentInfo.copy()
				lineInfo.expand(textInfos.UNIT_LINE)
				lineText = lineInfo.text.rstrip('\n\r')

				# Extract column range (convert to 0-based indexing)
				startIdx = max(0, windowLeft - 1)
				endIdx = min(len(lineText), windowRight)

				if startIdx < len(lineText):
					columnText = lineText[startIdx:endIdx]
				else:
					columnText = ''  # Line too short

				if columnText.strip():  # Only include non-empty lines
					lines.append(columnText)

				# Move to next line
				moved = currentInfo.move(textInfos.UNIT_LINE, 1)
				if moved == 0:
					break

			# Read window content
			windowText = ' '.join(lines)
			if windowText:
				speech.speakText(windowText)
			else:
				# Translators: Message when window contains no text
				ui.message(_("Window is empty"))

		except Exception:
			ui.message(_("Unable to read window"))

	@script(
		# Translators: Description for reading text attributes
		description=_("Read text attributes at cursor"),
		gesture="kb:NVDA+alt+shift+a"
	)
	def script_readAttributes(self, gesture):
		"""Read color and formatting attributes at cursor position using enhanced ANSI parser."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read attributes"))
				return

			# Get text from start of line to cursor to capture all ANSI codes
			lineStart = reviewPos.copy()
			lineStart.expand(textInfos.UNIT_LINE)
			lineStart.collapse()

			# Get text from line start to cursor
			textToCursor = lineStart.copy()
			textToCursor.setEndPoint(reviewPos, "endToStart")
			textToCursor.expand(textInfos.UNIT_CHARACTER)

			# Get the text with ANSI codes
			text = textToCursor.text

			if text:
				# Parse ANSI codes using enhanced parser
				parser = ANSIParser()
				parser.parse(text)

				# Format attributes in detailed mode
				attributeMsg = parser.formatAttributes(mode='detailed')
				ui.message(attributeMsg)
			else:
				# Translators: Message when no text at cursor
				ui.message(_("No text at cursor"))

		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Error reading attributes: {e}")
			ui.message(_("Unable to read attributes"))

	# Phase 1 Quick Win Features

	@script(
		# Translators: Description for continuous reading (say all)
		description=_("Read continuously from cursor to end of buffer"),
		gesture="kb:NVDA+alt+a"
	)
	def script_sayAll(self, gesture):
		"""Read continuously from current review cursor position to end of buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when unable to start continuous reading
				ui.message(_("Unable to read"))
				return

			# Get text from current position to end
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_STORY)

			# Move to current position
			info.setEndPoint(reviewPos, "startToStart")

			text = info.text
			if not text or not text.strip():
				# Translators: Message when buffer is empty
				ui.message(_("Nothing to read"))
				return

			# Use NVDA's speech system to read the text
			# This allows for proper interruption
			speech.speakText(text)
		except Exception:
			# Translators: Message when continuous reading fails
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for jumping to start of line
		description=_("Move to first character of current line"),
		gesture="kb:NVDA+alt+home"
	)
	def script_reviewHome(self, gesture):
		"""Move review cursor to first character of current line."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when unable to move
				ui.message(_("Unable to move"))
				return

			# Move to start of line
			info = reviewPos.copy()
			info.collapse()
			info.move(textInfos.UNIT_LINE, -1)
			info.move(textInfos.UNIT_LINE, 1)
			api.setReviewPosition(info)

			# Read character at new position
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text
			if char and char != '\n' and char != '\r':
				speech.speakText(char)
			else:
				# Translators: Message for blank line
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to end of line
		description=_("Move to last character of current line"),
		gesture="kb:NVDA+alt+end"
	)
	def script_reviewEnd(self, gesture):
		"""Move review cursor to last character of current line."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to move"))
				return

			# Expand to line and move to end
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_LINE)
			# Collapse to end
			info.collapse(end=True)
			# Move back one character to be on the last character, not after it
			info.move(textInfos.UNIT_CHARACTER, -1)
			api.setReviewPosition(info)

			# Read character at new position
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text
			if char and char != '\n' and char != '\r':
				speech.speakText(char)
			else:
				# Translators: Message for blank line
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to top
		description=_("Move to top of terminal buffer"),
		gesture="kb:NVDA+alt+pageUp"
	)
	def script_reviewTop(self, gesture):
		"""Move review cursor to top of terminal buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to move"))
				return

			# Move to first position
			info = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			api.setReviewPosition(info)

			# Read character at new position
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text
			if char and char != '\n' and char != '\r':
				speech.speakText(char)
			else:
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to bottom
		description=_("Move to bottom of terminal buffer"),
		gesture="kb:NVDA+alt+pageDown"
	)
	def script_reviewBottom(self, gesture):
		"""Move review cursor to bottom of terminal buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to move"))
				return

			# Move to last position
			info = terminal.makeTextInfo(textInfos.POSITION_LAST)
			api.setReviewPosition(info)

			# Read character at new position
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text
			if char and char != '\n' and char != '\r':
				speech.speakText(char)
			else:
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for announcing position
		description=_("Announce current row and column position"),
		gesture="kb:NVDA+alt+p"
	)
	def script_announcePosition(self, gesture):
		"""Announce current row and column coordinates of review cursor."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when position unavailable
				ui.message(_("Position unavailable"))
				return

			# Calculate position using helper method
			lineCount, colCount = self._positionCalculator.calculate(reviewPos, self._boundTerminal)

			if lineCount == 0 or colCount == 0:
				ui.message(_("Position unavailable"))
				return

			# Translators: Message announcing row and column position
			ui.message(_("Row {row}, column {col}").format(row=lineCount, col=colCount))
		except Exception:
			ui.message(_("Position unavailable"))

	@script(
		# Translators: Description for announcing active profile
		description=_("Announce which profile is currently active and which is set as default"),
		gesture="kb:NVDA+alt+f10"
	)
	def script_announceActiveProfile(self, gesture):
		"""Announce the currently active profile and default profile."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Get active profile name
		if self._currentProfile:
			activeProfileName = self._currentProfile.displayName
		else:
			# Translators: Message when no profile is active
			activeProfileName = _("None (using global settings)")

		# Get default profile name
		defaultProfileName = config.conf["terminalAccess"].get("defaultProfile", "")
		if defaultProfileName and defaultProfileName in self._profileManager.profiles:
			defaultProfile = self._profileManager.getProfile(defaultProfileName)
			defaultProfileDisplay = defaultProfile.displayName
		else:
			# Translators: Message when no default profile is set
			defaultProfileDisplay = _("None")

		# Announce both active and default profiles
		# Translators: Message announcing active and default profiles
		ui.message(_("Active profile: {active}. Default profile: {default}").format(
			active=activeProfileName,
			default=defaultProfileDisplay
		))

	def _announceIndentation(self):
		"""Announce the indentation level of the current line."""
		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when unable to read indentation
				ui.message(_("Unable to read indentation"))
				return

			# Get current line text
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_LINE)
			lineText = info.text

			if not lineText:
				# Translators: Message for empty line
				ui.message(_("Empty line"))
				return

			# Remove trailing newline if present
			if lineText.endswith('\n') or lineText.endswith('\r'):
				lineText = lineText.rstrip('\n\r')

			if not lineText:
				ui.message(_("Empty line"))
				return

			# Count leading spaces and tabs
			spaces = 0
			tabs = 0
			for char in lineText:
				if char == ' ':
					spaces += 1
				elif char == '\t':
					tabs += 1
				else:
					break

			# Announce indentation
			if spaces == 0 and tabs == 0:
				# Translators: Message when line has no indentation
				ui.message(_("No indentation"))
			elif tabs > 0 and spaces > 0:
				# Translators: Message for mixed indentation
				ui.message(_("{tabs} tab, {spaces} spaces").format(tabs=tabs, spaces=spaces) if tabs == 1 else _("{tabs} tabs, {spaces} spaces").format(tabs=tabs, spaces=spaces))
			elif tabs > 0:
				# Translators: Message for tab indentation
				ui.message(_("{count} tab").format(count=tabs) if tabs == 1 else _("{count} tabs").format(count=tabs))
			else:
				# Translators: Message for space indentation
				ui.message(_("{count} space").format(count=spaces) if spaces == 1 else _("{count} spaces").format(count=spaces))
		except Exception:
			ui.message(_("Unable to read indentation"))

	def _getIndentationInfo(self, lineText: str) -> tuple:
		"""
		Get indentation information from a line of text.

		Args:
			lineText: The line text to analyze

		Returns:
			Tuple of (spaces, tabs) counts
		"""
		if not lineText:
			return (0, 0)

		# Remove trailing newline if present
		if lineText.endswith('\n') or lineText.endswith('\r'):
			lineText = lineText.rstrip('\n\r')

		if not lineText:
			return (0, 0)

		# Count leading spaces and tabs
		spaces = 0
		tabs = 0
		for char in lineText:
			if char == ' ':
				spaces += 1
			elif char == '\t':
				tabs += 1
			else:
				break

		return (spaces, tabs)

	def _formatIndentation(self, spaces: int, tabs: int) -> str:
		"""
		Format indentation info as a string.

		Args:
			spaces: Number of leading spaces
			tabs: Number of leading tabs

		Returns:
			Formatted string describing the indentation
		"""
		if spaces == 0 and tabs == 0:
			return ""
		elif tabs > 0 and spaces > 0:
			# Translators: Message for mixed indentation
			return _("{tabs} tab, {spaces} spaces").format(tabs=tabs, spaces=spaces) if tabs == 1 else _("{tabs} tabs, {spaces} spaces").format(tabs=tabs, spaces=spaces)
		elif tabs > 0:
			# Translators: Message for tab indentation
			return _("{count} tab").format(count=tabs) if tabs == 1 else _("{count} tabs").format(count=tabs)
		else:
			# Translators: Message for space indentation
			return _("{count} space").format(count=spaces) if spaces == 1 else _("{count} spaces").format(count=spaces)

	def _readLineWithIndentation(self, gesture, moveFunction):
		"""
		Read a line and optionally announce indentation.

		Args:
			gesture: The gesture that triggered this command
			moveFunction: The function to call to read the line (e.g., script_review_currentLine)
		"""
		# Check if indentation should be announced
		shouldAnnounceIndentation = config.conf["terminalAccess"]["indentationOnLineRead"]

		# Get line text before reading it aloud
		if shouldAnnounceIndentation:
			try:
				reviewPos = self._getReviewPosition()
				if reviewPos:
					info = reviewPos.copy()
					info.expand(textInfos.UNIT_LINE)
					lineText = info.text
					spaces, tabs = self._getIndentationInfo(lineText)
					indentInfo = self._formatIndentation(spaces, tabs)
				else:
					indentInfo = ""
			except Exception:
				indentInfo = ""
		else:
			indentInfo = ""

		# Read the line using NVDA's built-in functionality
		moveFunction(gesture)

		# Announce indentation after line is read, if enabled
		if indentInfo:
			ui.message(indentInfo)

	def _readReviewCharacter(self, movement=0, phonetic=False):
		"""
		Read a character at the review cursor position.

		Args:
			movement: -1 for previous, 0 for current, 1 for next
			phonetic: Whether to use phonetic reading
		"""
		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when no review position
				ui.message(_("No review position"))
				return

			# Move review cursor if needed
			if movement != 0:
				info = reviewPos.copy()
				result = info.move(textInfos.UNIT_CHARACTER, movement)
				if result == 0:
					# Translators: Message when at edge of text
					ui.message(_("Edge") if movement > 0 else _("Top"))
					return
				api.setReviewPosition(info)
				reviewPos = info

			# Expand to character and read
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_CHARACTER)

			# Use speech to speak the character
			if phonetic:
				# For phonetic reading, speak with spelling mode
				speech.speakSpelling(info.text)
			else:
				# Normal character reading
				speech.speakTextInfo(info, unit=textInfos.UNIT_CHARACTER, reason=speech.OutputReason.CARET)

		except Exception:
			# Translators: Message when unable to read character
			ui.message(_("Unable to read character"))

	def _announceCharacterCode(self):
		"""Announce the ASCII/Unicode code of the current character."""
		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when unable to read character
				ui.message(_("Unable to read character"))
				return

			# Get character at cursor
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text

			if not char or char == '\n' or char == '\r':
				# Translators: Message when no character at position
				ui.message(_("No character"))
				return

			# Get character code
			charCode = ord(char)
			hexCode = hex(charCode)[2:].upper()

			# Get character name for common control characters
			charName = char
			if charCode == 32:
				charName = "space"
			elif charCode == 9:
				charName = "tab"
			elif charCode == 10:
				charName = "line feed"
			elif charCode == 13:
				charName = "carriage return"
			elif charCode < 32:
				charName = "control character"

			# Translators: Message announcing character code
			ui.message(_("Character {decimal}, hex {hex}, {name}").format(
				decimal=charCode,
				hex=hexCode,
				name=charName
			))
		except Exception:
			ui.message(_("Unable to read character"))

	# Phase 2 Core Enhancement Features

	def _shouldProcessSymbol(self, char):
		"""
		Determine if a symbol should be processed/announced based on current punctuation level.

		Args:
			char: The character to check.

		Returns:
			bool: True if the symbol should be announced, False otherwise.
		"""
		level = config.conf["terminalAccess"]["punctuationLevel"]

		if level == PUNCT_ALL:
			# Level 3: Process all symbols
			return True
		if level == PUNCT_NONE:
			# Level 0: Process no symbols
			return False

		# Level 1 or 2: Check if character is in the level's punctuation set
		punctSet = PUNCTUATION_SETS.get(level, set())
		return char in punctSet

	@script(
		# Translators: Description for decreasing punctuation level
		description=_("Decrease punctuation level"),
		gesture="kb:NVDA+alt+["
	)
	def script_decreasePunctuationLevel(self, gesture):
		"""Decrease the punctuation level (wraps from 0 to 3)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentLevel = config.conf["terminalAccess"]["punctuationLevel"]
		newLevel = (currentLevel - 1) % 4
		config.conf["terminalAccess"]["punctuationLevel"] = newLevel

		# Announce new level
		levelNames = {
			PUNCT_NONE: _("Punctuation level none"),
			PUNCT_SOME: _("Punctuation level some"),
			PUNCT_MOST: _("Punctuation level most"),
			PUNCT_ALL: _("Punctuation level all")
		}
		ui.message(levelNames.get(newLevel, _("Punctuation level unknown")))

	@script(
		# Translators: Description for increasing punctuation level
		description=_("Increase punctuation level"),
		gesture="kb:NVDA+alt+]"
	)
	def script_increasePunctuationLevel(self, gesture):
		"""Increase the punctuation level (wraps from 3 to 0)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentLevel = config.conf["terminalAccess"]["punctuationLevel"]
		newLevel = (currentLevel + 1) % 4
		config.conf["terminalAccess"]["punctuationLevel"] = newLevel

		# Announce new level
		levelNames = {
			PUNCT_NONE: _("Punctuation level none"),
			PUNCT_SOME: _("Punctuation level some"),
			PUNCT_MOST: _("Punctuation level most"),
			PUNCT_ALL: _("Punctuation level all")
		}
		ui.message(levelNames.get(newLevel, _("Punctuation level unknown")))

	@script(
		# Translators: Description for reading to left edge
		description=_("Read from cursor to beginning of line"),
		gesture="kb:NVDA+alt+shift+leftArrow"
	)
	def script_readToLeft(self, gesture):
		"""Read from current cursor position to beginning of line."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			# Get the current line
			lineInfo = reviewPos.copy()
			lineInfo.expand(textInfos.UNIT_LINE)

			# Create range from line start to cursor
			lineInfo.setEndPoint(reviewPos, "endToStart")

			text = lineInfo.text
			if not text or not text.strip():
				# Translators: Message when region is empty
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to right edge
		description=_("Read from cursor to end of line"),
		gesture="kb:NVDA+alt+shift+rightArrow"
	)
	def script_readToRight(self, gesture):
		"""Read from current cursor position to end of line."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			# Get the current line
			lineInfo = reviewPos.copy()
			lineInfo.expand(textInfos.UNIT_LINE)

			# Create range from cursor to line end
			lineInfo.setEndPoint(reviewPos, "startToStart")

			text = lineInfo.text
			if not text or not text.strip():
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to top
		description=_("Read from cursor to top of buffer"),
		gesture="kb:NVDA+alt+shift+upArrow"
	)
	def script_readToTop(self, gesture):
		"""Read from current cursor position to top of buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to read"))
				return

			# Get range from buffer start to cursor
			startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			startInfo.setEndPoint(reviewPos, "endToStart")

			text = startInfo.text
			if not text or not text.strip():
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to bottom
		description=_("Read from cursor to bottom of buffer"),
		gesture="kb:NVDA+alt+shift+downArrow"
	)
	def script_readToBottom(self, gesture):
		"""Read from current cursor position to bottom of buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to read"))
				return

			# Get range from cursor to buffer end
			endInfo = terminal.makeTextInfo(textInfos.POSITION_LAST)
			reviewPos.setEndPoint(endInfo, "endToEnd")

			text = reviewPos.text
			if not text or not text.strip():
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for toggling mark position
		description=_("Toggle mark for selection (enhanced)"),
		gesture="kb:NVDA+alt+r"
	)
	def script_toggleMark(self, gesture):
		"""Toggle marking positions for enhanced selection."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to set mark"))
				return

			if self._markStart is None:
				# Set start mark
				self._markStart = reviewPos.bookmark
				# Translators: Message when start mark is set (Phase 6: Enhanced with context)
				self._announceWithContext(_("Mark start set"), includePosition=True)
			elif self._markEnd is None:
				# Set end mark
				self._markEnd = reviewPos.bookmark
				# Translators: Message when end mark is set (Phase 6: Enhanced with context)
				self._announceWithContext(_("Mark end set"), includePosition=True)
			else:
				# Clear marks and start over
				self._markStart = None
				self._markEnd = None
				# Translators: Message when marks are cleared
				ui.message(_("Marks cleared"))
		except Exception:
			ui.message(_("Unable to set mark"))

	@script(
		# Translators: Description for copying linear selection
		description=_("Copy linear selection between marks"),
		gesture="kb:NVDA+alt+c"
	)
	def script_copyLinearSelection(self, gesture):
		"""Copy text from start mark to end mark (continuous selection)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._markStart or not self._markEnd:
			# Translators: Message when marks are not set
			ui.message(_("Set start and end marks first"))
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to copy"))
				return

			# Get text from start to end mark
			startInfo = terminal.makeTextInfo(self._markStart)
			endInfo = terminal.makeTextInfo(self._markEnd)
			startInfo.setEndPoint(endInfo, "endToEnd")

			text = startInfo.text
			if text and self._copyToClipboard(text):
				# Translators: Message when selection copied
				ui.message(_("Selection copied"))
			else:
				ui.message(_("Unable to copy"))
		except (RuntimeError, AttributeError) as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Linear selection copy failed - {type(e).__name__}: {e}")
			ui.message(_("Unable to copy: terminal not accessible"))
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Unexpected error in linear selection - {type(e).__name__}: {e}")
			ui.message(_("Unable to copy"))

	@script(
		# Translators: Description for copying rectangular selection
		description=_("Copy rectangular selection between marks"),
		gesture="kb:NVDA+alt+shift+c"
	)
	def script_copyRectangularSelection(self, gesture):
		"""Copy rectangular region (column-based) between marks."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._markStart or not self._markEnd:
			ui.message(_("Set start and end marks first"))
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to copy"))
				return

			# Get start and end positions
			startInfo = terminal.makeTextInfo(self._markStart)
			endInfo = terminal.makeTextInfo(self._markEnd)

			# Calculate row and column coordinates
			startRow, startCol = self._positionCalculator.calculate(startInfo, terminal)
			endRow, endCol = self._positionCalculator.calculate(endInfo, terminal)

			# Validate coordinates
			if startRow == 0 or startCol == 0 or endRow == 0 or endCol == 0:
				ui.message(_("Unable to determine position"))
				return

			# Ensure correct order (top-left to bottom-right)
			if startRow > endRow:
				startRow, endRow = endRow, startRow
			if startCol > endCol:
				startCol, endCol = endCol, startCol

			# Validate selection size against resource limits
			isValid, errorMessage = _validateSelectionSize(startRow, endRow, startCol, endCol)
			if not isValid:
				ui.message(errorMessage)
				return

			# Calculate selection size
			rowCount = endRow - startRow + 1

			# Use background thread for large selections (>100 rows)
			if rowCount > 100:
				# Check if operation queue is busy (Section 1.3: Queue system)
				if self._operationQueue.is_busy():
					ui.message(_("Background operation in progress, please wait"))
					return

				ui.message(_("Processing large selection ({rows} rows), please wait...").format(rows=rowCount))

				# Create progress dialog for large operations (Section 1.3: Improved progress dialog)
				progressDialog = None
				if rowCount > 500:  # Show visual progress for very large selections
					progressDialog = SelectionProgressDialog(
						gui.mainFrame,
						_("Terminal Access - Copying Selection"),
						100  # Percentage-based progress
					)

				# Start background thread
				thread = threading.Thread(
					target=self._copyRectangularSelectionBackground,
					args=(terminal, startRow, endRow, startCol, endCol, progressDialog)
				)
				thread.daemon = True

				# Start operation using queue (Section 1.3: Queue system)
				if not self._operationQueue.start_operation(thread):
					ui.message(_("Failed to start background operation"))
					if progressDialog:
						progressDialog.close()
					return

				return

			# For smaller selections, process synchronously
			self._performRectangularCopy(terminal, startRow, endRow, startCol, endCol)

		except (RuntimeError, AttributeError) as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Rectangular selection failed - {type(e).__name__}: {e}")
			ui.message(_("Unable to copy: terminal not accessible"))
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Unexpected error in rectangular selection - {type(e).__name__}: {e}")
			ui.message(_("Unable to copy"))

	def _copyRectangularSelectionBackground(self, terminal, startRow, endRow, startCol, endCol, progressDialog=None):
		"""
		Background thread worker for large rectangular selections.

		Args:
			terminal: Terminal object
			startRow: Starting row (1-based)
			endRow: Ending row (1-based)
			startCol: Starting column (1-based)
			endCol: Ending column (1-based)
			progressDialog: Optional SelectionProgressDialog for visual feedback
		"""
		try:
			self._performRectangularCopy(terminal, startRow, endRow, startCol, endCol, progressDialog)
		except (RuntimeError, AttributeError) as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Background rectangular copy failed - {type(e).__name__}: {e}")
			if progressDialog:
				progressDialog.close()
			wx.CallAfter(ui.message, _("Background copy failed: terminal not accessible"))
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Unexpected error in background copy - {type(e).__name__}: {e}")
			if progressDialog:
				progressDialog.close()
			wx.CallAfter(ui.message, _("Background copy failed"))
		finally:
			# Clear operation from queue
			self._operationQueue.clear()

	def _performRectangularCopy(self, terminal, startRow, endRow, startCol, endCol, progressDialog=None):
		"""
		Perform the actual rectangular copy operation with Unicode/CJK support.

		Args:
			terminal: Terminal object
			startRow: Starting row (1-based)
			endRow: Ending row (1-based)
			startCol: Starting column (1-based)
			endCol: Ending column (1-based)
			progressDialog: Optional SelectionProgressDialog for visual feedback
		"""
		# Extract rectangular region line by line
		lines = []
		currentInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)

		# Move to start row
		currentInfo.move(textInfos.UNIT_LINE, startRow - 1)

		# Calculate total rows for progress tracking
		totalRows = endRow - startRow + 1

		# Extract each line in range
		for idx, row in enumerate(range(startRow, endRow + 1)):
			# Update progress dialog if provided (Section 1.3: Improved progress tracking)
			if progressDialog and idx % 10 == 0:  # Update every 10 rows
				progress = int((idx / totalRows) * 100)
				message = _("Copying row {current} of {total}...").format(current=idx + 1, total=totalRows)
				# Check for cancellation (Section 1.3: Cancellation support)
				if not progressDialog.update(progress, message):
					# User cancelled - stop processing
					if threading.current_thread() != threading.main_thread():
						wx.CallAfter(ui.message, _("Copy operation cancelled by user"))
					else:
						ui.message(_("Copy operation cancelled by user"))
					progressDialog.close()
					return

			lineInfo = currentInfo.copy()
			lineInfo.expand(textInfos.UNIT_LINE)
			lineText = lineInfo.text.rstrip('\n\r')

			# Strip ANSI codes for accurate column extraction
			cleanText = ANSIParser.stripANSI(lineText)

			# Extract column range using Unicode-aware helper (1-based columns)
			columnText = UnicodeWidthHelper.extractColumnRange(cleanText, startCol, endCol)

			lines.append(columnText)

			# Move to next line
			moved = currentInfo.move(textInfos.UNIT_LINE, 1)
			if moved == 0:
				break

		# Join lines and copy to clipboard
		rectangularText = '\n'.join(lines)

		# Close progress dialog if provided (Section 1.3: Proper cleanup)
		if progressDialog:
			progressDialog.update(100, _("Copy complete!"))
			progressDialog.close()

		if rectangularText and self._copyToClipboard(rectangularText):
			# Translators: Message for successful rectangular selection copy
			message = _("Rectangular selection copied: {rows} rows, columns {start} to {end}").format(
				rows=len(lines),
				start=startCol,
				end=endCol
			)
			# If called from background thread, schedule message on main thread
			if threading.current_thread() != threading.main_thread():
				wx.CallAfter(ui.message, message)
			else:
				ui.message(message)
		else:
			message = _("Unable to copy")
			if threading.current_thread() != threading.main_thread():
				wx.CallAfter(ui.message, message)
			else:
				ui.message(message)

	@script(
		# Translators: Description for clearing marks
		description=_("Clear selection marks"),
		gesture="kb:NVDA+alt+x"
	)
	def script_clearMarks(self, gesture):
		"""Clear the selection marks."""
		if not self.isTerminalApp():
			gesture.send()
			return

		self._markStart = None
		self._markEnd = None
		# Translators: Message when marks cleared
		ui.message(_("Marks cleared"))

	# Section 8.3: Bookmark functionality gestures (v1.0.29+)

	@scriptHandler.script(
		# Translators: Description for setting bookmark
		description=_("Set a bookmark at the current review position (use with 0-9)"),
		category=SCRCAT_TERMINALACCESS,
		gestures=["kb:NVDA+alt+shift+0", "kb:NVDA+alt+shift+1", "kb:NVDA+alt+shift+2",
		          "kb:NVDA+alt+shift+3", "kb:NVDA+alt+shift+4", "kb:NVDA+alt+shift+5",
		          "kb:NVDA+alt+shift+6", "kb:NVDA+alt+shift+7", "kb:NVDA+alt+shift+8",
		          "kb:NVDA+alt+shift+9"]
	)
	def script_setBookmark(self, gesture):
		"""Set a bookmark at current position."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._bookmarkManager:
			# Translators: Error message when bookmark manager not initialized
			ui.message(_("Bookmark manager not available"))
			return

		# Get bookmark number from gesture (0-9)
		key = gesture.mainKeyName
		if key.isdigit():
			name = key
		else:
			# For custom bookmark names, we'd need a dialog - for now use "temp"
			name = "temp"

		if self._bookmarkManager.set_bookmark(name):
			# Translators: Message when bookmark set
			ui.message(_("Bookmark {name} set").format(name=name))
		else:
			# Translators: Error message when bookmark setting fails
			ui.message(_("Failed to set bookmark"))

	@scriptHandler.script(
		# Translators: Description for jumping to bookmark
		description=_("Jump to a previously set bookmark (use with 0-9)"),
		category=SCRCAT_TERMINALACCESS,
		gestures=["kb:NVDA+alt+0", "kb:NVDA+alt+1", "kb:NVDA+alt+2",
		          "kb:NVDA+alt+3", "kb:NVDA+alt+4", "kb:NVDA+alt+5",
		          "kb:NVDA+alt+6", "kb:NVDA+alt+7", "kb:NVDA+alt+8", "kb:NVDA+alt+9"]
	)
	def script_jumpToBookmark(self, gesture):
		"""Jump to a bookmark."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._bookmarkManager:
			# Translators: Error message when bookmark manager not initialized
			ui.message(_("Bookmark manager not available"))
			return

		# Get bookmark number from gesture (0-9)
		key = gesture.mainKeyName
		if key.isdigit():
			name = key
		else:
			name = "temp"

		if self._bookmarkManager.jump_to_bookmark(name):
			# Announce position after jump
			info = api.getReviewPosition()
			if info:
				text = info.text
				if text:
					ui.message(text)
				else:
					# Translators: Message when jumping to bookmark
					ui.message(_("Jumped to bookmark {name}").format(name=name))
		else:
			# Translators: Error message when bookmark not found
			ui.message(_("Bookmark {name} not found").format(name=name))

	@scriptHandler.script(
		# Translators: Description for listing bookmarks
		description=_("List all bookmarks"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+shift+b"
	)
	def script_listBookmarks(self, gesture):
		"""List all bookmarks."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._bookmarkManager:
			# Translators: Error message when bookmark manager not initialized
			ui.message(_("Bookmark manager not available"))
			return

		bookmarks = self._bookmarkManager.list_bookmarks()
		if bookmarks:
			count = len(bookmarks)
			# Translators: Message listing bookmarks
			message = _("{count} bookmarks: {names}").format(
				count=count,
				names=", ".join(bookmarks)
			)
			ui.message(message)
		else:
			# Translators: Message when no bookmarks exist
			ui.message(_("No bookmarks set"))

	# Section 9: Tab management gestures (v1.0.39+)

	@scriptHandler.script(
		# Translators: Description for creating a new terminal tab
		description=_("Create a new tab in the terminal"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+shift+alt+t"
	)
	def script_createNewTab(self, gesture):
		"""Create a new tab in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Send the standard keyboard shortcut for creating a new tab
		# Most modern terminals use Ctrl+Shift+T
		try:
			import keyboardHandler
			# Press Ctrl+Shift+T to create new tab
			keyboardHandler.KeyboardInputGesture.fromName("control+shift+t").send()
			# Announce that we're creating a new tab
			# Translators: Message when creating a new tab
			ui.message(_("Creating new tab"))
		except Exception:
			# Translators: Error message when tab creation fails
			ui.message(_("Unable to create new tab"))

	@scriptHandler.script(
		# Translators: Description for listing/navigating tabs
		description=_("List tabs or switch to tab bar"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+t"
	)
	def script_listTabs(self, gesture):
		"""List all tabs or focus tab bar."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._tabManager:
			# Translators: Error message when tab manager not initialized
			ui.message(_("Tab manager not available"))
			return

		# Get list of known tabs
		tabs = self._tabManager.list_tabs()
		tab_count = self._tabManager.get_tab_count()
		current_tab_id = self._tabManager.get_current_tab_id()

		if tab_count == 0:
			# Translators: Message when no tabs are detected
			ui.message(_("No tabs detected"))
		elif tab_count == 1:
			# Only one tab, announce it
			# Translators: Message for single tab
			ui.message(_("Single tab: {title}").format(title=tabs[0].get('title', 'Unknown')))
		else:
			# Multiple tabs - show simple announcement for now
			# (Full dialog implementation would go here)
			# Translators: Message listing tab count
			ui.message(_("{count} tabs detected").format(count=tab_count))

			# Also send Ctrl+Tab to switch to next tab
			try:
				import keyboardHandler
				keyboardHandler.KeyboardInputGesture.fromName("control+tab").send()
				# Translators: Message when switching tabs
				ui.message(_("Switching to next tab"))
			except Exception:
				pass

	# Section 8.1: Command history navigation gestures (v1.0.31+)

	@scriptHandler.script(
		# Translators: Description for scanning command history
		description=_("Scan terminal output to detect and store command history"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+shift+h"
	)
	def script_scanCommandHistory(self, gesture):
		"""Scan terminal output for commands."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._commandHistoryManager:
			# Translators: Error message when command history manager not initialized
			ui.message(_("Command history not available"))
			return

		# Scan terminal output for commands
		count = self._commandHistoryManager.detect_and_store_commands()

		if count > 0:
			total = self._commandHistoryManager.get_history_count()
			# Translators: Message when commands detected
			ui.message(_("Found {count} new commands, {total} total").format(count=count, total=total))
		else:
			# Translators: Message when no new commands found
			ui.message(_("No new commands found"))

	@scriptHandler.script(
		# Translators: Description for previous command navigation
		description=_("Navigate to previous command in history"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+upArrow"
	)
	def script_previousCommand(self, gesture):
		"""Navigate to previous command."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._commandHistoryManager:
			# Translators: Error message when command history manager not initialized
			ui.message(_("Command history not available"))
			return

		# Auto-scan if history is empty
		if self._commandHistoryManager.get_history_count() == 0:
			self._commandHistoryManager.detect_and_store_commands()

		if not self._commandHistoryManager.navigate_history(-1):
			# Translators: Message when at beginning of history
			ui.message(_("No previous command"))

	@scriptHandler.script(
		# Translators: Description for next command navigation
		description=_("Navigate to next command in history"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+downArrow"
	)
	def script_nextCommand(self, gesture):
		"""Navigate to next command."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._commandHistoryManager:
			# Translators: Error message when command history manager not initialized
			ui.message(_("Command history not available"))
			return

		# Auto-scan if history is empty
		if self._commandHistoryManager.get_history_count() == 0:
			self._commandHistoryManager.detect_and_store_commands()

		if not self._commandHistoryManager.navigate_history(1):
			# Translators: Message when at end of history
			ui.message(_("No next command"))

	@scriptHandler.script(
		# Translators: Description for listing command history
		description=_("List all commands in history"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+shift+l"
	)
	def script_listCommandHistory(self, gesture):
		"""List all commands in history."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._commandHistoryManager:
			# Translators: Error message when command history manager not initialized
			ui.message(_("Command history not available"))
			return

		# Auto-scan if history is empty
		if self._commandHistoryManager.get_history_count() == 0:
			self._commandHistoryManager.detect_and_store_commands()

		history = self._commandHistoryManager.list_history()

		if history:
			count = len(history)
			# Create a summary of recent commands (last 5)
			recent = history[-5:] if count > 5 else history
			commands_list = ", ".join([f"{idx}: {cmd[:30]}" for idx, cmd in recent])

			# Translators: Message listing command history
			ui.message(_("{count} commands in history. Recent: {commands}").format(
				count=count,
				commands=commands_list
			))
		else:
			# Translators: Message when no commands in history
			ui.message(_("No commands in history"))

	# Section 8.2: Output search functionality gestures (v1.0.30+)

	@scriptHandler.script(
		# Translators: Description for searching output
		description=_("Search terminal output for text pattern"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+control+f"
	)
	def script_searchOutput(self, gesture):
		"""Search terminal output."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._searchManager:
			# Translators: Error message when search manager not initialized
			ui.message(_("Search not available"))
			return

		# Prompt for search text using wx dialog
		import wx

		def show_search_dialog():
			"""Show search dialog."""
			parent = gui.mainFrame
			dlg = wx.TextEntryDialog(
				parent,
				# Translators: Search dialog prompt
				_("Enter search text:"),
				# Translators: Search dialog title
				_("Search Terminal Output")
			)

			if dlg.ShowModal() == wx.ID_OK:
				search_text = dlg.GetValue()
				dlg.Destroy()

				if search_text:
					# Perform search (case insensitive by default)
					match_count = self._searchManager.search(search_text, case_sensitive=False)

					if match_count > 0:
						# Jump to first match
						self._searchManager.first_match()

						# Announce result
						info = self._searchManager.get_current_match_info()
						if info:
							match_num, total, line_text, line_num = info
							# Translators: Search results message
							message = _("Found {total} matches. Match {num} of {total}: {text}").format(
								num=match_num,
								total=total,
								text=line_text[:100]  # Truncate long lines
							)
							ui.message(message)
					else:
						# Translators: No matches found
						ui.message(_("No matches found for '{pattern}'").format(pattern=search_text))
			else:
				dlg.Destroy()

		# Run dialog in main thread
		wx.CallAfter(show_search_dialog)

	@scriptHandler.script(
		# Translators: Description for next search match
		description=_("Jump to next search match"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+f3"
	)
	def script_findNext(self, gesture):
		"""Jump to next search match."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._searchManager:
			return

		if self._searchManager.get_match_count() == 0:
			# Translators: No search results
			ui.message(_("No search results. Use NVDA+Control+F to search."))
			return

		if self._searchManager.next_match():
			info = self._searchManager.get_current_match_info()
			if info:
				match_num, total, line_text, line_num = info
				# Announce current line
				ui.message(line_text)
		else:
			# Translators: Error jumping to next match
			ui.message(_("Cannot jump to next match"))

	@scriptHandler.script(
		# Translators: Description for previous search match
		description=_("Jump to previous search match"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+shift+f3"
	)
	def script_findPrevious(self, gesture):
		"""Jump to previous search match."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._searchManager:
			return

		if self._searchManager.get_match_count() == 0:
			# Translators: No search results
			ui.message(_("No search results. Use NVDA+Control+F to search."))
			return

		if self._searchManager.previous_match():
			info = self._searchManager.get_current_match_info()
			if info:
				match_num, total, line_text, line_num = info
				# Announce current line
				ui.message(line_text)
		else:
			# Translators: Error jumping to previous match
			ui.message(_("Cannot jump to previous match"))

	def _copyToClipboard(self, text):
		"""
		Copy text to the Windows clipboard using NVDA's clipboard API.

		Args:
			text: The text to copy to the clipboard.
		"""
		try:
			result = api.copyToClip(text, notify=False)
			return result if isinstance(result, bool) else True
		except TypeError:
			# Older NVDA versions do not support the notify parameter
			try:
				result = api.copyToClip(text)
				return result if isinstance(result, bool) else True
			except Exception:
				return False
		except Exception:
			return False

	def _getReviewPosition(self):
		"""
		Return the current review position, re-binding to the terminal if None.

		Returns:
			textInfos.TextInfo or None if no terminal is bound.
		"""
		info = api.getReviewPosition()
		if info is not None:
			return info
		if self._boundTerminal is None:
			return None
		try:
			info = self._boundTerminal.makeTextInfo(textInfos.POSITION_CARET)
		except Exception:
			try:
				info = self._boundTerminal.makeTextInfo(textInfos.POSITION_LAST)
			except Exception:
				return None
		api.setReviewPosition(info)
		return info


class TerminalAccessSettingsPanel(SettingsPanel):
	"""
	Enhanced settings panel for Terminal Access configuration.

	Provides organized UI with logical grouping, tooltips, and reset functionality.
	Follows NVDA GUI guidelines for accessibility and usability.
	"""

	# Translators: Title for the Terminal Access settings category
	title = _("Terminal Settings")

	def makeSettings(self, settingsSizer):
		"""Create the settings UI elements with logical grouping."""
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# === Cursor Tracking Section ===
		# Translators: Label for cursor tracking settings group
		cursorGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Cursor Tracking")),
			wx.VERTICAL
		))
		sHelper.addItem(cursorGroup)

		# Cursor tracking checkbox
		# Translators: Label for cursor tracking checkbox
		self.cursorTrackingCheckBox = cursorGroup.addItem(
			wx.CheckBox(self, label=_("Enable cursor &tracking"))
		)
		self.cursorTrackingCheckBox.SetValue(config.conf["terminalAccess"]["cursorTracking"])
		# Translators: Tooltip for cursor tracking checkbox
		self.cursorTrackingCheckBox.SetToolTip(_(
			"Automatically announce cursor position changes in the terminal"
		))

		# Cursor tracking mode choice
		# Translators: Label for cursor tracking mode choice
		self.cursorTrackingModeChoice = cursorGroup.addLabeledControl(
			_("Cursor tracking &mode:"),
			wx.Choice,
			choices=[
				# Translators: Cursor tracking mode option
				_("Off"),
				# Translators: Cursor tracking mode option
				_("Standard"),
				# Translators: Cursor tracking mode option
				_("Highlight"),
				# Translators: Cursor tracking mode option
				_("Window")
			]
		)
		self.cursorTrackingModeChoice.SetSelection(config.conf["terminalAccess"]["cursorTrackingMode"])
		# Translators: Tooltip for cursor tracking mode
		self.cursorTrackingModeChoice.SetToolTip(_(
			"Standard: announce line/column changes, "
			"Highlight: announce highlighted text, "
			"Window: only announce within defined window"
		))

		# Cursor delay spinner
		# Translators: Label for cursor delay spinner
		self.cursorDelaySpinner = cursorGroup.addLabeledControl(
			_("Cursor delay (milliseconds):"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=1000,
			initial=config.conf["terminalAccess"]["cursorDelay"]
		)
		# Translators: Tooltip for cursor delay
		self.cursorDelaySpinner.SetToolTip(_(
			"Delay before announcing cursor position (0-1000ms). "
			"Higher values reduce announcement frequency."
		))

		# === Feedback Settings Section ===
		# Translators: Label for feedback settings group
		feedbackGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Feedback")),
			wx.VERTICAL
		))
		sHelper.addItem(feedbackGroup)

		# Key echo checkbox
		# Translators: Label for key echo checkbox
		self.keyEchoCheckBox = feedbackGroup.addItem(
			wx.CheckBox(self, label=_("Enable &key echo"))
		)
		self.keyEchoCheckBox.SetValue(config.conf["terminalAccess"]["keyEcho"])
		# Translators: Tooltip for key echo
		self.keyEchoCheckBox.SetToolTip(_(
			"Announce characters as you type in the terminal"
		))

		# Line pause checkbox
		# Translators: Label for line pause checkbox
		self.linePauseCheckBox = feedbackGroup.addItem(
			wx.CheckBox(self, label=_("Pause at &newlines"))
		)
		self.linePauseCheckBox.SetValue(config.conf["terminalAccess"]["linePause"])
		# Translators: Tooltip for line pause
		self.linePauseCheckBox.SetToolTip(_(
			"Brief pause when speaking line content to improve clarity"
		))

		# Punctuation level choice
		# Translators: Label for punctuation level choice
		self.punctuationLevelChoice = feedbackGroup.addLabeledControl(
			_("&Punctuation level:"),
			wx.Choice,
			choices=[
				# Translators: Punctuation level option
				_("None"),
				# Translators: Punctuation level option
				_("Some (.,?!;:)"),
				# Translators: Punctuation level option
				_("Most (adds @#$%^&*()_+=[]{}\\|<>/)"),
				# Translators: Punctuation level option
				_("All")
			]
		)
		self.punctuationLevelChoice.SetSelection(config.conf["terminalAccess"]["punctuationLevel"])
		# Translators: Tooltip for punctuation level
		self.punctuationLevelChoice.SetToolTip(_(
			"Controls which punctuation symbols are announced. "
			"Higher levels announce more symbols. "
			"Use NVDA+Alt+[ and ] to adjust quickly."
		))

		# Quiet mode checkbox
		# Translators: Label for quiet mode checkbox
		self.quietModeCheckBox = feedbackGroup.addItem(
			wx.CheckBox(self, label=_("&Quiet mode"))
		)
		self.quietModeCheckBox.SetValue(config.conf["terminalAccess"]["quietMode"])
		# Translators: Tooltip for quiet mode
		self.quietModeCheckBox.SetToolTip(_(
			"Suppress most Terminal Access announcements. Use NVDA+Alt+Q to toggle quickly."
		))

		# Verbose mode checkbox (Phase 6: Verbose Mode with Context)
		# Translators: Label for verbose mode checkbox
		self.verboseModeCheckBox = feedbackGroup.addItem(
			wx.CheckBox(self, label=_("&Verbose mode (detailed feedback)"))
		)
		self.verboseModeCheckBox.SetValue(config.conf["terminalAccess"]["verboseMode"])
		# Translators: Tooltip for verbose mode
		self.verboseModeCheckBox.SetToolTip(_(
			"Include position and context information with announcements. "
			"Useful for debugging and understanding terminal layout."
		))

		# Indentation announcement checkbox
		# Translators: Label for indentation announcement checkbox
		self.indentationOnLineReadCheckBox = feedbackGroup.addItem(
			wx.CheckBox(self, label=_("Announce &indentation when reading lines"))
		)
		self.indentationOnLineReadCheckBox.SetValue(config.conf["terminalAccess"]["indentationOnLineRead"])
		# Translators: Tooltip for indentation announcement
		self.indentationOnLineReadCheckBox.SetToolTip(_(
			"Automatically announce indentation level when reading lines. "
			"Use NVDA+Alt+F5 to toggle quickly. NVDA+Alt+I pressed twice still reads indentation."
		))

		# === Advanced Settings Section ===
		# Translators: Label for advanced settings group
		advancedGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Advanced")),
			wx.VERTICAL
		))
		sHelper.addItem(advancedGroup)

		# Repeated symbols checkbox
		# Translators: Label for repeated symbols checkbox
		self.repeatedSymbolsCheckBox = advancedGroup.addItem(
			wx.CheckBox(self, label=_("Condense &repeated symbols"))
		)
		self.repeatedSymbolsCheckBox.SetValue(config.conf["terminalAccess"]["repeatedSymbols"])
		# Translators: Tooltip for repeated symbols
		self.repeatedSymbolsCheckBox.SetToolTip(_(
			"Condense runs of repeated symbols (e.g., '====' becomes '4 equals')"
		))

		# Repeated symbols values text field
		# Translators: Label for repeated symbols values
		self.repeatedSymbolsValuesText = advancedGroup.addLabeledControl(
			_("Repeated symbols to condense:"),
			wx.TextCtrl
		)
		self.repeatedSymbolsValuesText.SetValue(config.conf["terminalAccess"]["repeatedSymbolsValues"])
		# Translators: Tooltip for repeated symbols values
		self.repeatedSymbolsValuesText.SetToolTip(_(
			"Characters that will be condensed when repeated. "
			"Example: -_=! (max 50 characters)"
		))

		# === Profile Management Section (Section 3: Profile Management UI) ===
		# Translators: Label for profile management group
		profileGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Application Profiles")),
			wx.VERTICAL
		))
		sHelper.addItem(profileGroup)

		# Profile list
		# Translators: Label for profile list
		self.profileList = profileGroup.addLabeledControl(
			_("Installed &profiles:"),
			wx.Choice,
			choices=self._getProfileNames(withIndicators=True)
		)
		if len(self._getProfileNames()) > 0:
			self.profileList.SetSelection(0)
		# Translators: Tooltip for profile list
		self.profileList.SetToolTip(_(
			"Select an application profile to view or edit. "
			"Profiles customize Terminal Access behavior for specific applications. "
			"Active and default profiles are marked."
		))

		# Default profile dropdown
		# Translators: Label for default profile choice
		defaultProfileChoices = [_("None (use global settings)")] + self._getProfileNames()
		self.defaultProfileChoice = profileGroup.addLabeledControl(
			_("&Default profile:"),
			wx.Choice,
			choices=defaultProfileChoices
		)
		# Set current default profile selection
		currentDefault = config.conf["terminalAccess"].get("defaultProfile", "")
		if currentDefault and currentDefault in self._profileManager.profiles:
			# Find index (+1 because "None" is at index 0)
			profileNames = self._getProfileNames()
			if currentDefault in profileNames:
				self.defaultProfileChoice.SetSelection(profileNames.index(currentDefault) + 1)
			else:
				self.defaultProfileChoice.SetSelection(0)
		else:
			self.defaultProfileChoice.SetSelection(0)
		# Translators: Tooltip for default profile
		self.defaultProfileChoice.SetToolTip(_(
			"Profile to use when no application-specific profile is detected. "
			"Use NVDA+Alt+0 to check which profile is active."
		))

		# Profile action buttons
		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)

		# Translators: Label for new profile button
		self.newProfileButton = wx.Button(self, label=_("&New Profile..."))
		self.newProfileButton.Bind(wx.EVT_BUTTON, self.onNewProfile)
		# Translators: Tooltip for new profile button
		self.newProfileButton.SetToolTip(_(
			"Create a new application profile with custom settings"
		))
		buttonSizer.Add(self.newProfileButton, flag=wx.RIGHT, border=5)

		# Translators: Label for edit profile button
		self.editProfileButton = wx.Button(self, label=_("&Edit Profile..."))
		self.editProfileButton.Bind(wx.EVT_BUTTON, self.onEditProfile)
		# Translators: Tooltip for edit profile button
		self.editProfileButton.SetToolTip(_(
			"Edit the selected application profile"
		))
		buttonSizer.Add(self.editProfileButton, flag=wx.RIGHT, border=5)

		# Translators: Label for delete profile button
		self.deleteProfileButton = wx.Button(self, label=_("&Delete Profile"))
		self.deleteProfileButton.Bind(wx.EVT_BUTTON, self.onDeleteProfile)
		# Translators: Tooltip for delete profile button
		self.deleteProfileButton.SetToolTip(_(
			"Delete the selected custom profile (default profiles cannot be deleted)"
		))
		buttonSizer.Add(self.deleteProfileButton, flag=wx.RIGHT, border=5)

		profileGroup.sizer.Add(buttonSizer, flag=wx.TOP, border=5)

		# Import/Export buttons
		importExportSizer = wx.BoxSizer(wx.HORIZONTAL)

		# Translators: Label for import profile button
		self.importProfileButton = wx.Button(self, label=_("&Import..."))
		self.importProfileButton.Bind(wx.EVT_BUTTON, self.onImportProfile)
		# Translators: Tooltip for import profile button
		self.importProfileButton.SetToolTip(_(
			"Import a profile from a JSON file"
		))
		importExportSizer.Add(self.importProfileButton, flag=wx.RIGHT, border=5)

		# Translators: Label for export profile button
		self.exportProfileButton = wx.Button(self, label=_("E&xport..."))
		self.exportProfileButton.Bind(wx.EVT_BUTTON, self.onExportProfile)
		# Translators: Tooltip for export profile button
		self.exportProfileButton.SetToolTip(_(
			"Export the selected profile to a JSON file"
		))
		importExportSizer.Add(self.exportProfileButton)

		profileGroup.sizer.Add(importExportSizer, flag=wx.TOP, border=5)

		# Update button states based on selection
		self.profileList.Bind(wx.EVT_CHOICE, self.onProfileSelection)
		self.onProfileSelection(None)  # Initialize button states

		# === Reset Button ===
		# Translators: Label for reset to defaults button
		self.resetButton = sHelper.addItem(
			wx.Button(self, label=_("&Reset to Defaults"))
		)
		# Translators: Tooltip for reset button
		self.resetButton.SetToolTip(_(
			"Reset all Terminal Access settings to their default values"
		))
		self.resetButton.Bind(wx.EVT_BUTTON, self.onResetToDefaults)

	def onResetToDefaults(self, event):
		"""Reset all settings to their default values."""
		# Translators: Confirmation dialog for resetting settings
		result = gui.messageBox(
			_("Are you sure you want to reset all Terminal Access settings to their default values?"),
			_("Confirm Reset"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
		)

		if result == wx.YES:
			# Reset all settings to defaults
			config.conf["terminalAccess"]["cursorTracking"] = True
			config.conf["terminalAccess"]["cursorTrackingMode"] = CT_STANDARD
			config.conf["terminalAccess"]["keyEcho"] = True
			config.conf["terminalAccess"]["linePause"] = True
			config.conf["terminalAccess"]["punctuationLevel"] = PUNCT_MOST
			config.conf["terminalAccess"]["repeatedSymbols"] = False
			config.conf["terminalAccess"]["repeatedSymbolsValues"] = "-_=!"
			config.conf["terminalAccess"]["cursorDelay"] = 20
			config.conf["terminalAccess"]["quietMode"] = False
			config.conf["terminalAccess"]["verboseMode"] = False  # Phase 6: Verbose Mode
			config.conf["terminalAccess"]["indentationOnLineRead"] = False

			# Update UI to reflect defaults
			self.cursorTrackingCheckBox.SetValue(True)
			self.cursorTrackingModeChoice.SetSelection(CT_STANDARD)
			self.keyEchoCheckBox.SetValue(True)
			self.linePauseCheckBox.SetValue(True)
			self.punctuationLevelChoice.SetSelection(PUNCT_MOST)
			self.repeatedSymbolsCheckBox.SetValue(False)
			self.repeatedSymbolsValuesText.SetValue("-_=!")
			self.cursorDelaySpinner.SetValue(20)
			self.quietModeCheckBox.SetValue(False)
			self.verboseModeCheckBox.SetValue(False)  # Phase 6: Verbose Mode
			self.indentationOnLineReadCheckBox.SetValue(False)

			# Translators: Message after resetting to defaults
			gui.messageBox(
				_("All settings have been reset to their default values."),
				_("Settings Reset"),
				wx.OK | wx.ICON_INFORMATION
			)

	def onSave(self):
		"""Save the settings when the user clicks OK with validation."""
		# Validate and save cursor tracking mode
		trackingMode = self.cursorTrackingModeChoice.GetSelection()
		config.conf["terminalAccess"]["cursorTracking"] = self.cursorTrackingCheckBox.GetValue()
		config.conf["terminalAccess"]["cursorTrackingMode"] = _validateInteger(
			trackingMode, 0, 3, 1, "cursorTrackingMode"
		)

		# Boolean settings (no validation needed)
		config.conf["terminalAccess"]["keyEcho"] = self.keyEchoCheckBox.GetValue()
		config.conf["terminalAccess"]["linePause"] = self.linePauseCheckBox.GetValue()
		config.conf["terminalAccess"]["repeatedSymbols"] = self.repeatedSymbolsCheckBox.GetValue()
		config.conf["terminalAccess"]["quietMode"] = self.quietModeCheckBox.GetValue()
		config.conf["terminalAccess"]["verboseMode"] = self.verboseModeCheckBox.GetValue()  # Phase 6: Verbose Mode
		config.conf["terminalAccess"]["indentationOnLineRead"] = self.indentationOnLineReadCheckBox.GetValue()

		# Validate and save punctuation level
		punctLevel = self.punctuationLevelChoice.GetSelection()
		config.conf["terminalAccess"]["punctuationLevel"] = _validateInteger(
			punctLevel, 0, 3, 2, "punctuationLevel"
		)

		# Validate and save repeated symbols string
		repeatedSymbolsValue = self.repeatedSymbolsValuesText.GetValue()
		config.conf["terminalAccess"]["repeatedSymbolsValues"] = _validateString(
			repeatedSymbolsValue, MAX_REPEATED_SYMBOLS_LENGTH, "-_=!", "repeatedSymbolsValues"
		)

		# Validate and save cursor delay
		cursorDelay = self.cursorDelaySpinner.GetValue()
		config.conf["terminalAccess"]["cursorDelay"] = _validateInteger(
			cursorDelay, 0, 1000, 20, "cursorDelay"
		)

		# Save default profile setting
		defaultProfileIndex = self.defaultProfileChoice.GetSelection()
		if defaultProfileIndex == 0:
			# "None" was selected
			config.conf["terminalAccess"]["defaultProfile"] = ""
		else:
			# Get the profile name (subtract 1 for "None" offset)
			profileNames = self._getProfileNames()
			if defaultProfileIndex - 1 < len(profileNames):
				config.conf["terminalAccess"]["defaultProfile"] = profileNames[defaultProfileIndex - 1]
			else:
				config.conf["terminalAccess"]["defaultProfile"] = ""

	def _getProfileNames(self, withIndicators=False):
		"""Get list of profile names for the dropdown.

		Args:
			withIndicators: If True, add indicators for active/default profiles
		"""
		try:
			# Get the global plugin instance to access ProfileManager
			from . import terminalAccess
			for plugin in globalPluginHandler.runningPlugins:
				if isinstance(plugin, terminalAccess.GlobalPlugin):
					if hasattr(plugin, '_profileManager') and plugin._profileManager:
						names = list(plugin._profileManager.profiles.keys())
						# Sort with default profiles first, then custom profiles
						default_profiles = ['vim', 'nvim', 'tmux', 'htop', 'less', 'more', 'git', 'nano', 'irssi']
						defaults = [n for n in names if n in default_profiles]
						customs = [n for n in names if n not in default_profiles]
						sortedNames = sorted(defaults) + sorted(customs)

						if withIndicators:
							# Add indicators for active and default profiles
							activeProfile = plugin._currentProfile
							defaultProfileName = config.conf["terminalAccess"].get("defaultProfile", "")

							indicatorNames = []
							for name in sortedNames:
								indicators = []
								# Check if this is the active profile
								if activeProfile and activeProfile.appName == name:
									# Translators: Indicator for currently active profile
									indicators.append(_("Active"))
								# Check if this is the default profile
								if name == defaultProfileName:
									# Translators: Indicator for default profile
									indicators.append(_("Default"))

								if indicators:
									indicatorNames.append(f"{name} ({', '.join(indicators)})")
								else:
									indicatorNames.append(name)
							return indicatorNames
						else:
							return sortedNames
			return []
		except Exception:
			return []

	def _getSelectedProfileName(self):
		"""Get the currently selected profile name (without indicators)."""
		selection = self.profileList.GetSelection()
		if selection != wx.NOT_FOUND:
			displayName = self.profileList.GetString(selection)
			# Strip indicators like " (Active)" or " (Default)" or " (Active, Default)"
			# Extract the profile name before any parentheses
			if ' (' in displayName:
				return displayName.split(' (')[0]
			return displayName
		return None

	def _isDefaultProfile(self, profileName):
		"""Check if a profile is a default (built-in) profile."""
		default_profiles = ['vim', 'nvim', 'tmux', 'htop', 'less', 'more', 'git', 'nano', 'irssi']
		return profileName in default_profiles

	def onProfileSelection(self, event):
		"""Update button states when profile selection changes."""
		profileName = self._getSelectedProfileName()
		hasSelection = profileName is not None
		isDefault = self._isDefaultProfile(profileName) if profileName else False

		# Enable/disable buttons based on selection
		self.editProfileButton.Enable(hasSelection)
		self.deleteProfileButton.Enable(hasSelection and not isDefault)
		self.exportProfileButton.Enable(hasSelection)

	def onNewProfile(self, event):
		"""Create a new application profile."""
		# Translators: Message for profile creation
		gui.messageBox(
			_("Profile creation dialog will be implemented soon. "
			  "For now, profiles can be created programmatically via the ProfileManager API."),
			_("Feature In Development"),
			wx.OK | wx.ICON_INFORMATION
		)

	def onEditProfile(self, event):
		"""Edit the selected profile."""
		profileName = self._getSelectedProfileName()
		if not profileName:
			return

		# Translators: Message for profile editing
		gui.messageBox(
			_("Profile editing dialog will be implemented soon. "
			  "Selected profile: {name}").format(name=profileName),
			_("Feature In Development"),
			wx.OK | wx.ICON_INFORMATION
		)

	def onDeleteProfile(self, event):
		"""Delete the selected custom profile."""
		profileName = self._getSelectedProfileName()
		if not profileName or self._isDefaultProfile(profileName):
			return

		# Translators: Confirmation dialog for deleting profile
		result = gui.messageBox(
			_("Are you sure you want to delete the profile '{name}'?").format(name=profileName),
			_("Confirm Delete"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
		)

		if result == wx.YES:
			try:
				# Get the global plugin instance to access ProfileManager
				from . import terminalAccess
				for plugin in globalPluginHandler.runningPlugins:
					if isinstance(plugin, terminalAccess.GlobalPlugin):
						if hasattr(plugin, '_profileManager') and plugin._profileManager:
							plugin._profileManager.removeProfile(profileName)
							# Update the profile list
							self.profileList.SetItems(self._getProfileNames())
							if len(self._getProfileNames()) > 0:
								self.profileList.SetSelection(0)
							self.onProfileSelection(None)
							# Translators: Message after deleting profile
							gui.messageBox(
								_("Profile '{name}' has been deleted.").format(name=profileName),
								_("Profile Deleted"),
								wx.OK | wx.ICON_INFORMATION
							)
							return
			except Exception as e:
				import logHandler
				logHandler.log.error(f"Terminal Access: Failed to delete profile: {e}")
				# Translators: Error message for profile deletion
				gui.messageBox(
					_("Failed to delete profile. See NVDA log for details."),
					_("Error"),
					wx.OK | wx.ICON_ERROR
				)

	def onImportProfile(self, event):
		"""Import a profile from a JSON file."""
		# Translators: File dialog for importing profile
		with wx.FileDialog(
			self,
			_("Import Profile"),
			defaultDir=os.path.expanduser("~"),
			wildcard=_("JSON files (*.json)|*.json"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
		) as fileDialog:
			if fileDialog.ShowModal() == wx.ID_CANCEL:
				return

			pathname = fileDialog.GetPath()
			try:
				import json
				with open(pathname, 'r', encoding='utf-8') as f:
					profileData = json.load(f)

				# Get the global plugin instance to access ProfileManager
				from . import terminalAccess
				for plugin in globalPluginHandler.runningPlugins:
					if isinstance(plugin, terminalAccess.GlobalPlugin):
						if hasattr(plugin, '_profileManager') and plugin._profileManager:
							profile = plugin._profileManager.importProfile(profileData)
							# Update the profile list
							self.profileList.SetItems(self._getProfileNames())
							# Select the newly imported profile
							profileIndex = self.profileList.FindString(profile.appName)
							if profileIndex != wx.NOT_FOUND:
								self.profileList.SetSelection(profileIndex)
							self.onProfileSelection(None)
							# Translators: Message after importing profile
							gui.messageBox(
								_("Profile '{name}' has been imported successfully.").format(
									name=profile.displayName
								),
								_("Profile Imported"),
								wx.OK | wx.ICON_INFORMATION
							)
							return
			except Exception as e:
				import logHandler
				logHandler.log.error(f"Terminal Access: Failed to import profile: {e}")
				# Translators: Error message for profile import
				gui.messageBox(
					_("Failed to import profile. The file may be invalid or corrupted."),
					_("Import Error"),
					wx.OK | wx.ICON_ERROR
				)

	def onExportProfile(self, event):
		"""Export the selected profile to a JSON file."""
		profileName = self._getSelectedProfileName()
		if not profileName:
			return

		try:
			# Get the global plugin instance to access ProfileManager
			from . import terminalAccess
			for plugin in globalPluginHandler.runningPlugins:
				if isinstance(plugin, terminalAccess.GlobalPlugin):
					if hasattr(plugin, '_profileManager') and plugin._profileManager:
						profileData = plugin._profileManager.exportProfile(profileName)
						if not profileData:
							return

						# Translators: File dialog for exporting profile
						with wx.FileDialog(
							self,
							_("Export Profile"),
							defaultDir=os.path.expanduser("~"),
							defaultFile=f"{profileName}_profile.json",
							wildcard=_("JSON files (*.json)|*.json"),
							style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
						) as fileDialog:
							if fileDialog.ShowModal() == wx.ID_CANCEL:
								return

							pathname = fileDialog.GetPath()
							import json
							with open(pathname, 'w', encoding='utf-8') as f:
								json.dump(profileData, f, indent=2, ensure_ascii=False)

							# Translators: Message after exporting profile
							gui.messageBox(
								_("Profile '{name}' has been exported successfully.").format(name=profileName),
								_("Profile Exported"),
								wx.OK | wx.ICON_INFORMATION
							)
							return
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Failed to export profile: {e}")
			# Translators: Error message for profile export
			gui.messageBox(
				_("Failed to export profile. See NVDA log for details."),
				_("Export Error"),
				wx.OK | wx.ICON_ERROR
			)
