# Terminal Access for NVDA: Quick Start

Terminal Access adds keyboard-driven navigation and reading commands to 30 Windows terminals. Inspired by [TDSR](https://github.com/tspivey/tdsr) and [Speakup](https://github.com/linux-speakup/speakup).

## Installation

1. Download the latest `.nvda-addon` file from the [GitHub Releases page](https://github.com/PratikP1/Terminal-Access-for-NVDA/releases/latest).
2. Press Enter on the downloaded file.
3. Confirm installation.
4. Restart NVDA.

## First Steps

### Open a Terminal

Open any supported terminal: Windows Terminal, PowerShell, Command Prompt, WSL, or any of the 30 supported emulators.

You will hear: "Terminal Access support active. Press NVDA+shift+f1 for help."

### Enter the Command Layer

Press **NVDA+apostrophe** to enter the command layer. You will hear "Terminal commands" and a high tone. Every command becomes a single key press.

| Key        | Action             |
|------------|--------------------|
| **I**      | Read current line  |
| **O**      | Read next line     |
| **U**      | Read previous line |
| **K**      | Read current word  |
| **L**      | Read next word     |
| **J**      | Read previous word |
| **Escape** | Exit the layer     |

### More Commands in the Layer

| Key     | Action                          |
|---------|---------------------------------|
| **A**   | Continuous reading (say all)    |
| **;**   | Announce position (row, column) |
| **F**   | Search terminal output          |
| **Q**   | Toggle quiet mode               |
| **F1**  | Open user guide                 |

### Character Reading

| Key                 | Action                           |
|---------------------|----------------------------------|
| **M**               | Read previous character          |
| **,** (comma)       | Read current character           |
| **,** (twice)       | Phonetic reading                 |
| **,** (three times) | Character code (decimal and hex) |
| **.** (period)      | Read next character              |

### Buffer Navigation

| Key               | Action                    |
|-------------------|---------------------------|
| **Home / End**    | Start or end of line      |
| **PageUp / Down** | Top or bottom of buffer   |
| **Shift+Left**    | Read to start of line     |
| **Shift+Right**   | Read to end of line       |
| **Shift+Up**      | Read to top of buffer     |
| **Shift+Down**    | Read to bottom of buffer  |
| **- / =**         | Decrease or increase punctuation |
| **D**             | Toggle indentation announcement  |

### Direct Gestures

All commands also work with NVDA modifier combos without entering the layer:

| Gesture                   | Action                              |
|---------------------------|-------------------------------------|
| **NVDA+I**                | Read current line                   |
| **NVDA+O**                | Read next line                      |
| **NVDA+U**                | Read previous line                  |
| **NVDA+K**                | Read current word                   |
| **NVDA+A**                | Continuous reading (say all)        |
| **NVDA+minus / equals**   | Decrease or increase punctuation    |

These can be remapped in NVDA's Input Gestures dialog under "Terminal Access".

## Command Layer Reference

Enter with **NVDA+apostrophe**. Exit with **Escape**.

### Navigation

| Key                   | Action                              |
|-----------------------|-------------------------------------|
| **U / I / O**         | Previous / current / next line      |
| **J / K / L**         | Previous / current / next word      |
| **M / , / .**         | Previous / current / next character |
| **Home / End**        | Start / end of line                 |
| **PageUp / PageDown** | Top / bottom of buffer              |
| **Shift+Left**        | Read to start of line               |
| **Shift+Right**       | Read to end of line                 |
| **Shift+Up**          | Read to top of buffer               |
| **Shift+Down**        | Read to bottom of buffer            |

### Reading and Information

| Key                 | Action                           |
|---------------------|----------------------------------|
| **A**               | Continuous reading (say all)     |
| **;**               | Announce position (row, column)  |
| **Shift+A**         | Read text attributes and colors  |
| **I** (twice)       | Announce line indentation        |
| **,** (twice)       | Phonetic character reading       |
| **,** (three times) | Character code (decimal and hex) |
| **K** (twice)       | Spell current word               |

### Search and URLs

| Key          | Action                             |
|--------------|------------------------------------|
| **F**        | Search terminal output             |
| **F3**       | Next search match                  |
| **Shift+F3** | Previous search match              |
| **E**        | List URLs found in terminal output |

### Bookmarks

| Key           | Action                       |
|---------------|------------------------------|
| **0-9**       | Jump to bookmark             |
| **Shift+0-9** | Set bookmark at current line |
| **B**         | Open bookmark list dialog    |

### Selection and Copy

| Key   | Action                                         |
|-------|-------------------------------------------------|
| **R** | Toggle mark (start/end)                        |
| **C** | Copy linear selection                          |
| **X** | Clear marks                                    |
| **V** | Enter copy mode (L=line, S=screen, Esc=cancel) |

### Configuration

| Key       | Action                                             |
|-----------|----------------------------------------------------|
| **Q**     | Toggle quiet mode                                  |
| **- / =** | Decrease or increase punctuation level             |
| **D**     | Toggle indentation announcement                    |
| **P**     | Announce active profile. Press twice to select.    |
| **Y**     | Cycle cursor tracking mode                         |

### Tabs, Windows, Help

| Key         | Action                        |
|-------------|-------------------------------|
| **T**       | Create new tab                |
| **Shift+T** | List tabs                     |
| **W**       | Read window content           |
| **Shift+W** | Set window boundaries         |
| **Ctrl+W**  | Clear window                  |
| **S**       | Open Terminal Access settings |
| **F1**      | Open user guide               |
| **Escape**  | Exit command layer            |

## Direct Gesture Reference

### Navigation

| Gesture                   | Action                              |
|---------------------------|-------------------------------------|
| **NVDA+apostrophe**       | Enter or exit command layer         |
| **NVDA+U / I / O**       | Previous / current / next line      |
| **NVDA+J / K / L**       | Previous / current / next word      |
| **NVDA+M / , / .**       | Previous / current / next character |
| **NVDA+Shift+Home / End** | Start / end of line                |
| **NVDA+F4 / F6**         | Top / bottom of buffer              |

### Reading

| Gesture                  | Action                           |
|--------------------------|----------------------------------|
| **NVDA+A**               | Continuous reading (say all)     |
| **NVDA+;**               | Announce position (row, column)  |
| **NVDA+I** (twice)       | Announce line indentation        |
| **NVDA+F5**              | Toggle indentation announcement  |
| **NVDA+,** (twice)       | Phonetic character reading       |
| **NVDA+,** (three times) | Character code (decimal and hex) |
| **NVDA+K** (twice)       | Spell current word               |
| **NVDA+Shift+A**         | Read text attributes and colors  |

### Directional Reading

| Gesture              | Action                   |
|----------------------|--------------------------|
| **NVDA+Shift+Left**  | Read to start of line    |
| **NVDA+Shift+Right** | Read to end of line      |
| **NVDA+Shift+Up**    | Read to top of buffer    |
| **NVDA+Shift+Down**  | Read to bottom of buffer |

### Punctuation and Modes

| Gesture          | Action                                |
|------------------|---------------------------------------|
| **NVDA+minus**   | Decrease punctuation level            |
| **NVDA+equals**  | Increase punctuation level            |
| **NVDA+Alt+Y**   | Cycle cursor tracking mode            |
| **NVDA+Shift+Q** | Toggle quiet mode                     |

### Selection and Copy

| Gesture        | Action                |
|----------------|-----------------------|
| **NVDA+R**     | Toggle mark           |
| **NVDA+C** | Copy linear selection |
| **NVDA+X**     | Clear marks           |
| **NVDA+V**     | Enter copy mode       |

### Bookmarks

| Gesture          | Action                       |
|------------------|------------------------------|
| **Alt+0-9**      | Jump to bookmark             |
| **NVDA+Alt+0-9** | Set bookmark at current line |
| **NVDA+Shift+B** | Open bookmark list dialog    |

### Search and URLs

| Gesture           | Action                       |
|-------------------|------------------------------|
| **NVDA+F**        | Search terminal output       |
| **NVDA+F3**       | Next search match            |
| **NVDA+Shift+F3** | Previous search match        |
| **NVDA+Alt+U**    | List URLs in terminal output |

### Tabs, Windows, Help

| Gesture           | Action                                      |
|-------------------|---------------------------------------------|
| **NVDA+Shift+T**  | Create new tab                              |
| **NVDA+W**        | List tabs                                   |
| **NVDA+Alt+F2**   | Set screen window (press twice: start, end) |
| **NVDA+Alt+F3**   | Clear screen window                         |
| **NVDA+Alt+Plus** | Read window content                         |
| **NVDA+F10**      | Announce profile. Press twice to select.    |
| **NVDA+Shift+F1** | Open user guide                             |

## Settings

Open settings: NVDA menu, Preferences, Settings, Terminal Settings.

| Setting                          | Description                                                          |
|----------------------------------|----------------------------------------------------------------------|
| **Key Echo**                     | Hear characters as you type.                                         |
| **Cursor Tracking**              | Announce cursor movements.                                           |
| **Punctuation Level**            | Control symbol verbosity (None, Some, Most, All).                    |
| **Indentation**                  | Automatically announce indentation for code.                         |
| **Error Audio Cues**             | Play tones on error/warning lines during navigation. On by default.  |
| **Error Audio Cues in Quiet Mode** | Play error/warning tones on caret events while quiet mode is active. Off by default. |
| **Output Activity Tones**        | Play two ascending tones (600+800 Hz) when new program output appears. Off by default. |
| **Output Activity Debounce**     | Minimum interval between activity tones in milliseconds (100 to 10000, default 1000). |

### NVDA Gesture Conflicts

Open NVDA menu, Preferences, Settings, Terminal Settings. The "NVDA Gesture Conflicts" section lists all direct gestures. Uncheck any gesture to disable it and resolve conflicts with other add-ons. Disabled gestures remain accessible through the command layer (NVDA+apostrophe).

### Gesture Scoping

Terminal Access gestures only activate inside supported terminals. Outside a terminal, the gestures pass through to NVDA or other add-ons. Terminal detection uses exact match on the process name.

## Common Tasks

### Reading Command Output

1. Run a command.
2. Press **NVDA+A** for continuous reading.
3. Or press **NVDA+U/I/O** to read line by line.
4. Press **NVDA+Shift+Q** to enable quiet mode if output is verbose.

### Selecting and Copying Text

1. Navigate to selection start.
2. Press **NVDA+R** to mark start.
3. Navigate to selection end.
4. Press **NVDA+R** to mark end.
5. Press **NVDA+C** to copy.
6. Press **NVDA+X** to clear marks.

### Working with Code

1. Enable indentation announcement with **NVDA+F5**.
2. Navigate lines with **NVDA+U/I/O**.
3. Indentation level is announced after each line.
4. Press **NVDA+I** twice to query the current line's indentation.
5. Toggle off with **NVDA+F5** when not needed.

### Finding Characters

1. Navigate to a character.
2. Press **NVDA+comma** three times.
3. Hear the character code (decimal and hex).
4. Useful for finding hidden control characters.

## Tips

1. **Use the command layer.** Press NVDA+apostrophe. Single-key commands are faster than modifier combos.
2. **Use continuous reading.** Press A in the layer to read long output.
3. **Adjust punctuation.** Press minus or equals in the layer to match your task.
4. **Use directional reading.** Shift+Arrow combos scan quickly without moving the cursor.
5. **Use quiet mode.** Press Q in the layer when commands produce verbose output.
6. **Remap gestures.** All commands appear in NVDA's Input Gestures under "Terminal Access".

## Troubleshooting

### Add-on does not activate

- Confirm you are in a supported terminal.
- Check that the add-on is enabled in NVDA, Tools, Manage Add-ons.
- Restart NVDA.

### Commands do not respond

- Try a different terminal application.
- Check for keyboard shortcut conflicts in NVDA Input Gestures.
- Review the NVDA log (NVDA menu, Tools, View log).

## Getting Help

- Press **NVDA+Shift+F1** in any terminal for the full user guide.
- Report issues on [GitHub](https://github.com/PratikP1/Terminal-Access-for-NVDA/issues).
