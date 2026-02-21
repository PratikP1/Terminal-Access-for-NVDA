# Phase 2 Core Enhancements - Specifications and Requirements

## Overview

This document specifies the requirements for implementing Phase 2 features from the Speakup Feature Analysis. These core enhancements provide significant improvements to terminal accessibility, particularly for developers and power users.

**Target Version**: 1.0.12
**Implementation Date**: 2026-02-21
**Priority**: High (Phase 2 - Core Enhancements)

## Feature 1: Punctuation Level System

### Priority: ⭐⭐⭐⭐⭐ (Highest - Most Impactful)

### Description
Four levels of punctuation verbosity that control how many symbols are announced during reading, typing, and navigation. This replaces the current binary processSymbols setting with a sophisticated, context-appropriate system.

### User Story
As a developer working in terminals, I want granular control over punctuation announcement, so that I can hear critical symbols in code and commands without being overwhelmed by excessive verbosity in prose or documentation.

### Requirements

#### Functional Requirements
- **FR1.1**: Implement 4 punctuation levels (0-3)
- **FR1.2**: Level 0 announces no punctuation
- **FR1.3**: Level 1 announces basic punctuation: .,?!;:
- **FR1.4**: Level 2 announces most punctuation: adds @#$%^&*()_+=[]{}\\|<>/
- **FR1.5**: Level 3 announces all punctuation (every symbol)
- **FR1.6**: Apply punctuation level to key echo
- **FR1.7**: Apply punctuation level to cursor tracking
- **FR1.8**: Apply punctuation level to character navigation
- **FR1.9**: Apply punctuation level to continuous reading
- **FR1.10**: Provide gestures to cycle through levels
- **FR1.11**: Announce current level when changing

#### Non-Functional Requirements
- **NFR1.1**: Level changes must be instantaneous
- **NFR1.2**: Must not impact performance during typing or navigation
- **NFR1.3**: Must integrate seamlessly with existing features
- **NFR1.4**: Must be backward compatible (migrate old processSymbols setting)

#### Gesture Bindings
- **Decrease level**: `NVDA+Alt+[` (left bracket)
- **Increase level**: `NVDA+Alt+]` (right bracket)

#### Punctuation Sets

```python
PUNCTUATION_SETS = {
    0: set(),  # No punctuation
    1: set('.,?!;:'),  # Basic punctuation
    2: set('.,?!;:@#$%^&*()_+=[]{}\\|<>/'),  # Most punctuation
    3: None  # All punctuation (process everything)
}
```

#### Technical Implementation

```python
# Configuration update
"punctuationLevel": "integer(default=2, min=0, max=3)"

# Helper method
def _shouldProcessSymbol(self, char):
    """Determine if a symbol should be processed based on punctuation level."""
    level = config.conf["TDSR"]["punctuationLevel"]

    if level == 3:
        return True  # Process all
    if level == 0:
        return False  # Process none

    punctSet = PUNCTUATION_SETS[level]
    return char in punctSet

# Apply in multiple locations:
# - Key echo (onKeyPress)
# - Cursor tracking (_announceCursorPosition)
# - Character navigation (script_readCurrentChar, etc.)
# - Continuous reading (script_sayAll)
```

#### Migration Strategy
```python
# On first load, migrate old processSymbols to punctuation level
if "processSymbols" in config.conf["TDSR"]:
    oldValue = config.conf["TDSR"]["processSymbols"]
    # True -> Level 2 (most punctuation)
    # False -> Level 0 (no punctuation)
    config.conf["TDSR"]["punctuationLevel"] = 2 if oldValue else 0
```

#### Test Cases
- **TC1.1**: Level 0 - no symbols announced during typing
- **TC1.2**: Level 1 - basic punctuation announced (period, comma, etc.)
- **TC1.3**: Level 2 - most punctuation announced (including @, #, $, etc.)
- **TC1.4**: Level 3 - all symbols announced
- **TC1.5**: Cycling with NVDA+Alt+[ decreases level
- **TC1.6**: Cycling with NVDA+Alt+] increases level
- **TC1.7**: Level 3 -> ] -> wraps to Level 0
- **TC1.8**: Level 0 -> [ -> wraps to Level 3
- **TC1.9**: Level applies to key echo
- **TC1.10**: Level applies to character navigation
- **TC1.11**: Level applies to cursor tracking
- **TC1.12**: Level persists across NVDA restarts

#### Success Criteria
- Users can control punctuation verbosity with 4 distinct levels
- Levels apply consistently across all features
- Settings persist and can be changed on-the-fly
- Performance is not impacted

---

## Feature 2: Read From/To Position

### Priority: ⭐⭐⭐ (High)

### Description
Directional reading commands that read from the current cursor position to a screen edge (left, right, top, bottom). Complements the edge navigation from Phase 1.

### User Story
As a terminal user, I want to quickly read from my current position to a screen edge, so that I can scan portions of content without navigating line-by-line or character-by-character.

### Requirements

#### Functional Requirements
- **FR2.1**: Read from cursor to left edge of line
- **FR2.2**: Read from cursor to right edge of line
- **FR2.3**: Read from cursor to top of buffer
- **FR2.4**: Read from cursor to bottom of buffer
- **FR2.5**: Respect current punctuation level during reading
- **FR2.6**: Provide clear audio feedback when regions are empty

#### Non-Functional Requirements
- **NFR2.1**: Reading must be smooth without pauses
- **NFR2.2**: Must work with all terminal types
- **NFR2.3**: Must handle empty regions gracefully

#### Gesture Bindings
- **Read to left**: `NVDA+Alt+Shift+Left`
- **Read to right**: `NVDA+Alt+Shift+Right`
- **Read to top**: `NVDA+Alt+Shift+Up`
- **Read to bottom**: `NVDA+Alt+Shift+Down`

#### Technical Implementation

```python
def script_readToLeft(self, gesture):
    """Read from cursor position to beginning of line."""
    # Get current position
    # Expand to line start
    # Collapse to create range from start to cursor
    # Read the text

def script_readToRight(self, gesture):
    """Read from cursor position to end of line."""
    # Get current position
    # Expand to line end
    # Create range from cursor to end
    # Read the text

def script_readToTop(self, gesture):
    """Read from cursor position to top of buffer."""
    # Get current position
    # Get buffer start position
    # Create range from start to cursor
    # Read the text

def script_readToBottom(self, gesture):
    """Read from cursor position to bottom of buffer."""
    # Get current position
    # Get buffer end position
    # Create range from cursor to end
    # Read the text
```

#### Test Cases
- **TC2.1**: Read to left from middle of line
- **TC2.2**: Read to left from start of line (empty, announces "Nothing")
- **TC2.3**: Read to right from middle of line
- **TC2.4**: Read to right from end of line (empty, announces "Nothing")
- **TC2.5**: Read to top from middle of buffer
- **TC2.6**: Read to top from buffer start (empty)
- **TC2.7**: Read to bottom from middle of buffer
- **TC2.8**: Read to bottom from buffer end (empty)
- **TC2.9**: Punctuation level is respected

#### Success Criteria
- All four directional reading commands work reliably
- Text is read smoothly with proper speech
- Empty regions are handled gracefully
- Commands work in all supported terminals

---

## Feature 3: Enhanced Selection System

### Priority: ⭐⭐⭐ (High)

### Description
Enhanced mark-based selection system that supports arbitrary start/end positions and rectangular (column-based) selections, not just full lines.

### User Story
As a terminal user working with tables and structured data, I want to select arbitrary rectangular regions and specific text ranges, so that I can copy columns from tables or specific portions of text without being limited to full lines.

### Requirements

#### Functional Requirements
- **FR3.1**: Mark arbitrary start position (not just line start)
- **FR3.2**: Mark arbitrary end position (not just line end)
- **FR3.3**: Support linear selection (start to end, continuous)
- **FR3.4**: Support rectangular selection (column range across lines)
- **FR3.5**: Announce selection bounds when marking
- **FR3.6**: Copy selected region to clipboard
- **FR3.7**: Provide audio feedback for marking and copying
- **FR3.8**: Clear selection marks

#### Non-Functional Requirements
- **NFR3.1**: Selection must be accurate for all text ranges
- **NFR3.2**: Rectangular selection must handle varying line lengths
- **NFR3.3**: Must work with existing copy mode
- **NFR3.4**: Must not break backward compatibility

#### Gesture Bindings
- **Mark/toggle position**: `NVDA+Alt+R` (existing selection gesture, enhanced)
- **Copy linear selection**: `NVDA+Alt+C` (when marks are set)
- **Copy rectangular selection**: `NVDA+Alt+Shift+C` (when marks are set)
- **Clear marks**: `NVDA+Alt+X`

#### Selection Types

**Linear Selection**: Continuous text from start to end position
```
Start: Row 5, Col 10
End: Row 8, Col 15
Result: All text from start through end (crosses lines)
```

**Rectangular Selection**: Column range across multiple lines
```
Start: Row 5, Col 10
End: Row 8, Col 20
Result: Columns 10-20 from rows 5-8 (table column)
```

#### Technical Implementation

```python
# State variables
self._markStart = None  # TextInfo bookmark for start
self._markEnd = None    # TextInfo bookmark for end
self._selectionMode = "linear"  # "linear" or "rectangular"

def script_toggleMark(self, gesture):
    """Toggle marking start/end positions."""
    if self._markStart is None:
        # Set start mark
        self._markStart = reviewPos.bookmark
        ui.message(_("Mark start set"))
    elif self._markEnd is None:
        # Set end mark
        self._markEnd = reviewPos.bookmark
        ui.message(_("Mark end set"))
    else:
        # Clear marks
        self._clearMarks()

def script_copyLinearSelection(self, gesture):
    """Copy text from start to end mark (continuous)."""
    if not self._markStart or not self._markEnd:
        ui.message(_("Set start and end marks first"))
        return

    # Get text from start to end
    startInfo = terminal.makeTextInfo(self._markStart)
    endInfo = terminal.makeTextInfo(self._markEnd)
    # ... copy logic

def script_copyRectangularSelection(self, gesture):
    """Copy rectangular region (columns across rows)."""
    if not self._markStart or not self._markEnd:
        ui.message(_("Set start and end marks first"))
        return

    # Calculate row/column bounds
    # Extract text from each line in column range
    # Join with newlines
    # Copy to clipboard
```

#### Test Cases
- **TC3.1**: Mark start position
- **TC3.2**: Mark end position
- **TC3.3**: Copy linear selection (continuous text)
- **TC3.4**: Copy rectangular selection (table column)
- **TC3.5**: Clear marks and start over
- **TC3.6**: Marks on same line
- **TC3.7**: Marks across multiple lines
- **TC3.8**: Rectangular selection with varying line lengths
- **TC3.9**: Copy announces success message
- **TC3.10**: Attempting copy without marks gives helpful message

#### Success Criteria
- Users can mark arbitrary positions for selection
- Linear selections work for continuous text
- Rectangular selections work for table columns
- All selections copy correctly to clipboard
- Clear, helpful audio feedback throughout

---

## Implementation Order

Based on impact and complexity, implement in this order:

1. **Punctuation Level System** (Days 1-3)
   - Highest impact for developers
   - Replaces existing processSymbols
   - Affects multiple features
   - Must be done first as other features depend on it

2. **Read From/To Position** (Days 4-5)
   - Complements Phase 1 navigation
   - Moderate complexity
   - Independent of other features
   - High utility for scanning content

3. **Enhanced Selection System** (Days 6-8)
   - Builds on existing copy mode
   - Most complex of the three
   - High value for structured data
   - Can be refined iteratively

## Version and Release Planning

**Target Version**: 1.0.12
**Release Type**: Major Feature Enhancement

### Version Update Requirements
- Update `buildVars.py` - `addon_info['addon_version'] = "1.0.12"`
- Update `addon/manifest.ini` - `version = 1.0.12`
- Add comprehensive entry to `CHANGELOG.md` with all Phase 2 features

### Changelog Entry Template
```markdown
## [1.0.12] - 2026-02-21

### Added - Phase 2 Core Enhancements
- **Punctuation Level System** - Four levels of punctuation verbosity (0-3)
  - Level 0: No punctuation
  - Level 1: Basic punctuation (.,?!;:)
  - Level 2: Most punctuation (adds @#$%^&*()_+=[]{}\\|<>/)
  - Level 3: All punctuation
  - NVDA+Alt+[/]: Decrease/increase punctuation level
  - Applies to key echo, cursor tracking, character navigation, and continuous reading
  - Replaces binary processSymbols with granular control
- **Read From/To Position** - Directional reading commands
  - NVDA+Alt+Shift+Left: Read from cursor to left edge
  - NVDA+Alt+Shift+Right: Read from cursor to right edge
  - NVDA+Alt+Shift+Up: Read from cursor to top of buffer
  - NVDA+Alt+Shift+Down: Read from cursor to bottom of buffer
  - Complements Phase 1 edge navigation features
- **Enhanced Selection System** - Flexible mark-based text selection
  - Support for arbitrary start/end positions
  - Linear selection (continuous text from start to end)
  - Rectangular selection (column-based for tables)
  - NVDA+Alt+R: Toggle mark positions
  - NVDA+Alt+C: Copy linear selection
  - NVDA+Alt+Shift+C: Copy rectangular selection
  - NVDA+Alt+X: Clear marks

### Changed
- Replaced boolean processSymbols with integer punctuationLevel (0-3)
- Enhanced NVDA+Alt+R to support arbitrary position marking
- Improved copy mode with rectangular selection support
- Settings panel updated with punctuation level control

### Migration
- Existing processSymbols setting automatically migrated to punctuationLevel
- True -> Level 2 (most punctuation), False -> Level 0 (no punctuation)

### Technical
- Added PUNCTUATION_SETS dictionary for level definitions
- Implemented _shouldProcessSymbol() helper method
- Enhanced selection system with linear/rectangular modes
- Added mark start/end bookmark tracking

### Credits
- Phase 2 features inspired by [Speakup](https://github.com/linux-speakup/speakup) screen reader
```

## Testing Strategy

### Manual Testing
Each feature must be tested with:
1. Windows Terminal
2. PowerShell
3. Command Prompt (cmd.exe)

### Test Scenarios per Feature

**Punctuation Level System:**
1. Test each level (0-3) with various symbol types
2. Test level cycling in both directions
3. Test level persistence across restarts
4. Test migration from old processSymbols setting
5. Test application to key echo, cursor tracking, navigation

**Read From/To Position:**
1. Test all four directions (left, right, up, down)
2. Test from various cursor positions
3. Test with empty regions
4. Test with very long lines/buffers
5. Test punctuation level integration

**Enhanced Selection:**
1. Test linear selection (same line, multiple lines)
2. Test rectangular selection (tables, columns)
3. Test mark clearing
4. Test with varying line lengths
5. Test clipboard integration

### Validation Checklist
- [ ] All gestures properly bound
- [ ] No conflicts with existing gestures
- [ ] Features work in all supported terminals
- [ ] Speech output clear and appropriate
- [ ] No crashes or errors in NVDA log
- [ ] Settings persist correctly
- [ ] Migration from old settings works
- [ ] Documentation updated
- [ ] Backward compatibility maintained

## Documentation Updates

### Files to Update
1. **README.md** - Add Phase 2 features to feature list
2. **QUICKSTART.md** - Add new gestures and usage examples
3. **CHANGELOG.md** - Document all changes
4. **ROADMAP.md** - Mark Phase 2 as completed
5. **TESTING.md** - Add test cases for new features

### User-Facing Documentation
All features must include:
- Clear gesture documentation
- Usage examples for common scenarios
- Expected behavior description
- Migration notes (for punctuation levels)

## Success Metrics

### Completion Criteria
- All 3 features fully implemented
- All test cases passing
- No regressions in existing features
- Documentation updated
- Version bumped to 1.0.12
- Changelog comprehensive

### Quality Criteria
- No errors in NVDA log during normal operation
- Smooth, responsive user experience
- Clear, helpful speech output
- Consistent with existing TDSR patterns
- Improved workflow for developers and power users

## Dependencies and Constraints

### NVDA Version Compatibility
- Minimum NVDA version: 2019.3
- Test with latest NVDA stable release

### Python Version
- Python 3.7+ (NVDA's embedded Python)

### External Dependencies
- None (all features use NVDA's built-in APIs)

### Known Limitations
- Rectangular selection may have reduced accuracy in legacy console mode
- Punctuation level applies globally (not per-application)
- Selection marks are temporary (cleared on terminal switch)

## Risk Assessment

### Low Risk
- Read From/To Position (extends existing navigation)
- Punctuation level UI (settings panel update)

### Medium Risk
- Punctuation level implementation (affects multiple features)
- Enhanced selection (modifies existing copy mode)

### Mitigation Strategies
- Extensive testing across terminal types
- Backward compatibility for processSymbols migration
- Graceful degradation for unsupported scenarios
- Clear user feedback and error messages
- Incremental implementation with frequent testing

## Future Enhancements (Out of Scope for Phase 2)

The following are NOT included in Phase 2:

- Per-application punctuation levels (Phase 4)
- Persistent selection marks across sessions (Phase 4)
- Multiple independent mark pairs (future consideration)
- Punctuation customization per level (future consideration)

---

## References

- **Speakup Feature Analysis**: `SPEAKUP_FEATURE_ANALYSIS.md`
- **Phase 1 Specs**: `PHASE1_SPECS.md`
- **NVDA API Documentation**: https://www.nvaccess.org/files/nvda/documentation/developerGuide.html
- **TextInfo API**: Used for all text navigation and selection
- **Configuration System**: NVDA's configspec and config.conf

---

**Document Status**: Final
**Last Updated**: 2026-02-21
**Author**: TDSR Development Team
