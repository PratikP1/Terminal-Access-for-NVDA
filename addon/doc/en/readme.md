# Terminal Access for NVDA

Terminal Access adds keyboard-driven review navigation, search, bookmarks, and audio cues to 30 Windows terminal applications, including Windows Terminal, PowerShell, Command Prompt, WSL, and popular third-party emulators. It gives you line, word, and character navigation through terminal output without moving the cursor, so you can read command results the way you read a document.

Open this guide any time from inside a terminal by pressing **NVDA+Shift+F1**.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Command Layer](#command-layer)
3. [Buffer Window](#buffer-window)
4. [Table Mode](#table-mode)
5. [Bookmarks](#bookmarks)
6. [Error and Warning Detection](#error-and-warning-detection)
7. [Gesture Conflict Detection](#gesture-conflict-detection)
8. [Application Profiles](#application-profiles)
9. [Third-Party Terminal Support](#third-party-terminal-support)
10. [Window Definitions](#window-definitions)
11. [Unicode and CJK Text](#unicode-and-cjk-text)
12. [Performance](#performance)
13. [AI CLI Support](#ai-cli-support)
14. [Settings](#settings)
15. [Troubleshooting](#troubleshooting)
16. [Getting Help](#getting-help)

---

## Getting Started

### Installation

1. Download the latest `.nvda-addon` file from the [Releases page](https://github.com/PratikP1/Terminal-Access-for-NVDA/releases/latest).
2. Press Enter on the downloaded file.
3. Confirm the prompt.
4. Restart NVDA.

Terminal Access requires Windows 10 or 11 and NVDA 2025.1 or later.

### First Steps

Open any supported terminal. When Terminal Access recognizes it, you hear: "Terminal Access support active. Press NVDA+shift+f1 for help."

You read terminal output in two ways:

- **Direct gestures**: NVDA modifier combinations such as **NVDA+I** to read the current line. These work at any time inside a terminal.
- **Command layer**: Press **NVDA+apostrophe** to enter a mode where every command is a single key press. You hear "Terminal commands" and a high tone. Press **Escape** to leave.

The command layer is faster for a sequence of commands and avoids clashes with other add-ons. Both routes run the same commands, and you can remap every gesture in NVDA's Input Gestures dialog under "Terminal Access".

### Essential Reading Commands

These few commands cover most reading. The first column is the key inside the command layer; the second is the equivalent direct gesture.

| Command layer | Direct gesture | Action |
|---------------|----------------|--------|
| **I / O / U** | **NVDA+I / O / U** | Read current / next / previous line |
| **K / L / J** | **NVDA+K / L / J** | Read current / next / previous word |
| **comma / period / M** | **NVDA+comma / period / M** | Read current / next / previous character |
| **A** | **NVDA+A** | Continuous reading (say all) |
| **semicolon** | **NVDA+semicolon** | Announce position (row, column) |
| **Escape** | | Exit the command layer |

The full reference for every command is in the next section.

---

## Command Layer

The command layer is a modal input mode that runs Terminal Access commands with single-key presses instead of multi-key NVDA modifier combinations. This avoids conflicts with other NVDA add-ons and makes commands faster to type.

### Entering and Exiting

| Gesture                        | Action                                                                   |
|--------------------------------|--------------------------------------------------------------------------|
| **NVDA+apostrophe**            | Enter the command layer. You hear "Terminal commands" and a high tone.    |
| **Escape** or **NVDA+apostrophe** | Exit the command layer. You hear "Exit terminal commands" and a low tone. |

The layer stays active until you exit. Each command keeps you in the layer so you can chain commands. The layer exits on its own when focus leaves the terminal.

### Command Reference

While in the command layer, these keys are active:

#### Navigation
| Key | Action |
|-----|--------|
| **U / I / O** | Read previous / current / next line |
| **J / K / L** | Read previous / current / next word |
| **M / comma / period** | Read previous / current / next character |
| **Home / End** | Jump to start / end of line |
| **PageUp / PageDown** | Jump to top / bottom of buffer |
| **Shift+Left / Right** | Read to start / end of line |
| **Shift+Up / Down** | Read to top / bottom of buffer |

#### Information and Reading
| Key | Action |
|-----|--------|
| **A** | Continuous reading (say all) |
| **semicolon** | Announce position (row, column) |
| **Shift+A** | Read text attributes and colors |
| **I** (twice) | Announce line indentation |
| **comma** (twice) | Phonetic character reading |
| **comma** (three times) | Character code |
| **K** (twice) | Spell current word |

#### Selection and Copying
| Key | Action |
|-----|--------|
| **R** | Toggle mark (start/end) |
| **C** | Copy linear selection |
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
| **minus / equals** | Decrease / increase punctuation level |
| **D** | Toggle indentation announcement |
| **P** | Announce active profile. Press twice to select. |

#### Bookmarks
| Key | Action |
|-----|--------|
| **0-9** | Jump to bookmark |
| **Shift+0-9** | Set bookmark at current line (line text is captured as a label) |
| **B** | Open bookmark list dialog (shows bookmark number and line content; press Enter to jump, Delete to remove) |

#### Tabs
| Key | Action |
|-----|--------|
| **T** | Create new tab |
| **Shift+T** | List tabs |

#### Search and URL List
| Key | Action |
|-----|--------|
| **E** | List URLs found in terminal output |
| **F** | Search terminal output |
| **F3** | Next search match |
| **Shift+F3** | Previous search match |

The search dialog has a text box plus two options: **Case sensitive** (match letter case exactly) and **Regular expression** (treat the text as a Python regular expression). Both remember their setting for the next search in the session. If a regular expression is invalid, you hear a short message and the search is not run.

Search opens a results dialog listing every matching line. Activating a result (Enter or the Activate button) closes the dialog and places the review cursor at the beginning of the matched line, the same way a bookmark jump does, so review-current-line reads the match. After the dialog closes, F3 and Shift+F3 continue through the remaining matches, announcing each match's position as "N of M" and saying "Wrapped" when navigation loops back to the start. If a search finds nothing, close fuzzy matches (one typo away) are offered instead.

Search results are taken at the moment you search. If the program then prints more output, the next find-next or find-previous re-runs the search against the current buffer so the results stay accurate, keeping your place on the same matched line where possible. Results are remembered per terminal window for the current NVDA session; they are not saved across an NVDA restart.

#### Table Mode
| Key | Action |
|-----|--------|
| **G** | Toggle table mode on the table under the review cursor |

#### Buffer Window
| Key | Action |
|-----|--------|
| **Enter** | Open the buffer window (a browsable snapshot of the whole buffer) |
| **Shift+Enter** | Open the jump to line dialog |
| **Shift+E** | Open the errors-only buffer window |
| **Shift+C** | Open the commands-only buffer window |

#### Help and Settings
| Key | Action |
|-----|--------|
| **F1** | Open user guide |
| **S** | Open Terminal Access settings |
| **Escape** | Exit command layer |

### Copy Mode Within the Layer

When you press **V** in the command layer, you enter copy mode. The keys **L** (copy line), **S** (copy screen), and **Escape** (cancel) temporarily override their layer bindings. When copy mode exits, those bindings are restored.

### Customizing Gestures

All Terminal Access commands, both layer and direct, are registered under the "Terminal Access" category in NVDA's Input Gestures dialog. You can remap any gesture.

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

Supported URL types: HTTP/HTTPS, FTP, www-prefixed, and OSC 8 terminal hyperlinks. Duplicate URLs are removed automatically.

**Security note:** URLs with `file://`, `javascript:`, or other non-web schemes are detected and listed but cannot be opened from the dialog. Attempting to open one produces the spoken message "Cannot open this URL type for security reasons." This stops malicious terminal output from tricking you into launching dangerous local resources.

---

## Buffer Window

The buffer window takes a snapshot of everything in the terminal's scrollback and opens it in a browsable NVDA window. Inside it you read with the browse mode commands you already know: the arrow keys move line by line, H moves by heading, NVDA's find command searches the text, the Copy button copies everything, and Escape closes the window and returns you to the terminal. Nothing in the window can move under you while you read, because it is a frozen copy, not the live terminal.

### Opening the Window

| Gesture | Command layer key | Action |
|---------|-------------------|--------|
| **NVDA+Enter** | **Enter** | Open the whole buffer |
| none | **Shift+E** | Open only the errors, warnings, and stack traces |
| none | **Shift+C** | Open only the commands you ran |

The filtered windows say so in their titles, for example "PowerShell buffer snapshot, errors only", so a filtered view cannot be mistaken for the whole buffer. If a filter finds nothing, Terminal Access announces that instead of opening an empty window.

### Structure and Headings

The window marks the buffer's structure with headings so the H key moves you through it quickly:

- Heading level 1 is the terminal itself.
- Heading level 2 is each command you ran (each prompt line).
- Heading level 3 is the start of each error, warning, or stack trace. An error and the stack trace under it count as one heading, not two.

Ordinary output is never a heading, so pressing H only lands somewhere meaningful. A table of contents at the top of the window links every command and error, letting you reach any part of a long buffer without arrowing through it.

Columnar output such as `docker ps` or `ls -l` is rendered as a real table, so NVDA's table navigation commands work and announce the column header for each cell. Column detection uses the same experimental heuristic as table mode; when Terminal Access is not confident, output stays as plain lines, because a wrong table is worse than no table.

Web addresses in the output become real links you can activate. Addresses with unsafe schemes (file, javascript, data) are never turned into links; they stay as plain text. This is the same protection the URL list applies.

### The Window Is Read-Only

The buffer window is for reading. Pressing Enter inside it does not move the terminal's review cursor. To act on a line you found, use the jump to line dialog described next.

### Jump to Line

Press **NVDA+Shift+Enter** (or **Shift+Enter** in the command layer) to open the jump to line dialog: a list of every line in the buffer with three columns, the line number, the line's text, and the command that produced it. Type in the filter box to narrow the list by the line's text or by the command. Press Enter on a line to close the dialog and move the review cursor to that line in the live terminal.

The landing is found by matching the line's text, not by counting lines, so it stays correct even though terminals number lines inconsistently. If the line has scrolled out of the terminal's history by the time you jump, Terminal Access says "Could not reach that line. It may have scrolled out of the terminal history." instead of leaving you guessing.

### What a Snapshot Is and Is Not

- The window is frozen at the moment you open it. New terminal output does not appear inside it. To see newer output, close the window and open it again; every open captures a fresh snapshot.
- The window holds what the terminal still holds. Terminals limit their own scrollback (PowerShell keeps roughly the most recent 9,000 lines by default), so lines the terminal has dropped cannot appear in the snapshot either. Terminal Access caps a snapshot at 50,000 lines, far beyond any default scrollback; if the cap ever applies, the window title says "most recent 50,000 of" however many lines the buffer held.
- On the legacy Windows console, NVDA itself can only read the visible screen. Terminal Access reads that console's full screen buffer directly instead, so the buffer window and search both see the scrollback there, not just what is on display. If that direct read is unavailable for any reason, Terminal Access falls back to what NVDA exposes, and the window then shows only the visible screen.

### Note for Laptop Keyboard Layout Users

On NVDA's laptop keyboard layout, NVDA+Enter is NVDA's own command to activate the current navigator object. Terminal Access takes this gesture only inside supported terminals, where activating a navigator object rarely applies. If you need NVDA's command while in a terminal, use the command layer's Enter instead, or reassign either gesture in the Input Gestures dialog. This overlap is listed in the NVDA Gesture Conflicts section of the Terminal Access settings.

---

## Table Mode

Terminal programs often print tabular output such as `docker ps`, `kubectl get pods`, `ls -l`, `psql` result grids, and Markdown pipe tables. Read as plain lines, these become long run-on strings where a value is hard to match to its column. Table mode reads the output column by column and announces the header for each cell, so you always know which column you are in.

### Entering and Exiting

Move the review cursor onto any line of the table, then press **G** in the command layer (or **NVDA+Alt+G** directly). If a table is detected at that position, table mode activates and the arrow keys navigate cells. If no table is found, you hear "No table at this position".

Press **Escape** or toggle the command again to leave table mode. Table mode also exits on its own when focus leaves the terminal.

### Navigating Cells

While table mode is active, these keys navigate the detected table:

| Key | Action |
|-----|--------|
| **Up / Down Arrow** | Previous / next row |
| **Left / Right Arrow** | Previous / next column |
| **Home / End** | First / last column in the row |
| **Ctrl+Up Arrow** | Announce the header of the current column |
| **Space** | Read a summary of the current row |
| **Escape** | Exit table mode |

Each cell is announced with its column header followed by the cell value, so you can move down a column and compare values without losing track of what they mean.

### Supported Table Shapes

Table mode recognizes two shapes:

| Shape | Examples |
|-------|----------|
| **Aligned columns** | Space-padded output such as `docker ps`, `kubectl get pods`, and `ls -l` |
| **Pipe tables** | Markdown-style tables and `psql` grids that use `|` separators |

### Column Detection Is Heuristic (Experimental)

Table mode's column detection is heuristic. It infers where columns begin and end from the alignment of spaces and pipe characters in the visible text, because terminal output carries no structural markup describing its columns. This works well for the common tools listed above, but unusual spacing, wrapped lines, cells that contain multiple spaces, or wide (CJK) characters can place a column boundary in the wrong spot.

This behavior will be refined in future updates as we gather testing results and user reports of tables that are not detected or split correctly. If you hit a table that reads incorrectly, please report it with a sample of the output so the detection can be improved.

---

## Bookmarks

Bookmarks let you save and revisit specific lines in the terminal buffer.

### Setting Bookmarks

Press **Shift+0** through **Shift+9** in the command layer (or **NVDA+Alt+0** through **NVDA+Alt+9** directly) to set a bookmark at the current line. The line's text is captured as a label so you can identify it later.

### Jumping to Bookmarks

Press **0-9** in the command layer (or **Alt+0** through **Alt+9** directly) to jump to that bookmark.

### Bookmark List Dialog

Press **B** in the command layer (or **NVDA+Shift+B** directly) to open an interactive list. The dialog shows two columns: bookmark number and line content. Press Enter to jump to the selected bookmark, or Delete to remove it.

Bookmarks are kept per terminal window and persist while that window is open, including when focus leaves and returns. Separate terminal windows keep their own bookmarks. Note that several tabs inside a single Windows Terminal window share one window, so they share the same bookmarks. Bookmarks are held for the current NVDA session only; they are not saved across an NVDA restart. Up to 50 bookmarks are kept per window; once that limit is reached, setting a new one announces "Bookmark limit reached" until you delete one.

Because terminal output scrolls, a bookmark points at a line by its content. Jumping to a bookmark re-finds that line, which is reliable while the line is still in the buffer; if the line has scrolled out of the terminal's history, the jump may not land.

---

## Error and Warning Detection

Terminal Access plays audio cues when you navigate to lines that contain errors or warnings. This helps you scan build output, test results, or log files by ear.

- **Error lines** produce a low-pitched tone.
- **Warning lines** produce a higher-pitched tone.

The detector recognizes common patterns from compilers, linters, and shell output, such as `error:`, `ERROR`, `warning:`, and `WARN`.

### Audio Cue Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| **Error Audio Cues** | boolean | True | Play tones on error/warning lines during navigation. |
| **Error Audio Cues in Quiet Mode** | boolean | False | Play error/warning tones on caret events while quiet mode is active. |
| **Output Activity Tones** | boolean | False | Play two ascending tones (600+800 Hz) when new program output appears. |
| **Output Activity Debounce** | integer | 1000 ms | Minimum interval between activity tones. Range: 100 to 10000 ms. |

Configure these in NVDA menu > Preferences > Settings > Terminal Settings.

### Gesture Scoping

Terminal Access gestures only activate inside supported terminals. Outside a terminal the gestures pass through to NVDA or other add-ons. Terminal detection uses an exact match on the process name.

---

## Gesture Conflict Detection

Terminal Access detects when its keyboard shortcuts conflict with other installed NVDA add-ons. When it finds a conflict, it warns you so you can decide which binding to keep.

To resolve conflicts:

1. Open NVDA menu > Preferences > Settings > Terminal Settings.
2. In the "NVDA Gesture Conflicts" section, uncheck any gesture you want to disable.
3. Disabled direct gestures remain accessible through the command layer (NVDA+apostrophe).

The command layer and help gestures (NVDA+Shift+F1) cannot be disabled.

---

## Application Profiles

Application profiles adjust Terminal Access settings based on the terminal application you are using. Each profile can customize punctuation levels, cursor tracking modes, and window regions for specialized behavior.

### Understanding Profiles

Terminal Access ships with default profiles for popular applications:

- **vim/nvim**: Punctuation MOST (for code symbols), cursor tracking WINDOW mode, silent zones for the status line and command line.
- **tmux**: Cursor tracking STANDARD mode, silent zone for the status bar.
- **htop**: Repeated symbols disabled (progress bars repeat characters), window regions for the header (lines 1-4) and process list (lines 5+).
- **less/more**: Quiet mode enabled, key echo disabled.
- **git**: Punctuation MOST (symbols in diffs), repeated symbols disabled.
- **nano**: Cursor tracking STANDARD mode, silent zones for the status and shortcut bars.
- **irssi**: Punctuation SOME, line pause disabled for fast chat reading, silent zone for the status bar.
- **WSL**: Punctuation MOST (code-friendly for Linux commands and paths), cursor tracking STANDARD mode, repeated symbols off.

### Managing Profiles

View, export, import, and delete profiles from NVDA menu > Preferences > Settings > Terminal Settings > Application Profiles. The "Installed profiles" dropdown lists default profiles first, then custom profiles alphabetically.

- **Export**: Select a profile and click "Export..." to save it as a JSON file with all settings and window definitions.
- **Import**: Click "Import..." and choose a profile JSON file. A profile with the same name is replaced.
- **Delete**: Select a custom profile and click "Delete Profile". Default profiles (vim, tmux, htop, less, git, nano, irssi) cannot be deleted.

### Profile Setting Overrides

When a profile is active, its settings override the global Terminal Access settings. For example, if the `less` profile sets key echo off, key echo is disabled while `less` runs, regardless of the global setting.

If you toggle a setting such as quiet mode while a profile is active, the change is saved to that profile's overrides rather than the global settings. When you switch to a different application, the global settings return.

### Creating Custom Profiles

Create a custom profile by exporting an existing one as a template, editing the JSON, and importing it back:

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

Terminal Access supports 30 terminals: the 5 built-in Windows terminals, WSL, and 24 third-party emulators. It detects them automatically when you switch to them, and each has a default profile tuned for common use.

### Built-in Windows Terminals

Windows Terminal, cmd (Command Prompt), powershell (Windows PowerShell), pwsh (PowerShell Core), and conhost (Console Host).

### Third-Party Terminal Emulators

Cmder, ConEmu, mintty (Git Bash and Cygwin), PuTTY and KiTTY, Terminus, Hyper, Alacritty, WezTerm, Tabby, FluentTerminal, Ghostty, Rio, Wave Terminal, Contour, Cool Retro Term, MobaXterm, SecureCRT, Tera Term, mRemoteNG, and Royal TS.

### Default Profiles by Category

| Category | Terminals | Punctuation | Cursor tracking |
|----------|-----------|-------------|-----------------|
| General | Cmder, ConEmu, Terminus, Hyper, Tabby, FluentTerminal | SOME | STANDARD |
| Development | mintty (Git Bash) | MOST | STANDARD |
| Remote access | PuTTY, KiTTY | SOME | STANDARD |
| High performance | Alacritty, WezTerm | SOME | STANDARD |

All Terminal Access features work with third-party terminals: navigation, selection, cursor tracking, punctuation levels, and window definitions. To customize a terminal, use it, open NVDA Settings > Terminal Access, adjust settings, and export the profile for backup or sharing.

---

## Window Definitions

Window definitions mark regions of the terminal screen with different speech behaviors. This helps with applications that have status bars, command areas, or split panes.

### Basics

Each window definition has a name, coordinates (top, bottom, left, right), a mode, and an enabled flag.

Coordinates are 1-based, so row 1, column 1 is the top-left. The value **9999** means "last row or column".

### Window Modes

| Mode | Behavior |
|------|----------|
| **announce** | Read content normally (default) |
| **silent** | Suppress all speech for this region |
| **monitor** | Track changes but announce differently |

### Example: Vim Status Line

```json
[
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
]
```

This reads all lines except the last (the editor region) normally and silences the last line (the status bar). Common uses include silencing status bars, defining tmux or screen panes, handling htop headers, and monitoring command input regions.

---

## Unicode and CJK Text

Terminal Access handles double-width characters, right-to-left text, and complex emoji sequences.

### CJK Characters

Chinese, Japanese, and Korean characters count as 2 columns, so column-based operations line up correctly. Zero-width combining marks are handled properly.

```
Hello世界   # "Hello" = 5 columns, "世界" = 4 columns, total = 9 columns
```

### Right-to-Left Text

Terminal Access detects Arabic and Hebrew by character range and applies the Unicode bidirectional algorithm (UAX #9), including Arabic contextual reshaping and mixed RTL/LTR text.

For full RTL support, install the optional libraries:

```bash
pip install python-bidi arabic-reshaper
```

Without them, Terminal Access falls back to basic Unicode support.

### Emoji

Terminal Access handles zero-width joiner sequences (family and profession emoji), skin tone modifiers, variation selectors, and flag sequences. Emoji are typically 2 columns wide.

For full emoji support, install the optional library:

```bash
pip install emoji
```

---

## Performance

Terminal Access includes optimizations for large terminal buffers.

- **Position caching**: Position calculations are cached for up to 100 positions with a 1-second timeout, and invalidated on content changes, resize, or terminal switch. A calculation that is O(n) on first access becomes O(1) when cached.
- **Incremental tracking**: Small cursor movements (within 10 positions) are 10 to 20 times faster than a full calculation, with automatic fallback for large jumps.
- **Background processing**: Selections over 100 rows run in a background thread with a progress dialog and cancellation support.
- **Pure Python**: The add-on contains no compiled components. Earlier 2.0.0 betas bundled a native library and helper process for terminal reads; both were removed after field testing showed the in-process Python reads are faster and more reliable (the helper's reads hung for seconds on some terminals, and NVDA's own watchdog can recover a slow in-process read). Being pure Python, the add-on also runs on ARM64 versions of Windows without a separate build.

---

## AI CLI Support

Terminal Access detects AI command-line tools and adds navigation for conversational workflows. Supported tools: Claude, Aider, ChatGPT CLI, GitHub Copilot CLI, Gemini CLI, OpenAI Codex CLI, and Ollama.

**Experimental:** turn and code-block detection is heuristic. It infers boundaries from each tool's prompt markers, so a tool with unusual output can split turns in the wrong place or miss a code block. If a conversation reads incorrectly, please report it with a sample so the detection can be improved.

### Turn Navigation

Terminal Access splits the buffer into turns based on the role markers each AI CLI uses (user prompts and assistant responses).

| Command layer | Direct gesture | Action |
|---------------|----------------|--------|
| **Ctrl+T** | **NVDA+Alt+T** | Jump to next turn |
| **Ctrl+Shift+T** | **NVDA+Alt+Shift+T** | Jump to previous turn |

When you land on a turn, Terminal Access announces the role (user or assistant) and the first line. If no more turns exist in that direction, you hear "No more turns."

### Code Block Navigation

Terminal Access scans for fenced code blocks (triple backtick delimiters) and tracks the language, start line, end line, and content of each.

| Command layer | Direct gesture | Action |
|---------------|----------------|--------|
| **Ctrl+B** | **NVDA+Alt+B** | Next code block |
| **Ctrl+Shift+B** | **NVDA+Alt+Shift+B** | Previous code block |
| **Ctrl+L** | **NVDA+Alt+L** | Announce code block (language and line count) |
| **Ctrl+C** | **NVDA+Alt+C** | Copy code block to clipboard |
| **Ctrl+E** | **NVDA+Alt+E** | Explain code block |

The explain command gives a brief offline explanation of the block. It is gated by the "Enable code block explanation" setting, which is off by default.

### Streaming Delta

Press **NVDA+Shift+D** to hear only what changed since the last check while an AI assistant is streaming its response. Terminal Access diffs the current buffer against a stored snapshot to find the new content.

### Scoped Search

Press **Ctrl+F** in the command layer to search within the current AI turn only. Standard search (**F** in the command layer) still searches the full buffer.

### AI Error Detection

Terminal Access recognizes AI-specific error patterns in addition to standard compiler and shell errors.

| Pattern type | Examples |
|--------------|----------|
| Rate limit | "rate limit exceeded", "429 Too Many Requests" |
| Token limit | "token limit reached", "message was truncated" |
| API error | "invalid API key", "authentication failed" |
| Connection | "unable to reach API endpoint" |

Rate limit and token limit errors produce a pulsing low tone (two quick 220 Hz beeps). Other API errors produce a single low tone.

### Verbosity Level

The verbosity level controls how much optional context Terminal Access speaks. Press **Shift+V** in the command layer (or **NVDA+Shift+V**) to cycle through the levels, or set it in NVDA menu > Preferences > Settings > Terminal Settings.

| Level | Behavior |
|-------|----------|
| **Quiet** | Only errors and turn boundaries are announced |
| **Normal** | Standard announcements (default) |
| **Verbose** | Extra context such as the section category on a jump, the search match count, and profile override detail |

### Privacy Settings

Terminal Access does not send terminal text, code blocks, or summaries to an AI provider or any other external service. Code explanation and summarization run entirely inside the add-on. Their settings are local-processing controls, not permission to upload data, and both are off by default so you choose whether these features inspect additional terminal text.

| Setting | Default | Description |
|---------|---------|-------------|
| **Enable summarization** | Off | Selects important lines locally using extractive rules for errors, warnings, URLs, headings, and statistics. No AI model or network service is used. |
| **Enable code block explanation** | Off | Builds a brief local explanation using heuristics for imports, definitions, control flow, and error handling. No code is uploaded. |

When you invoke a privacy-gated feature while it is disabled, Terminal Access explains that the feature is off and how to enable it. To enable, open NVDA menu > Preferences > Settings > Terminal Settings > Privacy and check the setting.

Opening a detected URL is separate from these features. Terminal Access launches your default browser only after you explicitly choose to open the URL; the browser then handles the connection in the usual way.

---

## Settings

Open settings from NVDA menu > Preferences > Settings > Terminal Settings.

| Setting | Description |
|---------|-------------|
| **Key Echo** | Hear characters as you type in terminals, spoken at your punctuation level and with repeated symbols condensed ("dash 4 times"). Inside terminals this replaces NVDA's own "speak typed characters". See the note below. |
| **Speak typed words in terminals** | Hear each word as you finish typing it in a terminal. Off by default. Replaces NVDA's "speak typed words" while you are in a terminal, so word echo follows your per-profile settings. |
| **Cursor Tracking** | Announce cursor movements. |
| **Punctuation Level** | Control symbol verbosity (None, Some, Most, All). |
| **Indentation** | Announce indentation for code automatically. |
| **Error Audio Cues** | Play tones on error/warning lines during navigation. On by default. |
| **Error Audio Cues in Quiet Mode** | Play error/warning tones on caret events while quiet mode is active. Off by default. |
| **Output Activity Tones** | Play two ascending tones (600+800 Hz) when new program output appears. Off by default. |
| **Output Activity Debounce** | Minimum interval between activity tones in milliseconds (100 to 10000, default 1000). |

The settings panel also has a "NVDA Gesture Conflicts" section for disabling conflicting gestures and an "Application Profiles" section for managing profiles.

### Key Echo and NVDA's Typing Echo

NVDA has two typing-echo settings of its own in NVDA menu > Preferences > Settings > Keyboard: "Speak typed characters" and "Speak typed words". Terminal Access has its own Key Echo, and its own Speak typed words in terminals. Inside a terminal, Terminal Access's settings take over; NVDA's continue to apply everywhere else. You no longer need to turn NVDA's settings off to make Key Echo work.

- **Key Echo** replaces NVDA's "Speak typed characters" while you are in a terminal. You get symbol names at your chosen punctuation level, repeated symbols condensed ("dash 4 times"), and per-application profile control: profiles for single-key programs such as less, lazygit, btop, and Claude turn echo off automatically so shortcuts do not chatter.
- **Speak typed words in terminals** replaces NVDA's "Speak typed words" the same way, and gives word echo the same per-profile behavior. It is off by default, so nothing changes for you unless you ask for it.
- **The one case where Terminal Access steps aside:** NVDA's "Speak typed words" is on and Terminal Access's own word echo is off. NVDA builds each spoken word from the individual keystrokes it sees, so it needs to keep receiving them; Terminal Access stays quiet rather than break your word echo. Turn on Terminal Access's Speak typed words in terminals if you would rather it handled words too.

**Passwords are never spoken.** When the terminal marks what you are typing as protected, Terminal Access announces a masked character instead of the real one and never speaks the completed word, matching what NVDA does. Repeated-symbol condensing is also skipped there, since "dash 4 times" would describe the shape of what you typed.


---

## Troubleshooting

### The add-on does not activate

- Confirm you are in a supported terminal.
- Check that the add-on is enabled in NVDA menu > Tools > Manage Add-ons.
- Restart NVDA.

### Commands do not respond

- Try a different terminal application to see if the problem is terminal-specific.
- Check for keyboard shortcut conflicts in NVDA's Input Gestures dialog.
- Review the NVDA log (NVDA menu > Tools > View log).

---

## Getting Help

- Press **NVDA+Shift+F1** in any terminal to reopen this guide.
- **Save an issue report**: press **Shift+I** in the command layer (or **NVDA+Alt+I** directly) when a feature reads something wrong, for example table mode splitting a column in the wrong place or an AI turn detected at the wrong line. It saves a text file with your add-on and NVDA versions, the terminal, the active profile, and a buffer sample. Add a sentence about what you expected, then attach the file to a GitHub issue.
- Report issues on the [GitHub issue tracker](https://github.com/PratikP1/Terminal-Access-for-NVDA/issues). Include your NVDA version, Terminal Access version, terminal application and version, steps to reproduce, and expected versus actual behavior.
- The [frequently asked questions](https://github.com/PratikP1/Terminal-Access-for-NVDA/blob/main/docs/user/FAQ.md) and [version history](https://github.com/PratikP1/Terminal-Access-for-NVDA/blob/main/CHANGELOG.md) are on GitHub.
