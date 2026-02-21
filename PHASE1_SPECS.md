# Phase 1 Quick Wins - Specifications and Requirements

## Overview

This document specifies the requirements for implementing Phase 1 features from the Speakup Feature Analysis. These features provide high value with relatively low implementation complexity, establishing a foundation for enhanced terminal accessibility.

**Target Version**: 1.0.11
**Implementation Date**: 2026-02-21
**Priority**: High (Phase 1 - Quick Wins)

## Feature 1: Continuous Reading (Say All)

### Priority: ⭐⭐⭐⭐⭐ (Highest)

### Description
Read continuously from the current review cursor position to the end of the terminal buffer, similar to NVDA's standard "Say All" functionality but optimized for terminal content.

### User Story
As a terminal user, I want to read long output (log files, man pages, command output) continuously without manually navigating line-by-line, so that I can efficiently consume large amounts of terminal content.

### Requirements

#### Functional Requirements
- **FR1.1**: Implement continuous reading starting from current review cursor position
- **FR1.2**: Read to the end of the terminal buffer
- **FR1.3**: Allow interruption with any key press
- **FR1.4**: Respect current processSymbols setting during reading
- **FR1.5**: Provide audio feedback when reading begins and ends
- **FR1.6**: Handle empty buffers gracefully

#### Non-Functional Requirements
- **NFR1.1**: Reading must be smooth without noticeable pauses
- **NFR1.2**: Interruption must be immediate (< 100ms response time)
- **NFR1.3**: Must work with all supported terminal applications
- **NFR1.4**: Must not interfere with other NVDA speech operations

#### Gesture Binding
- **Primary**: `NVDA+Alt+A` (for "All")
- **Conflict**: Previous gesture for attribute reading moved to `NVDA+Alt+Shift+A`

#### Technical Implementation
```python
def script_sayAll(self, gesture):
    """Read continuously from current position to end of buffer."""
    # 1. Get current review position
    # 2. Get text from position to end of buffer
    # 3. Use NVDA's speech.speakText() or sayAll mechanism
    # 4. Set up interruption handler
```

#### Test Cases
- **TC1.1**: Continuous reading from beginning of buffer
- **TC1.2**: Continuous reading from middle of buffer
- **TC1.3**: Interruption with Escape key
- **TC1.4**: Interruption with any other key
- **TC1.5**: Reading empty buffer (no crash, appropriate message)
- **TC1.6**: Reading single line buffer
- **TC1.7**: ProcessSymbols setting is respected

#### Success Criteria
- Users can read long terminal output without manual navigation
- Reading can be interrupted immediately
- No crashes or freezes during continuous reading

---

## Feature 2: Screen Edge Navigation

### Priority: ⭐⭐⭐ (High)

### Description
Quick navigation commands to jump to screen/line boundaries, enabling faster movement in large terminal buffers.

### User Story
As a terminal user, I want to quickly jump to line boundaries and screen edges, so that I can efficiently navigate wide output and large buffers without repetitive key presses.

### Requirements

#### Functional Requirements
- **FR2.1**: Jump to first character of current line
- **FR2.2**: Jump to last character of current line
- **FR2.3**: Jump to top of visible screen/buffer
- **FR2.4**: Jump to bottom of visible screen/buffer
- **FR2.5**: Announce character at destination after navigation
- **FR2.6**: Move review cursor, not system caret

#### Non-Functional Requirements
- **NFR2.1**: Navigation must be instantaneous (< 50ms)
- **NFR2.2**: Must work consistently across all terminal types
- **NFR2.3**: Must handle edge cases (empty lines, single-character lines)

#### Gesture Bindings
- **First character of line**: `NVDA+Alt+Home`
- **Last character of line**: `NVDA+Alt+End`
- **Top of screen**: `NVDA+Alt+PageUp`
- **Bottom of screen**: `NVDA+Alt+PageDown`

#### Technical Implementation
```python
def script_reviewHome(self, gesture):
    """Move to first character of current line."""
    # Use textInfos.move() with UNIT_LINE and UNIT_CHARACTER

def script_reviewEnd(self, gesture):
    """Move to last character of current line."""
    # Use textInfos.move() to end of line

def script_reviewTop(self, gesture):
    """Move to top of screen/buffer."""
    # Use textInfos.POSITION_FIRST

def script_reviewBottom(self, gesture):
    """Move to bottom of screen/buffer."""
    # Use textInfos.POSITION_LAST
```

#### Test Cases
- **TC2.1**: Jump to start of line from middle
- **TC2.2**: Jump to end of line from middle
- **TC2.3**: Jump to top of buffer from bottom
- **TC2.4**: Jump to bottom of buffer from top
- **TC2.5**: Navigation on empty line
- **TC2.6**: Navigation on single-character line
- **TC2.7**: Navigation on very long line (> 200 chars)
- **TC2.8**: Character announcement after each navigation

#### Success Criteria
- All four edge navigation commands work reliably
- Character at destination is announced
- Navigation is fast and responsive

---

## Feature 3: Line Indentation Detection

### Priority: ⭐⭐⭐⭐ (High)

### Description
Announce the indentation level (spaces/tabs) of the current line when double-pressing the "read current line" gesture.

### User Story
As a developer reading Python or YAML code in a terminal, I want to know the indentation level of each line, so that I can understand code structure and hierarchy without visual inspection.

### Requirements

#### Functional Requirements
- **FR3.1**: Detect leading whitespace on current line
- **FR3.2**: Distinguish between spaces and tabs
- **FR3.3**: Count indentation level accurately
- **FR3.4**: Announce indentation on double-press of current line gesture
- **FR3.5**: Announce "no indentation" for lines starting at column 1
- **FR3.6**: Handle mixed spaces/tabs gracefully

#### Non-Functional Requirements
- **NFR3.1**: Detection must be accurate for all indentation styles
- **NFR3.2**: Announcement must be clear and concise
- **NFR3.3**: Must not interfere with single-press behavior

#### Gesture Binding
- **Trigger**: Double-press `NVDA+Alt+I` (existing "read current line" gesture)
- **Behavior**:
  - Single press: Read line text
  - Double press: Announce indentation level

#### Technical Implementation
```python
def script_readCurrentLine(self, gesture):
    """Read current line. On double-press, announce indentation."""
    if scriptHandler.getLastScriptRepeatCount() == 1:
        # Double press - announce indentation
        self._announceIndentation()
    else:
        # Single press - read line normally
        # ... existing code ...

def _announceIndentation(self):
    """Count and announce leading whitespace."""
    # 1. Get current line text
    # 2. Count leading spaces/tabs
    # 3. Announce result
```

#### Indentation Reporting Format
- `"4 spaces"` - 4 spaces
- `"2 tabs"` - 2 tabs
- `"1 tab, 2 spaces"` - mixed indentation
- `"No indentation"` - line starts at column 1
- `"Empty line"` - blank line

#### Test Cases
- **TC3.1**: Line with 4 spaces
- **TC3.2**: Line with 2 tabs
- **TC3.3**: Line with mixed tabs and spaces
- **TC3.4**: Line with no indentation
- **TC3.5**: Empty line
- **TC3.6**: Line with only whitespace
- **TC3.7**: Double-press detection works correctly
- **TC3.8**: Single press still reads line normally

#### Success Criteria
- Indentation is accurately detected and announced
- Works for spaces, tabs, and mixed indentation
- Does not interfere with normal line reading

---

## Feature 4: Position Announcement

### Priority: ⭐⭐ (Medium)

### Description
Announce the current row and column coordinates of the review cursor within the terminal.

### User Story
As a terminal user, I want to know my exact position in row/column coordinates, so that I can understand table alignment, verify cursor location, and debug positioning issues.

### Requirements

#### Functional Requirements
- **FR4.1**: Announce current row number (line number)
- **FR4.2**: Announce current column number (character position in line)
- **FR4.3**: Use 1-based indexing for user-friendly reporting
- **FR4.4**: Handle edge cases (first position, last position)

#### Non-Functional Requirements
- **NFR4.1**: Position calculation must be accurate
- **NFR4.2**: Announcement must be clear and concise
- **NFR4.3**: Must work in all terminal applications

#### Gesture Binding
- **Primary**: `NVDA+Alt+P` (for "Position")

#### Technical Implementation
```python
def script_announcePosition(self, gesture):
    """Announce current row and column position."""
    # 1. Get review position
    # 2. Calculate line number (row)
    # 3. Calculate character position (column)
    # 4. Announce: "Row X, column Y"
```

#### Announcement Format
- `"Row 15, column 42"` - Standard announcement
- `"Row 1, column 1"` - First position
- `"Position unavailable"` - Error fallback

#### Test Cases
- **TC4.1**: Position at start of buffer (row 1, col 1)
- **TC4.2**: Position in middle of buffer
- **TC4.3**: Position at end of buffer
- **TC4.4**: Position on empty line
- **TC4.5**: Position on very long line
- **TC4.6**: Accuracy verification across multiple positions

#### Success Criteria
- Position is accurately calculated and announced
- Works reliably across all terminal types
- Announcement is clear and user-friendly

---

## Feature 5: Character Code Announcement

### Priority: ⭐⭐ (Medium)

### Description
Announce the ASCII/Unicode value of the character at the review cursor when triple-pressing the character reading gesture.

### User Story
As a terminal user, I want to know the numeric code of special characters, so that I can identify hidden control characters, debug encoding issues, and understand special symbols.

### Requirements

#### Functional Requirements
- **FR5.1**: Announce character code on triple-press
- **FR5.2**: Report decimal and hexadecimal values
- **FR5.3**: Include character name/representation
- **FR5.4**: Handle control characters appropriately
- **FR5.5**: Handle Unicode characters beyond ASCII

#### Non-Functional Requirements
- **NFR5.1**: Code calculation must be accurate
- **NFR5.2**: Announcement must be comprehensive but concise
- **NFR5.3**: Must work for all character types

#### Gesture Binding
- **Trigger**: Triple-press `NVDA+Alt+Comma`
- **Behavior**:
  - Single press: Read character
  - Double press: Read character phonetically
  - Triple press: Read character code

#### Technical Implementation
```python
def script_readCurrentChar(self, gesture):
    """Read character. Double-press: phonetic. Triple-press: code."""
    repeatCount = scriptHandler.getLastScriptRepeatCount()

    if repeatCount == 2:
        # Triple press - announce character code
        self._announceCharacterCode()
    elif repeatCount == 1:
        # Double press - phonetic (existing)
        # ... existing code ...
    else:
        # Single press - read character
        # ... existing code ...

def _announceCharacterCode(self):
    """Announce ASCII/Unicode code of current character."""
    # 1. Get character at cursor
    # 2. Get ord(char) - numeric code
    # 3. Format announcement with decimal and hex
```

#### Announcement Format
- `"Character 65, hex 41, A"` - Letter A
- `"Character 32, hex 20, space"` - Space character
- `"Character 10, hex 0A, line feed"` - Control character
- `"Character 8364, hex 20AC, Euro sign"` - Unicode symbol
- `"No character"` - Empty position

#### Test Cases
- **TC5.1**: Regular ASCII character (A-Z, a-z, 0-9)
- **TC5.2**: Space character
- **TC5.3**: Punctuation marks
- **TC5.4**: Control characters (tab, newline)
- **TC5.5**: Extended ASCII (128-255)
- **TC5.6**: Unicode characters (> 255)
- **TC5.7**: Triple-press detection works correctly
- **TC5.8**: Single and double press still work normally

#### Success Criteria
- Character codes are accurately calculated and announced
- Works for ASCII, extended ASCII, and Unicode
- Does not interfere with single/double press behavior

---

## Implementation Order

Based on value and complexity, implement in this order:

1. **Continuous Reading (Say All)** - Highest value, moderate complexity
2. **Line Indentation Detection** - High value, low complexity (quick win)
3. **Position Announcement** - Low complexity, good foundation
4. **Character Code Announcement** - Low complexity, extends existing feature
5. **Screen Edge Navigation** - Medium complexity, four separate commands

## Version and Release Planning

**Target Version**: 1.0.11
**Release Type**: Feature Enhancement

### Version Update Requirements
- Update `buildVars.py` - `addon_info['addon_version'] = "1.0.11"`
- Update `addon/manifest.ini` - `version = 1.0.11`
- Add entry to `CHANGELOG.md` with all Phase 1 features

### Changelog Entry Template
```markdown
## [1.0.11] - 2026-02-21

### Added
- **Continuous Reading (Say All)** - NVDA+Alt+A reads from cursor to end of buffer
- **Screen Edge Navigation** - Jump to line/screen boundaries (Home/End/PageUp/PageDown)
- **Line Indentation Detection** - Double-press NVDA+Alt+I announces indentation level
- **Position Announcement** - NVDA+Alt+P announces row and column coordinates
- **Character Code Announcement** - Triple-press NVDA+Alt+Comma announces character code

### Changed
- Attribute reading gesture moved from NVDA+Alt+A to NVDA+Alt+Shift+A
- Enhanced double-press and triple-press gesture handling

### Credits
- Features inspired by [Speakup](https://github.com/linux-speakup/speakup) screen reader
```

## Testing Strategy

### Manual Testing
Each feature must be tested with:
1. Windows Terminal
2. PowerShell
3. Command Prompt (cmd.exe)
4. Git Bash (if available)

### Test Scenarios
1. Basic functionality (happy path)
2. Edge cases (empty buffers, single lines, etc.)
3. Error conditions (graceful failure)
4. Gesture conflicts (verify no interference)
5. Integration with existing features

### Validation Checklist
- [ ] All gestures are properly bound
- [ ] No conflicts with existing NVDA or TDSR gestures
- [ ] Features work in all supported terminals
- [ ] Speech output is clear and appropriate
- [ ] No crashes or errors in NVDA log
- [ ] Settings are properly persisted
- [ ] Documentation is updated

## Documentation Updates

### Files to Update
1. **README.md** - Add new features to feature list
2. **QUICKSTART.md** - Add new gestures to quick reference
3. **TESTING.md** - Add test cases for new features
4. **CHANGELOG.md** - Document all changes
5. **ROADMAP.md** - Mark Phase 1 as completed

### User-Facing Documentation
All features must include:
- Clear gesture documentation
- Usage examples
- Expected behavior description
- Known limitations (if any)

## Success Metrics

### Completion Criteria
- All 5 features fully implemented
- All test cases passing
- No regressions in existing features
- Documentation updated
- Version bumped to 1.0.11
- Changelog updated

### Quality Criteria
- No errors in NVDA log during normal operation
- Smooth, responsive user experience
- Clear, helpful speech output
- Consistent with existing TDSR patterns

## Dependencies and Constraints

### NVDA Version Compatibility
- Minimum NVDA version: 2019.3
- Test with latest NVDA stable release

### Python Version
- Python 3.7+ (NVDA's embedded Python)

### External Dependencies
- None (all features use NVDA's built-in APIs)

### Known Limitations
- Terminal must be UIA-enabled for full functionality
- Some features may have reduced functionality in legacy console mode
- Continuous reading performance depends on buffer size

## Risk Assessment

### Low Risk
- Position announcement (simple calculation)
- Character code announcement (extends existing feature)
- Line indentation detection (simple text analysis)

### Medium Risk
- Continuous reading (complex speech control)
- Screen edge navigation (multiple new gestures)

### Mitigation Strategies
- Extensive testing in various terminal emulators
- Graceful error handling for all features
- Fallback behaviors for edge cases
- Clear error messages for users

## Future Enhancements (Out of Scope)

The following are NOT included in Phase 1 but may be considered for future phases:

- Punctuation level system (Phase 2)
- Read from/to position (Phase 2)
- Enhanced selection system (Phase 2)
- Application-specific profiles (Phase 4)

---

## References

- **Speakup Feature Analysis**: `SPEAKUP_FEATURE_ANALYSIS.md`
- **NVDA API Documentation**: https://www.nvaccess.org/files/nvda/documentation/developerGuide.html
- **TextInfo API**: Used for all text navigation and manipulation
- **Gesture System**: NVDA's script decorator and gesture binding

---

**Document Status**: Final
**Last Updated**: 2026-02-21
**Author**: TDSR Development Team
