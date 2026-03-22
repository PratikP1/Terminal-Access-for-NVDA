# Terminal Access for NVDA - Architecture Overview

**Version:** 1.4.0
**Last Updated:** 2026-03-22

## Table of Contents

1. [System Overview](#system-overview)
2. [Module Structure](#module-structure)
3. [Dependency Flow](#dependency-flow)
4. [Event Handling Pipeline](#event-handling-pipeline)
5. [Settings Architecture](#settings-architecture)
6. [Native Acceleration Layer](#native-acceleration-layer)
7. [Data Flow](#data-flow)
8. [Testing Strategy](#testing-strategy)
9. [CI/CD Pipeline](#cicd-pipeline)

## System Overview

Terminal Access for NVDA is an NVDA global plugin that makes Windows terminals more accessible. It extends NVDA's review cursor with terminal-specific navigation, selection, search, and reading features.

### Design Principles

- **Non-intrusive**: Works alongside NVDA's built-in terminal support
- **Fast**: Caches expensive operations, offloads work to background threads and a Rust helper process
- **Extensible**: Application profiles customize behavior per terminal app
- **Accessible-first**: Every feature is designed for screen reader users

### Technology Stack

- **Language**: Python 3.11+ (addon), Rust (native acceleration)
- **Framework**: NVDA Global Plugin API
- **UI**: wxPython (via NVDA's GUI helpers)
- **Native**: Rust workspace with 3 crates (core, FFI, helper)
- **IPC**: Named pipe with length-prefixed JSON (helper process)
- **Dependencies**: wcwidth (Python fallback for Unicode), unicode-width (Rust)

## Module Structure

The codebase is split across a main plugin file and extracted library modules.

| Module | Lines | What it does |
|--------|------:|-------------|
| `globalPlugins/terminalAccess.py` | ~3774 | GlobalPlugin class, command layer, event handlers, all script definitions |
| `lib/_runtime.py` | ~25 | Runtime dependency registry. Holds references to native functions and helpers that lib modules need but cannot import directly (avoids circular imports). Populated by `terminalAccess.py` at startup. |
| `lib/config.py` | ~341 | Config constants (`CT_OFF`, `CT_STANDARD`, etc.), `confspec` dict, validation functions (`_validateInteger`, `_validateString`, `_validateSelectionSize`), `ConfigManager` class |
| `lib/caching.py` | ~233 | `PositionCache` (bookmark-keyed LRU with TTL), `TextDiffer` (line-level change detection) |
| `lib/navigation.py` | ~541 | `TabManager` (per-tab state isolation), `BookmarkManager` (named bookmarks with line content labels), `BookmarkListDialog` (list view with Number + Line Content columns) |
| `lib/operations.py` | ~203 | `SelectionProgressDialog` (thread-safe progress with cancellation), `OperationQueue` |
| `lib/profiles.py` | ~549 | `ApplicationProfile`, `WindowDefinition`, `ProfileManager` (detection + defaults for vim, tmux, htop, less, git, nano, irssi) |
| `lib/search.py` | ~1149 | `OutputSearchManager` (incremental text search with native acceleration), `CommandHistoryManager` (DEPRECATED for v2), `UrlExtractorManager` (URL detection and opening) |
| `lib/text_processing.py` | ~879 | `ANSIParser` (color/formatting detection), `UnicodeWidthHelper` (CJK display width), `PositionCalculator` (row/col from TextInfo), `ErrorLineDetector` (18 error + 5 warning regex patterns with word boundaries, `classify()` method) |
| `lib/window_management.py` | ~805 | `WindowMonitor` (background text polling), `WindowManager` (rectangular screen region tracking), `PositionCalculator` |
| `lib/settings_panel.py` | ~820 | `TerminalAccessSettingsPanel` with three flat sections: Speech and Tracking, NVDA Gesture Conflicts, Application Profiles |
| `native/termaccess_bridge.py` | | ctypes FFI wrapper for `termaccess.dll` |
| `native/helper_process.py` | | Named pipe IPC client for `termaccess-helper.exe` |

### Removed

| Item | Notes |
|------|-------|
| **NewOutputAnnouncer** | Removed entirely. NVDA+Shift+N toggle, coalesce/max-lines/strip-ansi settings are gone. |

### Deprecated for v2

| Item | Description |
|------|-------------|
| **CommandHistoryManager** | Command history navigation (NVDA+H/G, NVDA+Shift+H, NVDA+Shift+L) |
| **CT_HIGHLIGHT** | Highlight cursor tracking mode |
| **Rectangular Selection** | NVDA+Shift+C |

## Dependency Flow

`_runtime.py` acts as the hub between the main plugin and library modules. Library modules import `_runtime` to access native functions without importing `terminalAccess.py` directly.

```
terminalAccess.py (main plugin)
    │
    │  populates at startup
    ▼
lib/_runtime.py  ◄──────────── lib modules read from here
    │
    │  holds references to:
    ├── strip_ansi          (native or Python fallback)
    ├── make_text_differ    (TextDiffer factory)
    ├── native_available    (bool)
    ├── native_search_text  (Rust search function)
    ├── get_helper          (helper process accessor)
    ├── read_terminal_text  (terminal buffer reader)
    └── make_position_cache (PositionCache factory)

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
        ├── lib/settings_panel.py   (lazy-imports terminalAccess)
        ├── native/termaccess_bridge.py
        └── native/helper_process.py
```

## Event Handling Pipeline

### event_gainFocus breakdown

`event_gainFocus` was refactored from a monolithic method into 8 focused helpers called by `_onTerminalFocus`:

| Method | Purpose |
|--------|---------|
| `event_gainFocus` | Entry point. Calls `nextHandler()`, then checks terminal status. |
| `_updateGestureBindingsForFocus(obj)` | Returns False if not a terminal. |
| `_onTerminalFocus(obj)` | Orchestrates the 7 helpers below. |
| `_startHelperIfNeeded()` | Lazy-starts the native helper process. |
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
event_caret(obj)
    ↓
Start timer (configurable delay, 0-1000 ms)
    ↓
Timer expires → _announceCursorPosition(obj)
    ↓
Check tracking mode:
    CT_STANDARD → _announceStandardCursor()
    CT_HIGHLIGHT → _announceHighlightCursor()  (deprecated)
    CT_WINDOW → _announceWindowCursor()
```

### Audio Feedback

`_checkErrorAudioCue(obj)`: called from `event_caret` in quiet mode. Reads the current line, calls `ErrorLineDetector.classify()`, and plays a tone for error or warning lines. Controlled by `errorAudioCuesInQuietMode`.

`_checkOutputActivityTone()`: plays two ascending tones (600 + 800 Hz) when new program output appears. Controlled by `outputActivityTones`. Repeated tones suppressed for the duration set by `outputActivityDebounce`.

## Settings Architecture

Settings were extracted from the main plugin into two modules:

### lib/config.py

- Defines `confspec` dict registered at `config.conf.spec["terminalAccess"]`
- Constants: `CT_OFF`, `CT_STANDARD`, `CT_HIGHLIGHT`, `CT_WINDOW`, `PUNCT_*`, resource limits
- Validation: `_validateInteger()`, `_validateString()`, `_validateSelectionSize()`
- `ConfigManager` class wraps `config.conf["terminalAccess"]` with typed get/set, migration, and bulk validation

### lib/settings_panel.py

- `TerminalAccessSettingsPanel` extends NVDA's `SettingsPanel`
- Three flat sections (no collapsible panes):
  - **Speech and Tracking**: cursor tracking, key echo, quiet mode, punctuation level, tracking mode, cursor delay, line pause, verbose mode, indentation, repeated symbols, error audio cues, output activity tones, default profile, reset button
  - **NVDA Gesture Conflicts**: checklist of conflicting gestures from `_CONFLICTING_GESTURES`. Unchecked gestures are disabled but remain accessible through the command layer.
  - **Application Profiles**: dropdown with Active/Default indicators, New/Edit/Delete/Import/Export buttons
- Lazy-imports from `terminalAccess.py` to avoid circular dependencies

## Native Acceleration Layer

The addon ships an optional Rust-based native layer. Every native feature has a Python fallback. The addon works without any native binaries.

### Crate Layout

```
┌─────────────────────────────────────────────────────────┐
│                    Python Addon                         │
│                                                         │
│  termaccess_bridge.py    helper_process.py              │
│  (ctypes FFI wrapper)    (named pipe IPC client)        │
│         │                         │                     │
└─────────┼─────────────────────────┼─────────────────────┘
          │ cdylib (DLL)            │ named pipe (JSON)
          ▼                         ▼
┌──────────────────┐   ┌────────────────────────────────┐
│ termaccess-ffi   │   │ termaccess-helper              │
│ (termaccess.dll) │   │ (termaccess-helper.exe)        │
│                  │   │                                │
│ C ABI exports:   │   │ Runs in own process:           │
│ - Text diffing   │   │ - UIA terminal reads           │
│ - ANSI stripping │   │ - Console API fallback         │
│ - Text search    │   │ - Subscription polling         │
│ - Position cache │   │ - Diff + ANSI strip            │
│ - Unicode width  │   │ - Server-side search           │
└────────┬─────────┘   └────────────┬───────────────────┘
         │                          │
         ▼                          ▼
┌──────────────────────────────────────────────────────┐
│                   termaccess-core                     │
│ Pure Rust algorithms (no platform dependencies):      │
│ - text_differ   (line-level diff)                    │
│ - ansi_strip    (regex-based ANSI removal)           │
│ - search        (plain + regex text search)          │
│ - position_cache (LRU + TTL cache)                   │
│ - unicode_width (CJK/combining char column widths)   │
└──────────────────────────────────────────────────────┘
```

| Crate | Type | What it does |
|-------|------|-------------|
| `termaccess-core` | lib | Pure algorithms, no platform deps |
| `termaccess-ffi` | cdylib | C ABI exports for Python ctypes |
| `termaccess-helper` | binary | Out-of-process UIA reader and search server |

### FFI Interface

Communication: Python ctypes loads `termaccess.dll`.
Memory: Rust allocates output buffers; Python frees via `ta_free_string`.
Strings: UTF-8 as `*const u8 + usize` pairs.
Error codes: `0=OK, 1=NullPointer, 2=InvalidUTF8, 3=NotFound, 4=InvalidRegex`.

Exported functions:

| Function | Purpose |
|----------|---------|
| `ta_version` / `ta_version_len` | Version info |
| `ta_free_string` | Memory management |
| `ta_text_differ_new/free/update/reset/last_text` | Text diffing |
| `ta_strip_ansi` | ANSI escape removal |
| `ta_search_text` / `ta_search_results_free` | Pattern matching |
| `ta_position_cache_new/free/get/set/clear/invalidate` | Position caching |
| `ta_char_width` | Single character display width |
| `ta_text_width` | String display width |
| `ta_extract_column_range` | Column-aware substring extraction |
| `ta_find_column_position` | Column to char index mapping |

### Helper IPC Protocol

Communication: Named pipe (`\\.\pipe\termaccess-{pid}-{uid}`).
Wire format: `[4-byte LE u32 length][UTF-8 JSON payload]`.

Request types: `ping`, `read_text`, `read_lines`, `subscribe`, `unsubscribe`, `search_text`, `shutdown`.

Response types: `pong`, `text_result`, `lines_result`, `subscribe_ok`, `unsubscribe_ok`, `search_result`, `error`.

Notifications (unsolicited): `helper_ready`, `text_changed`, `text_diff`.

### Text Reading Fallback Chain

The helper reads terminal text with a multi-tier fallback:

| Tier | Method | Notes |
|------|--------|-------|
| 1 | **UIA TextPattern** | Works with Windows Terminal and modern consoles |
| 2 | **Win32 Console API** | `AttachConsole` + `ReadConsoleOutputCharacterW`, for legacy conhost |
| 3 | **Python main-thread** | `makeTextInfo(POSITION_ALL)`, the original approach |

### Search Acceleration

Three tiers, each falling back to the next:

| Tier | Method | Notes |
|------|--------|-------|
| 1 | **Helper-side search** | Reads buffer and searches in one IPC round-trip |
| 2 | **DLL search** | `native_search_text()` runs Rust search on a Python-read buffer |
| 3 | **Python matching** | Character-by-character loop (original implementation) |

### File Layout

```
addon/
├── globalPlugins/
│   └── terminalAccess.py      # Main plugin (~3774 lines)
├── lib/
│   ├── __init__.py
│   ├── _runtime.py            # Runtime dependency registry
│   ├── config.py              # Config constants, confspec, validation
│   ├── caching.py             # PositionCache, TextDiffer
│   ├── navigation.py          # TabManager, BookmarkManager, BookmarkListDialog
│   ├── operations.py          # SelectionProgressDialog, OperationQueue
│   ├── profiles.py            # ApplicationProfile, WindowDefinition, ProfileManager
│   ├── search.py              # OutputSearchManager, CommandHistoryManager, UrlExtractorManager
│   ├── text_processing.py     # ANSIParser, UnicodeWidthHelper, PositionCalculator, ErrorLineDetector
│   ├── window_management.py   # WindowMonitor, WindowManager, PositionCalculator
│   ├── settings_panel.py      # TerminalAccessSettingsPanel (Basic/Advanced)
│   ├── x64/
│   │   ├── termaccess.dll
│   │   └── termaccess-helper.exe
│   └── x86/
│       ├── termaccess.dll
│       └── termaccess-helper.exe
├── native/
│   ├── __init__.py
│   ├── termaccess_bridge.py   # ctypes FFI wrapper
│   └── helper_process.py      # Named pipe IPC client
│
native/                         # Rust workspace (not shipped in addon)
├── Cargo.toml
├── crates/
│   ├── termaccess-core/        # Pure algorithms
│   ├── termaccess-ffi/         # C ABI FFI layer (cdylib)
│   └── termaccess-helper/      # Helper process (binary)
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

768 tests pass, 67 skipped (native bridge tests, skipped when DLL absent).

**Python tests** (`tests/`, ~41 test files):
- pytest with `unittest.TestCase`
- `conftest.py` mocks all NVDA internals (config, api, speech, ui, wx, etc.)
- Covers validation, caching, config, selection, navigation, search, profiles, text processing, integration, performance

**Rust tests** (`native/`):
- `termaccess-core`: 66 tests (diff, ANSI strip, search, cache, unicode width)
- `termaccess-helper`: 35 tests (protocol serde, pipe framing, security, subscriptions)
- Run with `cargo test --all` (101 tests total)

### CI/CD

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `rust-build.yml` | Push/PR touching `native/` | Run Rust tests, clippy, build DLL+EXE for x86/x64 |
| `release.yml` | Push to `main` | Build native, bundle addon, create GitHub release |
| `nightly.yml` | Daily cron + manual | Build native, bundle nightly addon with version suffix |
| `changelog-check.yml` | PR | Verify changelog entry exists |

## CI/CD Pipeline

The release and nightly workflows produce these artifacts:

| Artifact | Contents |
|----------|----------|
| `termaccess-dll-x64` / `termaccess-dll-x86` | `termaccess_ffi.dll` renamed to `termaccess.dll` |
| `termaccess-helper-x64` / `termaccess-helper-x86` | `termaccess-helper.exe` |

These are placed into `addon/lib/{arch}/` before the `.nvda-addon` zip is built.

## References

- [NVDA Developer Guide](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html)
- [NVDA Add-on Development Guide](https://github.com/nvda-es/devguides_translation)
- [TextInfo API Documentation](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html#textInfos)
- [ANSI Escape Codes](https://en.wikipedia.org/wiki/ANSI_escape_code)
- [wcwidth Library](https://pypi.org/project/wcwidth/)
- [unicode-width Crate](https://crates.io/crates/unicode-width)
- [Windows UI Automation](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)

---

**Last Review**: 2026-03-22
**Next Review**: After major architectural changes
