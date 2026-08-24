# Terminal Access for NVDA

An NVDA add-on that makes Windows terminal applications more accessible. It adds keyboard-driven review navigation, search, bookmarks, and audio cues to 30 supported terminals, including Windows Terminal, PowerShell, Command Prompt, WSL, and popular third-party emulators.

## Key Features

- Command layer (NVDA+apostrophe) that turns every command into a single key press
- Line, word, and character navigation through terminal output
- Search with a results dialog, plus next and previous match keys
- Up to 10 bookmarks per tab with a bookmark list dialog
- Section, error, and prompt navigation for jumping through long output
- Table mode for column-aware reading of tabular output such as `docker ps`, `kubectl`, and `ls -l` (column detection is heuristic and will improve with testing and reports)
- Error and warning audio cues with structured pattern detection
- Quiet mode for fast-scrolling output, with optional error tones
- Application profiles that auto-adjust settings for vim, tmux, git, less, WSL, and AI CLI tools
- AI CLI support: turn navigation, code block navigation, streaming delta announcements
- Offline summarization of command output
- URL extraction, tab management, color and formatting reports, selection and copy
- Terminal analysis is fully local. The add-on never uploads terminal content; opening a detected URL is a separate, explicit action that launches your default browser.

## Installation

Download the latest `.nvda-addon` file from the [Releases page](https://github.com/PratikP1/Terminal-Access-for-NVDA/releases/latest), press Enter on it, confirm the prompt, and restart NVDA.

Requires Windows 10 or 11 and NVDA 2025.1 or later.

## Documentation

The full user guide, including the complete gesture reference, lives at [addon/doc/en/readme.md](addon/doc/en/readme.md). NVDA opens the same guide when you press NVDA+Shift+F1 inside a terminal.

For a short introduction, see [QUICKSTART.md](QUICKSTART.md). Version history is in [CHANGELOG.md](CHANGELOG.md).

## Building from Source

See [CONTRIBUTING.md](CONTRIBUTING.md) for build instructions and developer documentation in the [docs](docs/) folder.

## Credits

Inspired by [TDSR](https://github.com/tspivey/tdsr) by Tyler Spivey and [Speakup](https://github.com/linux-speakup/speakup), the Linux kernel screen reader.

## License

Copyright (C) 2024 Pratik Patel. Licensed under the GNU General Public License v3.0 or later. See the LICENSE file for details.
