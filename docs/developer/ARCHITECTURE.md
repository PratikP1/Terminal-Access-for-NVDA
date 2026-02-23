# TDSR for NVDA - Architecture Overview

**Version:** 1.0.18
**Last Updated:** 2026-02-21

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Architecture](#core-architecture)
3. [Key Components](#key-components)
4. [Data Flow](#data-flow)
5. [Extension Points](#extension-points)
6. [Performance Considerations](#performance-considerations)

## System Overview

TDSR for NVDA is implemented as an NVDA global plugin that enhances terminal accessibility for Windows. The add-on integrates with NVDA's review cursor system and extends it with terminal-specific navigation, selection, and reading features.

### Design Philosophy

- **Non-intrusive**: Works alongside NVDA's existing terminal support
- **Performance-conscious**: Caches expensive operations, uses background threading
- **Extensible**: Application profiles allow customization per terminal app
- **Accessible-first**: All features designed for screen reader users

### Technology Stack

- **Language**: Python 3.11+
- **Framework**: NVDA Global Plugin API
- **UI**: wxPython (via NVDA's GUI helpers)
- **Dependencies**: wcwidth (for Unicode/CJK support)

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
    Review Cursor (NVDA) ← Position Cache
                 ↓
         Text Extraction
                 ↓
    ANSI Parser / Unicode Helper
                 ↓
         Speech Output (NVDA)
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

**Location**: `addon/globalPlugins/tdsr.py:419-549`

**Uses**: wcwidth library with graceful fallback

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

### 5. Unicode Width Fallback

**Graceful Degradation**:
```python
try:
    import wcwidth
    width = wcwidth.wcwidth(char)
except ImportError:
    width = 1  # Fallback to ASCII assumption
```

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

Location: `tests/`

Files:
- `test_validation.py` - Input validation (40+ tests)
- `test_cache.py` - PositionCache (15+ tests)
- `test_config.py` - Configuration (20+ tests)
- `test_selection.py` - Selection operations (25+ tests)
- `test_integration.py` - Workflows (30+ tests)
- `test_performance.py` - Benchmarks (20+ tests)
- `test_ansi_unicode_profiles.py` - v1.0.18 features (20+ tests)

### Test Infrastructure

- **Framework**: pytest with unittest.TestCase
- **Mocking**: NVDA modules mocked in conftest.py
- **CI/CD**: GitHub Actions (Python 3.11)
- **Coverage**: 70%+ target, enforced in CI

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

## References

- [NVDA Developer Guide](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html)
- [NVDA Add-on Development Guide](https://github.com/nvda-es/devguides_translation)
- [TextInfo API Documentation](https://www.nvaccess.org/files/nvda/documentation/developerGuide.html#textInfos)
- [ANSI Escape Codes](https://en.wikipedia.org/wiki/ANSI_escape_code)
- [wcwidth Library](https://pypi.org/project/wcwidth/)

---

**Document Maintained By**: TDSR Development Team
**Last Review**: 2026-02-21
**Next Review**: After major architectural changes
