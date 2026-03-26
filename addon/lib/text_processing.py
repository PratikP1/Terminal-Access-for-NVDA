# Terminal Access text processing utilities.
# Extracted from terminalAccess.py for modularization.

import re
import unicodedata
import functools
from typing import Any

import characterProcessing

# Cache native and wcwidth availability at import time to avoid
# per-character sys.modules lookups on the hot path.
try:
	from native.termaccess_bridge import (
		native_char_width as _native_char_width,
		native_text_width as _native_text_width,
		native_extract_column_range as _native_extract_column_range,
		native_find_column_position as _native_find_column_position,
		native_available as _native_available_fn,
	)
	_HAS_NATIVE_WIDTH = _native_available_fn()
except Exception:
	_HAS_NATIVE_WIDTH = False

try:
	import wcwidth as _wcwidth
except ImportError:
	_wcwidth = None

@functools.lru_cache(maxsize=512)
def _get_symbol_description(locale: str, char: str) -> str:
	"""
	Return a locale-aware spoken name for *char* using NVDA's character processing.

	Delegates to ``characterProcessing.processSpeechSymbol`` so that symbol
	names respect the user's configured NVDA language (e.g. ``.`` → "dot" in
	English, "punto" in Spanish).  Falls back to the lowercased Unicode name
	if NVDA has no mapping for the character.

	Cached with ``functools.lru_cache`` keyed on *(locale, char)* so that
	repeated lookups (common during typing) are fast, and a language change
	invalidates stale entries naturally.
	"""
	if char.isalnum():
		return char
	result = characterProcessing.processSpeechSymbol(locale, char)
	# processSpeechSymbol returns the character unchanged when no mapping exists
	if result != char:
		return result
	# Fall back to Unicode name for unmapped symbols
	name = unicodedata.name(char, "")
	return name.lower() if name else char



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

	# Compiled regex patterns (class-level to avoid recompilation per call)
	_SGR_PATTERN: re.Pattern[str] = re.compile(r'\x1b\[([0-9;]+)m')
	_STRIP_PATTERN: re.Pattern[str] = re.compile(
		r'\x1b'           # ESC
		r'(?:'
		r'\[[0-9;?]*[a-zA-Z~]'            # CSI sequences (including private modes like ?25h)
		r'|\][^\x07\x1b]*(?:\x07|\x1b\\)' # OSC sequences (BEL or ST terminated)
		r'|P[^\x1b]*\x1b\\'               # DCS sequences (ST terminated)
		r'|[()][A-Z0-9]'                   # Charset designation (e.g., (B, )0)
		r'|[a-zA-Z0-9=><~]'               # Two-char ESC sequences (e.g., M, 7, 8)
		r')'
	)

	def __init__(self) -> None:
		"""Initialize the ANSI parser."""
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

	def parse(self, text: str) -> dict[str, Any]:
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
		matches = self._SGR_PATTERN.findall(text)

		for match in matches:
			codes = [int(c) for c in match.split(';') if c]
			self._processCodes(codes)

		return self._getCurrentAttributes()

	def _processCodes(self, codes: list[int]) -> None:
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

	def _getCurrentAttributes(self) -> dict[str, Any]:
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
		return ANSIParser._STRIP_PATTERN.sub('', text)


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

		Returns:
			int: Display width (0, 1, or 2 columns)
		"""
		if _HAS_NATIVE_WIDTH:
			return _native_char_width(char)
		if _wcwidth is not None:
			width = _wcwidth.wcwidth(char)
			return max(0, width) if width is not None else 1
		return 1

	@staticmethod
	def getTextWidth(text: str) -> int:
		"""
		Calculate total display width of a text string.

		Returns:
			int: Total display width in columns
		"""
		if _HAS_NATIVE_WIDTH:
			return _native_text_width(text)
		if _wcwidth is not None:
			width = _wcwidth.wcswidth(text)
			if width >= 0:
				return width
			# Control characters present — sum per-character
			return sum(max(0, _wcwidth.wcwidth(c)) for c in text)
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
		if _HAS_NATIVE_WIDTH:
			return _native_extract_column_range(text, startCol, endCol)

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
		if _HAS_NATIVE_WIDTH:
			return _native_find_column_position(text, targetCol)

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

	def extract_emoji_list(self, text: str) -> list[str]:
		"""
		Extract all emoji from text.

		Args:
			text: Text to analyze

		Returns:
			list[str]: List of emoji found in text
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


class ErrorLineDetector:
	"""Detect error and warning patterns in terminal output lines.

	Uses structured patterns (word boundaries, delimiters) to avoid
	false positives. "mirror" won't match "error", "forewarning" won't
	match "warning". Patterns are based on real compiler, linter, shell,
	and build tool output formats.
	"""

	# Compiled regex patterns for error detection.
	# Each pattern uses word boundaries or structural delimiters to
	# avoid matching keywords inside unrelated words.
	_ERROR_PATTERNS = [
		# Structured prefixes: "error:", "error[", "ERROR:", "[ERROR]"
		re.compile(r'\berror\b[\[:\s]', re.IGNORECASE),
		# "fatal:" or "fatal error"
		re.compile(r'\bfatal\b[\s:]', re.IGNORECASE),
		# "FAILED" as standalone word (pytest, make)
		re.compile(r'\bFAILED\b'),
		# "FAILURE:" (Gradle)
		re.compile(r'\bFAILURE\b:', re.IGNORECASE),
		# Exception types: "ValueError:", "RuntimeError:", "SyntaxError:"
		re.compile(r'\b\w*Error\b:', re.IGNORECASE),
		re.compile(r'\b\w*Exception\b:', re.IGNORECASE),
		# Python traceback header
		re.compile(r'^Traceback \(most recent call last\):', re.IGNORECASE),
		# "panic:" (Go, Rust)
		re.compile(r'\bpanic\b:', re.IGNORECASE),
		# "Segmentation fault"
		re.compile(r'\bSegmentation fault\b', re.IGNORECASE),
		# "segfault" as standalone word
		re.compile(r'\bsegfault\b', re.IGNORECASE),
		# Shell errors: "Permission denied", "command not found", "No such file"
		re.compile(r'\bPermission denied\b', re.IGNORECASE),
		re.compile(r'\bcommand not found\b', re.IGNORECASE),
		re.compile(r'\bNo such file or directory\b', re.IGNORECASE),
		# npm ERR!
		re.compile(r'\bnpm ERR!'),
		# Bracketed severity: [ERROR], [FATAL]
		re.compile(r'\[ERROR\]', re.IGNORECASE),
		re.compile(r'\[FATAL\]', re.IGNORECASE),
		# Make: *** [...] Error
		re.compile(r'\*\*\*.*\bError\b'),
		# CMake Error
		re.compile(r'\bCMake Error\b'),
		# "Connection refused" as full phrase
		re.compile(r'\bConnection refused\b', re.IGNORECASE),
		# Flake8/pylint error codes: E#### at word boundary
		re.compile(r'\b[EF]\d{3,4}\b'),
	]

	_WARNING_PATTERNS = [
		# Structured prefixes: "warning:", "WARNING:", "[WARNING]"
		re.compile(r'\bwarning\b[\s:\[]', re.IGNORECASE),
		# "deprecated" as standalone word
		re.compile(r'\bdeprecated\b', re.IGNORECASE),
		# "caution:" as structured prefix
		re.compile(r'\bcaution\b:', re.IGNORECASE),
		# CMake Warning
		re.compile(r'\bCMake Warning\b'),
		# Bracketed severity: [WARNING], [WARN]
		re.compile(r'\[WARNING\]', re.IGNORECASE),
		re.compile(r'\[WARN\]', re.IGNORECASE),
		# "warn:" as structured prefix (Rust, Node)
		re.compile(r'\bwarn\b:', re.IGNORECASE),
	]

	@staticmethod
	def classify(line_text: str) -> str | None:
		"""Classify a line as 'error', 'warning', or None.

		Uses regex patterns with word boundaries to avoid false positives.
		Error patterns are checked first (higher priority).

		Args:
			line_text: The line text to check.

		Returns:
			'error', 'warning', or None.
		"""
		if not line_text:
			return None
		for pattern in ErrorLineDetector._ERROR_PATTERNS:
			if pattern.search(line_text):
				return 'error'
		for pattern in ErrorLineDetector._WARNING_PATTERNS:
			if pattern.search(line_text):
				return 'warning'
		return None

