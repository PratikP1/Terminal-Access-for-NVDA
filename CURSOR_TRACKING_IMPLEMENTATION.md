# Cursor Tracking Implementation Summary

## Overview

This document summarizes the implementation of advanced cursor tracking features in TDSR for NVDA, inspired by the Speakup screen reader for Linux. These enhancements provide users with more sophisticated control over how cursor movements are announced in terminal applications.

## Features Implemented

### 1. Multiple Cursor Tracking Modes

TDSR now supports four distinct cursor tracking modes, allowing users to choose the most appropriate announcement strategy for their context:

#### Mode Constants
- `CT_OFF = 0` - Cursor tracking disabled
- `CT_STANDARD = 1` - Basic character announcement (default)
- `CT_HIGHLIGHT = 2` - Highlight/inverse video tracking
- `CT_WINDOW = 3` - Window-based tracking

#### Mode Cycling
- **Gesture**: `NVDA+Alt+Asterisk`
- **Behavior**: Cycles through modes: Off → Standard → Highlight → Window → Off
- **Announcement**: Announces the new mode when changed

#### Implementation Details
- Configuration: `cursorTrackingMode` in confspec (integer, default=1)
- Dispatcher: `_announceCursorPosition()` routes to mode-specific handlers
- Mode-specific handlers:
  - `_announceStandardCursor()` - Character at cursor position
  - `_announceHighlightCursor()` - Highlighted text detection
  - `_announceWindowCursor()` - Window-bounded tracking

### 2. Highlight Tracking Mode

Detects and announces text with special attributes (inverse video, color highlighting) commonly used in terminal applications for selections, menus, and emphasis.

#### Features
- ANSI escape code detection (ESC[7m for inverse video)
- Automatic fallback to standard mode if no highlighting detected
- Prevents repeated announcements of the same highlighted text
- Extracts clean text from ANSI-formatted lines

#### Implementation
- Detection: Searches for ANSI inverse video codes in current line
- Extraction: `_extractHighlightedText()` uses regex to clean ANSI codes
- State tracking: `_lastHighlightedText` prevents duplicates

#### Use Cases
- Menu navigation in ncurses applications
- Selection highlighting in editors
- Emphasized text in TUI applications
- Visual indicators (progress bars, status)

### 3. Screen Windowing System

Allows users to define rectangular regions on screen for focused monitoring or selective announcement, essential for complex terminal layouts.

#### Window Management Commands

**Set Window** - `NVDA+Alt+F2`
- Two-step process:
  1. First press: Set start position (top-left corner)
  2. Second press: Set end position (bottom-right corner)
- Announces confirmation at each step
- Stores window boundaries in configuration

**Clear Window** - `NVDA+Alt+F3`
- Removes window definition
- Restores full-screen tracking
- Disables window-based filtering

**Read Window** - `NVDA+Alt+Plus`
- Reads content within defined window
- Error message if no window defined
- Placeholder for future full implementation

#### Configuration Parameters
```python
"windowTop": "integer(default=0, min=0)",
"windowBottom": "integer(default=0, min=0)",
"windowLeft": "integer(default=0, min=0)",
"windowRight": "integer(default=0, min=0)",
"windowEnabled": "boolean(default=False)"
```

#### State Variables
- `_windowDefining`: Boolean flag for window definition in progress
- `_windowStartSet`: Boolean flag indicating start position is set
- `_windowStartBookmark`: TextInfo bookmark for window start position

#### Use Cases
- Silence status bars in tmux/screen
- Focus on specific output regions
- Monitor log sections in split terminals
- Ignore clock/date displays

### 4. Attribute/Color Reading

Enables users to identify ANSI color codes and text formatting attributes at the cursor position, crucial for understanding color-coded information.

#### Command
- **Gesture**: `NVDA+Alt+Shift+A`
- **Function**: Announces color and formatting attributes at cursor

#### Supported Attributes

**Text Colors** (30-37):
- Black, Red, Green, Yellow, Blue, Magenta, Cyan, White

**Background Colors** (40-47):
- Black, Red, Green, Yellow, Blue, Magenta, Cyan, White

**Text Formatting**:
- Bold (1)
- Underline (4)
- Inverse video (7)
- Reset (0)

#### Implementation
- Pattern: `\x1b\[([0-9;]+)m` - Captures ANSI SGR sequences
- Parser: `_parseColorCode()` - Converts codes to human-readable names
- Multi-attribute support: Handles semicolon-separated code lists
- Fallback: Announces "No color attributes detected" if none found

#### Use Cases
- Identify error messages (red text)
- Distinguish warning levels (yellow/orange)
- Understand syntax highlighting
- Verify color-coded status indicators

## Technical Architecture

### Event Flow

```
Terminal Application
    ↓
event_caret() triggered by cursor movement
    ↓
Cancel pending timer, schedule new announcement
    ↓
_announceCursorPosition() called after delay
    ↓
Check tracking mode (CT_OFF/STANDARD/HIGHLIGHT/WINDOW)
    ↓
Call mode-specific handler
    ↓
Announce to user via ui.message()
```

### Position Tracking

- Uses TextInfo bookmarks for position comparison
- Stores `_lastCaretPosition` to prevent duplicate announcements
- Debouncing with `wx.CallLater` for smooth experience
- Configurable delay via `cursorDelay` setting (0-1000ms)

### ANSI Code Processing

The implementation uses Python regex for ANSI escape sequence parsing:

```python
# Pattern for ANSI SGR (Select Graphic Rendition) codes
ansiPattern = re.compile(r'\x1b\[[0-9;]*m')

# Extract color codes
colorPattern = re.compile(r'\x1b\[([0-9;]+)m')
```

### Settings Integration

All features are configurable through NVDA's settings dialog:

**Settings Panel Updates**:
- Added "Cursor tracking mode" dropdown (Off, Standard, Highlight, Window)
- Integrated with existing TDSR settings panel
- Saved to NVDA configuration on OK

**Configuration Persistence**:
- All settings stored in `config.conf["TDSR"]`
- Preserved across NVDA sessions
- Default values provided for new installations

## Comparison with Speakup

### Similarities
- Four distinct tracking modes (Off, Standard, Highlight, Window)
- Screen windowing system with set/clear/read commands
- Attribute/color reading functionality
- Mode cycling gesture

### Differences

**TDSR for NVDA**:
- Uses NVDA's TextInfo API instead of direct console access
- ANSI code parsing instead of console attribute queries
- Windows Terminal/PowerShell focus instead of Linux TTY
- GUI settings panel instead of /sys filesystem
- wx.CallLater debouncing instead of kernel timers

**Speakup**:
- Kernel-level console access
- Direct VGA attribute reading
- Hardware synthesizer support
- More sophisticated highlight detection (8-color buffer tracking)
- Row/column coordinate tracking

### Adaptations

The implementation adapts Speakup's concepts to the Windows/NVDA environment:

1. **TextInfo Bookmarks** replace row/column coordinates
2. **ANSI Escape Parsing** replaces VGA attribute reading
3. **NVDA's ui.message()** replaces direct synthesizer control
4. **wx.CallLater** replaces kernel timers
5. **Configuration API** replaces /sys filesystem

## Future Enhancements

### Short-term (Next Release)
1. **Enhanced Window Tracking**:
   - Implement actual row/column coordinate tracking
   - Filter announcements based on window boundaries
   - Persist windows per application

2. **Improved Highlight Detection**:
   - More robust ANSI code parsing
   - Support for 256-color and RGB codes
   - Background color change detection
   - Visual attribute tracking (bold, italic)

3. **Better Window Reading**:
   - Full implementation of window content extraction
   - Line-by-line window reading
   - Window content copying

### Long-term (Future Versions)
1. **Application Profiles**:
   - Automatic window definitions for known apps (vim, htop, tmux)
   - Per-application tracking mode defaults
   - Custom gesture bindings per application

2. **Advanced Color Detection**:
   - 256-color palette support
   - True color (24-bit RGB) support
   - Color scheme awareness
   - Configurable color names

3. **Extended Windowing**:
   - Multiple window definitions
   - Window templates/presets
   - Automatic window adjustment for layout changes
   - Window-based silence/monitor modes (like Speakup)

4. **Position Coordinates**:
   - Announce row/column position (NVDA+Alt+P)
   - Jump to specific coordinates
   - Position-based navigation

## Testing Recommendations

### Manual Testing Scenarios

1. **Mode Cycling**:
   - Press NVDA+Alt+Asterisk repeatedly
   - Verify mode announcements
   - Test cursor tracking behavior in each mode

2. **Highlight Tracking**:
   - Run `dialog` or `whiptail` menu applications
   - Navigate menu items
   - Verify highlighted items are announced
   - Test with vim visual mode

3. **Screen Windowing**:
   - Open tmux with status bar
   - Set window to exclude status bar
   - Verify cursor tracking respects window
   - Test window reading

4. **Attribute Reading**:
   - Display colored text: `echo -e "\033[31mRed\033[0m \033[32mGreen\033[0m"`
   - Position cursor on colored text
   - Press NVDA+Alt+Shift+A
   - Verify color announcement

5. **ANSI Code Parsing**:
   - Test various color combinations
   - Verify bold, underline, inverse handling
   - Test compound codes (e.g., `\033[1;31m` for bold red)

### Automated Testing (Future)

Consider adding unit tests for:
- ANSI code parsing (`_extractHighlightedText`, `_parseColorCode`)
- Mode cycling logic
- Window boundary validation
- Configuration persistence

## NVDA API Usage

### Key APIs Used

**TextInfo API**:
- `obj.makeTextInfo(position)` - Create text position
- `info.expand(unit)` - Expand to line/character
- `info.bookmark` - Position identifier for comparison
- `info.text` - Get text content

**Review Cursor**:
- `api.getReviewPosition()` - Get current review position
- `api.setReviewPosition(info)` - Set review cursor
- `api.setNavigatorObject(obj)` - Bind to terminal

**Configuration**:
- `config.conf["TDSR"]` - Settings dictionary
- `config.conf.spec["TDSR"]` - Configuration schema

**UI**:
- `ui.message()` - Announce to user
- `wx.CallLater()` - Debounce timer

**Script Decorator**:
- `@script()` - Register gesture handlers
- `gesture` parameter - Define keyboard shortcuts

## Code Quality

### Best Practices Followed

1. **Error Handling**: All cursor tracking wrapped in try/except
2. **Fallback Behavior**: Modes fall back to standard tracking on error
3. **Documentation**: Comprehensive docstrings for all methods
4. **Internationalization**: All user-facing strings use `_()` translation
5. **Configuration**: All features configurable, with sensible defaults
6. **Backwards Compatibility**: New features don't break existing functionality
7. **NVDA Integration**: Uses built-in NVDA APIs instead of reinventing

### Code Organization

```
tdsr.py
├── Constants (CT_OFF, CT_STANDARD, CT_HIGHLIGHT, CT_WINDOW)
├── Configuration (confspec with new settings)
├── GlobalPlugin class
│   ├── __init__ (state initialization)
│   ├── Event handlers (event_caret)
│   ├── Cursor tracking (mode dispatcher + handlers)
│   ├── Helper methods (ANSI parsing, color mapping)
│   └── Script methods (gestures + commands)
└── TDSRSettingsPanel class
    ├── makeSettings (UI controls)
    └── onSave (persist configuration)
```

## Performance Considerations

1. **Debouncing**: Cursor delay prevents announcement spam
2. **Position Caching**: `_lastCaretPosition` prevents redundant announcements
3. **Lazy Loading**: ANSI parsing only when needed
4. **Efficient Regex**: Pre-compiled patterns for performance
5. **Fallback**: Minimal overhead when features not in use

## Documentation Updates

### README.md
- Added cursor tracking modes to features list
- Documented all new gestures
- Updated configuration section
- Added Speakup attribution

### User Guide (Future)
Should include:
- Detailed explanation of each tracking mode
- Use cases for each mode
- Step-by-step window setup tutorial
- Color code reference table
- Troubleshooting common issues

## Acknowledgments

This implementation was inspired by:
- **Speakup** (https://github.com/linux-speakup/speakup) - Linux kernel screen reader
- **TDSR** by Tyler Spivey - Original terminal data structure reader
- **NVDA** (https://www.nvaccess.org/) - NonVisual Desktop Access screen reader

Special thanks to the Speakup developers for creating a sophisticated terminal accessibility model that has guided 25+ years of screen reader development.

## References

- [Speakup GitHub Repository](https://github.com/linux-speakup/speakup)
- [NVDA Developer Guide](https://download.nvaccess.org/documentation/developerGuide.html)
- [ANSI Escape Codes](https://en.wikipedia.org/wiki/ANSI_escape_code)
- [SPEAKUP_FEATURE_ANALYSIS.md](./SPEAKUP_FEATURE_ANALYSIS.md) - Original feature analysis

## Conclusion

This implementation successfully adapts Speakup's sophisticated cursor tracking model to the Windows/NVDA environment. While simplified compared to Speakup's kernel-level implementation, it provides users with powerful tools for navigating complex terminal applications and understanding color-coded information.

The modular architecture allows for future enhancements while maintaining backwards compatibility and following NVDA add-on best practices.
