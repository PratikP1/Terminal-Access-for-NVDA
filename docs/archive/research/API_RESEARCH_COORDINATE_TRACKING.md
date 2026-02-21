# API Research: Coordinate Tracking and Rectangular Selection

## Executive Summary

This document provides comprehensive API research for implementing rectangular selection with column tracking and window coordinate tracking in Terminal Access for NVDA. These features require accessing terminal row/column coordinates, which is not directly exposed through NVDA's standard TextInfo API.

**Key Finding**: NVDA's TextInfo API provides character offsets and bookmarks but **does not expose terminal row/column coordinates directly**. To implement true coordinate-based features, we need to either:
1. Calculate coordinates manually by counting lines/characters from TextInfo
2. Use Windows Console APIs directly via ctypes
3. Leverage UIA (UI Automation) properties if exposed by the terminal

## Current Implementation Status

### What Terminal Access Currently Has

The current implementation in `/home/runner/work/Terminal-Access-for-NVDA/Terminal-Access-for-NVDA/addon/globalPlugins/tdsr.py` uses:

**Position Tracking (Lines 1114-1168)**:
```python
def script_announcePosition(self, gesture):
    """Announce current row and column coordinates of review cursor."""
    # Calculate row (line number)
    startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
    currentInfo = reviewPos.copy()

    # Count lines from start to current position
    lineCount = 1
    testInfo = startInfo.copy()
    while testInfo.compareEndPoints(currentInfo, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_LINE, 1)
        if moved == 0:
            break
        lineCount += 1

    # Calculate column (character position in line)
    lineInfo = reviewPos.copy()
    lineInfo.expand(textInfos.UNIT_LINE)
    lineInfo.collapse()

    colCount = 1
    testInfo = lineInfo.copy()
    while testInfo.compareEndPoints(reviewPos, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_CHARACTER, 1)
        if moved == 0:
            break
        colCount += 1
```

**Limitations**:
- Manual counting is slow for large buffers
- No true terminal coordinate system integration
- Rectangular selection is simplified (lines 1551-1592)
- Window tracking stores bookmarks, not coordinates (lines 782-828)

---

## 1. NVDA TextInfo API

### Core TextInfo Methods

NVDA's TextInfo API is the primary interface for text navigation and manipulation. All terminal text access goes through this API.

**Source**: NVDA Developer Guide - https://www.nvaccess.org/files/nvda/documentation/developerGuide.html

#### Creating TextInfo Objects

```python
import textInfos

# Create TextInfo at specific positions
info = obj.makeTextInfo(textInfos.POSITION_CARET)     # Current caret
info = obj.makeTextInfo(textInfos.POSITION_FIRST)     # Start of buffer
info = obj.makeTextInfo(textInfos.POSITION_LAST)      # End of buffer
info = obj.makeTextInfo(textInfos.POSITION_ALL)       # Entire buffer
info = obj.makeTextInfo(bookmark)                     # From saved bookmark
```

#### Position Units

```python
# Available units for text navigation
textInfos.UNIT_CHARACTER  # Single character
textInfos.UNIT_WORD       # Word boundary
textInfos.UNIT_LINE       # Line boundary
textInfos.UNIT_PARAGRAPH  # Paragraph
textInfos.UNIT_STORY      # Entire document
```

#### TextInfo Properties and Methods

```python
# Properties
info.text                  # Get text content (str)
info.bookmark             # Opaque position marker (for comparison)
info.isCollapsed          # True if start == end

# Navigation methods
info.move(unit, count)                    # Move by unit (returns count moved)
info.expand(unit)                         # Expand to unit boundaries
info.collapse(end=False)                  # Collapse to start or end
info.setEndPoint(otherInfo, which)        # Set endpoint to another position

# Comparison methods
info.compareEndPoints(other, which)       # Compare positions (-1, 0, 1)
# which can be: "startToStart", "startToEnd", "endToStart", "endToEnd"
```

#### Example: Counting Lines and Columns

```python
def calculatePosition(reviewPos, terminal):
    """Calculate row/column from TextInfo."""
    # Get line number by counting from start
    startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
    lineCount = 1

    testInfo = startInfo.copy()
    while testInfo.compareEndPoints(reviewPos, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_LINE, 1)
        if moved == 0:
            break
        lineCount += 1

    # Get column by counting from line start
    lineInfo = reviewPos.copy()
    lineInfo.expand(textInfos.UNIT_LINE)
    lineInfo.collapse()  # Move to line start

    colCount = 1
    testInfo = lineInfo.copy()
    while testInfo.compareEndPoints(reviewPos, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_CHARACTER, 1)
        if moved == 0:
            break
        colCount += 1

    return lineCount, colCount
```

### TextInfo Limitations for Terminal Coordinates

**Problems**:
1. **No direct coordinate access**: TextInfo doesn't expose row/column as properties
2. **Performance**: Counting from start is O(n) for position calculation
3. **No coordinate-to-position conversion**: Can't jump to specific (row, col)
4. **No visible area info**: Can't detect viewport boundaries
5. **Character offsets only**: Bookmarks are opaque, not coordinate-based

**Workarounds**:
- Cache line/column calculations
- Only recalculate when position changes
- Use bookmarks for relative positioning
- Accept performance trade-offs for coordinate features

---

## 2. Windows Console API

### Overview

The Windows Console API provides direct access to console screen buffers with full coordinate support. This is the underlying API that terminal emulators use.

**Documentation**: https://docs.microsoft.com/en-us/windows/console/console-functions

### Key Structures

#### COORD Structure

```python
import ctypes
from ctypes import wintypes

class COORD(ctypes.Structure):
    """Screen buffer coordinates (column, row)."""
    _fields_ = [
        ("X", wintypes.SHORT),  # Column (0-based)
        ("Y", wintypes.SHORT),  # Row (0-based)
    ]
```

#### SMALL_RECT Structure

```python
class SMALL_RECT(ctypes.Structure):
    """Screen buffer rectangle boundaries."""
    _fields_ = [
        ("Left", wintypes.SHORT),    # Left column
        ("Top", wintypes.SHORT),     # Top row
        ("Right", wintypes.SHORT),   # Right column
        ("Bottom", wintypes.SHORT),  # Bottom row
    ]
```

#### CONSOLE_SCREEN_BUFFER_INFO Structure

```python
class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    """Console screen buffer information."""
    _fields_ = [
        ("dwSize", COORD),              # Screen buffer size
        ("dwCursorPosition", COORD),    # Cursor position
        ("wAttributes", wintypes.WORD), # Character attributes
        ("srWindow", SMALL_RECT),       # Visible window rectangle
        ("dwMaximumWindowSize", COORD), # Maximum window size
    ]
```

#### CHAR_INFO Structure

```python
class CHAR_INFO(ctypes.Structure):
    """Character and attribute data for screen buffer cell."""
    _fields_ = [
        ("Char", wintypes.WCHAR),      # Unicode character
        ("Attributes", wintypes.WORD), # Color/formatting attributes
    ]
```

### Core API Functions

#### GetConsoleScreenBufferInfo

```python
import ctypes
from ctypes import windll

def GetConsoleScreenBufferInfo(hConsoleOutput):
    """
    Get console screen buffer information including cursor position.

    Args:
        hConsoleOutput: Handle to console screen buffer

    Returns:
        CONSOLE_SCREEN_BUFFER_INFO structure or None on failure
    """
    kernel32 = windll.kernel32
    csbi = CONSOLE_SCREEN_BUFFER_INFO()

    if kernel32.GetConsoleScreenBufferInfo(hConsoleOutput, ctypes.byref(csbi)):
        return csbi
    return None

# Usage
STD_OUTPUT_HANDLE = -11
hStdOut = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
csbi = GetConsoleScreenBufferInfo(hStdOut)

if csbi:
    cursor_x = csbi.dwCursorPosition.X
    cursor_y = csbi.dwCursorPosition.Y
    buffer_width = csbi.dwSize.X
    buffer_height = csbi.dwSize.Y
    window_left = csbi.srWindow.Left
    window_top = csbi.srWindow.Top
    window_right = csbi.srWindow.Right
    window_bottom = csbi.srWindow.Bottom
```

#### ReadConsoleOutputCharacter

```python
def ReadConsoleOutputCharacter(hConsoleOutput, coord, length):
    """
    Read characters from console screen buffer at specific coordinates.

    Args:
        hConsoleOutput: Handle to console screen buffer
        coord: COORD structure with starting position
        length: Number of characters to read

    Returns:
        String of characters read or None on failure
    """
    kernel32 = windll.kernel32
    buffer = ctypes.create_unicode_buffer(length)
    chars_read = wintypes.DWORD()

    success = kernel32.ReadConsoleOutputCharacterW(
        hConsoleOutput,
        buffer,
        length,
        coord,
        ctypes.byref(chars_read)
    )

    if success:
        return buffer.value[:chars_read.value]
    return None

# Usage: Read 10 characters at column 5, row 3
coord = COORD(5, 3)
text = ReadConsoleOutputCharacter(hStdOut, coord, 10)
```

#### ReadConsoleOutput

```python
def ReadConsoleOutputRegion(hConsoleOutput, rect):
    """
    Read rectangular region from console screen buffer.

    Args:
        hConsoleOutput: Handle to console screen buffer
        rect: SMALL_RECT with boundaries

    Returns:
        2D array of CHAR_INFO structures
    """
    kernel32 = windll.kernel32

    width = rect.Right - rect.Left + 1
    height = rect.Bottom - rect.Top + 1
    buffer_size = COORD(width, height)
    buffer_coord = COORD(0, 0)

    # Create buffer for CHAR_INFO array
    buffer = (CHAR_INFO * (width * height))()

    success = kernel32.ReadConsoleOutputW(
        hConsoleOutput,
        buffer,
        buffer_size,
        buffer_coord,
        ctypes.byref(rect)
    )

    if success:
        # Convert flat array to 2D list
        result = []
        for row in range(height):
            row_data = []
            for col in range(width):
                idx = row * width + col
                row_data.append(buffer[idx])
            result.append(row_data)
        return result
    return None

# Usage: Read rectangular region (columns 10-20, rows 5-10)
rect = SMALL_RECT(10, 5, 20, 10)
region = ReadConsoleOutputRegion(hStdOut, rect)
```

#### SetConsoleCursorPosition

```python
def SetConsoleCursorPosition(hConsoleOutput, coord):
    """
    Set cursor position in console screen buffer.

    Args:
        hConsoleOutput: Handle to console screen buffer
        coord: COORD structure with new position

    Returns:
        True on success, False on failure
    """
    kernel32 = windll.kernel32
    return kernel32.SetConsoleCursorPosition(hConsoleOutput, coord) != 0

# Usage: Move cursor to column 10, row 5
coord = COORD(10, 5)
SetConsoleCursorPosition(hStdOut, coord)
```

### Getting Console Handle from NVDA Object

**Challenge**: NVDA objects don't directly expose console handles.

**Approach 1: From Process ID**
```python
import win32console
import win32api

def getConsoleHandle(obj):
    """Get console handle from NVDA object."""
    try:
        # Get process ID from NVDA object
        processID = obj.processID

        # Attach to console of process (if it has one)
        # This is complex and may require elevated permissions
        # Not recommended for NVDA add-ons

    except Exception:
        return None
```

**Approach 2: Standard Handles (Only works for current process)**
```python
def getStdConsoleHandle():
    """Get standard output handle for current console."""
    kernel32 = ctypes.windll.kernel32
    STD_OUTPUT_HANDLE = -11
    return kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

# NOTE: This only works if NVDA itself is running in a console,
# which it typically is NOT. NVDA runs as a GUI application.
```

### Windows Console API Limitations for NVDA Add-ons

**Critical Problems**:
1. **No direct handle access**: Cannot get console handle from NVDA object
2. **Process isolation**: Console APIs work in-process, NVDA is separate process
3. **Permission issues**: Accessing another process's console requires special permissions
4. **Windows Terminal incompatibility**: Modern Windows Terminal uses ConPTY, not classic console API
5. **Security restrictions**: Windows security model prevents cross-process console access

**Verdict**: Windows Console API is **not practical** for NVDA add-ons due to process isolation.

---

## 3. UI Automation (UIA) Properties

### Overview

UI Automation is Microsoft's accessibility framework. Windows Terminal and modern console applications expose accessibility information through UIA.

**Documentation**: https://docs.microsoft.com/en-us/windows/win32/winauto/uiauto-entry-uiautomation

### UIA TextPattern Interface

Windows Terminal implements `IUIAutomationTextPattern` which provides text access with some coordinate support.

#### Accessing UIA Properties from NVDA

```python
def getUIAProperties(obj):
    """Get UIA properties from NVDA object."""
    try:
        # Check if object has UIA interface
        if not hasattr(obj, 'UIAElement'):
            return None

        element = obj.UIAElement

        # Get supported patterns
        textPattern = element.GetCurrentPattern(UIA_TextPatternId)
        if not textPattern:
            return None

        # Get document range
        documentRange = textPattern.DocumentRange

        return {
            'element': element,
            'textPattern': textPattern,
            'documentRange': documentRange
        }

    except Exception:
        return None
```

#### UIA Text Range Properties

```python
# UIA Text Range provides:
# - GetText() - Get text content
# - GetBoundingRectangles() - Get screen coordinates
# - Move() - Move by text units
# - MoveEndpointByUnit() - Adjust range boundaries

def getTextRangeCoordinates(textRange):
    """Get bounding rectangles for text range."""
    try:
        # Returns array of rectangles [left, top, width, height, ...]
        rects = textRange.GetBoundingRectangles()

        if rects:
            # First rectangle
            left = rects[0]
            top = rects[1]
            width = rects[2]
            height = rects[3]

            return {
                'left': left,
                'top': top,
                'width': width,
                'height': height
            }
    except Exception:
        return None
```

### UIA Coordinate System

**Important**: UIA uses **screen pixel coordinates**, not terminal row/column coordinates.

```python
# UIA provides:
# - X, Y pixel positions on screen
# - Width, height in pixels
# - Not row/column in terminal grid

# To convert to row/column, would need:
# - Character cell dimensions (pixels per character)
# - Terminal window position
# - Complex calculations with potential errors
```

### Terminal-Specific UIA Properties

**Windows Terminal UIA Implementation**:
- Implements `IUIAutomationTextPattern`
- Exposes text content via text ranges
- Provides bounding rectangles (pixel coordinates)
- Supports text unit navigation (character, word, line)

**What's Missing**:
- No direct row/column coordinate properties
- No terminal grid coordinate system
- No column-based text extraction API
- No visible viewport coordinate information

### Practical UIA Usage in NVDA Add-ons

```python
def checkUIASupport(obj):
    """Check if object supports UIA text access."""
    try:
        # NVDA abstracts UIA access
        # Check if object is UIA-based
        if hasattr(obj, 'UIATextPattern'):
            return True

        # Check TextInfo type
        info = obj.makeTextInfo(textInfos.POSITION_CARET)
        # UIA terminals typically use UIA.UIATextInfo
        return 'UIA' in str(type(info))

    except Exception:
        return False
```

### UIA Limitations for Coordinate Tracking

**Problems**:
1. **Pixel coordinates only**: No terminal grid coordinates
2. **Conversion complexity**: Pixel-to-row/column requires character metrics
3. **Font/size dependencies**: Character dimensions vary by font/size
4. **Window positioning**: Need to track terminal window position
5. **Performance overhead**: UIA calls have latency

**Verdict**: UIA is **available but not ideal** for terminal coordinate tracking. Better than nothing, but requires pixel-to-grid conversion.

---

## 4. Practical Implementation Strategies

### Strategy 1: TextInfo-Based Coordinate Calculation (Current Approach)

**Implementation**: Count lines and characters from buffer start using TextInfo.move()

**Pros**:
- Pure NVDA API, no external dependencies
- Works with all terminals NVDA supports
- No security or permission issues
- Already implemented in TDSR

**Cons**:
- O(n) performance for position calculation
- Slow in large buffers
- No reverse lookup (can't jump to coordinate)
- No viewport boundary detection

**Best For**:
- Position announcement (occasional use)
- Features that don't need real-time coordinates
- Maximum compatibility

**Code Example** (already in TDSR):
```python
# See lines 1114-1168 in tdsr.py
def script_announcePosition(self, gesture):
    # Count lines from start to current position
    lineCount = 1
    testInfo = startInfo.copy()
    while testInfo.compareEndPoints(currentInfo, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_LINE, 1)
        if moved == 0:
            break
        lineCount += 1
```

### Strategy 2: Cached Coordinate Mapping

**Implementation**: Build and maintain a cache of bookmarks to coordinates

**Approach**:
```python
class CoordinateCache:
    """Cache mapping between TextInfo bookmarks and coordinates."""

    def __init__(self, terminal):
        self.terminal = terminal
        self.cache = {}  # bookmark -> (row, col)
        self.lineCache = []  # List of bookmarks for line starts

    def buildCache(self):
        """Build initial coordinate cache."""
        info = self.terminal.makeTextInfo(textInfos.POSITION_FIRST)
        row = 1

        # Cache start of each line
        while True:
            lineStart = info.copy()
            lineStart.collapse()
            self.lineCache.append(lineStart.bookmark)

            # Move to next line
            moved = info.move(textInfos.UNIT_LINE, 1)
            if moved == 0:
                break
            row += 1

    def getCoordinates(self, bookmark):
        """Get row/column from bookmark (fast lookup)."""
        # Use binary search on lineCache to find row
        # Then count characters to find column
        pass

    def invalidate(self):
        """Clear cache when terminal content changes."""
        self.cache.clear()
        self.lineCache.clear()
```

**Pros**:
- Faster lookups after initial build
- Can handle multiple coordinate requests efficiently
- Still uses pure NVDA API

**Cons**:
- Memory overhead for large buffers
- Must invalidate on content changes
- Initial build still O(n)
- Complex cache invalidation logic

**Best For**:
- Multiple coordinate lookups in succession
- Rectangular selection operations
- Window-based tracking with frequent checks

### Strategy 3: Hybrid Approach with Viewport Tracking

**Implementation**: Assume viewport is small, only track visible region

**Approach**:
```python
class ViewportTracker:
    """Track only visible viewport region for fast coordinate access."""

    def __init__(self, terminal, viewportHeight=50):
        self.terminal = terminal
        self.viewportHeight = viewportHeight
        self.viewportStart = None
        self.coordinateMap = {}

    def updateViewport(self, currentPosition):
        """Update viewport around current position."""
        # Expand to viewport lines around current position
        info = currentPosition.copy()

        # Move up viewportHeight/2 lines
        info.move(textInfos.UNIT_LINE, -(self.viewportHeight // 2))
        self.viewportStart = info.copy()

        # Build coordinate map for viewport only
        self.coordinateMap.clear()
        for row in range(self.viewportHeight):
            lineInfo = info.copy()
            lineInfo.expand(textInfos.UNIT_LINE)
            self.coordinateMap[row] = lineInfo.bookmark

            info.move(textInfos.UNIT_LINE, 1)

    def getRelativeCoordinates(self, position):
        """Get coordinates relative to viewport."""
        # Fast lookup in small viewport
        pass
```

**Pros**:
- Fast for typical use cases
- Lower memory overhead
- Practical viewport size (not entire buffer)

**Cons**:
- Coordinates relative to viewport, not absolute
- Still needs updates on navigation
- Edge cases at viewport boundaries

**Best For**:
- Real-time cursor tracking
- Window-based monitoring
- Features that work with visible region

### Strategy 4: Rectangular Selection Without True Coordinates

**Implementation**: Extract text line-by-line and slice by character position

**Approach**:
```python
def extractRectangularRegion(terminal, startBookmark, endBookmark, startCol, endCol):
    """
    Extract rectangular region without true coordinate system.

    Args:
        terminal: Terminal object
        startBookmark: TextInfo bookmark for start line
        endBookmark: TextInfo bookmark for end line
        startCol: Starting column (1-based)
        endCol: Ending column (1-based)

    Returns:
        List of text strings (one per line)
    """
    result = []

    # Get start and end lines
    startInfo = terminal.makeTextInfo(startBookmark)
    endInfo = terminal.makeTextInfo(endBookmark)

    # Iterate line by line
    currentInfo = startInfo.copy()
    while currentInfo.compareEndPoints(endInfo, "startToStart") <= 0:
        # Get full line text
        lineInfo = currentInfo.copy()
        lineInfo.expand(textInfos.UNIT_LINE)
        lineText = lineInfo.text.rstrip('\n\r')

        # Extract columns
        # Convert to 0-based for slicing
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
- Works with TextInfo API
- No coordinate system needed
- Reasonably efficient for small regions

**Cons**:
- Must calculate start/end columns separately
- Assumes consistent column alignment
- May have issues with tab characters
- Variable-width characters (Unicode) can cause misalignment

**Best For**:
- Simplified rectangular selection
- Column-based copying from tables
- ASCII-aligned terminal output

### Strategy 5: Python Libraries for Console Access

**Available Libraries**:

#### pywin32 (win32console)

```python
import win32console

# Get console handle
hConsole = win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)

# Get screen buffer info
csbi = hConsole.GetConsoleScreenBufferInfo()

# Access coordinates
cursor = csbi['CursorPosition']
cursor_x = cursor.X
cursor_y = cursor.Y

# Read rectangular region
buffer = hConsole.ReadConsoleOutputCharacter(coord, length)
```

**Problem**: Same issue as raw Console API - can't get handle for external process (terminal running in another process).

#### wcwidth (Character Width Calculation)

```python
import wcwidth

# Get display width of Unicode string
text = "Hello 世界"
width = wcwidth.wcswidth(text)  # Returns 9 (Hello=5, space=1, 世界=4)

# Per-character width
for char in text:
    w = wcwidth.wcwidth(char)
    print(f"{char}: width {w}")
```

**Use Case**: Calculate actual display width for proper column alignment with Unicode characters.

**Limitation**: Doesn't solve coordinate access problem, but helps with column calculation.

---

## 5. Recommended Implementation Plan

### For Rectangular Selection with Column Tracking

**Recommendation**: Use **Strategy 4** (Line-by-line extraction with column slicing)

**Implementation Steps**:

1. **Mark Start and End Positions** (already implemented)
   ```python
   self._markStart = reviewPos.bookmark  # TextInfo bookmark
   self._markEnd = reviewPos.bookmark
   ```

2. **Calculate Column Numbers** (use existing position calculation)
   ```python
   startRow, startCol = self._calculatePosition(markStartInfo)
   endRow, endCol = self._calculatePosition(markEndInfo)
   ```

3. **Extract Line by Line**
   ```python
   lines = []
   currentInfo = markStartInfo.copy()

   while currentInfo.compareEndPoints(markEndInfo, "startToStart") <= 0:
       lineInfo = currentInfo.copy()
       lineInfo.expand(textInfos.UNIT_LINE)
       lineText = lineInfo.text.rstrip('\n\r')

       # Extract column range
       columnText = lineText[startCol-1:endCol]
       lines.append(columnText)

       currentInfo.move(textInfos.UNIT_LINE, 1)
   ```

4. **Join and Copy**
   ```python
   rectangularText = '\n'.join(lines)
   api.copyToClip(rectangularText)
   ```

**Enhancements**:
- Use `wcwidth` library for proper Unicode width calculations
- Handle tabs (expand to spaces first)
- Validate column ranges
- Provide feedback for successful extraction

### For Window Coordinate Tracking

**Recommendation**: Use **Strategy 3** (Viewport tracking) combined with **Strategy 2** (Coordinate cache)

**Implementation Steps**:

1. **Define Window Boundaries** (store as row/column, not bookmarks)
   ```python
   # Configuration
   config.conf["TDSR"]["windowTop"] = 5      # Row 5
   config.conf["TDSR"]["windowBottom"] = 20  # Row 20
   config.conf["TDSR"]["windowLeft"] = 10    # Column 10
   config.conf["TDSR"]["windowRight"] = 60   # Column 60
   ```

2. **Build Line Cache for Window Region**
   ```python
   class WindowTracker:
       def buildWindowCache(self):
           """Cache bookmarks for window boundaries."""
           info = self.terminal.makeTextInfo(textInfos.POSITION_FIRST)

           # Move to window top
           info.move(textInfos.UNIT_LINE, self.windowTop - 1)
           self.windowTopBookmark = info.bookmark

           # Cache each line in window
           self.windowLines = []
           lineCount = self.windowBottom - self.windowTop + 1
           for _ in range(lineCount):
               self.windowLines.append(info.bookmark)
               info.move(textInfos.UNIT_LINE, 1)
   ```

3. **Check if Position is in Window**
   ```python
   def isInWindow(self, reviewPos):
       """Check if position is within defined window."""
       row, col = self._calculatePosition(reviewPos)

       if self.windowTop <= row <= self.windowBottom:
           if self.windowLeft <= col <= self.windowRight:
               return True
       return False
   ```

4. **Announce Only Within Window**
   ```python
   def _announceWindowCursor(self, obj):
       info = obj.makeTextInfo(textInfos.POSITION_CARET)

       if self.isInWindow(info):
           # Announce as normal
           self._announceStandardCursor(obj)
       # else: silent (outside window)
   ```

**Optimizations**:
- Cache window boundary calculations
- Only recalculate when window definition changes
- Use relative coordinates within window for faster checks

---

## 6. Code Examples and Patterns

### Complete Rectangular Selection Implementation

```python
def script_copyRectangularSelection(self, gesture):
    """Copy rectangular region (column-based) between marks."""
    if not self.isTerminalApp():
        gesture.send()
        return

    if not self._markStart or not self._markEnd:
        ui.message(_("Set start and end marks first"))
        return

    try:
        terminal = self._boundTerminal
        if not terminal:
            ui.message(_("Unable to copy"))
            return

        # Get start and end positions
        startInfo = terminal.makeTextInfo(self._markStart)
        endInfo = terminal.makeTextInfo(self._markEnd)

        # Calculate row and column coordinates
        startRow, startCol = self._calculatePosition(startInfo)
        endRow, endCol = self._calculatePosition(endInfo)

        # Ensure correct order
        if startRow > endRow:
            startRow, endRow = endRow, startRow
        if startCol > endCol:
            startCol, endCol = endCol, startCol

        # Extract rectangular region line by line
        lines = []
        currentInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)

        # Move to start row
        currentInfo.move(textInfos.UNIT_LINE, startRow - 1)

        # Extract each line in range
        for row in range(startRow, endRow + 1):
            lineInfo = currentInfo.copy()
            lineInfo.expand(textInfos.UNIT_LINE)
            lineText = lineInfo.text.rstrip('\n\r')

            # Extract column range (0-based indexing)
            startIdx = max(0, startCol - 1)
            endIdx = min(len(lineText), endCol)

            if startIdx < len(lineText):
                columnText = lineText[startIdx:endIdx]
            else:
                columnText = ''  # Line too short

            lines.append(columnText)

            # Move to next line
            moved = currentInfo.move(textInfos.UNIT_LINE, 1)
            if moved == 0:
                break

        # Join lines and copy to clipboard
        rectangularText = '\n'.join(lines)

        if rectangularText and self._copyToClipboard(rectangularText):
            ui.message(_("Rectangular selection copied: {rows} rows, columns {start} to {end}").format(
                rows=len(lines),
                start=startCol,
                end=endCol
            ))
        else:
            ui.message(_("Unable to copy"))

    except Exception as e:
        ui.message(_("Unable to copy"))

def _calculatePosition(self, textInfo):
    """
    Calculate row and column coordinates from TextInfo.

    Args:
        textInfo: TextInfo object to get position for

    Returns:
        Tuple of (row, column) as 1-based integers
    """
    terminal = self._boundTerminal
    if not terminal:
        return (0, 0)

    # Calculate row (line number)
    startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
    lineCount = 1

    testInfo = startInfo.copy()
    while testInfo.compareEndPoints(textInfo, "startToStart") < 0:
        moved = testInfo.move(textInfos.UNIT_LINE, 1)
        if moved == 0:
            break
        lineCount += 1

    # Calculate column (character position in line)
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

### Complete Window Tracking Implementation

```python
def script_setWindow(self, gesture):
    """Set screen window boundaries using row/column coordinates."""
    if not self.isTerminalApp():
        gesture.send()
        return

    try:
        reviewPos = self._getReviewPosition()
        if reviewPos is None:
            ui.message(_("Unable to set window"))
            return

        # Calculate position
        row, col = self._calculatePosition(reviewPos)

        if not self._windowStartSet:
            # Set start position
            config.conf["TDSR"]["windowTop"] = row
            config.conf["TDSR"]["windowLeft"] = col
            self._windowStartSet = True
            ui.message(_("Window start set: row {row}, column {col}. Move to end position and press again.").format(
                row=row, col=col
            ))
        else:
            # Set end position
            startRow = config.conf["TDSR"]["windowTop"]
            startCol = config.conf["TDSR"]["windowLeft"]

            # Ensure correct order
            config.conf["TDSR"]["windowTop"] = min(startRow, row)
            config.conf["TDSR"]["windowBottom"] = max(startRow, row)
            config.conf["TDSR"]["windowLeft"] = min(startCol, col)
            config.conf["TDSR"]["windowRight"] = max(startCol, col)

            config.conf["TDSR"]["windowEnabled"] = True
            self._windowStartSet = False

            ui.message(_("Window defined: rows {top} to {bottom}, columns {left} to {right}").format(
                top=config.conf["TDSR"]["windowTop"],
                bottom=config.conf["TDSR"]["windowBottom"],
                left=config.conf["TDSR"]["windowLeft"],
                right=config.conf["TDSR"]["windowRight"]
            ))
    except Exception:
        ui.message(_("Unable to set window"))
        self._windowStartSet = False

def _announceWindowCursor(self, obj):
    """Window tracking - only announce if cursor is within defined window."""
    if not config.conf["TDSR"]["windowEnabled"]:
        # Window not enabled, fall back to standard tracking
        self._announceStandardCursor(obj)
        return

    try:
        # Get the current caret position
        info = obj.makeTextInfo(textInfos.POSITION_CARET)

        # Check if position has actually changed
        currentPos = (info.bookmark.startOffset if hasattr(info, 'bookmark') else None)
        if currentPos == self._lastCaretPosition:
            return

        self._lastCaretPosition = currentPos

        # Calculate position
        row, col = self._calculatePosition(info)

        # Check if within window bounds
        if (config.conf["TDSR"]["windowTop"] <= row <= config.conf["TDSR"]["windowBottom"] and
            config.conf["TDSR"]["windowLeft"] <= col <= config.conf["TDSR"]["windowRight"]):
            # Within window - announce as normal
            self._announceStandardCursor(obj)
        # else: outside window - silent

    except Exception:
        # Fall back to standard tracking on error
        self._announceStandardCursor(obj)

def script_readWindow(self, gesture):
    """Read the content within the defined window."""
    if not self.isTerminalApp():
        gesture.send()
        return

    if not config.conf["TDSR"]["windowEnabled"]:
        ui.message(_("No window defined"))
        return

    try:
        terminal = self._boundTerminal
        if not terminal:
            ui.message(_("Unable to read window"))
            return

        # Get window boundaries
        topRow = config.conf["TDSR"]["windowTop"]
        bottomRow = config.conf["TDSR"]["windowBottom"]
        leftCol = config.conf["TDSR"]["windowLeft"]
        rightCol = config.conf["TDSR"]["windowRight"]

        # Extract window region line by line
        lines = []
        info = terminal.makeTextInfo(textInfos.POSITION_FIRST)

        # Move to top row
        info.move(textInfos.UNIT_LINE, topRow - 1)

        # Extract each line in window
        for row in range(topRow, bottomRow + 1):
            lineInfo = info.copy()
            lineInfo.expand(textInfos.UNIT_LINE)
            lineText = lineInfo.text.rstrip('\n\r')

            # Extract column range
            startIdx = max(0, leftCol - 1)
            endIdx = min(len(lineText), rightCol)

            if startIdx < len(lineText):
                columnText = lineText[startIdx:endIdx]
            else:
                columnText = ''

            lines.append(columnText)

            info.move(textInfos.UNIT_LINE, 1)

        # Read window content
        windowText = '\n'.join(lines)
        if windowText and windowText.strip():
            speech.speakText(windowText)
        else:
            ui.message(_("Window is empty"))

    except Exception:
        ui.message(_("Unable to read window"))
```

---

## 7. Performance Considerations

### Position Calculation Performance

**Current Implementation** (counting from start):
- Time complexity: O(n) where n = row number
- For row 100: ~100 TextInfo.move() calls
- For row 1000: ~1000 TextInfo.move() calls
- Each move() call has API overhead

**Optimization Strategies**:

1. **Cache Recent Positions**
   ```python
   self._positionCache = {}  # bookmark -> (row, col)
   self._cacheTimeout = 1000  # ms
   ```

2. **Incremental Updates**
   ```python
   # If we know current position and moved one line:
   if lastRow is not None and moved == 1:
       currentRow = lastRow + 1  # O(1)
   ```

3. **Relative Positioning**
   ```python
   # Calculate relative to last known position, not start
   if abs(currentBookmark - lastBookmark) < 10:
       # Use relative calculation
   ```

### Rectangular Selection Performance

**Factors**:
- Number of lines in selection (N)
- Line length (L)
- Column range width (W)

**Complexity**: O(N * L) where N = rows, L = average line length

**Optimizations**:
- Limit maximum selection size
- Show progress for large selections
- Use background thread for very large regions

---

## 8. Limitations and Trade-offs

### Current Limitations

1. **No True Coordinate System**
   - TextInfo doesn't expose row/column directly
   - Must calculate every time
   - No coordinate-to-position conversion

2. **Performance**
   - O(n) for position calculation
   - Slow in large buffers (> 1000 lines)
   - Impacts real-time cursor tracking

3. **Rectangular Selection Accuracy**
   - Assumes consistent column alignment
   - Unicode characters may cause misalignment
   - Tabs complicate column calculations
   - Variable-width fonts not supported

4. **Window Tracking**
   - Must recalculate position for each cursor move
   - No viewport boundary detection
   - Can't distinguish visible vs. scrolled content

### Trade-offs

**Accuracy vs. Performance**:
- Accurate position calculation is slow
- Fast heuristics may be inaccurate
- Must choose based on use case

**Simplicity vs. Features**:
- Simple line-based selection is reliable
- True rectangular selection requires complexity
- Unicode handling adds significant complexity

**Compatibility vs. Optimization**:
- Pure TextInfo API works everywhere
- Terminal-specific optimizations may break
- Must support multiple terminal types

---

## 9. Recommendations and Next Steps

### Immediate Actions (Implement Now)

1. **Rectangular Selection**
   - Implement Strategy 4 (line-by-line with column slicing)
   - Add proper error handling for edge cases
   - Support Unicode with `wcwidth` library
   - Test with various terminal outputs

2. **Window Tracking**
   - Change window storage from bookmarks to row/column integers
   - Implement `_calculatePosition()` caching
   - Add window-based cursor tracking mode
   - Provide clear feedback for window definition

3. **Position Caching**
   - Add simple position cache with timeout
   - Cache last N position calculations
   - Invalidate on terminal content changes
   - Monitor performance improvements

### Future Enhancements (Consider Later)

1. **Viewport Tracking System**
   - Implement Strategy 3 (viewport-based coordinates)
   - Maintain cache for visible region only
   - Update on significant navigation
   - Optimize for common use cases

2. **Unicode Support**
   - Integrate `wcwidth` library
   - Handle double-width characters (CJK)
   - Handle combining characters
   - Handle zero-width characters

3. **Advanced Window Features**
   - Multiple window definitions
   - Window templates for common layouts
   - Per-application window profiles
   - Window monitoring mode (announce changes only)

### Research and Investigation

1. **Windows Terminal API**
   - Investigate if Windows Terminal exposes coordinate API
   - Check for Terminal-specific UIA properties
   - Explore Terminal's COM interfaces
   - Contact Windows Terminal team for accessibility API

2. **Performance Profiling**
   - Measure actual coordinate calculation times
   - Profile large buffer performance
   - Test with various terminal sizes
   - Identify bottlenecks for optimization

3. **Alternative Approaches**
   - Investigate terminal rendering pipelines
   - Explore console buffer snapshotting
   - Research accessibility API extensions
   - Consider hybrid approaches

---

## 10. References and Resources

### Official Documentation

- **NVDA Developer Guide**: https://www.nvaccess.org/files/nvda/documentation/developerGuide.html
- **Windows Console API**: https://docs.microsoft.com/en-us/windows/console/console-functions
- **UI Automation**: https://docs.microsoft.com/en-us/windows/win32/winauto/uiauto-entry-uiautomation
- **Windows Terminal**: https://github.com/microsoft/terminal

### Python Libraries

- **wcwidth**: https://pypi.org/project/wcwidth/ - Unicode character width calculations
- **pywin32**: https://pypi.org/project/pywin32/ - Windows API access (console, UIA)
- **ctypes**: https://docs.python.org/3/library/ctypes.html - Foreign function library

### Related Projects

- **Speakup**: https://github.com/linux-speakup/speakup - Linux terminal screen reader
- **TDSR Original**: Tyler Spivey's Terminal Data Structure Reader
- **NVDA Source**: https://github.com/nvaccess/nvda - NVDA screen reader source code

### Community Resources

- **NVDA Add-on Development Forum**: https://groups.io/g/nvda-addons
- **NVDA Developer Mailing List**: https://groups.io/g/nvda-devel
- **Windows Terminal Accessibility**: https://github.com/microsoft/terminal/issues

---

## Conclusion

Implementing rectangular selection and coordinate tracking in Terminal Access for NVDA is **feasible but requires working within TextInfo API limitations**. True terminal coordinate access is not available through standard NVDA APIs, but practical solutions exist:

**For Rectangular Selection**:
- Use line-by-line extraction with column slicing
- Calculate column positions from character offsets
- Handle Unicode characters with `wcwidth` library
- Accept limitations for complex layouts

**For Window Coordinate Tracking**:
- Store window as row/column integers (not bookmarks)
- Calculate position on-demand with caching
- Implement window boundary checks
- Optimize with position cache and relative calculations

**Performance**:
- Position calculation is O(n) but acceptable for typical use
- Caching dramatically improves repeated lookups
- Viewport-based approaches optimize for visible region
- Trade-offs between accuracy and speed

**Recommended Path Forward**:
1. Implement rectangular selection with Strategy 4
2. Enhance window tracking with coordinate storage
3. Add position caching for performance
4. Test extensively with various terminal content
5. Iterate based on user feedback

The implementation will not have the raw performance of kernel-level coordinate access (like Speakup), but will provide practical, reliable functionality within NVDA's architecture.
