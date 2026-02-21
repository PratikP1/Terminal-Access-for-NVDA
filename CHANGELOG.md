# Changelog

All notable changes to the TDSR for NVDA add-on will be documented in this file.

## [1.0.12] - 2026-02-21

### Added - Phase 2 Core Enhancements
- **Punctuation Level System** - Four levels of punctuation verbosity for granular control
  - Level 0 (None): No punctuation announced
  - Level 1 (Some): Basic punctuation (.,?!;:)
  - Level 2 (Most): Most punctuation (adds @#$%^&*()_+=[]{}\\|<>/)
  - Level 3 (All): All punctuation and symbols
  - NVDA+Alt+[: Decrease punctuation level
  - NVDA+Alt+]: Increase punctuation level
  - Applies to key echo, cursor tracking, character navigation, and continuous reading
  - Replaces binary processSymbols with sophisticated 4-level system
  - Essential for developers working with code, scripts, and configuration files
- **Read From/To Position** - Directional reading commands for quick content scanning
  - NVDA+Alt+Shift+Left: Read from cursor to beginning of line
  - NVDA+Alt+Shift+Right: Read from cursor to end of line
  - NVDA+Alt+Shift+Up: Read from cursor to top of buffer
  - NVDA+Alt+Shift+Down: Read from cursor to bottom of buffer
  - Complements Phase 1 edge navigation features
  - Respects current punctuation level
  - Announces "Nothing" for empty regions
- **Enhanced Selection System** - Flexible mark-based text selection
  - Support for arbitrary start/end positions (not just full lines)
  - Linear selection: Continuous text from start to end mark
  - Rectangular selection: Column-based selection for tables
  - NVDA+Alt+R: Toggle mark positions (start, end, or clear)
  - NVDA+Alt+C: Copy linear selection
  - NVDA+Alt+Shift+C: Copy rectangular selection
  - NVDA+Alt+X: Clear selection marks
  - Enables precise text extraction from structured terminal output
  - Essential for working with tables and columnar data

### Changed
- Replaced boolean `processSymbols` setting with integer `punctuationLevel` (0-3)
- Enhanced NVDA+Alt+R gesture to support arbitrary position marking (was simple toggle)
- Settings panel now includes punctuation level dropdown instead of processSymbols checkbox
- Punctuation level choices show examples of included symbols for clarity

### Migration
- Existing `processSymbols` setting automatically migrated to `punctuationLevel`
  - `True` → Level 2 (Most punctuation)
  - `False` → Level 0 (No punctuation)
- Migration occurs once on first load after update
- Old processSymbols setting retained for backward compatibility

### Technical
- Added `PUNCTUATION_SETS` dictionary defining character sets for each level
- Implemented `_shouldProcessSymbol()` helper method for level-based filtering
- Enhanced selection system with `_markStart` and `_markEnd` bookmark tracking
- Added punctuation level constants: PUNCT_NONE, PUNCT_SOME, PUNCT_MOST, PUNCT_ALL
- All Phase 2 features follow consistent error handling patterns
- Settings UI updated with wx.Choice control for punctuation levels

### Credits
- Phase 2 features inspired by [Speakup](https://github.com/linux-speakup/speakup) screen reader
- Implementation based on SPEAKUP_FEATURE_ANALYSIS.md Phase 2 recommendations

## [1.0.11] - 2026-02-21

### Added - Phase 1 Quick Win Features
- **Continuous Reading (Say All)** - NVDA+Alt+A reads continuously from cursor to end of terminal buffer
  - Leverages NVDA's speech system for smooth reading
  - Can be interrupted with any key press
  - Respects processSymbols settings
  - Essential for reading long log files, man pages, and command output
- **Screen Edge Navigation** - Quick navigation to screen and line boundaries
  - NVDA+Alt+Home: Jump to first character of current line
  - NVDA+Alt+End: Jump to last character of current line
  - NVDA+Alt+PageUp: Jump to top of terminal buffer
  - NVDA+Alt+PageDown: Jump to bottom of terminal buffer
  - Character at destination is announced after navigation
- **Line Indentation Detection** - Double-press NVDA+Alt+I to announce indentation level
  - Counts leading spaces and tabs on current line
  - Distinguishes between spaces, tabs, and mixed indentation
  - Critical for Python code and YAML configuration files
  - Announces "X spaces", "Y tabs", or "X tabs, Y spaces"
- **Position Announcement** - NVDA+Alt+P announces row and column coordinates
  - Reports current line number (row) and character position (column)
  - Uses 1-based indexing for user-friendly reporting
  - Useful for understanding table alignment and verifying cursor location
- **Character Code Announcement** - Triple-press NVDA+Alt+Comma to announce character code
  - Single press: Read character
  - Double press: Read character phonetically
  - Triple press: Announce ASCII/Unicode code (decimal and hexadecimal)
  - Identifies control characters (space, tab, line feed, etc.)
  - Helpful for debugging encoding issues and identifying special characters

### Changed
- Attribute reading gesture moved from NVDA+Alt+A to NVDA+Alt+Shift+A (to make room for continuous reading)
- Enhanced NVDA+Alt+I (read current line) to support double-press for indentation
- Enhanced NVDA+Alt+Comma (read character) to support triple-press for character code

### Technical
- Added speech module import for continuous reading functionality
- Added scriptHandler import for multi-press gesture detection
- Implemented helper methods: _announceIndentation() and _announceCharacterCode()
- All new features follow consistent error handling patterns

### Credits
- Phase 1 features inspired by [Speakup](https://github.com/linux-speakup/speakup) screen reader
- Implementation based on SPEAKUP_FEATURE_ANALYSIS.md recommendations

## [1.0.10] - 2026-02-21

### Changed
- Version bump and rebuild for distribution

## [1.0.9] - 2026-02-20

### Changed
- Version bump and rebuild for distribution

## [1.0.8] - 2026-02-19

### Added
- **Multiple cursor tracking modes** - Four distinct tracking modes (Off, Standard, Highlight, Window) inspired by Speakup
  - Off: Cursor tracking disabled
  - Standard: Announce character at cursor position (default)
  - Highlight: Track and announce highlighted/inverse video text
  - Window: Only track cursor within defined screen window
- **Gesture to cycle cursor tracking modes** - NVDA+Alt+Asterisk cycles through modes
- **Screen windowing system** - Define rectangular regions for focused monitoring
  - NVDA+Alt+F2: Set window boundaries (two-step: start, then end)
  - NVDA+Alt+F3: Clear window
  - NVDA+Alt+Plus: Read window content
- **Attribute/color reading** - NVDA+Alt+Shift+A announces ANSI colors and formatting
  - Supports 16 ANSI colors (foreground and background)
  - Recognizes bold, underline, and inverse video
  - Human-readable color announcements
- **Highlight tracking mode** - Detects and announces ANSI inverse video codes (ESC[7m)
- **ANSI escape sequence parser** - Comprehensive color code detection and parsing

### Changed
- Enhanced cursor tracking architecture with mode-based dispatcher
- Added cursor tracking mode selector to settings panel
- Updated documentation with new features and commands

### Technical
- Added mode constants: CT_OFF, CT_STANDARD, CT_HIGHLIGHT, CT_WINDOW
- New configuration parameters: cursorTrackingMode, windowTop/Bottom/Left/Right, windowEnabled
- Implemented _announceStandardCursor, _announceHighlightCursor, _announceWindowCursor methods
- Added _extractHighlightedText and _parseColorCode helper methods
- Enhanced settings panel with wx.Choice for tracking mode selection

### Credits
- Cursor tracking modes, screen windowing, and attribute reading inspired by [Speakup](https://github.com/linux-speakup/speakup) screen reader

## [1.0.7] - 2026-02-19

### Fixed
- Fixed spell current word command (NVDA+Alt+K twice) - now properly binds navigator to terminal before accessing review cursor
- Fixed phonetic character announcement (NVDA+Alt+Comma twice) - now properly binds navigator to terminal before accessing review cursor

### Technical
- Added api.setNavigatorObject(self._boundTerminal) call in script_spellCurrentWord before calling _getWordAtReview()
- Added api.setNavigatorObject(self._boundTerminal) call in script_readCurrentCharPhonetic before accessing review position
- Both functions now follow established pattern of binding navigator before review cursor access

## [1.0.5] - 2026-02-19

### Fixed
- Review cursor architecture corrected: navigator object is now used only in event_gainFocus to route the review cursor to the terminal; all read operations (line/word/character) use the review cursor directly via api.getReviewPosition(), preserving review position between navigation calls

### Technical
- Removed erroneous api.setNavigatorObject() calls from _readLine, _readWord, _readChar, _getWordAtReview, and script_readCurrentCharPhonetic
- script_copyScreen now uses stored self._boundTerminal reference instead of re-fetching focus object

## [1.0.4] - 2026-02-19

### Added
- Line copy (NVDA+Alt+C) and screen copy (NVDA+Alt+Shift+C) functionality to copy terminal content to clipboard

### Fixed
- Review cursor now properly binds to focused terminal window to prevent reading content outside the terminal (e.g., window title)
- Line, word, and character navigation now use the review cursor directly, preserving review position between navigation calls
- Phonetic character reading now uses the review cursor directly

### Technical
- Navigator object used only in event_gainFocus to route review cursor to the terminal; all read operations use api.getReviewPosition()
- Stored bound terminal reference (self._boundTerminal) for screen copy operations

## [1.0.3] - 2026-02-19

### Fixed
- Fixed line, word, and character reading by switching to NVDA review cursor API

## [1.0.2] - 2026-02-19

### Fixed
- Fixed "Missing file or invalid file format" error when installing add-on in NVDA
- Build script now properly excludes root-level __init__.py from .nvda-addon package

### Technical
- Updated build.py to skip addon/__init__.py during package creation (lines 45-48)
- NVDA add-ons must not include __init__.py at the root level of the package

## [1.0.1] - 2026-02-19

### Changed
- Updated compatibility for NVDA 2026.1 (beta)
- Updated lastTestedNVDAVersion to 2026.1 in manifest and build configuration
- Removed unused imports (controlTypes, winUser) for cleaner code

### Technical
- Verified all NVDA API usage is compatible with NVDA 2026.1
- Confirmed script decorator usage follows current NVDA patterns
- Validated settings panel integration with modern NVDA

## [1.0.0] - 2024-02-19

### Added
- Initial release of TDSR for NVDA add-on
- Support for Windows Terminal, PowerShell, PowerShell Core, Command Prompt, and Console Host
- Line-by-line navigation (NVDA+Alt+U/I/O)
- Word navigation with spelling support (NVDA+Alt+J/K/L)
- Character navigation with phonetic alphabet (NVDA+Alt+M/Comma/Period)
- Cursor tracking and automatic announcements
- Key echo functionality
- Symbol processing for better command syntax understanding
- Quiet mode toggle (NVDA+Alt+Q)
- Selection and copy mode functionality
- Comprehensive settings panel in NVDA preferences ("Terminal Settings")
- User guide accessible via NVDA+Shift+F1
- Automatic help announcement when entering terminals
- Configuration options for:
  - Cursor tracking
  - Key echo
  - Line pause
  - Symbol processing
  - Repeated symbols condensation
  - Cursor delay (0-1000ms)
- Support for Windows 10 and Windows 11
- Compatibility with NVDA 2019.3 and later versions

### Documentation
- Comprehensive user guide with keyboard commands reference
- Installation and configuration instructions
- Troubleshooting guide
- Tips and best practices

### Technical
- Global plugin architecture for system-wide terminal support
- Integration with NVDA's configuration system
- Settings persistence across sessions
- Modular code structure for maintainability
