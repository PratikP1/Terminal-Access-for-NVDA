# Terminal Access for NVDA - Roadmap and Specifications

## Project Overview

**Project Name:** Terminal Access for NVDA
**Version:** 1.4.0
**Purpose:** Make Windows terminal applications accessible to NVDA users
**Target Audience:** Blind and visually impaired developers, system administrators, and power users who use command-line interfaces

## Requirements Specification

### Functional Requirements

#### FR1: Terminal Support
- **FR1.1:** Support Windows Terminal application
- **FR1.2:** Support Windows PowerShell (5.x)
- **FR1.3:** Support PowerShell Core (7.x+)
- **FR1.4:** Support Command Prompt (cmd.exe)
- **FR1.5:** Support Console Host (conhost.exe)

#### FR2: Navigation Features
- **FR2.1:** Line-by-line navigation (previous, current, next)
- **FR2.2:** Word-by-word navigation (previous, current, next)
- **FR2.3:** Character-by-character navigation (previous, current, next)
- **FR2.4:** Review cursor tracking independent of system cursor

#### FR3: Speech Features
- **FR3.1:** Use NVDA's built-in speech synthesizer for all announcements
- **FR3.2:** Character echo (speak characters as typed)
- **FR3.3:** Word spelling (spell out word letter by letter)
- **FR3.4:** Phonetic character reading (NATO alphabet)
- **FR3.5:** Symbol processing (speak symbol names)
- **FR3.6:** Repeated symbol condensation

#### FR4: User Interface
- **FR4.1:** Settings panel in NVDA preferences dialog
- **FR4.2:** Settings category named "Terminal Settings"
- **FR4.3:** Help system accessible via NVDA+Shift+F1
- **FR4.4:** Announcement of help availability on terminal launch

#### FR5: Configuration
- **FR5.1:** Cursor tracking toggle
- **FR5.2:** Key echo toggle
- **FR5.3:** Line pause toggle
- **FR5.4:** Symbol processing toggle
- **FR5.5:** Repeated symbols toggle and configuration
- **FR5.6:** Cursor delay adjustment (0-1000ms)
- **FR5.7:** Quiet mode toggle

#### FR6: Selection and Copy
- **FR6.1:** Start/end selection marking
- **FR6.2:** Copy line functionality
- **FR6.3:** Copy screen functionality

#### FR7: Documentation
- **FR7.1:** User guide in HTML format
- **FR7.2:** Keyboard command reference
- **FR7.3:** Installation instructions
- **FR7.4:** Configuration guide
- **FR7.5:** Troubleshooting section

### Non-Functional Requirements

#### NFR1: Compatibility
- **NFR1.1:** Support NVDA versions 2025.1 and later
- **NFR1.2:** Support Windows 10 (all editions)
- **NFR1.3:** Support Windows 11 (all editions)
- **NFR1.4:** Maintain forward compatibility with future NVDA versions
- **NFR1.5:** Support both 32-bit and 64-bit Windows installations

#### NFR2: Performance
- **NFR2.1:** Minimal latency (<100ms) for keyboard commands
- **NFR2.2:** Low resource usage (minimal CPU and memory overhead)
- **NFR2.3:** No interference with terminal application performance

#### NFR3: Usability
- **NFR3.1:** Intuitive keyboard shortcuts following NVDA conventions
- **NFR3.2:** Clear and concise speech feedback
- **NFR3.3:** Accessible settings interface
- **NFR3.4:** Clear documentation

#### NFR4: Reliability
- **NFR4.1:** Graceful error handling
- **NFR4.2:** No crashes or freezes
- **NFR4.3:** Persistent configuration across sessions
- **NFR4.4:** Safe operation with other NVDA add-ons

#### NFR5: Maintainability
- **NFR5.1:** Modular code architecture
- **NFR5.2:** Clear code documentation
- **NFR5.3:** Standard Python coding practices
- **NFR5.4:** Version control with Git

## Development Roadmap

### Phase 1: Foundation (COMPLETED)
**Status:** Done

- [x] Project structure setup
- [x] Manifest and build configuration files
- [x] Basic global plugin infrastructure
- [x] Terminal application detection
- [x] Settings panel framework

### Phase 2: Core Features (COMPLETED)
**Status:** Done

- [x] Line navigation
- [x] Word navigation
- [x] Character navigation
- [x] Phonetic character reading
- [x] Quiet mode toggle
- [x] Help system (NVDA+Shift+F1)
- [x] Launch announcements

### Phase 3: Advanced Features (COMPLETED)
**Status:** Done

- [x] Symbol processing
- [x] Repeated symbol condensation
- [x] Selection and copy
- [x] Cursor tracking
- [x] Key echo
- [x] All configuration settings

### Phase 4: Documentation (COMPLETED)
**Status:** Done

- [x] User guide (HTML)
- [x] README.md
- [x] Installation guide
- [x] Changelog
- [x] Keyboard reference
- [x] Troubleshooting guide

### Phase 5: Testing and Refinement (COMPLETED)
**Status:** Done

- [x] 778 passing tests across 40 test files, ~54% total coverage
- [x] CI/CD pipeline: pytest on Python 3.11, flake8 lint, scons build
- [x] Manual testing on Windows 10 and Windows 11
- [x] Testing with NVDA 2025.1+
- [x] Testing with all supported terminals

### Phase 6: v2.0 Prep (IN PROGRESS)
**Status:** Partially complete

#### Done:
- [x] Settings panel with three flat sections: Speech and Tracking, NVDA Gesture Conflicts, Application Profiles
- [x] Error/warning line detection (`ErrorLineDetector`: 18 error + 5 warning regex patterns with word boundaries)
- [x] Audio cues: `_checkErrorAudioCue` (error tones in quiet mode), `_checkOutputActivityTone` (activity tones on output)
- [x] New config keys: `errorAudioCues`, `errorAudioCuesInQuietMode`, `outputActivityTones`, `outputActivityDebounce`
- [x] Profile transparency (announces profile name on terminal switch)
- [x] Gesture conflict detection (`GestureConflictDetector` in `lib/gesture_conflicts.py`)
- [x] `getScript()` override for gesture scoping (gestures bound but returns None outside terminals)
- [x] `_CONFLICTING_GESTURES` frozenset for settings checklist
- [x] Terminal detection via exact match on `appModule.appName` (not substring)
- [x] Removed `NewOutputAnnouncer` entirely

#### Remaining for v2.0 release:
- [ ] Remove Command History Navigation (NVDA+H/G, NVDA+Shift+H, NVDA+Shift+L)
- [ ] Remove Highlight cursor tracking mode (`CT_HIGHLIGHT`)
- [ ] Remove Rectangular selection (NVDA+Shift+C)
- [ ] Write migration guide for users of deprecated features

### Phase 7: Future Enhancements
**Status:** Planned

- [ ] Advanced terminal output parsing (tables, progress bars)
- [ ] Sound schemes for different event types
- [ ] Integration with TDSR plugins

### Phase 8: Maintenance (ONGOING)
**Status:** Active

- [ ] Bug fixes as reported
- [ ] NVDA compatibility updates
- [ ] Windows version compatibility
- [ ] Documentation updates
- [ ] User support
- [ ] Community engagement

## Feature Comparison: TDSR vs. Terminal Access

| Feature | Original TDSR | Terminal Access for NVDA |
|---------|---------------|---------------|
| Line navigation | Yes | Yes |
| Word navigation | Yes | Yes |
| Character navigation | Yes | Yes |
| Phonetic reading | Yes | Yes |
| Symbol processing | Yes | Yes |
| Quiet mode | Yes | Yes |
| Selection/Copy | Yes | Yes |
| Configuration menu | Yes | Yes (GUI) |
| Speech synthesis | External | NVDA built-in |
| Platform | Unix/Linux/macOS | Windows |
| Plugin system | Yes | Planned |
| Standalone app | Yes | No (NVDA add-on) |

## Technical Architecture

### Components

1. **Global Plugin** (`terminalAccess.py`)
   - Main entry point
   - Event handling
   - Terminal detection
   - Command routing

2. **Library Modules** (`addon/lib/`)
   - 11 modules, ~5556 lines total
   - Extracted from `terminalAccess.py` for testability
   - Use `_runtime.py` for dependency injection

3. **Settings Panel** (`lib/settings_panel.py`)
   - Three flat sections: Speech and Tracking, NVDA Gesture Conflicts, Application Profiles
   - Settings validation
   - Persistence management

4. **Navigation System** (`lib/navigation.py`)
   - Review cursor management
   - Tab management
   - Bookmarks with line content labels

5. **Speech System** (`lib/text_processing.py`)
   - ANSI parsing
   - Unicode width calculation
   - Error line classification

### Data Flow

```
User Input -> Global Plugin -> Terminal Detection -> Command Handler ->
Navigation System -> Text Extraction -> Speech Processing -> NVDA Speech
```

### Configuration Storage

Settings are stored in NVDA's configuration system:
```
%APPDATA%\nvda\nvda.ini
[terminalAccess]
cursorTracking = True
keyEcho = True
linePause = True
...
```

## Testing Strategy

### Test Categories

1. **Unit Testing**: 40+ test files, 1073 passing tests
2. **Integration Testing**: Core workflows, multi-component interactions
3. **Performance Testing**: Benchmarks and regression tests
4. **Compatibility Testing**: Windows 10/11, NVDA 2025.1+, all supported terminals
5. **Manual Testing**: Keyboard commands, settings, profiles

### Test Environments

- Windows 10 (21H2, 22H2)
- Windows 11 (21H2, 22H2, 23H2)
- NVDA 2025.1, 2025.x, 2026.x
- Windows Terminal, PowerShell, cmd.exe

## Support and Maintenance

### Support Channels
- GitHub Issues
- Project wiki

### Maintenance Schedule
- Bug fixes: As needed
- NVDA compatibility updates: Within 1 month of NVDA releases
- Feature updates: Quarterly
- Documentation updates: As needed

## Licensing

**License:** GNU General Public License v3.0
- Consistent with NVDA's license
- Keeps software free and open source
- Compatible with original TDSR license

---

**Document Version:** 1.3
**Last Updated:** 2026-03-22
**Maintained By:** Terminal Access for NVDA Contributors
