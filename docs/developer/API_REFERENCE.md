# Terminal Access for NVDA - API Reference

**Version:** 2.0.0-beta.15
**Last Updated:** 2026-07-12

## Table of Contents

1. [Public Classes](#public-classes)
2. [New in This Release](#new-in-this-release)
3. [Removed](#removed)
4. [Configuration API](#configuration-api)
5. [Runtime Registry](#runtime-registry)
6. [Extension API](#extension-api)
7. [Event Hooks](#event-hooks)
8. [Constants](#constants)

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

Calculates display width for Unicode text. Handles CJK characters (width 2) and combining characters (width 0). Pure Python: each method uses the `wcwidth` library when it is importable. When it is not (NVDA's bundled Python does not ship it), a standard library fallback (`_stdlib_char_width`, based on `unicodedata`) keeps CJK, combining, and control character widths correct.

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

Manages named bookmarks at terminal positions (typically the names "0" through "9"). Each bookmark stores the position, its line number for lazy jump resolution, and an auto-generated label taken from the line content, the nearby command prompt, or the AI turn.

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `set_bookmark(name)` | `bool` | Store a bookmark at the review position with an auto-generated label |
| `jump_to_bookmark(name)` | `bool` | Move the review cursor to the bookmark; falls back to line-number navigation when the stored position cannot be recreated |
| `remove_bookmark(name)` | `bool` | Remove a single bookmark |
| `list_bookmarks()` | `list` | Bookmarks with name, label, and line number |
| `has_bookmark(name)` | `bool` | Whether a bookmark exists |
| `get_bookmark_label(name)` | `str` or `None` | The bookmark's label |
| `rename_bookmark(name, new_label)` | `bool` | Override the auto-generated label |
| `list_sections(buffer_lines, category=None)` | `list` | Detected sections, optionally filtered by category |

---

### BookmarkListDialog (`lib/navigation.py`)

A factory function that builds the bookmark list on top of `BrowsableListDialog` (`lib/list_dialogs.py`). Shows Number and Line Content rows read live from the bookmark manager. Enter or the Activate button jumps to the selected bookmark, the Delete key removes it, Escape closes. Returns a dialog ready for `ShowModal()`. Fully keyboard-navigable.

---

### OutputSearchManager (`lib/search.py`)

Searches terminal output with plain text or regex patterns. Runs entirely in Python: the buffer is read in-process with `makeTextInfo` (`_acquire_raw_text`), ANSI codes are stripped, and matching runs in a Python loop. Buffer lines are cached and invalidated by a content generation counter bumped on text changes.

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

### AITurnTokenizer (`lib/ai_turn_tokenizer.py`)

Detects AI CLI conversation turns (user, assistant, tool, system) in terminal buffer lines and provides navigation between turns and code blocks. Handles ANSI color codes in role markers and streamed or partial output.

#### Constructor

```python
AITurnTokenizer()
```

#### Methods

##### `tokenize(lines: list[str]) -> list[AITurn]`

Classify buffer lines into turns. Results are cached and reused while the buffer is unchanged (same line count, first line, and last line). `AITurn` is a namedtuple with fields `line_num`, `end_line`, `role`, and `has_code_block`. Returns an empty list when no AI turn markers are found.

##### `next_turn(current_line: int, role: str | None = None) -> AITurn | None`

Return the next turn after `current_line`. When `role` is given, only turns with that role match.

##### `prev_turn(current_line: int, role: str | None = None) -> AITurn | None`

Return the previous turn before `current_line`, optionally filtered by role.

##### `get_code_blocks() -> list[CodeSpan]`

All code blocks found by the last `tokenize()` call. `CodeSpan` is a namedtuple with fields `line_num` and `end_line`.

##### `next_code_block(current_line: int) -> CodeSpan | None`

##### `prev_code_block(current_line: int) -> CodeSpan | None`

#### Module Function

##### `classify_ai_line(clean_line: str) -> tuple[str, str] | None`

Classify a single ANSI-stripped, whitespace-trimmed line. Returns a `(role, preview)` tuple where role is `'user'`, `'assistant'`, `'tool'`, `'system'`, or `'code'`, or `None` when the line is not a turn marker. Shared with `BookmarkManager` for AI-aware bookmark labels.

#### Recognized Markers

| Role | Markers |
|------|---------|
| user | `❯` prompt arrow, `You:`, `User:`, `> ` followed by text |
| assistant | `Claude:`, `ChatGPT:`, `Assistant:`, `Copilot:`, `Gemini:`, `Codex:` |
| tool | `Tool:`, `Function:` |
| system | `Aider v...` banner, `Model:`, `System:` |
| code | triple backtick fences |

---

### CodeBlockDetector and CodeBlock (`lib/code_block_reader.py`)

Detects fenced code blocks (triple backtick delimiters) in terminal buffer lines and provides navigation, copy, and offline explanation helpers. ANSI codes are stripped before fence matching.

#### CodeBlockDetector Methods

##### `detect(buffer: list[str]) -> list[CodeBlock]`

Scan buffer lines and return a list of `CodeBlock` objects. Handles multiple adjacent blocks. An opening fence without a closing fence is skipped.

##### `find_block_at(line_idx: int, blocks: list[CodeBlock]) -> CodeBlock | None` (static)

Return the block containing `line_idx`, or `None`.

#### CodeBlock

Represents one detected block. Attributes: `language` (fence tag or `None`), `start_line` and `end_line` (0-based indexes of the fence lines).

| Member | Returns | Description |
|--------|---------|-------------|
| `line_count` (property) | `int` | Content lines between the fences |
| `first_content_line` (property) | `int` | Index of the line after the opening fence |
| `last_content_line` (property) | `int` | Index of the line before the closing fence |
| `announce()` | `str` | Spoken summary, e.g. "Python block, 8 lines" |
| `get_line(line_idx, buffer)` | `str` | ANSI-stripped line inside the block, empty string if out of range |
| `next_line(current)` / `prev_line(current)` | `int` or `None` | Adjacent content line index, `None` at the block boundary |
| `copy_text(buffer)` | `(str, bool)` | Content text and a truncated flag (capped at 5000 characters) |
| `explain(buffer)` | `str` | One-sentence offline heuristic explanation (imports, function defs, classes, loops, conditionals, error handling). Callers should check `PrivacyGuard` first. |

---

### StreamingDeltaTracker (`lib/streaming_delta.py`)

Tracks changes between terminal buffer snapshots. Stores the last snapshot, computes a structured `Delta` (a namedtuple with `kind`, `count`, `after_line`, `lines`, `added`, `changed_count`, `new_content`), debounces rapid changes, and formats verbosity-aware output.

#### Constructor

```python
StreamingDeltaTracker(debounce_ms=500, verbosity=1)
```

- `debounce_ms`: Minimum interval between reported deltas in milliseconds. Changes inside the interval return `None`.
- `verbosity`: 0 (quiet, no delta speech), 1 (count only, "3 new lines"), 2 (count plus last new line content).

#### Methods

##### `has_previous` (property)

`True` once at least one snapshot has been taken.

##### `set_verbosity(level) -> None`

Update the verbosity level (0, 1, or 2).

##### `take_snapshot(current_lines: list[str]) -> str | None`

Store a new snapshot and return a human-readable delta string. Returns `None` on the first snapshot, when nothing changed, when the debounce interval has not elapsed, or when verbosity is 0.

##### `get_braille_delta() -> str | None`

Short braille form of the last delta: `+N` for new lines, `~LN` for a single changed line, `~N` for several changed lines, `-N` for removed lines. `None` if there was no change.

---

### PrivacyGuard (`lib/privacy.py`)

Central gatekeeper for privacy-sensitive opt-in processing. Summarization, code explanation, and AI turn parsing run locally and do not upload terminal content; the guard gates these features behind config flags. Explicitly opening a detected URL is separate and launches the default browser.

#### Constructor

```python
PrivacyGuard()
```

Stateless; config is passed to each check.

#### Methods

##### `check_feature(feature_name: str, config_manager) -> tuple[bool, str]`

Return `(allowed, message)`. Known feature names and their config keys: `'summarize'` (`summarizationEnabled`), `'explain_code'` (`codeBlockExplain`), `'ai_turn_parse'` (`aiTurnParseEnabled`). Unknown or empty names are blocked. When blocked, the message explains how to enable the feature, unless `privacyAnnounce` is `False`, in which case it is empty.

##### `is_offline_only() -> bool` (static)

Always returns `True`. This is a static assertion that the guarded terminal-analysis features are offline, not a runtime network monitor. It does not cover the separate, user-triggered action that opens a detected URL in the default browser.

##### `format_privacy_status(config_manager) -> str`

Human-readable privacy status, e.g. "Privacy: all features offline. Summarization: on. Code explain: off." Here, "features" refers to the guarded terminal-analysis features described above.

---

## New in This Release

| Class / Module | Location | What it does |
|----------------|----------|-------------|
| `ErrorLineDetector` | `lib/text_processing.py` | Classifies lines as error/warning for audio cues |
| `BookmarkListDialog` | `lib/navigation.py` | Dialog showing bookmarks with line content labels |
| `TerminalAccessSettingsPanel` | `lib/settings_panel.py` | Extracted settings panel with three flat sections |
| `lib/_runtime.py` | `lib/_runtime.py` | Centralized dependency registry replacing scattered DI stubs |
| `AITurnTokenizer` | `lib/ai_turn_tokenizer.py` | Detects AI conversation turns and navigates between them |
| `CodeBlockDetector` | `lib/code_block_reader.py` | Detects fenced code blocks with language tags |
| `StreamingDeltaTracker` | `lib/streaming_delta.py` | Tracks new content during AI streaming responses |
| `PrivacyGuard` | `lib/privacy.py` | Gates privacy-sensitive opt-in features behind settings |

## Removed

| Item | Was in | Notes |
|------|--------|-------|
| `NewOutputAnnouncer` | `lib/operations.py` | Fully removed. NVDA+Shift+N toggle and related settings (coalesce, max-lines, strip-ansi) are gone. |
| `CommandHistoryManager` | `lib/search.py` | Removed in v2.0.0. Shells have built-in history navigation. |
| `CT_HIGHLIGHT` (mode 2) | `lib/config.py` | Removed in v2.0.0. Modern terminals strip ANSI from UIA text. `CT_WINDOW` is now mode 2. |
| Rectangular Selection | `terminalAccess.py` | Removed in v2.0.0. Use linear selection (NVDA+C). |

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
| `cursorTrackingMode` | int | 1 | 0-2 | Off / Standard / Window |
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
| `announceIndentation` | bool | False | | Announce indentation when reading lines |
| `verbosityLevel` | int | 1 | 0-2 | Quiet / Normal / Verbose |
| `urlOpenWarning` | bool | True | | Confirmation before opening URLs from output |
| `summarizationEnabled` | bool | False | | Offline summarization (opt-in, privacy gated) |
| `codeBlockExplain` | bool | False | | Offline code block explanation (opt-in, privacy gated) |
| `aiTurnParseEnabled` | bool | False | | AI turn detection and navigation (opt-in) |
| `privacyAnnounce` | bool | True | | Spoken message when a gated feature is blocked |
| `streamingSuppression` | bool | True | | Suppress character speech during rapid output |
| `tutorialShown` | bool | False | | First-run tutorial already played |
| `progressMilestones` | bool | True | | Announce progress percentages at milestones |
| `earconVolume` | int | 100 | 10-100 | Earcon volume percent |
| `earconPitchShift` | int | 100 | 50-200 | Earcon pitch shift percent |
| `processSymbols` | bool | False | | Deprecated; kept for pre-v1.0.10 config migration |

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
_rt.read_terminal_text  # terminal buffer reader or None
_rt.make_position_cache # PositionCache factory or None
_rt.api_module          # NVDA api module (set at startup, None in tests)
_rt.webbrowser_module   # Python webbrowser module (set at startup, None in tests)
```

The module also defines `gesture_label(gesture, script_name)`, a shared helper that formats a gesture and script name into a human-readable label.

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

Fires when a terminal gains focus. Detects the terminal app, activates a profile, binds the review cursor, and clears the position cache. This is the only terminal event still handled at the GlobalPlugin level.

### Terminal Event Delegation (overlay)

Terminal `event_caret`, `event_textChange`, and `event_typedCharacter` are handled by the `TerminalAccessTerminal` overlay (`lib/terminal_overlay.py`), inserted via `chooseNVDAObjectOverlayClasses` for supported terminals. There are no global plugin handlers for these events. The overlay finds the running plugin through a module-level registration (`terminal_overlay.set_active_plugin`, called in `GlobalPlugin.__init__` and cleared in `terminate()`) and delegates:

| Overlay event | Plugin delegate | Behavior |
|---------------|-----------------|----------|
| `event_caret` | `_handleTerminalCaret(obj)` | Debounced cursor tracking, blank suppression, error cues. NVDA's native caret speech is suppressed. |
| `event_textChange` | `_handleTerminalTextChange(obj)` | Activity tones, progress milestones, quiet-mode error cues. Returns whether to wake the LiveText monitor thread that speaks new output. |
| `event_typedCharacter` | `_terminalTypedCharacter(obj, ch, speak_default)` | Key echo decisions and quiet-mode suppression. `speak_default` runs NVDA's own character echo. |

### _checkErrorAudioCue()

Called from `_handleTerminalCaret` and `_handleTerminalTextChange`. When `errorAudioCuesInQuietMode` is enabled and quiet mode is active, reads the current line and calls `ErrorLineDetector.classify()`. Plays a tone if the line is an error or warning.

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
CT_WINDOW = 2     # Only announce within defined window
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

**Last Updated**: 2026-07-12
