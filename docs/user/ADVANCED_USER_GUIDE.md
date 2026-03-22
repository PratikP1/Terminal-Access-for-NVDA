# Terminal Access for NVDA - Advanced User Guide

## Table of Contents

1. [Command Layer](#command-layer)
2. [Bookmarks](#bookmarks)
3. [Error and Warning Detection](#error-and-warning-detection)
4. [Gesture Conflict Detection](#gesture-conflict-detection)
5. [Application Profiles](#application-profiles)
6. [Third-Party Terminal Support](#third-party-terminal-support)
7. [Window Definitions](#window-definitions)
8. [Unicode and CJK Text](#unicode-and-cjk-text)
9. [Performance Optimization](#performance-optimization)

---

## Command Layer

The command layer is a modal input mode that lets you execute Terminal Access commands with simple single-key presses instead of multi-key NVDA modifier combinations. This avoids conflicts with other NVDA add-ons and makes commands much faster to type.

### Entering and Exiting

| Gesture                        | Action                                                                   |
|--------------------------------|--------------------------------------------------------------------------|
| **NVDA+apostrophe**            | Enter the command layer. You hear "Terminal commands" and a high tone.    |
| **Escape** or **NVDA+apostrophe** | Exit the command layer. You hear "Exit terminal commands" and a low tone. |

The layer stays active until you explicitly exit. Each command you press keeps you in the layer so you can chain multiple commands. The layer automatically exits if focus leaves the terminal.

### Command Reference

While in the command layer, the following keys are active:

#### Navigation
| Key | Action |
|-----|--------|
| **U / I / O** | Read previous / current / next line |
| **J / K / L** | Read previous / current / next word |
| **M / , / .** | Read previous / current / next character |
| **Home / End** | Jump to start / end of line |
| **PageUp / PageDown** | Jump to top / bottom of buffer |
| **Shift+Left / Right** | Read to start / end of line |
| **Shift+Up / Down** | Read to top / bottom of buffer |

#### Information & Reading
| Key | Action |
|-----|--------|
| **A** | Continuous reading (say all) |
| **;** | Announce position (row, column) |
| **Shift+A** | Read text attributes and colors |
| **I** (twice) | Announce line indentation |
| **,** (twice) | Phonetic character reading |
| **,** (three times) | Character code |

#### Selection & Copying
| Key | Action |
|-----|--------|
| **R** | Toggle mark (start/end) |
| **C** | Copy linear selection |
| **Shift+C** | Copy rectangular selection *(deprecated, removed in v2)* |
| **X** | Clear marks |
| **V** | Enter copy mode (L=line, S=screen, Esc=cancel) |

#### Window Management
| Key | Action |
|-----|--------|
| **W** | Read window content |
| **Shift+W** | Set window boundaries |
| **Ctrl+W** | Clear window |
| **Y** | Cycle cursor tracking mode |

#### Configuration
| Key | Action |
|-----|--------|
| **Q** | Toggle quiet mode |
| **- / =** | Decrease / increase punctuation level |
| **D** | Toggle indentation announcement |
| **P** | Announce active profile. Press twice to select. |

#### Bookmarks
| Key | Action |
|-----|--------|
| **0-9** | Jump to bookmark |
| **Shift+0-9** | Set bookmark at current line (line text is captured as a label) |
| **B** | Open bookmark list dialog (shows bookmark number + line content; press Enter to jump, Delete to remove) |

#### Tabs
| Key | Action |
|-----|--------|
| **T** | Create new tab |
| **Shift+T** | List tabs |

#### Command History *(deprecated, removed in v2)*
| Key | Action |
|-----|--------|
| **H / G** | Previous / next command in history |
| **Shift+H** | Scan command history |
| **Shift+L** | List command history |

#### Search & URL List
| Key | Action |
|-----|--------|
| **E** | List URLs found in terminal output |
| **F** | Search terminal output |
| **F3** | Next search match |
| **Shift+F3** | Previous search match |

#### Help & Settings
| Key | Action |
|-----|--------|
| **F1** | Open user guide |
| **S** | Open Terminal Access settings |
| **Escape** | Exit command layer |

### Copy Mode Within the Layer

When you press **V** in the command layer, you enter copy mode. The keys **L** (copy line), **S** (copy screen), and **Escape** (cancel) temporarily override their layer bindings. When copy mode exits, those layer bindings are automatically restored.

### Customizing Gestures

All Terminal Access commands (both layer and direct) are registered under the "Terminal Access" category in NVDA's Input Gestures dialog. You can remap any gesture to suit your workflow.

### URL List

Press **E** in the command layer (or **NVDA+Alt+U** directly) to scan the terminal buffer for URLs. An interactive dialog opens with:

| Control | Description |
|---------|-------------|
| **Filter box** | Type to narrow results |
| **URL list** | Shows each URL, its line number, and surrounding text |
| **Open** (Alt+O) | Opens the selected URL in your default browser |
| **Copy URL** (Alt+C) | Copies the URL to the clipboard |
| **Move to line** (Alt+M) | Announces the line containing the URL |
| **Close** (Escape) | Closes the dialog |

Supported URL types: HTTP/HTTPS, FTP, www-prefixed, and OSC 8 terminal hyperlinks. Duplicate URLs are deduplicated automatically.

**Security note:** URLs with `file://`, `javascript:`, or other non-web schemes are detected and listed but cannot be opened from the dialog. Attempting to open one will produce a spoken message: "Cannot open this URL type for security reasons." This prevents malicious terminal output from tricking users into launching dangerous local resources.

---

## Bookmarks

Bookmarks let you save and revisit specific lines in the terminal buffer.

### Setting Bookmarks

Press **Shift+0** through **Shift+9** in the command layer (or **NVDA+Alt+0** through **NVDA+Alt+9** directly) to set a bookmark at the current line. The line's text is captured as a label so you can identify it later.

### Jumping to Bookmarks

Press **0-9** in the command layer (or **Alt+0** through **Alt+9** directly) to jump to that bookmark.

### Bookmark List Dialog

Press **B** in the command layer (or **NVDA+Shift+B** directly) to open an interactive list. The dialog shows two columns: bookmark number and line content. Press Enter to jump to the selected bookmark, or Delete to remove it.

Bookmarks are isolated per tab when using Windows Terminal tabs.

---

## Error and Warning Detection

Terminal Access plays audio cues when you navigate to lines that contain errors or warnings. This helps you scan build output, test results, or log files by ear.

- **Error lines** produce a low-pitched tone.
- **Warning lines** produce a higher-pitched tone.

The detector recognizes common patterns from compilers, linters, and shell output (e.g., `error:`, `ERROR`, `warning:`, `WARN`).

### Audio Cue Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| **Error Audio Cues** | boolean | True | Play tones on error/warning lines during navigation. |
| **Error Audio Cues in Quiet Mode** | boolean | False | Play error/warning tones on caret events while quiet mode is active. |
| **Output Activity Tones** | boolean | False | Play two ascending tones (600+800 Hz) when new program output appears. |
| **Output Activity Debounce** | integer | 1000 ms | Minimum interval between activity tones. Range: 100 to 10000 ms. |

Configure these in NVDA menu > Preferences > Settings > Terminal Settings.

### Gesture Scoping

All Terminal Access gestures only activate inside supported terminals. Outside a terminal, `getScript` returns None, so the gestures pass through to NVDA or other add-ons. Terminal detection uses exact match on the process name.

---

## Gesture Conflict Detection

Terminal Access detects when its keyboard shortcuts conflict with other installed NVDA add-ons. When a conflict is found, Terminal Access warns you so you can decide which binding to keep.

To resolve conflicts:

1. Open NVDA menu > Preferences > Settings > Terminal Settings.
2. In the "NVDA Gesture Conflicts" section, uncheck any gesture you want to disable.
3. Disabled direct gestures remain accessible through the command layer (NVDA+apostrophe).

The command layer and help gestures (NVDA+Shift+F1) cannot be disabled.

---

## Application Profiles

Application profiles allow Terminal Access to adjust its settings based on the terminal application you're using. Each profile can customize punctuation levels, cursor tracking modes, and define window regions for specialized behavior.

### Understanding Profiles

Terminal Access comes with default profiles for popular applications:

#### Built-in Application Profiles (v1.0.18+)

- **vim/nvim**: Optimized for Vim/Neovim editors
  - Punctuation: MOST (for code symbols)
  - Cursor Tracking: WINDOW mode
  - Silent zones: Status line (bottom line), Command line (second from bottom)

- **tmux**: Terminal multiplexer support
  - Cursor Tracking: STANDARD mode
  - Silent zones: Status bar (bottom line)

- **htop**: Process viewer optimization
  - Repeated symbols: Disabled (progress bars have many repeated characters)
  - Window regions: Header (lines 1-4), Process list (lines 5+)

- **less/more**: Pager applications
  - Quiet mode: Enabled
  - Key echo: Disabled (navigation keys not announced)

- **git**: Version control operations
  - Punctuation: MOST (symbols in diffs)
  - Repeated symbols: Disabled (many dashes/equals)

- **nano**: GNU nano editor
  - Cursor Tracking: STANDARD mode
  - Silent zones: Status bar, Shortcut bar (bottom two lines)

- **irssi**: IRC client
  - Punctuation: SOME (for chat)
  - Line pause: Disabled (fast reading for chat)
  - Silent zones: Status bar (bottom line)

- **WSL (v1.0.27+)**: Windows Subsystem for Linux
  - Punctuation: MOST (code-friendly for Linux commands and paths)
  - Cursor Tracking: STANDARD mode
  - Repeated symbols: OFF (progress bars and separators common in Linux tools)
  - See [WSL_TESTING_GUIDE.md](WSL_TESTING_GUIDE.md) for detailed WSL support

### Managing Profiles

#### Viewing Installed Profiles

1. Open NVDA Settings (NVDA+N → Preferences → Settings)
2. Navigate to "Terminal Access" category
3. Go to "Application Profiles" section
4. The "Installed profiles" dropdown shows all available profiles

Profiles are sorted with default profiles first, then custom profiles alphabetically.

#### Exporting a Profile

To share a profile or create a backup:

1. Open Terminal Access Settings
2. Navigate to "Application Profiles" section
3. Select the profile you want to export from the dropdown
4. Click "Export..." button
5. Choose a location and filename (default: `profilename_profile.json`)
6. Click "Save"

The profile will be saved as a JSON file containing all settings and window definitions.

#### Importing a Profile

To import a shared profile:

1. Open Terminal Access Settings
2. Navigate to "Application Profiles" section
3. Click "Import..." button
4. Browse to the profile JSON file
5. Click "Open"

The profile will be added to your installed profiles list. If a profile with the same name exists, it will be replaced.

#### Deleting a Custom Profile

1. Open Terminal Access Settings
2. Navigate to "Application Profiles" section
3. Select the custom profile from the dropdown
4. Click "Delete Profile" button
5. Confirm deletion

**Note**: Default profiles (vim, tmux, htop, less, git, nano, irssi) cannot be deleted.

### Profile Setting Overrides

When an application profile is active, its settings override the global Terminal Access settings. For example, if the `less` profile sets `keyEcho = false`, key echo is disabled while `less` is running, regardless of the global setting.

If you toggle a setting (e.g., quiet mode) while a profile is active, the change is saved to that profile's overrides rather than the global settings. When you switch to a different application, the global settings are restored.

### Creating Custom Profiles

While a profile editor dialog is planned for future releases, you can currently create custom profiles by:

1. Exporting an existing profile as a template
2. Editing the JSON file with your preferred settings
3. Importing the modified profile

Example profile JSON structure:

```json
{
  "appName": "myapp",
  "displayName": "My Application",
  "punctuationLevel": 2,
  "cursorTrackingMode": 1,
  "quietMode": false,
  "keyEcho": true,
  "linePause": true,
  "repeatedSymbols": true,
  "windows": [
    {
      "name": "status",
      "top": 9999,
      "bottom": 9999,
      "left": 1,
      "right": 9999,
      "mode": "silent",
      "enabled": true
    }
  ]
}
```

---

## Third-Party Terminal Support

Terminal Access supports 24 third-party terminal emulators in addition to the 5 built-in Windows terminals and WSL (30 total).

### Supported Terminals

#### Built-in Windows Terminals
- **Windows Terminal**: Modern Windows terminal application
- **cmd**: Traditional Command Prompt
- **powershell**: Windows PowerShell
- **pwsh**: PowerShell Core (cross-platform)
- **conhost**: Console Host

#### Third-Party Terminal Emulators

1. **Cmder**: Portable console emulator for Windows
   - Popular among developers
   - Includes Unix tools
   - Default profile: Balanced settings for general use

2. **ConEmu**: Windows console emulator with tabs
   - Both 32-bit and 64-bit versions supported
   - Highly customizable
   - Supports multiple console processes

3. **mintty**: Terminal emulator for Git Bash and Cygwin
   - Lightweight and fast
   - Popular for Git operations
   - Default profile: MOST punctuation (for development)

4. **PuTTY**: SSH and telnet client
   - Industry-standard for remote access
   - Optimized for SSH sessions
   - KiTTY (PuTTY fork) also supported

5. **Terminus**: Modern, highly configurable terminal
   - Electron-based
   - Cross-platform support
   - Tab and split pane features

6. **Hyper**: Terminal with web technologies
   - Electron-based
   - Extensible with plugins
   - Modern UI

7. **Alacritty**: GPU-accelerated terminal emulator
   - Extremely fast
   - Minimal, focused design
   - Written in Rust

8. **WezTerm**: GPU-accelerated terminal with multiplexing
   - Advanced features
   - Both standard and GUI variants supported
   - Excellent Unicode support

9. **Tabby**: Modern terminal with SSH and serial support
   - Electron-based
   - Built-in SSH client
   - Connection management

10. **FluentTerminal**: UWP-based terminal with modern UI
    - Windows 10/11 native
    - Fluent Design System
    - Touch-friendly

11. **Ghostty**: Fast, native terminal emulator
    - Written in Zig for performance
    - Cross-platform with native UI

12. **Rio**: Hardware-accelerated terminal
    - Written in Rust
    - GPU-powered rendering

13. **Wave Terminal**: Modern terminal with inline rendering
    - Inline file previews and widgets
    - Web-based extensibility

14. **Contour**: GPU-accelerated terminal emulator
    - VT extensions support
    - Modern rendering

15. **Cool Retro Term**: Retro CRT terminal emulator
    - Vintage CRT visual effects
    - Customizable appearance

16. **MobaXterm**: Enhanced terminal for Windows
    - Built-in X11 server and SSH client
    - Tabbed sessions and SFTP browser

17. **SecureCRT**: Professional SSH and terminal emulation
    - Enterprise-grade remote access
    - Note: VanDyke SecureFX (SFTP client) is intentionally excluded as it is not a terminal

18. **Tera Term**: Open-source terminal emulator
    - Lightweight SSH and serial connections
    - Macro scripting support

19. **mRemoteNG**: Multi-remote connection manager
    - Supports SSH, RDP, VNC, and more
    - Tabbed interface for multiple sessions

20. **Royal TS**: Cross-platform remote management
    - Enterprise connection management
    - Credential management and team sharing

### Using Third-Party Terminals

Terminal Access automatically detects third-party terminals when you switch to them. Each terminal has a default profile optimized for common usage patterns:

- **General terminals** (Cmder, ConEmu, Terminus, Hyper, Tabby, FluentTerminal):
  - Punctuation: SOME (balanced)
  - Cursor tracking: STANDARD

- **Development terminals** (mintty/Git Bash):
  - Punctuation: MOST (shows code symbols)
  - Cursor tracking: STANDARD

- **Remote access terminals** (PuTTY, KiTTY):
  - Punctuation: SOME (SSH-optimized)
  - Cursor tracking: STANDARD

- **High-performance terminals** (Alacritty, WezTerm):
  - Punctuation: SOME
  - Cursor tracking: STANDARD

### Customizing Third-Party Terminal Behavior

You can customize settings for any terminal:

1. Use the terminal you want to customize
2. Open NVDA Settings → Terminal Access
3. Adjust settings as desired
4. Export the profile for backup or sharing
5. Create custom window definitions if needed

All Terminal Access features work with third-party terminals:
- Navigation commands (line, word, character)
- Selection (linear and rectangular)
- Cursor tracking modes
- Symbol/punctuation levels
- Window definitions

---

## Window Definitions

Window definitions allow you to define specific regions of the terminal screen with different speech behaviors. This is useful for applications with status bars, command areas, or split panes.

### Window Definition Basics

Each window definition has:
- **Name**: Identifier for the window
- **Coordinates**: Top, bottom, left, right (1-based)
- **Mode**: How content is announced
- **Enabled**: Whether the window is active

### Window Modes

- **announce**: Read content normally (default)
- **silent**: Suppress all speech for this region
- **monitor**: Track changes but announce differently

### Coordinate System

Coordinates are 1-based (row 1, col 1 is top-left):
- **Top/Bottom**: Row numbers (1 to screen height)
- **Left/Right**: Column numbers (1 to screen width)
- **9999**: Special value meaning "last row/column"

### Example: Vim Status Line

```json
{
  "name": "editor",
  "top": 1,
  "bottom": 9998,
  "left": 1,
  "right": 9999,
  "mode": "announce"
},
{
  "name": "status",
  "top": 9999,
  "bottom": 9999,
  "left": 1,
  "right": 9999,
  "mode": "silent"
}
```

This defines:
- **editor**: All lines except the last two (normal speech)
- **status**: Last line (silent - status bar not announced)

### Use Cases

1. **Status Bars**: Silence repetitive status information
2. **Split Panes**: Define regions for tmux/screen panes
3. **Headers**: Special handling for htop/top headers
4. **Command Areas**: Monitor command input regions

---

## Unicode and CJK Text

**New in v1.0.25**: Terminal Access supports advanced Unicode features including right-to-left text and complex emoji sequences.

### CJK Character Support

Terminal Access correctly handles double-width characters used in Chinese, Japanese, and Korean:

- **Accurate Width Calculation**: CJK characters count as 2 columns
- **Column Extraction**: Rectangular selection works correctly with CJK
- **Combining Characters**: Zero-width combining marks handled properly

Example:
```
Hello世界  # "Hello" = 5 columns, "世界" = 4 columns, total = 9 columns
```

### Right-to-Left (RTL) Text Support (v1.0.25)

Terminal Access automatically detects and processes RTL text:

**Supported Languages**:
- Arabic (U+0600-U+06FF, U+0750-U+077F)
- Hebrew (U+0590-U+05FF)

**Features**:
- **Automatic Detection**: Analyzes character ranges to detect RTL text
- **Bidirectional Algorithm**: Unicode UAX #9 implementation
- **Arabic Reshaping**: Contextual forms (initial, medial, final, isolated)
- **Mixed Text**: Handles RTL and LTR text together
- **Column Extraction**: RTL-aware column operations

**Optional Dependencies**:
For full RTL support, install:
```bash
pip install python-bidi arabic-reshaper
```

Without these libraries, Terminal Access gracefully degrades to basic Unicode support.

### Emoji Support (v1.0.25)

Terminal Access handles complex emoji sequences:

**Supported Features**:
- **Zero-Width Joiners (ZWJ)**: Family emoji, profession emoji
- **Skin Tone Modifiers**: U+1F3FB through U+1F3FF
- **Variation Selectors**: Emoji vs. text presentation
- **Flag Sequences**: Country flags
- **Width Calculation**: Emoji typically 2 columns wide

**Optional Dependency**:
For full emoji support, install:
```bash
pip install emoji
```

Example emoji sequences:
- 👨‍👩‍👧‍👦 (Family with ZWJ)
- 👋🏽 (Waving hand with skin tone)
- 🇺🇸 (Country flags)

---

## Performance Optimization

Terminal Access includes several performance optimizations for large terminal buffers.

### Position Caching (v1.0.21)

Position calculations are cached for fast repeated access:

- **Cache Timeout**: 1000ms (1 second)
- **Cache Size**: Up to 100 positions
- **Automatic Invalidation**: On content changes, window resize, terminal switch

**Performance Impact**:
- First calculation: O(n) where n = row number
- Cached calculation: O(1) constant time
- Row 1000: ~500ms → <1ms with cache

### Incremental Position Tracking

For small cursor movements (within 10 positions):

- **10-20x faster** than full calculation
- **No cache required** for simple movements
- **Automatic fallback** for large jumps

### Background Processing (v1.0.22)

Large rectangular selections (>100 rows) run in background threads:

- **Progress Dialog**: Shows completion percentage
- **Cancellation Support**: Cancel long-running operations
- **Operation Queue**: Prevents overlapping operations

### Native Acceleration

When the native component is available (`termaccess.dll`), CPU-bound text processing is offloaded to compiled Rust code:

- **ANSI escape stripping**: Faster removal of color/formatting codes from terminal output
- **Text diffing**: Efficient change detection for new output announcements
- **Search**: Regex and literal pattern matching with built-in ANSI stripping
- **Unicode width**: Accurate CJK/combining character width calculation using the `unicode-width` crate

A background **helper process** (`termaccess-helper.exe`) reads terminal buffers via UIA on a separate thread, keeping NVDA's main thread responsive. For terminals without UIA TextPattern support (some conhost configurations, mintty, older PuTTY builds), the helper falls back to reading via the Win32 Console API (`ReadConsoleOutputCharacterW`).

All native features fall back gracefully to pure Python when the native components are unavailable. No user action is required.

---

## Additional Resources

For troubleshooting and frequently asked questions, see:
- **[FAQ.md](FAQ.md)** - Troubleshooting and answers to common questions
- **[GitHub Repository](https://github.com/PratikP1/Terminal-Access-for-NVDA)** - Source code and issue tracker
- **[CHANGELOG.md](../../CHANGELOG.md)** - Detailed version history
- **[API_REFERENCE.md](../developer/API_REFERENCE.md)** - Developer API documentation
- **[ARCHITECTURE.md](../developer/ARCHITECTURE.md)** - System design and architecture

For support, please open an issue on GitHub with:
- NVDA version
- Terminal Access version
- Terminal application and version
- Steps to reproduce
- Expected vs. actual behavior

