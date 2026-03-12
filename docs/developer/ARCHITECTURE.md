# TDSR for NVDA - Architecture Overview

**Version:** 1.3.0
**Last Updated:** 2026-03-12

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Architecture](#core-architecture)
3. [Native Acceleration Layer](#native-acceleration-layer)
4. [Key Components](#key-components)
5. [Data Flow](#data-flow)
6. [Extension Points](#extension-points)
7. [Performance Considerations](#performance-considerations)

## System Overview

TDSR for NVDA is implemented as an NVDA global plugin that enhances terminal accessibility for Windows. The add-on integrates with NVDA's review cursor system and extends it with terminal-specific navigation, selection, and reading features.

### Design Philosophy

- **Non-intrusive**: Works alongside NVDA's existing terminal support
- **Performance-conscious**: Caches expensive operations, uses background threading
- **Extensible**: Application profiles allow customization per terminal app
- **Accessible-first**: All features designed for screen reader users

### Technology Stack

- **Language**: Python 3.11+ (addon), Rust (native acceleration layer)
- **Framework**: NVDA Global Plugin API
- **UI**: wxPython (via NVDA's GUI helpers)
- **Native**: Rust workspace with 3 crates (core, FFI, helper)
- **IPC**: Named pipe with length-prefixed JSON (helper process)
- **Dependencies**: wcwidth (Python fallback for Unicode), unicode-width (Rust)

## Core Architecture

### Plugin Structure

```
GlobalPlugin (tdsr.py)
├── Core Classes
│   ├── PositionCache - Terminal position caching
│   ├── ANSIParser - Color/formatting detection
│   ├── UnicodeWidthHelper - CJK character width
│   ├── WindowDefinition - Screen region definition
│   ├── ApplicationProfile - App-specific settings
│   └── ProfileManager - Profile detection & management
│
├── Event Handlers
│   ├── event_gainFocus - Terminal detection & binding
│   ├── event_typedCharacter - Key echo
│   └── event_caret - Cursor tracking
│
├── Navigation Scripts
│   ├── Line navigation (U/I/O)
│   ├── Word navigation (J/K/L)
│   ├── Character navigation (M/Comma/Period)
│   └── Edge navigation (Home/End/PageUp/PageDown)
│
├── Selection & Copy
│   ├── Mark-based selection (R)
│   ├── Linear copy (C)
│   ├── Rectangular copy (Shift+C)
│   └── Legacy copy mode (V)
│
├── Reading Commands
│   ├── Continuous reading (A)
│   ├── Directional reading (Shift+Arrows)
│   ├── Position announcement (P)
│   └── Attribute reading (Shift+A)
│
├── Command Layer (NVDA+')
│   ├── _COMMAND_LAYER_MAP - Single-key gesture → script mapping
│   ├── _enterCommandLayer() - Binds layer gestures, plays 880 Hz tone
│   ├── _exitCommandLayer() - Unbinds layer gestures, plays 440 Hz tone
│   ├── Auto-exit on focus loss (_disableTerminalGestures)
│   └── Copy-mode interaction (_exitCopyModeBindings restores layer keys)
│
└── Configuration
    ├── TDSRSettingsPanel - GUI settings
    ├── Config validation helpers
    └── Profile serialization

```

### Component Interaction

```
User Input → Script Handler → GlobalPlugin
                 ↓
         Terminal Detection
                 ↓
         Profile Manager → Application Profile
                 ↓
    Review Cursor (NVDA) ← Position Cache (native or Python)
                 ↓
         Text Extraction
            ↓ (fast path)              ↓ (fallback)
    Helper Process (Rust)         Python main thread
    UIA → Console API fallback    makeTextInfo(POSITION_ALL)
                 ↓
    ANSI Parser / Unicode Helper (native or Python)
                 ↓
         Speech Output (NVDA)
```

## Native Acceleration Layer

The addon includes an optional Rust-based native acceleration layer that
offloads CPU-bound operations off NVDA's main thread. Every native feature
has a complete Python fallback — the addon works without any native binaries.

### Architecture

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

### Crate Layout

| Crate | Type | Purpose |
|-------|------|---------|
| `termaccess-core` | lib | Pure algorithms, no platform deps |
| `termaccess-ffi` | cdylib | C ABI exports for Python ctypes |
| `termaccess-helper` | binary | Out-of-process UIA reader and search server |

### FFI Interface (`termaccess-ffi` → `termaccess_bridge.py`)

Communication: Python ctypes loads `termaccess.dll` (cdylib).
Memory: Rust allocates output buffers; Python frees via `ta_free_string`.
Strings: UTF-8 as `*const u8 + usize` pairs.
Error codes: `0=OK, 1=NullPointer, 2=InvalidUTF8, 3=NotFound, 4=InvalidRegex`.

Exported functions:
- `ta_version` / `ta_version_len` — version info
- `ta_free_string` — memory management
- `ta_text_differ_new/free/update/reset/last_text` — text diffing
- `ta_strip_ansi` — ANSI escape removal
- `ta_search_text` / `ta_search_results_free` — pattern matching
- `ta_position_cache_new/free/get/set/clear/invalidate` — position caching
- `ta_char_width` — single character display width
- `ta_text_width` — string display width
- `ta_extract_column_range` — column-aware substring extraction
- `ta_find_column_position` — column to char index mapping

### Helper IPC Protocol (`termaccess-helper` → `helper_process.py`)

Communication: Named pipe (`\\.\pipe\termaccess-{pid}-{uid}`).
Wire format: `[4-byte LE u32 length][UTF-8 JSON payload]`.

Request types: `ping`, `read_text`, `read_lines`, `subscribe`,
`unsubscribe`, `search_text`, `shutdown`.

Response types: `pong`, `text_result`, `lines_result`, `subscribe_ok`,
`unsubscribe_ok`, `search_result`, `error`.

Notifications (unsolicited): `helper_ready`, `text_changed`, `text_diff`.

### Text Reading Fallback Chain

The helper uses a multi-tier fallback for reading terminal text:

1. **UIA TextPattern** — preferred, works with Windows Terminal and modern consoles
2. **Win32 Console API** — `AttachConsole` + `ReadConsoleOutputCharacterW`, for legacy conhost
3. **Python main-thread** — `makeTextInfo(POSITION_ALL)`, the original approach

### Search Acceleration

Three tiers of search, each falling back to the next:

1. **Helper-side search** — reads buffer AND searches in one IPC round-trip (no buffer transfer)
2. **DLL search** — `native_search_text()` runs Rust search on a Python-read buffer
3. **Python matching** — character-by-character loop (original implementation)

### File Layout

```
addon/
├── native/
│   ├── __init__.py
│   ├── termaccess_bridge.py    # ctypes FFI wrapper for termaccess.dll
│   └── helper_process.py       # Named pipe IPC client for helper.exe
├── lib/
│   ├── x64/
│   │   ├── termaccess.dll      # Rust cdylib (64-bit)
│   │   └── termaccess-helper.exe
│   └── x86/
│       ├── termaccess.dll      # Rust cdylib (32-bit)
│       └── termaccess-helper.exe
│
native/                          # Rust workspace (not shipped in addon)
├── Cargo.toml                   # Workspace manifest
├── crates/
│   ├── termaccess-core/         # Pure algorithms
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── ansi_strip.rs
│   │       ├── position_cache.rs
│   │       ├── search.rs
│   │       ├── text_differ.rs
│   │       └── unicode_width.rs
│   ├── termaccess-ffi/          # C ABI FFI layer (cdylib)
│   │   └── src/
│   │       ├── lib.rs
│   │       └── ffi_types.rs
│   └── termaccess-helper/       # Helper process (binary)
│       └── src/
│           ├── main.rs
│           ├── console_reader.rs
│           ├── pipe_server.rs
│           ├── protocol.rs
│           ├── security.rs
│           ├── uia_events.rs
│           └── uia_reader.rs
```

## Key Components

### 1. PositionCache

**Purpose**: Cache terminal row/column calculations to avoid expensive O(n) operations.

**Key Features**:
- Timeout-based invalidation (1 second default)
- Thread-safe with locking
- Maximum size limit (100 entries)
- Automatic cache clearing on terminal switch

**Location**: `addon/globalPlugins/tdsr.py:86-160`

```python
class PositionCache:
    def get(self, bookmark) -> tuple[int, int] | None
    def set(self, bookmark, row, col) -> None
    def clear() -> None
    def invalidate(self, bookmark) -> None
```

### 2. ANSIParser

**Purpose**: Parse ANSI escape sequences for color and formatting detection.

**Capabilities**:
- Standard 8 colors (30-37, 40-47)
- Bright colors (90-97, 100-107)
- 256-color palette (ESC[38;5;N)
- RGB/TrueColor (ESC[38;2;R;G;B)
- Format attributes (bold, dim, italic, underline, etc.)
- Reset codes and attribute clearing

**Location**: `addon/globalPlugins/tdsr.py:162-417`

```python
class ANSIParser:
    def parse(self, text) -> dict
    def formatAttributes(self, mode='detailed') -> str
    @staticmethod
    def stripANSI(text) -> str
```

### 3. UnicodeWidthHelper

**Purpose**: Calculate display width for Unicode text (CJK, combining characters).

**Key Methods**:
- `getCharWidth(char)` - Returns 0, 1, or 2 columns
- `getTextWidth(text)` - Total display width
- `extractColumnRange(text, startCol, endCol)` - Column-aware extraction
- `findColumnPosition(text, targetCol)` - Column to index mapping

**Location**: `addon/globalPlugins/tdsr.py`

**Native acceleration**: Each method tries the Rust `unicode-width` crate via
FFI (`ta_char_width`, `ta_text_width`, `ta_extract_column_range`,
`ta_find_column_position`) first, falling back to the Python `wcwidth`
library on failure.

### 4. Application Profiles

**Purpose**: Automatic detection and application-specific optimizations.

**Components**:
- `WindowDefinition` - Screen region with mode (announce/silent/monitor)
- `ApplicationProfile` - Settings overrides and window definitions
- `ProfileManager` - Detection logic and default profiles

**Location**: `addon/globalPlugins/tdsr.py:551-853`

**Default Profiles**: vim, tmux, htop, less, git, nano, irssi

**Detection Logic**:
1. Check app module name (e.g., `appModule.appName`)
2. Fallback to window title pattern matching
3. Return 'default' if no match

### 5. Position Calculation

**Algorithm**: Manual counting from buffer start using TextInfo.move()

**Complexity**: O(n) where n = row number

**Optimization**: Position cache reduces repeated calculations

**Location**: `addon/globalPlugins/tdsr.py` (in `_calculatePosition` method)

```python
def _calculatePosition(self, textInfo) -> tuple[int, int]:
    """
    Calculate (row, col) by counting from buffer start.

    Returns:
        (row, col): 1-based coordinates
        (0, 0): On error (safe fallback)
    """
```

### 6. Selection System

**Mark-Based Selection**:
- `_markStart` - Bookmark for selection start
- `_markEnd` - Bookmark for selection end
- State machine: None → start → end → clear

**Types**:
1. **Linear**: Continuous text from start to end
2. **Rectangular**: Column-based extraction across lines

**Unicode-Aware**: Uses `UnicodeWidthHelper` for CJK text

**Location**: Selection scripts in `addon/globalPlugins/tdsr.py:2108-2362`

### 7. Cursor Tracking

**Modes**:
- `CT_OFF (0)` - No tracking
- `CT_STANDARD (1)` - Announce character at cursor
- `CT_HIGHLIGHT (2)` - Track highlighted text
- `CT_WINDOW (3)` - Only announce within defined window

**Implementation**:
- Timer-based with configurable delay (0-1000ms)
- Checks position cache before calculating
- Respects quiet mode and profile windows
- Integrated with window definitions

**Location**: `addon/globalPlugins/tdsr.py` (event handlers and tracking methods)

## Data Flow

### 1. Navigation Command Flow

```
User presses NVDA+Alt+I (read current line)
    ↓
script_readCurrentLine() called
    ↓
Check isTerminalApp() → Terminal detection
    ↓
_getReviewPosition() → Get current TextInfo
    ↓
Expand to UNIT_LINE
    ↓
Extract text and process punctuation
    ↓
speech.speakText() → NVDA speech output
```

### 2. Cursor Tracking Flow

```
Caret position changes (event_caret)
    ↓
Start timer with cursor delay
    ↓
Timer expires → _trackCursor()
    ↓
Check tracking mode (Off/Standard/Highlight/Window)
    ↓
Get position from cache or calculate
    ↓
Check profile windows (if active)
    ↓
Announce character (if within bounds)
```

### 3. Selection Flow

```
NVDA+Alt+R (toggle mark)
    ↓
State machine: None → start → end → clear
    ↓
Store bookmark in _markStart or _markEnd
    ↓
User navigates to selection end
    ↓
NVDA+Alt+C or NVDA+Alt+Shift+C (copy)
    ↓
Calculate positions for both bookmarks
    ↓
Extract text (linear or rectangular)
    ↓
Strip ANSI codes (for rectangular)
    ↓
Apply Unicode-aware column extraction
    ↓
Copy to clipboard
    ↓
Announce result
```

### 4. Profile Activation Flow

```
User focuses terminal (event_gainFocus)
    ↓
isTerminalApp() → Verify supported terminal
    ↓
ProfileManager.detectApplication()
    ↓
Check appModule.appName
    ↓
Fallback to window title patterns
    ↓
Load matching profile (or default)
    ↓
Set _currentProfile
    ↓
Profile windows used in cursor tracking
    ↓
Profile settings override global settings
```

## Extension Points

### 1. Adding New Application Profiles

```python
# In ProfileManager._initializeDefaultProfiles()

myapp = ApplicationProfile('myapp', 'My Application')
myapp.punctuationLevel = PUNCT_MOST
myapp.cursorTrackingMode = CT_STANDARD
myapp.addWindow('status', 1, 1, 1, 80, mode='silent')
self.profiles['myapp'] = myapp
```

### 2. Custom Window Definitions

```python
profile = ApplicationProfile('custom')
profile.addWindow('header', 1, 5, 1, 80, mode='announce')
profile.addWindow('main', 6, 20, 1, 80, mode='announce')
profile.addWindow('footer', 21, 24, 1, 80, mode='silent')
```

### 3. Adding New Navigation Commands

```python
@script(
    description=_("My custom command"),
    gesture="kb:NVDA+alt+newkey"
)
def script_myCustomCommand(self, gesture):
    """Implement custom navigation."""
    if not self.isTerminalApp():
        gesture.send()
        return

    # Your implementation
    reviewPos = self._getReviewPosition()
    # ... navigate and announce
```

### 4. Custom ANSI Processing

```python
# Extend ANSIParser for custom codes
parser = ANSIParser()
parser.parse(text)
attrs = parser._getCurrentAttributes()

# Custom formatting logic
if attrs['bold'] and attrs['foreground'] == 'red':
    # Special handling for bold red text
    pass
```

## Performance Considerations

### 1. Position Caching

**Problem**: Row/column calculation is O(n) - expensive for large buffers.

**Solution**: `PositionCache` with 1-second TTL
- First access: Calculate and cache
- Subsequent access: Instant retrieval
- Automatic invalidation on buffer changes

**Impact**: ~500ms → <1ms for cached positions

### 2. Background Threading

**Use Case**: Large rectangular selections (>100 rows)

**Implementation**: `_backgroundCalculationThread`
- Prevents UI freezing
- Shows "please wait" message
- Completion callback on main thread
- Thread safety via wx.CallAfter

### 3. Lazy Profile Loading

**Strategy**: Profiles loaded on demand when terminal focused

**Benefit**: Faster NVDA startup, lower memory use

### 4. ANSI Stripping

**Optimization**: Compiled regex patterns
- Pattern compilation once at module load
- Reused for all strip operations
- Minimal overhead

### 5. Unicode Width (Three-Tier)

**Priority order**:
1. Rust `unicode-width` crate via FFI (fastest, most accurate)
2. Python `wcwidth` library (reliable fallback)
3. ASCII assumption (`width = 1`) if wcwidth unavailable

Each `UnicodeWidthHelper` method wraps the native call in try/except
so any FFI failure silently falls through to Python.

### 6. Native Helper Process

**Off-main-thread UIA reads** eliminate the `wx.CallAfter` + `Event.wait()`
round-trip that blocked NVDA's main thread.

**Event-driven output** via diff-based subscriptions: the helper polls
subscribed terminals, diffs text snapshots, strips ANSI, and pushes only
changed content over the named pipe.

**Server-side search** reads the terminal buffer and searches it in a
single IPC round-trip, avoiding a full buffer transfer to Python.

**Console API fallback** uses `AttachConsole` + `ReadConsoleOutputCharacterW`
for terminals without UIA TextPattern support.

## Code Organization

### File Structure

```
addon/
├── globalPlugins/
│   └── tdsr.py (2600+ lines)
│       ├── Constants & imports (1-85)
│       ├── PositionCache (86-160)
│       ├── ANSIParser (162-417)
│       ├── UnicodeWidthHelper (419-549)
│       ├── WindowDefinition (551-619)
│       ├── ApplicationProfile (621-707)
│       ├── ProfileManager (709-853)
│       ├── Validation helpers (855-946)
│       ├── GlobalPlugin class (948-2600+)
│       │   ├── Initialization (955-1000)
│       │   ├── Event handlers (1082-1150)
│       │   ├── Helper methods (1150-1900)
│       │   ├── Navigation scripts (1900-2100)
│       │   ├── Selection scripts (2108-2362)
│       │   └── Settings panel (2364+)
│       └── TDSRSettingsPanel (2364+)
```

### Naming Conventions

- **Private methods**: Prefix with `_` (e.g., `_calculatePosition`)
- **Scripts**: Prefix with `script_` (e.g., `script_readCurrentLine`)
- **Event handlers**: Prefix with `event_` (e.g., `event_gainFocus`)
- **Constants**: UPPER_CASE (e.g., `CT_STANDARD`, `PUNCT_MOST`)
- **Classes**: PascalCase (e.g., `PositionCache`, `ANSIParser`)

### Configuration Spec

Location: `addon/globalPlugins/tdsr.py:63-80`

Format: ConfigObj specification
- Type validation
- Default values
- Min/max ranges
- Registered globally: `config.conf.spec["TDSR"]`

## Testing Strategy

### Unit Tests

**Python tests** (`tests/`):
- `test_validation.py` - Input validation (40+ tests)
- `test_cache.py` - PositionCache (15+ tests)
- `test_config.py` - Configuration (20+ tests)
- `test_selection.py` - Selection operations (25+ tests)
- `test_integration.py` - Workflows (30+ tests)
- `test_performance.py` - Benchmarks (20+ tests)
- `test_ansi_unicode_profiles.py` - v1.0.18 features (20+ tests)
- `test_native_bridge.py` - FFI wrapper tests (67 tests, skipped when DLL absent)
- `test_helper_process.py` - Helper IPC unit tests (42 tests)
- `test_helper_e2e.py` - End-to-end helper tests (12 tests)

**Rust tests** (`native/`):
- `termaccess-core`: 66 tests (diff, ANSI strip, search, cache, unicode width)
- `termaccess-helper`: 35 tests (protocol serde, pipe framing, security, subscriptions)

### Test Infrastructure

- **Python**: pytest with unittest.TestCase, NVDA mocks in conftest.py
- **Rust**: `cargo test --all` (101 tests)
- **CI/CD**: GitHub Actions — `rust-build.yml` (test + build), `release.yml` (release), `nightly.yml` (nightly with native artifacts)
- **Coverage**: 70%+ target for Python, enforced in CI

### Manual Testing

See: `TESTING.md` for comprehensive manual test procedures

## Future Architecture Considerations

### Planned Refactoring (v1.0.19+)

1. **Extract ConfigManager**
   - Centralize configuration access
   - Validation in one place
   - Profile-aware config resolution

2. **Extract WindowManager**
   - Manage all window definitions
   - Unified window checking
   - Support dynamic window updates

3. **Extract PositionCalculator**
   - Encapsulate position logic
   - Alternative calculation strategies
   - Better caching integration

### Extension Ideas

1. **Plugin System**: Allow third-party extensions
2. **Custom Profiles UI**: Visual profile editor
3. **Gesture Customization**: User-definable shortcuts
4. **Script Recording**: Macro system for common tasks
5. **Remote Terminals**: SSH/telnet support

## CI/CD Pipeline

### Workflows

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `rust-build.yml` | Push/PR touching `native/` | Run Rust tests, clippy, build DLL+EXE for x86/x64 |
| `release.yml` | Push to `main` | Build native, bundle into addon, create GitHub release |
| `nightly.yml` | Daily cron + manual | Build native, bundle nightly addon with version suffix |
| `changelog-check.yml` | PR | Verify changelog entry exists |

### Build Artifacts

The release and nightly workflows produce these artifacts:
- `termaccess-dll-x64` / `termaccess-dll-x86` — `termaccess_ffi.dll` renamed to `termaccess.dll`
- `termaccess-helper-x64` / `termaccess-helper-x86` — `termaccess-helper.exe`

These are placed into `addon/lib/{arch}/` before the addon `.nvda-addon` zip is built.

## References

- [NVDA Developer Guide](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html)
- [NVDA Add-on Development Guide](https://github.com/nvda-es/devguides_translation)
- [TextInfo API Documentation](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html#textInfos)
- [ANSI Escape Codes](https://en.wikipedia.org/wiki/ANSI_escape_code)
- [wcwidth Library](https://pypi.org/project/wcwidth/)
- [unicode-width Crate](https://crates.io/crates/unicode-width)
- [Windows UI Automation](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)

---

**Document Maintained By**: TDSR Development Team
**Last Review**: 2026-03-12
**Next Review**: After major architectural changes
