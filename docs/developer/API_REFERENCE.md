# Terminal Access for NVDA - API Reference

**Version:** 1.4.0
**Last Updated:** 2026-03-22

## Table of Contents

1. [Public Classes](#public-classes)
2. [New in This Release](#new-in-this-release)
3. [Removed](#removed)
4. [Deprecated for v2](#deprecated-for-v2)
5. [Configuration API](#configuration-api)
6. [Runtime Registry](#runtime-registry)
7. [Extension API](#extension-api)
8. [Event Hooks](#event-hooks)
9. [Constants](#constants)

## Public Classes

### PositionCache (`lib/caching.py`)

Caches terminal row/column calculations with timestamp-based invalidation. Stores `bookmark -> (row, col, timestamp)` mappings to skip repeated O(n) position calculations.

#### Methods

##### `get(bookmark) -> tuple[int, int] | None`

Return cached position for a bookmark, or `None` if the entry is missing or expired.

##### `set(bookmark, row, col) -> None`

Store a position in the cache.

##### `clear() -> None`

Remove all cached entries. Called on terminal switch.

##### `invalidate(bookmark) -> None`

Remove a specific cached entry.

#### Constants

- `CACHE_TIMEOUT_MS` (int): Entry lifetime in milliseconds (default: 1000)
- `MAX_CACHE_SIZE` (int): Maximum cached entries (default: 100)

---

### TextDiffer (`lib/caching.py`)

Detects line-level changes between consecutive terminal snapshots. Strips trailing whitespace and ANSI codes before comparing.

#### Methods

##### `update(new_text: str) -> str | None`

Compare `new_text` against the previously stored snapshot. Returns the changed text, or `None` if nothing changed.

##### `reset() -> None`

Clear stored state.

---

### ANSIParser (`lib/text_processing.py`)

Parses ANSI escape sequences to detect colors and formatting attributes.

Handles standard 8 colors (30-37, 40-47), bright colors (90-97, 100-107), 256-color palette (`ESC[38;5;N`), RGB/TrueColor (`ESC[38;2;R;G;B`), and format attributes (bold, dim, italic, underline, blink, inverse, hidden, strikethrough).

#### Methods

##### `parse(text: str) -> dict`

Parse ANSI codes and return a dict with keys: `foreground`, `background`, `bold`, `dim`, `italic`, `underline`, `blink`, `inverse`, `hidden`, `strikethrough`.

##### `formatAttributes(mode='detailed') -> str`

Format current attributes as a human-readable string. `mode` is `'brief'` or `'detailed'`.

##### `reset() -> None`

Clear all attributes to defaults.

##### `stripANSI(text: str) -> str` (static)

Remove all ANSI escape sequences from text.

---

### UnicodeWidthHelper (`lib/text_processing.py`)

Calculates display width for Unicode text. Handles CJK characters (width 2) and combining characters (width 0). Each method tries Rust FFI first, then falls back to Python `wcwidth`.

#### Methods (all static)

##### `getCharWidth(char: str) -> int`

Returns 0 (combining/control), 1 (standard), or 2 (CJK).

##### `getTextWidth(text: str) -> int`

Total display width of a string in columns.

##### `extractColumnRange(text: str, startCol: int, endCol: int) -> str`

Extract text within a column range (1-based, inclusive).

##### `findColumnPosition(text: str, targetCol: int) -> int`

Map a 1-based column position to a 0-based string index.

---

### ErrorLineDetector (`lib/text_processing.py`)

Classifies terminal output lines as errors, warnings, or neither. The main plugin plays audio cues based on the classification.

#### Methods

##### `classify(line_text: str) -> str | None` (static)

Returns `'error'`, `'warning'`, or `None`. Uses regex patterns with word boundaries (`\b`) to avoid false positives on substrings.

18 error patterns:

| Pattern | Pattern | Pattern |
|---------|---------|---------|
| `error` | `err:` | `fatal` |
| `failed` | `failure` | `exception` |
| `traceback` | `panic` | `segfault` |
| `permission denied` | `not found` | `no such file` |
| `cannot` | `unable to` | `refused` |
| `abort` | `critical` | `unhandled` |

5 warning patterns:

| Pattern | Pattern | Pattern |
|---------|---------|---------|
| `warning` | `warn:` | `deprecated` |
| `caution` | `notice` | |

---

### WindowDefinition (`lib/profiles.py`)

Defines a rectangular screen region for window tracking.

#### Constructor

```python
WindowDefinition(name, top, bottom, left, right, mode='announce', enabled=True)
```

- `mode`: `'announce'` (speak changes), `'silent'` (suppress), or `'monitor'` (background polling)
- All coordinates are 1-based.

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `contains(row, col)` | `bool` | Check if a position falls inside this window |
| `toDict()` | `dict` | Serialize to dictionary |
| `fromDict(data)` (classmethod) | `WindowDefinition` | Deserialize from dictionary |

---

### ApplicationProfile (`lib/profiles.py`)

Holds per-application settings overrides and window definitions. A `None` value for any setting means "use the global setting."

#### Constructor

```python
ApplicationProfile(appName, displayName=None)
```

#### Properties (overrides)

All properties accept `int | bool | str | None`. A `None` value means "use the global setting."

| Property | Type |
|----------|------|
| `punctuationLevel` | `int` or `None` |
| `cursorTrackingMode` | `int` or `None` |
| `keyEcho` | `bool` or `None` |
| `linePause` | `bool` or `None` |
| `repeatedSymbols` | `bool` or `None` |
| `repeatedSymbolsValues` | `str` or `None` |
| `cursorDelay` | `int` or `None` |
| `quietMode` | `bool` or `None` |

#### Collections

- `windows` (list): `WindowDefinition` objects
- `customGestures` (dict): custom gesture mappings

#### Methods

- `addWindow(name, top, bottom, left, right, mode='announce') -> WindowDefinition`
- `getWindowAtPosition(row, col) -> WindowDefinition | None`
- `toDict() -> dict`
- `fromDict(data) -> ApplicationProfile` (classmethod)

---

### ProfileManager (`lib/profiles.py`)

Detects applications and manages profiles. Ships with defaults for vim, tmux, htop, less, git, nano, irssi.

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `detectApplication(focusObject)` | `str` | Returns app name or `'default'` |
| `getProfile(appName)` | `ApplicationProfile` or `None` | Retrieve a profile by app name |
| `get_profile_names()` | `list[str]` | Sorted list of unique profile app names |
| `setActiveProfile(appName)` | `None` | Set the currently active profile |
| `addProfile(profile)` | `None` | Add or update a profile |
| `removeProfile(appName)` | `None` | Remove a profile (refuses built-in profiles) |
| `exportProfile(appName)` | `dict` or `None` | Export profile to dictionary |
| `importProfile(data)` | `ApplicationProfile` | Import profile from dictionary |

---

### TabManager (`lib/navigation.py`)

Detects and tracks terminal tabs. Isolates bookmarks, searches, and history per tab.

#### Methods

- `get_current_tab_id() -> str`
- `list_tabs() -> list`
- `update_terminal(obj) -> None`

---

### BookmarkManager (`lib/navigation.py`)

Manages numbered bookmarks at terminal positions. Each bookmark captures the line content at the time it was set, displayed as a label.

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `set_bookmark(number, textInfo)` | `None` | Store bookmark with line content label |
| `get_bookmark(number)` | `textInfo` or `None` | Retrieve a bookmark |
| `clear_bookmark(number)` | `None` | Remove a single bookmark |
| `clear_all()` | `None` | Remove all bookmarks |
| `list_bookmarks()` | `list` | Returns bookmarks with number and line content |
| `show_list_dialog(parent)` | `None` | Opens `BookmarkListDialog` |

---

### BookmarkListDialog (`lib/navigation.py`)

A `wx.Dialog` that shows all bookmarks in a two-column list (Number, Line Content). Supports jumping to a bookmark via Enter, deleting via the Delete key, and closing via Escape. Fully keyboard-navigable.

---

### OutputSearchManager (`lib/search.py`)

Searches terminal output with plain text or regex patterns. Uses three-tier acceleration: helper-side search, DLL search, then Python fallback.

#### Key Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `search(pattern, regex=False)` | `list` | Find all matches |
| `search_next()` | `textInfo` or `None` | Jump to next match |
| `search_previous()` | `textInfo` or `None` | Jump to previous match |
| `clear()` | `None` | Clear search state |
| `update_terminal(obj)` | `None` | Update terminal reference |

---

### UrlExtractorManager (`lib/search.py`)

Finds URLs in terminal output (HTTP/HTTPS/FTP, `www.` prefixed, `file://`, OSC 8 hyperlinks). Lets users cycle through and open them.

#### Key Methods

- `extract_urls() -> list`
- `next_url() -> str | None`
- `previous_url() -> str | None`
- `open_current() -> None`

---

### SelectionProgressDialog (`lib/operations.py`)

Thread-safe progress dialog for long-running selection operations. Uses `wx.CallAfter` to keep UI updates on the main thread.

#### Methods

- `update(value, message=None) -> None`
- `is_cancelled() -> bool`
- `close() -> None`

---

### OperationQueue (`lib/operations.py`)

Prevents overlapping background operations. Only one long-running operation runs at a time.

#### Methods

- `submit(operation, callback=None) -> bool`
- `is_busy() -> bool`
- `cancel() -> None`

---

### WindowManager (`lib/window_management.py`)

Tracks rectangular screen regions with different speech modes. Persists window state through `ConfigManager`.

---

### WindowMonitor (`lib/window_management.py`)

Polls multiple terminal windows for content changes in the background. Diffs text snapshots and announces new content.

---

### ConfigManager (`lib/config.py`)

Wraps `config.conf["terminalAccess"]` with typed get/set, validation, and legacy migration.

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get(key, default=None)` | `Any` | Read a config value |
| `set(key, value)` | `bool` | Validates before writing. Returns `False` on invalid input. |
| `validate_all()` | `None` | Re-validates all stored values |
| `reset_to_defaults()` | `None` | Reset all settings to defaults |

---

### TerminalAccessSettingsPanel (`lib/settings_panel.py`)

NVDA settings panel with three flat sections.

| Section | Controls |
|---------|----------|
| **Speech and Tracking** | Cursor tracking, key echo, quiet mode, punctuation level, tracking mode, cursor delay, line pause, verbose mode, indentation, repeated symbols, error audio cues, output activity tones, default profile, reset button |
| **NVDA Gesture Conflicts** | Checklist of all direct shortcuts. Unchecked gestures are disabled but remain accessible through the command layer. |
| **Application Profiles** | Dropdown with Active/Default indicators, New/Edit/Delete/Import/Export buttons |

---

## New in This Release

| Class / Module | Location | What it does |
|----------------|----------|-------------|
| `ErrorLineDetector` | `lib/text_processing.py` | Classifies lines as error/warning for audio cues |
| `BookmarkListDialog` | `lib/navigation.py` | Dialog showing bookmarks with line content labels |
| `TerminalAccessSettingsPanel` | `lib/settings_panel.py` | Extracted settings panel with three flat sections |
| `lib/_runtime.py` | `lib/_runtime.py` | Centralized dependency registry replacing scattered DI stubs |

## Removed

| Item | Was in | Notes |
|------|--------|-------|
| `NewOutputAnnouncer` | `lib/operations.py` | Fully removed. NVDA+Shift+N toggle and related settings (coalesce, max-lines, strip-ansi) are gone. |

## Deprecated for v2

These remain functional but will be removed in v2.0:

| Item | Location | Replacement |
|------|----------|-------------|
| `CommandHistoryManager` | `lib/search.py` | None planned. Contact PratikP1 on GitHub if you use this. |
| `CT_HIGHLIGHT` (mode 2) | `lib/config.py` | Use `CT_STANDARD` or `CT_WINDOW` instead. |
| Rectangular Selection | `terminalAccess.py` | Use linear selection (NVDA+C). |

---

## Configuration API

### Config Spec

Access settings through NVDA's config system:

```python
import config
tracking = config.conf["terminalAccess"]["cursorTracking"]
config.conf["terminalAccess"]["cursorDelay"] = 50
```

### Configuration Keys

| Key | Type | Default | Range | What it controls |
|-----|------|---------|-------|-----------------|
| `cursorTracking` | bool | True | |Cursor tracking on/off |
| `cursorTrackingMode` | int | 1 | 0-3 | Off / Standard / Highlight (deprecated) / Window |
| `keyEcho` | bool | True | |Announce typed characters |
| `linePause` | bool | True | |Pause at line endings |
| `punctuationLevel` | int | 2 | 0-3 | None / Some / Most / All |
| `repeatedSymbols` | bool | False | |Condense repeated symbols |
| `repeatedSymbolsValues` | str | `-_=!` | max 50 chars | Which symbols to condense |
| `cursorDelay` | int | 20 | 0-1000 | Tracking delay in ms |
| `quietMode` | bool | False | |Suppress announcements |
| `verboseMode` | bool | False | |Extra context in announcements |
| `indentationOnLineRead` | bool | False | |Announce indentation on line nav |
| `windowTop/Bottom/Left/Right` | int | 0 | 0-10000 | Window tracking region |
| `windowEnabled` | bool | False | |Window tracking on/off |
| `defaultProfile` | str | `""` | |Fallback profile name |
| `errorAudioCues` | bool | True | | Master switch for error/warning tones during navigation |
| `errorAudioCuesInQuietMode` | bool | False | | Error/warning tones on caret events in quiet mode |
| `outputActivityTones` | bool | False | | Ascending two-tone on new program output |
| `outputActivityDebounce` | int | 1000 | 100-10000 | Milliseconds between activity tone repeats |
| `unboundGestures` | str | `""` | | Comma-separated disabled gestures |

### Validation Helpers

- `_validateInteger(value, minValue, maxValue, default, fieldName) -> int`
- `_validateString(value, maxLength, default, fieldName) -> str`
- `_validateSelectionSize(startRow, endRow, startCol, endCol) -> tuple[bool, str | None]`

---

## Runtime Registry

`lib/_runtime.py` holds function references that library modules need but cannot import directly. The main plugin populates these at startup.

```python
import lib._runtime as _rt

# Available slots:
_rt.strip_ansi          # text -> text (default: identity)
_rt.make_text_differ    # TextDiffer class
_rt.native_available    # bool (default: False)
_rt.native_search_text  # Rust search function or None
_rt.get_helper          # returns helper process or None
_rt.read_terminal_text  # terminal buffer reader or None
_rt.make_position_cache # PositionCache factory or None
```

---

## Extension API

### Adding Navigation Commands

```python
@script(
    description=_("My custom command"),
    gesture="kb:NVDA+alt+newkey"
)
def script_myCustomCommand(self, gesture):
    if not self.isTerminalApp():
        gesture.send()
        return
    reviewPos = self._getReviewPosition()
    # ... navigate and announce
```

### Custom Profiles

```python
profile = ApplicationProfile('myapp', 'My Application')
profile.punctuationLevel = 2
profile.cursorTrackingMode = 1
profile.addWindow('header', 1, 5, 1, 80, mode='announce')
profile.addWindow('footer', 20, 24, 1, 80, mode='silent')
self._profileManager.addProfile(profile)
```

---

## Event Hooks

### event_gainFocus(obj, nextHandler)

Fires when a terminal gains focus. Detects the terminal app, activates a profile, binds the review cursor, and clears the position cache.

### event_typedCharacter(obj, nextHandler, ch)

Fires on each typed character. Handles key echo, symbol processing, and repeated symbol detection.

### event_caret(obj, nextHandler)

Fires on caret movement. Starts a delay timer, then announces the cursor position based on the active tracking mode.

### _checkErrorAudioCue(obj)

Called from `event_caret`. When `errorAudioCuesInQuietMode` is enabled and quiet mode is active, reads the current line and calls `ErrorLineDetector.classify()`. Plays a tone if the line is an error or warning.

### _checkOutputActivityTone()

Called when new terminal output is detected. Plays two ascending tones (600 Hz + 800 Hz) to signal program activity. Controlled by the `outputActivityTones` config key. Repeated tones are suppressed for the duration set by `outputActivityDebounce`.

---

## Gesture Scoping

### getScript() Override

All gestures remain in `_gestureMap` so they appear in NVDA's Input Gestures dialog. The `getScript()` method returns `None` for Terminal Access gestures when the current focus is not a supported terminal. This lets NVDA fall through to its native command for the same key.

### _CONFLICTING_GESTURES

A `frozenset` of gesture identifiers that conflict with NVDA built-in commands (e.g., NVDA+C for copy vs. clipboard read). Only these gestures appear in the NVDA Gesture Conflicts checklist in the settings panel. Users can disable individual conflicting gestures without affecting other Terminal Access shortcuts.

---

## Constants

### Cursor Tracking Modes

```python
CT_OFF = 0        # No tracking
CT_STANDARD = 1   # Announce character at cursor
CT_HIGHLIGHT = 2  # Track highlights (DEPRECATED)
CT_WINDOW = 3     # Only announce within defined window
```

### Punctuation Levels

```python
PUNCT_NONE = 0    # No punctuation
PUNCT_SOME = 1    # Basic (.,?!;:)
PUNCT_MOST = 2    # Most symbols
PUNCT_ALL = 3     # All symbols
```

### Resource Limits

```python
MAX_SELECTION_ROWS = 10000
MAX_SELECTION_COLS = 1000
MAX_WINDOW_DIMENSION = 10000
MAX_REPEATED_SYMBOLS_LENGTH = 50
```

---

## References

- [NVDA Developer Guide](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html)
- [TextInfo API](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html#textInfos)
- [NVDA Config System](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html#config)

---

**Last Updated**: 2026-03-22
