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
	   - Command Layer: modal input mode (NVDA+apostrophe) that binds single-key
	     gestures from _COMMAND_LAYER_MAP so commands do not require
	     NVDA modifier combos; auto-exits on focus loss

Key Features:
	- Command Layer: Press NVDA+apostrophe to enter single-key command mode; press
	  Escape or NVDA+apostrophe again to exit. All navigation, selection, configuration, and
	  search commands become simple single-key presses (e.g. u/i/o for line
	  navigation, j/k/l for word navigation, f for search, etc.).
	- Navigation: Line, word, character, column, row movement
	- Selection: Linear text selection
	- Cursor Tracking: Standard, window, or off modes
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
import unicodedata

import braille

# The Rust native layer was removed in 2.0.0: its helper-process reads hung
# on some terminals (the beta.3 machine freeze and a per-search stall), the
# FFI text paths measured slower than Python, and the remaining pieces had
# identical pure-Python implementations. Everything runs in Python.

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
	"kb:shift+r": "listAiTurns",
	# Tab management
	"kb:t": "createNewTab",
	"kb:shift+t": "listTabs",
	# Search
	"kb:f": "searchOutput",
	"kb:f3": "findNext",
	"kb:shift+f3": "findPrevious",
	# Help & settings
	"kb:f1": "showHelp",
	"kb:s": "openSettings",
	"kb:shift+f1": "checkGestureConflicts",
	"kb:shift+h": "replayTutorial",
	"kb:h": "findCommand",
	# Transcript export
	"kb:control+s": "exportTranscript",
	# Diagnostic issue report
	"kb:shift+i": "reportIssue",
	# URL list (elements)
	"kb:e": "listUrls",
	# Summarization
	"kb:z": "summarizeLastCommand",
	"kb:shift+z": "summarizeSelection",
	# Privacy
	"kb:shift+p": "announcePrivacyStatus",
	# AI turn and code block navigation
	"kb:control+t": "nextTurn",
	"kb:control+shift+t": "prevTurn",
	"kb:control+b": "nextCodeBlock",
	"kb:control+shift+b": "prevCodeBlock",
	"kb:control+l": "announceCodeBlock",
	"kb:control+c": "copyCodeBlock",
	"kb:control+e": "explainCodeBlock",
	# Section navigation
	"kb:n": "nextSection",
	"kb:shift+n": "prevSection",
	# Streaming delta
	"kb:shift+d": "whatChanged",
	# Verbosity
	"kb:shift+v": "cycleVerbosity",
	# Table mode
	"kb:g": "toggleTableMode",
	# Buffer window
	"kb:enter": "showBufferWindow",
	"kb:shift+enter": "jumpToBufferLine",
	"kb:shift+e": "showErrorsWindow",
	"kb:shift+c": "showCommandsWindow",
	# Layer exit
	"kb:escape": "exitCommandLayer",
}

# Table mode key map: while table mode is active these keys navigate the
# detected table cell by cell. Bound on entry, removed on exit, mirroring
# the copy mode pattern.
_TABLE_MODE_BINDINGS = {
	"kb:upArrow": "tablePreviousRow",
	"kb:downArrow": "tableNextRow",
	"kb:leftArrow": "tablePreviousColumn",
	"kb:rightArrow": "tableNextColumn",
	"kb:home": "tableFirstColumn",
	"kb:end": "tableLastColumn",
	"kb:control+upArrow": "tableColumnHeader",
	"kb:space": "tableRowSummary",
	"kb:escape": "exitTableMode",
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
	"kb:NVDA+enter": "showBufferWindow",
	"kb:NVDA+shift+enter": "jumpToBufferLine",
	"kb:NVDA+shift+leftArrow": "readToLeft",
	"kb:NVDA+shift+rightArrow": "readToRight",
	"kb:NVDA+shift+upArrow": "readToTop",
	"kb:NVDA+shift+downArrow": "readToBottom",
	"kb:NVDA+r": "toggleMark",
	"kb:NVDA+c": "copyLinearSelection",
	"kb:NVDA+x": "clearMarks",
	"kb:NVDA+shift+b": "listBookmarks",
	"kb:NVDA+shift+t": "createNewTab",
	"kb:NVDA+w": "listTabs",
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
	# AI turn and code block navigation
	"kb:NVDA+alt+t": "nextTurn",
	"kb:NVDA+alt+shift+t": "prevTurn",
	"kb:NVDA+alt+b": "nextCodeBlock",
	"kb:NVDA+alt+shift+b": "prevCodeBlock",
	"kb:NVDA+alt+l": "announceCodeBlock",
	"kb:NVDA+alt+c": "copyCodeBlock",
	"kb:NVDA+alt+e": "explainCodeBlock",
	# Streaming delta
	"kb:NVDA+shift+d": "whatChanged",
	# Verbosity
	"kb:NVDA+shift+v": "cycleVerbosity",
	# Diagnostic issue report
	"kb:NVDA+alt+i": "reportIssue",
	# Table mode
	"kb:NVDA+alt+g": "toggleTableMode",
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
	"kb:NVDA+enter",          # NVDA: activate navigator object (laptop layout only)
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
	CT_OFF, CT_STANDARD, CT_WINDOW,
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
	OutputSearchManager, UrlExtractorManager, UrlListDialog,
	_OSC8_URL_PATTERN, _URL_PATTERN, _clean_url,
)


def _read_terminal_text_on_main(terminal_obj, position=None, timeout: float = 2.0):
	"""Read terminal text on the main thread via ``wx.CallAfter``.

	UIA/COM objects are apartment-threaded and must be called from the thread
	that created them.  Background threads (polling, etc.) that
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

	Bulk-reads a range of terminal lines in one marshaled call.

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
	"""Read terminal text in-process (marshalled to the main thread).

	The helper-process read was retired: in the field its pipe I/O hung
	for seconds per read on some terminals, while the in-process COM read
	is fast and cancellable by NVDA's watchdog.
	"""
	return _read_terminal_text_on_main(terminal_obj, position, timeout)


def _read_lines(terminal_obj, start_row: int, end_row: int, timeout: float = 5.0):
	"""Read a range of terminal lines in-process (marshalled to the main thread)."""
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
	"""Create a TextDiffer."""
	return TextDiffer()


def _make_position_cache() -> PositionCache:
	"""Create a PositionCache."""
	return PositionCache()


def _strip_ansi(text: str) -> str:
	"""Strip ANSI escape sequences."""
	return ANSIParser.stripANSI(text)

# Populate runtime dependency registry (must be after _strip_ansi is defined)
import lib._runtime as _rt
_rt.strip_ansi = _strip_ansi
_rt.read_terminal_text = _read_terminal_text
_rt.make_text_differ = _make_text_differ
_rt.make_position_cache = _make_position_cache
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
from lib.privacy import PrivacyGuard
from lib.code_block_reader import CodeBlockDetector
from lib.ai_turn_tokenizer import AITurnTokenizer
from lib.streaming_delta import StreamingDeltaTracker
from lib.progress_milestones import ProgressMilestoneTracker
from lib.table_reader import TableDetector, TableNavigator
from lib.audio_cues import play_cue, should_speak

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
		NVDA+semicolon   - Announce cursor position (row, column)
		NVDA+A           - Say All (continuous reading)
		NVDA+Shift+A     - Read color and formatting attributes

	Selection and Copying:
		NVDA+R           - Toggle mark (start/end/clear)
		NVDA+Alt+C       - Copy linear selection (between marks)
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
		NVDA+minus       - Decrease punctuation level
		NVDA+equals      - Increase punctuation level
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
	2 - Window: Track within defined screen region
	"""

	# Grace period (seconds) after a keystroke during which "Blank"
	# announcements from cursor tracking are suppressed.  Keeps terminal
	# output responsive without masking navigation feedback.
	_BLANK_AFTER_TYPING_GRACE: float = 0.3
	# Grace period (seconds) after a textChange event during which caret
	# character announcements are suppressed.  When program output arrives,
	# both textChange and caret fire in quick succession. The caret movement
	# is a side effect of the output, not user navigation.
	_OUTPUT_CARET_GRACE: float = 0.1
	# Minimum interval (seconds) between progress milestone buffer reads.
	# textChange can fire many times per second during rapid output;
	# reading the last buffer line involves COM/UIA calls, so throttle.
	_PROGRESS_CHECK_INTERVAL: float = 0.5

	# Class-level gesture map: ALL gestures are bound so they appear in
	# NVDA's Input Gestures dialog under the Terminal Access category.
	# getScript() returns None for terminal-specific gestures outside
	# terminals, so NVDA's own handlers process those keystrokes.
	__gestures = _DEFAULT_GESTURES

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
		# (line_text, line_num) of the last activated search match, captured
		# while match state is intact so the review cursor can be re-applied
		# after focus returns to the terminal (which clears match state).
		self._searchJumpTarget = None
		# Reapply bookkeeping: how many scheduled attempts remain, and
		# whether any attempt resolved. Failure is announced only after the
		# last attempt, so a retry that succeeds stays silent.
		self._reapplyAttemptsLeft = 0
		self._reapplyEverResolved = False
		self._cursorTrackingTimer = None
		self._lastCaretPosition = None
		self._lastTypedChar = None
		self._repeatedCharCount = 0
		# Characters collected toward the current word, for our own
		# word echo (see _echoTypedWord).
		self._typedWordChars = []
		self._lastTypedCharTime: float = 0.0
		self._lastTextChangeTime: float = 0.0
		self._lastOutputActivityTime: float = 0.0
		self._lastProgressCheckTime: float = 0.0

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

		# Last-used search options, remembered across searches this session.
		self._searchCaseSensitive = False
		self._searchUseRegex = False

		# Table mode state (modal, like copy mode). _tableNavigator is
		# non-None only while table mode is active.
		self._tableNavigator = None
		self._tableRow = 0
		self._tableCol = 0

	def _initManagers(self):
		"""Initialize feature managers (lazy — populated on first terminal focus)."""
		self._configManager = ConfigManager()
		self._windowManager = WindowManager(self._configManager)
		self._positionCalculator = PositionCalculator()

		# Register with the terminal overlay so it can delegate terminal
		# events (caret, text change, typed character) back to this plugin.
		from lib import terminal_overlay
		terminal_overlay.set_active_plugin(self)

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
		self._urlExtractorManager = None

		# Error/warning line detector for audio cues during line navigation
		self._errorDetector = ErrorLineDetector()

		# Progress milestone tracker for percentage announcements during
		# long operations (complements streaming suppression)
		self._progressTracker = ProgressMilestoneTracker()

		# Section tokenizer for semantic navigation
		self._sectionTokenizer = SectionTokenizer()

		# AI turn tokenizer for navigating AI CLI conversations
		self._aiTurnTokenizer = AITurnTokenizer()

		# Extractive summarizer for terminal output
		self._outputSummarizer = OutputSummarizer()

		# Code block detector for fenced code blocks
		self._codeBlockDetector = CodeBlockDetector()

		# Privacy guard for gating opt-in features
		self._privacyGuard = PrivacyGuard()

		# Streaming delta tracker for buffer change announcements
		self._deltaTracker = None  # Created lazily with current verbosity

		# Gesture conflict detection
		self._conflictDetector = GestureConflictDetector()

		# The native helper process is no longer started: all terminal
		# reads run in-process (COM calls NVDA's watchdog can cancel).
		# terminate() still stops a helper defensively should one exist.

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
		# Exit table mode silently when focus leaves terminal
		if getattr(self, "_tableNavigator", None) is not None:
			self._exitTableModeBindings()
		return False

	def terminate(self):
		"""Clean up when the plugin is terminated."""
		# Unregister from the terminal overlay so it stops delegating to a
		# dead plugin instance after a reload.
		try:
			from lib import terminal_overlay
			terminal_overlay.set_active_plugin(None)
		except Exception:
			pass

		# Stop window monitoring if active
		if self._windowMonitor and self._windowMonitor.is_monitoring():
			self._windowMonitor.stop_monitoring()

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
		from lib.terminal_overlay import (
			TerminalAccessTerminal, has_terminal_class, should_apply_overlay,
		)
		# Trust NVDA's own classification first: if it already decided this
		# is a terminal, support it even if the app is not on our list. That
		# is what makes terminals we never enumerated (and ones released
		# after this code) work. The app-name list stays as a union for the
		# terminals that have no NVDA appModule.
		if not has_terminal_class(clsList):
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

		if not obj:
			return False

		# NVDA's own classification wins, and is deliberately NOT cached by
		# app name: one application can own both terminal and non-terminal
		# windows, so a class-based hit must not poison the name cache.
		from NVDAObjects.behaviors import Terminal
		if isinstance(obj, Terminal):
			return True

		if not obj.appModule:
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
		wasSearchJump = self._searchJumpPending
		jumpPending = self._handleSearchJumpSuppression(obj)
		self._initializeManagers(obj)
		self._positionCalculator.clear_cache()
		self._detectAndApplyProfile(obj)
		self._announceProfileIfNew(obj, appName)
		# After a search or bookmark jump, leave the review cursor on the
		# jumped-to line instead of snapping it back to the caret (the
		# command prompt). Only rebind on an ordinary focus. Skipping our
		# rebind is not enough: NVDA core already rebound the review cursor
		# to the caret during focus handling (before this handler ran), so
		# the search jump is re-applied once the focus dust settles.
		if not jumpPending:
			self._bindReviewCursor(obj)
		elif wasSearchJump and self._searchJumpTarget and self._searchManager:
			self._scheduleSearchJumpReapply()
		self._announceHelpIfNeeded(appName)

	# NVDA rebinds the review cursor to the caret while handling the focus
	# return to the terminal. A setReviewPosition during that transition is
	# overridden, so the search jump is re-applied on a short timer (after
	# the transition), with one later retry as insurance.
	_REVIEW_REAPPLY_DELAYS_MS = (120, 400)

	def _scheduleSearchJumpReapply(self):
		"""Re-apply the search jump after NVDA's focus transition settles."""
		self._reapplyAttemptsLeft = len(self._REVIEW_REAPPLY_DELAYS_MS)
		self._reapplyEverResolved = False
		for delay in self._REVIEW_REAPPLY_DELAYS_MS:
			try:
				wx.CallLater(delay, self._reapplySearchJump)
			except (RuntimeError, AttributeError):
				pass

	def _reapplySearchJump(self):
		"""Re-apply the captured search jump target.

		Resolves the review position from the line text captured at jump
		time, so it does not depend on the search manager's match state
		(which is cleared when focus returns to the terminal).

		When every scheduled attempt fails to resolve the line, that is
		announced once: the line has scrolled out of the terminal's
		history, and silence would leave the user thinking the jump
		worked. Serves both search jumps and buffer-window jumps, which
		land through this same path.
		"""
		try:
			self._reapplyAttemptsLeft = max(0, self._reapplyAttemptsLeft - 1)
			target = self._searchJumpTarget
			mgr = self._searchManager
			if not target or mgr is None:
				return
			line_text, line_num = target
			pos = mgr._resolve_line_by_content(line_text, line_num)
			if pos is not None:
				self._reapplyEverResolved = True
				try:
					pos.expand(textInfos.UNIT_LINE)
				except (RuntimeError, AttributeError, TypeError):
					pass
				api.setReviewPosition(pos)
			elif self._reapplyAttemptsLeft == 0 and not self._reapplyEverResolved:
				# Translators: Announced when a jump target line cannot be
				# found in the terminal anymore
				ui.message(_(
					"Could not reach that line. "
					"It may have scrolled out of the terminal history."
				))
		except Exception:
			pass

	def _handleSearchJumpSuppression(self, obj):
		"""Suppress focus-driven cursor resets after a search or bookmark jump.

		Returns True if a jump was pending (so the caller also skips the
		caret rebind), False on an ordinary focus (navigator is reset to the
		terminal as usual).
		"""
		if self._searchJumpPending:
			self._searchJumpPending = False
			return True
		elif self._bookmarkJumpPending:
			self._bookmarkJumpPending = False
			return True
		else:
			api.setNavigatorObject(obj)
			return False

	def _initializeManagers(self, obj):
		"""Initialize or update all feature managers for the terminal."""
		managers = [
			('_tabManager', TabManager, lambda: (obj,), {}),
			('_bookmarkManager', BookmarkManager, lambda: (obj, self._tabManager), {}),
			('_searchManager', OutputSearchManager, lambda: (obj, self._tabManager), {}),
			('_urlExtractorManager', UrlExtractorManager, lambda: (obj, self._tabManager), {}),
		]
		for attr, cls, args_fn, kwargs in managers:
			current = getattr(self, attr, None)
			if not current:
				setattr(self, attr, cls(*args_fn(), **kwargs))
			else:
				current.update_terminal(obj)

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

	def _verbosityLevel(self):
		"""Return the configured verbosity level, defaulting to normal (1).

		Defensive so callers work even before the config manager is bound.
		"""
		cfg = getattr(self, "_configManager", None)
		if cfg is None:
			return 1
		try:
			return cfg.get("verbosityLevel", 1)
		except Exception:
			return 1

	def _announceProfileIfNew(self, obj, appName):
		"""Announce the active profile when switching to a new terminal app."""
		if appName == self.lastTerminalAppName:
			return
		if self._currentProfile:
			name = self._currentProfile.displayName
			verbosity = self._verbosityLevel()
			if should_speak(verbosity, "profile_detail"):
				detail = self._profileDetailSummary(self._currentProfile)
				if detail:
					name = f"{name}: {detail}"
			ui.message(name)

	@staticmethod
	def _profileDetailSummary(profile):
		"""Summarize a profile's non-inherited overrides for verbose speech.

		Returns a short comma-separated string, or an empty string when the
		profile overrides nothing beyond global settings.
		"""
		parts = []
		if profile.punctuationLevel is not None:
			punct = {
				# Translators: Punctuation level in a profile summary
				PUNCT_NONE: _("punctuation none"),
				# Translators: Punctuation level in a profile summary
				PUNCT_SOME: _("punctuation some"),
				# Translators: Punctuation level in a profile summary
				PUNCT_MOST: _("punctuation most"),
				# Translators: Punctuation level in a profile summary
				PUNCT_ALL: _("punctuation all"),
			}.get(profile.punctuationLevel)
			if punct:
				parts.append(punct)
		if profile.cursorTrackingMode is not None:
			mode = {
				# Translators: Cursor tracking mode in a profile summary
				CT_OFF: _("tracking off"),
				# Translators: Cursor tracking mode in a profile summary
				CT_STANDARD: _("tracking standard"),
				# Translators: Cursor tracking mode in a profile summary
				CT_WINDOW: _("tracking window"),
			}.get(profile.cursorTrackingMode)
			if mode:
				parts.append(mode)
		if profile.keyEcho is False:
			# Translators: Included in a profile summary when key echo is off
			parts.append(_("key echo off"))
		if profile.quietMode:
			# Translators: Included in a profile summary when quiet mode is on
			parts.append(_("quiet mode"))
		return ", ".join(parts)

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
		"""Announce help availability on first focus to a terminal.

		On the very first terminal focus ever (tutorialShown False), a
		short spoken tutorial replaces the one-line message and the flag
		is set so the tutorial never auto-plays again.
		"""
		if not self.announcedHelp or appName != self.lastTerminalAppName:
			self.lastTerminalAppName = appName
			self.announcedHelp = True
			from lib.tutorial import should_offer_tutorial, build_tutorial_message
			if should_offer_tutorial(self._configManager):
				ui.message(build_tutorial_message())
				self._configManager.set("tutorialShown", True)
			else:
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
		return self._configManager.get(key)

	def _nvdaSpeaksTypedWords(self) -> bool:
		"""True when NVDA's own word echo is enabled.

		This is the only NVDA typing setting that constrains us. NVDA's
		speakTypedCharacters() both speaks the character AND accumulates
		the buffer its word echo is built from, so withholding keystrokes
		does not merely mute a character, it destroys the word. Reads
		default to 0, so a missing key means off (0=off, 1=edit controls,
		2=always; a terminal counts as an editable control).
		"""
		return bool(config.conf["keyboard"].get("speakTypedWords", 0))

	def _ownsTypingEcho(self) -> bool:
		"""True when Terminal Access, not NVDA, echoes typing here.

		Key Echo used to do nothing whenever either NVDA typing setting
		was on, which made it a setting that silently did nothing. The
		word buffer only matters when word echo is on, and that is what
		makes this fixable:

		- NVDA word echo off: withholding keystrokes costs nothing, so we
		  take over and Key Echo finally applies.
		- NVDA word echo on, our Word Echo off: NVDA must keep receiving
		  keystrokes or its word echo breaks, so we stand down.
		- Our Word Echo on: we speak words ourselves, so we take over
		  regardless. That is an explicit opt-in to replace NVDA's word
		  echo; nobody loses it by accident.
		"""
		if self._getEffective("quietMode"):
			return False
		if not (self._getEffective("keyEcho") or self._getEffective("wordEcho")):
			return False
		if self._nvdaSpeaksTypedWords() and not self._getEffective("wordEcho"):
			return False
		return True

	def _isKeyEchoActive(self) -> bool:
		"""True when the add-on should speak individual typed characters."""
		return bool(self._ownsTypingEcho() and self._getEffective("keyEcho"))

	def _terminalTypedCharacter(self, obj, ch, speak_default):
		"""Handle a typed character in a terminal.

		Called from the overlay's event_typedCharacter. ``speak_default`` is
		a callable that invokes NVDA's own typed-character handling (the
		overlay's ``super().event_typedCharacter``); it runs only in normal
		mode, before the add-on's own echo.

		Announces characters as they are typed if keyEcho is enabled, using
		the punctuation level to decide symbol names and repeatedSymbols to
		condense runs. When NVDA's own speak-typed-characters setting is on,
		the add-on defers to NVDA to avoid duplicate announcements.
		"""
		# Record typing timestamp so cursor tracking can distinguish
		# typing-induced caret events from navigation.
		self._lastTypedCharTime = time.time()

		# Move the braille display to the caret FIRST, before any of the
		# speech decisions below. Every return past this point suppresses
		# speech only; braille must still show what was just typed.
		self._updateBrailleCaret(obj)

		# In quiet mode, no speech at all (neither NVDA's nor ours).
		if self._getEffective("quietMode"):
			return

		if not self._ownsTypingEcho():
			# NVDA echoes here. It must receive the keystroke, both to
			# speak it and to accumulate the buffer its word echo needs.
			speak_default()
			return

		# We own typing echo in this terminal, so NVDA's handler is
		# deliberately NOT called: that is what stops the double-speech
		# which used to force Key Echo to stand down entirely.
		self._echoTypedWord(ch)

		if not self._getEffective("keyEcho"):
			return

		# Clear position cache on content change
		self._positionCalculator.clear_cache()

		# Increment content generation so cached line TextInfo is invalidated.
		self._contentGeneration += 1

		# Process the character for speech
		if ch:
			# Condensing builds runs out of the real characters and would
			# report a password's shape ("dash 4 times"), so protected
			# input goes straight to the masked echo.
			if self._isTypingProtected():
				self._speakCharacter(ch)
				return
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
		try:
			if self._getEffective("quietMode"):
				return
			if braille.handler.displaySize > 0:
				braille.handler.message(text)
		except (AttributeError, RuntimeError):
			pass

	def _updateBrailleCaret(self, obj):
		"""Tell the braille display that the caret moved.

		This must be called on every caret and typed-character event we
		handle, BEFORE any speech-suppression early return.

		The overlay never falls through to NVDA's native event_caret (that
		would double-speak and announce "blank" after Enter), and NVDA's
		braille caret tracking rides on that native handler. So if we do
		not do this ourselves, nothing does: the display keeps showing
		stale content until the user pans away and back, and it never
		tethers to the cursor while typing. That was a shipped bug through
		2.0.x, reported by a braille user.

		Speech and braille are separate output channels. Deliberately not
		gated on quiet mode or cursorTracking: those silence *speech*, and
		a braille reader who turns them off still needs the display to
		follow the cursor. Unlike _brailleMessage (a transient flash),
		this moves the display's tether, which is what makes typed text
		show up under the fingers.
		"""
		try:
			if braille.handler.displaySize > 0:
				braille.handler.handleCaretMove(obj)
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

	def _handleTerminalCaret(self, obj):
		"""Handle a caret movement event in a terminal.

		Called from the overlay's event_caret. The overlay never falls
		through to NVDA's native caret handling for terminals: our own
		_announceCursorPosition does the speech with debouncing, blank
		suppression, and error audio cues. In quiet mode nothing is spoken.
		"""
		isQuietMode = self._configManager.get("quietMode")

		# Braille first, unconditionally: the overlay suppressed NVDA's
		# native caret handling (and with it NVDA's braille tracking), so
		# every early return below would otherwise leave the display
		# stranded on stale content.
		self._updateBrailleCaret(obj)

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

		# Output-induced caret suppression: when textChange fires (program
		# output), the cursor moves to the end of new content as a side
		# effect. This caret movement should not speak characters.
		# User navigation (arrow keys) has no preceding textChange.
		if self._configManager.get("streamingSuppression", True):
			elapsed = time.monotonic() - self._lastTextChangeTime
			if elapsed < self._OUTPUT_CARET_GRACE:
				return

		# Cancel any pending cursor tracking announcement
		if self._cursorTrackingTimer:
			self._cursorTrackingTimer.Stop()
			self._cursorTrackingTimer = None

		# Schedule announcement with delay
		self._cursorTrackingTimer = wx.CallLater(
			self._configManager.get("cursorDelay", 20), self._announceCursorPosition, obj
		)

	def _handleTerminalTextChange(self, obj):
		"""Handle a terminal text-content change (called from the overlay).

		Fires when the buffer content changes (program output). Unlike a
		caret event, this fires even when the caret stays in place (output
		scrolling above the input line). Handles the output-caret timestamp,
		progress milestones, activity tones, and quiet-mode error detection.

		Returns True if the overlay should wake the live-text monitor to
		speak the new output (normal mode), or False to stay silent (quiet
		mode).
		"""
		isQuietMode = self._configManager.get("quietMode")

		# Record timestamp so the caret handler knows this cursor movement
		# was caused by output, not user navigation.
		self._lastTextChangeTime = time.monotonic()

		# New output invalidates the search manager's cached buffer so the
		# next search re-reads. Cheap (an int bump).
		searchManager = getattr(self, "_searchManager", None)
		if searchManager is not None:
			searchManager.note_content_changed()

		if self._configManager.get("progressMilestones", True):
			self._checkProgressMilestone(obj)

		if self._configManager.get("outputActivityTones", False):
			self._checkOutputActivityTone()

		if isQuietMode:
			if (self._configManager.get("errorAudioCues", True)
					and self._configManager.get("errorAudioCuesInQuietMode", False)):
				self._checkErrorAudioCue()

		return not isQuietMode

	def _checkProgressMilestone(self, terminal=None):
		"""Announce a progress milestone found on the last buffer line.

		Called from event_textChange with the terminal object that changed.
		Reads that terminal's last line (not self._boundTerminal, which may
		be a different or unfocused terminal). Throttled to one buffer read
		per _PROGRESS_CHECK_INTERVAL because textChange fires rapidly during
		streaming output and each read costs COM/UIA calls.
		"""
		if terminal is None:
			terminal = self._boundTerminal
		now = time.monotonic()
		if (now - self._lastProgressCheckTime) < self._PROGRESS_CHECK_INTERVAL:
			return
		self._lastProgressCheckTime = now
		try:
			info = terminal.makeTextInfo(textInfos.POSITION_LAST)
			info.expand(textInfos.UNIT_LINE)
			milestone = self._progressTracker.update(info.text)
			if milestone is not None:
				# Translators: Spoken when terminal output reaches a progress
				# milestone, for example 25, 50, 75, or 100 percent.
				ui.message(_("{percent} percent").format(percent=milestone))
		except (RuntimeError, AttributeError, TypeError, LookupError):
			pass

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
			if classification:
				play_cue(classification)
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
		# Re-check output grace: a textChange may have arrived after
		# this callback was scheduled by wx.CallLater in event_caret.
		if self._configManager.get("streamingSuppression", True):
			elapsed = time.monotonic() - self._lastTextChangeTime
			if elapsed < self._OUTPUT_CARET_GRACE:
				return

		try:
			trackingMode = self._getEffective("cursorTrackingMode")
			match trackingMode:
				case 0:  # CT_OFF
					return
				case 1:  # CT_STANDARD
					self._announceStandardCursor(obj)
				case 2:  # CT_WINDOW
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
		# bookmark is part of the TextInfo contract, but it raises on some
		# terminals (conhost) rather than being absent, which is exactly the
		# case hasattr would silently mistake for "no such attribute".
		try:
			currentPos = info.bookmark.startOffset
		except (AttributeError, RuntimeError, NotImplementedError):
			currentPos = None
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
			output_grace = (time.monotonic() - self._lastTextChangeTime) < self._OUTPUT_CARET_GRACE
			if not _retry and not output_grace:
				try:
					wx.CallLater(50, self._announceStandardCursor, obj, True)
					wx.CallLater(150, self._announceStandardCursor, obj, True)
				except (RuntimeError, AttributeError):
					pass
			return

		self._speakCharacter(char)

		# Re-assert the braille tether after speaking: _speakCharacter can
		# emit a transient braille message, and this puts the display back
		# on the caret with its line context. (The unconditional update at
		# the top of _handleTerminalCaret is what guarantees braille moves
		# at all; this is the post-speech refresh.)
		self._updateBrailleCaret(obj)

	# DEPRECATED: Scheduled for removal in v2.0
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

	# No direct gesture on purpose: replay is reachable from the command
	# layer (NVDA+apostrophe, then Shift+H) to keep the gesture surface small.
	@script(
		# Translators: Description for replaying the first-run tutorial
		description=_("Replay the Terminal Access spoken tutorial"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_replayTutorial(self, gesture):
		"""Speak the first-run tutorial on demand."""
		if not self.isTerminalApp():
			gesture.send()
			return
		from lib.tutorial import build_tutorial_message
		ui.message(build_tutorial_message())

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
	# Table Mode — modal column-aware reading of tabular output
	# ------------------------------------------------------------------

	@script(
		# Translators: Description for toggling table mode
		description=_("Toggle table mode for column-aware reading of tabular terminal output"),
		gesture="kb:NVDA+alt+g",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_toggleTableMode(self, gesture):
		"""Enter or leave table mode on the table under the review cursor."""
		if not self.isTerminalApp():
			gesture.send()
			return
		if self._tableNavigator is not None:
			self._exitTableModeBindings(announce=True)
			return

		lines = self._getBufferLines()
		region = None
		if lines:
			current = self._getCurrentLineNumber()
			region = TableDetector().detect(lines, current if current is not None else 0)
		if region is None:
			# Translators: Message when table mode finds no table on the current line
			ui.message(_("No table at this position"))
			return

		navigator = TableNavigator(region, lines)
		if navigator.n_rows < 1 or navigator.n_cols < 1:
			# Translators: Message when table mode finds no table on the current line
			ui.message(_("No table at this position"))
			return

		self._tableNavigator = navigator
		self._tableRow = 0
		self._tableCol = 0
		for gesture_id, script_name in _TABLE_MODE_BINDINGS.items():
			try:
				self.bindGesture(gesture_id, script_name)
			except (KeyError, AttributeError):
				pass
		# Translators: Announced when table mode starts. {rows} and {cols}
		# are the table dimensions.
		ui.message(_(
			"Table mode. {rows} rows, {cols} columns. "
			"Use arrows to move, Escape to exit."
		).format(rows=navigator.n_rows, cols=navigator.n_cols))

	def _exitTableModeBindings(self, announce=False):
		"""Leave table mode, unbind its keys and restore layer bindings."""
		self._tableNavigator = None
		self._tableRow = 0
		self._tableCol = 0
		for gesture_id in _TABLE_MODE_BINDINGS:
			try:
				self.removeGestureBinding(gesture_id)
			except (KeyError, AttributeError):
				pass
		# If the command layer is active, re-bind the layer gestures that
		# table mode temporarily overwrote (home, end, escape).
		if getattr(self, "_inCommandLayer", False):
			for gesture_id in _TABLE_MODE_BINDINGS:
				if gesture_id in _COMMAND_LAYER_MAP:
					try:
						self.bindGesture(gesture_id, _COMMAND_LAYER_MAP[gesture_id])
					except (KeyError, AttributeError):
						pass
		if announce:
			# Translators: Announced when table mode ends
			ui.message(_("Table mode off"))

	def _tableMove(self, gesture, drow, dcol):
		"""Move the table cursor by a row/column delta and speak the cell."""
		navigator = self._tableNavigator
		if navigator is None:
			gesture.send()
			return
		result = navigator.move(self._tableRow, self._tableCol, drow, dcol)
		if result is None:
			# Translators: Message when table navigation hits the table boundary
			ui.message(_("Edge of table"))
			return
		self._tableRow, self._tableCol = result
		ui.message(navigator.announce_for(self._tableRow, self._tableCol))

	@script(
		# Translators: Description for moving to the previous table row
		description=_("Move to the previous row in table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_tablePreviousRow(self, gesture):
		"""Move up one table row."""
		self._tableMove(gesture, -1, 0)

	@script(
		# Translators: Description for moving to the next table row
		description=_("Move to the next row in table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_tableNextRow(self, gesture):
		"""Move down one table row."""
		self._tableMove(gesture, 1, 0)

	@script(
		# Translators: Description for moving to the previous table column
		description=_("Move to the previous column in table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_tablePreviousColumn(self, gesture):
		"""Move left one table column."""
		self._tableMove(gesture, 0, -1)

	@script(
		# Translators: Description for moving to the next table column
		description=_("Move to the next column in table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_tableNextColumn(self, gesture):
		"""Move right one table column."""
		self._tableMove(gesture, 0, 1)

	@script(
		# Translators: Description for jumping to the first table column
		description=_("Move to the first column in table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_tableFirstColumn(self, gesture):
		"""Jump to the first column of the current row."""
		navigator = self._tableNavigator
		if navigator is None:
			gesture.send()
			return
		self._tableCol = 0
		ui.message(navigator.announce_for(self._tableRow, self._tableCol))

	@script(
		# Translators: Description for jumping to the last table column
		description=_("Move to the last column in table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_tableLastColumn(self, gesture):
		"""Jump to the last column of the current row."""
		navigator = self._tableNavigator
		if navigator is None:
			gesture.send()
			return
		self._tableCol = max(navigator.n_cols - 1, 0)
		ui.message(navigator.announce_for(self._tableRow, self._tableCol))

	@script(
		# Translators: Description for announcing the current column header
		description=_("Announce the header of the current column in table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_tableColumnHeader(self, gesture):
		"""Speak the header of the current column without moving."""
		navigator = self._tableNavigator
		if navigator is None:
			gesture.send()
			return
		ui.message(navigator.announce_for(0, self._tableCol))

	@script(
		# Translators: Description for reading the whole current table row
		description=_("Read the current row with headers in table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_tableRowSummary(self, gesture):
		"""Speak every cell of the current row with its header."""
		navigator = self._tableNavigator
		if navigator is None:
			gesture.send()
			return
		ui.message(navigator.row_summary(self._tableRow))

	@script(
		# Translators: Description for exiting table mode
		description=_("Exit table mode"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_exitTableMode(self, gesture):
		"""Leave table mode and restore normal keys."""
		if self._tableNavigator is None:
			gesture.send()
			return
		self._exitTableModeBindings(announce=True)

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
		# If table mode is active, exit it first so layer keys win
		if self._tableNavigator is not None:
			self._exitTableModeBindings()
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
		"""Cycle through cursor tracking modes: Off -> Standard -> Window -> Off."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Get current mode
		currentMode = self._getEffective("cursorTrackingMode")

		# Cycle to next mode: 0 (Off) -> 1 (Standard) -> 2 (Window) -> 0 (Off)
		nextMode = (currentMode + 1) % 3

		# Update configuration
		config.conf["terminalAccess"]["cursorTrackingMode"] = nextMode
		if self._currentProfile is not None and self._currentProfile.cursorTrackingMode is not None:
			self._currentProfile.cursorTrackingMode = nextMode

		# Announce new mode
		modeNames = {
			CT_OFF: _("Cursor tracking off"),
			CT_STANDARD: _("Standard cursor tracking"),
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
			if classification:
				play_cue(classification)

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

	#: Substituted for a typed character while typing is protected,
	#: matching NVDA's speech.PROTECTED_CHAR.
	_PROTECTED_CHAR = "*"

	def _clear_typing_echo_state(self):
		"""Discard partial words and symbol runs without speaking them."""
		self._typedWordChars = []
		self._lastTypedChar = None
		self._repeatedCharCount = 0

	def _echoTypedWord(self, ch):
		"""Accumulate typed characters and speak each completed word.

		Mirrors the rules in NVDA's speakTypedCharacters: letters, marks
		and numbers build the word; backspace removes the last character;
		the delete character produced by control+backspace is ignored;
		anything else ends the word.

		A completed word is never spoken while typing is protected. A
		password is exactly a run of characters ending in Enter, so
		speaking the "word" would read it aloud in full. The buffer is
		discarded in that case rather than kept.
		"""
		if self._isTypingProtected():
			self._clear_typing_echo_state()
			return
		if not self._getEffective("wordEcho"):
			# Keep the buffer clean so enabling word echo mid-session does
			# not speak a word half-collected while it was off.
			self._typedWordChars = []
			return
		if ch == "":
			return
		if ch == "\b":
			del self._typedWordChars[-1:]
			return
		if ch and unicodedata.category(ch)[0] in "LMN":
			self._typedWordChars.append(ch)
			return
		# Any other character closes the current word.
		word = "".join(self._typedWordChars)
		self._typedWordChars = []
		if word and not self._isTypingProtected():
			ui.message(word)

	def _isTypingProtected(self) -> bool:
		"""True when the focused control masks what is typed into it.

		Fails toward True: if the state cannot be determined, mask. An
		unnecessary mask is a small annoyance; speaking a password aloud
		is not recoverable.
		"""
		try:
			return bool(api.isTypingProtected())
		except Exception:
			return True

	def _speakCharacter(self, char):
		"""Speak a single character, handling space and blank specially.

		While typing is protected the character is replaced with a mask
		before it can reach speech, exactly as NVDA does. The keystroke
		is still announced rather than dropped, so the user knows it
		registered.
		"""
		if self._isTypingProtected():
			ui.message(self._resolveSymbol(self._PROTECTED_CHAR))
			return
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
		elif self._bookmarkManager.is_full_for(name):
			# Translators: Announced when the per-window bookmark limit is
			# reached and a new bookmark cannot be added.
			ui.message(_("Bookmark limit reached ({limit}). Delete a bookmark first.").format(
				limit=self._bookmarkManager.max_bookmarks))
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
		# No direct gesture: NVDA+alt+s belongs to summarizeLastCommand.
		# Available as Shift+S in the command layer or via Input Gestures.
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

	# Command finder (v2.1.0+)

	@scriptHandler.script(
		# Translators: Description for the command finder
		description=_("Open a searchable list of all Terminal Access commands"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+h"
	)
	def script_findCommand(self, gesture):
		"""Open a searchable list of all Terminal Access commands."""
		if not self.isTerminalApp():
			gesture.send()
			return

		from lib.list_dialogs import collect_commands
		commands = collect_commands(self)
		if not commands:
			# Translators: Message when no commands could be collected
			ui.message(_("No commands available"))
			return

		wx.CallAfter(self._showCommandFinderDialog, commands)

	def _showCommandFinderDialog(self, commands):
		"""Open the command finder dialog on the main thread."""
		from lib.list_dialogs import BrowsableListDialog
		import gui
		rows = [
			(cmd["name"], cmd["description"], cmd["gesture_display"])
			for cmd in commands
		]
		try:
			gui.mainFrame.prePopup()
			dlg = BrowsableListDialog(
				gui.mainFrame,
				# Translators: Title of the command finder dialog
				title=_("Terminal Access Commands"),
				columns=[
					# Translators: Column header for the command name
					(_("Command"), 160),
					# Translators: Column header for the command description
					(_("Description"), 300),
					# Translators: Column header for the command gesture
					(_("Gesture"), 220),
				],
				rows=rows,
				on_activate=lambda index: self._announceCommandInvocation(
					commands[index]
				),
				enable_search=True,
				search_columns=(0, 1),
			)
			dlg.ShowModal()
			dlg.Destroy()
		finally:
			gui.mainFrame.postPopup()

	def _announceCommandInvocation(self, command):
		"""Announce how to invoke a command without executing it."""
		bindings = []
		if command["gesture_display"]:
			bindings.append(command["gesture_display"])
		if command["layer_key"]:
			# Translators: How to invoke a command from the command layer
			bindings.append(
				_("command layer {key}").format(key=command["layer_key"])
			)
		if bindings:
			# Translators: Announces the gesture bindings of a command
			ui.message(_("{name}: {bindings}").format(
				name=command["name"], bindings="; ".join(bindings)
			))
		else:
			# Translators: Announced for a command with no gesture assigned
			ui.message(_("{name} has no gesture assigned").format(
				name=command["name"]
			))

	# Transcript export (v2.1.0+)

	@scriptHandler.script(
		# Translators: Description for exporting the terminal transcript
		description=_("Export the terminal transcript to a text file"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+x"
	)
	def script_exportTranscript(self, gesture):
		"""Export the terminal buffer to a plain text file."""
		if not self.isTerminalApp():
			gesture.send()
			return

		lines = self._getBufferLines()
		if not lines:
			# Translators: Message when terminal buffer cannot be read
			ui.message(_("Cannot read terminal buffer"))
			return

		wx.CallAfter(self._showExportTranscriptDialog, lines)

	def _showExportTranscriptDialog(self, lines):
		"""Prompt for a save location and write the transcript file."""
		from lib.list_dialogs import export_transcript_text
		import gui
		path = None
		try:
			gui.mainFrame.prePopup()
			dlg = wx.FileDialog(
				gui.mainFrame,
				# Translators: Title of the transcript save dialog
				message=_("Save transcript"),
				defaultDir=os.path.expanduser("~"),
				defaultFile="terminal-transcript.txt",
				# Translators: File type filter in the transcript save dialog
				wildcard=_("Text files (*.txt)|*.txt|All files (*.*)|*.*"),
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
			)
			try:
				if dlg.ShowModal() == wx.ID_OK:
					path = dlg.GetPath()
			finally:
				dlg.Destroy()
		finally:
			gui.mainFrame.postPopup()
		if not path:
			return
		try:
			with open(path, "w", encoding="utf-8") as transcript_file:
				transcript_file.write(export_transcript_text(lines))
			# Translators: Announced after the transcript file is written
			ui.message(_("Transcript saved"))
		except OSError:
			# Translators: Announced when the transcript file cannot be written
			ui.message(_("Unable to save transcript"))

	# Buffer window (see docs/plans/20260717-terminal-buffer-virtual-window.md)

	@script(
		# Translators: Description for opening the terminal buffer window
		description=_(
			"Open the terminal buffer in a browsable window. "
			"Arrow through it, navigate by heading, and press escape to close."
		),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+enter",
	)
	def script_showBufferWindow(self, gesture):
		"""Open a frozen snapshot of the terminal buffer in browse mode."""
		if not self.isTerminalApp():
			gesture.send()
			return
		self._openBufferWindow(gesture)

	@script(
		# Translators: Description for opening the errors-only buffer window
		description=_(
			"Open only the errors, warnings, and stack traces from the "
			"terminal buffer in a browsable window."
		),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_showErrorsWindow(self, gesture):
		"""Open a browsable window of only the buffer's problems."""
		if not self.isTerminalApp():
			gesture.send()
			return
		self._openBufferWindow(
			gesture,
			categories=frozenset({"error", "warning", "stack_trace"}),
			# Translators: Names the errors-only filter in the window title
			filter_label=_("errors only"),
			# Translators: Announced when the errors-only window has nothing
			# to show
			empty_message=_("No errors in the terminal buffer"),
		)

	@script(
		# Translators: Description for opening the commands-only buffer window
		description=_(
			"Open only the commands you ran, from the terminal buffer, "
			"in a browsable window."
		),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_showCommandsWindow(self, gesture):
		"""Open a browsable window of only the commands run."""
		if not self.isTerminalApp():
			gesture.send()
			return
		self._openBufferWindow(
			gesture,
			categories=frozenset({"prompt"}),
			# Translators: Names the commands-only filter in the window title
			filter_label=_("commands only"),
			# Translators: Announced when the commands-only window has
			# nothing to show
			empty_message=_("No commands found in the terminal buffer"),
		)

	def _openBufferWindow(self, gesture, categories=None,
			filter_label=None, empty_message=None):
		"""Shared open path for the full and filtered buffer windows."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# The COM/UIA read stays on this (main) thread, where NVDA's
		# watchdog can cancel a stuck call; worker-thread COM is what
		# deadlocked in 2.0.0-beta.3. Only the CPU-heavy render moves off.
		lines = self._getBufferLines()
		if not lines:
			# Translators: Message when terminal buffer cannot be read
			ui.message(_("Cannot read terminal buffer"))
			return
		from lib.buffer_snapshot import BufferSnapshot
		snapshot = BufferSnapshot.capture(self._boundTerminal, lines)
		import threading
		worker_args = (snapshot,) if categories is None else (
			snapshot, categories, filter_label, empty_message)
		threading.Thread(
			target=self._bufferWindowWorker,
			args=worker_args,
			name="TerminalAccessBufferWindow",
			daemon=True,
		).start()

	def _bufferWindowWorker(self, snapshot, categories=None,
			filter_label=None, empty_message=None):
		"""Render the snapshot to HTML off the main thread, then present.

		Tokenization runs here too: it is pure CPU over the captured
		lines and has no business on the main thread. A filtered render
		that matches nothing announces instead of opening empty.
		"""
		from lib import buffer_html
		from lib.section_tokenizer import SectionTokenizer
		tokenizer = SectionTokenizer()
		tokenizer.tokenize(snapshot.lines)
		spans = tokenizer.get_spans()
		if categories is None:
			html_doc = buffer_html.render(snapshot, spans)
		else:
			html_doc = buffer_html.render_filtered(snapshot, spans, categories)
			if not html_doc:
				wx.CallAfter(ui.message, empty_message)
				return
		title = buffer_html.window_title(snapshot, filter_label=filter_label)
		wx.CallAfter(self._presentBufferWindow, html_doc, title)

	def _presentBufferWindow(self, html_doc, title):
		"""Show the rendered snapshot (main thread).

		The identity sanitizeHtmlFunc is deliberate: every line was
		escaped on the worker (lib.buffer_html.escape_line is the
		security boundary), and browseableMessage's default nh3.clean
		would otherwise run on the main thread over the whole document.
		"""
		try:
			ui.browseableMessage(
				html_doc,
				title=title,
				isHtml=True,
				copyButton=True,
				sanitizeHtmlFunc=lambda sanitized: sanitized,
			)
		except Exception:
			# browseableMessage warns-and-returns on secure desktops but can
			# raise on MSHTML component failure; the user must hear something
			# rather than silence.
			# Translators: Announced when the buffer window cannot be shown
			ui.message(_("Unable to show the buffer window"))

	@script(
		# Translators: Description for the jump-to-line dialog
		description=_(
			"Open a list of every line in the terminal buffer, "
			"with the command that produced it. Press enter on a line "
			"to move the review cursor there."
		),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+shift+enter",
	)
	def script_jumpToBufferLine(self, gesture):
		"""Open the jump-to-line list for the terminal buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# COM read on the main thread (watchdog-cancellable), CPU work on
		# the worker: same split as the buffer window and search.
		lines = self._getBufferLines()
		if not lines:
			# Translators: Message when terminal buffer cannot be read
			ui.message(_("Cannot read terminal buffer"))
			return
		from lib.buffer_snapshot import BufferSnapshot
		snapshot = BufferSnapshot.capture(self._boundTerminal, lines)
		import threading
		threading.Thread(
			target=self._jumpDialogWorker,
			args=(snapshot,),
			name="TerminalAccessJumpList",
			daemon=True,
		).start()

	def _jumpDialogWorker(self, snapshot):
		"""Tokenize and build the jump rows off the main thread."""
		from lib.list_dialogs import build_jump_rows
		from lib.section_tokenizer import SectionTokenizer
		tokenizer = SectionTokenizer()
		sections = tokenizer.tokenize(snapshot.lines)
		rows = build_jump_rows(snapshot, sections)
		wx.CallAfter(self._showJumpToLineDialog, snapshot, rows)

	def _showJumpToLineDialog(self, snapshot, rows):
		"""Open the modal jump list (main thread).

		Selection arms the same reapply machinery the search results
		dialog uses: _searchJumpPending suppresses the focus-return
		cursor reset, and _searchJumpTarget carries (text, line number)
		so the landing is resolved by content after NVDA's focus
		transition settles, never by counting lines.
		"""
		from lib.list_dialogs import BrowsableListDialog
		import gui

		def on_activate(index):
			# Do NOT consult _boundTerminal here: focus is on this dialog,
			# so the global focus handler has already nulled it (that check
			# shipped as a bug that made every jump announce "no longer
			# available"). The reapply machinery resolves through the
			# search manager, which keeps its own terminal binding, exactly
			# like the search results dialog. No manager at all means no
			# terminal was ever focused, and nothing could resolve the
			# landing.
			if self._searchManager is None:
				# Translators: Announced when jumping fails because the
				# terminal window has gone away
				ui.message(_("The terminal is no longer available"))
				return
			line_num, text, _context = rows[index]
			self._searchJumpPending = True
			self._searchJumpTarget = (text, line_num)
			if text.strip():
				ui.message(text)

		display_rows = [
			(str(line_num + 1), text, context)
			for line_num, text, context in rows
		]
		try:
			gui.mainFrame.prePopup()
			dlg = BrowsableListDialog(
				gui.mainFrame,
				# Translators: Title of the jump-to-line dialog. {terminal}
				# is the terminal application's name.
				title=_("Jump to line - {terminal}").format(
					terminal=snapshot.terminal_name),
				columns=[
					# Translators: Column header for the line number
					(_("Line"), 80),
					# Translators: Column header for the line's text
					(_("Text"), 420),
					# Translators: Column header for the command that
					# produced the line
					(_("Command"), 260),
				],
				rows=display_rows,
				on_activate=on_activate,
				enable_search=True,
				search_columns=[1, 2],
			)
			dlg.ShowModal()
			dlg.Destroy()
		finally:
			gui.mainFrame.postPopup()

	@script(
		# Translators: Description for saving a diagnostic issue report
		description=_("Save a diagnostic issue report for the current terminal"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_reportIssue(self, gesture):
		"""Save a diagnostic report the user can attach to a bug report."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			# Translators: Message when terminal buffer cannot be read
			ui.message(_("Cannot read terminal buffer"))
			return
		stripped = [_rt.strip_ansi(line) for line in lines]
		context = self._collectDiagnosticContext()
		wx.CallAfter(self._showIssueReportDialog, context, stripped)

	def _collectDiagnosticContext(self):
		"""Gather environment fields for a diagnostic report."""
		context = {}
		try:
			import addonHandler
			context["addon_version"] = addonHandler.getCodeAddon().manifest["version"]
		except Exception:
			context["addon_version"] = "unknown"
		try:
			import versionInfo
			context["nvda_version"] = versionInfo.version
		except Exception:
			context["nvda_version"] = "unknown"
		context["terminal_app"] = getattr(self, "lastTerminalAppName", None)
		try:
			context["window_title"] = self._boundTerminal.name
		except Exception:
			context["window_title"] = ""
		context["profile"] = (
			self._currentProfile.displayName if self._currentProfile else "none"
		)
		context["verbosity_level"] = self._verbosityLevel()
		context["review_line"] = self._getCurrentLineNumber()
		return context

	def _showIssueReportDialog(self, context, lines):
		"""Prompt for a save location and write the diagnostic report."""
		from lib.diagnostics import build_issue_report
		import gui
		path = None
		try:
			gui.mainFrame.prePopup()
			dlg = wx.FileDialog(
				gui.mainFrame,
				# Translators: Title of the issue report save dialog
				message=_("Save issue report"),
				defaultDir=os.path.expanduser("~"),
				defaultFile="terminal-access-report.txt",
				# Translators: File type filter in the issue report save dialog
				wildcard=_("Text files (*.txt)|*.txt|All files (*.*)|*.*"),
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
			)
			try:
				if dlg.ShowModal() == wx.ID_OK:
					path = dlg.GetPath()
			finally:
				dlg.Destroy()
		finally:
			gui.mainFrame.postPopup()
		if not path:
			return
		try:
			with open(path, "w", encoding="utf-8") as report_file:
				report_file.write(build_issue_report(context, lines))
			# Translators: Announced after the issue report file is written
			ui.message(_("Issue report saved"))
		except OSError:
			# Translators: Announced when the issue report file cannot be written
			ui.message(_("Unable to save issue report"))

	# Section 8.5: AI turn list gesture (v1.5.0+)

	@scriptHandler.script(
		# Translators: Description for listing AI conversation turns
		description=_("List all AI conversation turns in the terminal buffer"),
		category=SCRCAT_TERMINALACCESS,
		gesture="kb:NVDA+alt+shift+l"
	)
	def script_listAiTurns(self, gesture):
		"""List all AI conversation turns in an accessible dialog."""
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

		turns = self._bookmarkManager.list_ai_turns(lines)
		if not turns:
			# Translators: Message when no AI turns detected
			ui.message(_("No AI turns detected"))
			return

		# Translators: Announced when AI turn list is loading with count
		ui.message(_("{count} AI turns found").format(count=len(turns)))
		wx.CallAfter(self._showAiTurnDialog, turns)

	def _showAiTurnDialog(self, turns):
		"""Open the AI turn list dialog on the main thread."""
		from lib.navigation import AiTurnListDialog
		import gui
		try:
			gui.mainFrame.prePopup()
			dlg = AiTurnListDialog(
				gui.mainFrame, turns, self._jumpToLine
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
			# At normal and verbose verbosity, speak the number of matches.
			verbosity = self._verbosityLevel()
			if should_speak(verbosity, "search_count"):
				if match_count == 1:
					# Translators: Announced when a search finds a single match
					ui.message(_("1 match"))
				else:
					# Translators: Announced with the number of search matches
					ui.message(_("{count} matches").format(count=match_count))
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
			"""Prompt for text and options, run the search, show results."""
			result = None
			try:
				gui.mainFrame.prePopup()
				result = self._promptForSearch()
			except Exception:
				try:
					import logHandler
					logHandler.log.error("Search dialog failed", exc_info=True)
				except Exception:
					pass
			finally:
				gui.mainFrame.postPopup()

			if not result or not result[0]:
				self._searchDialogOpen = False
				return

			search_text, case_sensitive, use_regex = result
			# Remember the options for the next search this session.
			self._searchCaseSensitive = case_sensitive
			self._searchUseRegex = use_regex

			# Run the search (matching moves off the main thread for large
			# buffers) and present results when it completes.
			self._runTerminalSearch(
				search_text, self._presentSearchResults,
				case_sensitive=case_sensitive, use_regex=use_regex)

		# Run dialog in main thread
		wx.CallAfter(show_search_dialog)

	def _promptForSearch(self):
		"""Show the search dialog with case-sensitive and regular-expression
		options. Returns (text, case_sensitive, use_regex), or None if the
		dialog was cancelled. The option checkboxes default to the last-used
		values (self._searchCaseSensitive / self._searchUseRegex)."""
		import wx
		dlg = wx.Dialog(gui.mainFrame, title=_("Search Terminal Output"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: Prompt in the terminal search dialog
		sizer.Add(wx.StaticText(dlg, label=_("Enter search text:")),
				  flag=wx.ALL, border=8)
		text_ctrl = wx.TextCtrl(dlg, style=wx.TE_PROCESS_ENTER)
		sizer.Add(text_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)
		# Translators: Search option: match letter case exactly
		case_cb = wx.CheckBox(dlg, label=_("&Case sensitive"))
		case_cb.SetValue(bool(getattr(self, "_searchCaseSensitive", False)))
		sizer.Add(case_cb, flag=wx.ALL, border=8)
		# Translators: Search option: treat the text as a regular expression
		regex_cb = wx.CheckBox(dlg, label=_("Regular &expression"))
		regex_cb.SetValue(bool(getattr(self, "_searchUseRegex", False)))
		sizer.Add(regex_cb, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)
		buttons = dlg.CreateButtonSizer(wx.OK | wx.CANCEL)
		if buttons:
			sizer.Add(buttons, flag=wx.EXPAND | wx.ALL, border=8)
		dlg.SetSizerAndFit(sizer)
		# Enter in the text field submits the dialog.
		text_ctrl.Bind(wx.EVT_TEXT_ENTER, lambda e: dlg.EndModal(wx.ID_OK))
		text_ctrl.SetFocus()
		try:
			if dlg.ShowModal() == wx.ID_OK:
				return (text_ctrl.GetValue(), case_cb.GetValue(),
						regex_cb.GetValue())
			return None
		finally:
			dlg.Destroy()

	# Buffers at or above this size (characters) have their matching run on a
	# worker thread so a large scrollback cannot block NVDA during a search.
	_SEARCH_ASYNC_THRESHOLD = 200_000

	def _runTerminalSearch(self, search_text, on_complete,
						   case_sensitive=False, use_regex=False):
		"""Read the terminal buffer, then match and deliver the count.

		The buffer read happens on the main thread (makeTextInfo is
		main-thread-affine). For a large buffer the ANSI strip and matching run on a worker
		thread, and the result is marshalled back with wx.CallAfter so
		on_complete always runs on the main thread.
		"""
		import wx
		mgr = self._searchManager
		if mgr is None:
			on_complete(search_text, 0)
			return

		# Fail fast (on the main thread) on an invalid regular expression
		# rather than silently returning zero matches from a worker.
		if use_regex:
			import re
			try:
				re.compile(search_text)
			except re.error as exc:
				# Translators: announced when a search regular expression is invalid
				ui.message(_("Invalid regular expression: {error}").format(error=exc))
				self._searchDialogOpen = False
				return

		try:
			raw_text = mgr._acquire_raw_text()
		except Exception:
			raw_text = None

		# Plain-text search runs synchronously whatever the buffer size.
		# Threading cannot make a search faster (nothing is known about the
		# text in advance), and Python's substring scan over a real terminal
		# buffer (a terminal caps its own scrollback near 9,000 lines, so
		# roughly a megabyte) completes in milliseconds. The thread only
		# bought the ability to use NVDA during that millisecond, at the
		# cost of a concurrency path to get wrong.
		#
		# A user-supplied regular expression is the exception, and the
		# reason the worker survives: a pattern like (a+)+b backtracks
		# catastrophically and can spin for minutes on a large buffer.
		# That would freeze NVDA's main thread, which is the one failure
		# this project treats as unacceptable.
		if not use_regex or not raw_text or len(raw_text) < self._SEARCH_ASYNC_THRESHOLD:
			try:
				count = mgr.search(search_text, case_sensitive=case_sensitive,
									use_regex=use_regex, raw_text=raw_text)
			except Exception:
				count = 0
			on_complete(search_text, count)
			return

		# Large buffer AND a user-supplied regex: match off the main thread,
		# so a catastrophically backtracking pattern cannot freeze NVDA.
		# Translators: Spoken while a search of a large terminal buffer runs.
		ui.message(_("Searching"))

		def worker():
			try:
				count = mgr.search(search_text, case_sensitive=case_sensitive,
									use_regex=use_regex, raw_text=raw_text)
			except Exception:
				count = 0
			wx.CallAfter(on_complete, search_text, count)

		import threading
		threading.Thread(target=worker, name="TerminalAccessSearch",
						 daemon=True).start()

	def _presentSearchResults(self, search_text, match_count):
		"""Announce the outcome and show the results dialog (main thread)."""
		try:
			if self._handleSearchResult(search_text, match_count):
				# Show results in a browsable dialog instead of auto-jumping.
				# The dialog's Jump handler sets _searchJumpPending so
				# event_gainFocus won't reset the review cursor.
				from lib.search import SearchResultsDialog

				def on_jump():
					self._searchJumpPending = True
					# Capture the activated line's text now, while the match
					# state is intact. The re-apply after focus returns must
					# not depend on the search manager's matches (they get
					# cleared when focus returns to the terminal); it resolves
					# the review position from this text directly.
					try:
						info = self._searchManager.get_current_match_info()
						self._searchJumpTarget = (info[2], info[3]) if info else None
					except Exception:
						self._searchJumpTarget = None

				try:
					gui.mainFrame.prePopup()
					results_dlg = SearchResultsDialog(
						gui.mainFrame, self._searchManager, on_jump)
					results_dlg.ShowModal()
					results_dlg.Destroy()
				finally:
					gui.mainFrame.postPopup()
		except Exception:
			try:
				import logHandler
				logHandler.log.error("Search results failed", exc_info=True)
			except Exception:
				pass
		finally:
			self._searchDialogOpen = False

	def _navigateSearch(self, direction):
		"""Navigate to the next or previous search match.

		Args:
			direction: 'next' or 'previous'.
		"""
		if not self._searchManager:
			return

		# Refresh the results if the terminal produced output since the
		# search ran, so navigation reflects the live buffer.
		try:
			self._searchManager.refresh_search_if_stale()
		except Exception:
			pass

		if self._searchManager.get_match_count() == 0:
			# Translators: No search results
			ui.message(_("No search results. Use NVDA+F to search."))
			return

		before = self._searchManager.get_current_match_info()
		old_num = before[0] if before else None

		move_fn = self._searchManager.next_match if direction == "next" else self._searchManager.previous_match
		if move_fn():
			info = self._searchManager.get_current_match_info()
			if info:
				match_num, total, line_text, line_num = info
				wrapped = old_num is not None and (
					(direction == "next" and match_num < old_num)
					or (direction == "previous" and match_num > old_num)
				)
				ui.message(self._format_search_match_message(
					line_text, match_num, total, wrapped))
		else:
			# Translators: Error jumping to search match
			ui.message(_("Cannot jump to {direction} match").format(direction=direction))

	@staticmethod
	def _format_search_match_message(line_text, match_num, total, wrapped):
		"""Build the spoken message for a search match: content, then its
		position, prefixed with a wrap cue when find next/previous looped
		around to the other end of the results."""
		# Translators: a search match's position among the results, e.g. "3 of 5"
		position = _("{num} of {total}").format(num=match_num, total=total)
		if wrapped:
			# Translators: spoken when find next/previous wraps to the other end
			return _("Wrapped, {line}, {position}").format(
				line=line_text, position=position)
		# Translators: a search match line followed by its position
		return _("{line}, {position}").format(line=line_text, position=position)

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
		# Legacy console: NVDA exposes only the visible window, so read the
		# whole screen buffer ourselves. Returns None when that is not
		# possible, which falls through to the normal path below.
		from lib.legacy_console import is_attached_console, read_full_buffer_lines
		if is_attached_console(terminal):
			lines = read_full_buffer_lines()
			if lines:
				return lines
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
			# At normal and verbose verbosity, name the section category
			# so the landmark is identified, not just its line content.
			verbosity = self._verbosityLevel()
			if should_speak(verbosity, "section_context"):
				label = self._sectionCategoryLabel(section.category)
				if label:
					ui.message(label)
		except Exception:
			ui.message(ANSIParser.stripANSI(section.text))

	@staticmethod
	def _sectionCategoryLabel(category):
		"""Return a spoken label for a section category, or None to stay silent.

		The plain "output" category carries no landmark meaning and is
		never announced.
		"""
		labels = {
			# Translators: Spoken section category when jumping to a shell prompt
			"prompt": _("prompt"),
			# Translators: Spoken section category when jumping to a command line
			"command": _("command"),
			# Translators: Spoken section category when jumping to an error line
			"error": _("error"),
			# Translators: Spoken section category when jumping to a warning line
			"warning": _("warning"),
			# Translators: Spoken section category when jumping to a stack trace
			"stack_trace": _("stack trace"),
			# Translators: Spoken section category when jumping to a progress line
			"progress": _("progress"),
			# Translators: Spoken section category when jumping to a timestamped line
			"timestamp": _("timestamp"),
			# Translators: Spoken section category when jumping to a heading line
			"heading": _("heading"),
		}
		return labels.get(category)

	@script(
		# Translators: Description for jumping to the next section boundary
		description=_("Jump to next section in terminal output"),
		gesture="kb:alt+n",
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
		gesture="kb:alt+shift+n",
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
	# Section 10b: AI Turn Navigation
	# ------------------------------------------------------------------

	def _navigateToTurn(self, turn):
		"""Move the review cursor to an AI turn and announce its role.

		Args:
			turn: An AITurn or CodeBlock namedtuple, or None (beeps if None).
		"""
		if turn is None:
			tones.beep(200, 100)
			return
		terminal = self._boundTerminal
		if terminal is None:
			return
		try:
			info = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			info.move(textInfos.UNIT_LINE, turn.line_num)
			info.expand(textInfos.UNIT_LINE)
			api.setReviewPosition(info)

			# Build announcement: role + first 40 chars of content
			role_label = getattr(turn, "role", "code block")
			line_text = info.text.strip() if info.text else ""
			preview = line_text[:40]
			if len(line_text) > 40:
				preview += "..."
			announcement = f"{role_label}: {preview}" if preview else role_label
			speech.speakText(announcement)
			self._brailleMessage(announcement[:30])

			# Audio cue for turn boundaries
			tones.beep(660, 30)
		except Exception:
			role_label = getattr(turn, "role", "code block")
			ui.message(role_label)

	def _navigateAiElement(self, gesture, nav_func):
		"""Shared boilerplate for AI turn / code block navigation scripts."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		self._aiTurnTokenizer.tokenize(lines)
		current = self._getCurrentLineNumber() or 0
		self._navigateToTurn(nav_func(current))

	@script(
		# Translators: Description for jumping to the next AI turn
		description=_("Jump to next AI turn in terminal output"),
		gesture="kb:NVDA+alt+t",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_nextTurn(self, gesture):
		"""Jump to the next AI conversation turn."""
		self._navigateAiElement(gesture, self._aiTurnTokenizer.next_turn)

	@script(
		# Translators: Description for jumping to the previous AI turn
		description=_("Jump to previous AI turn in terminal output"),
		gesture="kb:NVDA+alt+shift+t",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_prevTurn(self, gesture):
		"""Jump to the previous AI conversation turn."""
		self._navigateAiElement(gesture, self._aiTurnTokenizer.prev_turn)

	@script(
		# Translators: Description for jumping to the next code block
		description=_("Jump to next code block in terminal output"),
		gesture="kb:NVDA+alt+b",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_nextCodeBlock(self, gesture):
		"""Jump to the next fenced code block."""
		self._navigateAiElement(gesture, self._aiTurnTokenizer.next_code_block)

	@script(
		# Translators: Description for jumping to the previous code block
		description=_("Jump to previous code block in terminal output"),
		gesture="kb:NVDA+alt+shift+b",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_prevCodeBlock(self, gesture):
		"""Jump to the previous fenced code block."""
		self._navigateAiElement(gesture, self._aiTurnTokenizer.prev_code_block)

	# ------------------------------------------------------------------
	# Section 10b: Streaming Delta
	# ------------------------------------------------------------------

	def _ensureDeltaTracker(self):
		"""Create or reconfigure the delta tracker with current verbosity."""
		verbosity = self._configManager.get("verbosityLevel", 1)
		if self._deltaTracker is None:
			self._deltaTracker = StreamingDeltaTracker(
				debounce_ms=500, verbosity=verbosity,
			)
		else:
			self._deltaTracker.set_verbosity(verbosity)

	@script(
		# Translators: Description for announcing what changed in terminal buffer
		description=_("Announce what changed in the terminal buffer"),
		gesture="kb:NVDA+shift+d",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_whatChanged(self, gesture):
		"""Snapshot the terminal buffer and announce the delta."""
		if not self.isTerminalApp():
			gesture.send()
			return

		lines = self._getBufferLines()
		if lines is None:
			ui.message(_("Unable to read terminal"))
			return

		self._ensureDeltaTracker()
		delta_speech = self._deltaTracker.take_snapshot(lines)

		if delta_speech is None:
			# No previous snapshot, no change, debounced, or quiet mode
			if self._deltaTracker.has_previous:
				ui.message(_("No changes"))
			return

		ui.message(delta_speech)

		# Show braille delta if available
		braille_text = self._deltaTracker.get_braille_delta()
		if braille_text:
			braille.handler.message(braille_text)

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

		# Check privacy guard
		allowed, blocked_msg = self._privacyGuard.check_feature("summarize", self._configManager)
		if not allowed:
			if blocked_msg:
				ui.message(blocked_msg)
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

		# Check privacy guard
		allowed, blocked_msg = self._privacyGuard.check_feature("summarize", self._configManager)
		if not allowed:
			if blocked_msg:
				ui.message(blocked_msg)
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


	# ------------------------------------------------------------------
	# Section 11b: Privacy Status
	# ------------------------------------------------------------------

	@script(
		# Translators: Description for announcing privacy and feature status
		description=_("Announce privacy status and feature states"),
		gesture="kb:NVDA+shift+p",
		category=SCRCAT_TERMINALACCESS,
	)
	def script_announcePrivacyStatus(self, gesture):
		"""Announce the current privacy status and opt-in feature states."""
		if not self.isTerminalApp():
			gesture.send()
			return
		status = self._privacyGuard.format_privacy_status(self._configManager)
		ui.message(status)

	@script(
		# Translators: Description for announcing code block metadata
		description=_("Announce code block at cursor: language and line count"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_announceCodeBlock(self, gesture):
		"""Announce metadata of the fenced code block at the current line."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		current = self._getCurrentLineNumber() or 0
		blocks = self._codeBlockDetector.detect(lines)
		block = self._codeBlockDetector.find_block_at(current, blocks)
		if block is None:
			# Translators: Message when cursor is not inside a code block
			ui.message(_("Not inside a code block"))
			return
		ui.message(block.announce())

	@script(
		# Translators: Description for explaining a code block
		description=_("Explain the code block at cursor"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_explainCodeBlock(self, gesture):
		"""Provide a concise offline explanation of the code block at cursor."""
		if not self.isTerminalApp():
			gesture.send()
			return
		allowed, blocked_msg = self._privacyGuard.check_feature("explain_code", self._configManager)
		if not allowed:
			if blocked_msg:
				ui.message(blocked_msg)
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		current = self._getCurrentLineNumber() or 0
		blocks = self._codeBlockDetector.detect(lines)
		block = self._codeBlockDetector.find_block_at(current, blocks)
		if block is None:
			ui.message(_("Not inside a code block"))
			return
		explanation = block.explain(lines)
		ui.message(explanation)

	@script(
		# Translators: Description for copying a code block to the clipboard
		description=_("Copy the code block at cursor to the clipboard"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_copyCodeBlock(self, gesture):
		"""Copy the fenced code block at the current line to the clipboard."""
		if not self.isTerminalApp():
			gesture.send()
			return
		lines = self._getBufferLines()
		if not lines:
			tones.beep(200, 100)
			return
		current = self._getCurrentLineNumber() or 0
		blocks = self._codeBlockDetector.detect(lines)
		block = self._codeBlockDetector.find_block_at(current, blocks)
		if block is None:
			# Translators: Message when cursor is not inside a code block
			ui.message(_("Not inside a code block"))
			return
		text, truncated = block.copy_text(lines)
		if not self._copyToClipboard(text):
			# Translators: Announced when copying a code block fails
			ui.message(_("Unable to copy"))
			return
		if truncated:
			# Translators: Announced after copying a code block that was cut at the size cap
			ui.message(_("Code block copied, truncated"))
		else:
			# Translators: Announced after copying a code block
			ui.message(_("Code block copied"))

	@script(
		# Translators: Description for cycling the verbosity level
		description=_("Cycle the verbosity level: quiet, normal, verbose"),
		category=SCRCAT_TERMINALACCESS,
	)
	def script_cycleVerbosity(self, gesture):
		"""Cycle the verbosity level and announce the new setting."""
		if not self.isTerminalApp():
			gesture.send()
			return
		new_level = (self._verbosityLevel() + 1) % 3
		self._configManager.set("verbosityLevel", new_level)
		# Translators: Verbosity level names, in order: quiet, normal, verbose
		names = [_("Quiet"), _("Normal"), _("Verbose")]
		ui.message(names[new_level])

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
