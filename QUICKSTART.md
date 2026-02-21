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
Open Windows Terminal, PowerShell, or Command Prompt.

You'll hear: *"Terminal Access support active. Press NVDA+shift+f1 for help."*

### Step 2: Try Basic Navigation
Try these keyboard commands:

- **NVDA+Alt+I** - Read current line
- **NVDA+Alt+O** - Read next line
- **NVDA+Alt+U** - Read previous line

### Step 3: Navigate by Word
Type a command and try:

- **NVDA+Alt+K** - Read current word
- **NVDA+Alt+L** - Read next word
- **NVDA+Alt+J** - Read previous word

### Step 4: Character Reading
Position on any text and try:

- **NVDA+Alt+Comma** - Read current character
- **NVDA+Alt+Comma** (twice) - Phonetic reading (e.g., "alpha" for "a")
- **NVDA+Alt+Comma** (three times) - Character code (e.g., "Character 65, hex 41, A")

### Step 5: Try Advanced Features
- **NVDA+Alt+A** - Continuous reading (say all) from cursor to end
- **NVDA+Alt+I** (twice) - Announce line indentation
- **NVDA+Alt+P** - Announce current position (row and column)

### Step 6: Control Punctuation Levels
- **NVDA+Alt+]** - Increase punctuation level (None → Some → Most → All)
- **NVDA+Alt+[** - Decrease punctuation level
- Try typing symbols with different levels to hear the difference

## Essential Commands

| Command | Action |
|---------|--------|
| **NVDA+Shift+F1** | Open full user guide |
| **NVDA+Alt+Q** | Toggle quiet mode |
| **NVDA+Alt+C** | Open settings (or copy selection if marks set) |
| **NVDA+Alt+I** | Read current line |
| **NVDA+Alt+I** (twice) | Announce line indentation |
| **NVDA+Alt+K** | Read current word |
| **NVDA+Alt+A** | Continuous reading (say all) |
| **NVDA+Alt+P** | Announce position (row, column) |
| **NVDA+Alt+[/]** | Decrease/increase punctuation level |
| **NVDA+Alt+Home/End** | Jump to start/end of line |
| **NVDA+Alt+PageUp/Down** | Jump to top/bottom of buffer |
| **NVDA+Alt+Shift+Arrows** | Read to edge (left/right/up/down) |

## Settings (2 minutes)

Open settings with **NVDA+Alt+C** or:
1. Press **NVDA+N** (NVDA menu)
2. Go to Preferences > Settings
3. Select "Terminal Settings"

Try these settings:
- **Key Echo**: Hear characters as you type
- **Cursor Tracking**: Announce cursor movements
- **Punctuation Level**: Control symbol verbosity (None/Some/Most/All)

## Common Tasks

### Reading Command Output
1. Run a command
2. Use **NVDA+Alt+A** for continuous reading (say all)
3. Or use **NVDA+Alt+U/I/O** to read line by line
4. Use **NVDA+Alt+Q** to enable quiet mode if output is verbose

### Using Punctuation Levels
1. Press **NVDA+Alt+]** to increase level
2. Type commands with symbols (@, #, $, etc.)
3. Hear more or fewer symbols based on level
4. Level 2 (Most) is ideal for code and scripts
5. Level 0 (None) is good for prose

### Selecting and Copying Text
1. Navigate to selection start
2. Press **NVDA+Alt+R** to mark start
3. Navigate to selection end
4. Press **NVDA+Alt+R** to mark end
5. Press **NVDA+Alt+C** to copy (linear) or **NVDA+Alt+Shift+C** (rectangular)
6. Press **NVDA+Alt+X** to clear marks

### Reading Portions of Screen
1. Position cursor where you want to start
2. Press **NVDA+Alt+Shift+Right** to read to end of line
3. Or **NVDA+Alt+Shift+Down** to read to bottom of buffer
4. Use other directions (Left/Up) as needed

### Reading Long Files or Logs
1. Navigate to start position
2. Press **NVDA+Alt+A** to read continuously to the end
3. Press any key to stop reading
4. Use **NVDA+Alt+PageUp/PageDown** to jump to top or bottom

### Working with Python or YAML Code
1. Navigate to a line of code
2. Press **NVDA+Alt+I** twice to hear indentation level
3. Use line navigation to review code structure
4. Indentation feedback helps understand nesting

### Debugging Character Issues
1. Navigate to a suspicious character
2. Press **NVDA+Alt+Comma** three times
3. Hear the character code (decimal and hex)
4. Useful for finding hidden control characters

### Working with Long Commands
1. Type your command
2. Use **NVDA+Alt+J/K/L** to review word by word
3. Use **NVDA+Alt+M/Comma/Period** for character-by-character editing
4. Use **NVDA+Alt+Home/End** to jump to start or end of line

### Finding Specific Information
1. Run your command
2. Navigate with line commands
3. Use word navigation to scan faster
4. Switch to character navigation for precision

## Getting Help

- **Full User Guide**: Press **NVDA+Shift+F1** anytime in a terminal
- **GitHub**: https://github.com/PratikP1/Terminal-Access-for-NVDA
- **Documentation**: See INSTALL.md, README.md, and docs/ directory

## Tips for Efficiency

1. **Use Continuous Reading**: Press NVDA+Alt+A to read long output instead of navigating line by line
2. **Master Punctuation Levels**: Cycle with [/] to match your current task (code vs. prose)
3. **Use Directional Reading**: Shift+Arrow combos quickly scan portions without moving cursor
4. **Learn Screen Edge Navigation**: Jump to line/buffer boundaries with Home/End/PageUp/PageDown
5. **Use Mark-Based Selection**: For precise text extraction from tables or structured output
6. **Check Indentation**: Press NVDA+Alt+I twice when reviewing Python or YAML code
7. **Use Quiet Mode**: Enable with NVDA+Alt+Q when commands produce lots of output
8. **Learn Word Navigation**: Faster than character-by-character
9. **Adjust Cursor Delay**: Fine-tune in settings for your preference
10. **Practice Commands**: Muscle memory makes navigation much faster

## Troubleshooting

### Not Working?
- Ensure you're in a supported terminal (Terminal, PowerShell, cmd)
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
