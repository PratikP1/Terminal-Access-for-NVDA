# Terminal Access for NVDA - Frequently Asked Questions (FAQ)

## Table of Contents

1. [General Questions](#general-questions)
2. [Installation and Setup](#installation-and-setup)
3. [Terminal Compatibility](#terminal-compatibility)
4. [Features and Usage](#features-and-usage)
5. [Troubleshooting](#troubleshooting)
6. [Advanced Topics](#advanced-topics)
7. [Contributing](#contributing)

---

## General Questions

### What is Terminal Access for NVDA?

Terminal Access is an NVDA add-on that provides enhanced accessibility for Windows terminal applications. It enables screen reader users to efficiently navigate and interact with command-line interfaces using features inspired by the Speakup screen reader and TDSR (Terminal Data Structure Reader).

### What terminals does Terminal Access support?

**As of v1.0.26**, Terminal Access supports 18 terminal applications:

**Built-in Windows Terminals (5)**:
- Windows Terminal
- Command Prompt (cmd)
- Windows PowerShell
- PowerShell Core (pwsh)
- Console Host (conhost)

**Third-Party Terminals (13)**:
- Cmder
- ConEmu (32-bit and 64-bit)
- mintty (Git Bash, Cygwin)
- PuTTY
- KiTTY
- Terminus
- Hyper
- Alacritty
- WezTerm
- Tabby
- FluentTerminal

### How is Terminal Access different from NVDA's built-in terminal support?

Terminal Access provides additional features specifically designed for terminal workflows:
- **Enhanced Navigation**: Navigate by line, word, character, column, and row
- **Rectangular Selection**: Select columns of text (useful for tables and formatted output)
- **Application Profiles**: Automatic optimization for vim, tmux, git, and other CLI tools
- **Window Definitions**: Define and track specific screen regions
- **Cursor Tracking Modes**: Multiple modes for different workflows
- **Symbol Processing**: Configurable punctuation levels
- **Advanced Unicode**: RTL text support (Arabic, Hebrew) and emoji sequences

### Is Terminal Access free and open source?

Yes! Terminal Access is free and open source under the GNU General Public License v3.0. Source code is available at https://github.com/PratikP1/Terminal-Access-for-NVDA

---

## Installation and Setup

### How do I install Terminal Access?

1. Download the latest `.nvda-addon` file from the [GitHub Releases page](https://github.com/PratikP1/Terminal-Access-for-NVDA/releases)
2. Press Enter on the downloaded file
3. NVDA will prompt you to install the add-on
4. Click "Yes" to install
5. Restart NVDA when prompted

### How do I configure Terminal Access?

1. Open NVDA Settings (NVDA+N → Preferences → Settings)
2. Navigate to the "Terminal Access" category
3. Adjust settings as desired
4. Click "OK" to save changes

### What are the recommended settings for beginners?

Default settings are optimized for general use:
- **Cursor Tracking**: Standard mode
- **Punctuation Level**: Some
- **Key Echo**: Enabled
- **Line Pause**: Enabled (helpful for long lines)

You can adjust these later as you become more comfortable.

### Can I reset Terminal Access to default settings?

Yes:
1. Open NVDA Settings → Terminal Access
2. Click the "Reset to Defaults" button at the bottom
3. Click "OK" to apply

---

## Terminal Compatibility

### Does Terminal Access work with third-party terminals?

Yes! As of v1.0.26, Terminal Access supports 13 popular third-party terminal emulators including Cmder, ConEmu, mintty (Git Bash), PuTTY, Terminus, Hyper, Alacritty, WezTerm, and more.

### How do I request support for a new terminal?

1. Open a [Terminal Support Request](https://github.com/PratikP1/Terminal-Access-for-NVDA/issues/new/choose) on GitHub
2. Provide:
   - Terminal name and version
   - Application module name (see issue template for instructions)
   - Why you prefer this terminal
3. We'll review and consider adding support in a future release

### Does Terminal Access work with WSL (Windows Subsystem for Linux)?

WSL terminals should work as they run through Windows Terminal or other supported terminals. However, WSL-specific testing has not been comprehensive. If you encounter issues, please report them on GitHub.

### Can I use Terminal Access with SSH connections?

Yes! Terminal Access works well with:
- PuTTY and KiTTY for SSH/telnet
- Windows Terminal with SSH
- Any supported terminal running SSH clients

The application profile for PuTTY is optimized for remote terminal sessions.

---

## Features and Usage

### What keyboard shortcuts does Terminal Access provide?

Key navigation commands (customize in NVDA Input Gestures):
- **Line Navigation**: NVDA+Up/Down arrows
- **Word Navigation**: NVDA+Control+Left/Right arrows
- **Character Navigation**: NVDA+Left/Right arrows
- **Column/Row Navigation**: NVDA+Shift+Left/Right/Up/Down
- **Selection**: NVDA+Shift+selection keys
- **Cursor Tracking**: NVDA+T (cycle modes)
- **Read Position**: NVDA+NumpadDelete (current coordinates)

Refer to the main README for the complete gesture list.

### How do rectangular selections work?

Rectangular (column-based) selections are useful for:
- Selecting columns in tables
- Extracting specific fields from formatted output
- Working with data arranged in columns

To create a rectangular selection:
1. Move to the starting position
2. Use NVDA+Shift+Column/Row navigation to select
3. The selected text will be copied to the clipboard in column format

### What are application profiles?

Application profiles allow Terminal Access to automatically adjust settings when you switch between applications. For example:
- **vim**: Higher punctuation level (for code), silent status line
- **tmux**: Silent status bar
- **git**: Optimized for diffs and logs
- **htop**: Optimized for process viewer layout

You can create custom profiles for any application.

### Can I export and share profiles?

Yes! (v1.0.24+)
1. Open NVDA Settings → Terminal Access → Application Profiles
2. Select a profile
3. Click "Export..."
4. Save the JSON file
5. Share the file with others

To import:
1. Click "Import..."
2. Select a profile JSON file
3. The profile will be added to your list

### What is cursor tracking?

Cursor tracking automatically announces the cursor's position as you navigate. Terminal Access offers four modes:

- **Off**: No automatic announcements
- **Standard**: Announces character at cursor
- **Highlight**: Announces cursor position with context
- **Window**: Announces cursor within defined window regions

Cycle modes with NVDA+T.

### What are window definitions?

Window definitions let you define specific screen regions with different behaviors. For example, in vim:
- **Editor region**: Lines 1-N (normal speech)
- **Status line**: Last line (silent)

This prevents repetitive announcements of status bars and other UI elements.

---

## Troubleshooting

### Terminal Access gestures don't work in my terminal

**Check**:
1. Is the terminal supported? (See compatibility list)
2. Is focus in the terminal window?
3. Are Terminal Access gestures conflicting with terminal shortcuts?
   - Try remapping conflicting gestures in NVDA Input Gestures

**If the terminal isn't supported**:
- Open a Terminal Support Request on GitHub

### Cursor tracking announces too much/too little

**Adjust cursor tracking mode**:
- Press NVDA+T to cycle through modes
- Try different modes for different workflows:
  - **Standard**: For general use
  - **Highlight**: For more context
  - **Window**: For applications with defined regions
  - **Off**: When you prefer manual navigation

### Rectangular selection copies strange text

**Possible causes**:
1. **CJK characters**: Terminal Access handles double-width characters, but ensure your terminal displays them correctly
2. **Tab characters**: Tabs may not align as expected
3. **ANSI codes**: Some terminals include escape sequences

**Solutions**:
- Use linear selection (standard NVDA+Shift+arrows) for mixed content
- Clean up copied text with a text editor if needed

### Profile doesn't apply automatically

**Troubleshooting steps**:
1. Check NVDA log (NVDA+F1) for profile detection messages
2. Verify the profile exists in Terminal Access Settings → Application Profiles
3. Check the application module name matches the profile:
   - Open NVDA Python Console (NVDA+Control+Z)
   - Run: `api.getForegroundObject().appModule.appName`
   - Compare with profile name

### RTL text (Arabic/Hebrew) displays incorrectly

**Required dependencies**:
```bash
pip install python-bidi arabic-reshaper
```

**After installation**:
1. Restart NVDA
2. Verify dependencies loaded successfully in NVDA log

Without these libraries, Terminal Access provides basic Unicode support but not full RTL handling.

### Performance is slow in large buffers

**Optimizations** (automatic in v1.0.21+):
- Position caching reduces repeat calculations
- Incremental tracking optimizes small movements
- Background processing for large selections

**If still slow**:
- Use search/jump commands instead of line-by-line navigation
- Consider reducing buffer size in terminal settings
- Report performance issues on GitHub with buffer size details

---

## Advanced Topics

### How do I create a custom profile?

**Current method** (profile editor coming in future release):
1. Export an existing similar profile as a template
2. Edit the JSON file:
   - Change `appName` to match your application
   - Adjust `punctuationLevel`, `cursorTrackingMode`, etc.
   - Add window definitions if needed
3. Import the modified profile

**Example profile**:
```json
{
  "appName": "myapp",
  "displayName": "My Custom App",
  "punctuationLevel": 2,
  "cursorTrackingMode": 1,
  "quietMode": false,
  "keyEcho": true,
  "windows": []
}
```

### How do I add window definitions to a profile?

Window definitions are specified in the profile JSON:

```json
{
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

Coordinates are 1-based. Use 9999 for "last row/column".

**Modes**:
- `announce`: Normal speech
- `silent`: No speech
- `monitor`: Track changes (future feature)

### Can I use Terminal Access with screen or tmux?

Yes! Terminal Access has a built-in profile for tmux:
- Silent status bar (bottom line)
- Standard cursor tracking
- Optimized for multiplexed workflows

For screen, you can:
1. Export the tmux profile
2. Rename it to "screen"
3. Import it back

### Does Terminal Access support emoji?

Yes! (v1.0.25+) Terminal Access handles:
- Basic emoji
- Emoji with skin tone modifiers
- Zero-width joiner sequences (family, flags, professions)
- Accurate width calculation

**For full support, install**:
```bash
pip install emoji
```

### What Unicode features does Terminal Access support?

**v1.0.25 Unicode features**:
- **CJK characters**: Double-width calculation and column extraction
- **RTL text**: Arabic and Hebrew with bidirectional algorithm
- **Emoji sequences**: Complex multi-codepoint emoji
- **Combining characters**: Zero-width marks

**Optional dependencies**:
```bash
pip install python-bidi arabic-reshaper emoji
```

Terminal Access gracefully degrades without these libraries.

### Can I contribute to Terminal Access development?

Yes! Contributions are welcome:
- **Code**: Submit pull requests on GitHub
- **Documentation**: Improve guides and translations
- **Testing**: Test with different terminals and workflows
- **Bug Reports**: Report issues with detailed information
- **Feature Requests**: Suggest improvements

See CONTRIBUTING.md for guidelines.

---

## Still Have Questions?

- **GitHub Issues**: https://github.com/PratikP1/Terminal-Access-for-NVDA/issues
- **Documentation**: See README.md, ADVANCED_USER_GUIDE.md, API_REFERENCE.md
- **Code**: Explore the source on GitHub

For support, open a GitHub issue with:
- NVDA version
- Terminal Access version
- Terminal application
- Detailed steps to reproduce
- Expected vs. actual behavior
