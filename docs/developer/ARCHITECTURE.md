# Terminal Access for NVDA - Architecture Overview

**Version:** 2.0.0-beta.15
**Last Updated:** 2026-07-12

## Table of Contents

1. [System Overview](#system-overview)
2. [Module Structure](#module-structure)
3. [Dependency Flow](#dependency-flow)
4. [Event Handling Pipeline](#event-handling-pipeline)
5. [Settings Architecture](#settings-architecture)
6. [History: Native Layer (Removed)](#history-native-layer-removed)
7. [File Layout](#file-layout)
8. [Data Flow](#data-flow)
9. [Testing Strategy](#testing-strategy)
10. [CI/CD Pipeline](#cicd-pipeline)

## System Overview

Terminal Access for NVDA is an NVDA global plugin that makes Windows terminals more accessible. It extends NVDA's review cursor with terminal-specific navigation, selection, search, and reading features.

### Design Principles

- **Non-intrusive**: Works alongside NVDA's built-in terminal support
- **Fast**: Caches expensive operations and offloads blocking work to background threads
- **Extensible**: Application profiles customize behavior per terminal app
- **Accessible-first**: Every feature is designed for screen reader users

### Technology Stack

- **Language**: Python 3.11+, pure Python (no native binaries)
- **Framework**: NVDA Global Plugin API
- **UI**: wxPython (via NVDA's GUI helpers)
- **Dependencies**: wcwidth for Unicode display width when importable, with a standard library fallback based on unicodedata

## Module Structure

The codebase is split across a main plugin file and extracted library modules.

Line counts are omitted on purpose; they rot faster than descriptions.

| Module | What it does |
|--------|-------------|
| `globalPlugins/terminalAccess.py` | GlobalPlugin class, command layer, overlay class selection, terminal event delegate handlers, all script definitions |
| `lib/_runtime.py` | Runtime dependency registry. Holds references to shared functions and modules that lib modules need but cannot import directly (avoids circular imports). Populated by `terminalAccess.py` at startup. |
| `lib/config.py` | Config constants (`CT_OFF`, `CT_STANDARD`, etc.), `confspec` dict, validation functions (`_validateInteger`, `_validateString`, `_validateSelectionSize`), `ConfigManager` class |
| `lib/caching.py` | `PositionCache` (bookmark-keyed LRU with TTL), `TextDiffer` (line-level change detection) |
| `lib/navigation.py` | `TabManager` (per-tab state isolation), `BookmarkManager` (named bookmarks with line content labels), `BookmarkListDialog` (factory that builds the bookmark list on top of `BrowsableListDialog`) |
| `lib/operations.py` | `SelectionProgressDialog` (thread-safe progress with cancellation), `OperationQueue` |
| `lib/profiles.py` | `ApplicationProfile`, `WindowDefinition`, `ProfileManager` (detection + defaults for vim, tmux, htop, less, git, nano, irssi), `ProfileSelectionDialog` |
| `lib/search.py` | `OutputSearchManager` (incremental text search, pure Python), `UrlExtractorManager` (URL detection and opening), `UrlListDialog` |
| `lib/text_processing.py` | `ANSIParser` (color/formatting detection), `UnicodeWidthHelper` (CJK display width), `BidiHelper`, `EmojiHelper`, `ErrorLineDetector` (error/warning line classification with word-boundary regex patterns) |
| `lib/window_management.py` | `WindowMonitor` (background text polling), `WindowManager` (rectangular screen region tracking), `PositionCalculator` |
| `lib/settings_panel.py` | `TerminalAccessSettingsPanel` with three flat sections: Speech and Tracking, NVDA Gesture Conflicts, Application Profiles |
| `lib/terminal_overlay.py` | `TerminalAccessTerminal` NVDAObject overlay: replaces NVDA's LiveText output handling (coalescing, blank suppression, audio cues) and delegates terminal events to the plugin |
| `lib/ai_turn_tokenizer.py` | `AITurnTokenizer` and `classify_ai_line()`: detect AI CLI conversation turns (user, assistant, tool, system) and navigate between turns and code spans |
| `lib/code_block_reader.py` | `CodeBlock`, `CodeBlockDetector`: fenced code block detection with navigation, copy, and offline explanation helpers |
| `lib/streaming_delta.py` | `StreamingDeltaTracker`, `Delta`: buffer snapshot diffing with debounce and verbosity-aware speech and braille output |
| `lib/privacy.py` | `PrivacyGuard`: gates local opt-in processing (summarization, code explain, AI turn parsing) behind config flags; it does not authorize or perform uploads. Explicitly opening a detected URL is handled separately by the default browser. |
| `lib/gesture_conflicts.py` | `GestureConflictDetector`: detects gesture conflicts with other NVDA add-ons |
| `lib/audio_cues.py` | Tone definitions, `play_cue()`, braille message formatting, verbosity logic, buffer change descriptions |
| `lib/table_reader.py` | `TableDetector`, `TableNavigator`: column-aware table reading for docker ps, kubectl, ls -l, psql, and markdown pipe tables |
| `lib/tutorial.py` | First-run tutorial: short spoken walkthrough of the essential gestures, replayable from the command layer |
| `lib/summarizer.py` | `OutputSummarizer`: offline extractive summary, scores lines by heuristics and returns the top N in original order |
| `lib/section_tokenizer.py` | `SectionTokenizer`: classifies buffer lines into semantic sections (prompt, error, warning, stack trace, progress, timestamp, heading, output) with navigation |
| `lib/list_dialogs.py` | `BrowsableListDialog` plus pure data-prep helpers shared by the bookmark, section, AI turn, search result, and command finder dialogs |
| `lib/diagnostics.py` | Diagnostic report builder: plain-text environment and buffer sample a user can attach to a bug report |
| `lib/progress_milestones.py` | `ProgressMilestoneTracker`: extracts percentages from output lines and announces only when a milestone threshold is crossed |

### Removed

| Item | Notes |
|------|-------|
| **NewOutputAnnouncer** | Removed entirely. NVDA+Shift+N toggle, coalesce/max-lines/strip-ansi settings are gone. |
| **CommandHistoryManager** | Removed in v2.0.0. Shells have built-in history navigation. |
| **CT_HIGHLIGHT** | Removed in v2.0.0. Modern terminals strip ANSI from UIA text. CT_WINDOW is now mode 2. |
| **Rectangular Selection** | Removed in v2.0.0. Use linear selection (NVDA+C). |

## Dependency Flow

`_runtime.py` acts as the hub between the main plugin and library modules. Library modules import `_runtime` to access shared functions without importing `terminalAccess.py` directly.

```
terminalAccess.py (main plugin)
    │
    │  populates at startup
    ▼
lib/_runtime.py  ◄──────────── lib modules read from here
    │
    │  holds references to:
    ├── strip_ansi          (ANSI escape removal, default: identity)
    ├── make_text_differ    (TextDiffer factory)
    ├── read_terminal_text  (terminal buffer reader)
    ├── make_position_cache (PositionCache factory)
    ├── api_module          (NVDA api module)
    └── webbrowser_module   (Python webbrowser module)

Dependency direction:

    terminalAccess.py
        ├── lib/config.py
        ├── lib/caching.py
        ├── lib/navigation.py
        ├── lib/operations.py
        ├── lib/profiles.py
        ├── lib/search.py        ──► lib/_runtime.py
        ├── lib/text_processing.py
        ├── lib/window_management.py ──► lib/_runtime.py
        ├── lib/terminal_overlay.py  ──► lib/text_processing.py, lib/profiles.py
        ├── lib/ai_turn_tokenizer.py ──► lib/text_processing.py
        ├── lib/code_block_reader.py ──► lib/text_processing.py
        ├── lib/streaming_delta.py
        ├── lib/privacy.py
        └── lib/settings_panel.py   (lazy-imports terminalAccess)
```

## Event Handling Pipeline

### Terminal Overlay Delegation

`GlobalPlugin.chooseNVDAObjectOverlayClasses` inserts the `TerminalAccessTerminal` overlay (`lib/terminal_overlay.py`) at the front of the class list for supported terminals. The overlay replaces NVDA's LiveText output handling and is the entry point for terminal events. The GlobalPlugin has no global `event_caret`, `event_textChange`, or `event_typedCharacter` handlers, so the addon stays out of NVDA's event chain for non-terminal windows.

The overlay resolves the running plugin through a module-level registration: `GlobalPlugin.__init__` calls `terminal_overlay.set_active_plugin(self)` and `terminate()` clears it. Each overlay event delegates to a plugin method that owns the shared state (position cache, cursor timer, repeated-symbol state):

| Overlay event | Plugin delegate | Behavior |
|---------------|-----------------|----------|
| `event_caret` | `_handleTerminalCaret(obj)` | Debounced cursor tracking, blank suppression, error cues. NVDA's native caret speech is suppressed. |
| `event_textChange` | `_handleTerminalTextChange(obj)` | Activity tones, progress milestones, quiet-mode error cues. The return value decides whether the LiveText monitor thread is woken to speak new output (not woken in quiet mode). |
| `event_typedCharacter` | `_terminalTypedCharacter(obj, ch, speak_default)` | Key echo decisions and quiet-mode suppression. `speak_default` runs NVDA's own character echo. |

`_reportNewLines` lives in the overlay itself and coalesces output: blank lines are always suppressed, small output (up to 3 lines) is spoken fully, moderate output (4 to 20 lines) plays an activity tone and speaks the last 3 lines, and bulk output (21 or more lines) announces only a line count. Error and warning lines get audio cues via `ErrorLineDetector`.

### event_gainFocus breakdown

`event_gainFocus` was refactored from a monolithic method into focused helpers called by `_onTerminalFocus`:

| Method | Purpose |
|--------|---------|
| `event_gainFocus` | Entry point. Calls `nextHandler()`, then checks terminal status. |
| `_updateGestureBindingsForFocus(obj)` | Returns False if not a terminal. |
| `_onTerminalFocus(obj)` | Orchestrates the helpers below. |
| `_handleSearchJumpSuppression()` | Preserves review cursor after a search jump. |
| `_initializeManagers(obj)` | Creates or updates Tab, Bookmark, Search, and URL managers. |
| `_detectAndApplyProfile(obj)` | Matches app name or window title to a profile. |
| `_announceProfileIfNew(obj)` | Speaks the profile name on terminal switch. |
| `_bindReviewCursor(obj)` | Attaches the NVDA review cursor to the terminal. |
| `_announceHelpIfNeeded()` | Shows the first-run help hint. |

### Command Layer

The command layer (NVDA+') gives single-key access to all features:

1. `_enterCommandLayer()` binds single-key gestures and plays an 880 Hz tone
2. User presses a key (e.g., `F` for search, `B` for bookmarks)
3. `_exitCommandLayer()` unbinds gestures and plays a 440 Hz tone
4. Auto-exits on focus loss via `_disableTerminalGestures`

### Gesture Scoping

All gestures stay in `_gestureMap` so they appear in NVDA's Input Gestures dialog. The `getScript()` override returns `None` for Terminal Access gestures when the focus is not a supported terminal. NVDA then falls through to its native command for the same key.

`_CONFLICTING_GESTURES` is a `frozenset` listing gesture identifiers that overlap with NVDA built-in commands (e.g., NVDA+C). Only these appear in the NVDA Gesture Conflicts settings checklist.

### Terminal Detection

`isTerminalApp()` checks `appModule.appName` against the `_SUPPORTED_TERMINALS` frozenset using exact match (not substring). This prevents false positives from apps like PowerToys Command Palette.

### Cursor Tracking

```
TerminalAccessTerminal.event_caret (overlay)
    ↓
_handleTerminalCaret(obj)
    ↓
Start timer (configurable delay, 0-1000 ms)
    ↓
Timer expires → _announceCursorPosition(obj)
    ↓
Check tracking mode:
    CT_STANDARD → _announceStandardCursor()
    CT_WINDOW → _announceWindowCursor()
```

### Audio Feedback

`_checkErrorAudioCue()`: called from `_handleTerminalCaret` and `_handleTerminalTextChange` when quiet mode is active and `errorAudioCuesInQuietMode` is enabled. Reads the current line, calls `ErrorLineDetector.classify()`, and plays a tone for error or warning lines.

`_checkOutputActivityTone()`: plays two ascending tones (600 + 800 Hz) when new program output appears. Controlled by `outputActivityTones`. Repeated tones suppressed for the duration set by `outputActivityDebounce`.

## Settings Architecture

Settings were extracted from the main plugin into two modules:

### lib/config.py

- Defines `confspec` dict registered at `config.conf.spec["terminalAccess"]`
- Constants: `CT_OFF`, `CT_STANDARD`, `CT_WINDOW`, `PUNCT_*`, resource limits
- Validation: `_validateInteger()`, `_validateString()`, `_validateSelectionSize()`
- `ConfigManager` class wraps `config.conf["terminalAccess"]` with typed get/set, migration, and bulk validation

### lib/settings_panel.py

- `TerminalAccessSettingsPanel` extends NVDA's `SettingsPanel`
- Three flat sections (no collapsible panes):
  - **Speech and Tracking**: cursor tracking, key echo, quiet mode, punctuation level, tracking mode, cursor delay, line pause, verbose mode, indentation, repeated symbols, error audio cues, output activity tones, default profile, reset button
  - **NVDA Gesture Conflicts**: checklist of conflicting gestures from `_CONFLICTING_GESTURES`. Unchecked gestures are disabled but remain accessible through the command layer.
  - **Application Profiles**: dropdown with Active/Default indicators, New/Edit/Delete/Import/Export buttons
- Lazy-imports from `terminalAccess.py` to avoid circular dependencies

## History: Native Layer (Removed)

Early 2.0.0 betas shipped an optional Rust layer: a DLL loaded over ctypes and a helper process reached over a named pipe. It was removed before 2.0.0 final. The helper's pipe reads hung for seconds in the field on some terminals, and the FFI paths measured slower than the plain Python implementations they were meant to accelerate. Going pure Python also drops per-architecture binaries, which lets the same package run on ARM64. Terminal reads now run in-process through `makeTextInfo`, search and ANSI stripping are pure Python, and Unicode width uses wcwidth when importable with a standard library fallback.

## File Layout

```
addon/
├── globalPlugins/
│   └── terminalAccess.py      # Main plugin
├── lib/
│   ├── __init__.py
│   ├── _runtime.py            # Runtime dependency registry
│   ├── ai_turn_tokenizer.py   # AITurnTokenizer, classify_ai_line
│   ├── audio_cues.py          # Tone map, play_cue, braille formatting
│   ├── caching.py             # PositionCache, TextDiffer
│   ├── code_block_reader.py   # CodeBlock, CodeBlockDetector
│   ├── config.py              # Config constants, confspec, validation
│   ├── diagnostics.py         # Diagnostic report builder
│   ├── gesture_conflicts.py   # GestureConflictDetector
│   ├── list_dialogs.py        # BrowsableListDialog, data-prep helpers
│   ├── navigation.py          # TabManager, BookmarkManager, BookmarkListDialog
│   ├── operations.py          # SelectionProgressDialog, OperationQueue
│   ├── privacy.py             # PrivacyGuard
│   ├── profiles.py            # ApplicationProfile, WindowDefinition, ProfileManager, ProfileSelectionDialog
│   ├── progress_milestones.py # ProgressMilestoneTracker
│   ├── search.py              # OutputSearchManager, UrlExtractorManager, UrlListDialog
│   ├── section_tokenizer.py   # SectionTokenizer
│   ├── settings_panel.py      # TerminalAccessSettingsPanel
│   ├── streaming_delta.py     # StreamingDeltaTracker, Delta
│   ├── summarizer.py          # OutputSummarizer
│   ├── table_reader.py        # TableDetector, TableNavigator
│   ├── terminal_overlay.py    # TerminalAccessTerminal overlay
│   ├── text_processing.py     # ANSIParser, UnicodeWidthHelper, BidiHelper, EmojiHelper, ErrorLineDetector
│   ├── tutorial.py            # First-run tutorial steps
│   └── window_management.py   # WindowManager, WindowMonitor, PositionCalculator
```

## Data Flow

### Navigation Command

```
User presses I in command layer (read current line)
    ↓
script_readCurrentLine()
    ↓
isTerminalApp() → verify supported terminal
    ↓
_getReviewPosition() → get TextInfo
    ↓
Expand to UNIT_LINE
    ↓
Extract text → strip ANSI → process punctuation
    ↓
ErrorLineDetector.classify() → play audio cue if error/warning (errorAudioCues)
    ↓
speech.speakText() → NVDA speaks the line
```

### Selection

```
NVDA+Alt+R (toggle mark)
    ↓
State machine: None → start → end → clear
    ↓
User navigates to end position
    ↓
NVDA+C (linear copy)
    ↓
Calculate positions for both bookmarks
    ↓
Extract text → strip ANSI → apply Unicode column extraction
    ↓
Copy to clipboard → announce result
```

### Profile Activation

```
event_gainFocus → _onTerminalFocus
    ↓
_detectAndApplyProfile(obj)
    ↓
Check appModule.appName → fallback to window title patterns
    ↓
Match found → set _currentProfile
    ↓
_announceProfileIfNew → speak profile name on terminal switch
```

## Testing Strategy

### Test Suite

The suite is pure Python. Nothing is skipped for missing binaries because there are no native binaries.

**Python tests** (`tests/`, ~80 test files):
- pytest with `unittest.TestCase`
- `conftest.py` mocks all NVDA internals (config, api, speech, ui, wx, etc.)
- Covers validation, caching, config, selection, navigation, search, profiles, text processing, integration, performance

### CI/CD

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `tests.yml` | Push/PR | Run the Python test suite on Windows (Python 3.11 and 3.13) |
| `release.yml` | Push to `main` | Build the addon with SCons, create GitHub release |
| `changelog-check.yml` | PR | Verify changelog entry exists |

## CI/CD Pipeline

The release workflow builds the `.nvda-addon` zip with SCons and publishes it as a GitHub release. There are no native build steps or per-architecture artifacts; the same pure Python package runs on x86, x64, and ARM64.

## References

- [NVDA Developer Guide](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html)
- [NVDA Add-on Development Guide](https://github.com/nvda-es/devguides_translation)
- [TextInfo API Documentation](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html#textInfos)
- [ANSI Escape Codes](https://en.wikipedia.org/wiki/ANSI_escape_code)
- [wcwidth Library](https://pypi.org/project/wcwidth/)
- [Windows UI Automation](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)

---

**Last Review**: 2026-07-12
**Next Review**: After major architectural changes
