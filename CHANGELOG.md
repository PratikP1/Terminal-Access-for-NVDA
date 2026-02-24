# Changelog

All notable changes to Terminal Access for NVDA will be documented in this file.

## [Unreleased]

## [1.0.47] - 2026-02-24

### Changed

- **Simplified keyboard shortcuts**: All terminal-scoped commands now use simpler 2-modifier combinations instead of 3-modifier combinations
  - **Dropped Alt modifier entirely** (key unchanged) for most commands:
    - Line navigation: `NVDA+Alt+U/I/O` → `NVDA+U/I/O`
    - Word navigation: `NVDA+Alt+J/K/L` → `NVDA+J/K/L`
    - Character navigation: `NVDA+Alt+M/,/.` → `NVDA+M/,.`
    - Copy/selection: `NVDA+Alt+R/C/X/V` → `NVDA+R/C/X/V`
    - Punctuation: `NVDA+Alt+[/]` → `NVDA+[/]`
    - Search: `NVDA+Alt+F` → `NVDA+F`
    - Say all: `NVDA+Alt+A` → `NVDA+A`
  - **Dropped Alt, key changed** (to avoid NVDA global conflicts):
    - Quiet mode: `NVDA+Alt+Q` → `NVDA+Shift+Q`
    - Announce new output: `NVDA+Alt+N` → `NVDA+Shift+N`
    - Position: `NVDA+Alt+P` → `NVDA+;`
    - List tabs: `NVDA+Alt+T` → `NVDA+W`
    - Indentation toggle: `NVDA+Alt+F5` → `NVDA+F5`
    - Profile announcement: `NVDA+Alt+F10` → `NVDA+F10`
    - Buffer navigation: `NVDA+Alt+Home/End` → `NVDA+Shift+Home/End`
    - Buffer navigation: `NVDA+Alt+PageUp/Down` → `NVDA+F4/F6`
    - Command history: `NVDA+Alt+Up/Down` → `NVDA+H/G`
  - **3-key → 2-key** (dropped Alt from Shift combinations):
    - Directional reading: `NVDA+Alt+Shift+Arrow` → `NVDA+Shift+Arrow`
    - Advanced commands: `NVDA+Alt+Shift+A/C/B/H/L/T` → `NVDA+Shift+A/C/B/H/L/T`
    - Set bookmark: `NVDA+Alt+Shift+0-9` → `NVDA+Shift+0-9`
  - **Unchanged** (advanced features retain Alt modifier for safety):
    - Help: `NVDA+Shift+F1`
    - Jump to bookmark: `NVDA+Alt+0-9`
    - Window management: `NVDA+Alt+F2/F3/Plus/Asterisk`
    - Find next/previous: `NVDA+F3` / `NVDA+Shift+F3`
- Updated all documentation (README.md, addon/doc/en/readme.html, terminalAccess.py) to reflect new keyboard shortcuts

## [1.0.46] - 2026-02-24

### Added

- **Announce New Output feature**: New `NewOutputAnnouncer` class automatically speaks newly
  appended terminal output as it arrives, without any manual navigation required.
  - Enabled/disabled with `NVDA+Alt+N` (new toggle gesture) — announces "Announce new output on/off"
  - Coalesces rapid output within a configurable window (default 200 ms) so fast-scrolling
    commands do not overwhelm the speech synthesiser
  - When more than the configured line limit arrives at once (default 20 lines), speaks a
    concise summary: e.g. "47 new lines"
  - Strips ANSI colour/formatting escape codes before speech (configurable, on by default)
  - Automatically suppressed when quiet mode is active
  - Four new settings exposed in **NVDA Preferences → Settings → Terminal Settings**:
    - **Announce new terminal output automatically** (boolean, default off)
    - **Coalesce delay** in milliseconds (50–2000, default 200)
    - **Max lines before summarising** (1–200, default 20)
    - **Strip ANSI escape codes from output** (boolean, default on)

- **TextDiffer integration in WindowMonitor**: Each monitored region now carries its own
  `TextDiffer` instance for precise, efficient change detection.
  - First poll per region establishes a silent baseline (no false announcements on startup)
  - Subsequent polls only speak when content actually changed
  - For appended output (the common case) only the newly appended text is spoken — not the
    entire region
  - For non-trivial changes (screen clear, mid-screen edit) the full region content is spoken
  - Eliminates redundant UIA/COM reads and unnecessary speech on every poll cycle

### Changed

- **Minimum NVDA version raised to 2025.1** (Python 3.11 runtime); compatibility with earlier
  NVDA versions removed
- `WindowMonitor._announce_change` now speaks the relevant content directly instead of the
  generic "Window {name} changed" string
- `ConfigManager` validation and `reset_to_defaults` extended to cover the four new
  `announceNewOutput` settings
- Settings panel `onSave` and `onResetToDefaults` updated to persist and reset new settings
- `GlobalPlugin.event_caret` feeds the current terminal buffer to `NewOutputAnnouncer` on
  every caret event (best-effort, silently skipped on any error)
- `NVDA+Alt+N` toggle resets the announcer snapshot on enable so stale buffered content is
  never replayed when the feature is turned on mid-session

### Documentation

- Added "Announce New Output" feature description with usage example to the Features section
  of the user guide (`addon/doc/en/readme.html`)
- Added `NVDA+Alt+N` row to the Modes and Toggles keyboard commands table
- Added detailed settings reference for all four new options with examples, ranges, and
  interaction notes
- Added **Scenario 6b: Hands-Free Real-Time Output Monitoring** (pytest workflow example)
- Updated Settings Interaction Summary to document how quiet mode and the new settings interact

### Tests

- 23 new unit tests in `tests/test_new_output_announcer.py` covering:
  - Appended output detection, ANSI stripping (on and off), coalescing, max-lines summary
  - Quiet mode and feature-disabled suppression
  - `TextDiffer` state reset, unchanged-content silence, changed-content silence
  - `WindowMonitor` per-region `TextDiffer` instances, initial-poll silence, silent mode,
    appended-only speech
  - `ConfigManager` validation and `reset_to_defaults` for all four new settings
  - Confspec key presence check

## [1.0.45] - 2026-02-23

### Fixed

- Fixed keyboard command binding error by stripping "script_" prefix in _collectTerminalGestures()
- Keyboard gestures now bind correctly without "Error binding script" messages
- Gestures remain properly scoped to terminal windows only (not global)

## [1.0.44] - 2026-02-23

### Changed

- Version bump for release

## [1.0.43] - 2026-02-23

### Changed

- Version bump for release

## [1.0.42] - 2026-02-23

### Changed

- Version bump for release

## [1.0.41] - 2026-02-23

### Changed

- Version bump for release

## [1.0.40] - 2026-02-23

### Release Notes

This is the **first public release** of Terminal Access for NVDA. The add-on is now ready for general use by the screen reader community.

### Documentation

- All documentation reviewed and updated for public release
- README.md now includes direct links to CONTRIBUTING.md and docs/README.md
- Contributing section enhanced with clear navigation to contribution guidelines
- Documentation structure verified for completeness and accessibility

## [1.0.38] - 2026-02-23

### Added

- **Default Profile Setting**: Choose a default profile to use when no application-specific profile is detected
  - New config setting: `defaultProfile` (empty string by default)
  - UI: Default profile dropdown in Application Profiles section
  - Automatically applies when no app-specific profile matches
  - Use NVDA+Alt+F10 to check active and default profiles
- **Profile Status Indicators**: Profile list now shows which profiles are active and set as default
  - Active profile marked with "(Active)" indicator
  - Default profile marked with "(Default)" indicator
  - Combined indicator when profile is both: "(Active, Default)"
  - Tooltip updated to explain indicators
- **NVDA+Alt+F10 Shortcut**: Announce which profile is currently active and which is set as default
  - New `script_announceActiveProfile` command
  - Reports active profile or "None (using global settings)" if no profile active
  - Reports default profile setting
  - Example: "Active profile: Vim/Neovim. Default profile: None"

### Changed

- **Settings Shortcut Removed**: NVDA+Alt+Shift+S no longer opens settings
  - Removed gesture binding from `script_openSettings`
  - Settings now accessible only via NVDA menu > Preferences > Settings > Terminal Settings
  - Updated all documentation to remove shortcut references
  - Updated help text in plugin to remove shortcut reference
- **Bookmark Shortcuts Restored**: Bookmarks now support full 0-9 range
  - NVDA+Alt+0-9 jumps to bookmarks 0-9 (all 10 bookmarks)
  - NVDA+Alt+Shift+0-9 sets bookmarks 0-9 (all 10 bookmarks)
  - Profile announcement moved to NVDA+Alt+F10 to free up NVDA+Alt+0
  - Indentation toggle moved to NVDA+Alt+F5 to free up NVDA+Alt+5
- **Author Information**: Updated author to Pratik Patel

### Fixed

- **Profile Detection**: Profiles now apply automatically when terminal applications are detected
  - Profile detection on `event_appModule_gainFocus` verified and working
  - Default profile properly applied when no app-specific profile found
  - Log messages added for profile activation tracking

### Documentation

- Removed NVDA+Alt+Shift+S references from:
  - README.md (Settings and Configuration sections)
  - QUICKSTART.md (Essential Commands and Settings sections)
  - addon/doc/en/readme.html (multiple references)
  - Help text in terminalAccess.py

## [1.0.37] - 2026-02-22

### Added

- **Indentation Reading Feature**: Automatic announcement of indentation when reading lines
  - New setting: "Announce indentation when reading lines" (default: disabled)
  - **NVDA+Alt+5**: Quick toggle for indentation announcement (announces "Indentation announcement on/off")
  - Works with all line reading commands: NVDA+Alt+U (previous line), NVDA+Alt+I (current line), NVDA+Alt+O (next line)
  - Announces indentation after line content (e.g., "4 spaces", "2 tabs", "1 tab, 3 spaces")
  - Per-application profile support: customize indentation settings for specific apps (Python, YAML editors, etc.)
  - Helper methods: `_getIndentationInfo()`, `_formatIndentation()`, `_readLineWithIndentation()`
  - Preserves existing behavior: NVDA+Alt+I pressed twice still queries indentation of current line only
  - UI integration: new checkbox in Terminal Access Settings with descriptive tooltip
  - Essential for Python, YAML, Makefiles, and other indentation-sensitive code

### Fixed

- **Keyboard Commands**: Fixed NVDA+Alt+Comma and NVDA+Alt+Period commands typing characters
  - Commands now pass `None` to globalCommands review functions instead of gesture object
  - Prevents comma and period keys from being typed when reading current/next character
  - Affected commands: NVDA+Alt+Comma (read current character), NVDA+Alt+Period (read next character)
  - Applied pattern for all gestures containing typeable characters

### Documentation

- Updated README.md with indentation reading feature and NVDA+Alt+5 toggle
- Updated QUICKSTART.md with indentation usage examples for Python/YAML code
- Updated addon/doc/en/readme.html with complete keyboard commands and practical scenarios
- Added indentation to Settings Interactions section
- Updated Scenario 7 (Python Code Navigation) with automatic indentation workflow

## [1.0.36] - 2026-02-21

### Fixed

- **Global Plugin Initialization**: Fixed "Error initializing global plugin" caused by config migration attempting to delete keys
  - Fixed `AttributeError: __delitem__` in `ConfigManager._migrate_legacy_settings()` (line 1695)
  - Removed unsupported `del config.conf["terminalAccess"]["processSymbols"]` operation
  - NVDA's config objects don't support deletion; old deprecated keys now remain in config spec
  - Plugin now initializes successfully when migrating from `processSymbols` to `punctuationLevel`
  - Added comprehensive test suite (`test_config.py`) with 3 new migration tests

### Code Quality

- **Test Coverage**: Added 3 new tests for configuration migration functionality
  - Test migration from `processSymbols=True` to `punctuationLevel=2`
  - Test migration from `processSymbols=False` to `punctuationLevel=0`
  - Test that existing `punctuationLevel` values are preserved during migration

## [1.0.35] - 2026-02-21

### Fixed

- **Global Plugin Initialization**: Fixed "Error initializing global plugin" caused by GUI not being fully initialized
  - Added error handling in `GlobalPlugin.__init__` for GUI operations (line 3437-3442)
  - Added error handling in `script_openSettings` for GUI errors (line 4241-4245)
  - Plugin now initializes successfully even when GUI subsystem is not ready
  - Settings panel gracefully degrades if GUI unavailable during initialization
  - Added comprehensive test suite (`test_plugin_initialization.py`) with 5 tests

### Code Quality

- **Lint Compliance**: Fixed all critical lint errors to ensure code quality
  - Fixed F401: Removed unused `Set` import from typing
  - Fixed F541: Removed 2 unnecessary f-string prefixes (lines 491, 496)
  - Fixed F821: Fixed undefined variable `terminal` → `self._boundTerminal` (line 4644)
  - Fixed F841: Removed 3 unused variables (startInfo, endInfo, linesMoved)
  - Fixed E302, E303: Corrected blank lines formatting
  - Updated flake8 configuration to properly reflect NVDA coding standards (tabs for indentation)
  - Created comprehensive lint compliance documentation (`LINT_COMPLIANCE.md`)
  - All 298 tests passing successfully

### Documentation

- **Lint Compliance Documentation**: Added detailed documentation of NVDA coding standards
  - Explains why tabs are used (NVDA standard, not PEP 8 spaces)
  - Documents all fixed lint errors with line numbers
  - Provides validation steps for future development

## [1.0.34] - 2026-02-21

### Fixed

- **Translation Initialization**: Fixed "Error initializing global plugin" that occurred when `addonHandler.initTranslation()` failed
  - Added fallback translation function `def _(text): return text` in exception handler
  - Prevents `NameError` when translation system is unavailable
  - Plugin now initializes successfully even when NVDA translation modules fail to load
  - Added comprehensive test suite (`test_translation_fallback.py`) to verify fallback behavior

### Improved

- **Test Coverage**: Added 3 new tests for translation fallback functionality
- **Build Configuration**: Updated `.gitignore` to exclude coverage artifacts (`.coverage`, `coverage.xml`, `htmlcov/`)

## [1.0.33] - 2026-02-21

### Documentation - User Guide Enhancements

**Documentation Release**: Comprehensive user guide improvements with detailed feature explanations and practical usage scenarios.

#### Enhanced

- **Features Section**: Complete rewrite with detailed explanations and examples
  - Core Navigation Features: Line, word, and character navigation with practical examples
  - Advanced Reading Features: Continuous reading, indentation detection, position announcement
  - Real-Time Feedback Features: Cursor tracking, key echo, symbol processing with real command examples
  - Advanced Features: Comprehensive explanations for all features including:
    - Quiet Mode with use cases
    - Selection and Copy with step-by-step workflows
    - Bookmarks with complete navigation examples
    - Command History Navigation with git and command-line scenarios
    - Output Search with debugging scenarios
    - Window Management with htop and vim examples
    - Punctuation Levels with code vs. prose examples
    - Directional Reading with practical use cases
    - Configurable Settings overview

- **Practical Usage Scenarios**: Added 10 real-world scenarios demonstrating feature usage
  1. Reviewing Long Command Output (pip list workflow)
  2. Debugging a Failed Command (build error detection with bookmarks)
  3. Copying Specific Output (error message extraction)
  4. Editing a Complex Command (Docker command modification)
  5. Working with Git Output (git status and diff workflows)
  6. Monitoring a Long-Running Process (npm install with quiet mode)
  7. Reviewing Python Code Indentation (code structure understanding)
  8. Using Table Output (htop with window management)
  9. Copying Columns from Tabular Data (rectangular selection from ls -l)
  10. Verifying Special Characters in Commands (regex pattern verification)

- **Keyboard Commands Documentation**: Updated all documentation files with complete command reference
  - README.md: Added Bookmarks, Command History, Search, and Settings sections
  - QUICKSTART.md: Added complete keyboard reference with all 45 commands
  - HTML User Guide: Complete keyboard command tables with all features
  - Fixed keyboard shortcut references (NVDA+Alt+Shift+S for settings, not NVDA+Alt+C)

#### Improved

- Table of Contents: Updated to include Practical Usage Scenarios section
- Documentation Structure: Better organization with visual callouts and styled info boxes
- Example Quality: All examples use real commands and realistic scenarios with step-by-step workflows
- User Experience: Progressive learning approach from simple examples to complex workflows

---

## [1.0.32] - 2026-02-21

### Feature - Translation/Internationalization Support (Section 7)

**Feature Release**: Adds complete internationalization framework with support for 8 languages.

#### Added

- **Translation Framework**: Complete gettext-based i18n infrastructure
  - Translation template file (.pot) with all translatable strings
  - Translation files (.po) for 8 languages ready for community contribution
  - Standard NVDA translation workflow
  - Location: `addon/locale/` directory

- **Supported Languages**:
  - Spanish (es) - Español
  - French (fr) - Français
  - German (de) - Deutsch
  - Portuguese (pt) - Português
  - Chinese Simplified (zh_CN) - 简体中文
  - Chinese Traditional (zh_TW) - 繁體中文
  - Japanese (ja) - 日本語
  - Russian (ru) - Русский

- **Translation Documentation**:
  - Comprehensive Translation Guide (TRANSLATION_GUIDE.md)
  - Instructions for using Poedit and manual editing
  - Translation guidelines and best practices
  - Terminology guide for consistent translations
  - Testing procedures for translators
  - Contribution workflow

#### Technical Details

**Implementation Impact**:
- Translation template: 90+ translatable strings
- Locale directory structure: 8 languages × LC_MESSAGES
- Documentation: 400+ lines in TRANSLATION_GUIDE.md
- Build integration: Automatic .mo compilation via scons
- Compatible with NVDA's standard translation system

**File Structure**:
```
addon/
└── locale/
    ├── tdsr.pot           # Translation template
    ├── es/LC_MESSAGES/    # Spanish
    ├── fr/LC_MESSAGES/    # French
    ├── de/LC_MESSAGES/    # German
    ├── pt/LC_MESSAGES/    # Portuguese
    ├── zh_CN/LC_MESSAGES/ # Chinese (Simplified)
    ├── zh_TW/LC_MESSAGES/ # Chinese (Traditional)
    ├── ja/LC_MESSAGES/    # Japanese
    └── ru/LC_MESSAGES/    # Russian
```

**Translatable Categories**:
- Add-on metadata (name, description)
- Gesture descriptions (Input Gestures dialog)
- User messages (announcements, status, errors)
- Dialog text (search, settings)
- Help text and documentation
- Menu items and labels

**Translation Tools**:
- Poedit (recommended): https://poedit.net/
- GTranslator (Linux)
- Lokalize (KDE)
- Manual editing with any text editor

**For Translators**:
- Read TRANSLATION_GUIDE.md for complete instructions
- Edit `addon/locale/<lang>/LC_MESSAGES/nvda.po`
- Keep placeholders like `{name}`, `{count}` in English
- Test translations by building and installing add-on
- Submit translations via pull request

**Testing**:
- All languages compile successfully with msgfmt
- Build process generates .mo files automatically
- Fallback to English for untranslated strings
- Compatible with NVDA language settings

---

## [1.0.31] - 2026-02-21

### Feature - Command History Navigation (Section 8.1)

**Feature Release**: Adds automatic command detection and history navigation for terminal commands.

#### Added

- **CommandHistoryManager Class**: Detect and navigate through terminal command history
  - Automatic command detection from terminal output
  - Support for multiple shell prompt formats:
    * Bash: `$`, `#`, custom PS1 prompts (e.g., `user@host:~$`)
    * PowerShell: `PS>`, `PS C:\>`, custom prompts
    * Windows CMD: drive letter prompts (e.g., `C:\>`, `D:\Users\name>`)
    * WSL: Linux prompts in WSL environments
  - Navigate forward/backward through command history
  - List command history with recent commands
  - Configurable history size (default: 100 commands)
  - Automatic duplicate detection
  - Location: `addon/globalPlugins/tdsr.py` lines 3048-3291

- **Command History Gestures**:
  - `NVDA+Alt+Shift+H` - Scan terminal output to detect commands
  - `NVDA+Alt+UpArrow` - Navigate to previous command
  - `NVDA+Alt+DownArrow` - Navigate to next command
  - `NVDA+Alt+Shift+L` - List all commands in history

#### Technical Details

**Implementation Impact**:
- Code changes: 244 lines for CommandHistoryManager class + 118 lines for history gestures
- Automatic command scanning on first navigation
- Regex-based prompt pattern matching
- Bookmark-based position storage for fast navigation
- Efficient duplicate detection

**Use Cases**:
- Review previously executed commands
- Navigate to specific command results
- Audit command history in terminal sessions
- Find and re-read complex commands
- Track command execution in build scripts

**Supported Prompt Examples**:
```bash
# Bash/Linux
user@host:~$ ls -la
root@server:/var/log# grep error syslog
$ pwd

# PowerShell
PS C:\Users\name> Get-Process
PS> dir

# Windows CMD
C:\> dir
D:\Projects\myapp> npm start
```

**API Usage Example**:
```python
# CommandHistoryManager is automatically initialized
manager = self._commandHistoryManager

# Scan terminal output for commands
count = manager.detect_and_store_commands()

# Navigate through history
manager.navigate_history(-1)  # Previous
manager.navigate_history(1)   # Next

# List all commands
history = manager.list_history()
```

**Testing**:
- Compatible with all supported terminals (Windows Terminal, PowerShell, CMD, WSL)
- Tested with bash, zsh, PowerShell, cmd prompts
- Handles custom PS1 configurations
- Thread-safe implementation

---

## [1.0.30] - 2026-02-21

### Feature - Output Filtering and Search (Section 8.2)

**Feature Release**: Adds search functionality to find and navigate through terminal output.

#### Added

- **OutputSearchManager Class**: Search terminal output with pattern matching
  - Text search with case sensitivity option
  - Regular expression support (optional)
  - Navigate forward/backward through matches with wrap-around
  - Jump to first/last match
  - Get match count and current match information
  - Location: `addon/globalPlugins/tdsr.py` lines 2839-3046

- **Search Gestures**:
  - `NVDA+Alt+F` - Search terminal output (shows dialog)
  - `NVDA+F3` - Jump to next search match
  - `NVDA+Shift+F3` - Jump to previous search match

#### Technical Details

**Implementation Impact**:
- Code changes: 208 lines for OutputSearchManager class + 125 lines for search dialog and gestures
- Interactive search dialog using wx.TextEntryDialog
- Case-insensitive search by default
- Regex support for advanced patterns
- Efficient line-by-line searching with bookmarks

**Use Cases**:
- Find error messages in log output
- Locate specific command results
- Search through help text
- Find warnings in build output
- Navigate to specific lines in terminal history

**API Usage Example**:
```python
# SearchManager is automatically initialized
manager = self._searchManager

# Simple text search (case insensitive)
count = manager.search("error", case_sensitive=False)

# Regex search
count = manager.search(r"error:\s+\d+", use_regex=True)

# Navigate matches
manager.next_match()
manager.previous_match()
manager.first_match()
manager.last_match()

# Get match info
info = manager.get_current_match_info()
# Returns: (match_num, total_matches, line_text, line_num)
```

**Notes**:
- Search is performed on all terminal content
- Matches are line-based (entire lines containing pattern)
- Wrap-around navigation (next after last goes to first)
- Search results persist until new search or terminal switch
- Dialog allows quick text entry for search patterns

---

## [1.0.29] - 2026-02-21

### Feature - Bookmark Functionality (Section 8.3)

**Feature Release**: Adds bookmark/marker functionality for quick navigation in terminal output.

#### Added

- **BookmarkManager Class**: Manage named bookmarks for quick position recall
  - Set bookmarks at any position with names or numbers (0-9)
  - Jump to bookmarks instantly
  - List all bookmarks
  - Remove bookmarks
  - Maximum 50 bookmarks per terminal
  - Location: `addon/globalPlugins/tdsr.py` lines 2694-2837

- **Bookmark Gestures**:
  - `NVDA+Alt+Shift+0-9` - Set bookmark 0-9 at current position
  - `NVDA+Alt+0-9` - Jump to bookmark 0-9
  - `NVDA+Alt+Shift+B` - List all bookmarks

#### Technical Details

**Implementation Impact**:
- Code changes: 144 lines for BookmarkManager class + 106 lines for gestures
- Integration with GlobalPlugin lifecycle
- Automatic initialization when terminal is bound
- Position-relative bookmarks (survives content changes when possible)

**Use Cases**:
- Mark important log entries for later review
- Save positions in long command output
- Quick navigation in code review sessions
- Mark error locations in build output
- Navigate between different sections of output

**API Usage Example**:
```python
# BookmarkManager is automatically initialized
manager = self._bookmarkManager

# Set bookmark
manager.set_bookmark("error_line")

# Jump to bookmark
manager.jump_to_bookmark("error_line")

# List bookmarks
bookmarks = manager.list_bookmarks()

# Remove bookmark
manager.remove_bookmark("error_line")
```

**Notes**:
- Bookmarks are position-based using NVDA TextInfo bookmarks
- Invalid bookmarks (after content changes) are automatically removed
- Quick number bookmarks (0-9) for fast workflows
- Named bookmarks can be added via API for advanced use

---

## [1.0.28] - 2026-02-21

### Feature - Advanced Window Monitoring (Section 6.1)

**Feature Release**: Adds support for monitoring multiple terminal windows/regions simultaneously with change detection and automatic announcements.

#### Added

- **WindowMonitor Class**: New class for multi-window monitoring with background polling
  - Monitor multiple windows/regions simultaneously
  - Configurable polling intervals per window (default: 500ms)
  - Change detection with content comparison
  - Rate limiting to prevent announcement spam (minimum 2 seconds between announcements)
  - Thread-safe operations with locking
  - Background daemon thread for continuous monitoring
  - Location: `addon/globalPlugins/tdsr.py` lines 2402-2691

- **WindowMonitor API Methods**:
  - `add_monitor(name, bounds, interval_ms, mode)` - Add window to monitor
  - `remove_monitor(name)` - Remove monitored window
  - `enable_monitor(name)` / `disable_monitor(name)` - Toggle monitoring
  - `start_monitoring()` / `stop_monitoring()` - Control background thread
  - `is_monitoring()` - Check monitoring status
  - `get_monitor_status()` - Get all monitor configurations

- **Comprehensive Test Suite**: 32 test cases for WindowMonitor
  - Monitor management (add, remove, enable, disable)
  - Content extraction with bounds validation
  - Change detection and announcements
  - Thread safety testing
  - Integration tests with monitoring loop
  - Location: `tests/test_window_monitor.py` (32 tests)

#### Enhanced

- **GlobalPlugin Integration**: WindowMonitor initialized and managed by plugin
  - Automatic cleanup on plugin termination
  - Stops all monitoring when NVDA closes
  - Location: `addon/globalPlugins/tdsr.py` lines 2812-2822

- **Change Detection Strategies**:
  - Line-by-line content comparison
  - Announcement of changed windows by name
  - Configurable modes: 'changes' (announce) or 'silent' (track only)
  - Rate limiting prevents spam from rapidly changing content

#### Technical Details

**Implementation Impact**:
- Code changes: 290+ lines of new WindowMonitor class
- Test coverage: 32 test cases covering all public methods
- Thread management: Daemon thread with clean shutdown
- Memory efficient: Stores last content per window for comparison
- Performance: Configurable polling intervals (100ms to multiple seconds)

**Use Cases**:
- Monitor build output in split terminal panes
- Track log file tails in tmux/screen sessions
- Monitor system status bars (htop, top, etc.)
- Track chat messages in IRC/Discord clients
- Monitor background process output
- Watch for specific content changes in defined regions

**API Usage Example**:
```python
# Initialize monitor
monitor = WindowMonitor(terminal_obj, position_calculator)

# Add monitors for different regions
monitor.add_monitor("build_output", (1, 1, 10, 80), interval_ms=1000)
monitor.add_monitor("logs", (11, 1, 20, 80), interval_ms=500)
monitor.add_monitor("status", (21, 1, 21, 80), interval_ms=2000, mode='silent')

# Start monitoring
monitor.start_monitoring()

# ... monitoring runs in background ...

# Stop when done
monitor.stop_monitoring()
```

**Thread Safety**:
- All operations use thread locking
- Safe to call from multiple threads
- Background thread cleanly terminates on stop

**Rate Limiting**:
- Minimum 2 seconds between announcements per window
- Prevents overwhelming user with rapid changes
- Configurable per-monitor intervals

**Notes**:
- WindowMonitor is an API-based feature (no keyboard gestures)
- Designed for programmatic use by applications and profiles
- Can be used in custom application profiles for tmux, screen, etc.
- Background thread is a daemon (won't prevent NVDA exit)
- Content extraction uses TextInfo API for reliability
- Bounds are 1-based (row, column) coordinates

#### Breaking Changes

None. This is a new feature that doesn't affect existing functionality.

#### Migration Guide

No migration required. WindowMonitor is available for use in v1.0.28+.

**To use WindowMonitor programmatically**:
1. Create WindowMonitor instance with terminal and position calculator
2. Add monitors for desired regions using `add_monitor()`
3. Start monitoring with `start_monitoring()`
4. Monitors run in background and announce changes automatically
5. Stop monitoring with `stop_monitoring()` when done

**Example in application profile**:
```python
# In custom profile for tmux/screen
def activate_profile(terminal, calculator):
    monitor = WindowMonitor(terminal, calculator)
    # Monitor status bar
    monitor.add_monitor("status", (24, 1, 24, 80), interval_ms=1000)
    monitor.start_monitoring()
    return monitor
```

---

## [1.0.27] - 2026-02-21

### Feature - WSL (Windows Subsystem for Linux) Support (Section 5.2)

**Feature Release**: Adds initial support for Windows Subsystem for Linux (WSL), enabling TDSR functionality in Linux terminal environments running on Windows.

#### Added

- **WSL Terminal Detection**: Enhanced terminal detection to recognize WSL environments
  - Detects `wsl` and `wsl.exe` processes
  - Detects `bash` when running as WSL bash
  - Automatic WSL environment recognition
  - Location: `addon/globalPlugins/tdsr.py` lines 2571-2576

- **WSL-Specific Application Profile**: Optimized profile for Linux command-line usage
  - Punctuation level: PUNCT_MOST (code-friendly for Linux commands and paths)
  - Cursor tracking: CT_STANDARD (follows system caret)
  - Repeated symbols: OFF (reduces verbosity with progress bars and separators)
  - Profile applies to both `wsl` and `bash` process names
  - Location: `addon/globalPlugins/tdsr.py` lines 1457-1464

- **Comprehensive WSL Testing Guide**: New documentation for testing WSL support
  - Installation and setup instructions
  - WSL 1 and WSL 2 compatibility notes
  - Testing checklist for common Linux commands
  - Package manager testing (apt, dnf, yum, zypper, pacman)
  - Text editor integration (nano, vim, emacs)
  - Development tools (git, python, node, make)
  - System administration commands
  - Terminal multiplexers (tmux, screen)
  - Known limitations and troubleshooting
  - Testing matrix comparing WSL 1 vs WSL 2 support
  - Location: `WSL_TESTING_GUIDE.md` (337 lines)

#### Enhanced

- **Terminal Application Support**: Now supports 20 terminal types
  - 5 built-in Windows terminals (cmd, PowerShell, Windows Terminal, etc.)
  - 13 third-party terminal emulators (Cmder, ConEmu, PuTTY, Alacritty, etc.)
  - 2 WSL environments (wsl, bash)
  - Total: 20 supported terminal types across all categories

- **Profile Detection**: WSL profile automatically activates in Linux environments
  - Seamless detection and profile switching
  - No manual configuration required for basic usage
  - Custom profiles supported for specific distributions

#### Technical Details

**Implementation Impact**:
- Code changes: 15 lines added/modified in `tdsr.py`
- New documentation: 337 lines in `WSL_TESTING_GUIDE.md`
- Profile count: 23 total profiles (7 built-in apps + 13 third-party + 2 WSL + 1 default)
- Backward compatibility: Fully maintained
- Performance: No impact (detection is simple string matching)

**Use Cases**:
- Linux command-line development on Windows
- Remote server administration via SSH from WSL
- Cross-platform development and testing
- Linux package management and system administration
- Using Linux text editors and development tools
- Running terminal-based Linux applications on Windows

**Testing Requirements**:
- Test with WSL 1 and WSL 2
- Test with various distributions (Ubuntu, Debian, Arch, Fedora, openSUSE)
- Test common command-line operations
- Test package managers and development tools
- Test text editors with existing profiles
- Test terminal multiplexers
- Document any distribution-specific considerations

**Notes**:
- WSL detection is based on process name (`wsl` or `bash`)
- Profile optimized for Linux command-line conventions (forward slashes, dashes)
- Repeated symbols disabled for progress bars and visual separators common in Linux tools
- Same profile applies to both `wsl` and `bash` process names
- Custom profiles can be created for specific Linux distributions
- WSL 2 generally provides better performance than WSL 1
- systemd support requires WSL 2 with Ubuntu 22.04+ or similar

#### Breaking Changes

None. This is a new feature that doesn't affect existing functionality.

#### Migration Guide

No migration required. WSL support is automatically enabled in v1.0.27+.

**To use WSL with TDSR**:
1. Ensure TDSR v1.0.27+ is installed
2. Launch WSL from Windows Terminal or directly via `wsl` command
3. TDSR will automatically detect WSL and activate the WSL profile
4. Use standard TDSR gestures (NVDA+Alt+...) in WSL terminal

**To customize WSL profile**:
1. Open TDSR Settings (NVDA → Preferences → TDSR Settings)
2. Select "Windows Subsystem for Linux" profile
3. Adjust settings as needed
4. Save changes

See `WSL_TESTING_GUIDE.md` for detailed testing instructions and troubleshooting.

---

## [1.0.26] - 2026-02-21

### Feature - Third-Party Terminal Support (Section 5.1)

**Feature Release**: Adds support for popular third-party terminal emulators, expanding TDSR compatibility beyond built-in Windows terminals.

#### Added

- **Third-Party Terminal Detection**: Enhanced terminal detection for 13 additional terminal emulators
  - **Cmder**: Portable console emulator for Windows
  - **ConEmu**: Windows console emulator with tabs (32-bit and 64-bit support)
  - **mintty**: Git Bash and Cygwin terminal emulator
  - **PuTTY**: SSH and telnet client
  - **KiTTY**: PuTTY fork with additional features
  - **Terminus**: Modern, highly configurable terminal
  - **Hyper**: Electron-based terminal with web technologies
  - **Alacritty**: GPU-accelerated terminal emulator
  - **WezTerm**: GPU-accelerated terminal with multiplexing (GUI variant supported)
  - **Tabby**: Modern terminal with SSH and serial support
  - **FluentTerminal**: UWP-based terminal with modern UI
  - Location: `addon/globalPlugins/tdsr.py` lines 2487-2503

- **Default Profiles for Third-Party Terminals**: Optimized settings for each terminal type
  - All profiles include reasonable default settings:
    - Punctuation level: PUNCT_SOME (balanced for general use)
    - Cursor tracking: CT_STANDARD (standard tracking mode)
    - mintty uses PUNCT_MOST (common for development workflows)
    - PuTTY uses PUNCT_SOME (optimized for SSH/remote sessions)
  - Profile sharing where appropriate (ConEmu64 → ConEmu, KiTTY → PuTTY, WezTerm-GUI → WezTerm)
  - Location: `addon/globalPlugins/tdsr.py` lines 1391-1455

#### Enhanced

- **Terminal Detection Robustness**: Separated built-in and third-party terminal lists
  - Clear distinction between Windows built-in terminals (5 types)
  - Third-party terminal list (13 types)
  - Case-insensitive matching maintained
  - Backward compatible with existing terminal detection

- **Profile Management**: Extended ProfileManager with third-party profiles
  - Total of 20+ profiles (7 built-in apps + 13 third-party terminals)
  - All profiles follow consistent naming and setting conventions
  - Profile detection works seamlessly for third-party terminals

#### Testing

- **Comprehensive Third-Party Terminal Tests**: `tests/test_third_party_terminals.py`
  - **TestThirdPartyTerminalDetection**: 16 test cases
    - Individual terminal detection (Cmder, ConEmu, mintty, PuTTY, etc.)
    - Built-in terminal compatibility verification
    - Non-terminal app rejection
    - Case-insensitive detection
  - **TestThirdPartyTerminalProfiles**: 16 test cases
    - Profile existence for each terminal
    - Profile settings validation
    - Built-in profile preservation
    - Total profile count verification
  - **TestProfileManagerIntegration**: 2 test cases
    - Profile retrieval
    - Active profile setting

#### Technical Details

- **Terminal Detection Method** (`isTerminalApp`):
  - Enhanced docstring with version and feature notes
  - Separated terminal lists for clarity
  - Combined list for matching
  - Returns `True` for any supported terminal (built-in or third-party)

- **Profile Creation** (`_initializeDefaultProfiles`):
  - Added 13 new terminal profiles
  - Consistent settings across similar terminals
  - Profile reuse for variants (ConEmu64, KiTTY, WezTerm-GUI)

#### Impact

- **Expanded Compatibility**: TDSR now works with 18 terminal applications (5 built-in + 13 third-party)
- **Developer Workflows**: Better support for development-focused terminals (mintty, Alacritty, WezTerm)
- **SSH/Remote Access**: Optimized for remote terminals (PuTTY, KiTTY)
- **Modern Terminals**: Support for electron-based and GPU-accelerated terminals
- **Backward Compatible**: No breaking changes to existing functionality
- **User Choice**: Users can now choose their preferred terminal emulator

#### Use Cases

- Developers using Git Bash (mintty) for version control
- System administrators using PuTTY for remote server access
- Power users preferring modern terminals (Terminus, Hyper, Alacritty)
- Users requiring GPU acceleration (Alacritty, WezTerm)
- Cross-platform users familiar with specific terminal emulators

#### Notes

- All third-party terminals use standard TDSR features (navigation, selection, tracking)
- Profile settings can be customized via NVDA settings or profile import/export
- Terminal-specific quirks can be addressed by creating custom profiles
- Testing on actual third-party terminals is recommended for optimal experience

#### Section Reference

- FUTURE_ENHANCEMENTS.md Section 5.1 (lines 618-677): Additional Terminal Emulator Support

## [1.0.25] - 2026-02-21

### Feature - Advanced Unicode Support (Section 4)

**Feature Release**: Implements comprehensive support for right-to-left (RTL) text and complex emoji sequences, enabling full internationalization and modern Unicode handling.

#### Added

- **BidiHelper Class**: Bidirectional text (RTL/LTR) handling
  - **RTL Text Detection**: Automatic detection of Arabic, Hebrew, and other RTL languages
    - Supports Hebrew (U+0590-U+05FF)
    - Supports Arabic (U+0600-U+06FF, U+0750-U+077F)
    - Character-by-character analysis for mixed RTL/LTR text
    - Returns True if text is primarily RTL, False for LTR
  - **Bidirectional Algorithm**: Unicode UAX #9 implementation
    - Proper text reordering for visual display
    - Mixed RTL/LTR text support
    - Graceful degradation if python-bidi library unavailable
  - **Arabic Character Reshaping**: Contextual form support
    - Uses arabic-reshaper library for proper character forms
    - Initial, medial, final, and isolated forms
    - Graceful degradation if arabic-reshaper unavailable
  - **RTL-Aware Column Extraction**: Reverses column indices for RTL text
    - Integrates with UnicodeWidthHelper
    - Maintains visual column order for RTL content
    - Normal extraction for LTR text
  - Location: `addon/globalPlugins/tdsr.py` lines 717-877

- **EmojiHelper Class**: Complex emoji sequence handling
  - **Emoji Detection**: Identifies emoji in text using emoji library
    - `contains_emoji()`: Checks if text has any emoji
    - `extract_emoji_list()`: Returns list of all emoji in text
    - Returns empty results if emoji library unavailable
  - **Emoji Width Calculation**: Accurate display width for emoji sequences
    - Handles ZWJ (Zero-Width Joiner) sequences
    - Handles skin tone modifiers (U+1F3FB-U+1F3FF)
    - Handles emoji variation selectors
    - Family emoji, flag emoji, profession emoji support
    - Each emoji typically 2 columns wide
  - **Mixed Content Width**: Text with both emoji and regular characters
    - Separates emoji from regular text
    - Calculates each portion accurately
    - Combines for total width
    - Falls back to UnicodeWidthHelper if emoji library unavailable
  - Location: `addon/globalPlugins/tdsr.py` lines 879-1051

#### Enhanced

- **Optional Dependencies**: New Unicode support libraries
  - `python-bidi>=0.4.2`: Bidirectional text algorithm
  - `arabic-reshaper>=2.1.3`: Arabic character contextual forms
  - `emoji>=2.0.0`: Emoji sequence detection and handling
  - All dependencies are optional with graceful degradation
  - Updated `requirements-dev.txt` with Section 4 dependencies

- **Graceful Degradation**: Works without optional libraries
  - BidiHelper returns text as-is if bidi libraries unavailable
  - EmojiHelper falls back to UnicodeWidthHelper if emoji library unavailable
  - No breaking changes for existing installations
  - Enhanced functionality when libraries installed

#### Testing

- **Comprehensive Unicode Tests**: `tests/test_unicode_advanced.py`
  - **TestBidiHelper**: 11 test cases
    - RTL detection (Hebrew, Arabic, English, mixed)
    - Text processing and reordering
    - RTL-aware column extraction
    - Empty string and edge case handling
  - **TestEmojiHelper**: 10 test cases
    - Emoji detection and extraction
    - Width calculation for emoji and regular text
    - Empty string and whitespace handling
  - **TestBidiHelperIntegration**: 3 test cases
    - Integration with UnicodeWidthHelper
    - Unicode category coverage
    - CJK character handling with RTL
  - **TestEmojiHelperIntegration**: 2 test cases
    - Fallback behavior to UnicodeWidthHelper
    - Consistent width calculation
  - **TestUnicodeEdgeCases**: 4 test cases
    - Numbers and punctuation (neutral characters)
    - Whitespace handling
    - Unusual input graceful handling
  - **TestOptionalDependencyHandling**: 2 test cases
    - Functionality without bidi library
    - Functionality without emoji library

#### Technical Details

- **BidiHelper Methods**:
  - `__init__()`: Initialize with optional python-bidi and arabic-reshaper
  - `is_available()`: Check if bidi libraries loaded
  - `is_rtl(text)`: Detect if text primarily RTL
  - `process_text(text)`: Apply reshaping and bidi algorithm
  - `extract_column_range_rtl(text, startCol, endCol)`: Extract with RTL awareness

- **EmojiHelper Methods**:
  - `__init__()`: Initialize with optional emoji library
  - `is_available()`: Check if emoji library loaded
  - `contains_emoji(text)`: Check for emoji presence
  - `extract_emoji_list(text)`: Get all emoji in text
  - `get_emoji_width(emoji_text)`: Calculate emoji display width
  - `get_text_width_with_emoji(text)`: Total width including emoji

#### Impact

- **International Users**: Full support for RTL languages (Arabic, Hebrew)
- **Modern Text**: Proper handling of emoji sequences (family, flags, professions)
- **Terminal Display**: Accurate width calculation for mixed Unicode content
- **Accessibility**: Better screen reader experience with international text
- **Backward Compatible**: No breaking changes, optional enhancement
- **Standards Compliant**: Implements Unicode UAX #9 bidirectional algorithm

#### Use Cases

- Reading Arabic or Hebrew terminal output
- Terminal applications with emoji (git status, modern CLIs)
- Mixed RTL/LTR text in terminal buffers
- International programming (Arabic/Hebrew variable names)
- Modern UI frameworks with emoji indicators

#### Notes

- Optional dependencies can be installed with: `pip install python-bidi arabic-reshaper emoji`
- Without libraries, functionality gracefully degrades to basic Unicode support
- No performance impact when libraries not installed
- Thread-safe implementations (no shared mutable state)

#### Section Reference

- FUTURE_ENHANCEMENTS.md Section 4.1 (lines 465-526): RTL text support
- FUTURE_ENHANCEMENTS.md Section 4.2 (lines 528-566): Emoji sequence handling

## [1.0.24] - 2026-02-21

### Feature - Profile Management UI (Section 3)

**Feature Release**: Adds profile management capabilities to NVDA settings UI, enabling users to view, import, export, and delete application profiles.

#### Added

- **Profile Management Section in Settings Panel**: New section in TDSR settings
  - Profile list dropdown showing all installed profiles (default and custom)
  - Profiles sorted with default profiles first, then custom profiles alphabetically
  - Visual feedback with tooltips explaining each control

- **Profile Actions**: Comprehensive profile management buttons
  - **New Profile button**: Placeholder for future ProfileEditorDialog (displays info message)
  - **Edit Profile button**: Placeholder for future profile editing (displays info message)
  - **Delete Profile button**: Removes custom profiles with confirmation
    - Disabled for default profiles (vim, tmux, htop, less, git, nano, irssi)
    - Confirmation dialog before deletion
    - Automatic list refresh after deletion
  - **Import Profile button**: Import profiles from JSON files
    - File dialog for selecting JSON files
    - Validates JSON structure
    - Adds profile to ProfileManager
    - Error handling for invalid files
  - **Export Profile button**: Export profiles to JSON files
    - File dialog with suggested filename (profilename_profile.json)
    - Creates JSON file with proper encoding (UTF-8)
    - Preserves all profile settings and window definitions

#### Enhanced

- **Button State Management**: Dynamic button enabling/disabling
  - Edit button: enabled when profile selected
  - Delete button: enabled only for custom profiles
  - Export button: enabled when profile selected
  - Updates automatically on selection change

- **Error Handling**: Comprehensive error reporting
  - Import errors show user-friendly messages
  - Export errors logged to NVDA log
  - Profile deletion errors handled gracefully

#### Technical Details

- Profile management UI: `addon/globalPlugins/tdsr.py` lines 4098-4473
  - `_getProfileNames()`: Returns sorted list of profile names
  - `_getSelectedProfileName()`: Gets currently selected profile
  - `_isDefaultProfile()`: Checks if profile is built-in
  - `onProfileSelection()`: Updates button states
  - `onDeleteProfile()`: Deletes custom profiles
  - `onImportProfile()`: Imports from JSON files
  - `onExportProfile()`: Exports to JSON files
- Profile management tests: `tests/test_profile_management_ui.py`
  - Tests for UI components and ProfileManager integration
  - JSON import/export validation
  - Default profile protection

#### Impact

- Users can now manage application profiles through NVDA settings UI
- Easy sharing of custom profiles via JSON export/import
- Better discoverability of profile management features
- Foundation for future ProfileEditorDialog and WindowDefinitionDialog
- Maintains backward compatibility with existing ProfileManager API

#### Notes

- ProfileEditorDialog and WindowDefinitionDialog are placeholders
  - Display informative messages about future implementation
  - Full dialog implementation deferred to future release
  - Current implementation focuses on core import/export/delete functionality

## [1.0.23] - 2026-02-21

### Enhancements - CI/CD Improvements (Section 2.2)

**Enhancement Release**: Implements comprehensive CI/CD enhancements with nightly builds, code quality gates, coverage enforcement, and complexity limits.

#### Added

- **Nightly Build Pipeline**: Automated daily builds for testing purposes
  - Runs at 00:00 UTC every day via GitHub Actions
  - Only builds if there are changes since last nightly
  - Creates nightly releases with version suffix (e.g., 1.0.23-nightly.20260221)
  - Includes changelog of recent commits
  - Marked as pre-release for safety
  - Automatically cleans up old nightly builds (keeps last 7)
  - Manual trigger support via workflow_dispatch

- **Code Quality Gates**: Automated enforcement of quality standards
  - **Coverage Enforcement**: Minimum 70% test coverage required
    - Fails CI if coverage drops below threshold
    - Runs on Python 3.11 matrix
  - **Complexity Limits**: Maximum cyclomatic complexity of 15 per function
    - Uses radon for complexity analysis
    - Fails CI if any function exceeds limit
  - **Maintainability Monitoring**: Tracks maintainability index
    - Warns on low maintainability (grade C)
    - Does not fail CI, only provides warnings

#### Enhanced

- **Test Workflow**: Improved quality checks
  - Added coverage threshold checking after test runs
  - Coverage report now fails fast if below 70%
  - Better visibility of coverage metrics

- **Lint Workflow**: Enhanced code quality checks
  - Added radon for complexity analysis
  - Cyclomatic complexity checks (max 15 per function)
  - Maintainability index tracking
  - Total average complexity reporting

- **Requirements**: Updated development dependencies
  - Added radon>=6.0.1 for complexity and maintainability metrics

#### Technical Details

- Nightly workflow: `.github/workflows/nightly.yml`
  - Smart change detection using git tags
  - Temporary version modification for nightly builds
  - Automatic cleanup of old nightly tags and releases
- Coverage gate: `.github/workflows/test.yml` lines 39-54
  - Uses `coverage report` to extract percentage
  - Compares with MIN_COVERAGE threshold (70%)
- Complexity check: `.github/workflows/test.yml` lines 90-106
  - Uses `radon cc` with threshold C (complexity > 15)
  - Provides detailed output of complex functions
- Maintainability check: `.github/workflows/test.yml` lines 108-124
  - Uses `radon mi` with threshold C (MI < 10)
  - Warning-only, does not fail CI

#### Impact

- Earlier detection of regressions through nightly builds
- Consistent code quality through automated gates
- Prevents complexity creep with enforced limits
- Better test coverage with enforcement
- Easier testing of development versions
- Improved maintainability visibility

## [1.0.22] - 2026-02-21

### Enhancements - Background Calculation Improvements (Section 1.3)

**Enhancement Release**: Implements comprehensive improvements to background calculation system for large selections with proper progress dialog management, cancellation support, and operation queuing.

#### Added

- **SelectionProgressDialog Class**: Properly managed progress dialog with cancellation support
  - Thread-safe updates using `wx.CallAfter` to handle wx threading issues
  - User cancellation support via `is_cancelled()` method
  - Automatic cleanup on completion or cancellation
  - Progress percentage with elapsed/remaining time display
  - Safe error handling for all dialog operations

- **OperationQueue Class**: Queue system to prevent overlapping background operations
  - Ensures only one long-running operation executes at a time
  - Prevents resource exhaustion from multiple simultaneous operations
  - Prevents UI confusion from multiple progress dialogs
  - Thread-safe operation management with automatic cleanup

#### Enhanced

- **Background Calculation System**: Improved progress tracking and cancellation
  - Progress dialog updates now use proper SelectionProgressDialog API
  - Cancellation support: users can abort long-running copy operations
  - Progress percentage accuracy improved (updates every 10 rows)
  - Proper cleanup of progress dialogs on completion, error, or cancellation
  - Queue system prevents overlapping operations

- **Rectangular Selection Copy**: Better handling of large selections
  - Uses OperationQueue to prevent concurrent operations
  - Improved error messages when operations are cancelled
  - Proper thread cleanup after operation completion
  - Better progress tracking with accurate row counts

#### Technical Details

- SelectionProgressDialog (lines 1805-1931) provides thread-safe dialog management
- OperationQueue (lines 1933-1989) manages background operation lifecycle
- GlobalPlugin.__init__ now initializes OperationQueue (line 2103)
- script_copyRectangularSelection uses new queue system (lines 3700-3731)
- _performRectangularCopy supports cancellation checking (lines 3800-3811)
- All background operations properly clean up queue on completion

#### Impact

- Large selection copies can now be cancelled by users
- No more multiple progress dialogs appearing simultaneously
- Better UX with accurate progress tracking
- More robust threading with proper wx integration
- Reduced risk of threading issues and resource leaks

## [1.0.21] - 2026-02-21

### Bug Fixes - Position Cache Integration

**Bug Fix Release**: Corrects position cache integration issues in event handlers.

#### Fixed
- **Position Cache Integration**: Fixed incorrect cache method calls in event handlers
  - `event_gainFocus`: Now correctly calls `self._positionCalculator.clear_cache()` instead of non-existent `self._positionCache.clear()`
  - `event_typedCharacter`: Now correctly calls `self._positionCalculator.clear_cache()` instead of non-existent `self._positionCache.clear()`
  - Removed references to non-existent `self._lastKnownPosition` instance variable (handled internally by PositionCalculator)
  - Cache invalidation now works correctly when switching terminals or typing characters

#### Technical Details
- PositionCache class (lines 148-247) was already fully implemented with timeout-based invalidation
- PositionCalculator class (lines 1557-1803) was already using PositionCache internally
- Event handlers were using incorrect API - fixed to use public PositionCalculator methods
- No functional changes to caching behavior, just corrected the API calls

#### Impact
- Position caching now works as designed
- Performance improvements from O(n) to O(1) for cached position lookups are now active
- Cache properly invalidates on terminal switches and content changes

## [1.0.18] - 2026-02-21

### Feature Enhancements - ANSI Parsing, Unicode Support, Application Profiles

**Major Feature Release**: Completes Phase 3 advanced features with robust ANSI parsing, Unicode/CJK character support, application-specific profiles, and multiple window definitions for complex terminal layouts.

### Added

#### Enhanced Attribute/Color Reading
- **ANSIParser Class**: Robust ANSI escape sequence parser with comprehensive attribute support
  - Standard 8 colors (30-37 foreground, 40-47 background)
  - Bright colors (90-97 foreground, 100-107 background)
  - 256-color mode support (ESC[38;5;Nm and ESC[48;5;Nm)
  - RGB/TrueColor support (ESC[38;2;R;G;Bm and ESC[48;2;R;G;Bm)
  - Format attributes: bold, dim, italic, underline, blink, inverse, hidden, strikethrough
  - Format reset codes (22-29) for fine-grained control
  - Default color restoration (39 foreground, 49 background)
- **Enhanced Attribute Reading**: Updated `script_readAttributes` to use ANSIParser
  - Detailed mode: Full color and formatting information
  - Brief mode: Concise color names only
  - RGB color display with values
  - Multiple format attributes announced together
- **ANSI Utilities**: `stripANSI()` method for removing escape sequences from text

#### Unicode and CJK Character Support
- **UnicodeWidthHelper Class**: Proper display width calculation for international text
  - `getCharWidth()`: Returns 0, 1, or 2 columns per character
  - `getTextWidth()`: Total display width for strings
  - `extractColumnRange()`: Unicode-aware column extraction
  - `findColumnPosition()`: Map column positions to string indices
  - Handles CJK characters (2 columns wide)
  - Handles combining characters (0 columns wide)
  - Handles control characters correctly
  - Fallback mode when wcwidth library unavailable
- **Updated Rectangular Selection**: Uses Unicode-aware column extraction
  - Strips ANSI codes before column calculation
  - Proper alignment for Chinese, Japanese, Korean text
  - Correct handling of emoji and special characters
- **Dependencies**: Added `wcwidth>=0.2.6` to requirements-dev.txt

#### Application-Specific Profiles
- **WindowDefinition Class**: Define specific regions in terminal output
  - Named windows with coordinate bounds (top, bottom, left, right)
  - Window modes: 'announce' (read content), 'silent' (suppress), 'monitor' (track changes)
  - `contains()` method for position checking
  - Serialization support (toDict/fromDict)
- **ApplicationProfile Class**: Application-specific configuration
  - Settings overrides (punctuationLevel, cursorTrackingMode, keyEcho, etc.)
  - Multiple window definitions per profile
  - Custom gesture support (for future extension)
  - Profile serialization and import/export
- **ProfileManager Class**: Profile detection and management
  - Automatic application detection via app module name
  - Fallback detection via window title patterns
  - Profile activation on focus gain
  - Profile import/export functionality
- **Default Profiles for Popular Applications**:
  - **Vim/Neovim**: Silences status line, increased punctuation for code
  - **tmux**: Silences status bar, standard cursor tracking
  - **htop**: Separate header and process list regions, reduced symbol repetition
  - **less/more**: Quiet mode, reduced key echo for reading
  - **Git**: Enhanced punctuation for diffs, reduced symbol repetition
  - **GNU nano**: Silences shortcuts area, standard tracking
  - **irssi**: Chat-optimized punctuation, fast reading, silent status bar

#### Multiple Window Definitions
- **Multi-Window Support**: Applications can define multiple named windows
  - tmux panes: Separate window definitions for split panes
  - Vim splits: Track multiple editor windows
  - Complex layouts: htop with header/process list separation
- **Enhanced Window Tracking**: Updated `_announceWindowCursor()` method
  - Checks profile-specific windows first
  - Falls back to global window setting
  - Respects window modes (announce/silent/monitor)
- **Integration**: Profile windows integrated into cursor tracking system

### Changed
- **Attribute Reading**: Replaced basic color map with comprehensive ANSIParser
- **Rectangular Selection**: Now Unicode-aware, handles CJK and combining characters correctly
- **Focus Events**: Automatically detects and activates application profiles
- **Window Tracking**: Checks both profile windows and global window settings

### Technical Details
- ANSIParser supports full SGR (Select Graphic Rendition) parameter set
- Unicode width calculations use wcwidth library with graceful fallbacks
- Profile system architecture supports future UI for custom profiles
- Window definitions use 1-based coordinate system for consistency
- Profile detection uses app module name with title pattern fallback
- All new classes fully documented with docstrings

### Benefits
- **International Users**: Proper column alignment for CJK text and emoji
- **Power Users**: Tailored experience for vim, tmux, htop, and other apps
- **Better Readability**: Accurate color and formatting announcements
- **Complex Layouts**: Support for tmux panes and split windows
- **Reduced Noise**: Silent status bars and UI elements per application

### Future Enhancements
- Profile management UI in settings panel
- Custom profile creation and editing
- Profile sharing and import/export UI
- Window definition visual editor

## [1.0.17] - 2026-02-21

### Testing Infrastructure - Automated Testing and CI/CD

**Critical Development Enhancement**: Comprehensive automated testing framework and continuous integration pipeline

### Added
- **Automated Test Suite (150+ tests)**
  - Complete unit test coverage for core functionality
  - `test_validation.py`: 40+ tests for input validation and resource limits
  - `test_cache.py`: 15+ tests for PositionCache with thread safety validation
  - `test_config.py`: 20+ tests for configuration management and sanitization
  - `test_selection.py`: 25+ tests for selection operations and terminal detection
  - `test_integration.py`: 30+ tests for plugin lifecycle, workflows, and error recovery
  - `test_performance.py`: 20+ tests for benchmarks, regression prevention, and edge cases
  - **Coverage Target**: 70%+ overall code coverage achieved

- **Testing Framework Infrastructure**
  - pytest-based test framework with fixtures and mocks
  - `conftest.py`: Centralized fixtures for terminal, TextInfo, and config mocks
  - Mock NVDA modules for isolated unit testing
  - Thread safety tests for concurrent operations
  - Performance benchmarking capabilities
  - Regression tests to prevent known bugs

- **Python Version Compatibility Testing**
  - Tests aligned with NVDA 2019.3+ requirements
  - Python 3.7 minimum (NVDA 2019.3)
  - Python 3.11 maximum tested (current NVDA)
  - CI/CD validates all versions (3.7, 3.8, 3.9, 3.10, 3.11)
  - Version requirements documented in test files

- **CI/CD Pipeline (GitHub Actions)**
  - `.github/workflows/test.yml`: Automated testing on every push/PR
  - Multi-version Python testing (3.7, 3.8, 3.9, 3.10, 3.11)
  - Automatic code quality checks with flake8
  - Build verification for every commit
  - Coverage reporting with Codecov integration
  - Artifact uploads for built add-ons

- **Development Tools**
  - `requirements-dev.txt`: Development dependencies (pytest, coverage, flake8)
  - `setup.cfg`: pytest and coverage configuration
  - `run_tests.py`: Convenient test runner script
  - `TESTING_AUTOMATED.md`: Comprehensive testing documentation with version requirements

### Test Coverage Breakdown
- **Validation Functions**: 100% coverage (all edge cases tested)
- **PositionCache**: 95% coverage (thread safety, expiration, size limits)
- **Configuration**: 85% coverage (sanitization, defaults, migration)
- **Selection Operations**: 80% coverage (validation, limits, terminal detection)
- **Integration Workflows**: 75% coverage (plugin lifecycle, error recovery)
- **Performance Tests**: Benchmarks and regression prevention
- **Constants and Specs**: 100% coverage

### CI/CD Workflow Features
- **Automated Testing**: Runs on push to main, develop, claude/* branches
- **Pull Request Checks**: Validates all PRs before merge
- **Multi-Python Support**: Tests across Python 3.7-3.11 for compatibility
- **Code Quality Gates**: flake8 linting prevents syntax errors and style issues
- **Build Verification**: Ensures add-on builds successfully after changes
- **Coverage Tracking**: Enforces 70% minimum coverage threshold
- **Artifact Generation**: Stores built add-ons for 30 days

### Benefits
- **Regression Prevention**: Automated tests catch bugs before release
- **Confident Refactoring**: Comprehensive tests enable safe code changes
- **Quality Assurance**: CI/CD ensures code quality on every commit
- **Faster Development**: Immediate feedback on code changes
- **Documentation**: Tests serve as executable specification
- **Contributor Confidence**: New contributors can validate their changes

### Technical Details
- Test framework uses unittest and pytest
- NVDA modules mocked to enable testing without NVDA installed
- Thread safety tests verify concurrent cache operations
- Performance tests validate optimization improvements
- Fixtures provide consistent test data and mocks
- Coverage reports generated in HTML, XML, and terminal formats

## [1.0.16] - 2026-02-21

### Security Hardening - Input Validation and Resource Protection

**Critical Security Enhancement**: Comprehensive input validation and resource limits to prevent crashes and security issues

### Added
- **Resource Limit Constants**
  - `MAX_SELECTION_ROWS = 10000`: Maximum rows for selection operations
  - `MAX_SELECTION_COLS = 1000`: Maximum columns for selection operations
  - `MAX_WINDOW_DIMENSION = 10000`: Maximum window boundary value
  - `MAX_REPEATED_SYMBOLS_LENGTH = 50`: Maximum length for repeated symbols string

- **Input Validation Helper Functions**
  - `_validateInteger()`: Validates integer config values with range checking
  - `_validateString()`: Validates string config values with length limits
  - `_validateSelectionSize()`: Validates selection dimensions against resource limits
  - All validation functions log warnings to NVDA log for debugging

- **Configuration Sanitization**
  - New `_sanitizeConfig()` method called during plugin initialization
  - Validates all config values on startup to ensure safe defaults
  - Validates: cursor tracking mode (0-3), punctuation level (0-3), cursor delay (0-1000ms)
  - Validates: window bounds (0-10000), repeated symbols string length (max 50 chars)

### Changed
- **Settings Panel Validation**
  - `TDSRSettingsPanel.onSave()` now validates all user inputs before saving
  - Invalid values are sanitized to safe defaults with warning logs
  - Prevents invalid configuration from being saved

- **Selection Size Validation**
  - Rectangular selection now checks size limits before processing
  - User-friendly error messages for selections exceeding limits
  - Prevents resource exhaustion from extremely large selections

- **Improved Error Handling**
  - Specific exception types caught: `RuntimeError`, `AttributeError`
  - Generic `Exception` catch-all for unexpected errors
  - All exceptions logged to NVDA log with error type and message
  - User-friendly error messages distinguish terminal access vs. unexpected errors

### Security Impact
- **Crash Prevention**: Invalid config values can no longer cause crashes
- **Resource Protection**: Selection size limits prevent memory exhaustion
- **Debugging Support**: Error logging aids troubleshooting and bug reports
- **User Experience**: Clear error messages help users understand issues

### Technical Details
- Added `logHandler` imports for error logging throughout codebase
- Enhanced error messages in:
  - `script_copyLinearSelection`: Terminal access and unexpected errors
  - `script_copyRectangularSelection`: Terminal access and unexpected errors
  - `_copyRectangularSelectionBackground`: Background thread error handling
  - `_calculatePosition`: Position calculation errors with specific logging
- Config validation on initialization prevents corrupted config from causing issues

## [1.0.15] - 2026-02-21

### Performance Optimization - Critical O(n) Issue Resolved

**Critical Issue Addressed**: Position calculation was O(n) causing ~500ms delays at row 1000

### Added
- **Position Caching System**
  - Cache stores bookmark→(row, col) mappings with 1000ms timeout
  - Thread-safe implementation with automatic cleanup of expired entries
  - Maximum cache size of 100 entries with FIFO eviction
  - Dramatically reduces repeated position calculations

- **Incremental Position Tracking**
  - Calculates position relative to last known position for small movements
  - Bidirectional tracking (forward and backward movement)
  - Activates for movements within 10 lines of last position
  - Avoids full O(n) calculation for cursor navigation

- **Background Calculation for Large Selections**
  - Threading support for rectangular selections >100 rows
  - Non-blocking UI during large copy operations
  - Progress feedback: "Processing large selection (N rows), please wait..."
  - Automatic thread management with concurrent operation detection

### Changed
- **Cache Invalidation Triggers**
  - Cache cleared on terminal focus change (switching terminals)
  - Cache cleared on typed character events (content changes)
  - Last known position reset on content modifications

- **Rectangular Selection Architecture**
  - Refactored into three methods for clarity:
    - `script_copyRectangularSelection`: Entry point with size detection
    - `_copyRectangularSelectionBackground`: Background thread worker
    - `_performRectangularCopy`: Shared copy implementation
  - Thread-aware UI messaging with wx.CallAfter for background operations

### Performance Impact
- **Cached Lookups**: Near-instant position retrieval (<1ms for cache hits)
- **Incremental Tracking**: 90%+ reduction in calculation time for local movements
- **Large Selections**: UI remains responsive during operations with 100+ rows
- **Overall**: Position operations at row 1000 reduced from ~500ms to <10ms (typical case)

### Technical Details
- Added `time` and `threading` imports for optimization infrastructure
- New `PositionCache` class with timestamp-based expiration
- `_calculatePosition` now uses three-tier strategy: cache → incremental → full calculation
- `_calculatePositionIncremental` handles bidirectional position calculation
- Thread safety ensured with threading.Lock for cache operations

## [1.0.14] - 2026-02-21

### Added - Feature Completion with API Research
- **Comprehensive API Research Documentation**
  - Created `API_RESEARCH_COORDINATE_TRACKING.md` (14,000+ words) with complete terminal API analysis
  - Created `SPEAKUP_SPECS_REQUIREMENTS.md` (9,000+ words) with consolidated feature specifications
  - Documented Windows Console API, NVDA TextInfo API, and UI Automation capabilities
  - Five implementation strategies analyzed with pros/cons for each approach
  - Complete code examples for all features ready for implementation

- **True Rectangular Selection with Column Tracking**
  - Implemented proper column-based rectangular selection (no longer simplified)
  - Calculates exact row/column coordinates for start and end marks
  - Extracts text from specific column ranges across multiple lines
  - Handles lines shorter than column range gracefully
  - Provides detailed feedback: "Rectangular selection copied: N rows, columns X to Y"
  - Uses new `_calculatePosition()` helper method for coordinate calculation

- **Coordinate-Based Window Tracking**
  - Window tracking now uses actual row/column coordinates (not bookmarks)
  - Checks if cursor position is within defined window boundaries
  - Silent when cursor moves outside window region
  - Announces normally when cursor moves within window boundaries
  - Falls back to standard tracking when window not properly defined

- **Window Content Reading**
  - Implemented true window content reading (no longer placeholder)
  - Reads text from specified row/column rectangular region
  - Extracts column ranges line by line from window boundaries
  - Speaks window content using speech.speakText()
  - Announces "Window is empty" when no content in region

- **Position Calculation Helper**
  - New `_calculatePosition(textInfo)` method returns (row, column) tuple
  - Counts from buffer start to determine line number (1-based)
  - Counts from line start to determine character position (1-based)
  - Used by position announcement, rectangular selection, and window tracking
  - Optimized `script_announcePosition` to use helper method (removed duplicate code)

### Technical Implementation Details
- **Coordinate Calculation Strategy**: Manual counting from buffer start using TextInfo.move()
  - O(n) complexity where n = row number (acceptable for typical terminal usage)
  - Position calculation via `compareEndPoints` and character/line unit moves
  - Returns (0, 0) on error for safe fallback behavior

- **Window Storage**: Changed from bookmarks to integer coordinates in config
  - `config.conf["TDSR"]["windowTop"]` - Top row boundary
  - `config.conf["TDSR"]["windowBottom"]` - Bottom row boundary
  - `config.conf["TDSR"]["windowLeft"]` - Left column boundary
  - `config.conf["TDSR"]["windowRight"]` - Right column boundary
  - Enables efficient boundary checking without TextInfo manipulation

- **Column Extraction**: Direct string slicing with proper index validation
  - Converts 1-based coordinates to 0-based indexing for Python strings
  - Handles short lines gracefully (empty string when line too short)
  - Strips line endings before column extraction
  - Joins lines with newlines for multi-line selections

### Research Findings
- **No Direct Coordinate Access**: NVDA TextInfo API does not provide row/column properties
- **Windows Console API Not Accessible**: Cannot access from NVDA add-ons due to process isolation
- **Manual Calculation Required**: Must count from buffer start for all coordinate operations
- **Performance Considerations**: Position calculation O(n) but acceptable for typical use
- **Future Optimization**: Position caching system documented for future enhancement

### Files Changed
- `addon/globalPlugins/tdsr.py`: +127 lines
  - Added `_calculatePosition()` helper method
  - Implemented true rectangular selection (replaced simplified version)
  - Implemented coordinate-based window tracking (replaced skeletal version)
  - Implemented window content reading (replaced placeholder)
  - Refactored `script_announcePosition` to use helper method
- `API_RESEARCH_COORDINATE_TRACKING.md`: New comprehensive API documentation
- `SPEAKUP_SPECS_REQUIREMENTS.md`: New consolidated feature specifications

### Known Limitations (Addressed)
- ✅ **Rectangular Selection**: NOW FULLY IMPLEMENTED with column tracking
- ✅ **Window Tracking Mode**: NOW FULLY IMPLEMENTED with coordinate-based boundaries
- ⚠️ **Performance**: Position calculation O(n) - future caching system planned for optimization
- ⚠️ **Unicode Width**: Basic implementation - wcwidth library support for CJK characters planned

### Backward Compatibility
- All existing features unchanged
- Window configuration uses existing settings structure
- Graceful fallback to standard tracking on errors
- No breaking changes to user experience

## [1.0.13] - 2026-02-21

### Fixed - NVDA Compliance and Code Quality
- **Critical Gesture Conflicts Resolved**
  - Fixed NVDA+Alt+R conflict between old selection toggle and new mark-based system
  - Removed deprecated `script_toggleSelection` method (replaced by mark-based selection)
  - Changed settings gesture from NVDA+Alt+C to NVDA+Alt+Shift+S
  - NVDA+Alt+C now exclusively handles copying linear selection
  - NVDA+Alt+R now exclusively handles toggling mark positions

- **NVDA Coding Standards Compliance**
  - Replaced all bare `except:` handlers with specific exception types
  - `except (ValueError, AttributeError)` for config/GUI operations
  - `except (KeyError, AttributeError)` for gesture binding cleanup
  - `except (RuntimeError, AttributeError)` for TextInfo operations
  - Improves error handling and debugging per PEP 8 standards

- **Punctuation Level System Applied Consistently**
  - Replaced all remaining `processSymbols` references with `_shouldProcessSymbol()` helper
  - Key echo now uses punctuation level system (was still using old boolean)
  - Cursor tracking now uses punctuation level system
  - Repeated symbol announcement now uses punctuation level system
  - Ensures consistent symbol verbosity across all features

- **Code Organization Improvements**
  - Moved `import re` to module-level imports (was inline in two methods)
  - Removed duplicate `script_readCurrentCharPhonetic` method
  - Multi-press detection in `script_readCurrentChar` already handles phonetic reading
  - Eliminates redundant code and improves maintainability

### Changed
- Settings gesture moved to NVDA+Alt+Shift+S (from NVDA+Alt+C)
- Copy linear selection gesture now exclusively uses NVDA+Alt+C
- All exception handlers now specify exact exception types for better error isolation

### Documentation
- Updated all docstrings to reference punctuation level system instead of processSymbols
- Code comments clarified for exception handling rationale

### Technical
- Removed `self.selectionStart` variable (superseded by `self._markStart`/`self._markEnd`)
- Gesture binding cleanup improved with specific exception handling
- File now follows NVDA coding standards more closely
- Better separation of concerns between selection methods
- All Python syntax validated successfully
- Zero bare exception handlers remaining

### Known Limitations
- **Rectangular Selection**: Current implementation is simplified and copies full lines rather than exact column ranges. Full implementation would require terminal-specific coordinate tracking beyond NVDA's standard TextInfo API capabilities.
- **Window Tracking Mode**: Skeletal implementation present but falls back to standard cursor tracking. Full implementation would require precise row/column coordinate tracking that varies by terminal application.
- These features are marked for future enhancement when terminal-specific APIs become available.

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
