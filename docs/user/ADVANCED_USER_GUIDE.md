# Terminal Access for NVDA - Advanced User Guide

## Table of Contents

1. [Application Profiles](#application-profiles)
2. [Third-Party Terminal Support](#third-party-terminal-support)
3. [Window Definitions](#window-definitions)
4. [Unicode and CJK Text](#unicode-and-cjk-text)
5. [Performance Optimization](#performance-optimization)
6. [Troubleshooting Advanced Scenarios](#troubleshooting-advanced-scenarios)

---

## Application Profiles

Application profiles allow Terminal Access to automatically adjust its settings based on the terminal application you're using. Each profile can customize punctuation levels, cursor tracking modes, and define window regions for specialized behavior.

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

**New in v1.0.26**: Terminal Access now supports 13 popular third-party terminal emulators in addition to the 5 built-in Windows terminals.

### Supported Terminals

#### Built-in Windows Terminals
- **Windows Terminal**: Modern Windows terminal application
- **cmd**: Traditional Command Prompt
- **powershell**: Windows PowerShell
- **pwsh**: PowerShell Core (cross-platform)
- **conhost**: Console Host

#### Third-Party Terminal Emulators (v1.0.26+)

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

**New in v1.0.25**: TDSR supports advanced Unicode features including right-to-left text and complex emoji sequences.

### CJK Character Support

TDSR correctly handles double-width characters used in Chinese, Japanese, and Korean:

- **Accurate Width Calculation**: CJK characters count as 2 columns
- **Column Extraction**: Rectangular selection works correctly with CJK
- **Combining Characters**: Zero-width combining marks handled properly

Example:
```
Hello世界  # "Hello" = 5 columns, "世界" = 4 columns, total = 9 columns
```

### Right-to-Left (RTL) Text Support (v1.0.25)

TDSR automatically detects and processes RTL text:

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

Without these libraries, TDSR gracefully degrades to basic Unicode support.

### Emoji Support (v1.0.25)

TDSR handles complex emoji sequences:

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

TDSR includes several performance optimizations for large terminal buffers.

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

---

## Troubleshooting Advanced Scenarios

### Profile Not Applied Automatically

**Symptoms**: Profile doesn't activate when switching to an application

**Solutions**:
1. Check application name detection:
   - Open NVDA log (NVDA+F1)
   - Look for TDSR profile detection messages

2. Verify profile exists:
   - Open TDSR Settings → Application Profiles
   - Check if profile is in the list

3. Manual profile application:
   - Try exporting and re-importing the profile
   - Check JSON for correct `appName` field

### RTL Text Not Displaying Correctly

**Symptoms**: Arabic or Hebrew text appears reversed or garbled

**Solutions**:
1. Install optional dependencies:
   ```bash
   pip install python-bidi arabic-reshaper
   ```

2. Restart NVDA after installing dependencies

3. Verify text direction:
   - Check that text contains RTL characters
   - Mixed RTL/LTR text should work automatically

### Third-Party Terminal Not Detected

**Symptoms**: TDSR doesn't activate in a third-party terminal

**Solutions**:
1. Verify terminal is supported (see list above)

2. Check application name:
   - Open NVDA Python console (NVDA+Control+Z)
   - Run: `api.getForegroundObject().appModule.appName`
   - Compare with supported terminal names

3. Create a GitHub issue:
   - Include terminal name and version
   - Include appModule name from step 2
   - We can add support in a future release

### Performance Issues in Large Buffers

**Symptoms**: Slow response when navigating in buffers with 1000+ rows

**Solutions**:
1. Position caching should help automatically
   - Verify cache is enabled (it is by default)

2. Use incremental tracking:
   - Small cursor movements are optimized automatically

3. For extremely large buffers:
   - Consider using search/jump commands
   - Use bookmarks for frequent positions (future feature)

### Emoji Displaying as Single Characters

**Symptoms**: Complex emoji (family, flags) show as multiple characters

**Solutions**:
1. Install emoji library:
   ```bash
   pip install emoji
   ```

2. Restart NVDA after installing

3. If still not working:
   - Check terminal's emoji support
   - Some terminals may not render complex emoji sequences

---

## Additional Resources

- **GitHub Repository**: https://github.com/PratikP1/Terminal-Access-for-NVDA
- **Issue Tracker**: Report bugs and request features
- **CHANGELOG.md**: Detailed version history
- **API_REFERENCE.md**: Developer API documentation
- **ARCHITECTURE.md**: System design and architecture

For support, please open an issue on GitHub with:
- NVDA version
- TDSR version
- Terminal application and version
- Steps to reproduce
- Expected vs. actual behavior
