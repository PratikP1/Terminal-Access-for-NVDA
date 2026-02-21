# Speakup-Inspired Feature Specifications and API Requirements

## Document Purpose

This document consolidates the research, analysis, and specifications for implementing Speakup-inspired features in Terminal Access for NVDA, with special focus on the API requirements for rectangular selection and window coordinate tracking.

**Related Documents**:
- `docs/archive/research/SPEAKUP_FEATURE_ANALYSIS.md` - Original feature analysis
- `docs/archive/research/API_RESEARCH_COORDINATE_TRACKING.md` - Detailed API research
- `docs/archive/implementation/CURSOR_TRACKING_IMPLEMENTATION.md` - Cursor tracking implementation
- `docs/archive/development/PHASE1_SPECS.md` - Phase 1 quick wins specifications
- `docs/archive/development/PHASE2_SPECS.md` - Phase 2 core enhancements

---

## Executive Summary

### What is Speakup?

Speakup is a kernel-level screen reader for Linux terminals that has been the gold standard for terminal accessibility since 1997. It provides sophisticated features for terminal navigation, cursor tracking, and text selection that make terminal usage accessible and efficient.

**Repository**: https://github.com/linux-speakup/speakup

### Why This Matters

Terminal users, especially developers and system administrators, need powerful accessibility features to work efficiently with command-line interfaces, TUIs (Text User Interfaces), and structured terminal output. Speakup's 25+ years of development have identified the key features that make terminal work accessible.

### Implementation Status

**Already Implemented in Terminal Access v1.0.13**:
- Basic line/word/character navigation ✅
- Cursor tracking with multiple modes ✅
- Key echo with symbol processing ✅
- Quiet mode ✅
- Copy functionality ✅
- Screen windowing system (basic) ✅
- Attribute/color reading ✅
- Position announcement ✅

**Needs Enhancement**:
- Rectangular selection with true column tracking ⚠️
- Window coordinate tracking (currently uses bookmarks, not coordinates) ⚠️
- Punctuation level system (replaces binary processSymbols) ⚠️

---

## Feature Priority Matrix

### Tier 1: Critical Features (Highest Impact)

| Feature | Priority | Status | Complexity | API Requirements |
|---------|----------|--------|------------|------------------|
| **Punctuation Level System** | ⭐⭐⭐⭐⭐ | Not Started | Moderate | NVDA TextInfo API |
| **Screen Windowing System** | ⭐⭐⭐⭐⭐ | Partially Complete | Complex | Coordinate tracking, TextInfo |
| **Multiple Cursor Tracking Modes** | ⭐⭐⭐⭐ | Complete | Moderate | TextInfo, ANSI parsing |
| **Continuous Reading (Say All)** | ⭐⭐⭐⭐⭐ | Complete | Easy | TextInfo, Speech API |
| **Line Indentation Detection** | ⭐⭐⭐⭐ | Complete | Easy | TextInfo |

### Tier 2: Enhanced Navigation (Medium Priority)

| Feature | Priority | Status | Complexity | API Requirements |
|---------|----------|--------|------------|------------------|
| **Screen Edge Navigation** | ⭐⭐⭐ | Complete | Easy | TextInfo |
| **Read From/To Position** | ⭐⭐⭐ | Complete | Moderate | TextInfo |
| **Attribute/Color Reading** | ⭐⭐⭐⭐ | Complete | Moderate | ANSI parsing |
| **Enhanced Selection System** | ⭐⭐⭐ | Partially Complete | Moderate | Coordinate tracking |

### Tier 3: Nice to Have (Lower Priority)

| Feature | Priority | Status | Complexity | API Requirements |
|---------|----------|--------|------------|------------------|
| **Position Announcement** | ⭐⭐ | Complete | Easy | Coordinate calculation |
| **Character Code Announcement** | ⭐⭐ | Complete | Easy | TextInfo |
| **Application-Specific Profiles** | ⭐⭐⭐ | Not Started | Complex | Configuration system |

---

## Critical API Requirements

### 1. Rectangular Selection with Column Tracking

**User Need**: Copy columns from tables or structured data in terminal output.

**Example Use Case**:
```
# Terminal showing process list
PID    USER    CPU%   MEM%   COMMAND
1234   john    23.4   5.2    python script.py
5678   jane    45.1   8.7    node server.js
9012   mike    12.3   3.1    bash

# User wants to copy just the CPU% column (columns 20-25, rows 2-4)
# Result: "23.4\n45.1\n12.3"
```

#### API Requirements

**What We Need**:
1. Row/column coordinate system (not just character offsets)
2. Ability to extract text from specific column ranges across multiple lines
3. Fast position-to-coordinate and coordinate-to-position conversion
4. Unicode-aware character width calculations

**Available APIs**:

**NVDA TextInfo API** (Current Approach):
```python
# What TextInfo provides:
info = obj.makeTextInfo(textInfos.POSITION_CARET)
info.bookmark                    # Opaque position marker
info.text                        # Text content
info.move(unit, count)          # Move by line/character
info.expand(textInfos.UNIT_LINE) # Expand to line boundaries

# What TextInfo DOES NOT provide:
info.row                         # No row property ❌
info.column                      # No column property ❌
info.moveToCoordinate(row, col)  # No coordinate movement ❌
```

**Workaround - Manual Coordinate Calculation**:
```python
def _calculatePosition(self, textInfo):
    """Calculate row/column by counting from start."""
    terminal = self._boundTerminal

    # Count lines from buffer start to current position
    startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
    lineCount = 1
    testInfo = startInfo.copy()

    while testInfo.compareEndPoints(textInfo, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_LINE, 1)
        if moved == 0:
            break
        lineCount += 1

    # Count characters from line start to current position
    lineInfo = textInfo.copy()
    lineInfo.expand(textInfos.UNIT_LINE)
    lineInfo.collapse()

    colCount = 1
    testInfo = lineInfo.copy()

    while testInfo.compareEndPoints(textInfo, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_CHARACTER, 1)
        if moved == 0:
            break
        colCount += 1

    return (lineCount, colCount)
```

**Performance**: O(n) where n = row number. Acceptable for typical use but slow in large buffers.

**Windows Console API** (Not Accessible):
```python
# What Console API provides (if we had access):
COORD structure:
    .X  # Column coordinate
    .Y  # Row coordinate

GetConsoleScreenBufferInfo(handle)  # Get cursor position
ReadConsoleOutput(handle, rect)     # Read rectangular region

# Why we can't use it:
# - No way to get console handle from NVDA object
# - Process isolation (NVDA is separate process from terminal)
# - Windows Terminal uses ConPTY, not classic console API
```

**UI Automation** (Provides Pixel Coordinates, Not Grid Coordinates):
```python
# UIA TextPattern provides:
textRange.GetBoundingRectangles()  # Returns [left, top, width, height] in pixels

# Problem: Need to convert pixels to terminal grid coordinates
# Requires: character cell dimensions, terminal window position
# Result: Complex, error-prone, font/size dependent
```

#### Recommended Implementation

**Strategy**: Line-by-line extraction with column slicing (See API_RESEARCH_COORDINATE_TRACKING.md, Strategy 4)

**Implementation**:
```python
def extractRectangularRegion(self, startBookmark, endBookmark, startCol, endCol):
    """Extract rectangular region without true coordinate system."""
    terminal = self._boundTerminal
    result = []

    # Get start and end positions
    startInfo = terminal.makeTextInfo(startBookmark)
    endInfo = terminal.makeTextInfo(endBookmark)

    # Iterate line by line
    currentInfo = startInfo.copy()
    while currentInfo.compareEndPoints(endInfo, "startToStart") <= 0:
        # Get full line text
        lineInfo = currentInfo.copy()
        lineInfo.expand(textInfos.UNIT_LINE)
        lineText = lineInfo.text.rstrip('\n\r')

        # Extract column range (0-based indexing)
        startIdx = max(0, startCol - 1)
        endIdx = min(len(lineText), endCol)

        if startIdx < len(lineText):
            columnText = lineText[startIdx:endIdx]
            result.append(columnText)
        else:
            result.append('')  # Line too short

        # Move to next line
        moved = currentInfo.move(textInfos.UNIT_LINE, 1)
        if moved == 0:
            break

    return result
```

**Pros**:
- Works with pure NVDA TextInfo API
- No external dependencies or permissions needed
- Reasonably efficient for typical selections
- Compatible with all terminals NVDA supports

**Cons**:
- Assumes consistent column alignment (fixed-width font)
- Unicode characters may cause misalignment
- Tabs complicate column calculations
- No true coordinate system

**Enhancements**:
- Use `wcwidth` library for proper Unicode character width
- Expand tabs to spaces before extracting
- Validate column ranges
- Provide clear feedback

**Python Library**: `wcwidth` for Unicode character width calculations
```python
import wcwidth

text = "Hello 世界"  # Mixed ASCII and CJK
width = wcwidth.wcswidth(text)  # Returns 9 (Hello=5, space=1, 世界=4)

# Per-character width
for char in text:
    w = wcwidth.wcwidth(char)
    # Returns: 1 for ASCII, 2 for CJK, 0 for combining characters
```

---

### 2. Window Coordinate Tracking

**User Need**: Define rectangular regions to monitor or silence in terminals with complex layouts (status bars, split panes, tmux/screen).

**Example Use Case**:
```
# tmux with status bar at bottom
┌─────────────────────────────────────┐
│ Command output here                 │  ← Monitor this region only
│ More output                          │
│ ...                                  │
├─────────────────────────────────────┤
│ [tmux] 0:bash  1:vim  2:htop       │  ← Silence this (status bar)
└─────────────────────────────────────┘

# Window definition:
# Top: Row 1
# Bottom: Row 20
# Left: Column 1
# Right: Column 80
# Status bar (rows 21-25) is silenced
```

#### API Requirements

**What We Need**:
1. Store window boundaries as row/column coordinates
2. Check if cursor position is within window bounds
3. Fast coordinate comparison (happens on every cursor move)
4. Extract and read window content on demand

**Current Implementation** (tdsr.py, lines 782-828):
```python
# CURRENT: Stores TextInfo bookmarks
self._windowStartBookmark = reviewPos.bookmark

# PROBLEM: Bookmarks are opaque, can't check if position is "within" bounds
# Must recalculate coordinates every time
```

**Required Change**: Store as coordinates, not bookmarks
```python
# Configuration (already exists in confspec):
config.conf["TDSR"]["windowTop"] = 5       # Row 5
config.conf["TDSR"]["windowBottom"] = 20   # Row 20
config.conf["TDSR"]["windowLeft"] = 10     # Column 10
config.conf["TDSR"]["windowRight"] = 60    # Column 60
config.conf["TDSR"]["windowEnabled"] = True
```

#### Recommended Implementation

**Strategy**: Coordinate-based window with cached position checks

**Set Window by Coordinates**:
```python
def script_setWindow(self, gesture):
    """Set window using calculated coordinates."""
    reviewPos = self._getReviewPosition()
    row, col = self._calculatePosition(reviewPos)

    if not self._windowStartSet:
        # Store start coordinates
        config.conf["TDSR"]["windowTop"] = row
        config.conf["TDSR"]["windowLeft"] = col
        self._windowStartSet = True
        ui.message(_("Window start: row {row}, column {col}").format(row=row, col=col))
    else:
        # Store end coordinates (ensure correct order)
        startRow = config.conf["TDSR"]["windowTop"]
        startCol = config.conf["TDSR"]["windowLeft"]

        config.conf["TDSR"]["windowTop"] = min(startRow, row)
        config.conf["TDSR"]["windowBottom"] = max(startRow, row)
        config.conf["TDSR"]["windowLeft"] = min(startCol, col)
        config.conf["TDSR"]["windowRight"] = max(startCol, col)
        config.conf["TDSR"]["windowEnabled"] = True
        self._windowStartSet = False
        ui.message(_("Window defined"))
```

**Check if Position is in Window**:
```python
def _isInWindow(self, row, col):
    """Check if coordinates are within defined window."""
    if not config.conf["TDSR"]["windowEnabled"]:
        return True  # No window defined, everything is "in window"

    return (config.conf["TDSR"]["windowTop"] <= row <= config.conf["TDSR"]["windowBottom"] and
            config.conf["TDSR"]["windowLeft"] <= col <= config.conf["TDSR"]["windowRight"])
```

**Window-Based Cursor Tracking**:
```python
def _announceWindowCursor(self, obj):
    """Only announce if cursor is within defined window."""
    info = obj.makeTextInfo(textInfos.POSITION_CARET)

    # Check if position changed
    currentPos = info.bookmark.startOffset if hasattr(info, 'bookmark') else None
    if currentPos == self._lastCaretPosition:
        return
    self._lastCaretPosition = currentPos

    # Calculate coordinates (cache this!)
    row, col = self._calculatePosition(info)

    # Only announce if in window
    if self._isInWindow(row, col):
        self._announceStandardCursor(obj)
    # else: silent (outside window)
```

**Read Window Content**:
```python
def script_readWindow(self, gesture):
    """Read content within defined window."""
    if not config.conf["TDSR"]["windowEnabled"]:
        ui.message(_("No window defined"))
        return

    terminal = self._boundTerminal
    topRow = config.conf["TDSR"]["windowTop"]
    bottomRow = config.conf["TDSR"]["windowBottom"]
    leftCol = config.conf["TDSR"]["windowLeft"]
    rightCol = config.conf["TDSR"]["windowRight"]

    # Extract window region (same as rectangular selection)
    lines = []
    info = terminal.makeTextInfo(textInfos.POSITION_FIRST)
    info.move(textInfos.UNIT_LINE, topRow - 1)

    for row in range(topRow, bottomRow + 1):
        lineInfo = info.copy()
        lineInfo.expand(textInfos.UNIT_LINE)
        lineText = lineInfo.text.rstrip('\n\r')

        # Extract column range
        startIdx = max(0, leftCol - 1)
        endIdx = min(len(lineText), rightCol)

        if startIdx < len(lineText):
            lines.append(lineText[startIdx:endIdx])
        else:
            lines.append('')

        info.move(textInfos.UNIT_LINE, 1)

    windowText = '\n'.join(lines)
    if windowText.strip():
        speech.speakText(windowText)
    else:
        ui.message(_("Window is empty"))
```

**Performance Optimization**: Position caching
```python
class PositionCache:
    """Cache coordinate calculations with timeout."""

    def __init__(self, timeout_ms=1000):
        self.cache = {}  # bookmark -> (row, col, timestamp)
        self.timeout = timeout_ms

    def get(self, bookmark):
        """Get cached coordinates if still valid."""
        if bookmark in self.cache:
            row, col, timestamp = self.cache[bookmark]
            if (wx.GetApp().GetElapsedTime() - timestamp) < self.timeout:
                return (row, col)
        return None

    def set(self, bookmark, row, col):
        """Cache coordinates for bookmark."""
        self.cache[bookmark] = (row, col, wx.GetApp().GetElapsedTime())

    def invalidate(self):
        """Clear cache when terminal content changes."""
        self.cache.clear()
```

---

## Implementation Roadmap

### Phase 1: Quick Wins (COMPLETED - v1.0.11)

**Implemented**:
- ✅ Continuous Reading (Say All)
- ✅ Screen Edge Navigation
- ✅ Line Indentation Detection
- ✅ Position Announcement
- ✅ Character Code Announcement

### Phase 2: Core Enhancements (PRIORITY - v1.0.12)

**To Implement**:

1. **Punctuation Level System** (3-4 days)
   - Replace boolean `processSymbols` with 4-level system
   - Define punctuation sets for each level
   - Add cycling gestures (NVDA+Alt+[ and ])
   - Apply to key echo, cursor tracking, navigation
   - Update settings panel

2. **Read From/To Position** (2-3 days)
   - Implement directional reading (left, right, top, bottom)
   - Add NVDA+Alt+Shift+Arrow gestures
   - Integrate with punctuation levels
   - Test in various terminals

3. **Enhanced Selection System** (4-5 days)
   - Implement true rectangular selection with column tracking
   - Add `_calculatePosition()` helper method
   - Implement `extractRectangularRegion()`
   - Add position caching for performance
   - Support Unicode with `wcwidth`
   - Update copy gestures (NVDA+Alt+C, NVDA+Alt+Shift+C)

**Total Estimated Time**: 9-12 days

### Phase 3: Advanced Features (FUTURE - v1.0.13+)

**To Implement**:

1. **Enhanced Window Tracking** (1-2 weeks)
   - Convert window storage from bookmarks to coordinates
   - Implement coordinate-based boundary checks
   - Add position caching with invalidation
   - Implement full window reading
   - Add window monitoring mode

2. **Application Profiles** (2-3 weeks)
   - Application detection
   - Profile storage and management
   - Pre-configured windows for known apps
   - Profile switching logic

3. **Advanced Features** (ongoing)
   - Multiple window definitions
   - Window templates
   - Per-application punctuation levels
   - Custom gesture bindings per application

---

## Technical Specifications

### NVDA TextInfo API Usage

**Core Methods**:
```python
# Position creation
info = obj.makeTextInfo(textInfos.POSITION_CARET)     # Current position
info = obj.makeTextInfo(textInfos.POSITION_FIRST)     # Buffer start
info = obj.makeTextInfo(textInfos.POSITION_LAST)      # Buffer end
info = obj.makeTextInfo(bookmark)                     # From saved position

# Navigation
info.move(textInfos.UNIT_LINE, count)        # Move by lines
info.move(textInfos.UNIT_CHARACTER, count)   # Move by characters
info.expand(textInfos.UNIT_LINE)             # Expand to line boundaries
info.collapse(end=False)                     # Collapse to start/end

# Comparison
info.compareEndPoints(other, "startToStart")  # Compare positions (-1, 0, 1)

# Properties
info.text                                     # Text content
info.bookmark                                 # Position marker
```

**Coordinate Calculation Pattern**:
```python
def _calculatePosition(self, textInfo):
    """Calculate (row, column) from TextInfo."""
    # Count lines from start
    startInfo = self.terminal.makeTextInfo(textInfos.POSITION_FIRST)
    lineCount = 1
    testInfo = startInfo.copy()

    while testInfo.compareEndPoints(textInfo, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_LINE, 1)
        if moved == 0:
            break
        lineCount += 1

    # Count characters from line start
    lineInfo = textInfo.copy()
    lineInfo.expand(textInfos.UNIT_LINE)
    lineInfo.collapse()

    colCount = 1
    testInfo = lineInfo.copy()

    while testInfo.compareEndPoints(textInfo, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_CHARACTER, 1)
        if moved == 0:
            break
        colCount += 1

    return (lineCount, colCount)
```

### Windows Console API (Reference Only - Not Directly Accessible)

**Key Structures**:
```python
class COORD(ctypes.Structure):
    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", COORD),              # Buffer size
        ("dwCursorPosition", COORD),    # Cursor position
        ("wAttributes", wintypes.WORD), # Attributes
        ("srWindow", SMALL_RECT),       # Visible window
        ("dwMaximumWindowSize", COORD)  # Max window size
    ]
```

**Key Functions**:
- `GetConsoleScreenBufferInfo()` - Get console information
- `ReadConsoleOutputCharacter()` - Read characters at coordinates
- `ReadConsoleOutput()` - Read rectangular region
- `SetConsoleCursorPosition()` - Set cursor position

**Why Not Usable**:
- Cannot get console handle from NVDA object
- Process isolation prevents cross-process console access
- Windows Terminal uses ConPTY, not classic console
- Security restrictions

### Unicode Handling with wcwidth

**Installation**: `pip install wcwidth`

**Usage**:
```python
import wcwidth

# String display width
text = "Hello 世界"
width = wcwidth.wcswidth(text)  # Returns 9

# Per-character width
for char in text:
    w = wcwidth.wcwidth(char)
    # 1 for ASCII, 2 for CJK, 0 for combining, -1 for control
```

**Application**:
```python
def extractColumnWithUnicode(line, startCol, endCol):
    """Extract column range accounting for Unicode width."""
    currentCol = 1
    startIdx = 0
    endIdx = len(line)

    for idx, char in enumerate(line):
        charWidth = wcwidth.wcwidth(char) or 1  # Treat control as width 1

        if currentCol <= startCol < currentCol + charWidth:
            startIdx = idx
        if currentCol <= endCol < currentCol + charWidth:
            endIdx = idx + 1
            break

        currentCol += charWidth

    return line[startIdx:endIdx]
```

---

## Performance Considerations

### Position Calculation Performance

**Current Complexity**: O(n) where n = row number

**Typical Performance**:
- Row 10: ~10 TextInfo.move() calls (< 10ms)
- Row 100: ~100 calls (< 50ms)
- Row 1000: ~1000 calls (< 500ms)

**Acceptable For**:
- Occasional position announcements
- Window boundary setting (infrequent)
- Selection operations (user-initiated)

**Not Acceptable For**:
- Real-time cursor tracking (every cursor move)
- Frequent window checks without caching

**Optimization Strategy**: Position caching

```python
# Cache recent position calculations
self._positionCache = {}  # bookmark -> (row, col)
self._lastCachedPosition = None
self._cacheTimestamp = 0
CACHE_TIMEOUT = 1000  # ms

def _getPositionCached(self, textInfo):
    """Get position with caching."""
    bookmark = textInfo.bookmark

    # Check cache
    if bookmark in self._positionCache:
        cachedTime = self._cacheTimestamp
        currentTime = wx.GetApp().GetElapsedTime()
        if (currentTime - cachedTime) < CACHE_TIMEOUT:
            return self._positionCache[bookmark]

    # Calculate and cache
    row, col = self._calculatePosition(textInfo)
    self._positionCache[bookmark] = (row, col)
    self._cacheTimestamp = wx.GetApp().GetElapsedTime()

    return (row, col)
```

### Rectangular Selection Performance

**Factors**:
- Number of lines (N)
- Line length (L)
- Column range width (W)

**Complexity**: O(N * L) where N = rows selected, L = average line length

**Typical Performance**:
- 10 lines × 80 chars = 800 operations (< 50ms)
- 100 lines × 80 chars = 8000 operations (< 200ms)
- 1000 lines × 200 chars = 200,000 operations (~ 2-3 seconds)

**Mitigation**:
- Limit maximum selection size (e.g., 500 lines)
- Show progress for large selections
- Provide cancel option
- Consider background thread for very large selections

---

## Testing Requirements

### Manual Test Cases

**Rectangular Selection**:
1. Select single line, multiple columns
2. Select multiple lines, same column range
3. Select region with varying line lengths
4. Select region with Unicode characters (CJK)
5. Select region with tabs
6. Select empty region
7. Select region at buffer boundaries

**Window Coordinate Tracking**:
1. Define window in middle of screen
2. Define window at screen boundaries
3. Move cursor within window (should announce)
4. Move cursor outside window (should be silent)
5. Read window content
6. Clear window definition
7. Define multiple windows in succession

**Position Announcement**:
1. Announce position at buffer start (1, 1)
2. Announce position in middle
3. Announce position at buffer end
4. Announce position on empty line
5. Verify accuracy by comparing with manual count

### Performance Tests

1. **Large Buffer Position Calculation**:
   - Create buffer with 1000+ lines
   - Measure time to calculate position at row 500, 1000
   - Target: < 500ms for row 1000

2. **Repeated Window Checks**:
   - Define window
   - Move cursor rapidly within/outside window
   - Verify no lag or delay in announcements

3. **Large Rectangular Selection**:
   - Select 100 lines × 50 columns
   - Measure extraction time
   - Target: < 500ms

### Compatibility Tests

**Terminal Types**:
- Windows Terminal
- PowerShell
- Command Prompt (cmd.exe)
- Git Bash
- WSL terminal

**Content Types**:
- ASCII text
- Unicode (CJK, Arabic, Emoji)
- ANSI color codes
- Tables with columns
- Code with indentation
- Log files with timestamps

---

## Known Limitations and Trade-offs

### Coordinate Tracking Limitations

1. **No True Terminal Coordinate System**
   - TextInfo doesn't expose row/column directly
   - Must calculate by counting (O(n) complexity)
   - No coordinate-to-position conversion

2. **Performance in Large Buffers**
   - Position calculation slows with buffer size
   - Row 1000+ can take 500ms+ to calculate
   - Requires caching for acceptable performance

3. **Unicode Complexity**
   - Double-width characters (CJK) complicate column calculations
   - Combining characters have zero width
   - Variable-width fonts not supported
   - Requires `wcwidth` library for accurate handling

### Rectangular Selection Limitations

1. **Fixed-Width Font Assumption**
   - Assumes monospace font with consistent character width
   - Variable-width fonts will cause misalignment
   - Terminal font changes invalidate column positions

2. **Tab Character Handling**
   - Tabs expand to different widths depending on context
   - May need to expand tabs to spaces first
   - Tab width varies by terminal configuration

3. **ANSI Escape Sequences**
   - Color codes and formatting may be included in text
   - Need to strip ANSI codes before column calculations
   - May affect perceived vs. actual column positions

### Window Tracking Limitations

1. **No Viewport Detection**
   - Can't distinguish visible vs. scrolled content
   - Can't automatically adjust window for scrolling
   - User must manually define window boundaries

2. **No Layout Change Detection**
   - Terminal resize invalidates window definition
   - Split pane changes not automatically detected
   - User must redefine window after layout changes

3. **Single Window Limitation**
   - Only one window definition at a time
   - Can't monitor multiple regions simultaneously
   - Future enhancement: multiple window support

---

## Recommendations

### Immediate Actions (Implement in Phase 2 - v1.0.12)

1. **Implement True Rectangular Selection**
   - Add `_calculatePosition()` method if not present
   - Implement `extractRectangularRegion()` with line-by-line extraction
   - Add position caching for performance
   - Support Unicode with `wcwidth` library
   - Update `script_copyRectangularSelection()` to use new implementation

2. **Enhance Window Coordinate Tracking**
   - Change window storage from bookmarks to coordinate integers
   - Implement coordinate-based `_isInWindow()` check
   - Add position caching to `_announceWindowCursor()`
   - Implement full `script_readWindow()` with column extraction
   - Update `script_setWindow()` to calculate and store coordinates

3. **Add Punctuation Level System**
   - Define `PUNCTUATION_SETS` dictionary
   - Implement `_shouldProcessSymbol()` helper
   - Update key echo to use punctuation levels
   - Update cursor tracking to use punctuation levels
   - Add level cycling gestures
   - Update settings panel

### Future Enhancements (Phase 3+)

1. **Coordinate Caching System**
   - Implement `PositionCache` class
   - Cache with timeout and invalidation
   - Use for all coordinate calculations
   - Monitor performance improvements

2. **Viewport-Based Tracking**
   - Track only visible region (e.g., 50 lines around cursor)
   - Build line cache for viewport
   - Update cache on significant navigation
   - Optimize for real-time cursor tracking

3. **Advanced Window Features**
   - Multiple window definitions
   - Window templates for common layouts
   - Per-application window profiles
   - Window monitoring mode (announce changes only)
   - Automatic window adjustment for layout changes

4. **Unicode Improvements**
   - Integrate `wcwidth` for all column calculations
   - Handle combining characters correctly
   - Handle zero-width characters
   - Handle right-to-left text (Arabic, Hebrew)
   - Test with emoji and special Unicode

---

## References and Resources

### Documentation

- **NVDA Developer Guide**: https://www.nvaccess.org/files/nvda/documentation/developerGuide.html
- **TextInfo API**: https://www.nvaccess.org/files/nvda/documentation/developerGuide.html#TextInfos
- **Windows Console API**: https://docs.microsoft.com/en-us/windows/console/console-functions
- **UI Automation**: https://docs.microsoft.com/en-us/windows/win32/winauto/uiauto-entry-uiautomation

### Python Libraries

- **wcwidth**: https://pypi.org/project/wcwidth/ - Unicode character width calculations
- **pywin32**: https://pypi.org/project/pywin32/ - Windows API access (reference only)
- **ctypes**: https://docs.python.org/3/library/ctypes.html - Foreign function library

### Related Projects

- **Speakup**: https://github.com/linux-speakup/speakup - Linux terminal screen reader
- **NVDA**: https://github.com/nvaccess/nvda - NVDA screen reader source code
- **Windows Terminal**: https://github.com/microsoft/terminal - Windows Terminal source

### TDSR Documentation

- `docs/archive/research/SPEAKUP_FEATURE_ANALYSIS.md` - Comprehensive Speakup feature analysis
- `docs/archive/research/API_RESEARCH_COORDINATE_TRACKING.md` - Detailed API research and implementation strategies
- `docs/archive/implementation/CURSOR_TRACKING_IMPLEMENTATION.md` - Cursor tracking implementation details
- `docs/archive/development/PHASE1_SPECS.md` - Phase 1 quick wins specifications
- `docs/archive/development/PHASE2_SPECS.md` - Phase 2 core enhancements specifications

---

## Conclusion

Implementing Speakup-inspired features in TDSR requires working within NVDA's TextInfo API limitations. While we cannot access true terminal coordinates directly through Windows Console API or UIA, we can achieve practical functionality through:

1. **Manual coordinate calculation** - Count lines and characters from buffer start
2. **Position caching** - Cache calculations for performance
3. **Line-by-line extraction** - Extract rectangular regions by iterating lines and slicing columns
4. **Coordinate-based window tracking** - Store windows as (row, col) coordinates instead of bookmarks
5. **Unicode handling** - Use `wcwidth` library for accurate character width calculations

**The result**: Practical, reliable rectangular selection and window tracking features that work within NVDA's architecture, providing significant value to terminal users despite not having kernel-level coordinate access like Speakup.

**Next Steps**:
1. Review this specification with development team
2. Prioritize Phase 2 features for v1.0.12
3. Begin implementation with rectangular selection
4. Test extensively with various terminal content
5. Iterate based on user feedback

---

**Document Version**: 1.0
**Last Updated**: 2026-02-21
**Author**: Terminal Access Development Team
**Status**: Final - Ready for Implementation
