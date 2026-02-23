# Terminal Access for NVDA

An NVDA add-on that provides enhanced terminal accessibility for various Windows Terminals like PowerShell, WSL2, and others. Inspired by [TDSR (Terminal Data Structure Reader)](https://github.com/tspivey/tdsr), this add-on incorporates functionality from both TDSR and [Speakup](https://github.com/linux-speakup/speakup). Advanced features inspired by community suggestions and discussions.

## Overview

Terminal Access enables screen reader users to efficiently navigate and interact with command-line interfaces on Windows. The add-on integrates seamlessly with NVDA's built-in speech synthesis and provides comprehensive navigation and reading commands specifically designed for terminal usage.

## Features

### Core Navigation
- **Line-by-line navigation** through terminal output
- **Word and character navigation** with phonetic spelling support
- **Continuous reading (Say All)** - Read from cursor to end of buffer
- **Screen edge navigation** - Jump to line/buffer boundaries quickly
- **Directional reading** - Read from cursor to any edge (left/right/top/bottom)

### Text Processing & Reading
- **Punctuation level system** - 4 levels of punctuation verbosity (None/Some/Most/All)
- **Line indentation detection** - Essential for Python and YAML code
- **Position announcement** - Report row and column coordinates
- **Character code announcement** - Display ASCII/Unicode values

### Advanced Selection & Copy
- **Enhanced selection system** - Linear and rectangular (column-based) selections
- **Mark-based selection** - Set start/end marks for precise text selection
- **Unicode/CJK support** - Proper column alignment for international text
- **ANSI-aware column extraction** - Accurate rectangular selection with color codes

### Color & Formatting (v1.0.18)
- **Enhanced ANSI parser** - Full support for terminal colors and formatting
  - Standard 8 colors + bright colors (16 total)
  - 256-color palette support
  - RGB/TrueColor (24-bit color) support
- **Format detection** - Bold, dim, italic, underline, blink, inverse, strikethrough
- **Attribute reading** - Announce colors and formatting at cursor (NVDA+Alt+Shift+A)

### Cursor Tracking & Windowing
- **Multiple cursor tracking modes** - Standard, Highlight, Window, or Off
- **Highlight tracking** - Detect and announce highlighted/inverse video text
- **Screen windowing** - Define and monitor specific screen regions
- **Multiple window definitions** - Support for split panes and complex layouts

### Application Profiles (v1.0.18)
**Automatic detection and optimized settings for popular terminal applications:**
- **Vim/Neovim** - Silences status line, enhanced punctuation for code
- **tmux** - Suppresses status bar for cleaner navigation
- **htop** - Separate regions for header and process list
- **less/more** - Quiet mode optimized for reading documents
- **Git** - Enhanced punctuation for diffs and logs
- **GNU nano** - Silences keyboard shortcuts area
- **irssi** - Chat-optimized settings for IRC
- **WSL (v1.0.27+)** - Linux command-line optimized with enhanced punctuation for paths and operators

### Tab Management (v1.0.39+)
- **Multi-tab terminal support** - Work seamlessly with Windows Terminal tabs
- **Tab-aware state management** - Bookmarks, searches, and command history automatically isolated per tab
- **Tab creation and navigation** - Keyboard shortcuts for creating and switching between tabs
- **Automatic tab detection** - Identifies when you switch tabs and updates context accordingly

### System Features
- **Key echo** to hear characters as you type
- **Quiet mode** to temporarily disable automatic announcements
- **Copy functionality** for terminal content with flexible selection
- **Configurable settings** through NVDA's settings dialog

## Supported Terminals

**Built-in Windows Terminals (5):**
- Windows Terminal
- Windows PowerShell
- PowerShell Core (pwsh)
- Command Prompt (cmd.exe)
- Console Host (conhost.exe)

**Windows Subsystem for Linux (WSL):**
- WSL1 and WSL2 (all distributions)
- Automatic detection and optimized profile
- Full support for Linux commands and tools

**Third-Party Terminal Emulators (13):**
- Cmder - Portable console emulator
- ConEmu - Console emulator with tabs (32-bit and 64-bit)
- mintty - Git Bash and Cygwin terminal
- PuTTY - SSH and telnet client
- KiTTY - PuTTY fork with enhancements
- Terminus - Modern, highly configurable terminal
- Hyper - Electron-based terminal
- Alacritty - GPU-accelerated terminal
- WezTerm - GPU-accelerated with multiplexing
- Tabby - Modern terminal with SSH support
- FluentTerminal - UWP-based terminal

**Total: 19 supported terminal applications (including WSL)**

For detailed information about each terminal, see [ADVANCED_USER_GUIDE.md](docs/user/ADVANCED_USER_GUIDE.md#third-party-terminal-support). For WSL-specific information, see [WSL_TESTING_GUIDE.md](docs/user/WSL_TESTING_GUIDE.md).

## System Requirements

- **Operating Systems:** Windows 10, Windows 11
- **NVDA Versions:** 2019.3 and later
- **Python:** 3.7+ (included with NVDA)

## Installation

1. Download the latest release (.nvda-addon file)
2. Press Enter on the downloaded file to install
3. Confirm installation when NVDA prompts
4. Restart NVDA when prompted

## Quick Start

When you open a supported terminal application, NVDA will announce:
> "Terminal Access support active. Press NVDA+shift+f1 for help."

Press **NVDA+Shift+F1** to open the comprehensive user guide.

## Key Commands

### Navigation
- **NVDA+Alt+U/I/O** - Read previous/current/next line
- **NVDA+Alt+I** (twice) - Announce line indentation level
- **NVDA+Alt+F5** - Toggle automatic indentation announcement on line read
- **NVDA+Alt+J/K/L** - Read previous/current/next word
- **NVDA+Alt+M/Comma/Period** - Read previous/current/next character
- **NVDA+Alt+Comma** (twice) - Read character phonetically
- **NVDA+Alt+Comma** (three times) - Announce character code

### Screen Edge Navigation
- **NVDA+Alt+Home** - Jump to first character of line
- **NVDA+Alt+End** - Jump to last character of line
- **NVDA+Alt+PageUp** - Jump to top of terminal buffer
- **NVDA+Alt+PageDown** - Jump to bottom of terminal buffer

### Directional Reading
- **NVDA+Alt+Shift+Left** - Read from cursor to beginning of line
- **NVDA+Alt+Shift+Right** - Read from cursor to end of line
- **NVDA+Alt+Shift+Up** - Read from cursor to top of buffer
- **NVDA+Alt+Shift+Down** - Read from cursor to bottom of buffer

### Reading & Position
- **NVDA+Alt+A** - Continuous reading (Say All) from cursor to end
- **NVDA+Alt+P** - Announce current row and column position

### Punctuation Levels
- **NVDA+Alt+[** - Decrease punctuation level
- **NVDA+Alt+]** - Increase punctuation level
- Levels: None (0) → Some (1) → Most (2) → All (3)

### Cursor Tracking & Attributes
- **NVDA+Alt+Asterisk** - Cycle cursor tracking mode (Off → Standard → Highlight → Window)
- **NVDA+Alt+Shift+A** - Read text attributes/colors at cursor

### Screen Windowing
- **NVDA+Alt+F2** - Set screen window (press twice: start, then end)
- **NVDA+Alt+F3** - Clear screen window
- **NVDA+Alt+Plus** - Read window content

### Selection & Copy
- **NVDA+Alt+R** - Toggle mark (start/end/clear for enhanced selection)
- **NVDA+Alt+C** - Copy linear selection (requires marks to be set)
- **NVDA+Alt+Shift+C** - Copy rectangular selection (requires marks to be set)
- **NVDA+Alt+X** - Clear selection marks
- **NVDA+Alt+V** - Enter legacy copy mode

### Bookmarks (v1.0.29+)
- **NVDA+Alt+Shift+0-9** - Set bookmark at current position
- **NVDA+Alt+0-9** - Jump to bookmark
- **NVDA+Alt+Shift+B** - List all bookmarks

### Tab Management (v1.0.39+)
- **NVDA+Shift+Alt+T** - Create a new tab in the terminal
- **NVDA+Alt+T** - List tabs or switch to next tab

**Note:** Tab management works with terminals that support multiple tabs, such as Windows Terminal, PowerShell 7+, and other modern terminal applications. Bookmarks, search results, and command history are automatically isolated per tab when using tab-aware terminals.

### Command History (v1.0.31+)
- **NVDA+Alt+Shift+H** - Scan and detect command history
- **NVDA+Alt+Up Arrow** - Navigate to previous command
- **NVDA+Alt+Down Arrow** - Navigate to next command
- **NVDA+Alt+Shift+L** - List command history

### Search (v1.0.30+)
- **NVDA+Alt+F** - Search terminal output
- **NVDA+F3** - Jump to next search match
- **NVDA+Shift+F3** - Jump to previous search match

### Special Features
- **NVDA+Alt+K** (twice) - Spell current word
- **NVDA+Alt+Q** - Toggle quiet mode
- **NVDA+Alt+F5** - Toggle automatic indentation announcement
- **NVDA+Alt+F10** - Announce active and default profiles

### Help
- **NVDA+Shift+F1** - Open user guide

## Configuration

Access Terminal Access settings through:
- NVDA menu > Preferences > Settings > Terminal Settings

### Available Settings

**Cursor Tracking** - Automatically announces the character at cursor position when it moves. Essential for monitoring position while navigating with arrow keys. Works with Cursor Delay to control timing.

**Cursor Tracking Mode** - Choose between four tracking modes:
- **Off**: No cursor tracking
- **Standard**: Announce character at cursor position (default)
- **Highlight**: Track and announce highlighted/inverse video text
- **Window**: Only track cursor within defined screen window

**Key Echo** - Announces each character as you type it. Provides immediate feedback for every keystroke. Works with Process Symbols and Condense Repeated Symbols for intelligent announcements.

**Line Pause** - Reserved for future continuous reading functionality. Currently preserved but not actively used.

**Announce Indentation When Reading Lines** - When enabled, automatically announces the indentation level (spaces and/or tabs) after reading each line with NVDA+Alt+U, I, or O. Essential for Python, YAML, and other indentation-sensitive code. Use NVDA+Alt+F5 to toggle quickly, or NVDA+Alt+I twice to query indentation of current line. Can be customized per application profile.

**Punctuation Level** - Controls how many symbols are announced (0-3):
- **Level 0 (None)**: No punctuation announced
- **Level 1 (Some)**: Basic punctuation (.,?!;:)
- **Level 2 (Most)**: Most punctuation (adds @#$%^&*()_+=[]{}\\|<>/)
- **Level 3 (All)**: All punctuation and symbols
- Applies to typing echo, cursor tracking, and character navigation. Essential for developers who need to hear punctuation in code and commands without overwhelming verbosity in prose.

**Condense Repeated Symbols** - Counts repeated symbols and announces them as a group (e.g., "3 equals" instead of "equals equals equals"). Only works with symbols specified in "Repeated Symbols to Condense".

**Repeated Symbols to Condense** - Specifies which symbols to condense (default: `-_=!`). Customize for your workflow (e.g., `-=#` for Markdown users).

**Cursor Delay** - Delay in milliseconds (0-1000) before announcing cursor position changes. Lower values provide instant feedback but may overwhelm during rapid movement. Default: 20ms.

**Default Profile** - Select a profile to use when no application-specific profile is detected. Allows you to have custom settings apply by default rather than global settings. Use NVDA+Alt+F10 to check which profile is currently active and which is set as default.

### Settings Interactions

- **Quiet Mode** (NVDA+Alt+Q) temporarily disables cursor tracking and key echo
- **Indentation Announcement** (NVDA+Alt+F5) toggles indentation reading on line navigation
- **Process Symbols** affects cursor tracking, key echo, and character navigation
- **Condense Repeated Symbols** requires Key Echo to be enabled
- **Cursor Delay** only affects cursor tracking, not key echo or manual navigation

## Troubleshooting

For troubleshooting common issues, please refer to the **[FAQ.md](docs/user/FAQ.md#troubleshooting)** which provides comprehensive solutions for:

- Terminal Access gestures not working
- No speech when moving cursor
- Punctuation not being announced
- Colors/formatting not announced
- Selection marks issues
- Profile activation problems
- Window tracking behavior
- Performance issues in large buffers
- Settings not saving
- Build/installation issues
- And more...

For advanced troubleshooting scenarios, see the **[Advanced User Guide](docs/user/ADVANCED_USER_GUIDE.md#troubleshooting-advanced-scenarios)**.

## Documentation

For detailed documentation, including:
- Complete keyboard command reference
- Configuration guide
- Tips and best practices

Press **NVDA+Shift+F1** while using the add-on, or view the `addon/doc/en/readme.html` file.

## Development

### Building from Source

The add-on can be built using standard NVDA add-on build tools. Ensure you have:
- Python 3.7+
- NVDA add-on development environment

To build the add-on manually:
```bash
python build.py
```

For automated builds (non-interactive mode):
```bash
python build.py --non-interactive
```

### Automated Releases

This project uses GitHub Actions to automatically build and publish releases when changes are pushed to the `main` branch. The release process:

1. **Automatic Triggering**: When commits are pushed to the `main` branch that affect `buildVars.py`, `manifest.ini`, `addon/`, or `build.py`, the workflow automatically triggers.

2. **Version Detection**: The version number is extracted from `buildVars.py` (the `addon_version` field).

3. **Build Process**: The workflow:
   - Builds the `.nvda-addon` package
   - Creates a source code archive
   - Extracts changelog information from `CHANGELOG.md`

4. **Release Creation**: If the version tag doesn't already exist, a GitHub release is created with:
   - Tag name: `v{version}` (e.g., `v1.0.1`)
   - The compiled `.nvda-addon` file
   - Source code archive
   - Changelog excerpt from the latest version

5. **Latest Tag**: The `latest` tag is automatically updated to point to the most recent release, making it easy for users to always download the current version.

**Note**: To create a new release, simply update the version number in `buildVars.py` and `manifest.ini`, update the `CHANGELOG.md`, and push to the `main` branch.

### Project Structure

```
Terminal-Access-for-NVDA/
├── addon/
│   ├── globalPlugins/
│   │   └── terminalAccess.py  # Main plugin code
│   ├── locale/              # Translation files (v1.0.32+)
│   └── doc/
│       └── en/
│           └── readme.html   # User guide
├── docs/                     # Organized documentation
│   ├── user/                # User guides and FAQs
│   ├── developer/           # Architecture and API docs
│   ├── testing/             # Testing procedures
│   └── archive/             # Historical/research documents
├── tests/                    # Automated test suite
├── .github/                  # CI/CD and issue templates
├── manifest.ini              # Add-on metadata
├── buildVars.py             # Build configuration
├── CHANGELOG.md             # Version history
└── README.md                # This file
```

## Documentation

Terminal Access provides comprehensive documentation organized by audience:

### User Documentation
- **[README.md](README.md)** (this file) - Quick start and feature overview
- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide for new users
- **[INSTALL.md](INSTALL.md)** - Installation instructions
- **[ADVANCED_USER_GUIDE.md](docs/user/ADVANCED_USER_GUIDE.md)** - In-depth guide covering:
  - Application profiles and customization
  - Third-party terminal emulator guide (18 terminals)
  - Window definitions and screen regions
  - Unicode, CJK, RTL text, and emoji support
  - Performance optimization tips
  - Advanced troubleshooting scenarios
- **[FAQ.md](docs/user/FAQ.md)** - Frequently asked questions covering:
  - General questions and getting started
  - Terminal compatibility
  - Feature usage and workflows
  - Troubleshooting common issues
  - Advanced topics
- **[WSL_TESTING_GUIDE.md](docs/user/WSL_TESTING_GUIDE.md)** - Windows Subsystem for Linux testing guide
- **[TRANSLATION_GUIDE.md](docs/user/TRANSLATION_GUIDE.md)** - Guide for translators (v1.0.32+)

### Developer Documentation
- **[ARCHITECTURE.md](docs/developer/ARCHITECTURE.md)** - System design and architecture (550+ lines)
- **[API_REFERENCE.md](docs/developer/API_REFERENCE.md)** - Complete API documentation (900+ lines)
- **[ROADMAP.md](docs/developer/ROADMAP.md)** - Project roadmap and future plans
- **[FUTURE_ENHANCEMENTS.md](docs/developer/FUTURE_ENHANCEMENTS.md)** - Future enhancement tracking
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development setup and contribution guidelines

### Testing Documentation
- **[TESTING_GUIDE.md](docs/testing/TESTING_GUIDE.md)** - Comprehensive testing guide covering:
  - Automated testing with pytest
  - Manual testing procedures
  - CI/CD integration
  - Test writing guidelines

### Change History
- **[CHANGELOG.md](CHANGELOG.md)** - Detailed version history with all changes from v1.0.0 to current (v1.0.32+)

### Release Documentation
- **[RELEASE.md](RELEASE.md)** - Release process and procedures

### GitHub Resources
- **Issue Templates** - Structured templates for:
  - Bug reports
  - Feature requests
  - Terminal support requests

### Archived Documentation
Historical and research documentation is preserved in `docs/archive/`:
- **Development artifacts** - Phase specifications, implementation summaries
- **Research documents** - Feature analysis, API research
- **Legacy documentation** - Superseded by current documentation but kept for reference

## Contributing

Contributions are welcome! Please feel free to:
- Report bugs or issues
- Suggest new features
- Submit pull requests
- Improve documentation

## Credits

Terminal Access is inspired by:
- [TDSR (Terminal Data Structure Reader)](https://github.com/tspivey/tdsr) by Tyler Spivey - Original terminal accessibility project that laid the foundation for terminal screen reader support
- [Speakup](https://github.com/linux-speakup/speakup) - Linux kernel screen reader, which inspired the advanced cursor tracking modes, screen windowing system, and attribute reading features

Community contributions and discussions from various accessibility forums and social media have shaped the advanced features in Terminal Access.

## License

Copyright (C) 2024 Pratik Patel

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

See the LICENSE file for the complete license text.

## Links

- [Project Repository](https://github.com/PratikP1/Terminal-Access-for-NVDA)
- [NVDA Official Website](https://www.nvaccess.org/)
- [Original TDSR Project](https://github.com/tspivey/tdsr)
- [Speakup Screen Reader](https://github.com/linux-speakup/speakup)
- [NVDA Add-on Development Guide](https://github.com/nvda-es/devguides_translation/blob/master/original_docs/NVDA-Add-on-DevelopmentGuide.md)
- [NVDA Developer Guide](https://download.nvaccess.org/documentation/developerGuide.html)
