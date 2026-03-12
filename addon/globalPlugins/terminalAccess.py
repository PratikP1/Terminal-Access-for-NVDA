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
	   - Command Layer: modal input mode (NVDA+') that binds single-key
	     gestures from _COMMAND_LAYER_MAP so commands do not require
	     NVDA modifier combos; auto-exits on focus loss

Key Features:
	- Command Layer: Press NVDA+' to enter single-key command mode; press Escape
	  or NVDA+' again to exit. All navigation, selection, configuration, and
	  search commands become simple single-key presses (e.g. u/i/o for line
	  navigation, j/k/l for word navigation, f for search, etc.).
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
import collections
import functools
import os
import re
import time
import threading
import webbrowser
import unicodedata
from scriptHandler import script
import scriptHandler
import globalCommands
import speech
import characterProcessing
import languageHandler
import tones
from typing import Any

try:
	import braille
	_braille_available = True
except (ImportError, AttributeError):
	_braille_available = False

# Native (Rust) acceleration — optional, falls back to pure Python.
try:
	from native.termaccess_bridge import (
		native_available as _native_available_fn,
		NativeTextDiffer as _NativeTextDiffer,
		native_strip_ansi as _native_strip_ansi,
		native_search_text as _native_search_text,
		NativePositionCache as _NativePositionCache,
		get_helper as _get_helper,
		stop_helper as _stop_helper,
		start_helper_eagerly as _start_helper_eagerly,
	)
	_native_available = _native_available_fn()
except Exception:
	_native_available = False
	def _get_helper():
		return None
	def _stop_helper():
		pass
	def _start_helper_eagerly():
		pass

try:
	addonHandler.initTranslation()
except (ImportError, AttributeError, OSError):
	# If translation initialization fails, provide a fallback function
	def _(text):
		return text

# Script category for Terminal Access commands
SCRCAT_TERMINALACCESS = _("Terminal Access")

# Command layer key map: single-key gestures → script names (without "script_" prefix).
# When the command layer is active (entered via NVDA+'), these simple key presses
# invoke the corresponding script, avoiding the need for NVDA modifier combos.
_COMMAND_LAYER_MAP = {
	# Line navigation
	"kb:u": "readPreviousLine",
	"kb:i": "readCurrentLine",
	"kb:o": "readNextLine",
	# Word navigation
	"kb:j": "readPreviousWord",
	"kb:k": "readCurrentWord",
	"kb:l": "readNextWord",
	# Character navigation
	"kb:m": "readPreviousChar",
	"kb:,": "readCurrentChar",
	"kb:.": "readNextChar",
	# Boundary movement
	"kb:home": "reviewHome",
	"kb:end": "reviewEnd",
	"kb:pageUp": "reviewTop",
	"kb:pageDown": "reviewBottom",
	# Directional reading
	"kb:shift+leftArrow": "readToLeft",
	"kb:shift+rightArrow": "readToRight",
	"kb:shift+upArrow": "readToTop",
	"kb:shift+downArrow": "readToBottom",
	# Information & attributes
	"kb:;": "announcePosition",
	"kb:a": "sayAll",
	"kb:shift+a": "readAttributes",
	# Selection & copying
	"kb:r": "toggleMark",
	"kb:c": "copyLinearSelection",
	"kb:shift+c": "copyRectangularSelection",
	"kb:x": "clearMarks",
	"kb:v": "copyMode",
	# Window management
	"kb:w": "readWindow",
	"kb:shift+w": "setWindow",
	"kb:control+w": "clearWindow",
	"kb:y": "cycleCursorTrackingMode",
	# Configuration
	"kb:q": "toggleQuietMode",
	"kb:n": "toggleAnnounceNewOutput",
	"kb:[": "decreasePunctuationLevel",
	"kb:]": "increasePunctuationLevel",
	"kb:d": "toggleIndentation",
	"kb:p": "announceActiveProfile",
	# Bookmarks (0-9 for jump, shift+0-9 for set)
	"kb:0": "jumpToBookmark",
	"kb:1": "jumpToBookmark",
	"kb:2": "jumpToBookmark",
	"kb:3": "jumpToBookmark",
	"kb:4": "jumpToBookmark",
	"kb:5": "jumpToBookmark",
	"kb:6": "jumpToBookmark",
	"kb:7": "jumpToBookmark",
	"kb:8": "jumpToBookmark",
	"kb:9": "jumpToBookmark",
	"kb:shift+0": "setBookmark",
	"kb:shift+1": "setBookmark",
	"kb:shift+2": "setBookmark",
	"kb:shift+3": "setBookmark",
	"kb:shift+4": "setBookmark",
	"kb:shift+5": "setBookmark",
	"kb:shift+6": "setBookmark",
	"kb:shift+7": "setBookmark",
	"kb:shift+8": "setBookmark",
	"kb:shift+9": "setBookmark",
	"kb:b": "listBookmarks",
	# Tab management
	"kb:t": "createNewTab",
	"kb:shift+t": "listTabs",
	# Command history
	"kb:h": "previousCommand",
	"kb:g": "nextCommand",
	"kb:shift+h": "scanCommandHistory",
	"kb:shift+l": "listCommandHistory",
	# Search
	"kb:f": "searchOutput",
	"kb:f3": "findNext",
	"kb:shift+f3": "findPrevious",
	# Help & settings
	"kb:f1": "showHelp",
	"kb:s": "openSettings",
	# URL list (elements)
	"kb:e": "listUrls",
	# Layer exit
	"kb:escape": "exitCommandLayer",
}

# Default gesture bindings: gesture string → script name (without "script_" prefix).
# Stored as a module-level constant so NVDA's Input Gestures dialog can display
# all Terminal Access commands (via the class-level __gestures dict) and the
# dynamic binding system can reference them without name-mangling issues.
_DEFAULT_GESTURES = {
	"kb:NVDA+shift+f1": "showHelp",
	"kb:NVDA+u": "readPreviousLine",
	"kb:NVDA+i": "readCurrentLine",
	"kb:NVDA+o": "readNextLine",
	"kb:NVDA+j": "readPreviousWord",
	"kb:NVDA+k": "readCurrentWord",
	"kb:NVDA+k,kb:NVDA+k": "spellCurrentWord",
	"kb:NVDA+l": "readNextWord",
	"kb:NVDA+m": "readPreviousChar",
	"kb:NVDA+,": "readCurrentChar",
	"kb:NVDA+.": "readNextChar",
	"kb:NVDA+shift+q": "toggleQuietMode",
	"kb:NVDA+shift+n": "toggleAnnounceNewOutput",
	"kb:NVDA+f5": "toggleIndentation",
	"kb:NVDA+v": "copyMode",
	"kb:NVDA+'": "toggleCommandLayer",
	"kb:NVDA+alt+y": "cycleCursorTrackingMode",
	"kb:NVDA+alt+f2": "setWindow",
	"kb:NVDA+alt+f3": "clearWindow",
	"kb:NVDA+alt+plus": "readWindow",
	"kb:NVDA+shift+a": "readAttributes",
	"kb:NVDA+a": "sayAll",
	"kb:NVDA+shift+home": "reviewHome",
	"kb:NVDA+shift+end": "reviewEnd",
	"kb:NVDA+f4": "reviewTop",
	"kb:NVDA+f6": "reviewBottom",
	"kb:NVDA+;": "announcePosition",
	"kb:NVDA+f10": "announceActiveProfile",
	"kb:NVDA+[": "decreasePunctuationLevel",
	"kb:NVDA+]": "increasePunctuationLevel",
	"kb:NVDA+shift+leftArrow": "readToLeft",
	"kb:NVDA+shift+rightArrow": "readToRight",
	"kb:NVDA+shift+upArrow": "readToTop",
	"kb:NVDA+shift+downArrow": "readToBottom",
	"kb:NVDA+r": "toggleMark",
	"kb:NVDA+c": "copyLinearSelection",
	"kb:NVDA+shift+c": "copyRectangularSelection",
	"kb:NVDA+x": "clearMarks",
	"kb:NVDA+shift+b": "listBookmarks",
	"kb:NVDA+shift+t": "createNewTab",
	"kb:NVDA+w": "listTabs",
	"kb:NVDA+shift+h": "scanCommandHistory",
	"kb:NVDA+h": "previousCommand",
	"kb:NVDA+g": "nextCommand",
	"kb:NVDA+shift+l": "listCommandHistory",
	"kb:NVDA+f": "searchOutput",
	"kb:NVDA+f3": "findNext",
	"kb:NVDA+shift+f3": "findPrevious",
	"kb:NVDA+alt+u": "listUrls",
	"kb:NVDA+alt+0": "setBookmark",
	"kb:NVDA+alt+1": "setBookmark",
	"kb:NVDA+alt+2": "setBookmark",
	"kb:NVDA+alt+3": "setBookmark",
	"kb:NVDA+alt+4": "setBookmark",
	"kb:NVDA+alt+5": "setBookmark",
	"kb:NVDA+alt+6": "setBookmark",
	"kb:NVDA+alt+7": "setBookmark",
	"kb:NVDA+alt+8": "setBookmark",
	"kb:NVDA+alt+9": "setBookmark",
	"kb:alt+0": "jumpToBookmark",
	"kb:alt+1": "jumpToBookmark",
	"kb:alt+2": "jumpToBookmark",
	"kb:alt+3": "jumpToBookmark",
	"kb:alt+4": "jumpToBookmark",
	"kb:alt+5": "jumpToBookmark",
	"kb:alt+6": "jumpToBookmark",
	"kb:alt+7": "jumpToBookmark",
	"kb:alt+8": "jumpToBookmark",
	"kb:alt+9": "jumpToBookmark",
}

# Gestures that are always bound regardless of user exclusions
_ALWAYS_BOUND = frozenset({"kb:NVDA+'", "kb:NVDA+shift+f1"})


def _gestureLabel(gesture: str, script_name: str) -> str:
	"""Format a gesture and script name into a human-readable label.

	Example: 'kb:NVDA+shift+c' + 'copyRectangularSelection'
	→ 'NVDA+Shift+C — Copy Rectangular Selection'
	"""
	import re
	key = gesture.replace("kb:", "")
	# Title-case each part of the key combo; keep NVDA uppercase
	parts = key.split("+")
	formatted = []
	for p in parts:
		if p.upper() == "NVDA":
			formatted.append("NVDA")
		elif len(p) > 1:
			formatted.append(p.capitalize())
		else:
			formatted.append(p.upper())
	key_display = "+".join(formatted)
	# Convert camelCase script name to spaced title
	label = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', script_name)
	return f"{key_display} \u2014 {label.title()}"


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
	"announceNewOutput": "boolean(default=False)",  # Announce newly appended terminal output
	"newOutputCoalesceMs": "integer(default=200, min=50, max=2000)",  # ms to wait before announcing accumulated output
	"newOutputMaxLines": "integer(default=20, min=1, max=200)",  # max lines before summarising
	"stripAnsiInOutput": "boolean(default=True)",  # strip ANSI codes from announced output
	"unboundGestures": "string(default='')",  # Comma-separated gestures excluded from direct binding
}

# Register configuration
config.conf.spec["terminalAccess"] = confspec

# ---------------------------------------------------------------------------
# Module-level constants (hoisted from hot-path methods)
# ---------------------------------------------------------------------------

# Frozenset of all supported terminal application names (used in isTerminalApp)
_SUPPORTED_TERMINALS: frozenset[str] = frozenset([
	# Built-in Windows terminal applications
	"windowsterminal",  # Windows Terminal
	"cmd",              # Command Prompt
	"powershell",       # Windows PowerShell
	"pwsh",             # PowerShell Core
	"conhost",          # Console Host
	# Third-party terminal emulators
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
	# WSL (Windows Subsystem for Linux)
	"wsl",              # WSL executable
	"bash",             # WSL bash
	# Modern GPU-accelerated terminals
	"ghostty",          # Ghostty
	"rio",              # Rio
	"waveterm",         # Wave Terminal
	"contour",          # Contour Terminal
	"cool-retro-term",  # Cool Retro Term
	# Remote access / professional terminals
	"mobaxterm",        # MobaXterm
	"securecrt",        # SecureCRT
	"ttermpro",         # Tera Term
	"mremoteng",        # mRemoteNG
	"royalts",          # Royal TS
])

# Applications that share a process name prefix with a supported terminal
# but are NOT terminals themselves.  Checked before _SUPPORTED_TERMINALS.
_NON_TERMINAL_APPS: frozenset[str] = frozenset([
	"securefx",         # VanDyke SecureFX (SFTP client, shares branding with SecureCRT)
	"sfxcl",            # SecureFX command-line utility
])

# Frozenset of built-in profile names that cannot be removed
_BUILTIN_PROFILE_NAMES: frozenset[str] = frozenset([
	'vim', 'tmux', 'htop', 'less', 'git', 'nano', 'irssi',
	'claude', 'lazygit', 'btop', 'btm', 'yazi', 'k9s',
])

# Terminals that strip ANSI escape codes from UIA text (highlight detection is pointless)
_ANSI_STRIPPING_TERMINALS: frozenset[str] = frozenset([
	"windowsterminal", "alacritty", "wezterm", "wezterm-gui",
	"ghostty", "rio", "contour",
])

# Compiled regex for stripping ANSI highlight codes (used in _extractHighlightedText)
_ANSI_HIGHLIGHT_RE: re.Pattern[str] = re.compile(r'\x1b\[[0-9;]*m')

# Compiled regex for stripping trailing spaces per line (conhost pads lines to screen width)
_TRAILING_SPACES_RE: re.Pattern[str] = re.compile(r' +$', re.MULTILINE)

# Compiled prompt patterns for CommandHistoryManager (avoids re-compilation per instance)
_PROMPT_PATTERNS: list[re.Pattern[str]] = [
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

# Compiled URL extraction patterns for UrlExtractorManager.
# OSC 8 hyperlinks embedded by modern terminals: ESC]8;;URL BEL display_text ESC]8;; BEL
_OSC8_URL_PATTERN: re.Pattern[str] = re.compile(
	r'\x1b\]8;'           # OSC 8 start
	r'[^;]*;'             # optional params (id=xxx, etc.)
	r'([^\x07\x1b]+)'     # capture the URL
	r'(?:\x07|\x1b\\)'    # BEL or ST terminator
)

# Plain-text URL pattern applied after ANSI stripping.
_URL_PATTERN: re.Pattern[str] = re.compile(
	r'(?:'
	# Standard http/https/ftp URLs
	r'(?:https?|ftp)://[^\s<>\[\]()\"\'`{}|\\^]+'
	r'|'
	# www. prefixed URLs (common in terminal output)
	r'www\.[^\s<>\[\]()\"\'`{}|\\^]+'
	r'|'
	# file:// protocol
	r'file://[^\s<>\[\]()\"\'`{}|\\^]+'
	r')',
	re.IGNORECASE
)


def _clean_url(url: str) -> str:
	"""Strip trailing punctuation that is likely not part of the URL."""
	# Strip trailing periods, commas, semicolons that are almost never URL-final
	while url and url[-1] in '.,;:!?':
		url = url[:-1]
	# Strip unbalanced trailing bracket/paren characters
	pairs = {'(': ')', '[': ']', '<': '>'}
	for open_char, close_char in pairs.items():
		while url.endswith(close_char) and url.count(close_char) > url.count(open_char):
			url = url[:-1]
	return url


def _read_terminal_text_on_main(terminal_obj, position=None, timeout: float = 2.0):
	"""Read terminal text on the main thread via ``wx.CallAfter``.

	UIA/COM objects are apartment-threaded and must be called from the thread
	that created them.  Background threads (polling, rectangular copy) that
	need terminal text should use this helper instead of calling
	``makeTextInfo()`` directly.

	Args:
		terminal_obj: NVDA terminal NVDAObject with ``makeTextInfo()``.
		position: ``textInfos.POSITION_*`` constant (default: ``POSITION_ALL``).
		timeout: Maximum seconds to wait for the main thread to respond.

	Returns:
		The text string, or ``None`` on failure / timeout.
	"""
	if position is None:
		position = textInfos.POSITION_ALL
	result: list[str | None] = [None]
	done = threading.Event()

	def _do_read():
		try:
			info = terminal_obj.makeTextInfo(position)
			result[0] = info.text
		except Exception:
			result[0] = None
		done.set()

	try:
		wx.CallAfter(_do_read)
	except Exception:
		return None
	done.wait(timeout)
	return result[0]


def _read_lines_on_main(terminal_obj, start_row: int, end_row: int, timeout: float = 5.0):
	"""Read a range of terminal lines on the main thread.

	Used by ``_performRectangularCopy`` to bulk-read all needed lines in one
	marshaled call, then column-slice them in the background thread.

	Args:
		terminal_obj: NVDA terminal NVDAObject.
		start_row: First row to read (1-based).
		end_row: Last row to read (1-based, inclusive).
		timeout: Maximum seconds to wait.

	Returns:
		List of line strings, or ``None`` on failure / timeout.
	"""
	result: list[list[str] | None] = [None]
	done = threading.Event()

	def _do_read():
		try:
			lines: list[str] = []
			info = terminal_obj.makeTextInfo(textInfos.POSITION_FIRST)
			info.move(textInfos.UNIT_LINE, start_row - 1)
			for _ in range(end_row - start_row + 1):
				line_info = info.copy()
				line_info.expand(textInfos.UNIT_LINE)
				lines.append(line_info.text or "")
				if info.move(textInfos.UNIT_LINE, 1) == 0:
					break
			result[0] = lines
		except Exception:
			result[0] = None
		done.set()

	try:
		wx.CallAfter(_do_read)
	except Exception:
		return None
	done.wait(timeout)
	return result[0]


def _read_terminal_text(terminal_obj, position=None, timeout: float = 2.0):
	"""Read terminal text, preferring the helper process over main-thread marshaling.

	Tries the native helper process first (bypasses wx.CallAfter entirely).
	Falls back to ``_read_terminal_text_on_main()`` if the helper is unavailable.
	"""
	helper = _get_helper()
	if helper is not None and hasattr(terminal_obj, 'windowHandle'):
		try:
			text = helper.read_text(terminal_obj.windowHandle)
			if text is not None:
				return text
		except Exception:
			pass
	# Fallback: marshal to the main thread
	return _read_terminal_text_on_main(terminal_obj, position, timeout)


def _read_lines(terminal_obj, start_row: int, end_row: int, timeout: float = 5.0):
	"""Read a range of terminal lines, preferring the helper process.

	Tries the native helper process first (bypasses wx.CallAfter entirely).
	Falls back to ``_read_lines_on_main()`` if the helper is unavailable.
	"""
	helper = _get_helper()
	if helper is not None and hasattr(terminal_obj, 'windowHandle'):
		try:
			lines = helper.read_lines(terminal_obj.windowHandle, start_row, end_row)
			if lines is not None:
				return lines
		except Exception:
			pass
	# Fallback: marshal to the main thread
	return _read_lines_on_main(terminal_obj, start_row, end_row, timeout)


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

	CACHE_TIMEOUT_S: float = 1.0  # Seconds (avoids per-call ms conversion)
	MAX_CACHE_SIZE = 100  # Maximum number of cached positions

	def __init__(self) -> None:
		"""Initialize an empty position cache."""
		from collections import OrderedDict
		self._cache: OrderedDict[str, tuple[int, int, float]] = OrderedDict()
		self._lock: threading.Lock = threading.Lock()

	def get(self, bookmark: Any) -> tuple[int, int] | None:
		"""
		Retrieve cached position for a bookmark if valid.

		Uses LRU eviction: a cache hit moves the entry to the end so
		frequently accessed positions stay in the cache longer.

		Args:
			bookmark: TextInfo bookmark object

		Returns:
			tuple: (row, col) if cache hit and not expired, None otherwise
		"""
		with self._lock:
			key = str(bookmark)
			entry = self._cache.get(key)
			if entry is not None:
				row, col, timestamp = entry
				if (time.time() - timestamp) < self.CACHE_TIMEOUT_S:
					# LRU: move to end so this entry is evicted last
					self._cache.move_to_end(key)
					return (row, col)
				# Expired entry, remove it
				del self._cache[key]
		return None

	def set(self, bookmark: Any, row: int, col: int) -> None:
		"""
		Store position in cache with current timestamp.

		Uses LRU eviction: when the cache is full, the least-recently
		used entry is evicted instead of the oldest by insertion time.

		Args:
			bookmark: TextInfo bookmark object
			row: Row number
			col: Column number
		"""
		with self._lock:
			key = str(bookmark)
			# If already present, update and move to end (LRU refresh)
			if key in self._cache:
				self._cache.move_to_end(key)
			elif len(self._cache) >= self.MAX_CACHE_SIZE:
				# Evict the least-recently used entry (front of OrderedDict)
				self._cache.popitem(last=False)

			self._cache[key] = (row, col, time.time())

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


class TextDiffer:
	"""
	Lightweight text differ for detecting new terminal output.

	Stores a snapshot of the last-known terminal text and compares it
	against the current text to identify newly appended content.

	The common case—output being appended to the end—is handled in O(n)
	time, where n is the length of the new suffix.  For edits in the
	middle or full screen clears the differ reports a ``"changed"`` state
	without computing a detailed diff.

	This class is opt-in; callers must call :meth:`update` explicitly.
	No UIA/COM calls are made here.

	Example usage:
		>>> differ = TextDiffer()
		>>> differ.update("line1\\nline2\\n")
		('initial', '')
		>>> differ.update("line1\\nline2\\nline3\\n")
		('appended', 'line3\\n')
		>>> differ.update("completely different")
		('changed', '')

	Thread Safety:
		Not internally thread-safe; callers must synchronise if needed.
	"""

	# Possible diff result kinds
	KIND_INITIAL = "initial"    # First snapshot — no previous state
	KIND_UNCHANGED = "unchanged"  # Text identical to last snapshot
	KIND_APPENDED = "appended"  # New text was appended after old text
	KIND_CHANGED = "changed"    # Non-trivial change (edit, clear, etc.)
	KIND_LAST_LINE_UPDATED = "last_line_updated"  # Only the last line changed (progress bars, spinners)

	__slots__ = ('_last_text', '_last_len')

	def __init__(self) -> None:
		"""Initialise with no previous snapshot."""
		self._last_text: str | None = None
		self._last_len: int = 0

	@staticmethod
	def _normalize(text: str) -> str:
		"""Strip trailing spaces from each line for padding-agnostic comparison.

		conhost pads UNIT_LINE text to screen width (80/120 chars) with trailing
		spaces. When padding shifts between reads, the prefix comparison fails.
		Normalizing before comparison prevents false KIND_CHANGED results.
		"""
		return _TRAILING_SPACES_RE.sub('', text)

	def update(self, current_text: str) -> tuple[str, str]:
		"""
		Compare *current_text* to the stored snapshot and return a diff result.

		Uses length pre-checks to avoid expensive full-string comparisons
		on the common unchanged and append cases.

		Args:
			current_text: The full current terminal text.

		Returns:
			tuple: ``(kind, new_content)`` where *kind* is one of the
			``KIND_*`` constants and *new_content* is the appended portion
			(non-empty for :attr:`KIND_APPENDED` and :attr:`KIND_LAST_LINE_UPDATED`).
		"""
		current_text = self._normalize(current_text)
		old = self._last_text
		if old is None:
			self._last_text = current_text
			self._last_len = len(current_text)
			return (self.KIND_INITIAL, "")

		cur_len = len(current_text)

		# Fast identity check: same length → likely unchanged.
		if cur_len == self._last_len and current_text == old:
			return (self.KIND_UNCHANGED, "")

		# Fast append detection: new text is longer and starts with old text.
		old_len = self._last_len
		if cur_len > old_len and current_text[:old_len] == old:
			appended = current_text[old_len:]
			self._last_text = current_text
			self._last_len = cur_len
			return (self.KIND_APPENDED, appended)

		# Last-line overwrite detection: everything before the last newline is
		# identical, only the trailing content differs (progress bars, spinners).
		# Skip the expensive rpartition if the lengths differ dramatically.
		if abs(cur_len - old_len) <= 500:
			old_prefix, old_sep, _old_tail = old.rpartition('\n')
			new_prefix, new_sep, new_tail = current_text.rpartition('\n')
			if old_sep and new_sep and old_prefix == new_prefix:
				self._last_text = current_text
				self._last_len = cur_len
				return (self.KIND_LAST_LINE_UPDATED, new_tail)

		# Non-trivial change.
		self._last_text = current_text
		self._last_len = cur_len
		return (self.KIND_CHANGED, "")

	def reset(self) -> None:
		"""Discard the stored snapshot so the next :meth:`update` is treated as initial."""
		self._last_text = None
		self._last_len = 0

	@property
	def last_text(self) -> str | None:
		"""The last snapshot text, or ``None`` if no snapshot has been taken."""
		return self._last_text


# ═══════════════════════════════════════════════════════════════
#  Native-or-fallback factory helpers
# ═══════════════════════════════════════════════════════════════

def _make_text_differ() -> TextDiffer:
	"""Create a TextDiffer, using the native Rust implementation if available."""
	if _native_available:
		try:
			return _NativeTextDiffer()
		except Exception:
			pass
	return TextDiffer()


def _make_position_cache() -> PositionCache:
	"""Create a PositionCache, using the native Rust implementation if available."""
	if _native_available:
		try:
			return _NativePositionCache()
		except Exception:
			pass
	return PositionCache()


def _strip_ansi(text: str) -> str:
	"""Strip ANSI escape sequences, using the native Rust implementation if available."""
	if _native_available:
		try:
			return _native_strip_ansi(text)
		except Exception:
			pass
	# Fallback to Python regex (ANSIParser._STRIP_PATTERN is defined below)
	return ANSIParser.stripANSI(text)


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
		self.foreground: str | tuple[int, int, int] | None = None
		self.background: str | tuple[int, int, int] | None = None
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

		Args:
			char: Single character string

		Returns:
			int: Display width (0, 1, or 2 columns)
		"""
		try:
			from native.termaccess_bridge import native_char_width, native_available
			if native_available():
				return native_char_width(char)
		except Exception:
			pass
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
			from native.termaccess_bridge import native_text_width, native_available
			if native_available():
				return native_text_width(text)
		except Exception:
			pass
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
		try:
			from native.termaccess_bridge import native_extract_column_range, native_available
			if native_available():
				return native_extract_column_range(text, startCol, endCol)
		except Exception:
			pass

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
		try:
			from native.termaccess_bridge import native_find_column_position, native_available
			if native_available():
				return native_find_column_position(text, targetCol)
		except Exception:
			pass

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

	__slots__ = ('name', 'top', 'bottom', 'left', 'right', 'mode', 'enabled')

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

	def toDict(self) -> dict[str, Any]:
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
	def fromDict(cls, data: dict[str, Any]) -> 'WindowDefinition':
		"""Create window definition from dictionary with validation."""
		return cls(
			name=_validateString(data.get('name', ''), 64, '', 'windowName'),
			top=_validateInteger(data.get('top', 0), 0, MAX_WINDOW_DIMENSION, 0, 'windowTop'),
			bottom=_validateInteger(data.get('bottom', 0), 0, MAX_WINDOW_DIMENSION, 0, 'windowBottom'),
			left=_validateInteger(data.get('left', 0), 0, MAX_WINDOW_DIMENSION, 0, 'windowLeft'),
			right=_validateInteger(data.get('right', 0), 0, MAX_WINDOW_DIMENSION, 0, 'windowRight'),
			mode=data.get('mode', 'announce') if data.get('mode') in ('announce', 'monitor', 'silent') else 'announce',
			enabled=bool(data.get('enabled', True)),
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

	def __init__(self, appName: str, displayName: str | None = None) -> None:
		"""
		Initialize an application profile.

		Args:
			appName: Application identifier (e.g., "vim", "tmux", "htop")
			displayName: Human-readable name (e.g., "Vim/Neovim")
		"""
		self.appName: str = appName
		self.displayName: str = displayName or appName

		# Settings overrides (None = use global setting)
		self.punctuationLevel: int | None = None
		self.cursorTrackingMode: int | None = None
		self.keyEcho: bool | None = None
		self.linePause: bool | None = None
		self.processSymbols: bool | None = None
		self.repeatedSymbols: bool | None = None
		self.repeatedSymbolsValues: str | None = None
		self.cursorDelay: int | None = None
		self.quietMode: bool | None = None
		self.announceIndentation: bool | None = None
		self.indentationOnLineRead: bool | None = None

		# Window definitions (list of WindowDefinition objects)
		self.windows: list[WindowDefinition] = []

		# Custom gestures (dict of gesture -> function name)
		self.customGestures: dict[str, str] = {}

	def addWindow(self, name: str, top: int, bottom: int, left: int, right: int,
				  mode: str = 'announce') -> WindowDefinition:
		"""Add a window definition to this profile."""
		window = WindowDefinition(name, top, bottom, left, right, mode)
		self.windows.append(window)
		return window

	def getWindowAtPosition(self, row: int, col: int) -> WindowDefinition | None:
		"""Get the window containing the specified position."""
		for window in self.windows:
			if window.contains(row, col):
				return window
		return None

	def toDict(self) -> dict[str, Any]:
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
	def fromDict(cls, data: dict[str, Any]) -> 'ApplicationProfile':
		"""Create profile from dictionary with field validation."""
		profile = cls(
			_validateString(data.get('appName', ''), 64, '', 'appName'),
			_validateString(data.get('displayName', ''), 128, None, 'displayName'),
		)

		# Validate integer fields with known ranges (None = use global)
		raw = data.get('punctuationLevel')
		profile.punctuationLevel = _validateInteger(raw, 0, 3, 2, 'punctuationLevel') if raw is not None else None
		raw = data.get('cursorTrackingMode')
		profile.cursorTrackingMode = _validateInteger(raw, 0, 3, 1, 'cursorTrackingMode') if raw is not None else None
		raw = data.get('linePause')
		profile.linePause = _validateInteger(raw, 0, 1000, 20, 'linePause') if raw is not None else None
		raw = data.get('cursorDelay')
		profile.cursorDelay = _validateInteger(raw, 50, 2000, 200, 'cursorDelay') if raw is not None else None

		# Validate boolean fields (None = use global)
		for field in ('keyEcho', 'processSymbols', 'repeatedSymbols', 'quietMode',
		              'announceIndentation', 'indentationOnLineRead'):
			val = data.get(field)
			setattr(profile, field, bool(val) if val is not None else None)

		raw = data.get('repeatedSymbolsValues')
		profile.repeatedSymbolsValues = _validateString(raw, MAX_REPEATED_SYMBOLS_LENGTH, '-_=!', 'repeatedSymbolsValues') if raw is not None else None

		# Restore windows
		windows_data = data.get('windows', [])
		if isinstance(windows_data, list):
			for winData in windows_data:
				if isinstance(winData, dict):
					profile.windows.append(WindowDefinition.fromDict(winData))

		# Validate customGestures: only allow known gesture pattern → script name
		raw_gestures = data.get('customGestures', {})
		if isinstance(raw_gestures, dict):
			safe_gestures = {}
			for gesture, script_name in raw_gestures.items():
				# Gesture keys must be "kb:..." strings; script names must be alphanumeric
				if (isinstance(gesture, str) and isinstance(script_name, str)
						and gesture.startswith('kb:') and script_name.isidentifier()):
					safe_gestures[gesture] = script_name
			profile.customGestures = safe_gestures
		else:
			profile.customGestures = {}

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
		self.profiles: dict[str, ApplicationProfile] = {}
		self.activeProfile: ApplicationProfile | None = None
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

		# Section 5.3: Modern GPU-accelerated terminal profiles (v1.0.49+)
		ghostty = ApplicationProfile('ghostty', 'Ghostty')
		ghostty.punctuationLevel = PUNCT_SOME
		ghostty.cursorTrackingMode = CT_STANDARD
		self.profiles['ghostty'] = ghostty

		rio = ApplicationProfile('rio', 'Rio')
		rio.punctuationLevel = PUNCT_SOME
		rio.cursorTrackingMode = CT_STANDARD
		self.profiles['rio'] = rio

		wave = ApplicationProfile('waveterm', 'Wave Terminal')
		wave.punctuationLevel = PUNCT_SOME
		wave.cursorTrackingMode = CT_STANDARD
		self.profiles['waveterm'] = wave

		contour = ApplicationProfile('contour', 'Contour Terminal')
		contour.punctuationLevel = PUNCT_SOME
		contour.cursorTrackingMode = CT_STANDARD
		self.profiles['contour'] = contour

		coolretro = ApplicationProfile('cool-retro-term', 'Cool Retro Term')
		coolretro.punctuationLevel = PUNCT_SOME
		coolretro.cursorTrackingMode = CT_STANDARD
		self.profiles['cool-retro-term'] = coolretro

		# Section 5.4: Remote access / professional terminal profiles (v1.0.49+)
		mobaxterm = ApplicationProfile('mobaxterm', 'MobaXterm')
		mobaxterm.punctuationLevel = PUNCT_SOME
		mobaxterm.cursorTrackingMode = CT_STANDARD
		self.profiles['mobaxterm'] = mobaxterm

		securecrt = ApplicationProfile('securecrt', 'SecureCRT')
		securecrt.punctuationLevel = PUNCT_SOME
		securecrt.cursorTrackingMode = CT_STANDARD
		self.profiles['securecrt'] = securecrt

		ttermpro = ApplicationProfile('ttermpro', 'Tera Term')
		ttermpro.punctuationLevel = PUNCT_SOME
		ttermpro.cursorTrackingMode = CT_STANDARD
		self.profiles['ttermpro'] = ttermpro

		mremoteng = ApplicationProfile('mremoteng', 'mRemoteNG')
		mremoteng.punctuationLevel = PUNCT_SOME
		mremoteng.cursorTrackingMode = CT_STANDARD
		self.profiles['mremoteng'] = mremoteng

		royalts = ApplicationProfile('royalts', 'Royal TS')
		royalts.punctuationLevel = PUNCT_SOME
		royalts.cursorTrackingMode = CT_STANDARD
		self.profiles['royalts'] = royalts

		# Section 5.5: TUI Application profiles (v1.0.49+)

		# Claude CLI profile
		claude = ApplicationProfile('claude', 'Claude CLI')
		claude.punctuationLevel = PUNCT_MOST  # Code-heavy output needs punctuation
		claude.repeatedSymbols = False  # Markdown-style separators in output
		claude.linePause = False  # Fast reading for streaming responses
		claude.keyEcho = False  # Don't echo typing during input
		# Silence bottom status bar region
		claude.addWindow('conversation', 1, 9997, 1, 9999, mode='announce')
		claude.addWindow('statusbar', 9998, 9999, 1, 9999, mode='silent')
		self.profiles['claude'] = claude

		# lazygit profile
		lazygit = ApplicationProfile('lazygit', 'lazygit')
		lazygit.punctuationLevel = PUNCT_MOST  # Git diff symbols
		lazygit.repeatedSymbols = False  # Many repeated chars in borders/diffs
		lazygit.keyEcho = False  # Single-key shortcuts
		lazygit.cursorTrackingMode = CT_WINDOW
		# Panel layout: announce all content
		lazygit.addWindow('main', 1, 9999, 1, 9999, mode='announce')
		self.profiles['lazygit'] = lazygit

		# btop/btm profile (system monitor)
		btop = ApplicationProfile('btop', 'btop/btm (System Monitor)')
		btop.repeatedSymbols = False  # Progress bars, box-drawing
		btop.keyEcho = False  # Single-key navigation
		btop.linePause = False  # Fast refresh rates
		# Header with CPU/memory meters
		btop.addWindow('header', 1, 6, 1, 9999, mode='announce')
		btop.addWindow('processes', 7, 9999, 1, 9999, mode='announce')
		self.profiles['btop'] = btop
		self.profiles['btm'] = btop  # bottom uses same profile

		# yazi profile (file manager)
		yazi = ApplicationProfile('yazi', 'yazi (File Manager)')
		yazi.punctuationLevel = PUNCT_SOME
		yazi.keyEcho = False  # Single-key shortcuts
		yazi.repeatedSymbols = False  # File listing separators
		yazi.cursorTrackingMode = CT_STANDARD
		self.profiles['yazi'] = yazi

		# k9s profile (Kubernetes TUI)
		k9s = ApplicationProfile('k9s', 'k9s (Kubernetes)')
		k9s.punctuationLevel = PUNCT_MOST  # Namespace/pod names with symbols
		k9s.repeatedSymbols = False  # Table borders
		k9s.keyEcho = False  # Single-key navigation
		k9s.linePause = False  # Fast status updates
		self.profiles['k9s'] = k9s

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
				# Note: more specific matches (lazygit) must come before
				# less specific ones (git) to avoid false positives.
				if 'vim' in title or 'nvim' in title:
					return 'vim'
				elif 'tmux' in title:
					return 'tmux'
				elif 'btop' in title or 'btm' in title:
					return 'btop'
				elif 'htop' in title:
					return 'htop'
				elif 'less' in title or 'more' in title:
					return 'less'
				elif 'lazygit' in title:
					return 'lazygit'
				elif 'git' in title:
					return 'git'
				elif 'nano' in title:
					return 'nano'
				elif 'irssi' in title:
					return 'irssi'
				# TUI applications (detected by window title)
				elif 'claude' in title:
					return 'claude'
				elif 'yazi' in title:
					return 'yazi'
				elif 'k9s' in title:
					return 'k9s'

		except Exception:
			pass

		return 'default'

	def getProfile(self, appName: str) -> ApplicationProfile | None:
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
		if appName in self.profiles and appName not in _BUILTIN_PROFILE_NAMES:
			del self.profiles[appName]

	def exportProfile(self, appName: str) -> dict[str, Any] | None:
		"""Export profile to dictionary."""
		profile = self.profiles.get(appName)
		if profile:
			return profile.toDict()
		return None

	def importProfile(self, data: dict[str, Any]) -> ApplicationProfile:
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
					 "quietMode", "verboseMode", "windowEnabled",
					 "announceNewOutput", "stripAnsiInOutput"]:
			return bool(value)

		# New output coalesce window (ms)
		elif key == "newOutputCoalesceMs":
			return _validateInteger(value, 50, 2000, 200, key)
		elif key == "newOutputMaxLines":
			return _validateInteger(value, 1, 200, 20, key)

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
		config.conf["terminalAccess"]["announceNewOutput"] = False
		config.conf["terminalAccess"]["newOutputCoalesceMs"] = 200
		config.conf["terminalAccess"]["newOutputMaxLines"] = 20
		config.conf["terminalAccess"]["stripAnsiInOutput"] = True


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

	def get_window_bounds(self) -> dict[str, int]:
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
		self._cache = _make_position_cache()
		self._last_known_position: tuple[Any, int, int] | None = None

	def calculate(self, textInfo: Any, terminal: Any) -> tuple[int, int]:
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
									 bookmark: Any) -> tuple[int, int] | None:
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
							   comparison: int) -> tuple[int, int] | None:
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
				charRange.setEndPoint(targetCopy, "endToEnd")
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
				charRange.setEndPoint(targetCopy, "endToEnd")
				charsFromLineStart = len(charRange.text) if charRange.text else 0
				newCol = charsFromLineStart + 1

				return (newRow, newCol)

		except Exception:
			return None

	@staticmethod
	def _needs_scrollback_compensation(terminal) -> bool:
		"""Return True if the terminal needs scrollback compensation.

		Windows Terminal's POSITION_FIRST is already viewport-relative, so
		no compensation is needed.  conhost includes scrollback, so we need
		to estimate the viewport offset.
		"""
		try:
			appName = terminal.appModule.appName.lower()
		except (AttributeError, TypeError):
			return False
		# Windows Terminal is already viewport-relative
		if "windowsterminal" in appName:
			return False
		# conhost, cmd, powershell, etc. may include scrollback
		return any(t in appName for t in ("cmd", "powershell", "pwsh", "conhost"))

	@staticmethod
	def _to_viewport_row(buffer_row: int, total_lines: int, terminal) -> int:
		"""Convert buffer-absolute row to viewport-relative row on conhost.

		conhost's POSITION_FIRST includes scrollback, so buffer_row may be
		inflated by thousands.  We estimate the viewport height from the
		terminal window's pixel dimensions and subtract the scrollback offset.

		Args:
			buffer_row: Row number counted from POSITION_FIRST (1-based).
			total_lines: Total line count in the buffer.
			terminal: NVDA terminal NVDAObject.

		Returns:
			Viewport-relative row (1-based), or *buffer_row* unchanged on failure.
		"""
		try:
			loc = getattr(terminal, 'location', None)
			if loc is None:
				return buffer_row
			pixel_height = loc[3] if len(loc) >= 4 else getattr(loc, 'height', 0)
			if pixel_height <= 0:
				return buffer_row
			# ~18px per character cell is a reasonable estimate for common DPI / font combos
			viewport_rows = max(1, pixel_height // 18)
			scrollback = max(0, total_lines - viewport_rows)
			return max(1, buffer_row - scrollback)
		except Exception:
			return buffer_row

	def _calculate_full(self, textInfo: Any, terminal: Any,
					   bookmark: Any) -> tuple[int, int]:
		"""
		Perform full O(n) position calculation from buffer start.

		Args:
			textInfo: TextInfo to calculate position for
			terminal: Terminal object
			bookmark: TextInfo bookmark

		Returns:
			(row, col) tuple
		"""
		# Start from beginning of buffer and count lines forward to the target
		startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
		startInfo.collapse()

		# Calculate row by counting lines
		targetCopy = textInfo.copy()
		targetCopy.collapse()

		# Count how many lines from buffer start until target
		lineCount = 0
		while startInfo.compareEndPoints(targetCopy, "startToStart") < 0:
			moved = startInfo.move(textInfos.UNIT_LINE, 1)
			if moved == 0:
				break
			lineCount += 1

		buffer_row = lineCount + 1

		# Compensate for scrollback on conhost.  Only do the expensive
		# POSITION_ALL read when the terminal actually needs it — Windows
		# Terminal is already viewport-relative, so we skip the extra UIA call.
		if self._needs_scrollback_compensation(terminal):
			total_lines = 1
			try:
				all_info = terminal.makeTextInfo(textInfos.POSITION_ALL)
				all_text = all_info.text
				if all_text:
					total_lines = all_text.count('\n') + 1
			except Exception:
				pass
			row = self._to_viewport_row(buffer_row, total_lines, terminal)
		else:
			row = buffer_row

		# Calculate column by counting characters from line start
		lineStart = targetCopy.copy()
		lineStart.expand(textInfos.UNIT_LINE)
		lineStart.collapse()

		# Create range from line start to target and count characters
		charRange = lineStart.copy()
		charRange.setEndPoint(targetCopy, "endToEnd")
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
		self._dialog: Any | None = None
		self._cancelled: bool = False
		self._lock: threading.Lock = threading.Lock()
		self._ready: threading.Event = threading.Event()
		# Create dialog on main thread
		wx.CallAfter(self._create, parent, title, maximum)
		# Wait for the main thread to actually create the dialog (up to 2s).
		# This replaces a fixed sleep(0.1) which could lose the race.
		self._ready.wait(timeout=2.0)

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
		finally:
			self._ready.set()

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
			dialog = self._dialog
			self._dialog = None
		if dialog:
			wx.CallAfter(self._destroy, dialog)

	def _destroy(self, dialog) -> None:
		"""
		Destroy the dialog (called on main thread).

		Receives the dialog reference explicitly so it is not lost
		when ``close()`` clears ``self._dialog`` before this runs.
		"""
		try:
			dialog.Destroy()
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
		self._active_operation: threading.Thread | None = None
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


class NewOutputAnnouncer:
	"""
	Announces newly appended terminal output using TextDiffer.

	When the "announce new output" feature is enabled, this class monitors
	terminal content and speaks newly appended lines as they arrive.

	The announcer uses two mechanisms to detect new output:
	1. Event-driven: Content fed via :meth:`feed` (called from event_caret)
	2. Polling: Background thread that polls terminal buffer at regular intervals

	The polling mechanism ensures reliable detection even when terminals don't
	fire caret events for program output. Rapid bursts are coalesced by a short
	timer so that fast-scrolling output (``cat`` of a large file, ``apt``
	progress bars, etc.) does not overwhelm the speech synthesiser.

	Features:
	- Background polling: actively checks for new output every 300ms
	- Event-driven updates: also processes event_caret notifications
	- Coalescing: accumulates text within a configurable window (newOutputCoalesceMs)
	- Max-lines guard: if more than newOutputMaxLines arrive at once, a summary
	  "{N} new lines" is spoken instead of the full text
	- ANSI stripping: controlled by stripAnsiInOutput config key
	- Quiet-mode awareness: no output when quietMode is active

	Thread Safety:
		:meth:`feed` and polling may be called from multiple threads.
		Internal state is protected by a ``threading.Lock``.
	"""

	# Polling interval in seconds (300ms)
	POLL_INTERVAL = 0.3
	# Minimum interval between consecutive feed() calls (50ms).
	# Prevents duplicate buffer reads when event_caret and polling overlap.
	_MIN_FEED_INTERVAL: float = 0.05

	def __init__(self) -> None:
		"""Initialise with no previous snapshot."""
		self._differ = _make_text_differ()
		self._lock = threading.Lock()
		self._timer: threading.Timer | None = None
		self._pending_text: str = ""
		self._poll_thread: threading.Thread | None = None
		self._stop_polling = threading.Event()
		self._terminal_obj = None
		self._last_feed_time: float = 0.0
		# Deadline-based coalescing: avoids cancel+recreate of threading.Timer
		# on every content update.  The running timer checks the deadline when
		# it fires and reschedules itself if the deadline was pushed forward.
		self._coalesce_deadline: float = 0.0

	def should_read(self) -> bool:
		"""Check if a feed is worthwhile before the caller does an expensive read.

		Returns True only when the feature is enabled, quiet mode is off,
		and the throttle interval has elapsed.  Callers should gate the
		expensive ``makeTextInfo(POSITION_ALL)`` behind this check.
		"""
		if (time.time() - self._last_feed_time) < self._MIN_FEED_INTERVAL:
			return False
		try:
			ta_conf = config.conf["terminalAccess"]
			if ta_conf["quietMode"] or not ta_conf["announceNewOutput"]:
				return False
		except Exception:
			return False
		return True

	def feed(self, text: str) -> None:
		"""
		Feed the current terminal text and queue an announcement if new output
		was appended.

		Args:
			text: The full current terminal buffer text.
		"""
		# Throttle: skip if the last feed was very recent (duplicate event_caret / poll overlap)
		now = time.time()
		if (now - self._last_feed_time) < self._MIN_FEED_INTERVAL:
			return
		self._last_feed_time = now

		# Respect quiet mode and master toggle — single config lookup
		try:
			ta_conf = config.conf["terminalAccess"]
			if ta_conf["quietMode"] or not ta_conf["announceNewOutput"]:
				return
		except Exception:
			return

		kind, new_content = self._differ.update(text)

		if kind == TextDiffer.KIND_LAST_LINE_UPDATED:
			# Last-line overwrite (progress bars, spinners): REPLACE pending
			# text because the old partial content is now stale.
			stripped = new_content.strip()
			if not stripped:
				return
			try:
				if ta_conf["stripAnsiInOutput"]:
					new_content = _strip_ansi(new_content)
					if not new_content.strip():
						return
			except Exception:
				pass
			self._schedule_coalesce(new_content, replace=True, ta_conf=ta_conf)
			return

		if kind != TextDiffer.KIND_APPENDED:
			return
		stripped = new_content.strip()
		if not stripped:
			return

		# Strip ANSI escape codes if configured
		try:
			if ta_conf["stripAnsiInOutput"]:
				new_content = _strip_ansi(new_content)
				if not new_content.strip():
					return
		except Exception:
			pass

		self._schedule_coalesce(new_content, replace=False, ta_conf=ta_conf)

	def feed_diff(self, kind: int, content: str) -> None:
		"""Feed a pre-computed diff result from the helper process.

		Unlike :meth:`feed`, this bypasses the local TextDiffer since the
		helper already performed ANSI stripping and diff detection. This
		avoids duplicate work and removes the need to transfer the full
		terminal buffer over the pipe.

		Args:
			kind: Diff kind from the helper (2=Appended, 3=Changed,
				4=LastLineUpdated).
			content: The diff content (appended lines or updated last line).
		"""
		# Throttle: skip if the last feed was very recent
		now = time.time()
		if (now - self._last_feed_time) < self._MIN_FEED_INTERVAL:
			return
		self._last_feed_time = now

		# Respect quiet mode and master toggle
		try:
			ta_conf = config.conf["terminalAccess"]
			if ta_conf["quietMode"] or not ta_conf["announceNewOutput"]:
				return
		except Exception:
			return

		stripped = content.strip()
		if not stripped:
			return

		# The helper already strips ANSI, but if the user has stripAnsiInOutput
		# enabled and somehow ANSI slipped through, strip again as safety net.
		try:
			if ta_conf["stripAnsiInOutput"]:
				content = _strip_ansi(content)
				if not content.strip():
					return
		except Exception:
			pass

		if kind == self._DIFF_KIND_LAST_LINE_UPDATED:
			self._schedule_coalesce(content, replace=True, ta_conf=ta_conf)
		elif kind == self._DIFF_KIND_APPENDED:
			self._schedule_coalesce(content, replace=False, ta_conf=ta_conf)
		# kind == _DIFF_KIND_CHANGED: content is empty (full screen change),
		# nothing to announce.

	def _schedule_coalesce(self, content: str, *, replace: bool, ta_conf) -> None:
		"""
		Accumulate (or replace) pending text and ensure a coalesce timer is running.

		Uses a deadline approach: existing timers are NOT cancelled.  When the
		timer fires it checks whether the deadline was pushed forward and, if
		so, reschedules itself with the remaining time.  This avoids creating a
		new ``threading.Timer`` (and its thread) on every content update.
		"""
		try:
			coalesce_ms = int(ta_conf["newOutputCoalesceMs"])
		except Exception:
			coalesce_ms = 200
		coalesce_s = coalesce_ms / 1000.0

		with self._lock:
			if replace:
				self._pending_text = content
			else:
				self._pending_text += content
			self._coalesce_deadline = time.time() + coalesce_s
			# Only create a new timer if none is currently alive.
			if self._timer is None or not self._timer.is_alive():
				self._timer = threading.Timer(coalesce_s, self._announce_pending)
				self._timer.daemon = True
				self._timer.start()

	def _announce_pending(self) -> None:
		"""Announce the accumulated pending text (called from timer thread)."""
		with self._lock:
			remaining = self._coalesce_deadline - time.time()
			if remaining > 0.005:
				# Deadline was pushed forward — reschedule instead of announcing.
				self._timer = threading.Timer(remaining, self._announce_pending)
				self._timer.daemon = True
				self._timer.start()
				return
			text = self._pending_text
			self._pending_text = ""
			self._timer = None

		if not text.strip():
			return

		# Re-check quiet mode and feature toggle (might have changed while timer was running)
		try:
			ta_conf = config.conf["terminalAccess"]
			if ta_conf["quietMode"] or not ta_conf["announceNewOutput"]:
				return
		except Exception:
			return

		lines = [ln for ln in text.split('\n') if ln.strip()]
		try:
			max_lines = int(ta_conf["newOutputMaxLines"])
		except Exception:
			max_lines = 20

		if len(lines) > max_lines:
			# Translators: Summary when many new lines arrive at once
			ui.message(_("{n} new lines").format(n=len(lines)))
		else:
			ui.message(text.strip())

	def reset(self) -> None:
		"""Reset internal state (call when toggling the feature on/off)."""
		with self._lock:
			if self._timer is not None:
				self._timer.cancel()
				self._timer = None
			self._pending_text = ""
		self._differ.reset()

	def set_terminal(self, terminal_obj) -> None:
		"""
		Set the terminal object for polling.

		Args:
			terminal_obj: The focused terminal object to poll for content.
		"""
		self._terminal_obj = terminal_obj

	def start_polling(self) -> None:
		"""
		Start monitoring for new output.

		Prefers push-based subscription via the helper process (50ms latency).
		Falls back to a background polling thread (300ms) if the helper is
		unavailable or subscription fails.
		"""
		if self._poll_thread is not None or getattr(self, "_subscribed_hwnd", None) is not None:
			return  # Already monitoring

		# Try subscription via helper process first
		helper = _get_helper()
		if helper is not None and self._terminal_obj is not None:
			hwnd = getattr(self._terminal_obj, "windowHandle", None)
			if hwnd is not None:
				try:
					if helper.subscribe(hwnd):
						self._subscribed_hwnd = hwnd
						helper.on("text_diff", self._on_text_diff)
						helper.on("helper_crashed", self._on_helper_crashed)
						log.debug("Subscribed to hwnd %d via helper (diff mode)", hwnd)
						return
				except Exception:
					log.debug("Subscription failed, falling back to polling", exc_info=True)

		# Fallback: polling
		self._stop_polling.clear()
		self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
		self._poll_thread.start()

	def stop_polling(self) -> None:
		"""
		Stop monitoring for new output.

		Handles both subscription mode and polling mode.
		"""
		# Unsubscribe if in subscription mode
		hwnd = getattr(self, "_subscribed_hwnd", None)
		if hwnd is not None:
			helper = _get_helper()
			if helper is not None:
				try:
					helper.unsubscribe(hwnd)
					helper.off("text_diff", self._on_text_diff)
					helper.off("helper_crashed", self._on_helper_crashed)
				except Exception:
					pass
			self._subscribed_hwnd = None

		# Stop polling if in polling mode
		if self._poll_thread is None:
			return

		self._stop_polling.set()
		if self._poll_thread.is_alive():
			self._poll_thread.join(timeout=1.0)
		self._poll_thread = None

	# Mapping from Rust DiffKind numeric values to Python-side processing.
	# 0 = Initial, 1 = Unchanged, 2 = Appended, 3 = Changed, 4 = LastLineUpdated
	_DIFF_KIND_APPENDED = 2
	_DIFF_KIND_CHANGED = 3
	_DIFF_KIND_LAST_LINE_UPDATED = 4

	def _on_text_diff(self, hwnd: int, kind: int, content: str) -> None:
		"""Callback for helper process text_diff notifications.

		Receives pre-diffed content from the helper, bypassing the local
		TextDiffer. The helper already strips ANSI and computes diffs.

		Args:
			hwnd: Window handle of the terminal.
			kind: Diff kind (2=Appended, 3=Changed, 4=LastLineUpdated).
			content: The diff content (appended text or updated last line).
		"""
		subscribed = getattr(self, "_subscribed_hwnd", None)
		if subscribed is not None and hwnd == subscribed and content:
			self.feed_diff(kind, content)

	def _on_helper_crashed(self, msg) -> None:
		"""Callback when the helper process gives up restarting.

		Falls back to polling mode so output detection continues even
		after the helper dies permanently.
		"""
		if getattr(self, "_subscribed_hwnd", None) is None:
			return  # Not in subscription mode

		log.warning("Helper crashed permanently, falling back to polling")
		self._subscribed_hwnd = None

		# Start polling thread as fallback
		if self._poll_thread is None:
			self._stop_polling.clear()
			self._poll_thread = threading.Thread(
				target=self._poll_loop, daemon=True
			)
			self._poll_thread.start()

	def _poll_loop(self) -> None:
		"""
		Background polling loop that checks for new terminal output.

		Runs in a separate thread and polls the terminal buffer at regular
		intervals (POLL_INTERVAL). Uses the same feed() method as event-driven
		updates, so all detection and coalescing logic is shared.
		"""
		while not self._stop_polling.wait(self.POLL_INTERVAL):
			try:
				# Check if feature is still enabled
				if not config.conf["terminalAccess"]["announceNewOutput"]:
					continue

				# Get terminal content and feed to announcer.
				# Uses helper process if available; falls back to main-thread marshaling.
				if self._terminal_obj is not None:
					try:
						text = _read_terminal_text(self._terminal_obj)
						if text is not None:
							self.feed(text)
					except Exception:
						# Terminal object may be invalid, ignore
						pass
			except Exception:
				# Config access or other errors - continue polling
				pass


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
				'enabled': True,
				'differ': _make_text_differ(),  # Per-monitor differ for change detection
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
			# Collect monitors that are due for a check while holding the
			# lock, then release it *before* any I/O.  _check_window calls
			# _read_terminal_text_on_main which blocks waiting for the main
			# thread — holding the lock during that call would deadlock if
			# the main thread tried to acquire it (e.g. stop_monitoring).
			due_monitors = []
			with self._lock:
				if not self._monitoring_active:
					break

				current_time = time.time() * 1000  # Convert to milliseconds

				for monitor in self._monitors:
					if not monitor['enabled']:
						continue
					time_since_check = current_time - monitor['last_check']
					if time_since_check >= monitor['interval']:
						due_monitors.append(monitor)

			# Perform I/O outside the lock to avoid deadlock.
			for monitor in due_monitors:
				current_time = time.time() * 1000
				self._check_window(monitor, current_time)
				monitor['last_check'] = current_time

			# Sleep briefly to avoid busy-waiting
			time.sleep(0.1)

	def _check_window(self, monitor: dict, current_time: float) -> None:
		"""
		Check if window content changed using TextDiffer.

		For appended output (the common case) only the new lines are announced.
		For non-trivial changes (screen clears, edits in the middle) the
		full region content is announced.

		Args:
			monitor: Monitor configuration dictionary
			current_time: Current timestamp in milliseconds
		"""
		try:
			# Extract window content
			content = self._extract_window_content(monitor['bounds'])
			name = monitor['name']

			# Use per-monitor TextDiffer for change detection
			differ: TextDiffer = monitor['differ']
			kind, new_content = differ.update(content)

			# Nothing to do for initial snapshot or unchanged content
			if kind in (TextDiffer.KIND_INITIAL, TextDiffer.KIND_UNCHANGED):
				return

			# Keep legacy _last_content dict in sync for external callers
			self._last_content[name] = content

			# Only announce in 'changes' mode and when rate-limit allows it
			if monitor['mode'] != 'changes':
				return

			time_since_announcement = current_time - self._last_announcement.get(name, 0)
			if time_since_announcement < self._min_announcement_interval:
				return

			if kind == TextDiffer.KIND_APPENDED:
				# Speak only the newly appended portion
				self._announce_change(name, new_content, content)
			else:
				# Non-trivial change (clear / mid-edit): speak the full region
				self._announce_change(name, content, None)
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
			# Uses helper process if available; falls back to main-thread marshaling.
			all_text = _read_terminal_text(self._terminal)
			if all_text is None:
				return ""

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

	def _announce_change(self, name: str, new_content: str, old_content) -> None:
		"""
		Announce content change to user.

		When called with the appended text as *new_content* and the full
		region as *old_content*, the appended text is spoken directly.
		When *old_content* is ``None`` (non-trivial change / full region), a
		brief summary is spoken instead.

		Args:
			name: Monitor name
			new_content: Appended text or full region content
			old_content: Previous window content, or None for non-trivial changes
		"""
		try:
			if old_content is None:
				# Non-trivial change (clear / edit): speak the region content
				text = new_content.strip()
				if text:
					ui.message(text)
			else:
				# Appended output: speak only the new portion
				text = new_content.strip()
				if text:
					ui.message(text)
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

		# Validate regex early so callers get a clear error instead of a
		# silent 0-match result buried inside the broad except below.
		if use_regex:
			try:
				flags = 0 if case_sensitive else re.IGNORECASE
				re.compile(pattern, flags)
			except re.error as exc:
				try:
					import logHandler
					logHandler.log.warning(f"Terminal Access: Invalid regex '{pattern}': {exc}")
				except Exception:
					pass
				raise ValueError(f"Invalid regular expression: {exc}") from exc

		# Use a local list so _store_match doesn't touch instance/per-tab
		# state until the search is complete.
		matches = []

		def _store_match(line_info, line_text, line_num, char_offset):
			"""
			Store a search match with a bookmark and fallback position.

			Fallback is needed when bookmarks aren't supported by the TextInfo implementation.
			char_offset is the character position within the line where the match starts.
			"""
			bookmark = getattr(line_info, "bookmark", None)
			try:
				fallback_pos = line_info.copy()
			except Exception:
				fallback_pos = line_info
			matches.append((bookmark, line_text, line_num, fallback_pos, char_offset))

		def _find_match_offset(line_text, pattern, case_sensitive, use_regex):
			"""Find the character offset of the first match in the line."""
			if use_regex:
				flags = 0 if case_sensitive else re.IGNORECASE
				match = re.search(pattern, line_text, flags)
				return match.start() if match else 0
			else:
				search_pattern = pattern if case_sensitive else pattern.lower()
				search_text = line_text if case_sensitive else line_text.lower()
				offset = search_text.find(search_pattern)
				return offset if offset >= 0 else 0

		try:
			# ─── Fast path: helper-side search (no buffer transfer) ───
			# When the helper is running, it reads the terminal buffer via
			# UIA and searches it in one IPC round-trip.  This avoids the
			# expensive makeTextInfo(POSITION_ALL) call entirely.
			helper_search_result = None
			try:
				helper = _get_helper()
			except Exception:
				helper = None

			if helper is not None and helper.is_running:
				hwnd = getattr(self._terminal, "windowHandle", None)
				if hwnd:
					try:
						resp = helper.search_text(
							hwnd, pattern, case_sensitive, use_regex,
						)
						if resp is not None:
							helper_search_result = resp
					except ValueError:
						raise
					except Exception:
						pass

			if helper_search_result is not None:
				# Helper returned matches — build matching_indices and
				# line_text/offset maps from the response.
				resp = helper_search_result
				matching_indices = [m["line_index"] for m in resp.get("matches", [])]
				native_offset_map = {
					m["line_index"]: m["char_offset"]
					for m in resp.get("matches", [])
				}
				helper_line_texts = {
					m["line_index"]: m["line_text"]
					for m in resp.get("matches", [])
				}
				total_lines = resp.get("total_lines", 0)
				lines = None  # Not available in helper path
			else:
				# ─── Standard path: read buffer + match locally ───
				info = self._terminal.makeTextInfo(textInfos.POSITION_ALL)
				all_text = info.text

				if not all_text:
					return 0

				# Strip ANSI escape sequences that some terminals leave
				# in the text buffer.
				all_text = _strip_ansi(all_text)

				# Split into lines and build matching indices.
				lines = all_text.split('\n')
				total_lines = len(lines)
				helper_line_texts = None

				# Try Rust-accelerated search first.
				native_offset_map = None
				if _native_available:
					try:
						native_matches = _native_search_text(
							all_text, pattern, case_sensitive, use_regex,
						)
						matching_indices = [m[0] for m in native_matches]
						native_offset_map = {m[0]: m[1] for m in native_matches}
					except ValueError:
						raise
					except Exception:
						native_offset_map = None

				if native_offset_map is None:
					# Python fallback: match line by line.
					if use_regex:
						flags = 0 if case_sensitive else re.IGNORECASE
						compiled = re.compile(pattern, flags)
						matching_indices = [i for i, line in enumerate(lines) if compiled.search(line)]
					else:
						search_pattern = pattern if case_sensitive else pattern.lower()
						matching_indices = [
							i for i, line in enumerate(lines)
							if search_pattern in (line if case_sensitive else line.lower())
						]

			if not matching_indices:
				return 0

			# ─── Bookmark walk ───
			# Single forward pass from POSITION_FIRST: walk line by line,
			# collecting bookmarks only for matching lines.
			def _get_line_text(line_index):
				"""Get line text from whichever source is available."""
				if helper_line_texts is not None and line_index in helper_line_texts:
					return helper_line_texts[line_index]
				if lines is not None and line_index < len(lines):
					return lines[line_index]
				return ""

			walk_end = total_lines - 1 if total_lines > 0 else 0
			try:
				cursor = self._terminal.makeTextInfo(textInfos.POSITION_FIRST)
				match_set = set(matching_indices)
				for line_index in range(walk_end + 1):
					if line_index in match_set:
						line_text = _get_line_text(line_index)
						if native_offset_map is not None and line_index in native_offset_map:
							char_offset = native_offset_map[line_index]
						else:
							char_offset = _find_match_offset(line_text, pattern, case_sensitive, use_regex)
						_store_match(cursor, line_text, line_index + 1, char_offset)
					if line_index < walk_end:
						moved = cursor.move(textInfos.UNIT_LINE, 1)
						if not moved:
							break
			except Exception:
				# Fall back to per-match walk if single-pass fails.
				matches.clear()
				for i in matching_indices:
					try:
						line_info = self._terminal.makeTextInfo(textInfos.POSITION_FIRST)
						line_info.move(textInfos.UNIT_LINE, i)
						line_text = _get_line_text(i)
						if native_offset_map is not None and i in native_offset_map:
							char_offset = native_offset_map[i]
						else:
							char_offset = _find_match_offset(line_text, pattern, case_sensitive, use_regex)
						_store_match(line_info, line_text, i + 1, char_offset)
					except Exception:
						pass

			# Save results through the tab-aware state mechanism so
			# multi-tab and legacy modes stay in sync.
			self._save_search_state({
				'pattern': pattern,
				'matches': matches,
				'current_match_index': -1,
				'case_sensitive': case_sensitive,
				'use_regex': use_regex
			})

			return len(matches)

		except Exception:
			return 0

	def next_match(self) -> bool:
		"""
		Jump to next match.

		Returns:
			bool: True if jumped to next match
		"""
		state = self._get_search_state()
		matches = state['matches']
		if not matches:
			return False

		# Move to next match (wrap around)
		state['current_match_index'] = (state['current_match_index'] + 1) % len(matches)
		self._save_search_state(state)
		return self._jump_to_current_match()

	def previous_match(self) -> bool:
		"""
		Jump to previous match.

		Returns:
			bool: True if jumped to previous match
		"""
		state = self._get_search_state()
		matches = state['matches']
		if not matches:
			return False

		# Move to previous match (wrap around)
		state['current_match_index'] = (state['current_match_index'] - 1) % len(matches)
		self._save_search_state(state)
		return self._jump_to_current_match()

	def first_match(self) -> bool:
		"""
		Jump to first match.

		Returns:
			bool: True if jumped to first match
		"""
		state = self._get_search_state()
		if not state['matches']:
			return False

		state['current_match_index'] = 0
		self._save_search_state(state)
		return self._jump_to_current_match()

	def last_match(self) -> bool:
		"""
		Jump to last match.

		Returns:
			bool: True if jumped to last match
		"""
		state = self._get_search_state()
		if not state['matches']:
			return False

		state['current_match_index'] = len(state['matches']) - 1
		self._save_search_state(state)
		return self._jump_to_current_match()

	def _unpack_match(self, match):
		"""Handle legacy (bookmark, text, line), (bookmark, text, line, pos), and new (bookmark, text, line, pos, offset) tuples."""
		if len(match) == 5:
			return match[0], match[1], match[2], match[3], match[4]
		elif len(match) == 4:
			return match[0], match[1], match[2], match[3], 0
		bookmark, line_text, line_num = match
		return bookmark, line_text, line_num, None, 0

	def _jump_to_current_match(self) -> bool:
		"""
		Jump to current match index and position cursor at the search term.

		Returns:
			bool: True if jump successful
		"""
		state = self._get_search_state()
		matches = state['matches']
		current_index = state['current_match_index']
		if not matches or current_index < 0:
			return False

		try:
			bookmark, line_text, line_num, pos_info, char_offset = self._unpack_match(
				matches[current_index]
			)

			pos = None
			if bookmark is not None:
				try:
					pos = self._terminal.makeTextInfo(bookmark)
				except Exception:
					pos = None

			if pos is None and pos_info is not None:
				try:
					pos = pos_info.copy()
				except Exception:
					pos = pos_info

			if pos:
				# Move cursor to the character position of the search term within the line
				if char_offset > 0:
					try:
						pos.move(textInfos.UNIT_CHARACTER, char_offset)
					except Exception:
						# If we can't move by character, just use line position
						pass

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
		state = self._get_search_state()
		return len(state['matches'])

	def get_current_match_info(self) -> tuple:
		"""
		Get information about current match.

		Returns:
			tuple: (match_number, total_matches, line_text, line_num) or None
		"""
		state = self._get_search_state()
		matches = state['matches']
		current_index = state['current_match_index']
		if not matches or current_index < 0:
			return None

		_, line_text, line_num, _, _ = self._unpack_match(matches[current_index])
		return (current_index + 1, len(matches), line_text, line_num)

	def clear_search(self) -> None:
		"""Clear current search results."""
		self._save_search_state({
			'pattern': None,
			'matches': [],
			'current_match_index': -1,
			'case_sensitive': False,
			'use_regex': False
		})

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
		# Legacy single-tab storage (deque for O(1) pop-from-front when limiting size)
		self._history: collections.deque = collections.deque(maxlen=max_history)
		self._current_index = -1  # Current position in history (-1 = not navigating)
		self._last_scan_line = 0  # Last line scanned for commands
		# Per-tab storage
		self._tab_histories = {}  # tab_id -> {history, current_index, last_scan_line}

		# Use module-level compiled prompt patterns
		self._prompt_patterns = _PROMPT_PATTERNS

	def detect_and_store_commands(self) -> int:
		"""
		Scan terminal output for new commands and store them.

		Uses a single forward walk from POSITION_FIRST to collect bookmarks,
		avoiding repeated POSITION_ALL + per-command O(line_num) walks.

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

			# Strip ANSI escape sequences that some terminals leave in the
			# text buffer so prompt patterns match cleanly.
			content = _strip_ansi(content)

			lines = content.split('\n')
			new_commands = 0
			scan_start = self._last_scan_line
			scan_end = len(lines)

			if scan_start >= scan_end:
				return 0

			# Single forward walk: start at POSITION_FIRST, advance to
			# scan_start, then walk through new lines collecting bookmarks
			# only for matching lines.  This is O(total_new_lines) COM calls
			# instead of O(sum_of_line_numbers) for the old per-command walk.
			try:
				cursor = self._terminal.makeTextInfo(textInfos.POSITION_FIRST)
				# Skip to scan_start position
				if scan_start > 0:
					cursor.move(textInfos.UNIT_LINE, scan_start)

				for line_num in range(scan_start, scan_end):
					line = lines[line_num].strip()

					if line:
						# Try to match against prompt patterns
						for pat in self._prompt_patterns:
							match = pat.match(line)
							if match:
								command_text = match.group(1).strip()

								# Ignore empty commands or very short ones
								if len(command_text) < 2:
									continue

								# Check if this is a duplicate of last command
								if self._history and self._history[-1][1] == command_text:
									continue

								# Grab bookmark from the cursor at current position
								try:
									bookmark = cursor.bookmark
									self._history.append((line_num, command_text, bookmark))
									new_commands += 1
								except Exception:
									pass

								break  # Found a match, no need to try other patterns

					# Advance cursor to next line
					if line_num < scan_end - 1:
						if not cursor.move(textInfos.UNIT_LINE, 1):
							break
			except Exception:
				# Cursor walk failed — fall back silently
				pass

			# Update last scan position
			self._last_scan_line = scan_end

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


# ── URL entry data structure ─────────────────────────────────────────
UrlEntry = collections.namedtuple('UrlEntry', ['url', 'line_num', 'line_text', 'source', 'count'])


class UrlExtractorManager:
	"""
	Extract and manage URLs found in terminal output.

	Scans terminal buffer for URLs (HTTP/HTTPS/FTP, www-prefixed,
	file:// protocol, and OSC 8 terminal hyperlinks) and provides
	a navigable list with copy/open/move-to actions.
	"""

	def __init__(self, terminal_obj, tab_manager=None):
		self._terminal = terminal_obj
		self._tab_manager = tab_manager
		self._urls: list = []  # list of UrlEntry

	def extract_urls(self) -> list:
		"""Scan terminal buffer and return deduplicated URLs with context.

		Returns:
			List of UrlEntry namedtuples ordered by first occurrence.
		"""
		if not self._terminal:
			return []

		try:
			text_info = self._terminal.makeTextInfo(textInfos.POSITION_ALL)
			raw_text = text_info.text
		except Exception:
			try:
				import logHandler
				logHandler.log.debugWarning("UrlExtractorManager: failed to read terminal text", exc_info=True)
			except Exception:
				pass
			return []

		if not raw_text:
			return []

		# Phase 1: Extract OSC 8 hyperlinks from raw text (before ANSI strip)
		osc8_urls: dict[str, int] = {}  # url -> first line_num
		raw_lines = raw_text.split('\n')
		for line_num, line in enumerate(raw_lines, start=1):
			for match in _OSC8_URL_PATTERN.finditer(line):
				url = _clean_url(match.group(1).strip())
				if url and url not in osc8_urls:
					osc8_urls[url] = line_num

		# Phase 2: Extract plain-text URLs after ANSI stripping
		clean_text = _strip_ansi(raw_text)
		lines = clean_text.split('\n')

		# Deduplicate preserving first-occurrence order
		seen: collections.OrderedDict = collections.OrderedDict()

		# Add OSC 8 URLs first
		for url, line_num in osc8_urls.items():
			line_text = lines[line_num - 1].strip() if line_num <= len(lines) else ''
			seen[url] = {'line_num': line_num, 'line_text': line_text, 'source': 'osc8', 'count': 1}

		# Scan each line for plain-text URLs
		for line_num, line in enumerate(lines, start=1):
			for match in _URL_PATTERN.finditer(line):
				url = _clean_url(match.group(0).strip())
				if not url:
					continue
				if url in seen:
					seen[url]['count'] += 1
				else:
					seen[url] = {
						'line_num': line_num,
						'line_text': line.strip(),
						'source': 'text',
						'count': 1,
					}

		self._urls = [
			UrlEntry(url=url, line_num=meta['line_num'], line_text=meta['line_text'],
			         source=meta['source'], count=meta['count'])
			for url, meta in seen.items()
		]
		return list(self._urls)

	def get_url_count(self) -> int:
		"""Return number of extracted URLs."""
		return len(self._urls)

	def copy_url(self, index: int) -> bool:
		"""Copy URL at index to clipboard."""
		if 0 <= index < len(self._urls):
			api.copyToClip(self._urls[index].url)
			return True
		return False

	# Schemes considered safe to open in a browser.
	_SAFE_SCHEMES = ('http://', 'https://', 'ftp://')

	def open_url(self, index: int) -> bool:
		"""Open URL at index in default browser.

		Only http://, https://, and ftp:// URLs are opened.  Other schemes
		(file://, javascript:, etc.) are rejected to prevent a malicious
		terminal from launching local executables.
		"""
		if 0 <= index < len(self._urls):
			url = self._urls[index].url
			# Ensure scheme for www. URLs
			if url.lower().startswith('www.'):
				url = 'https://' + url
			# Block unsafe schemes
			if not url.lower().startswith(self._SAFE_SCHEMES):
				return False
			try:
				webbrowser.open(url)
				return True
			except Exception:
				return False
		return False

	def update_terminal(self, terminal_obj):
		"""Update terminal reference and clear cached URLs."""
		self._terminal = terminal_obj
		self._urls = []

	def set_tab_manager(self, tab_manager):
		"""Set or update tab manager."""
		self._tab_manager = tab_manager


class UrlListDialog(wx.Dialog):
	"""
	Dialog for displaying and interacting with URLs found in terminal output.

	Modeled after NVDA's Elements List (NVDA+F7) but designed for terminal
	focus mode where the Elements List is unavailable.
	"""

	def __init__(self, parent, urls, manager):
		super().__init__(
			parent,
			# Translators: Title for URL list dialog
			title=_("URL List - Terminal Access"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._urls = urls  # list of UrlEntry
		self._filtered_urls = list(urls)
		self._manager = manager

		main_sizer = wx.BoxSizer(wx.VERTICAL)

		# Filter
		filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Label for URL filter text box
		filter_label = wx.StaticText(self, label=_("&Filter:"))
		filter_sizer.Add(filter_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self._filter_ctrl = wx.TextCtrl(self)
		self._filter_ctrl.Bind(wx.EVT_TEXT, self._on_filter)
		filter_sizer.Add(self._filter_ctrl, 1, wx.EXPAND)
		main_sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 5)

		# List
		self._list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		# Translators: Column header for URL list index
		self._list_ctrl.InsertColumn(0, _("#"), width=40)
		# Translators: Column header for URL
		self._list_ctrl.InsertColumn(1, _("URL"), width=320)
		# Translators: Column header for line number
		self._list_ctrl.InsertColumn(2, _("Line"), width=55)
		# Translators: Column header for line context
		self._list_ctrl.InsertColumn(3, _("Context"), width=220)
		self._list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_open)
		main_sizer.Add(self._list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

		# Buttons
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button to open URL in browser
		self._open_btn = wx.Button(self, label=_("&Open"))
		# Translators: Button to copy URL to clipboard
		self._copy_btn = wx.Button(self, label=_("&Copy URL"))
		# Translators: Button to move cursor to URL line
		self._move_btn = wx.Button(self, label=_("&Move to line"))
		# Use wx.ID_CANCEL so pressing Escape automatically closes the dialog
		close_btn = wx.Button(self, wx.ID_CANCEL, label=_("Close"))

		self._open_btn.Bind(wx.EVT_BUTTON, self._on_open)
		self._copy_btn.Bind(wx.EVT_BUTTON, self._on_copy)
		self._move_btn.Bind(wx.EVT_BUTTON, self._on_move)
		close_btn.Bind(wx.EVT_BUTTON, self._on_close)
		self.Bind(wx.EVT_CLOSE, self._on_close)

		# Allow Escape key to close the dialog from any focused control
		self.SetEscapeId(wx.ID_CANCEL)

		btn_sizer.Add(self._open_btn, 0, wx.RIGHT, 5)
		btn_sizer.Add(self._copy_btn, 0, wx.RIGHT, 5)
		btn_sizer.Add(self._move_btn, 0, wx.RIGHT, 5)
		btn_sizer.Add(close_btn, 0)
		main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self.SetSizer(main_sizer)
		self._populate_list()
		self.SetSize(680, 420)
		self.CenterOnScreen()

		# Focus the list
		if self._list_ctrl.GetItemCount() > 0:
			self._list_ctrl.Select(0)
			self._list_ctrl.Focus(0)
			self._list_ctrl.SetFocus()
		else:
			self._filter_ctrl.SetFocus()

	def _populate_list(self):
		"""Fill the list control with the current filtered URLs."""
		self._list_ctrl.DeleteAllItems()
		for i, entry in enumerate(self._filtered_urls):
			idx = self._list_ctrl.InsertItem(i, str(i + 1))
			self._list_ctrl.SetItem(idx, 1, entry.url)
			self._list_ctrl.SetItem(idx, 2, str(entry.line_num))
			context = entry.line_text[:80] if entry.line_text else ''
			self._list_ctrl.SetItem(idx, 3, context)

	def _on_filter(self, event):
		"""Filter URLs as the user types."""
		filter_text = self._filter_ctrl.GetValue().lower()
		if filter_text:
			self._filtered_urls = [
				u for u in self._urls
				if filter_text in u.url.lower() or filter_text in u.line_text.lower()
			]
		else:
			self._filtered_urls = list(self._urls)
		self._populate_list()
		if self._list_ctrl.GetItemCount() > 0:
			self._list_ctrl.Select(0)
			self._list_ctrl.Focus(0)

	def _get_selected_index(self) -> int:
		"""Return the index into _filtered_urls of the selected list item."""
		return self._list_ctrl.GetFirstSelected()

	def _on_open(self, event):
		"""Open selected URL in the default browser."""
		sel = self._get_selected_index()
		if sel < 0:
			return
		entry = self._filtered_urls[sel]
		url = entry.url
		if url.lower().startswith('www.'):
			url = 'https://' + url
		# Block unsafe schemes (file://, javascript:, etc.)
		if not url.lower().startswith(UrlExtractorManager._SAFE_SCHEMES):
			# Translators: Announced when a URL with an unsafe scheme is blocked
			ui.message(_("Cannot open this URL type for security reasons"))
			return
		try:
			webbrowser.open(url)
		except Exception:
			pass
		self.Close()

	def _on_copy(self, event):
		"""Copy selected URL to clipboard."""
		sel = self._get_selected_index()
		if sel < 0:
			return
		api.copyToClip(self._filtered_urls[sel].url)
		# Translators: Announced after URL is copied
		ui.message(_("URL copied"))
		self.Close()

	def _on_move(self, event):
		"""Close dialog and announce which line the URL is on."""
		sel = self._get_selected_index()
		if sel < 0:
			return
		entry = self._filtered_urls[sel]
		self.Close()
		# Translators: Announced when moving to a URL line
		ui.message(_("Line {num}: {text}").format(num=entry.line_num, text=entry.line_text[:100]))

	def _on_close(self, event):
		"""Close the dialog."""
		if self.IsModal():
			self.EndModal(wx.ID_CANCEL)
		else:
			self.Destroy()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""
	Terminal Access Global Plugin for NVDA

	Provides enhanced terminal accessibility for Windows Terminal, PowerShell,
	Command Prompt, and other console applications.

	==== KEYBOARD GESTURES ====

	Navigation (Line-based):
		NVDA+U - Previous line
		NVDA+I - Current line (double-press: indentation level)
		NVDA+O - Next line

	Navigation (Word-based):
		NVDA+J - Previous word
		NVDA+K - Current word (double-press: spell word)
		NVDA+L - Next word

	Navigation (Character-based):
		NVDA+M          - Previous character
		NVDA+Comma      - Current character (double: phonetic, triple: code)
		NVDA+Period     - Next character

	Navigation (Boundary Movement):
		NVDA+Shift+Home     - Move to first character of current line
		NVDA+Shift+End      - Move to last character of current line
		NVDA+F4             - Move to top of buffer
		NVDA+F6             - Move to bottom of buffer

	Reading (Directional):
		NVDA+Shift+Left  - Read from cursor to start of line
		NVDA+Shift+Right - Read from cursor to end of line
		NVDA+Shift+Up    - Read from cursor to top of buffer
		NVDA+Shift+Down  - Read from cursor to bottom of buffer

	Information and Attributes:
		NVDA+;           - Announce cursor position (row, column)
		NVDA+A           - Say All (continuous reading)
		NVDA+Shift+A     - Read color and formatting attributes

	Selection and Copying:
		NVDA+R           - Toggle mark (start/end/clear)
		NVDA+C           - Copy linear selection (between marks)
		NVDA+Shift+C     - Copy rectangular selection (columns)
		NVDA+X           - Clear selection marks
		NVDA+V           - Enter copy mode (line/screen)

	Window Management:
		NVDA+Alt+F2      - Define screen window (two-step)
		NVDA+Alt+F3      - Clear screen window
		NVDA+Alt+Plus    - Read window content
		NVDA+Alt+Y - Cycle cursor tracking mode
		(Note: Window management retains the Alt modifier as these are advanced,
		 infrequently-used features where the extra modifier prevents accidental activation.)

	Configuration:
		NVDA+Shift+Q     - Toggle quiet mode
		NVDA+Shift+N     - Toggle announce new output
		NVDA+[           - Decrease punctuation level
		NVDA+]           - Increase punctuation level
		NVDA+F5          - Toggle automatic indentation announcement
		NVDA+F10         - Announce active and default profiles

	Help:
		NVDA+Shift+F1    - Open Terminal Access user guide

	URL List:
		NVDA+Alt+U       - List URLs in terminal output (open, copy, navigate)

	==== DESIGN PATTERNS ====
	- Base navigation: NVDA+{letter} (no Alt required)
	- Extended operations: NVDA+Shift+{letter}
	- Line navigation: U/I/O (vertical cluster on keyboard)
	- Word navigation: J/K/L (horizontal cluster on keyboard)
	- Character navigation: M/Comma/Period (right hand cluster)
	- Boundaries: Shift+Home/End (line), F4/F6 (buffer top/bottom)
	- Directional reading: Shift+Arrow keys
	- Selection: R (mark), C (copy), X (clear)
	- Punctuation: Bracket keys [ and ]

	==== CURSOR TRACKING MODES ====
	0 - Off: No automatic tracking
	1 - Standard: Follow system caret
	2 - Highlight: Track highlighted/selected text
	3 - Window: Track within defined screen region
	"""

	# Class-level gesture map consumed by NVDA's Input Gestures dialog.
	# Without this dict, gestures defined via @script(gesture=...) are bound
	# at the instance level but do not appear in the Input Gestures list.
	__gestures = _DEFAULT_GESTURES

	def __init__(self):
		"""Initialize the Terminal Access global plugin."""
		super().__init__()

		# Initialize manager classes for configuration, windows, and position tracking
		self._configManager = ConfigManager()
		self._windowManager = WindowManager(self._configManager)
		self._positionCalculator = PositionCalculator()

		# Initialize state variables
		self.lastTerminalAppName = None
		self.announcedHelp = False
		self.copyMode = False
		self._inCommandLayer = False
		self._boundTerminal = None
		self._cursorTrackingTimer = None
		self._lastCaretPosition = None
		self._lastTypedChar = None
		self._repeatedCharCount = 0
		self._lastTypedCharTime: float = 0.0

		# Content generation counter — incremented whenever terminal content changes.
		# Used to invalidate per-line TextInfo caches in _announceStandardCursor.
		self._contentGeneration: int = 0

		# Line-level TextInfo cache for _announceStandardCursor.
		# Stores the text of the last line visited so that moving within the
		# same line (and with no intervening content change) avoids extra COM
		# calls.
		self._lastLineText: str | None = None
		self._lastLineStartOffset: int | None = None
		self._lastLineEndOffset: int | None = None
		self._lastLineGeneration: int = -1

		# isTerminalApp cache — maps appName (str) to bool result so the
		# 30-entry substring scan runs only once per unique application name.
		self._terminalAppCache: dict[str, bool] = {}

		# Cached punctuation set — avoids dict lookup on every typed character.
		# Invalidated when the punctuation level changes.
		self._cachedPunctLevel: int = -1
		self._cachedPunctSet: set | None = None

		# Highlight tracking state
		self._lastHighlightedText = None
		self._lastHighlightPosition = None

		# Enhanced selection state
		self._markStart = None
		self._markEnd = None

		# Window definition two-step state (Section 6 - setWindow)
		self._windowStartSet = False
		self._windowStartBookmark = None
		self._windowStartRow = 0
		self._windowStartCol = 0

		# Background calculation thread for long operations
		self._backgroundCalculationThread = None

		# Operation queue to prevent overlapping background operations (Section 1.3)
		self._operationQueue = OperationQueue()

		# Application profile management
		self._profileManager = ProfileManager()
		self._currentProfile = None

		# Window monitor for multi-window monitoring (Section 6.1 - v1.0.28+)
		self._windowMonitor = None  # Initialized when terminal is bound

		# New output announcer for automatically speaking appended terminal output.
		# Polling is deferred until a terminal is actually focused (in
		# event_gainFocus) to avoid spinning a background thread before there
		# is anything to poll.
		self._newOutputAnnouncer = NewOutputAnnouncer()

		# Start the helper process eagerly on a background thread so it's warm
		# by the time a terminal is focused.  Non-blocking and non-fatal.
		threading.Thread(target=_start_helper_eagerly, daemon=True).start()

		# Tab manager for managing terminal tabs (Section 9 - v1.0.39+)
		self._tabManager = None  # Initialized when terminal is bound

		# Bookmark manager for quick navigation (Section 8.3 - v1.0.29+)
		self._bookmarkManager = None  # Initialized when terminal is bound

		# Output search manager for filtering and search (Section 8.2 - v1.0.30+)
		self._searchManager = None  # Initialized when terminal is bound
		self._searchDialogOpen = False  # Guard against multiple search dialog instances

		# Command history manager for navigation (Section 8.1 - v1.0.31+)
		self._commandHistoryManager = None  # Initialized when terminal is bound

		# URL extractor manager for URL detection and navigation (Section 8.4)
		self._urlExtractorManager = None  # Initialized when terminal is bound
		self._urlDialogOpen = False  # Guard against multiple URL list instances

		# Track and scope gesture bindings to terminal focus only
		self._terminalGestures = self._collectTerminalGestures()
		self._gesturesBound = False
		self._disableTerminalGestures()
		try:
			self._updateGestureBindingsForFocus(api.getForegroundObject())
		except Exception:
			# Foreground detection can fail during early startup
			pass

		# Add settings panel to NVDA preferences
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(TerminalAccessSettingsPanel)
		except (AttributeError, TypeError, RuntimeError):
			# GUI may not be fully initialized yet, which is acceptable
			# Settings panel will not be available in this case
			pass

	def _collectTerminalGestures(self) -> dict[str, str]:
		"""Return the gesture map for conditional binding, excluding user-disabled gestures."""
		try:
			raw = config.conf["terminalAccess"]["unboundGestures"]
		except (KeyError, TypeError):
			raw = ""
		excluded = set(g.strip() for g in raw.split(",") if g.strip())
		return {
			g: s for g, s in _DEFAULT_GESTURES.items()
			if g not in excluded or g in _ALWAYS_BOUND
		}

	def _enableTerminalGestures(self):
		"""Bind Terminal Access gestures when a terminal is focused."""
		if self._gesturesBound or not self._terminalGestures:
			return
		try:
			self.bindGestures(self._terminalGestures)
		except Exception:
			# Fallback for test mocks without bindGestures
			try:
				self.__class__.__gestures__ = self._terminalGestures
			except Exception:
				pass
		self._gesturesBound = True

	def _disableTerminalGestures(self):
		"""Unbind Terminal Access gestures outside terminal focus."""
		if not self._terminalGestures:
			return
		# Exit command layer silently before unbinding (focus loss auto-exit)
		if getattr(self, "_inCommandLayer", False):
			self._exitCommandLayer()
		# Iterate _DEFAULT_GESTURES (not _terminalGestures) to also clean up
		# decorator-created bindings for gestures excluded from _terminalGestures
		for gesture in _DEFAULT_GESTURES:
			try:
				self.removeGestureBinding(gesture)
			except Exception:
				pass
		if getattr(self, "copyMode", False):
			self._exitCopyModeBindings()
			self.copyMode = False
		self._gesturesBound = False

	def _reloadGestures(self):
		"""Rebuild gesture bindings from current config (called after settings change)."""
		wasBound = self._gesturesBound
		if wasBound:
			self._disableTerminalGestures()
		self._terminalGestures = self._collectTerminalGestures()
		if wasBound:
			self._gesturesBound = False
			self._enableTerminalGestures()

	def _updateGestureBindingsForFocus(self, obj) -> bool:
		"""Enable gestures when a terminal is focused, otherwise disable them."""
		if self.isTerminalApp(obj):
			self._enableTerminalGestures()
			return True
		self._disableTerminalGestures()
		return False

	def terminate(self):
		"""Clean up when the plugin is terminated."""
		# Stop new output announcer polling if active
		if self._newOutputAnnouncer:
			self._newOutputAnnouncer.stop_polling()

		# Stop window monitoring if active
		if self._windowMonitor and self._windowMonitor.is_monitoring():
			self._windowMonitor.stop_monitoring()

		# Stop the native helper process
		try:
			_stop_helper()
		except Exception:
			pass

		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(TerminalAccessSettingsPanel)
		except (ValueError, AttributeError):
			pass
		super().terminate()
	
	def isTerminalApp(self, obj=None):
		"""
		Check if the current application is a supported terminal.

		Supports built-in Windows terminals, popular third-party terminal
		emulators, and WSL (Windows Subsystem for Linux).  Also detects TUI
		applications that run *inside* terminal windows (their host process
		is a supported terminal).

		Results are cached per appName so the 30-entry substring scan only
		runs once per unique application.  The cache is a plain dict keyed
		by the lowercased appName string.

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

		if not isinstance(appName, str):
			return False

		# Cache lookup — avoids re-scanning substrings on every event.
		cached = self._terminalAppCache.get(appName)
		if cached is not None:
			return cached

		# Reject known non-terminal apps before checking the inclusion list
		if any(exc in appName for exc in _NON_TERMINAL_APPS):
			self._terminalAppCache[appName] = False
			return False

		result = any(term in appName for term in _SUPPORTED_TERMINALS)
		self._terminalAppCache[appName] = result
		return result

	def _terminalStripsAnsi(self, obj=None) -> bool:
		"""Return True if the terminal's UIA provider strips ANSI escape codes.

		Modern GPU-accelerated terminals (Windows Terminal, Alacritty, WezTerm,
		Ghostty, etc.) return clean text from UIA — checking for raw ANSI codes
		like ``\\x1b[7m`` will never succeed and just wastes a UNIT_LINE read.
		"""
		if obj is None:
			obj = self._boundTerminal
		if obj is None:
			return False
		try:
			appName = obj.appModule.appName.lower()
			return any(t in appName for t in _ANSI_STRIPPING_TERMINALS)
		except (AttributeError, TypeError):
			return False

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
			# calculate() returns 1-based values; do not add 1 again
			return _("Row {row}, column {col}").format(row=row, col=col)
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

		if not self._updateGestureBindingsForFocus(obj):
			self._boundTerminal = None
			return

		if self.isTerminalApp(obj):
			try:
				appName = obj.appModule.appName
			except (AttributeError, TypeError):
				return

			# Store the terminal object and route the review cursor to it via the navigator
			self._boundTerminal = obj

			# Lazy-start the native helper process on first terminal focus.
			# This is a no-op if already running or if the EXE is unavailable.
			try:
				_get_helper()
			except Exception:
				pass
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

			# Initialize UrlExtractorManager for this terminal (Section 8.4)
			if not self._urlExtractorManager:
				self._urlExtractorManager = UrlExtractorManager(obj, self._tabManager)
			else:
				self._urlExtractorManager.update_terminal(obj)

			# Start new-output polling lazily on first terminal focus
			try:
				self._newOutputAnnouncer.set_terminal(obj)
				if config.conf["terminalAccess"]["announceNewOutput"]:
					self._newOutputAnnouncer.start_polling()
			except Exception:
				pass

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

	def _getEffective(self, key: str):
		"""Return the effective value of a Terminal Access setting.

		When an application profile is active and it explicitly overrides
		*key* (i.e. the attribute is not ``None``), that value is returned.
		Otherwise the global ``config.conf["terminalAccess"]`` value is used.

		This ensures that profile-specific settings (e.g. ``keyEcho = False``
		for lazygit, ``punctuationLevel = PUNCT_MOST`` for git) take effect
		at runtime while still falling back to the user's global preferences
		for settings the profile does not override.
		"""
		if self._currentProfile is not None:
			val = getattr(self._currentProfile, key, None)
			if val is not None:
				return val
		return config.conf["terminalAccess"][key]

	def _isKeyEchoActive(self) -> bool:
		"""Check if the addon should perform its own key echo.

		Returns False when the addon's key echo is disabled, quiet mode is on,
		or NVDA's native speak-typed-characters setting is already enabled
		(to avoid duplicate announcements).
		"""
		if not self._getEffective("keyEcho"):
			return False
		if self._getEffective("quietMode"):
			return False
		# When NVDA's own character echo is on, let NVDA handle it
		# to avoid speaking every character twice.
		if config.conf["keyboard"]["speakTypedCharacters"]:
			return False
		return True

	def event_typedCharacter(self, obj, nextHandler, ch):
		"""
		Handle typed character events.

		Announces characters as they are typed if keyEcho is enabled.
		Uses punctuation level system to determine whether to speak symbol names.
		Uses repeatedSymbols to condense sequences of repeated symbols.

		When NVDA's own speak-typed-characters setting is enabled, the addon
		defers to NVDA to avoid duplicate announcements.
		"""
		nextHandler()

		# Only handle if in a terminal
		if not self.isTerminalApp(obj):
			return

		# Record typing timestamp so cursor tracking can distinguish
		# typing-induced caret events from navigation.
		self._lastTypedCharTime = time.time()

		# Don't echo if disabled, quiet, or NVDA is already echoing
		if not self._isKeyEchoActive():
			return

		# Clear position cache on content change
		self._positionCalculator.clear_cache()

		# Increment content generation so cached line TextInfo is invalidated.
		self._contentGeneration += 1

		# Process the character for speech
		if ch:
			# Check if we should condense repeated symbols
			if self._getEffective("repeatedSymbols"):
				repeatedSymbolsValues = self._getEffective("repeatedSymbolsValues")

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

			self._speakCharacter(ch)

	def _brailleMessage(self, text):
		"""Show text on the Braille display.

		Safe to call when no display is connected or the braille module is
		unavailable.  Use this alongside ``speech.speakText()`` calls which
		do not produce Braille output on their own.

		Args:
			text: The text to show on the Braille display.
		"""
		if not _braille_available:
			return
		try:
			if self._getEffective("quietMode"):
				return
			if braille.handler.displaySize > 0:
				braille.handler.message(text)
		except Exception:
			pass

	def _announceRepeatedSymbol(self, char, count):
		"""
		Announce a repeated symbol with its count.

		Args:
			char: The repeated character.
			count: The number of times it was repeated.
		"""
		symbolName = self._resolveSymbol(char)
		if count > 1:
			# Translators: Message format for repeated symbols, e.g. "3 dash"
			ui.message(_("{count} {symbol}").format(count=count, symbol=symbolName))
		else:
			ui.message(symbolName)

	def event_caret(self, obj, nextHandler):
		"""
		Handle caret movement events.

		Announces cursor position changes if cursorTracking is enabled.
		Uses cursorDelay to debounce rapid movements.
		"""
		nextHandler()

		# Feed terminal content to the new output announcer when enabled.
		# This is done before the quiet/cursorTracking guards so that the
		# announcer's own quiet-mode check governs output independently.
		if not self.isTerminalApp(obj):
			return

		self._feedNewOutputAnnouncer(obj)

		# Only handle if cursor tracking is enabled
		ta_conf = config.conf["terminalAccess"]
		if not ta_conf["cursorTracking"] or ta_conf["quietMode"]:
			return

		# Cancel any pending cursor tracking announcement
		if self._cursorTrackingTimer:
			self._cursorTrackingTimer.Stop()
			self._cursorTrackingTimer = None

		# Schedule announcement with delay
		self._cursorTrackingTimer = wx.CallLater(ta_conf["cursorDelay"], self._announceCursorPosition, obj)

	def _feedNewOutputAnnouncer(self, obj) -> None:
		"""
		Read the current terminal buffer and feed it to the new output announcer.

		Also updates the terminal object reference for polling.

		When the helper process is subscribed and pushing diff notifications,
		the expensive ``makeTextInfo(POSITION_ALL)`` read is skipped entirely —
		the helper's 50ms push loop handles output detection. This eliminates
		the 10KB-1MB UIA read from the main thread on every caret event.

		This is a best-effort helper: any exception is silently ignored so it
		never disrupts normal caret handling.

		Args:
			obj: The focused terminal object.
		"""
		try:
			# Update terminal object for polling (in case it changed)
			self._newOutputAnnouncer.set_terminal(obj)
			# When the helper is subscribed and pushing diffs, skip the expensive
			# POSITION_ALL read — the helper handles output detection at 50ms.
			if getattr(self._newOutputAnnouncer, "_subscribed_hwnd", None) is not None:
				return
			# Gate the expensive POSITION_ALL read behind cheap config/throttle checks.
			# On conhost this avoids reading the entire buffer (10KB-1MB) hundreds of
			# times per second when announceNewOutput is off or in quiet mode.
			if not self._newOutputAnnouncer.should_read():
				return
			info = obj.makeTextInfo(textInfos.POSITION_ALL)
			self._newOutputAnnouncer.feed(info.text)
		except Exception:
			pass

	def _announceCursorPosition(self, obj):
		"""
		Announce the current cursor position based on the tracking mode.

		Args:
			obj: The terminal object.
		"""
		try:
			trackingMode = self._getEffective("cursorTrackingMode")
			match trackingMode:
				case 0:  # CT_OFF
					return
				case 1:  # CT_STANDARD
					self._announceStandardCursor(obj)
				case 2:  # CT_HIGHLIGHT
					self._announceHighlightCursor(obj)
				case 3:  # CT_WINDOW
					self._announceWindowCursor(obj)
		except Exception:
			# Silently fail - cursor tracking is a non-critical feature
			pass

	def _announceStandardCursor(self, obj):
		"""
		Standard cursor tracking - announce character at cursor position.

		Uses a line-level cache to avoid redundant UIA/COM calls when the
		caret moves within the same line and no content change has occurred
		since the last announcement.

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

		# Try to retrieve the character from the line cache.
		# The cache is valid when:
		#   (a) content generation hasn't changed (no typing/text changes), and
		#   (b) the new caret offset falls within the cached line's range.
		char = None
		lls = self._lastLineStartOffset
		lle = self._lastLineEndOffset
		cache_valid = (
			self._lastLineText is not None
			and self._lastLineGeneration == self._contentGeneration
			and currentPos is not None
			and lls is not None
			and lle is not None
			and lls <= currentPos < lle
		)

		if cache_valid:
			# Compute character index within the cached line text.
			char_index = currentPos - lls
			if 0 <= char_index < len(self._lastLineText):
				char = self._lastLineText[char_index]

		if char is None:
			# Cache miss or out-of-range: expand to character and also refresh
			# the line cache for future caret events on the same line.
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text

			# On conhost, bookmark offsets are often unavailable (AttributeError),
			# so the indexed cache lookup always fails.  When offsets are None and
			# the content generation hasn't changed, we can skip the UNIT_LINE
			# re-read — the text hasn't changed, we just can't index into it.
			# This saves one UIA call per cursor movement on conhost.
			skip_line_reread = (
				self._lastLineStartOffset is None
				and self._lastLineEndOffset is None
				and self._lastLineGeneration == self._contentGeneration
				and self._lastLineText is not None
			)
			if not skip_line_reread:
				# Refresh line cache: expand a fresh copy to the full line.
				try:
					line_info = obj.makeTextInfo(textInfos.POSITION_CARET)
					line_info.expand(textInfos.UNIT_LINE)
					self._lastLineText = line_info.text
					bm = getattr(line_info, 'bookmark', None)
					try:
						self._lastLineStartOffset = bm.startOffset
						self._lastLineEndOffset = bm.endOffset
					except AttributeError:
						# Offsets unavailable (conhost); keep text cache but can't
						# do indexed character lookup.  The UNIT_CHARACTER expand
						# above still works.
						self._lastLineStartOffset = None
						self._lastLineEndOffset = None
					self._lastLineGeneration = self._contentGeneration
				except Exception:
					self._lastLineText = None
					self._lastLineStartOffset = None
					self._lastLineEndOffset = None

		# When a recent keystroke caused this caret movement and the addon's
		# key echo is off, suppress the character announcement to avoid a
		# "shadow key echo" through cursor tracking.  Navigation-induced
		# caret events (arrow keys, Home/End, etc.) are not affected because
		# they don't set _lastTypedCharTime.
		typing_induced = (time.time() - self._lastTypedCharTime) < 0.3
		if typing_induced and not self._isKeyEchoActive():
			return

		self._speakCharacter(char)

		# Notify the Braille display of the caret movement so it shows the
		# full line context around the cursor instead of a brief character flash.
		if _braille_available:
			try:
				if braille.handler.displaySize > 0:
					braille.handler.handleCaretMove(obj)
			except Exception:
				pass

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

			# Try to detect ANSI escape codes for highlighting (inverse video: ESC[7m).
			# Skip on terminals whose UIA provider strips ANSI codes (Windows Terminal,
			# Alacritty, etc.) — the check can never succeed and wastes a UNIT_LINE read.
			if not self._terminalStripsAnsi(obj) and ('\x1b[7m' in lineText or 'ESC[7m' in lineText):
				# Extract highlighted portion
				highlightedText = self._extractHighlightedText(lineText)
				if highlightedText and highlightedText != self._lastHighlightedText:
					self._lastHighlightedText = highlightedText
					ui.message(_("Highlighted: {text}").format(text=highlightedText))
				# Update Braille display with full line context
				if _braille_available:
					try:
						if braille.handler.displaySize > 0:
							braille.handler.handleCaretMove(obj)
					except Exception:
						pass
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
		cleanText = _ANSI_HIGHLIGHT_RE.sub('', text).strip()
		return cleanText if cleanText else None

	@script(
		# Translators: Description for the show help gesture
		description=_("Opens the Terminal Access user guide"),
		gesture="kb:NVDA+shift+f1",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+u",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+i",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+o",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+j",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+k",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+k,kb:NVDA+k",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+l",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+m",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+,",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+.",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+shift+q",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_toggleQuietMode(self, gesture):
		"""Toggle quiet mode on/off."""
		if not self.isTerminalApp():
			gesture.send()
			return
		
		currentState = self._getEffective("quietMode")
		newState = not currentState
		# Write to global config; also update profile override if one is active
		# so the toggle takes immediate effect.
		config.conf["terminalAccess"]["quietMode"] = newState
		if self._currentProfile is not None and self._currentProfile.quietMode is not None:
			self._currentProfile.quietMode = newState

		if newState:
			# Translators: Message when quiet mode is enabled
			ui.message(_("Quiet mode on"))
		else:
			# Translators: Message when quiet mode is disabled
			ui.message(_("Quiet mode off"))

	@script(
		# Translators: Description for toggling announce new output
		description=_("Toggle announce new output in terminal"),
		gesture="kb:NVDA+shift+n",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_toggleAnnounceNewOutput(self, gesture):
		"""Toggle announce new output on/off."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentState = config.conf["terminalAccess"]["announceNewOutput"]
		config.conf["terminalAccess"]["announceNewOutput"] = not currentState

		if config.conf["terminalAccess"]["announceNewOutput"]:
			# Reset the announcer so it doesn't speak stale buffered content
			self._newOutputAnnouncer.reset()
			# Set the current terminal object and start polling
			try:
				obj = api.getForegroundObject()
				self._newOutputAnnouncer.set_terminal(obj)
				self._newOutputAnnouncer.start_polling()
			except Exception:
				pass
			# Translators: Message when announce new output is enabled
			ui.message(_("Announce new output on"))
		else:
			# Stop polling when feature is disabled
			self._newOutputAnnouncer.stop_polling()
			# Translators: Message when announce new output is disabled
			ui.message(_("Announce new output off"))

	@script(
		# Translators: Description for toggling indentation announcement
		description=_("Toggle indentation announcement on line read in terminal"),
		gesture="kb:NVDA+f5",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_toggleIndentation(self, gesture):
		"""Toggle indentation announcement on/off."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentState = self._getEffective("indentationOnLineRead")
		newState = not currentState
		config.conf["terminalAccess"]["indentationOnLineRead"] = newState
		if self._currentProfile is not None and self._currentProfile.indentationOnLineRead is not None:
			self._currentProfile.indentationOnLineRead = newState

		if newState:
			# Translators: Message when indentation announcement is enabled
			ui.message(_("Indentation announcement on"))
		else:
			# Translators: Message when indentation announcement is disabled
			ui.message(_("Indentation announcement off"))

	@script(
		# Translators: Description for copy mode
		description=_("Enter copy mode in terminal"),
		gesture="kb:NVDA+v",
		category=SCRCAT_TERMINALACCESS,
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
		description=_("Copy line in copy mode"),
		category=SCRCAT_TERMINALACCESS,
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
		description=_("Copy screen in copy mode"),
		category=SCRCAT_TERMINALACCESS,
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
		description=_("Exit copy mode"),
		category=SCRCAT_TERMINALACCESS,
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
		# If the command layer is active, re-bind the layer gestures that
		# copy mode temporarily overwrote (l, s, escape).
		if getattr(self, "_inCommandLayer", False):
			for gesture_id in ("kb:l", "kb:s", "kb:escape"):
				if gesture_id in _COMMAND_LAYER_MAP:
					try:
						self.bindGesture(gesture_id, _COMMAND_LAYER_MAP[gesture_id])
					except Exception:
						pass

	# ------------------------------------------------------------------
	# Command Layer — modal input mode for single-key commands
	# ------------------------------------------------------------------

	@script(
		# Translators: Description for toggling the command layer
		description=_("Toggle terminal command layer (single-key command mode)"),
		gesture="kb:NVDA+'",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_toggleCommandLayer(self, gesture):
		"""Toggle the command layer on/off."""
		if not self.isTerminalApp():
			gesture.send()
			return
		if self._inCommandLayer:
			self._exitCommandLayer()
		else:
			self._enterCommandLayer()

	def _enterCommandLayer(self):
		"""Activate the command layer by binding all single-key gestures."""
		if self._inCommandLayer:
			return
		# If copy mode is active, exit it first
		if self.copyMode:
			self._exitCopyModeBindings()
		for gesture_id, script_name in _COMMAND_LAYER_MAP.items():
			try:
				self.bindGesture(gesture_id, script_name)
			except Exception:
				pass
		self._inCommandLayer = True
		tones.beep(880, 100)
		# Translators: Announced when the terminal command layer is activated
		ui.message(_("Terminal commands"))

	def _exitCommandLayer(self):
		"""Deactivate the command layer by removing all single-key gestures."""
		if not self._inCommandLayer:
			return
		for gesture_id in _COMMAND_LAYER_MAP:
			try:
				self.removeGestureBinding(gesture_id)
			except (KeyError, AttributeError):
				pass
		self._inCommandLayer = False
		tones.beep(440, 100)
		# Translators: Announced when the terminal command layer is deactivated
		ui.message(_("Exit terminal commands"))

	@script(
		# Translators: Description for exiting the command layer
		description=_("Exit the terminal command layer"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_exitCommandLayer(self, gesture):
		"""Exit the command layer (bound to Escape within the layer)."""
		if self._inCommandLayer:
			self._exitCommandLayer()
		else:
			gesture.send()

	@script(
		# Translators: Description for opening terminal settings
		description=_("Open Terminal Access settings"),
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+alt+y",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_cycleCursorTrackingMode(self, gesture):
		"""Cycle through cursor tracking modes: Off -> Standard -> Highlight -> Window -> Off."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Get current mode
		currentMode = self._getEffective("cursorTrackingMode")

		# Cycle to next mode
		nextMode = (currentMode + 1) % 4

		# Update configuration
		config.conf["terminalAccess"]["cursorTrackingMode"] = nextMode
		if self._currentProfile is not None and self._currentProfile.cursorTrackingMode is not None:
			self._currentProfile.cursorTrackingMode = nextMode

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
		gesture="kb:NVDA+alt+f2",
		category=SCRCAT_TERMINALACCESS,
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

			terminal = self._boundTerminal if self._boundTerminal else api.getForegroundObject()
			if not terminal:
				ui.message(_("Unable to set window"))
				return

			if not self._windowStartSet:
				# Set start position — calculate and store the row/col
				startRow, startCol = self._positionCalculator.calculate(reviewPos, terminal)
				self._windowStartBookmark = reviewPos.bookmark
				self._windowStartRow = startRow
				self._windowStartCol = startCol
				self._windowStartSet = True
				# Translators: Message when window start is set
				ui.message(_("Window start set. Move to end position and press again."))
			else:
				# Set end position — calculate row/col and store both corners
				endRow, endCol = self._positionCalculator.calculate(reviewPos, terminal)

				# Ensure top <= bottom and left <= right
				windowTop = min(self._windowStartRow, endRow)
				windowBottom = max(self._windowStartRow, endRow)
				windowLeft = min(self._windowStartCol, endCol)
				windowRight = max(self._windowStartCol, endCol)

				config.conf["terminalAccess"]["windowTop"] = windowTop
				config.conf["terminalAccess"]["windowBottom"] = windowBottom
				config.conf["terminalAccess"]["windowLeft"] = windowLeft
				config.conf["terminalAccess"]["windowRight"] = windowRight
				config.conf["terminalAccess"]["windowEnabled"] = True
				self._windowStartSet = False
				# Translators: Message when window is defined with coordinates
				ui.message(_("Window defined: rows {top}-{bottom}, columns {left}-{right}").format(
					top=windowTop, bottom=windowBottom, left=windowLeft, right=windowRight))
		except Exception:
			ui.message(_("Unable to set window"))
			self._windowStartSet = False

	@script(
		# Translators: Description for clearing screen window
		description=_("Clear screen window"),
		gesture="kb:NVDA+alt+f3",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+alt+plus",
		category=SCRCAT_TERMINALACCESS,
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
				self._brailleMessage(windowText)
			else:
				# Translators: Message when window contains no text
				ui.message(_("Window is empty"))

		except Exception:
			ui.message(_("Unable to read window"))

	@script(
		# Translators: Description for reading text attributes
		description=_("Read text attributes at cursor"),
		gesture="kb:NVDA+shift+a",
		category=SCRCAT_TERMINALACCESS,
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

			# Get text from line start to cursor, including the character at cursor
			textToCursor = lineStart.copy()
			cursorChar = reviewPos.copy()
			cursorChar.expand(textInfos.UNIT_CHARACTER)
			textToCursor.setEndPoint(cursorChar, "endToEnd")

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
		gesture="kb:NVDA+a",
		category=SCRCAT_TERMINALACCESS,
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
			self._brailleMessage(text)
		except Exception:
			# Translators: Message when continuous reading fails
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for jumping to start of line
		description=_("Move to first character of current line"),
		gesture="kb:NVDA+shift+home",
		category=SCRCAT_TERMINALACCESS,
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
				self._brailleMessage(char)
			else:
				# Translators: Message for blank line
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to end of line
		description=_("Move to last character of current line"),
		gesture="kb:NVDA+shift+end",
		category=SCRCAT_TERMINALACCESS,
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
				self._brailleMessage(char)
			else:
				# Translators: Message for blank line
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to top
		description=_("Move to top of terminal buffer"),
		gesture="kb:NVDA+f4",
		category=SCRCAT_TERMINALACCESS,
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
				self._brailleMessage(char)
			else:
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to bottom
		description=_("Move to bottom of terminal buffer"),
		gesture="kb:NVDA+f6",
		category=SCRCAT_TERMINALACCESS,
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
				self._brailleMessage(char)
			else:
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for announcing position
		description=_("Announce current row and column position"),
		gesture="kb:NVDA+;",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+f10",
		category=SCRCAT_TERMINALACCESS,
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
		shouldAnnounceIndentation = self._getEffective("indentationOnLineRead")

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
		reviewInfo = self._getReviewPosition()
		if reviewInfo is None:
			# Translators: Message when no review position
			ui.message(_("No review position"))
			return

		try:
			reviewInfo = reviewInfo.copy()
		except Exception:
			ui.message(_("Unable to read character"))
			return

		# Move review cursor if needed
		try:
			if movement != 0:
				lineInfo = reviewInfo.copy()
				lineInfo.expand(textInfos.UNIT_LINE)

				reviewInfo.expand(textInfos.UNIT_CHARACTER)
				reviewInfo.collapse()

				result = reviewInfo.move(textInfos.UNIT_CHARACTER, movement)
				isEdge = (
					result == 0
					or (movement > 0 and reviewInfo.compareEndPoints(lineInfo, "endToEnd") >= 0)
					or (movement < 0 and reviewInfo.compareEndPoints(lineInfo, "startToStart") <= 0)
				)
				if isEdge:
					# Translators: Message when at edge of text
					ui.message(_("Edge") if movement > 0 else _("Top"))
					return

				api.setReviewPosition(reviewInfo)

			reviewInfo.expand(textInfos.UNIT_CHARACTER)
			charText = reviewInfo.text
		except Exception:
			ui.message(_("Unable to read character"))
			return

		if not charText:
			ui.message(_("Unable to read character"))
			return

		if phonetic:
			try:
				speech.speakSpelling(charText)
			except Exception:
				ui.message(charText)
			return

		speak_kwargs = {"unit": textInfos.UNIT_CHARACTER}
		try:
			speak_reason = speech.OutputReason.CARET
			speak_kwargs["reason"] = speak_reason
		except Exception:
			# Older/limited speech modules may not expose OutputReason
			pass

		try:
			speech.speakTextInfo(reviewInfo, **speak_kwargs)
		except Exception:
			ui.message(charText)
		self._brailleMessage(charText)

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

		Uses a cached punctuation set so the dict lookup only occurs when the
		level actually changes (rare), rather than on every character.

		Args:
			char: The character to check.

		Returns:
			bool: True if the symbol should be announced, False otherwise.
		"""
		level = self._getEffective("punctuationLevel")

		if level == PUNCT_ALL:
			return True
		if level == PUNCT_NONE:
			return False

		# Refresh cached set only when the level has changed.
		if level != self._cachedPunctLevel:
			self._cachedPunctLevel = level
			self._cachedPunctSet = PUNCTUATION_SETS.get(level, set())

		return char in self._cachedPunctSet

	def _processSymbol(self, char):
		"""
		Return a human-friendly, locale-aware name for a symbol.

		Uses NVDA's character processing to respect the user's configured
		language.  Falls back to the Unicode character name if no locale
		mapping exists.
		"""
		locale = languageHandler.getLanguage()
		return _get_symbol_description(locale, char)

	def _resolveSymbol(self, char):
		"""Return the spoken form of *char* respecting the punctuation level.

		If the current punctuation level includes *char*, returns a
		locale-aware symbol name via ``_processSymbol``.  Otherwise returns
		*char* unchanged.
		"""
		if self._shouldProcessSymbol(char):
			return self._processSymbol(char)
		return char

	def _speakCharacter(self, char):
		"""Speak a single character, handling space and blank specially."""
		if char == ' ':
			ui.message(_("space"))
		elif not char or char in ('\r', '\n'):
			ui.message(_("Blank"))
		elif char.strip():
			ui.message(self._resolveSymbol(char))

	@script(
		# Translators: Description for decreasing punctuation level
		description=_("Decrease punctuation level"),
		gesture="kb:NVDA+[",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_decreasePunctuationLevel(self, gesture):
		"""Decrease the punctuation level (wraps from 0 to 3)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentLevel = self._getEffective("punctuationLevel")
		newLevel = (currentLevel - 1) % 4
		config.conf["terminalAccess"]["punctuationLevel"] = newLevel
		if self._currentProfile is not None and self._currentProfile.punctuationLevel is not None:
			self._currentProfile.punctuationLevel = newLevel

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
		gesture="kb:NVDA+]",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_increasePunctuationLevel(self, gesture):
		"""Increase the punctuation level (wraps from 3 to 0)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentLevel = self._getEffective("punctuationLevel")
		newLevel = (currentLevel + 1) % 4
		config.conf["terminalAccess"]["punctuationLevel"] = newLevel
		if self._currentProfile is not None and self._currentProfile.punctuationLevel is not None:
			self._currentProfile.punctuationLevel = newLevel

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
		gesture="kb:NVDA+shift+leftArrow",
		category=SCRCAT_TERMINALACCESS,
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
			lineInfo.setEndPoint(reviewPos, "endToEnd")

			text = lineInfo.text
			if not text or not text.strip():
				# Translators: Message when region is empty
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
			self._brailleMessage(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to right edge
		description=_("Read from cursor to end of line"),
		gesture="kb:NVDA+shift+rightArrow",
		category=SCRCAT_TERMINALACCESS,
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
			self._brailleMessage(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to top
		description=_("Read from cursor to top of buffer"),
		gesture="kb:NVDA+shift+upArrow",
		category=SCRCAT_TERMINALACCESS,
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
			startInfo.setEndPoint(reviewPos, "endToEnd")

			text = startInfo.text
			if not text or not text.strip():
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
			self._brailleMessage(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to bottom
		description=_("Read from cursor to bottom of buffer"),
		gesture="kb:NVDA+shift+downArrow",
		category=SCRCAT_TERMINALACCESS,
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
			self._brailleMessage(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for toggling mark position
		description=_("Toggle mark for selection (enhanced)"),
		gesture="kb:NVDA+r",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+c",
		category=SCRCAT_TERMINALACCESS,
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
		gesture="kb:NVDA+shift+c",
		category=SCRCAT_TERMINALACCESS,
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
		# Bulk-read all needed lines — uses helper process if available,
		# otherwise marshals to the main thread in a single call.
		raw_lines = _read_lines(terminal, startRow, endRow)
		if raw_lines is None:
			if threading.current_thread() != threading.main_thread():
				wx.CallAfter(ui.message, _("Background copy failed"))
			else:
				ui.message(_("Background copy failed"))
			return

		# Calculate total rows for progress tracking
		totalRows = len(raw_lines)

		# Process each line (column slicing — no UIA needed)
		lines = []
		for idx, lineText in enumerate(raw_lines):
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

			lineText = lineText.rstrip('\n\r')

			# Strip ANSI codes for accurate column extraction
			cleanText = _strip_ansi(lineText)

			# Extract column range using Unicode-aware helper (1-based columns)
			columnText = UnicodeWidthHelper.extractColumnRange(cleanText, startCol, endCol)

			lines.append(columnText)

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
		gesture="kb:NVDA+x",
		category=SCRCAT_TERMINALACCESS,
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
		gestures=["kb:NVDA+alt+0", "kb:NVDA+alt+1", "kb:NVDA+alt+2",
		          "kb:NVDA+alt+3", "kb:NVDA+alt+4", "kb:NVDA+alt+5",
		          "kb:NVDA+alt+6", "kb:NVDA+alt+7", "kb:NVDA+alt+8",
		          "kb:NVDA+alt+9"]
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
		gestures=["kb:alt+0", "kb:alt+1", "kb:alt+2",
		          "kb:alt+3", "kb:alt+4", "kb:alt+5",
		          "kb:alt+6", "kb:alt+7", "kb:alt+8", "kb:alt+9"]
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
		gesture="kb:NVDA+shift+b"
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
		gesture="kb:NVDA+shift+t"
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
		gesture="kb:NVDA+w"
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
		gesture="kb:NVDA+shift+h"
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
		gesture="kb:NVDA+h"
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
		gesture="kb:NVDA+g"
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
		gesture="kb:NVDA+shift+l"
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

	# Section 8.4: URL extraction and navigation (v1.2.0+)

	@script(
		# Translators: Description for listing URLs in terminal output
		description=_("List URLs found in terminal output"),
		gesture="kb:NVDA+alt+u",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_listUrls(self, gesture):
		"""List and interact with URLs found in terminal output."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Prevent multiple dialog instances
		if self._urlDialogOpen:
			# Translators: Announced when URL list dialog is already open
			ui.message(_("URL list already open"))
			return

		if not self._urlExtractorManager:
			# Translators: Error when URL extractor not ready
			ui.message(_("URL list not available"))
			return

		try:
			urls = self._urlExtractorManager.extract_urls()
		except Exception:
			try:
				import logHandler
				logHandler.log.error("URL extraction failed", exc_info=True)
			except Exception:
				pass
			# Translators: Error when URL extraction fails
			ui.message(_("Error extracting URLs"))
			return

		if not urls:
			# Translators: Announced when no URLs found
			ui.message(_("No URLs found"))
			return

		# Translators: Announced when URL list is loading with count of URLs found
		ui.message(_("{count} URLs found").format(count=len(urls)))
		self._urlDialogOpen = True

		def show_url_dialog():
			try:
				gui.mainFrame.prePopup()
				dlg = UrlListDialog(gui.mainFrame, urls, self._urlExtractorManager)
				dlg.ShowModal()
				dlg.Destroy()
			except Exception:
				try:
					import logHandler
					logHandler.log.error("URL list dialog failed", exc_info=True)
				except Exception:
					pass
				# Translators: Error when URL dialog fails to open
				ui.message(_("Error opening URL list"))
			finally:
				gui.mainFrame.postPopup()
				self._urlDialogOpen = False

		wx.CallAfter(show_url_dialog)

	# Section 8.2: Output search functionality gestures (v1.0.30+)

	@scriptHandler.script(
		# Translators: Description for searching output
		description=_("Search terminal output for text pattern"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+f"
	)
	def script_searchOutput(self, gesture):
		"""Search terminal output."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Prevent multiple dialog instances
		if self._searchDialogOpen:
			# Translators: Announced when search dialog is already open
			ui.message(_("Search already open"))
			return

		if not self._searchManager:
			# Translators: Error message when search manager not initialized
			ui.message(_("Search not available"))
			return

		# Prompt for search text using wx dialog
		import wx
		self._searchDialogOpen = True

		def show_search_dialog():
			"""Show search dialog."""
			try:
				gui.mainFrame.prePopup()
				dlg = wx.TextEntryDialog(
					gui.mainFrame,
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
			except Exception:
				try:
					import logHandler
					logHandler.log.error("Search dialog failed", exc_info=True)
				except Exception:
					pass
			finally:
				gui.mainFrame.postPopup()
				self._searchDialogOpen = False

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
			ui.message(_("No search results. Use NVDA+F to search."))
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
			ui.message(_("No search results. Use NVDA+F to search."))
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
		profileManager = self._getProfileManager()

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
			"Use NVDA+[ and ] to adjust quickly."
		))

		# Quiet mode checkbox
		# Translators: Label for quiet mode checkbox
		self.quietModeCheckBox = feedbackGroup.addItem(
			wx.CheckBox(self, label=_("&Quiet mode"))
		)
		self.quietModeCheckBox.SetValue(config.conf["terminalAccess"]["quietMode"])
		# Translators: Tooltip for quiet mode
		self.quietModeCheckBox.SetToolTip(_(
			"Suppress most Terminal Access announcements. Use NVDA+Shift+Q to toggle quickly."
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
			"Use NVDA+F5 to toggle quickly. NVDA+I pressed twice still reads indentation."
		))

		# === Announce New Output Section ===
		# Translators: Label for the announce new output group
		newOutputGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Announce New Output")),
			wx.VERTICAL
		))
		sHelper.addItem(newOutputGroup)

		# Announce new output master toggle
		# Translators: Label for announce new output checkbox
		self.announceNewOutputCheckBox = newOutputGroup.addItem(
			wx.CheckBox(self, label=_("&Announce new terminal output automatically"))
		)
		self.announceNewOutputCheckBox.SetValue(config.conf["terminalAccess"]["announceNewOutput"])
		# Translators: Tooltip for announce new output
		self.announceNewOutputCheckBox.SetToolTip(_(
			"Automatically speak newly appended terminal output as it arrives. "
			"Use NVDA+Shift+N to toggle quickly."
		))

		# Coalesce delay spinner
		# Translators: Label for coalesce delay spinner
		self.newOutputCoalesceSpinner = newOutputGroup.addLabeledControl(
			_("&Coalesce delay (ms):"),
			wx.SpinCtrl,
			min=50, max=2000
		)
		self.newOutputCoalesceSpinner.SetValue(config.conf["terminalAccess"]["newOutputCoalesceMs"])
		# Translators: Tooltip for coalesce delay
		self.newOutputCoalesceSpinner.SetToolTip(_(
			"Milliseconds to wait before announcing accumulated new output. "
			"Larger values reduce interruptions during fast output."
		))

		# Max lines spinner
		# Translators: Label for max lines spinner
		self.newOutputMaxLinesSpinner = newOutputGroup.addLabeledControl(
			_("&Max lines before summarising:"),
			wx.SpinCtrl,
			min=1, max=200
		)
		self.newOutputMaxLinesSpinner.SetValue(config.conf["terminalAccess"]["newOutputMaxLines"])
		# Translators: Tooltip for max lines
		self.newOutputMaxLinesSpinner.SetToolTip(_(
			"When more than this many lines arrive at once, speak a summary "
			"('N new lines') instead of the full text."
		))

		# Strip ANSI checkbox
		# Translators: Label for strip ANSI checkbox
		self.stripAnsiInOutputCheckBox = newOutputGroup.addItem(
			wx.CheckBox(self, label=_("&Strip ANSI escape codes from output"))
		)
		self.stripAnsiInOutputCheckBox.SetValue(config.conf["terminalAccess"]["stripAnsiInOutput"])
		# Translators: Tooltip for strip ANSI
		self.stripAnsiInOutputCheckBox.SetToolTip(_(
			"Remove ANSI colour and formatting codes before speaking new output."
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
		if currentDefault and profileManager and currentDefault in profileManager.profiles:
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
			"Use NVDA+F10 to check which profile is active."
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

		# === Direct Gesture Bindings Section ===
		# Translators: Label for direct gesture bindings settings group
		gestureGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Direct Gesture Bindings")),
			wx.VERTICAL
		))
		sHelper.addItem(gestureGroup)

		# Build ordered list of bindable gestures (excluding always-bound)
		self._gestureItems = [
			(g, s) for g, s in sorted(_DEFAULT_GESTURES.items(), key=lambda x: x[1])
			if g not in _ALWAYS_BOUND
		]
		labels = [_gestureLabel(g, s) for g, s in self._gestureItems]

		# Translators: Label for gesture bindings checklist
		self.gestureCheckList = gestureGroup.addItem(
			wx.CheckListBox(self, choices=labels, size=(-1, 200))
		)

		# Read current exclusion list from config and check appropriate items
		try:
			raw = config.conf["terminalAccess"]["unboundGestures"]
		except (KeyError, TypeError):
			raw = ""
		excluded = set(g.strip() for g in raw.split(",") if g.strip())
		for i, (gesture, _) in enumerate(self._gestureItems):
			self.gestureCheckList.Check(i, gesture not in excluded)

		# Translators: Help text for gesture bindings
		gestureGroup.addItem(
			wx.StaticText(self, label=_(
				"Unchecked gestures are disabled. Use the command layer (NVDA+') to access them.\n"
				"NVDA+' (Command Layer) and NVDA+Shift+F1 (Help) are always available."
			))
		)

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
			config.conf["terminalAccess"]["announceNewOutput"] = False
			config.conf["terminalAccess"]["newOutputCoalesceMs"] = 200
			config.conf["terminalAccess"]["newOutputMaxLines"] = 20
			config.conf["terminalAccess"]["stripAnsiInOutput"] = True
			self.announceNewOutputCheckBox.SetValue(False)
			self.newOutputCoalesceSpinner.SetValue(200)
			self.newOutputMaxLinesSpinner.SetValue(20)
			self.stripAnsiInOutputCheckBox.SetValue(True)
			config.conf["terminalAccess"]["unboundGestures"] = ""
			# Check all items in the gesture checklist (re-enable all gestures)
			for i in range(self.gestureCheckList.GetCount()):
				self.gestureCheckList.Check(i, True)

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
		config.conf["terminalAccess"]["announceNewOutput"] = self.announceNewOutputCheckBox.GetValue()
		config.conf["terminalAccess"]["stripAnsiInOutput"] = self.stripAnsiInOutputCheckBox.GetValue()

		# Validate and save new output coalesce/max-lines settings
		config.conf["terminalAccess"]["newOutputCoalesceMs"] = _validateInteger(
			self.newOutputCoalesceSpinner.GetValue(), 50, 2000, 200, "newOutputCoalesceMs"
		)
		config.conf["terminalAccess"]["newOutputMaxLines"] = _validateInteger(
			self.newOutputMaxLinesSpinner.GetValue(), 1, 200, 20, "newOutputMaxLines"
		)

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

		# Save gesture exclusions
		unchecked = []
		for i, (gesture, _) in enumerate(self._gestureItems):
			if not self.gestureCheckList.IsChecked(i):
				unchecked.append(gesture)
		config.conf["terminalAccess"]["unboundGestures"] = ",".join(unchecked)

		# Live-reload gesture bindings
		try:
			for plugin in globalPluginHandler.runningPlugins:
				if isinstance(plugin, GlobalPlugin):
					plugin._reloadGestures()
					break
		except (StopIteration, Exception):
			pass

	def _getProfileManager(self):
		"""Return the shared ProfileManager from the running global plugin, if available."""
		try:
			from . import terminalAccess
			for plugin in globalPluginHandler.runningPlugins:
				if isinstance(plugin, terminalAccess.GlobalPlugin):
					return getattr(plugin, "_profileManager", None)
		except Exception:
			return None
		return None

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
