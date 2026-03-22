# Terminal Access for NVDA

User guide for Terminal Access, an NVDA add-on that adds keyboard-driven navigation, search, bookmarks, and audio cues to 30 Windows terminal applications.

## Quick Start

### Installation

1. Download the latest `.nvda-addon` file from the [GitHub Releases page](https://github.com/PratikP1/Terminal-Access-for-NVDA/releases/latest).
2. Press Enter on the downloaded file.
3. Confirm installation when NVDA prompts.
4. Restart NVDA.

### First Use

Open any supported terminal (Windows Terminal, PowerShell, Command Prompt, WSL, or others). You will hear:

> "Terminal Access support active. Press NVDA+shift+f1 for help."

### The Command Layer

Press **NVDA+apostrophe** to enter the command layer. You will hear "Terminal commands" and a high tone. Every command becomes a single key press. No modifier combos are needed.

Try these keys first:

| Key        | Action             |
|------------|--------------------|
| **I**      | Read current line  |
| **O**      | Read next line     |
| **U**      | Read previous line |
| **K**      | Read current word  |
| **A**      | Read continuously  |
| **Escape** | Exit the layer     |

Press **Escape** or **NVDA+apostrophe** again to leave the command layer.

## Gesture Reference

Terminal Access has two input modes. The **command layer** activates with NVDA+apostrophe and turns every command into a single key press. **Direct gestures** use NVDA+key combos and work without entering the layer.

Terminal Access gestures only activate inside terminal windows. Outside terminals, all NVDA commands work normally.

### Command Layer Keys

Enter with **NVDA+apostrophe**. Exit with **Escape**.

#### Navigation

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

#### Reading and Information

| Key                 | Action                           |
|---------------------|----------------------------------|
| **A**               | Continuous reading (say all)     |
| **;**               | Announce position (row, column)  |
| **Shift+A**         | Read text attributes and colors  |
| **I** (twice)       | Announce line indentation        |
| **,** (twice)       | Phonetic character reading       |
| **,** (three times) | Character code (decimal and hex) |
| **K** (twice)       | Spell current word               |

#### Search and URLs

| Key          | Action                             |
|--------------|------------------------------------|
| **F**        | Search terminal output             |
| **F3**       | Next search match                  |
| **Shift+F3** | Previous search match              |
| **E**        | List URLs found in terminal output |

#### Bookmarks

| Key           | Action                       |
|---------------|------------------------------|
| **0-9**       | Jump to bookmark             |
| **Shift+0-9** | Set bookmark at current line |
| **B**         | Open bookmark list dialog    |

#### Selection and Copy

| Key   | Action                                         |
|-------|-------------------------------------------------|
| **R** | Toggle mark (start/end)                        |
| **C** | Copy linear selection                          |
| **X** | Clear marks                                    |
| **V** | Enter copy mode (L=line, S=screen, Esc=cancel) |

#### Configuration

| Key       | Action                                          |
|-----------|-------------------------------------------------|
| **Q**     | Toggle quiet mode                               |
| **- / =** | Decrease / increase punctuation level           |
| **D**     | Toggle indentation announcement                 |
| **P**     | Announce active profile. Press twice to select.  |
| **Y**     | Cycle cursor tracking mode                      |

#### Tabs and Windows

| Key         | Action                |
|-------------|-----------------------|
| **T**       | Create new tab        |
| **Shift+T** | List tabs             |
| **W**       | Read window content   |
| **Shift+W** | Set window boundaries |
| **Ctrl+W**  | Clear window          |

#### Help and Settings

| Key        | Action                        |
|------------|-------------------------------|
| **F1**     | Open this user guide          |
| **S**      | Open Terminal Access settings |
| **Escape** | Exit command layer            |

### Direct Gestures

These work without entering the command layer.

#### Navigation

| Gesture                   | Action                              |
|---------------------------|-------------------------------------|
| **NVDA+apostrophe**       | Enter or exit command layer         |
| **NVDA+U / I / O**       | Previous / current / next line      |
| **NVDA+J / K / L**       | Previous / current / next word      |
| **NVDA+M / , / .**       | Previous / current / next character |
| **NVDA+Shift+Home / End** | Start / end of line                |
| **NVDA+F4 / F6**         | Top / bottom of buffer              |

#### Reading

| Gesture                  | Action                           |
|--------------------------|----------------------------------|
| **NVDA+A**               | Continuous reading (say all)     |
| **NVDA+;**               | Announce position (row, column)  |
| **NVDA+I** (twice)       | Announce line indentation        |
| **NVDA+,** (twice)       | Phonetic character reading       |
| **NVDA+,** (three times) | Character code (decimal and hex) |
| **NVDA+K** (twice)       | Spell current word               |
| **NVDA+Shift+A**         | Read text attributes and colors  |

#### Directional Reading

| Gesture              | Action                   |
|----------------------|--------------------------|
| **NVDA+Shift+Left**  | Read to start of line    |
| **NVDA+Shift+Right** | Read to end of line      |
| **NVDA+Shift+Up**    | Read to top of buffer    |
| **NVDA+Shift+Down**  | Read to bottom of buffer |

#### Search and URLs

| Gesture           | Action                       |
|-------------------|------------------------------|
| **NVDA+F**        | Search terminal output       |
| **NVDA+F3**       | Next search match            |
| **NVDA+Shift+F3** | Previous search match        |
| **NVDA+Alt+U**    | List URLs in terminal output |

#### Bookmarks

| Gesture          | Action                       |
|------------------|------------------------------|
| **Alt+0-9**      | Jump to bookmark             |
| **NVDA+Alt+0-9** | Set bookmark at current line |
| **NVDA+Shift+B** | Open bookmark list dialog    |

#### Selection and Copy

| Gesture    | Action                |
|------------|-----------------------|
| **NVDA+R** | Toggle mark           |
| **NVDA+C** | Copy linear selection |
| **NVDA+X** | Clear marks           |
| **NVDA+V** | Enter copy mode       |

#### Modes and Settings

| Gesture                 | Action                                                    |
|-------------------------|-----------------------------------------------------------|
| **NVDA+minus / equals** | Decrease / increase punctuation level                     |
| **NVDA+Alt+Y**          | Cycle cursor tracking mode                                |
| **NVDA+Shift+Q**        | Toggle quiet mode                                         |
| **NVDA+F5**             | Toggle indentation announcement                           |
| **NVDA+F10**            | Announce active profile. Press twice to select a profile. |

#### Tabs and Windows

| Gesture           | Action                                      |
|-------------------|---------------------------------------------|
| **NVDA+Shift+T**  | Create new tab                              |
| **NVDA+W**        | List tabs                                   |
| **NVDA+Alt+F2**   | Set screen window (press twice: start, end) |
| **NVDA+Alt+F3**   | Clear screen window                         |
| **NVDA+Alt+Plus** | Read window content                         |

#### Help

| Gesture           | Action               |
|-------------------|----------------------|
| **NVDA+Shift+F1** | Open this user guide |

All gestures can be remapped in NVDA's Input Gestures dialog under the "Terminal Access" category.

## Features

### Navigation

Move through terminal output by line, word, or character. Jump to the start or end of a line, or to the top or bottom of the buffer. Read continuously with say all. Read in any direction from the current position.

Example: press NVDA+O three times to move down three lines. Press NVDA+K to hear the word at the cursor. Press NVDA+K twice to spell it letter by letter.

### Search

Press NVDA+F (or F in the command layer) to search terminal output. Type your search term and press Enter. If matches are found, a results dialog opens showing the match number, line number, and line content for each hit. Select a match and press Enter to jump there. Press F3 or Shift+F3 to move between matches after closing the dialog. If nothing is found, you hear a low tone and a message with the search term.

Example: run `pip install requests`, then press NVDA+F, type "error", and press Enter. If the install failed, the results dialog lists every error line. Select one and press Enter to review it.

### Bookmarks

Set up to 10 bookmarks (0 through 9) at any line. The full line text is captured as a label so you can identify it later. Press B in the command layer (or NVDA+Shift+B) to open the bookmark list dialog. The dialog shows two columns: bookmark number and line content. Press Enter to jump to a bookmark. Press Delete to remove one. Bookmarks are isolated per tab in Windows Terminal.

Example: while reading a long build log, navigate to an important error line and press Shift+1 in the command layer to set bookmark 1. Continue reading. Later press 1 to jump back to that error. Press B to see all your bookmarks in a list.

### Error and Warning Audio Cues

Terminal Access plays audio cues when you navigate to lines that contain errors or warnings.

| Tone      | Frequency | Meaning                                      |
|-----------|-----------|----------------------------------------------|
| Low tone  | 220 Hz    | Error (compilation failure, exception, crash) |
| Mid tone  | 440 Hz    | Warning (deprecation, caution)               |

The detector uses word-boundary matching to recognize structured patterns from compilers, linters, and shells. It matches output from GCC, Clang, MSVC, Rust, Python, TypeScript, ESLint, Go, Java, Maven, Git, Docker, Make, and CMake, among others.

Examples of lines that trigger the error tone:

- `main.c:5:12: error: expected ';' before 'int'`
- `Traceback (most recent call last):`
- `FAILED tests/test_main.py::test_login`
- `fatal: 'origin' does not appear to be a git repository`
- `npm ERR! 404 Not Found`
- `bash: foo: command not found`

Examples of lines that trigger the warning tone:

- `main.c:5:12: warning: unused variable 'x'`
- `DeprecationWarning: old API is deprecated`
- `[WARNING] Using platform encoding`

Normal text like "mirror", "forewarning", or help text containing "cannot" does not trigger false positives. The detector checks for structured delimiters (colons, brackets, specific phrases) rather than bare substrings.

You can disable audio cues in Terminal Settings by unchecking "Error and Warning Audio Cues".

### Error Audio Cues in Quiet Mode

When quiet mode is active, Terminal Access suppresses speech but can still play error and warning tones on caret events. Enable "Error Audio Cues in Quiet Mode" in settings to hear a beep when an error line scrolls past during fast output, even though speech is off.

Example: you run `cargo build` with quiet mode on. The build produces hundreds of lines of output silently. If a compilation error appears, you hear a low 220 Hz tone. You can then exit quiet mode (NVDA+Shift+Q) and review the output to find the error.

### Output Activity Tones

Enable "Output Activity Tones" in settings to hear two ascending tones (600 Hz then 800 Hz) whenever new program output appears on screen. This tells you "something is happening" without reading every line.

The tones play only for program output, not for characters you type. After the tones play, they are suppressed for a configurable interval (default: 1 second) so rapid output does not produce continuous beeping. Adjust the debounce interval in settings under "Output Activity Debounce" (100 to 10000 milliseconds).

Example: you run `apt update` and switch to another window. When you return to the terminal, the ascending tones tell you that output appeared while you were away. A longer debounce (5000ms) means you hear the tone once every 5 seconds during sustained output, giving you a periodic "heartbeat" that the command is still running.

### Application Profiles

Terminal Access adjusts settings automatically based on the running application.

| Profile        | Settings                                     |
|----------------|----------------------------------------------|
| **Vim/Neovim** | Punctuation MOST, silent status line         |
| **tmux**       | Silent status bar                            |
| **htop**       | Separate regions for header and process list |
| **less/more**  | Quiet mode, key echo disabled                |
| **Git**        | Punctuation MOST for diffs                   |
| **GNU nano**   | Silent shortcut bar                          |
| **irssi**      | Chat-optimized punctuation                   |
| **WSL**        | Punctuation MOST for Linux paths             |

Press P in the command layer (or NVDA+F10) to check which profile is active. Press NVDA+F10 twice to open the profile selection dialog, which lists all profiles. Press Enter on a profile to activate it. You can create, export, and import custom profiles through the settings panel.

### URL Extraction

Press E in the command layer (or NVDA+Alt+U) to scan the terminal buffer for URLs. A dialog opens with a filter box, a list of URLs with line numbers and context, and buttons for opening, copying, or navigating. Supports HTTP, HTTPS, FTP, www-prefixed links, and OSC 8 hyperlinks. File URLs are listed but blocked from opening for security.

Example: after running `git remote -v`, press E to list the repository URLs. Select one and press Alt+C to copy it, or Alt+O to open it in your browser.

### Tab Management

Terminal Access tracks Windows Terminal tabs. Bookmarks, searches, and settings stay isolated per tab. Use T or Shift+T in the command layer (or NVDA+Shift+T and NVDA+W) to create and list tabs. Tab switches are detected automatically.

### Color and Formatting

Press Shift+A in the command layer (or NVDA+Shift+A) to hear colors and formatting at the cursor. The ANSI parser supports 8 standard colors, bright colors, 256-color palette, RGB/TrueColor, bold, dim, italic, underline, blink, inverse, and strikethrough.

Example: in a diff output, navigate to a changed line and press Shift+A. You might hear "green foreground, bold" indicating an added line.

### Selection and Copy

Set a start mark with NVDA+R, navigate to the end, press NVDA+R again to set the end mark, then NVDA+C to copy. Press NVDA+X to clear marks. Copy mode (V in the command layer or NVDA+V) offers quick copy by line or by screen.

Example: navigate to the first line of a stack trace. Press NVDA+R to mark the start. Navigate to the last line and press NVDA+R again. Press NVDA+C to copy the entire stack trace to the clipboard.

### Quiet Mode

Press NVDA+Shift+Q (or Q in the command layer) to toggle quiet mode. Quiet mode suppresses cursor tracking and key echo so fast-scrolling output does not overwhelm the speech synthesizer. Navigation commands (NVDA+U/I/O) still work and still speak.

Example: you run a long `make` build. Press NVDA+Shift+Q to silence the output. If "Error Audio Cues in Quiet Mode" is enabled, you hear a beep if the build fails. Press NVDA+Shift+Q again to re-enable speech and review the output.

## Settings

Open settings from the NVDA menu: Preferences, Settings, Terminal Settings. The panel has three sections: Speech and Tracking, NVDA Gesture Conflicts, and Application Profiles.

### Speech and Tracking

| Setting               | Description                                                                     |
|-----------------------|---------------------------------------------------------------------------------|
| **Cursor Tracking**   | Announces the character at the cursor when it moves.                            |
| **Key Echo**          | Announces each character as you type.                                           |
| **Quiet Mode**        | Suppresses cursor tracking and key echo. Toggle with NVDA+Shift+Q.              |
| **Punctuation Level** | Controls how many symbols are announced. Adjust with NVDA+minus and NVDA+equals.|

#### Punctuation Levels

| Level    | Symbols Announced                                                    |
|----------|----------------------------------------------------------------------|
| 0 (None) | No punctuation                                                       |
| 1 (Some) | Period, comma, question mark, exclamation, semicolon, colon          |
| 2 (Most) | Most symbols including at, hash, dollar, brackets, braces, operators |
| 3 (All)  | Every symbol                                                         |

#### Advanced Speech and Tracking

| Setting                       | Description                                                              |
|-------------------------------|--------------------------------------------------------------------------|
| **Cursor Tracking Mode**      | Off, Standard (default), or Window (only within defined screen regions). |
| **Cursor Delay**              | Milliseconds (0 to 1000) before announcing cursor moves. Default: 20ms. |
| **Indentation on Line Read**  | Announces indentation depth after each line. Toggle with NVDA+F5.        |
| **Condense Repeated Symbols** | Announces "3 equals" instead of "equals equals equals".                  |
| **Repeated Symbols**          | Which symbols to condense. Default: hyphen, underscore, equals, exclamation. |
| **Default Profile**           | Profile to use when no app-specific profile is detected.                 |

### Audio Cues

| Setting                            | Default | Description                                                     |
|------------------------------------|---------|-----------------------------------------------------------------|
| **Error and Warning Audio Cues**   | On      | Play tones on error/warning lines during line navigation.       |
| **Error Audio Cues in Quiet Mode** | Off     | Play error/warning tones on caret events while quiet mode is active. Lets you hear errors during fast output without speech. |
| **Output Activity Tones**          | Off     | Play two ascending tones when new program output appears. Does not play during typing. Works in both normal and quiet mode. |
| **Output Activity Debounce**       | 1000ms  | Milliseconds between activity tone repeats (100 to 10000). Higher values mean fewer tones during sustained output. |

### NVDA Gesture Conflicts

Some Terminal Access gestures override NVDA's default global commands inside terminal windows. For example, NVDA+F normally reports text formatting, but Terminal Access uses it for search.

The NVDA Gesture Conflicts section lists only these overlapping gestures. Uncheck any gesture to restore its NVDA default behavior inside terminals. Unchecked gestures remain available through the command layer (NVDA+').

To customize gestures that do not conflict with NVDA defaults, use NVDA's Input Gestures dialog (Preferences, Input Gestures) and look under the Terminal Access category.

If you need the full list of all Terminal Access gestures in this settings panel, open an issue on [GitHub](https://github.com/PratikP1/Terminal-Access-for-NVDA/issues).

## Supported Terminals

### Built-in Windows Terminals (5)

Windows Terminal, Windows PowerShell, PowerShell Core (pwsh), Command Prompt (cmd.exe), Console Host (conhost.exe).

### Windows Subsystem for Linux

WSL1 and WSL2, all distributions. Detected automatically with an optimized profile.

### Third-Party Terminal Emulators (24)

Cmder, ConEmu (32-bit and 64-bit), mintty (Git Bash, Cygwin), PuTTY, KiTTY, Terminus, Hyper, Alacritty, WezTerm, Tabby, FluentTerminal, Ghostty, Rio, Wave Terminal, Contour, Cool Retro Term, MobaXterm, SecureCRT, Tera Term, mRemoteNG, Royal TS.

**Total: 30 supported terminals including WSL.**

## Troubleshooting

### Terminal Access does not activate

Confirm you are in a supported terminal. Check that the add-on is enabled under NVDA, Tools, Manage Add-ons. Restart NVDA.

### A gesture conflicts with NVDA or another add-on

Terminal Access gestures only activate inside terminal windows. Outside terminals, NVDA's own commands work normally. If a gesture conflicts with NVDA's defaults inside a terminal, open Terminal Access settings and uncheck it in the NVDA Gesture Conflicts section. The command will still be available through the command layer (NVDA+'). For conflicts with other add-ons, use NVDA's Input Gestures dialog to reassign the gesture.

### No speech when moving the cursor

Check that cursor tracking is not set to Off. Press NVDA+Alt+Y to cycle tracking modes. Make sure quiet mode is not active (toggle with NVDA+Shift+Q). Try setting cursor delay to 0ms in settings.

### Punctuation is not announced

Increase the punctuation level with NVDA+equals. Level 0 suppresses all punctuation. Level 2 works well for code. Level 3 announces every symbol.

### Profile does not apply automatically

Press NVDA+F10 to see which profile is active. Open the NVDA Python Console (NVDA+Control+Z) and type `api.getForegroundObject().appModule.appName` to verify the application name matches the profile.

### Error tones play on lines that are not errors

Open an issue on [GitHub](https://github.com/PratikP1/Terminal-Access-for-NVDA/issues) with the exact line text that triggered a false positive. You can disable error tones entirely in Terminal Settings by unchecking "Error and Warning Audio Cues".

## Deprecated Features

These features still work but will be removed in version 2.

| Feature                   | Gestures                              | Reason                                   |
|---------------------------|---------------------------------------|------------------------------------------|
| **Command History**       | NVDA+H/G, NVDA+Shift+H, NVDA+Shift+L | Shells have built-in history navigation. |
| **Highlight tracking**    | Cycle with NVDA+Alt+Y                 | Modern terminals strip ANSI from UIA.    |
| **Rectangular selection** | NVDA+Shift+C                          | Linear copy covers most needs.           |

If you rely on any of these, open an issue on [GitHub](https://github.com/PratikP1/Terminal-Access-for-NVDA/issues) before they are removed.

## System Requirements

- Windows 10 or Windows 11
- NVDA 2025.1 or later

## Credits

Terminal Access is inspired by [TDSR](https://github.com/tspivey/tdsr) by Tyler Spivey and [Speakup](https://github.com/linux-speakup/speakup), the Linux kernel screen reader.

## License

Copyright (C) 2024 Pratik Patel. Licensed under the GNU General Public License v3.0 or later. See the LICENSE file for details.

[Project Repository](https://github.com/PratikP1/Terminal-Access-for-NVDA)
