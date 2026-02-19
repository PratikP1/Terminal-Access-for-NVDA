# TDSR for NVDA

An NVDA add-on that provides enhanced terminal accessibility for Windows Terminal and PowerShell, bringing Terminal Data Structure Reader (TDSR) functionality directly into NVDA.

## Overview

TDSR for NVDA enables screen reader users to efficiently navigate and interact with command-line interfaces on Windows. The add-on integrates seamlessly with NVDA's built-in speech synthesis and provides comprehensive navigation and reading commands specifically designed for terminal usage.

## Features

- **Line-by-line navigation** through terminal output
- **Word and character navigation** with phonetic spelling support
- **Cursor tracking** with automatic position announcements
- **Key echo** to hear characters as you type
- **Symbol processing** to speak symbol names
- **Quiet mode** to temporarily disable automatic announcements
- **Selection and copy functionality** for terminal content
- **Configurable settings** through NVDA's settings dialog

## Supported Terminals

- Windows Terminal
- Windows PowerShell
- PowerShell Core (pwsh)
- Command Prompt (cmd.exe)
- Console Host (conhost.exe)

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
> "TDSR terminal support active. Press NVDA+shift+f1 for help."

Press **NVDA+Shift+F1** to open the comprehensive user guide.

## Key Commands

### Navigation
- **NVDA+Alt+U/I/O** - Read previous/current/next line
- **NVDA+Alt+J/K/L** - Read previous/current/next word
- **NVDA+Alt+M/Comma/Period** - Read previous/current/next character

### Special Features
- **NVDA+Alt+K** (twice) - Spell current word
- **NVDA+Alt+Comma** (twice) - Read character phonetically
- **NVDA+Alt+Q** - Toggle quiet mode
- **NVDA+Alt+R** - Start/end selection
- **NVDA+Alt+V** - Enter copy mode
- **NVDA+Alt+C** - Open settings

### Help
- **NVDA+Shift+F1** - Open user guide

## Configuration

Access TDSR settings through:
- NVDA menu > Preferences > Settings > Terminal Settings
- Or press **NVDA+Alt+C** while in a terminal

Available settings:
- Cursor tracking
- Key echo
- Line pause
- Symbol processing
- Repeated symbols condensation
- Cursor delay

## Documentation

For detailed documentation, including:
- Complete keyboard command reference
- Configuration guide
- Tips and best practices
- Troubleshooting

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
TDSR-for-NVDA/
├── addon/
│   ├── globalPlugins/
│   │   └── tdsr.py          # Main plugin code
│   └── doc/
│       └── en/
│           └── readme.html   # User guide
├── manifest.ini              # Add-on metadata
├── buildVars.py             # Build configuration
└── README.md                # This file
```

## Contributing

Contributions are welcome! Please feel free to:
- Report bugs or issues
- Suggest new features
- Submit pull requests
- Improve documentation

## Credits

This add-on is inspired by [TDSR (Terminal Data Structure Reader)](https://github.com/tspivey/tdsr) by Tyler Spivey.

## License

Copyright (C) 2024 TDSR for NVDA Contributors

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

See the LICENSE file for the complete license text.

## Links

- [Project Repository](https://github.com/PratikP1/TDSR-for-NVDA)
- [NVDA Official Website](https://www.nvaccess.org/)
- [Original TDSR Project](https://github.com/tspivey/tdsr)
- [NVDA Add-on Development Guide](https://github.com/nvda-es/devguides_translation/blob/master/original_docs/NVDA-Add-on-DevelopmentGuide.md)
