# Changelog

All notable changes to the TDSR for NVDA add-on will be documented in this file.

## [1.0.2] - 2026-02-19

### Fixed
- Fixed "Missing file or invalid file format" error when installing add-on in NVDA
- Build script now properly excludes root-level __init__.py from .nvda-addon package

### Technical
- Updated build.py to skip addon/__init__.py during package creation (lines 45-48)
- NVDA add-ons must not include __init__.py at the root level of the package

## [1.0.1] - 2026-02-19

### Changed
- Updated compatibility for NVDA 2026.1 (beta)
- Updated lastTestedNVDAVersion to 2026.1 in manifest and build configuration
- Removed unused imports (controlTypes, winUser) for cleaner code

### Technical
- Verified all NVDA API usage is compatible with NVDA 2026.1
- Confirmed script decorator usage follows current NVDA patterns
- Validated settings panel integration with modern NVDA

## [1.0.0] - 2024-02-19

### Added
- Initial release of TDSR for NVDA add-on
- Support for Windows Terminal, PowerShell, PowerShell Core, Command Prompt, and Console Host
- Line-by-line navigation (NVDA+Alt+U/I/O)
- Word navigation with spelling support (NVDA+Alt+J/K/L)
- Character navigation with phonetic alphabet (NVDA+Alt+M/Comma/Period)
- Cursor tracking and automatic announcements
- Key echo functionality
- Symbol processing for better command syntax understanding
- Quiet mode toggle (NVDA+Alt+Q)
- Selection and copy mode functionality
- Comprehensive settings panel in NVDA preferences ("Terminal Settings")
- User guide accessible via NVDA+Shift+F1
- Automatic help announcement when entering terminals
- Configuration options for:
  - Cursor tracking
  - Key echo
  - Line pause
  - Symbol processing
  - Repeated symbols condensation
  - Cursor delay (0-1000ms)
- Support for Windows 10 and Windows 11
- Compatibility with NVDA 2019.3 and later versions

### Documentation
- Comprehensive user guide with keyboard commands reference
- Installation and configuration instructions
- Troubleshooting guide
- Tips and best practices

### Technical
- Global plugin architecture for system-wide terminal support
- Integration with NVDA's configuration system
- Settings persistence across sessions
- Modular code structure for maintainability
