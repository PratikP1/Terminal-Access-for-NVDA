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

import os
import sys

# Add the addon root directory to sys.path so that lib/ and native/
# packages are importable.  NVDA only adds globalPlugins/ to the path.
_addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _addon_dir not in sys.path:
	sys.path.insert(0, _addon_dir)

import globalPluginHandler
import api
import ui
import config
import gui
import textInfos
import addonHandler
import wx
import re
import time
import threading
import webbrowser
from scriptHandler import script
import scriptHandler
import globalCommands
import speech
import languageHandler
import tones

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
	"kb:shift+c": "copyRectangularSelection",  # DEPRECATED: Scheduled for removal in v2.0
	"kb:x": "clearMarks",
	"kb:v": "copyMode",
	# Window management
	"kb:w": "readWindow",
	"kb:shift+w": "setWindow",
	"kb:control+w": "clearWindow",
	"kb:y": "cycleCursorTrackingMode",
	# Configuration
	"kb:q": "toggleQuietMode",
	"kb:-": "decreasePunctuationLevel",
	"kb:=": "increasePunctuationLevel",
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
	"kb:shift+s": "listSections",
	# Tab management
	"kb:t": "createNewTab",
	"kb:shift+t": "listTabs",
	# DEPRECATED: Scheduled for removal in v2.0 — Command history
	"kb:h": "previousCommand",  # DEPRECATED: Scheduled for removal in v2.0
	"kb:g": "nextCommand",  # DEPRECATED: Scheduled for removal in v2.0
	"kb:shift+h": "scanCommandHistory",  # DEPRECATED: Scheduled for removal in v2.0
	"kb:shift+l": "listCommandHistory",  # DEPRECATED: Scheduled for removal in v2.0
	# Search
	"kb:f": "searchOutput",
	"kb:f3": "findNext",
	"kb:shift+f3": "findPrevious",
	# Help & settings
	"kb:f1": "showHelp",
	"kb:s": "openSettings",
	"kb:shift+f1": "checkGestureConflicts",
	# URL list (elements)
	"kb:e": "listUrls",
	# Summarization
	"kb:z": "summarizeLastCommand",
	"kb:shift+z": "summarizeSelection",
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
	"kb:NVDA+-": "decreasePunctuationLevel",
	"kb:NVDA+=": "increasePunctuationLevel",
	"kb:NVDA+shift+leftArrow": "readToLeft",
	"kb:NVDA+shift+rightArrow": "readToRight",
	"kb:NVDA+shift+upArrow": "readToTop",
	"kb:NVDA+shift+downArrow": "readToBottom",
	"kb:NVDA+r": "toggleMark",
	"kb:NVDA+c": "copyLinearSelection",
	"kb:NVDA+shift+c": "copyRectangularSelection",  # DEPRECATED: Scheduled for removal in v2.0
	"kb:NVDA+x": "clearMarks",
	"kb:NVDA+shift+b": "listBookmarks",
	"kb:NVDA+shift+t": "createNewTab",
	"kb:NVDA+w": "listTabs",
	"kb:NVDA+shift+h": "scanCommandHistory",  # DEPRECATED: Scheduled for removal in v2.0
	"kb:NVDA+h": "previousCommand",  # DEPRECATED: Scheduled for removal in v2.0
	"kb:NVDA+g": "nextCommand",  # DEPRECATED: Scheduled for removal in v2.0
	"kb:NVDA+shift+l": "listCommandHistory",  # DEPRECATED: Scheduled for removal in v2.0
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
	# Summarization
	"kb:NVDA+alt+s": "summarizeLastCommand",
	"kb:NVDA+alt+shift+s": "summarizeSelection",
}

# Gestures that are always active regardless of context.
# All other gestures are bound (visible in Input Gestures dialog) but
# getScript() returns None for them outside terminals, so NVDA's own
# handlers process the keystroke instead.
_ALWAYS_BOUND = frozenset({"kb:NVDA+'", "kb:NVDA+shift+f1"})

# Gestures that conflict with NVDA's default global commands.
# Only these appear in the Terminal Settings checklist for users to
# disable. All other gesture customization goes through NVDA's
# Input Gestures dialog.
_CONFLICTING_GESTURES = frozenset({
	"kb:NVDA+f",           # NVDA: report text formatting
	"kb:NVDA+f3",          # NVDA: find next in document
	"kb:NVDA+shift+f3",    # NVDA: find previous in document
	"kb:NVDA+f5",          # NVDA: reload document
	"kb:NVDA+f10",         # NVDA: select then copy to review cursor
	"kb:NVDA+m",           # NVDA: toggle mouse tracking
	"kb:NVDA+k",           # NVDA: report link destination
	"kb:NVDA+k,kb:NVDA+k", # NVDA: report link destination (double press)
	"kb:NVDA+x",           # NVDA: repeat last speech
	"kb:NVDA+shift+b",     # NVDA: report battery status
	"kb:NVDA+shift+upArrow",  # NVDA: report selection
	"kb:NVDA+c",              # NVDA: read clipboard contents
})


from lib._runtime import gesture_label as _gestureLabel


def _message_thread_safe(message):
	"""Announce a message, dispatching to the main thread if needed."""
	if threading.current_thread() != threading.main_thread():
		wx.CallAfter(ui.message, message)
	else:
		ui.message(message)


# Cursor tracking mode constants
# Config classes extracted to lib.config
from lib.config import (
	ConfigManager, confspec, _validateInteger, _validateString, _validateSelectionSize,
	CT_OFF, CT_STANDARD, CT_HIGHLIGHT, CT_WINDOW,
	PUNCT_NONE, PUNCT_SOME, PUNCT_MOST, PUNCT_ALL,
	PUNCTUATION_SETS,
	MAX_SELECTION_ROWS, MAX_SELECTION_COLS, MAX_WINDOW_DIMENSION, MAX_REPEATED_SYMBOLS_LENGTH,
)

# Register configuration
config.conf.spec["terminalAccess"] = confspec

# Profile classes extracted to lib.profiles
from lib.profiles import (
	WindowDefinition, ApplicationProfile, ProfileManager,
	_SUPPORTED_TERMINALS, _NON_TERMINAL_APPS,
	_BUILTIN_PROFILE_NAMES, _ANSI_STRIPPING_TERMINALS,
)

# Compiled regex for stripping ANSI highlight codes

# Human-readable punctuation level names (used by _changePunctuationLevel)
_PUNCT_LEVEL_NAMES = {
	PUNCT_NONE: _("Punctuation level none"),
	PUNCT_SOME: _("Punctuation level some"),
	PUNCT_MOST: _("Punctuation level most"),
	PUNCT_ALL: _("Punctuation level all"),
}

# Search-related constants and classes extracted to lib.search
from lib.search import (
	OutputSearchManager, CommandHistoryManager, UrlExtractorManager, UrlListDialog,
	_OSC8_URL_PATTERN, _URL_PATTERN, _clean_url,
)


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


# Text processing classes extracted to lib.text_processing
from lib.text_processing import (
	ANSIParser, UnicodeWidthHelper, BidiHelper, EmojiHelper,
	ErrorLineDetector,
	_get_symbol_description,
)


# Caching classes extracted to lib.caching
from lib.caching import PositionCache, TextDiffer

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


def _strip_ansi_fallback(text: str) -> str:
	"""Strip ANSI escape sequences using the Python regex fallback."""
	return ANSIParser.stripANSI(text)


if _native_available:
	def _strip_ansi(text: str) -> str:
		"""Strip ANSI escape sequences using the native Rust implementation."""
		try:
			return _native_strip_ansi(text)
		except Exception:
			return ANSIParser.stripANSI(text)
else:
	_strip_ansi = _strip_ansi_fallback

# Populate runtime dependency registry (must be after _strip_ansi is defined)
import lib._runtime as _rt
_rt.strip_ansi = _strip_ansi
_rt.get_helper = _get_helper
_rt.read_terminal_text = _read_terminal_text
_rt.native_available = _native_available
_rt.make_text_differ = _make_text_differ
_rt.make_position_cache = _make_position_cache
try:
	_rt.native_search_text = _native_search_text
except NameError:
	pass
_rt.api_module = api
_rt.webbrowser_module = webbrowser


# Window management classes extracted to lib.window_management
from lib.window_management import WindowManager, PositionCalculator, WindowMonitor



# Operations classes extracted to lib.operations
from lib.operations import SelectionProgressDialog, OperationQueue


# Navigation classes extracted to lib.navigation
from lib.navigation import TabManager, BookmarkManager
from lib.gesture_conflicts import GestureConflictDetector
from lib.section_tokenizer import SectionTokenizer
from lib.summarizer import OutputSummarizer

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
		NVDA+Alt+C       - Copy linear selection (between marks)
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
		NVDA+-           - Decrease punctuation level
		NVDA+=           - Increase punctuation level
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
	- Punctuation: Minus/equals keys (- and =)

	==== CURSOR TRACKING MODES ====
	0 - Off: No automatic tracking
	1 - Standard: Follow system caret
	2 - Highlight: Track highlighted/selected text
	3 - Window: Track within defined screen region
	"""

	# Grace period (seconds) after a keystroke during which "Blank"
	# announcements from cursor tracking are suppressed.  Keeps terminal
	# output responsive without masking navigation feedback.
	_BLANK_AFTER_TYPING_GRACE: float = 0.3

	# Class-level gesture map: ALL gestures are bound so they appear in
	# NVDA's Input Gestures dialog under the Terminal Access category.
	# getScript() returns None for terminal-specific gestures outside
	# terminals, so NVDA's own handlers process those keystrokes.
	__gestures = _DEFAULT_GESTURES

	# Track which deprecation warnings have been shown this session
	_deprecation_warned = set()

	def __init__(self):
		"""Initialize the Terminal Access global plugin."""
		super().__init__()
		self._initState()
		self._initManagers()
		self._initBindings()

	def _initState(self):
		"""Initialize plugin state variables."""
		self.lastTerminalAppName = None
		self.announcedHelp = False
		self.copyMode = False
		self._inCommandLayer = False
		self._boundTerminal = None
		self._searchJumpPending = False
		self._bookmarkJumpPending = False
		self._cursorTrackingTimer = None
		self._lastCaretPosition = None
		self._lastTypedChar = None
		self._repeatedCharCount = 0
		self._lastTypedCharTime: float = 0.0
		self._lastOutputActivityTime: float = 0.0

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

		# _terminalStripsAnsi cache — maps appName (str) to bool result so
		# the _ANSI_STRIPPING_TERMINALS scan runs only once per app name.
		self._stripsAnsiCache: dict[str, bool] = {}

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

		# Dialog guard flags
		self._searchDialogOpen = False
		self._urlDialogOpen = False

	def _initManagers(self):
		"""Initialize feature managers (lazy — populated on first terminal focus)."""
		self._configManager = ConfigManager()
		self._windowManager = WindowManager(self._configManager)
		self._positionCalculator = PositionCalculator()

		# Background calculation thread for long operations
		self._backgroundCalculationThread = None

		# Operation queue to prevent overlapping background operations
		self._operationQueue = OperationQueue()

		# Application profile management
		self._profileManager = ProfileManager()
		self._currentProfile = None

		# Lazy-start managers — initialized when terminal is bound
		self._windowMonitor = None
		self._tabManager = None
		self._bookmarkManager = None
		self._searchManager = None
		self._commandHistoryManager = None
		self._urlExtractorManager = None

		# Error/warning line detector for audio cues during line navigation
		self._errorDetector = ErrorLineDetector()

		# Section tokenizer for semantic navigation
		self._sectionTokenizer = SectionTokenizer()

		# Extractive summarizer for terminal output
		self._outputSummarizer = OutputSummarizer()

		# Gesture conflict detection
		self._conflictDetector = GestureConflictDetector()

		# Helper process is started lazily on first terminal focus
		# (in _startHelperIfNeeded). Eager startup during __init__ was
		# removed because subprocess.Popen and named pipe connection
		# acquire the GIL, causing NVDA to freeze for several seconds
		# during restart.

	def _initBindings(self):
		"""Set up gesture bindings and settings panel registration."""
		# All gestures are bound so they appear in NVDA's Input Gestures
		# dialog. getScript() returns None for terminal-specific gestures
		# outside terminals, letting NVDA's own handlers process them.
		self.bindGestures(_DEFAULT_GESTURES)
		self._applyGestureExclusions()

		# Detect whether the foreground is already a terminal
		try:
			self._updateGestureBindingsForFocus(api.getForegroundObject())
		except (AttributeError, TypeError, RuntimeError):
			pass

		# Add settings panel to NVDA preferences
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(_get_settings_panel_class())
		except (AttributeError, TypeError, RuntimeError, ImportError):
			# GUI may not be fully initialized yet, which is acceptable
			pass

	def _getExcludedGestures(self) -> set[str]:
		"""Return the set of user-excluded gestures from config."""
		raw = self._configManager.get("unboundGestures", "")
		return {g.strip() for g in raw.split(",") if g.strip()} - _ALWAYS_BOUND

	def _applyGestureExclusions(self):
		"""Remove user-excluded gestures from the gesture map."""
		for gesture in self._getExcludedGestures():
			try:
				self.removeGestureBinding(gesture)
			except (KeyError, AttributeError):
				pass

	def _reloadGestures(self):
		"""Rebuild gesture bindings from current config (called after settings change)."""
		self.bindGestures(_DEFAULT_GESTURES)
		self._applyGestureExclusions()

	def getScript(self, gesture):
		"""Return the script for a gesture, or None if not in a terminal.

		All gestures stay in _gestureMap so NVDA's Input Gestures dialog
		shows them under Terminal Access. But outside terminals, this
		method returns None for terminal-specific gestures. NVDA then
		checks its next handler (globalCommands), so native commands
		like NVDA+L (read current line) work normally.

		Uses _boundTerminal (set by event_gainFocus) rather than calling
		isTerminalApp() on every keystroke. This avoids redundant foreground
		object lookups and ensures consistent state with the event system.
		"""
		script = super().getScript(gesture)
		if script is None:
			return None
		# Always-active gestures work everywhere
		for identifier in gesture.normalizedIdentifiers:
			if identifier in _ALWAYS_BOUND:
				return script
		# Terminal-specific gestures only work when a terminal has focus.
		# _boundTerminal is set by event_gainFocus and cleared on focus loss.
		if self._boundTerminal is not None:
			return script
		return None

	def _updateGestureBindingsForFocus(self, obj) -> bool:
		"""Handle focus changes between terminal and non-terminal windows.

		Gestures stay bound (visible in Input Gestures dialog) but
		getScript() returns None outside terminals. This method handles
		command layer auto-exit on focus loss.
		"""
		if self.isTerminalApp(obj):
			return True
		# Exit command layer silently when focus leaves terminal
		if getattr(self, "_inCommandLayer", False):
			self._exitCommandLayer()
		if getattr(self, "copyMode", False):
			self._exitCopyModeBindings()
			self.copyMode = False
		return False

	def terminate(self):
		"""Clean up when the plugin is terminated."""
		# Stop window monitoring if active
		if self._windowMonitor and self._windowMonitor.is_monitoring():
			self._windowMonitor.stop_monitoring()

		# Stop the native helper process on a background thread to avoid
		# blocking NVDA shutdown. The helper's stop() method waits up to
		# 7 seconds for the process to exit, which freezes NVDA's restart.
		def _stop_helper_background():
			try:
				_stop_helper()
			except (OSError, RuntimeError):
				pass
		threading.Thread(target=_stop_helper_background, daemon=True).start()

		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(_get_settings_panel_class())
		except (ValueError, AttributeError):
			pass
		super().terminate()

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		"""Insert TerminalAccessTerminal overlay for terminal NVDAObjects.

		Called by NVDA when building the class list for a new NVDAObject.
		If the object belongs to a supported terminal, we insert our
		overlay at position 0 so its methods (event_textChange,
		_reportNewLines) take priority over NVDA's LiveText defaults.
		"""
		from lib.terminal_overlay import TerminalAccessTerminal, should_apply_overlay
		try:
			appName = obj.appModule.appName
		except AttributeError:
			return
		if not should_apply_overlay(appName):
			return
		if TerminalAccessTerminal in clsList:
			return
		clsList.insert(0, TerminalAccessTerminal)

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

		# Cache lookup — avoids repeated set lookups on every event.
		cached = self._terminalAppCache.get(appName)
		if cached is not None:
			return cached

		# Exact match against the supported terminals set.
		# Using set membership (O(1)) instead of substring scanning.
		# The exclusion list is checked first as a safety net for edge cases
		# where an app name exactly matches a terminal name but is not one.
		if appName in _NON_TERMINAL_APPS:
			self._terminalAppCache[appName] = False
			return False

		result = appName in _SUPPORTED_TERMINALS
		self._terminalAppCache[appName] = result
		return result

	def _terminalStripsAnsi(self, obj=None) -> bool:
		"""Return True if the terminal's UIA provider strips ANSI escape codes.

		Modern GPU-accelerated terminals (Windows Terminal, Alacritty, WezTerm,
		Ghostty, etc.) return clean text from UIA — checking for raw ANSI codes
		like ``\\x1b[7m`` will never succeed and just wastes a UNIT_LINE read.

		Results are cached per appName in ``_stripsAnsiCache``.
		"""
		if obj is None:
			obj = self._boundTerminal
		if obj is None:
			return False
		try:
			appName = obj.appModule.appName.lower()
		except (AttributeError, TypeError):
			return False
		cached = self._stripsAnsiCache.get(appName)
		if cached is not None:
			return cached
		result = appName in _ANSI_STRIPPING_TERMINALS
		self._stripsAnsiCache[appName] = result
		return result

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
		except (AttributeError, TypeError, RuntimeError):
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
				except (AttributeError, TypeError):
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
		"""Handle focus gain events."""
		nextHandler()
		if not self._updateGestureBindingsForFocus(obj):
			self._boundTerminal = None
			return
		self._onTerminalFocus(obj)

	def _onTerminalFocus(self, obj):
		"""Handle focus on a terminal window."""
		try:
			appName = obj.appModule.appName
		except (AttributeError, TypeError):
			return
		self._boundTerminal = obj
		self._startHelperIfNeeded()
		self._handleSearchJumpSuppression(obj)
		self._initializeManagers(obj)
		self._positionCalculator.clear_cache()
		self._detectAndApplyProfile(obj)
		self._announceProfileIfNew(obj, appName)
		self._bindReviewCursor(obj)
		self._wireOverlayConfig(obj)
		self._announceHelpIfNeeded(appName)

	def _startHelperIfNeeded(self):
		"""Lazy-start the native helper process (no-op if already running)."""
		try:
			_get_helper()
		except (OSError, RuntimeError):
			pass

	def _handleSearchJumpSuppression(self, obj):
		"""After a search or bookmark jump, skip navigator reset so review cursor stays on target."""
		if self._searchJumpPending:
			self._searchJumpPending = False
		elif self._bookmarkJumpPending:
			self._bookmarkJumpPending = False
		else:
			api.setNavigatorObject(obj)

	def _initializeManagers(self, obj):
		"""Initialize or update all feature managers for the terminal."""
		managers = [
			('_tabManager', TabManager, lambda: (obj,), {}),
			('_bookmarkManager', BookmarkManager, lambda: (obj, self._tabManager), {}),
			('_searchManager', OutputSearchManager, lambda: (obj, self._tabManager), {}),
			('_commandHistoryManager', CommandHistoryManager, lambda: (obj,), {'max_history': 100, 'tab_manager': self._tabManager}),
			('_urlExtractorManager', UrlExtractorManager, lambda: (obj, self._tabManager), {}),
		]
		for attr, cls, args_fn, kwargs in managers:
			current = getattr(self, attr, None)
			if not current:
				setattr(self, attr, cls(*args_fn(), **kwargs))
			else:
				current.update_terminal(obj)

	def _wireOverlayConfig(self, obj):
		"""Pass the config manager to the overlay if present on the object."""
		from lib.terminal_overlay import TerminalAccessTerminal
		if isinstance(obj, TerminalAccessTerminal):
			obj._configManager = self._configManager

	def _detectAndApplyProfile(self, obj):
		"""Detect and activate the appropriate application profile."""
		detectedApp = self._profileManager.detect_application(obj)
		if detectedApp != 'default':
			profile = self._profileManager.get_profile(detectedApp)
			if profile:
				self._currentProfile = profile
		else:
			defaultProfileName = self._configManager.get("defaultProfile", "")
			if defaultProfileName and defaultProfileName in self._profileManager.profiles:
				self._currentProfile = self._profileManager.get_profile(defaultProfileName)
			else:
				self._currentProfile = None

	def _announceProfileIfNew(self, obj, appName):
		"""Announce the active profile when switching to a new terminal app."""
		if appName == self.lastTerminalAppName:
			return
		if self._currentProfile:
			ui.message(self._currentProfile.displayName)

	def _bindReviewCursor(self, obj):
		"""Bind the review cursor to the terminal."""
		try:
			info = obj.makeTextInfo(textInfos.POSITION_CARET)
			api.setReviewPosition(info)
		except (RuntimeError, AttributeError, TypeError, NotImplementedError):
			try:
				info = obj.makeTextInfo(textInfos.POSITION_LAST)
				api.setReviewPosition(info)
			except (RuntimeError, AttributeError, TypeError, NotImplementedError):
				pass

	def _announceHelpIfNeeded(self, appName):
		"""Announce help availability on first focus to a terminal."""
		if not self.announcedHelp or appName != self.lastTerminalAppName:
			self.lastTerminalAppName = appName
			self.announcedHelp = True
			# Translators: Message announced when entering a terminal application
			ui.message(_("Terminal Access support active. Press NVDA+shift+f1 for help."))
			# Check for conflicts silently on first focus
			self._checkConflictsSilently()

	def _checkConflictsSilently(self):
		"""Run conflict detection and warn if issues found."""
		try:
			import globalPluginHandler
			other_plugins = [p for p in globalPluginHandler.runningPlugins
							if p is not self]
			excluded = self._getExcludedGestures()
			conflicts = self._conflictDetector.detect_conflicts(
				our_gestures=_DEFAULT_GESTURES,
				other_plugins=other_plugins,
				excluded_gestures=excluded
			)
			if conflicts:
				count = len(conflicts)
				# Brief warning, not full report
				# Translators: Warning when gesture conflicts are detected
				wx.CallLater(2000, ui.message,
					_("{count} gesture conflicts with other add-ons. "
					  "Open Terminal Access settings to resolve.").format(count=count))
		except Exception:
			pass

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
		# In a terminal, we handle character echo ourselves.
		# Skip nextHandler in quiet mode so NVDA doesn't speak.
		if self._boundTerminal is None:
			nextHandler()
			return

		# Record typing timestamp so cursor tracking can distinguish
		# typing-induced caret events from navigation.
		self._lastTypedCharTime = time.time()

		# In quiet mode, skip nextHandler entirely (no speech at all)
		if self._getEffective("quietMode"):
			return

		# Let NVDA handle its own echo, then check if we should add ours
		nextHandler()

		# Don't echo if disabled or NVDA is already echoing
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
		except (AttributeError, RuntimeError):
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

		When Terminal Access is active, this handler takes over caret
		announcement from NVDA's native handler. In quiet mode,
		nextHandler is skipped entirely so NVDA does not speak.
		In normal mode, nextHandler is skipped because our own
		_announceCursorPosition handles speech with debouncing,
		blank suppression, and error audio cues.
		"""
		if self._boundTerminal is None:
			nextHandler()
			return

		isQuietMode = self._configManager.get("quietMode")

		# In quiet mode, do NOT call nextHandler (suppresses all speech).
		# Only play audio cues if enabled.
		if isQuietMode:
			if self._configManager.get("outputActivityTones", False):
				self._checkOutputActivityTone()
			if (self._configManager.get("errorAudioCues", True)
					and self._configManager.get("errorAudioCuesInQuietMode", False)):
				self._checkErrorAudioCue()
			return

		# Normal mode: activity tones
		if self._configManager.get("outputActivityTones", False):
			self._checkOutputActivityTone()

		# Normal mode: cursor tracking handled by our addon (not NVDA native).
		# We skip nextHandler() so NVDA's native caret tracking doesn't
		# announce "blank" after Enter or double-speak with our handler.
		if not self._configManager.get("cursorTracking"):
			return

		# Cancel any pending cursor tracking announcement
		if self._cursorTrackingTimer:
			self._cursorTrackingTimer.Stop()
			self._cursorTrackingTimer = None

		# Schedule announcement with delay
		self._cursorTrackingTimer = wx.CallLater(
			self._configManager.get("cursorDelay", 20), self._announceCursorPosition, obj
		)

	def event_textChange(self, obj, nextHandler):
		"""Handle text content changes in the terminal.

		Fires when the terminal buffer content changes (program output).
		Unlike event_caret, this fires even when the caret stays in place
		(e.g., output scrolling above the input line).

		Used for output activity tones and quiet-mode error detection.
		In quiet mode, nextHandler is skipped so NVDA doesn't speak.
		"""
		if self._boundTerminal is None:
			nextHandler()
			return

		isQuietMode = self._configManager.get("quietMode")

		# In quiet mode, skip nextHandler (no speech)
		if not isQuietMode:
			nextHandler()

		if self._configManager.get("outputActivityTones", False):
			self._checkOutputActivityTone()

		if isQuietMode:
			if (self._configManager.get("errorAudioCues", True)
					and self._configManager.get("errorAudioCuesInQuietMode", False)):
				self._checkErrorAudioCue()

	def _checkErrorAudioCue(self):
		"""Play error/warning beep for the current line if applicable.

		Used by event_caret in quiet mode to provide audio-only
		notification of errors without speech.
		"""
		try:
			reviewPos = self._getReviewPosition()
			if not reviewPos:
				return
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_LINE)
			text = getattr(info, "text", "")
			if not isinstance(text, str):
				return
			classification = self._errorDetector.classify(text)
			if classification == 'error':
				tones.beep(220, 50)
			elif classification == 'warning':
				tones.beep(440, 30)
		except (RuntimeError, AttributeError, TypeError):
			pass

	def _checkOutputActivityTone(self):
		"""Play two ascending tones when new program output appears.

		Distinguishes program output from user typing by checking
		_lastTypedCharTime. Debounces using the user-configurable
		outputActivityDebounce setting (milliseconds).
		"""
		now = time.time()

		# Skip if user was recently typing (this is key echo, not output)
		if (now - self._lastTypedCharTime) < self._BLANK_AFTER_TYPING_GRACE:
			return

		# Skip if we already played the tone recently (configurable debounce)
		debounce_ms = self._configManager.get("outputActivityDebounce", 1000)
		debounce_s = debounce_ms / 1000.0
		if (now - self._lastOutputActivityTime) < debounce_s:
			return

		# New output detected: play two ascending tones
		self._lastOutputActivityTime = now
		tones.beep(600, 30)
		tones.beep(800, 30)

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
		except (AttributeError, TypeError, RuntimeError):
			# Cursor tracking is a non-critical feature; common failures are
			# missing attributes on obj or COM/UIA errors.
			pass

	def _announceStandardCursor(self, obj, _retry=False):
		"""
		Standard cursor tracking - announce character at cursor position.

		Uses a line-level cache to avoid redundant UIA/COM calls when the
		caret moves within the same line and no content change has occurred
		since the last announcement.

		Args:
			obj: The terminal object.
			_retry: If True, this is a deferred retry call; skip scheduling
				further retries to prevent unbounded CallLater chains.
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
				except (RuntimeError, AttributeError, TypeError):
					self._lastLineText = None
					self._lastLineStartOffset = None
					self._lastLineEndOffset = None

		# When a recent keystroke caused this caret movement and the addon's
		# key echo is off, suppress the character announcement to avoid a
		# "shadow key echo" through cursor tracking.  Navigation-induced
		# caret events (arrow keys, Home/End, etc.) are not affected because
		# they don't set _lastTypedCharTime.
		typing_induced = (time.time() - self._lastTypedCharTime) < self._BLANK_AFTER_TYPING_GRACE
		if typing_induced and not self._isKeyEchoActive():
			return

		# When the caret lands on blank/empty after recent typing (e.g. pressing
		# Enter), suppress the "Blank" announcement.  Navigation blanks (no
		# recent typing) are always announced as meaningful position feedback.
		if typing_induced and (not char or char in ('\r', '\n')):
			if not _retry:
				try:
					wx.CallLater(50, self._announceStandardCursor, obj, True)
					wx.CallLater(150, self._announceStandardCursor, obj, True)
				except (RuntimeError, AttributeError):
					pass
			return

		self._speakCharacter(char)

		# Notify the Braille display of the caret movement so it shows the
		# full line context around the cursor instead of a brief character flash.
		if _braille_available:
			try:
				if braille.handler.displaySize > 0:
					braille.handler.handleCaretMove(obj)
			except (AttributeError, RuntimeError):
				pass

	# DEPRECATED: Scheduled for removal in v2.0
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
				# Strip ANSI codes to get clean text
				highlightedText = _strip_ansi(lineText).strip() or None
				if highlightedText and highlightedText != self._lastHighlightedText:
					self._lastHighlightedText = highlightedText
					ui.message(_("Highlighted: {text}").format(text=highlightedText))
				# Update Braille display with full line context
				if _braille_available:
					try:
						if braille.handler.displaySize > 0:
							braille.handler.handleCaretMove(obj)
					except (AttributeError, RuntimeError):
						pass
			else:
				# Fall back to standard cursor announcement
				self._announceStandardCursor(obj)
		except (AttributeError, TypeError, RuntimeError):
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
				window = self._currentProfile.get_window_at_position(currentRow, currentCol)
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
			if self._configManager.get("windowEnabled"):
				windowTop = self._configManager.get("windowTop")
				windowBottom = self._configManager.get("windowBottom")
				windowLeft = self._configManager.get("windowLeft")
				windowRight = self._configManager.get("windowRight")

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

		except (AttributeError, TypeError, RuntimeError):
			# On error, fall back to standard tracking
			self._announceStandardCursor(obj)

	@script(
		# Translators: Description for the show help gesture
		description=_("Opens the Terminal Access user guide"),
		gesture="kb:NVDA+shift+f1",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_showHelp(self, gesture):
		"""Open the Terminal Access user guide."""
		addon = addonHandler.getCodeAddon()
		if not addon:
			ui.message(_("Terminal Access add-on not properly installed."))
			return

		# Find the doc file for the user's language, fall back to English.
		# We build the path ourselves instead of using getDocFilePath()
		# because that method can produce doubled paths in some NVDA versions.
		docFile = "readme.html"
		lang = languageHandler.getLanguage()
		candidates = [
			os.path.join(addon.path, "doc", lang, docFile),
			os.path.join(addon.path, "doc", lang.split("_")[0], docFile),
			os.path.join(addon.path, "doc", "en", docFile),
		]
		for docPath in candidates:
			if os.path.isfile(docPath):
				os.startfile(docPath)
				return
		ui.message(_("Help file not found. Please reinstall the add-on."))
	
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
			self._copyAndAnnounce(info.text, _("Line copied"))
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

			info = terminal.makeTextInfo(textInfos.POSITION_ALL)
			self._copyAndAnnounce(info.text, _("Screen copied"))
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
					except (KeyError, AttributeError):
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
			wx.CallAfter(gui.mainFrame._popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, _get_settings_panel_class())
		except (AttributeError, TypeError, RuntimeError):
			# Translators: Error message when settings dialog cannot be opened
			ui.message(_("Unable to open settings dialog. Please try again."))

	@script(
		# Translators: Description for checking gesture conflicts
		description=_("Check for gesture conflicts with other add-ons"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_checkGestureConflicts(self, gesture):
		"""Check and report gesture conflicts with other loaded plugins."""
		if not self.isTerminalApp():
			gesture.send()
			return
		import globalPluginHandler
		other_plugins = [p for p in globalPluginHandler.runningPlugins
						if p is not self]
		excluded = self._getExcludedGestures()
		conflicts = self._conflictDetector.detect_conflicts(
			our_gestures=_DEFAULT_GESTURES,
			other_plugins=other_plugins,
			excluded_gestures=excluded
		)
		if conflicts:
			report = self._conflictDetector.format_report(conflicts)
			count = len(conflicts)
			# Translators: Announced when gesture conflicts are found
			ui.message(_("{count} gesture conflicts found. {report}").format(
				count=count, report=report
			))
		else:
			# Translators: Announced when no gesture conflicts are found
			ui.message(_("No gesture conflicts detected."))

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
			# DEPRECATED: Scheduled for removal in v2.0
			CT_HIGHLIGHT: _("Highlight tracking (deprecated)"),
			CT_WINDOW: _("Window tracking")
		}
		ui.message(modeNames.get(nextMode, _("Unknown mode")))

		# Show deprecation warning when cycling to Highlight mode
		if nextMode == CT_HIGHLIGHT and "highlight_tracking" not in self._deprecation_warned:
			self._deprecation_warned.add("highlight_tracking")
			ui.message(_("Note: Highlight tracking is deprecated and will be removed in version 2. Contact PratikP1 on GitHub if you use this feature."))

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

		if not self._configManager.get("windowEnabled"):
			# Translators: Message when no window is defined
			ui.message(_("No window defined"))
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to read window"))
				return

			# Get window boundaries
			windowTop = self._configManager.get("windowTop")
			windowBottom = self._configManager.get("windowBottom")
			windowLeft = self._configManager.get("windowLeft")
			windowRight = self._configManager.get("windowRight")

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

	def _announceCharAtPosition(self, info):
		"""Expand info to a character and speak it, or announce Blank.

		Args:
			info: A TextInfo object positioned where the character should be read.
		"""
		info.expand(textInfos.UNIT_CHARACTER)
		char = info.text
		if char and char != '\n' and char != '\r':
			speech.speakText(char)
			self._brailleMessage(char)
		else:
			# Translators: Message for blank line
			ui.message(_("Blank"))

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

			self._announceCharAtPosition(info)
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

			self._announceCharAtPosition(info)
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

			self._announceCharAtPosition(info)
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

			self._announceCharAtPosition(info)
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
		# Translators: Description for announcing active profile; double-press opens profile selection
		description=_("Announce active profile. Press twice to select a profile."),
		gesture="kb:NVDA+f10",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_announceActiveProfile(self, gesture):
		"""Announce the active profile, or open profile selection on double-press."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if scriptHandler.getLastScriptRepeatCount() >= 1:
			self._showProfileSelectionDialog()
			return

		if self._currentProfile:
			activeProfileName = self._currentProfile.displayName
		else:
			activeProfileName = _("None (using global settings)")

		defaultProfileName = self._configManager.get("defaultProfile", "")
		if defaultProfileName and defaultProfileName in self._profileManager.profiles:
			defaultProfile = self._profileManager.get_profile(defaultProfileName)
			defaultProfileDisplay = defaultProfile.displayName
		else:
			defaultProfileDisplay = _("None")

		ui.message(_("Active profile: {active}. Default profile: {default}").format(
			active=activeProfileName,
			default=defaultProfileDisplay
		))

	def _showProfileSelectionDialog(self):
		"""Open the profile selection dialog."""
		from lib.profiles import ProfileSelectionDialog

		def on_activate(app_name):
			profile = self._profileManager.get_profile(app_name)
			if profile:
				self._currentProfile = profile
				ui.message(_("Profile activated: {name}").format(name=profile.displayName))

		def _show():
			try:
				gui.mainFrame.prePopup()
				dlg = ProfileSelectionDialog(gui.mainFrame, self._profileManager, on_activate)
				dlg.ShowModal()
				dlg.Destroy()
			finally:
				gui.mainFrame.postPopup()

		wx.CallAfter(_show)

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

			spaces, tabs = self._getIndentationInfo(lineText)
			if spaces == 0 and tabs == 0 and not lineText.strip():
				# Translators: Message for empty line
				ui.message(_("Empty line"))
				return

			formatted = self._formatIndentation(spaces, tabs)
			if formatted:
				ui.message(formatted)
			else:
				# Translators: Message when line has no indentation
				ui.message(_("No indentation"))
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
		Read a line with optional indentation announcement and error audio cues.

		Args:
			gesture: The gesture that triggered this command
			moveFunction: The function to call to read the line
		"""
		shouldAnnounceIndentation = self._getEffective("indentationOnLineRead")
		shouldPlayErrorCues = self._configManager.get("errorAudioCues", True)

		# Read the line using NVDA's built-in functionality.
		# This moves the review cursor and speaks the line.
		moveFunction(gesture)

		# Get the line text at the NEW review position (after move).
		lineText = ""
		try:
			reviewPos = self._getReviewPosition()
			if reviewPos:
				info = reviewPos.copy()
				info.expand(textInfos.UNIT_LINE)
				text = getattr(info, "text", "")
				if isinstance(text, str):
					lineText = text
		except (RuntimeError, AttributeError, TypeError):
			pass

		# Play error/warning audio cue immediately after speech
		if shouldPlayErrorCues and lineText:
			classification = self._errorDetector.classify(lineText)
			if classification == 'error':
				tones.beep(220, 50)
			elif classification == 'warning':
				tones.beep(440, 30)

		# Announce indentation after line is read
		if shouldAnnounceIndentation and lineText:
			try:
				spaces, tabs = self._getIndentationInfo(lineText)
				indentInfo = self._formatIndentation(spaces, tabs)
				if indentInfo:
					ui.message(indentInfo)
			except (RuntimeError, AttributeError, TypeError):
				pass

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
		except (RuntimeError, AttributeError):
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
		except (RuntimeError, AttributeError, TypeError):
			ui.message(_("Unable to read character"))
			return

		if not charText:
			ui.message(_("Unable to read character"))
			return

		if phonetic:
			try:
				speech.speakSpelling(charText)
			except (AttributeError, TypeError):
				ui.message(charText)
			return

		speak_kwargs = {"unit": textInfos.UNIT_CHARACTER}
		try:
			speak_reason = speech.OutputReason.CARET
			speak_kwargs["reason"] = speak_reason
		except AttributeError:
			# Older/limited speech modules may not expose OutputReason
			pass

		try:
			speech.speakTextInfo(reviewInfo, **speak_kwargs)
		except (AttributeError, TypeError, RuntimeError):
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

	def _changePunctuationLevel(self, delta):
		"""Change the punctuation level by delta (wraps around 0-3).

		Args:
			delta: Amount to change (+1 or -1).
		"""
		currentLevel = self._getEffective("punctuationLevel")
		newLevel = (currentLevel + delta) % 4
		config.conf["terminalAccess"]["punctuationLevel"] = newLevel
		if self._currentProfile is not None and self._currentProfile.punctuationLevel is not None:
			self._currentProfile.punctuationLevel = newLevel

		ui.message(_PUNCT_LEVEL_NAMES.get(newLevel, _("Punctuation level unknown")))

	@script(
		# Translators: Description for decreasing punctuation level
		description=_("Decrease punctuation level"),
		gesture="kb:NVDA+-",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_decreasePunctuationLevel(self, gesture):
		"""Decrease the punctuation level (wraps from 0 to 3)."""
		if not self.isTerminalApp():
			gesture.send()
			return
		self._changePunctuationLevel(-1)

	@script(
		# Translators: Description for increasing punctuation level
		description=_("Increase punctuation level"),
		gesture="kb:NVDA+=",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_increasePunctuationLevel(self, gesture):
		"""Increase the punctuation level (wraps from 3 to 0)."""
		if not self.isTerminalApp():
			gesture.send()
			return
		self._changePunctuationLevel(1)

	def _readDirectional(self, direction):
		"""Read text in a given direction from the current review position.

		Args:
			direction: One of 'left', 'right', 'top', 'bottom'.
		"""
		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			if direction in ("left", "right"):
				lineInfo = reviewPos.copy()
				lineInfo.expand(textInfos.UNIT_LINE)
				if direction == "left":
					lineInfo.setEndPoint(reviewPos, "endToEnd")
				else:
					lineInfo.setEndPoint(reviewPos, "startToStart")
				text = lineInfo.text
			else:
				terminal = self._boundTerminal
				if not terminal:
					ui.message(_("Unable to read"))
					return
				if direction == "top":
					rangeInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
					rangeInfo.setEndPoint(reviewPos, "endToEnd")
					text = rangeInfo.text
				else:  # bottom
					endInfo = terminal.makeTextInfo(textInfos.POSITION_LAST)
					reviewPos.setEndPoint(endInfo, "endToEnd")
					text = reviewPos.text

			if not text or not text.strip():
				# Translators: Message when region is empty
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
			self._brailleMessage(text)
		except Exception:
			ui.message(_("Unable to read"))

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
		self._readDirectional("left")

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
		self._readDirectional("right")

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
		self._readDirectional("top")

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
		self._readDirectional("bottom")

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

			self._copyAndAnnounce(startInfo.text, _("Selection copied"))
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
		description=_("Copy rectangular selection between marks (deprecated)"),
		gesture="kb:NVDA+shift+c",
		category=SCRCAT_TERMINALACCESS,
	)
	# DEPRECATED: Scheduled for removal in v2.0
	def script_copyRectangularSelection(self, gesture):
		"""Copy rectangular region (column-based) between marks."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if "rectangular_selection" not in self._deprecation_warned:
			self._deprecation_warned.add("rectangular_selection")
			ui.message(_("Note: Rectangular selection is deprecated and will be removed in version 2. Contact PratikP1 on GitHub if you use this feature."))
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
			_message_thread_safe(_("Background copy failed"))
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
					_message_thread_safe(_("Copy operation cancelled by user"))
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
			_message_thread_safe(message)
		else:
			_message_thread_safe(_("Unable to copy"))

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

		# Provide buffer lines for context-aware auto-labeling.
		self._bookmarkManager._buffer_lines = self._getBufferLines()

		if self._bookmarkManager.set_bookmark(name):
			label = self._bookmarkManager.get_bookmark_label(name) or ""
			if label:
				# Translators: Message when bookmark set with line content
				ui.message(_("Bookmark {name}: {label}").format(name=name, label=label))
			else:
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
			# Announce bookmark label and position after jump
			label = self._bookmarkManager.get_bookmark_label(name) or ""
			info = api.getReviewPosition()
			if info and info.text:
				ui.message(info.text)
			elif label:
				# Translators: Message when jumping to bookmark with label
				ui.message(_("Bookmark {name}: {label}").format(name=name, label=label))
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
		"""List all bookmarks in an accessible dialog."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._bookmarkManager:
			# Translators: Error message when bookmark manager not initialized
			ui.message(_("Bookmark manager not available"))
			return

		bookmarks = self._bookmarkManager.list_bookmarks()
		if not bookmarks:
			# Translators: Message when no bookmarks exist
			ui.message(_("No bookmarks set"))
			return

		wx.CallAfter(self._showBookmarkDialog)

	def _showBookmarkDialog(self):
		"""Open the bookmark list dialog on the main thread."""
		from lib.navigation import BookmarkListDialog
		import gui
		try:
			gui.mainFrame.prePopup()
			dlg = BookmarkListDialog(gui.mainFrame, self._bookmarkManager)
			dlg.ShowModal()
			dlg.Destroy()
			# Suppress navigator reset when focus returns to terminal
			# so the review cursor stays on the bookmarked line.
			self._bookmarkJumpPending = True
		finally:
			gui.mainFrame.postPopup()

	# Section 8.4: Section list gesture (v1.5.0+)

	@scriptHandler.script(
		# Translators: Description for listing detected sections
		description=_("List all detected sections in the terminal buffer"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+s"
	)
	def script_listSections(self, gesture):
		"""List all detected sections in an accessible dialog."""
		if not self.isTerminalApp():
			gesture.send()
			return

		lines = self._getBufferLines()
		if not lines:
			# Translators: Message when terminal buffer cannot be read
			ui.message(_("Cannot read terminal buffer"))
			return

		if not self._bookmarkManager:
			ui.message(_("Bookmark manager not available"))
			return

		sections = self._bookmarkManager.list_sections(lines)
		if not sections:
			# Translators: Message when no sections detected
			ui.message(_("No sections detected"))
			return

		wx.CallAfter(self._showSectionDialog, sections)

	def _showSectionDialog(self, sections):
		"""Open the section list dialog on the main thread."""
		from lib.navigation import SectionListDialog
		import gui
		try:
			gui.mainFrame.prePopup()
			dlg = SectionListDialog(
				gui.mainFrame, sections, self._jumpToLine
			)
			dlg.ShowModal()
			dlg.Destroy()
			self._bookmarkJumpPending = True
		finally:
			gui.mainFrame.postPopup()

	def _jumpToLine(self, line_num):
		"""Move the review cursor to a 0-based line number."""
		terminal = self._boundTerminal
		if terminal is None:
			return
		try:
			pos = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			if line_num > 0:
				pos.move(textInfos.UNIT_LINE, line_num)
			pos.expand(textInfos.UNIT_LINE)
			api.setReviewPosition(pos)
			if pos.text:
				ui.message(pos.text)
		except Exception:
			pass

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

	# DEPRECATED: Scheduled for removal in v2.0 — Command history navigation

	@scriptHandler.script(
		# Translators: Description for scanning command history
		description=_("Scan terminal output to detect and store command history (deprecated)"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+shift+h"
	)
	# DEPRECATED: Scheduled for removal in v2.0
	def script_scanCommandHistory(self, gesture):
		"""Scan terminal output for commands."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if "command_history" not in self._deprecation_warned:
			self._deprecation_warned.add("command_history")
			ui.message(_("Note: Command history is deprecated and will be removed in version 2. Contact PratikP1 on GitHub if you use this feature."))
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
		description=_("Navigate to previous command in history (deprecated)"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+h"
	)
	# DEPRECATED: Scheduled for removal in v2.0
	def script_previousCommand(self, gesture):
		"""Navigate to previous command."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if "command_history" not in self._deprecation_warned:
			self._deprecation_warned.add("command_history")
			ui.message(_("Note: Command history is deprecated and will be removed in version 2. Contact PratikP1 on GitHub if you use this feature."))
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
		description=_("Navigate to next command in history (deprecated)"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+g"
	)
	# DEPRECATED: Scheduled for removal in v2.0
	def script_nextCommand(self, gesture):
		"""Navigate to next command."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if "command_history" not in self._deprecation_warned:
			self._deprecation_warned.add("command_history")
			ui.message(_("Note: Command history is deprecated and will be removed in version 2. Contact PratikP1 on GitHub if you use this feature."))
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
		description=_("List all commands in history (deprecated)"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+shift+l"
	)
	# DEPRECATED: Scheduled for removal in v2.0
	def script_listCommandHistory(self, gesture):
		"""List all commands in history."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if "command_history" not in self._deprecation_warned:
			self._deprecation_warned.add("command_history")
			ui.message(_("Note: Command history is deprecated and will be removed in version 2. Contact PratikP1 on GitHub if you use this feature."))
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

	def _handleSearchResult(self, search_text, match_count):
		"""Handle search results: beep and announce failure or signal success.

		Returns True if matches were found (caller should open results dialog),
		False otherwise.
		"""
		if match_count > 0:
			tones.beep(800, 50)
			return True
		else:
			tones.beep(300, 100)
			# Translators: No matches found
			ui.message(_("No matches found for '{pattern}'").format(pattern=search_text))
			return False

	@scriptHandler.script(
		# Translators: Description for searching output
		description=_("Search terminal output for text pattern"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+f"
	)
	def script_searchOutput(self, gesture):
		"""Search terminal output and show results in a browsable dialog."""
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
			"""Show search dialog, then results dialog if matches found."""
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

						if self._handleSearchResult(search_text, match_count):
							# Show results in a browsable dialog instead of
							# auto-jumping.  The dialog's Jump handler sets
							# _searchJumpPending so event_gainFocus won't
							# reset the review cursor.
							from lib.search import SearchResultsDialog

							def on_jump():
								self._searchJumpPending = True

							results_dlg = SearchResultsDialog(
								gui.mainFrame, self._searchManager, on_jump)
							results_dlg.ShowModal()
							results_dlg.Destroy()
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

	def _navigateSearch(self, direction):
		"""Navigate to the next or previous search match.

		Args:
			direction: 'next' or 'previous'.
		"""
		if not self._searchManager:
			return

		if self._searchManager.get_match_count() == 0:
			# Translators: No search results
			ui.message(_("No search results. Use NVDA+F to search."))
			return

		move_fn = self._searchManager.next_match if direction == "next" else self._searchManager.previous_match
		if move_fn():
			info = self._searchManager.get_current_match_info()
			if info:
				match_num, total, line_text, line_num = info
				ui.message(line_text)
		else:
			# Translators: Error jumping to search match
			ui.message(_("Cannot jump to {direction} match").format(direction=direction))

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
		self._navigateSearch("next")

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
		self._navigateSearch("previous")

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

	def _copyAndAnnounce(self, text, successMessage=None):
		"""Copy text to clipboard and announce the result.

		Args:
			text: The text to copy.
			successMessage: Message to announce on success. Defaults to "Copied".

		Returns:
			True if copy succeeded, False otherwise.
		"""
		if not text:
			ui.message(_("Unable to copy"))
			return False
		if self._copyToClipboard(text):
			ui.message(successMessage or _("Copied"))
			return True
		ui.message(_("Unable to copy"))
		return False

	# ------------------------------------------------------------------
	# Section navigation helpers and scripts
	# ------------------------------------------------------------------

	def _getBufferLines(self):
		"""Read all lines from the current terminal buffer.

		Returns:
			list[str] or None if the terminal buffer cannot be read.
		"""
		terminal = self._boundTerminal
		if terminal is None:
			return None
		try:
			info = terminal.makeTextInfo(textInfos.POSITION_ALL)
			text = info.text or ""
			return text.split("\n")
		except Exception:
			return None

	def _getCurrentLineNumber(self):
		"""Return the 0-based line number of the review cursor.

		Returns:
			int or None if the position cannot be determined.
		"""
		info = self._getReviewPosition()
		if info is None:
			return None
		terminal = self._boundTerminal
		if terminal is None:
			return None
		try:
			topInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			topInfo.setEndPoint(info, "endToStart")
			above = topInfo.text or ""
			return above.count("\n")
		except Exception:
			return 0

	def _navigateToSection(self, section):
		"""Move the review cursor to the line indicated by *section* and speak it.

		Args:
			section: A Section namedtuple, or None (beeps if None).
		"""
		if section is None:
			tones.beep(200, 100)
			return
		terminal = self._boundTerminal
		if terminal is None:
			return
		try:
			info = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			info.move(textInfos.UNIT_LINE, section.line_num)
			info.expand(textInfos.UNIT_LINE)
			api.setReviewPosition(info)
			speech.speakTextInfo(info, reason=speech.REASON_CARET)
			# Play a brief audio cue for error/warning sections
			if section.category == "error":
				tones.beep(220, 40)
			elif section.category == "warning":
				tones.beep(440, 40)
		except Exception:
			ui.message(section.text)

	@script(
		# Translators: Description for jumping to the next section boundary
		description=_("Jump to next section in terminal output"),
		gesture="kb:NVDA+n",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_nextSection(self, gesture):
		"""Jump to the next section boundary."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		self._sectionTokenizer.tokenize(lines)
		current = self._getCurrentLineNumber() or 0
		self._navigateToSection(self._sectionTokenizer.next_section(current))

	@script(
		# Translators: Description for jumping to the previous section boundary
		description=_("Jump to previous section in terminal output"),
		gesture="kb:NVDA+shift+n",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_prevSection(self, gesture):
		"""Jump to the previous section boundary."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		self._sectionTokenizer.tokenize(lines)
		current = self._getCurrentLineNumber() or 0
		self._navigateToSection(self._sectionTokenizer.prev_section(current))

	@script(
		# Translators: Description for jumping to the next error or warning
		description=_("Jump to next error or warning in terminal output"),
		gesture="kb:NVDA+alt+n",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_nextError(self, gesture):
		"""Jump to the next error or warning line."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		self._sectionTokenizer.tokenize(lines)
		current = self._getCurrentLineNumber() or 0
		self._navigateToSection(self._sectionTokenizer.next_error(current))

	@script(
		# Translators: Description for jumping to the previous error or warning
		description=_("Jump to previous error or warning in terminal output"),
		gesture="kb:NVDA+alt+shift+n",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_prevError(self, gesture):
		"""Jump to the previous error or warning line."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		self._sectionTokenizer.tokenize(lines)
		current = self._getCurrentLineNumber() or 0
		self._navigateToSection(self._sectionTokenizer.prev_error(current))

	@script(
		# Translators: Description for jumping to the next prompt
		description=_("Jump to next prompt in terminal output"),
		gesture="kb:NVDA+alt+p",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_nextPrompt(self, gesture):
		"""Jump to the next prompt line."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		self._sectionTokenizer.tokenize(lines)
		current = self._getCurrentLineNumber() or 0
		self._navigateToSection(self._sectionTokenizer.next_prompt(current))

	@script(
		# Translators: Description for jumping to the previous prompt
		description=_("Jump to previous prompt in terminal output"),
		gesture="kb:NVDA+alt+shift+p",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_prevPrompt(self, gesture):
		"""Jump to the previous prompt line."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		self._sectionTokenizer.tokenize(lines)
		current = self._getCurrentLineNumber() or 0
		self._navigateToSection(self._sectionTokenizer.prev_prompt(current))

	# ------------------------------------------------------------------
	# Section 11: Summarization
	# ------------------------------------------------------------------

	@script(
		# Translators: Description for summarizing the last command output
		description=_("Summarize the output of the last command"),
		gesture="kb:NVDA+alt+s",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_summarizeLastCommand(self, gesture):
		"""Summarize the output between the last prompt and the cursor."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Check privacy toggle
		if not self._configManager.get("summarizationEnabled", False):
			ui.message(self._outputSummarizer.get_disabled_message())
			return

		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return

		# Find the last prompt using SectionTokenizer
		self._sectionTokenizer.tokenize(lines)
		current = self._getCurrentLineNumber() or len(lines) - 1

		# Walk backwards to find the last prompt before the cursor
		last_prompt_line = None
		for section in reversed(self._sectionTokenizer._sections):
			if section.category == "prompt" and section.line_num <= current:
				last_prompt_line = section.line_num
				break

		if last_prompt_line is None:
			# No prompt found; summarize from the beginning
			output_lines = lines[:current + 1]
		else:
			# Extract lines between prompt and cursor (skip the prompt itself)
			output_lines = lines[last_prompt_line + 1:current + 1]

		if not output_lines:
			# Translators: Message when there is no output to summarize
			ui.message(_("No output to summarize"))
			return

		summary = self._outputSummarizer.summarize_lines(output_lines)
		if summary:
			ui.message("\n".join(summary))
		else:
			# Translators: Message when summarizer produces empty result
			ui.message(_("No significant output found"))

	@script(
		# Translators: Description for summarizing the current selection
		description=_("Summarize the text between selection marks"),
		gesture="kb:NVDA+alt+shift+s",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_summarizeSelection(self, gesture):
		"""Summarize the text between selection marks."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Check privacy toggle
		if not self._configManager.get("summarizationEnabled", False):
			ui.message(self._outputSummarizer.get_disabled_message())
			return

		if not self._markStart or not self._markEnd:
			# Translators: Message when no selection marks are set
			ui.message(_("No selection. Set marks first."))
			return

		terminal = self._boundTerminal
		if terminal is None:
			return

		try:
			startInfo = terminal.makeTextInfo(self._markStart)
			endInfo = terminal.makeTextInfo(self._markEnd)
			startInfo.setEndPoint(endInfo, "endToEnd")
			text = startInfo.text or ""
			selection_lines = text.split("\n")
		except Exception:
			# Translators: Error message when selection text cannot be read
			ui.message(_("Unable to read selection"))
			return

		if not selection_lines:
			ui.message(_("No output to summarize"))
			return

		summary = self._outputSummarizer.summarize_lines(selection_lines)
		if summary:
			ui.message("\n".join(summary))
		else:
			ui.message(_("No significant output found"))

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


# Lazy import: TerminalAccessSettingsPanel imports wx/gui modules that may
# not be ready during early NVDA startup.  Loaded on first access.
_TerminalAccessSettingsPanel = None


def _get_settings_panel_class():
	global _TerminalAccessSettingsPanel
	if _TerminalAccessSettingsPanel is None:
		from lib.settings_panel import TerminalAccessSettingsPanel
		_TerminalAccessSettingsPanel = TerminalAccessSettingsPanel
	return _TerminalAccessSettingsPanel
