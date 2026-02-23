# TDSR for NVDA - Roadmap and Specifications

## Project Overview

**Project Name:** TDSR for NVDA  
**Version:** 1.0.0  
**Purpose:** Provide enhanced terminal accessibility for NVDA users on Windows  
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
- **FR7.1:** Comprehensive user guide in HTML format
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
- **NFR2.2:** Efficient resource usage (minimal CPU and memory overhead)
- **NFR2.3:** No interference with terminal application performance

#### NFR3: Usability
- **NFR3.1:** Intuitive keyboard shortcuts following NVDA conventions
- **NFR3.2:** Clear and concise speech feedback
- **NFR3.3:** Accessible settings interface
- **NFR3.4:** Comprehensive documentation

#### NFR4: Reliability
- **NFR4.1:** Graceful handling of errors
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
**Duration:** Initial development  
**Status:** ✅ Complete

#### Deliverables:
- [x] Project structure setup
- [x] Manifest and build configuration files
- [x] Basic global plugin infrastructure
- [x] Terminal application detection
- [x] Settings panel framework

### Phase 2: Core Features (COMPLETED)
**Duration:** Initial development  
**Status:** ✅ Complete

#### Deliverables:
- [x] Line navigation implementation
- [x] Word navigation implementation
- [x] Character navigation implementation
- [x] Phonetic character reading
- [x] Quiet mode toggle
- [x] Help system (NVDA+Shift+F1)
- [x] Launch announcements

### Phase 3: Advanced Features (COMPLETED)
**Duration:** Initial development  
**Status:** ✅ Complete

#### Deliverables:
- [x] Symbol processing
- [x] Repeated symbol condensation
- [x] Selection and copy functionality
- [x] Cursor tracking
- [x] Key echo
- [x] All configuration settings

### Phase 4: Documentation (COMPLETED)
**Duration:** Initial development  
**Status:** ✅ Complete

#### Deliverables:
- [x] User guide (HTML)
- [x] README.md
- [x] Installation guide
- [x] Changelog
- [x] Keyboard reference
- [x] Troubleshooting guide

### Phase 5: Testing and Refinement (NEXT)
**Duration:** 2-4 weeks  
**Status:** 🔄 Planned

#### Activities:
- [ ] Manual testing on Windows 10
- [ ] Manual testing on Windows 11
- [ ] Testing with NVDA 2025.1 (minimum version)
- [ ] Testing with latest NVDA version
- [ ] Testing with all supported terminals
- [ ] Accessibility testing
- [ ] Performance testing
- [ ] User acceptance testing

#### Success Criteria:
- All features working as specified
- No critical bugs
- Positive feedback from test users
- Performance meets requirements

### Phase 6: Enhancement (FUTURE)
**Duration:** Ongoing  
**Status:** 📋 Planned

#### Planned Enhancements:
- [ ] Advanced terminal output parsing (tables, progress bars)
- [ ] Command history navigation
- [ ] Output filtering and search
- [ ] Bookmark/marker functionality
- [ ] Multi-language support
- [ ] Sound schemes for different event types
- [ ] Integration with TDSR plugins
- [ ] Windows Subsystem for Linux (WSL) support
- [ ] Additional terminal emulator support

### Phase 7: Maintenance (ONGOING)
**Duration:** Ongoing  
**Status:** 🔄 Active

#### Activities:
- [ ] Bug fixes as reported
- [ ] NVDA compatibility updates
- [ ] Windows version compatibility
- [ ] Documentation updates
- [ ] User support
- [ ] Community engagement

## Feature Comparison: TDSR vs. TDSR for NVDA

| Feature | Original TDSR | TDSR for NVDA |
|---------|---------------|---------------|
| Line navigation | ✅ | ✅ |
| Word navigation | ✅ | ✅ |
| Character navigation | ✅ | ✅ |
| Phonetic reading | ✅ | ✅ |
| Symbol processing | ✅ | ✅ |
| Quiet mode | ✅ | ✅ |
| Selection/Copy | ✅ | ✅ |
| Configuration menu | ✅ | ✅ (GUI) |
| Speech synthesis | External | NVDA built-in |
| Platform | Unix/Linux/macOS | Windows |
| Plugin system | ✅ | 🔮 Planned |
| Standalone app | ✅ | ❌ (NVDA add-on) |

## Technical Architecture

### Components

1. **Global Plugin** (`tdsr.py`)
   - Main entry point
   - Event handling
   - Terminal detection
   - Command routing

2. **Settings Panel** (`TDSRSettingsPanel`)
   - GUI for configuration
   - Settings validation
   - Persistence management

3. **Configuration System**
   - NVDA config integration
   - Default values
   - Validation rules

4. **Navigation System**
   - Review cursor management
   - Line/word/character tracking
   - Text extraction

5. **Speech System**
   - NVDA speech integration
   - Symbol processing
   - Phonetic translation

### Data Flow

```
User Input → Global Plugin → Terminal Detection → Command Handler → 
Navigation System → Text Extraction → Speech Processing → NVDA Speech
```

### Configuration Storage

Settings are stored in NVDA's configuration system:
```
%APPDATA%\nvda\nvda.ini
[TDSR]
cursorTracking = True
keyEcho = True
linePause = True
...
```

## Testing Strategy

### Test Categories

1. **Functional Testing**
   - All keyboard commands
   - All settings options
   - Help system
   - Terminal detection

2. **Compatibility Testing**
   - Windows 10 versions
   - Windows 11 versions
   - NVDA versions 2025.1+
   - All supported terminals

3. **Accessibility Testing**
   - Settings dialog accessibility
   - Keyboard navigation
   - Screen reader feedback

4. **Performance Testing**
   - Command response time
   - Resource usage
   - Long terminal sessions

5. **Integration Testing**
   - Interaction with other NVDA add-ons
   - NVDA speech system integration
   - Windows accessibility APIs

### Test Environments

- Windows 10 (21H2, 22H2)
- Windows 11 (21H2, 22H2, 23H2)
- NVDA 2025.1, 2025.x, 2026.x
- Windows Terminal, PowerShell, cmd.exe

## Success Metrics

1. **Adoption**
   - Downloads
   - Active users
   - User feedback

2. **Quality**
   - Bug reports
   - Crash rate
   - User satisfaction

3. **Performance**
   - Command latency
   - Resource usage
   - Compatibility

## Support and Maintenance

### Support Channels
- GitHub Issues
- Project wiki
- User community forum (planned)

### Maintenance Schedule
- Bug fixes: As needed
- NVDA compatibility updates: Within 1 month of NVDA releases
- Feature updates: Quarterly
- Documentation updates: As needed

## Licensing

**License:** GNU General Public License v3.0  
**Rationale:** 
- Consistent with NVDA's license
- Ensures software remains free and open source
- Compatible with original TDSR license

## Future Considerations

### Potential Extensions
1. **TDSR Plugin Compatibility**
   - Adapt TDSR plugin system for Windows
   - Support for custom parsing plugins
   - Community plugin repository

2. **Advanced Terminal Features**
   - ANSI escape sequence handling
   - Color and formatting announcement
   - Table structure detection
   - Progress bar monitoring

3. **AI-Enhanced Features**
   - Command suggestion
   - Output summarization
   - Error explanation

4. **Cloud Integration**
   - Configuration sync
   - Collaborative features
   - Remote terminal support

### Community Engagement
- Contribution guidelines
- Developer documentation
- Community forum
- Regular release cycle

---

**Document Version:** 1.0  
**Last Updated:** 2024-02-19  
**Maintained By:** TDSR for NVDA Contributors
