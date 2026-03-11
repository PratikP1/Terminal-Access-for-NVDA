# Terminal Access for NVDA - Quick Start Guide

Welcome to Terminal Access for NVDA! This quick start guide will help you get up and running in minutes.

## What is Terminal Access for NVDA?

Terminal Access for NVDA is an add-on that enhances terminal accessibility on Windows. It provides navigation, reading, and interaction features specifically designed for command-line interfaces. Inspired by [TDSR](https://github.com/tspivey/tdsr) and [Speakup](https://github.com/linux-speakup/speakup).

## Installation (1 minute)

1. Download `terminalAccess-1.0.17.nvda-addon`
2. Press Enter on the file
3. Confirm installation
4. Restart NVDA

That's it! The add-on is now installed.

## First Steps (5 minutes)

### Step 1: Open a Terminal
Open any supported terminal: Windows Terminal, PowerShell, Command Prompt, WSL, or any of the 30 supported terminal emulators (including Alacritty, WezTerm, Ghostty, MobaXterm, and more).

You'll hear: *"Terminal Access support active. Press NVDA+shift+f1 for help."*

### Step 2: Enter the Command Layer (Recommended)
Press **NVDA+'** (apostrophe) to enter the **command layer**. You'll hear "Terminal commands" and a high-pitched tone. Now every command is a single key press — no modifier combos needed!

Try navigating:
- **I** - Read current line
- **O** - Read next line
- **U** - Read previous line
- **K** - Read current word
- **L** - Read next word
- **J** - Read previous word
- **Escape** or **NVDA+'** - Exit the command layer

### Step 3: Try More Commands in the Layer
While in the command layer:

- **A** - Continuous reading (say all)
- **;** - Announce position (row, column)
- **F** - Search terminal output
- **Q** - Toggle quiet mode
- **F1** - Open user guide

Press **Escape** when done.

### Step 4: Character Reading
Enter the command layer (**NVDA+'**) and try:

- **M** - Read previous character
- **,** (comma) - Read current character (twice for phonetic, three times for code)
- **.** (period) - Read next character

### Step 5: Try Advanced Features
Still in the command layer:

- **Home/End** - Jump to start/end of line
- **PageUp/PageDown** - Jump to top/bottom of buffer
- **Shift+Arrows** - Read to edge (left/right/up/down)
- **[/]** - Decrease/increase punctuation level
- **D** - Toggle indentation announcement

### Step 6: Direct Gestures (Alternative)
All commands also work with traditional NVDA modifier combos for power users:

- **NVDA+I** - Read current line
- **NVDA+O** - Read next line
- **NVDA+U** - Read previous line
- **NVDA+K** - Read current word
- **NVDA+A** - Continuous reading (say all)

These direct gestures can be remapped in NVDA's Input Gestures dialog under "Terminal Access".

## Essential Commands

### Command Layer (NVDA+' to enter, Escape to exit)

| Layer Key | Action |
|-----------|--------|
| **I** | Read current line |
| **O / U** | Read next / previous line |
| **K** | Read current word |
| **L / J** | Read next / previous word |
| **,** | Read current character |
| **A** | Continuous reading (say all) |
| **;** | Announce position (row, column) |
| **[/]** | Decrease/increase punctuation level |
| **Home/End** | Jump to start/end of line |
| **PageUp/Down** | Jump to top/bottom of buffer |
| **Shift+Arrows** | Read to edge (left/right/up/down) |
| **E** | List URLs in terminal output |
| **F** | Search terminal output |
| **Q** | Toggle quiet mode |
| **D** | Toggle indentation announcement |
| **F1** | Open user guide |
| **Escape** | Exit command layer |

### Direct Gestures (always available in terminal)

| Command | Action |
|---------|--------|
| **NVDA+'** | Enter/exit command layer |
| **NVDA+Shift+F1** | Open full user guide |
| **NVDA+Shift+Q** | Toggle quiet mode |
| **NVDA+F5** | Toggle automatic indentation announcement |
| **NVDA+I** | Read current line |
| **NVDA+I** (twice) | Announce line indentation |
| **NVDA+K** | Read current word |
| **NVDA+A** | Continuous reading (say all) |
| **NVDA+;** | Announce position (row, column) |
| **NVDA+[/]** | Decrease/increase punctuation level |
| **NVDA+Shift+Home/End** | Jump to start/end of line |
| **NVDA+F4/F6** | Jump to top/bottom of buffer |
| **NVDA+Shift+Arrows** | Read to edge (left/right/up/down) |
| **NVDA+Alt+U** | List URLs in terminal output |

## Settings (2 minutes)

Open settings:
1. Press **NVDA+N** (NVDA menu)
2. Go to Preferences > Settings
3. Select "Terminal Settings"

Try these settings:
- **Key Echo**: Hear characters as you type
- **Cursor Tracking**: Announce cursor movements
- **Punctuation Level**: Control symbol verbosity (None/Some/Most/All)
- **Announce Indentation When Reading Lines**: Automatically announce indentation for code

## Common Tasks

### Reading Command Output
1. Run a command
2. Use **NVDA+A** for continuous reading (say all)
3. Or use **NVDA+U/I/O** to read line by line
4. Use **NVDA+Shift+Q** to enable quiet mode if output is verbose

### Using Punctuation Levels
1. Press **NVDA+]** to increase level
2. Type commands with symbols (@, #, $, etc.)
3. Hear more or fewer symbols based on level
4. Level 2 (Most) is ideal for code and scripts
5. Level 0 (None) is good for prose

### Selecting and Copying Text
1. Navigate to selection start
2. Press **NVDA+R** to mark start
3. Navigate to selection end
4. Press **NVDA+R** to mark end
5. Press **NVDA+C** to copy (linear) or **NVDA+Shift+C** (rectangular)
6. Press **NVDA+X** to clear marks

### Reading Portions of Screen
1. Position cursor where you want to start
2. Press **NVDA+Shift+Right** to read to end of line
3. Or **NVDA+Shift+Down** to read to bottom of buffer
4. Use other directions (Left/Up) as needed

### Reading Long Files or Logs
1. Navigate to start position
2. Press **NVDA+A** to read continuously to the end
3. Press any key to stop reading
4. Use **NVDA+F4/F6** to jump to top or bottom

### Working with Python or YAML Code
1. Enable automatic indentation announcement with **NVDA+F5**
2. Navigate to a line of code with **NVDA+U/I/O**
3. Indentation level is announced automatically after the line content
4. Or press **NVDA+I** twice to query indentation of current line
5. Use line navigation to review code structure
6. Toggle off with **NVDA+F5** when not needed

### Debugging Character Issues
1. Navigate to a suspicious character
2. Press **NVDA+Comma** three times
3. Hear the character code (decimal and hex)
4. Useful for finding hidden control characters

### Working with Long Commands
1. Type your command
2. Use **NVDA+J/K/L** to review word by word
3. Use **NVDA+M/Comma/Period** for character-by-character editing
4. Use **NVDA+Shift+Home/End** to jump to start or end of line

### Finding Specific Information
1. Run your command
2. Navigate with line commands
3. Use word navigation to scan faster
4. Switch to character navigation for precision

## Complete Keyboard Reference

### Command Layer (enter with NVDA+', exit with Escape)

Once in the command layer, all commands are single-key presses:

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| **u/i/o** | Prev/current/next line | **j/k/l** | Prev/current/next word |
| **m/,/.** | Prev/current/next char | **Home/End** | Start/end of line |
| **PgUp/PgDn** | Top/bottom of buffer | **Shift+Arrows** | Read to edge |
| **a** | Say all | **;** | Announce position |
| **Shift+A** | Read attributes | **f** | Search output |
| **F3/Shift+F3** | Next/prev search match | **q** | Toggle quiet mode |
| **n** | Toggle new output | **d** | Toggle indentation |
| **[/]** | Punctuation level -/+ | **p** | Active profile |
| **r** | Toggle mark | **c/Shift+C** | Copy linear/rectangular |
| **x** | Clear marks | **v** | Copy mode |
| **w/Shift+W/Ctrl+W** | Read/set/clear window | **y** | Cycle tracking mode |
| **0-9** | Jump to bookmark | **Shift+0-9** | Set bookmark |
| **b** | List bookmarks | **t/Shift+T** | New tab / list tabs |
| **h/g** | Prev/next command | **Shift+H/Shift+L** | Scan/list history |
| **e** | List URLs | **s** | Open settings |
| **F1** | Open user guide | **Escape** | Exit command layer |

### Direct Gestures (NVDA modifier combos)

#### Basic Navigation
- **NVDA+U/I/O** - Read previous/current/next line
- **NVDA+J/K/L** - Read previous/current/next word
- **NVDA+M/Comma/Period** - Read previous/current/next character
- **NVDA+Shift+Home/End** - Jump to start/end of line
- **NVDA+F4/F6** - Jump to top/bottom of buffer

#### Advanced Reading
- **NVDA+A** - Continuous reading (say all)
- **NVDA+I** (twice) - Announce indentation level
- **NVDA+F5** - Toggle automatic indentation announcement
- **NVDA+Comma** (twice) - Read character phonetically
- **NVDA+Comma** (three times) - Announce character code
- **NVDA+K** (twice) - Spell current word
- **NVDA+;** - Announce position (row, column)

#### Directional Reading
- **NVDA+Shift+Left/Right** - Read to beginning/end of line
- **NVDA+Shift+Up/Down** - Read to top/bottom of buffer

#### Punctuation & Tracking
- **NVDA+[/]** - Decrease/increase punctuation level
- **NVDA+Alt+Y** - Cycle cursor tracking mode (layer: **y**)
- **NVDA+Shift+Q** - Toggle quiet mode

#### Selection & Copy
- **NVDA+R** - Toggle mark (press 3 times: start, end, clear)
- **NVDA+C** - Copy linear selection
- **NVDA+Shift+C** - Copy rectangular selection
- **NVDA+X** - Clear marks
- **NVDA+V** - Enter legacy copy mode

#### Window Management
- **NVDA+Alt+F2** - Set screen window (press twice: start, end)
- **NVDA+Alt+F3** - Clear screen window
- **NVDA+Alt+Plus** - Read window content
- **NVDA+Alt+Shift+A** - Read text attributes/colors

#### Bookmarks (v1.0.29+)
- **NVDA+Alt+0-9** - Set bookmark (0-9)
- **Alt+0-9** - Jump to bookmark (0-9)
- **NVDA+Shift+B** - List bookmarks

#### Command History (v1.0.31+)
- **NVDA+Shift+H** - Scan command history
- **NVDA+H/G** - Navigate previous/next command
- **NVDA+Shift+L** - List command history

#### Search (v1.0.30+)
- **NVDA+F** - Search terminal output
- **NVDA+F3** - Next search match
- **NVDA+Shift+F3** - Previous search match

#### URL List
- **NVDA+Alt+U** - List URLs in terminal output

#### Tab Management
- **NVDA+Shift+T** - Create new tab
- **NVDA+W** - List tabs

#### Settings & Help
- **NVDA+'** - Toggle command layer
- **NVDA+Shift+F1** - Open user guide
- **NVDA+F10** - Announce active and default profiles
- **NVDA+Shift+N** - Toggle new output announcements

## Getting Help

- **Full User Guide**: Press **NVDA+Shift+F1** anytime in a terminal
- **GitHub**: https://github.com/PratikP1/Terminal-Access-for-NVDA
- **Documentation**: See INSTALL.md, README.md, and docs/ directory

## Tips for Efficiency

1. **Use the Command Layer**: Press NVDA+' to enter single-key mode — much faster than modifier combos
2. **Use Continuous Reading**: Press A (in layer) to read long output instead of navigating line by line
3. **Master Punctuation Levels**: Press [/] (in layer) to match your current task (code vs. prose)
4. **Use Directional Reading**: Shift+Arrow combos quickly scan portions without moving cursor
5. **Learn Screen Edge Navigation**: Jump to line/buffer boundaries with Home/End/PageUp/PageDown
6. **Use Mark-Based Selection**: For precise text extraction from tables or structured output
7. **Check Indentation**: Press I twice (in layer) or NVDA+I twice for Python/YAML code
8. **Use Quiet Mode**: Press Q (in layer) when commands produce lots of output
9. **Remap Gestures**: All commands appear in NVDA's Input Gestures under "Terminal Access"
10. **Practice Commands**: Muscle memory makes navigation much faster

## Troubleshooting

### Not Working?
- Ensure you're in a supported terminal (Windows Terminal, PowerShell, cmd, WSL, or any of the 30 supported terminals)
- Check add-on is enabled in NVDA > Tools > Manage Add-ons
- Restart NVDA

### Commands Not Responding?
- Try different terminal application
- Check for keyboard shortcut conflicts in NVDA Input Gestures
- Review NVDA log (NVDA menu > Tools > View log)

## Next Steps

1. **Read the Full Guide**: Press **NVDA+Shift+F1** for complete documentation
2. **Explore Settings**: Customize Terminal Access to your workflow
3. **Try All Features**: Selection, copy mode, phonetic reading
4. **Practice Daily**: The more you use it, the more efficient you become

## Support

Need help?
- Check the troubleshooting section in the user guide
- Visit the GitHub repository
- Report issues on GitHub

---

**Enjoy using Terminal Access for NVDA!** Your command-line experience just got a lot better.
