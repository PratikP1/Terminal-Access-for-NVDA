# Speakup Feature Analysis and TDSR Enhancement Plan

## Executive Summary

This document provides a comprehensive analysis of the Speakup screen reader for Linux terminals and identifies valuable features that can be adapted for TDSR for NVDA to improve the Windows terminal experience.

**Key Finding**: While TDSR already implements core navigation features comparable to Speakup, there are 12 significant feature categories that would dramatically improve terminal accessibility in Windows.

## About Speakup

Speakup is a kernel-level screen reader for Linux that provides speech access at the console level. It has been in active development since 1997 and is now integrated into the Linux kernel. Repository: https://github.com/linux-speakup/speakup

**Key Characteristics**:
- Operates at kernel level (boot-time speech access)
- Supports multiple hardware and software synthesizers
- Extensive configuration via /sys filesystem
- Comprehensive internationalization support
- Designed specifically for text console/terminal usage

## Current Feature Parity

### Features TDSR Already Has (Comparable to Speakup)

| Feature | TDSR Implementation | Speakup Implementation |
|---------|---------------------|------------------------|
| Line Navigation | NVDA+Alt+U/I/O | Keypad 7/8/9 |
| Word Navigation | NVDA+Alt+J/K/L | Keypad 4/5/6 |
| Character Navigation | NVDA+Alt+M/Comma/Period | Keypad 1/2/3 |
| Phonetic Spelling | Double-press NVDA+Alt+Comma | Double-press Keypad 2 |
| Word Spelling | Double-press NVDA+Alt+K | Double-press Keypad 5 |
| Cursor Tracking | Configurable with delay | Multiple modes |
| Key Echo | Yes, with symbol processing | Yes |
| Symbol Processing | Yes, via processSymbols setting | Yes, with punctuation levels |
| Quiet Mode | NVDA+Alt+Q | Speakup+Keypad Enter |
| Copy Functionality | Copy mode (L=line, S=screen) | Cut & paste buffer with marks |
| Configurable Settings | NVDA Settings panel | /sys filesystem |

## Missing Features with High Value

### Tier 1: Critical Features (High Priority)

These features would have the most significant impact on terminal usability and should be implemented first.

#### 1. Punctuation Level Control ⭐⭐⭐⭐⭐

**What it is**: Four levels of punctuation verbosity that control how many symbols are announced.

**Speakup Implementation**:
- Level 0: No punctuation
- Level 1: Some punctuation (.,?!;:)
- Level 2: Most punctuation (adds @#$%^&*()_+=[]{}\\|<>/)
- Level 3: All punctuation (every symbol)
- Separate levels for typing vs. reading
- Configurable character sets per level

**Why TDSR needs this**:
- Current binary processSymbols is too limiting
- Developers need to hear punctuation in code/commands
- But don't want overwhelming verbosity in prose
- Essential for working with scripts, paths, and configuration files

**Implementation Complexity**: Moderate
- Replace boolean processSymbols with 4-level system
- Define punctuation sets for each level
- Add gestures to cycle levels (NVDA+Alt+[ and NVDA+Alt+])
- Apply to key echo, cursor tracking, and character navigation

**Example Usage**:
```bash
# Command: grep -r "error" /var/log/*.log
# Level 0: "grep dash r quote error quote slash var slash log asterisk dot log"
# Level 1: "grep dash r quote error quote slash var slash log asterisk period log"
# Level 2: Full punctuation
# Level 3: Every symbol explicitly named
```

#### 2. Screen Windowing System ⭐⭐⭐⭐⭐

**What it is**: Define rectangular regions on screen for selective monitoring or silencing.

**Speakup Implementation**:
- Set window boundaries (top-left to bottom-right)
- Read only window content
- Silence changes within window
- Monitor only window changes

**Why TDSR needs this**:
- Modern terminals have complex layouts (status bars, split panes, tmux/screen)
- Clock displays and status lines create noise
- Need to focus on specific output regions
- Essential for tools like htop, tmux, vim with splits

**Implementation Complexity**: Complex
- Track window boundaries (row/col coordinates)
- Filter cursor tracking to window region
- Add window-aware reading commands
- Persist window definitions per application

**Key Gestures**:
- NVDA+Alt+F2: Set window start/end
- NVDA+Alt+F3: Clear window
- NVDA+Alt+F4: Toggle window silence
- NVDA+Alt+Plus: Read window content

**Use Cases**:
- Silence status bar in tmux while monitoring main pane
- Focus on command output, ignore prompt area
- Monitor log region in split-screen terminal
- Ignore clock/date displays

#### 3. Multiple Cursor Tracking Modes ⭐⭐⭐⭐

**What it is**: Three distinct modes for how cursor movement is announced.

**Speakup Modes**:
1. **Standard**: Speaks characters/lines as cursor moves (current TDSR behavior)
2. **Highlight Tracking**: Tracks highlighted text in menus/selection lists
3. **Read Window**: Only announces changes within defined window

**Why TDSR needs this**:
- TUI (Text User Interface) applications like htop, vim, mc (Midnight Commander)
- Menu navigation in terminal applications
- Reduces verbosity in specific contexts
- Better experience with ncurses-based applications

**Implementation Complexity**: Moderate
- Add tracking mode state variable
- Implement highlight detection (inverse video/color changes)
- Integrate with window system
- Add gesture to cycle modes (NVDA+Alt+Asterisk)

**Tracking Mode Cycle**:
Standard → Highlight → Window → Off → Standard

#### 4. Continuous Reading (Say All) ⭐⭐⭐⭐⭐

**What it is**: Read continuously from current position to end of terminal buffer.

**Speakup Implementation**:
- Speakup+R: Read from cursor to end
- Can be interrupted with any key
- Respects punctuation level settings

**Why TDSR needs this**:
- Essential for reading long log files
- Reading documentation in terminal (man pages, --help output)
- Reviewing command output without manual navigation
- Currently must navigate line-by-line (tedious)

**Implementation Complexity**: Easy
- Leverage NVDA's existing sayAll functionality
- Start from review cursor position
- Read to end of terminal buffer
- Allow interruption

**Gesture**: NVDA+Alt+A (for "All")

#### 5. Line Indentation Detection ⭐⭐⭐⭐

**What it is**: Announce the indentation level (spaces/tabs) of current line.

**Speakup Implementation**:
- Double-press Keypad 8 (current line)
- Announces number of leading spaces/tabs

**Why TDSR needs this**:
- Critical for Python code (indentation-based syntax)
- Essential for YAML configuration files
- Helpful for any structured/hierarchical output
- Aids in understanding code structure when reviewing

**Implementation Complexity**: Easy
- Count leading whitespace on current line
- Announce "X spaces" or "X tabs"
- Add to existing double-press gesture for current line

**Gesture**: NVDA+Alt+I (twice) - already bound to read current line

**Example**:
```python
def foo():
    if bar:        # Double-press: "8 spaces"
        return     # Double-press: "12 spaces"
```

### Tier 2: Enhanced Navigation (Medium Priority)

These features improve navigation efficiency and should be implemented after Tier 1.

#### 6. Screen Edge Navigation ⭐⭐⭐

**What it is**: Jump directly to edges of screen or line.

**Speakup Commands**:
- First character of line
- Last character of line
- Top of screen
- Bottom of screen
- Left edge (column 1)
- Right edge (last column)

**Why TDSR needs this**:
- Faster navigation in large terminal buffers
- Quick access to line boundaries
- Essential for wide output (tables, logs with timestamps)

**Implementation Complexity**: Easy

**Proposed Gestures**:
- NVDA+Alt+Home: First character of line
- NVDA+Alt+End: Last character of line
- NVDA+Alt+PageUp: Top of screen/buffer
- NVDA+Alt+PageDown: Bottom of screen/buffer

#### 7. Read From/To Position ⭐⭐⭐

**What it is**: Read from cursor position to edge of screen.

**Speakup Commands**:
- Say from cursor to left edge
- Say from cursor to right edge
- Say from cursor to top
- Say from cursor to bottom

**Why TDSR needs this**:
- Quickly scan portions of terminal content
- Useful for reviewing partial lines or regions
- Complements edge navigation

**Implementation Complexity**: Moderate

**Proposed Gestures**:
- NVDA+Alt+Shift+Left: Read to left edge
- NVDA+Alt+Shift+Right: Read to right edge
- NVDA+Alt+Shift+Up: Read to top
- NVDA+Alt+Shift+Down: Read to bottom

#### 8. Attribute/Color Reading ⭐⭐⭐⭐

**What it is**: Announce text attributes (color, bold, underline) at cursor position.

**Speakup Implementation**:
- Speakup+Keypad Period: Announce attributes
- Announces foreground/background color, bold, blink, etc.

**Why TDSR needs this**:
- Syntax highlighting identification (red=error, yellow=warning)
- Distinguishing emphasized text
- Understanding terminal color schemes
- Accessibility for color-blind users

**Implementation Complexity**: Moderate-Complex
- Parse ANSI escape codes in terminal buffer
- Access Windows Terminal's rendering attributes
- Map color codes to names
- Announce formatting (bold, italic, underline)

**Proposed Gesture**: NVDA+Alt+A

**Example Output**:
- "Red text, bold"
- "Green background, white foreground"
- "Underlined"

#### 9. Enhanced Selection/Cut/Paste ⭐⭐⭐

**What it is**: More flexible mark-based text selection and copying.

**Speakup Features**:
- Mark start position
- Navigate to end position
- Cut/copy marked region (not just lines)
- Supports rectangular selections
- Persistent paste buffer

**Why TDSR needs this**:
- Current implementation only copies lines or entire screen
- Need column-based selections for tables
- Paste buffer across terminal sessions
- More flexible than current copy mode

**Implementation Complexity**: Moderate

**Enhancements to Current Copy Mode**:
- Support rectangular (column-based) selections
- Allow arbitrary start/end positions (not just lines)
- Multiple paste operations from same buffer
- Visual feedback for marked regions

### Tier 3: Nice to Have (Lower Priority)

These features provide incremental improvements and can be implemented later.

#### 10. Position Announcement ⭐⭐

**What it is**: Announce current cursor row and column coordinates.

**Speakup Implementation**:
- Keypad Period: "Row 15, column 42"

**Why it's useful**:
- Debugging terminal positioning issues
- Understanding table alignment
- Verifying cursor location

**Implementation Complexity**: Easy

**Proposed Gesture**: NVDA+Alt+P

#### 11. Character Code Announcement ⭐⭐

**What it is**: Announce ASCII/Unicode value of character at cursor.

**Speakup Implementation**:
- Speakup+Keypad Minus: "Character 65, hex 41, A"

**Why it's useful**:
- Identifying hidden control characters
- Debugging encoding issues
- Understanding special characters

**Implementation Complexity**: Easy

**Proposed Gesture**: NVDA+Alt+Comma (triple-press)
- Single: Read character
- Double: Read phonetically
- Triple: Read character code

#### 12. Application-Specific Profiles ⭐⭐⭐

**What it is**: Automatic configuration switching based on terminal application.

**Concept**:
- Detect running application (vim, htop, tmux, etc.)
- Load pre-defined settings for that application
- Pre-configured window definitions
- Application-specific gesture bindings

**Why it's useful**:
- Different apps have different needs (vim vs. PowerShell)
- Pre-configured windows for known TUI layouts
- Better out-of-box experience

**Implementation Complexity**: Complex
- Application detection
- Profile storage/management
- Profile switching logic
- Default profiles for common apps

## Features Not Applicable to Windows/NVDA

These Speakup features don't apply in Windows context:

1. **Hardware Synthesizer Support**: Windows uses software TTS exclusively
2. **Boot-Time Speech**: Windows has Narrator for boot access
3. **Kernel-Level Integration**: NVDA operates at application level
4. **/sys Filesystem Configuration**: Windows uses registry/config files
5. **TTY-Specific Features**: Windows terminal model is different
6. **Serial Port Communication**: Not relevant for modern Windows usage

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 weeks)
Implement features with high value and low complexity:

1. **Line Indentation Detection** (1 day)
   - Extend existing double-press line gesture
   - Count leading whitespace

2. **Continuous Reading / Say All** (2-3 days)
   - Leverage NVDA's sayAll API
   - Add interrupt handling

3. **Position Announcement** (1 day)
   - Read cursor coordinates from terminal

4. **Character Code Announcement** (1 day)
   - Extend triple-press character gesture

5. **Screen Edge Navigation** (2-3 days)
   - Add Home/End/PageUp/PageDown navigation

### Phase 2: Core Enhancements (3-4 weeks)
Implement high-impact features:

1. **Punctuation Level System** (1 week)
   - Replace binary processSymbols with 4-level system
   - Define character sets for each level
   - Add cycling gestures
   - Update settings UI

2. **Read From/To Position** (3-4 days)
   - Implement directional reading commands
   - Add Shift+Arrow combinations

3. **Enhanced Selection System** (1 week)
   - Support arbitrary mark positions
   - Implement rectangular selections
   - Improve copy mode UX

### Phase 3: Advanced Features (4-6 weeks)
Implement complex, high-value features:

1. **Screen Windowing System** (2-3 weeks)
   - Window boundary tracking
   - Window-aware reading
   - Silence/monitor modes
   - Persistence per application

2. **Multiple Cursor Tracking Modes** (1-2 weeks)
   - Highlight detection
   - Window-based tracking
   - Mode cycling
   - Integration with window system

3. **Attribute/Color Reading** (1-2 weeks)
   - ANSI escape code parsing
   - Windows Terminal attribute access
   - Color name mapping
   - Format announcement

### Phase 4: Polish & Advanced (4-8 weeks)
Final enhancements and refinements:

1. **Application-Specific Profiles** (3-4 weeks)
   - Application detection
   - Profile system architecture
   - Default profiles for common apps
   - Profile UI/management

2. **Documentation Updates** (1 week)
   - Update user guide with all new features
   - Create feature comparison table
   - Add usage examples and best practices

3. **Testing & Refinement** (2-3 weeks)
   - Comprehensive testing of all new features
   - Performance optimization
   - Bug fixes
   - User feedback integration

## Technical Considerations

### NVDA API Compatibility
- All features must work with NVDA 2019.3+
- Use NVDA's review cursor API consistently
- Respect NVDA's global speech settings
- Integrate with NVDA's settings system

### Windows Terminal Compatibility
- Test with Windows Terminal, PowerShell, cmd.exe
- Handle various terminal emulators (ConPTY, legacy console)
- Parse Windows Terminal's rendering pipeline
- Support Windows Terminal's pane system

### Performance
- Window system must not impact performance
- Efficient attribute/color detection
- Minimal overhead for tracking modes
- Optimize frequent operations (cursor tracking)

### Configuration
- Extend existing TDSR settings panel
- Add sub-categories for complex features (windowing, punctuation)
- Export/import settings
- Sensible defaults for all features

### Backward Compatibility
- All new features optional/configurable
- Existing gestures unchanged
- Graceful degradation for older terminals
- Migration path for existing users

## Gesture Mapping Summary

### New Gestures Required

| Gesture | Feature |
|---------|---------|
| NVDA+Alt+[ | Decrease punctuation level |
| NVDA+Alt+] | Increase punctuation level |
| NVDA+Alt+F2 | Set screen window |
| NVDA+Alt+F3 | Clear screen window |
| NVDA+Alt+F4 | Toggle window silence |
| NVDA+Alt+Plus | Read window content |
| NVDA+Alt+Asterisk | Cycle cursor tracking mode |
| NVDA+Alt+A | Continuous reading (say all) |
| NVDA+Alt+I, I | Line indentation (double-press) |
| NVDA+Alt+Home | First character of line |
| NVDA+Alt+End | Last character of line |
| NVDA+Alt+PageUp | Top of screen |
| NVDA+Alt+PageDown | Bottom of screen |
| NVDA+Alt+Shift+Arrows | Read to edge |
| NVDA+Alt+P | Position announcement |
| NVDA+Alt+Comma, , , | Character code (triple-press) |

### Modified Gestures
- NVDA+Alt+A: Move from attribute reading to continuous reading (more important)
- Consider using NVDA+Alt+Shift+A for attribute reading

## Expected Impact

### User Experience Improvements

1. **For Developers**:
   - Punctuation levels essential for reading code
   - Indentation detection for Python/YAML
   - Attribute reading for syntax highlighting
   - Window system for split terminals

2. **For System Administrators**:
   - Continuous reading for log files
   - Window system to silence status bars
   - Enhanced navigation for large output
   - Position commands for table data

3. **For General Users**:
   - Better experience with TUI applications
   - More flexible text copying
   - Reduced verbosity with windowing
   - Clearer terminal navigation

### Accessibility Improvements

- **Reduced Cognitive Load**: Window system eliminates repetitive announcements
- **Better Comprehension**: Punctuation levels provide context-appropriate detail
- **Faster Navigation**: Edge commands and read-to-edge features
- **Improved Accuracy**: Indentation and attribute reading
- **Greater Flexibility**: Multiple tracking modes for different contexts

## Conclusion

Speakup offers a mature, feature-rich model for terminal accessibility that has been refined over 25+ years. By adapting its most valuable features to the Windows/NVDA context, TDSR can provide a significantly enhanced terminal experience.

**Recommended Implementation Priority**:
1. Start with Tier 1 features (highest impact)
2. Implement Phase 1 quick wins first (build momentum)
3. Tackle Phase 2 core enhancements (punctuation levels)
4. Then implement Phase 3 advanced features (windowing system)
5. Finally add Phase 4 polish and profiles

**Estimated Total Implementation Time**: 12-18 weeks for full feature set

**Key Success Metrics**:
- User feedback on navigation efficiency
- Reduced need for manual line-by-line reading
- Better experience with complex TUI applications
- Improved accessibility for code and configuration review

This enhancement plan positions TDSR as the most comprehensive terminal accessibility solution for Windows, matching and in some areas exceeding Speakup's capabilities while being optimized for the Windows/NVDA ecosystem.
