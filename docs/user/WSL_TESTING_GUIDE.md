# WSL (Windows Subsystem for Linux) Testing Guide

**Version:** 1.0.27+
**Status:** Initial WSL Support
**Last Updated:** 2026-02-21

## Overview

TDSR for NVDA v1.0.27+ includes support for Windows Subsystem for Linux (WSL), enabling screen reader users to work effectively in Linux terminal environments directly from Windows.

## What is WSL?

Windows Subsystem for Linux (WSL) is a compatibility layer for running Linux binary executables natively on Windows. WSL 2 provides a full Linux kernel running in a lightweight virtual machine.

### WSL Versions

- **WSL 1**: Translation layer that converts Linux system calls to Windows system calls
- **WSL 2**: Full Linux kernel in a lightweight VM (recommended)

## Installation and Setup

### Prerequisites

1. **NVDA** 2019.3 or later
2. **TDSR for NVDA** v1.0.27 or later
3. **Windows 10** version 2004+ or **Windows 11**
4. **WSL** installed with a Linux distribution

### Installing WSL

If WSL is not already installed:

```powershell
# Install WSL with default Ubuntu distribution
wsl --install

# Or install a specific distribution
wsl --install -d Ubuntu-22.04
```

After installation, restart your computer.

### Verifying WSL Installation

```powershell
# Check WSL version
wsl --version

# List installed distributions
wsl --list --verbose

# Check default distribution
wsl --status
```

## Using TDSR with WSL

### Launching WSL

**Method 1: Direct WSL Command**
```powershell
wsl
```

**Method 2: Windows Terminal**
```powershell
wt -p "Ubuntu"
```

**Method 3: Distribution-Specific Command**
```bash
ubuntu2204.exe
```

### Detecting WSL in TDSR

TDSR automatically detects WSL environments by identifying:
- Process name: `wsl` or `wsl.exe`
- Process name: `bash` (when running as WSL bash)

The WSL profile is automatically activated when TDSR detects a WSL terminal.

## WSL Profile Settings

TDSR's WSL profile (v1.0.27+) includes optimizations for Linux command-line usage:

### Default Settings

- **Punctuation Level**: MOST (code-friendly for Linux commands and paths)
- **Cursor Tracking**: STANDARD (follows system caret)
- **Repeated Symbols**: OFF (reduces verbosity with progress bars and repeated characters)

### Why These Settings?

**Punctuation Level: MOST**
- Linux paths use forward slashes: `/home/user/documents`
- Command-line arguments: `--verbose`, `--help`
- Shell operators: `|`, `>`, `<`, `&&`, `||`

**Repeated Symbols: OFF**
- Progress bars: `████████████` (common in package managers)
- Separators: `========`, `--------`
- File listings: `drwxr-xr-x`

## Testing Checklist

### Basic Functionality

- [ ] WSL terminal is detected by TDSR
- [ ] WSL profile automatically activates
- [ ] NVDA+Alt+H gesture shows TDSR help in WSL
- [ ] Standard terminal navigation works (lines, words, characters)

### Command Execution

Test common Linux commands:

- [ ] `ls -la` (list files with details)
- [ ] `pwd` (print working directory)
- [ ] `cd /home` (change directory)
- [ ] `cat /etc/os-release` (display file contents)
- [ ] `grep pattern file.txt` (search in files)
- [ ] `ps aux` (process listing)
- [ ] `df -h` (disk usage)
- [ ] `history` (command history)

### Package Management

- [ ] `apt update` (Debian/Ubuntu)
- [ ] `apt install package` (with progress bars)
- [ ] `dnf install package` (Fedora)
- [ ] `yum install package` (RHEL/CentOS)
- [ ] `zypper install package` (openSUSE)

### Text Editors

- [ ] `nano file.txt` (GNU nano editor)
- [ ] `vim file.txt` (Vim editor with profile)
- [ ] `emacs file.txt` (Emacs editor)

### Development Tools

- [ ] `git status` (Git with profile)
- [ ] `git log` (Git history)
- [ ] `git diff` (Git changes)
- [ ] `python3` (Python REPL)
- [ ] `node` (Node.js REPL)
- [ ] `make` (build tool output)

### System Administration

- [ ] `systemctl status` (systemd on WSL 2)
- [ ] `journalctl` (system logs on WSL 2)
- [ ] `sudo command` (elevated commands)
- [ ] `ssh user@host` (SSH connections)

### Long-Running Operations

Test cursor tracking and output handling:

- [ ] `sleep 5` (simple delay)
- [ ] `ping google.com` (continuous output - use Ctrl+C to stop)
- [ ] `tail -f /var/log/syslog` (log monitoring - use Ctrl+C to stop)
- [ ] `watch -n 1 date` (periodic command - use Ctrl+C to stop)

### Terminal Multiplexers

- [ ] `tmux` (tmux with profile)
- [ ] `screen` (GNU Screen)

### File Navigation

- [ ] Browse multi-line output with NVDA+Alt+U/I/O (previous/current/next line)
- [ ] Read long lines with NVDA+Alt+J/K/L (previous/current/next word)
- [ ] Character navigation with NVDA+Alt+M/Comma/Period

## Known Limitations

### WSL 1 vs WSL 2

- **WSL 1**: May have slower text rendering in some scenarios
- **WSL 2**: Better performance but requires virtualization support

### Terminal Applications

- **Windows Terminal**: Recommended for best experience
- **ConHost**: Basic support (Windows Console Host)
- **Third-party terminals**: May require additional configuration

### Accessibility Features

- **Unicode Support**: Full support for UTF-8 (emoji, CJK characters)
- **RTL Text**: Supported for Arabic and Hebrew
- **ANSI Colors**: Attribute/color reading available (NVDA+Alt+A)

## Troubleshooting

### TDSR Not Detecting WSL

**Issue**: TDSR gestures don't work in WSL terminal

**Solutions**:
1. Verify TDSR version: Check NVDA Add-ons Manager for v1.0.27+
2. Check application module:
   - Open NVDA Python console (NVDA+Control+Z)
   - Run: `api.getForegroundObject().appModule.appName`
   - Should show "wsl" or "bash"
3. Restart NVDA after launching WSL
4. Try launching WSL from Windows Terminal instead

### Profile Not Activating

**Issue**: WSL profile settings not applied

**Solutions**:
1. Manually activate profile: TDSR Settings → Select "Windows Subsystem for Linux"
2. Check for conflicting profiles
3. Reset to defaults: TDSR Settings → Reset

### Slow Performance

**Issue**: TDSR is slow in WSL

**Solutions**:
1. Upgrade to WSL 2: `wsl --set-version <distro> 2`
2. Enable position caching (already enabled in v1.0.21+)
3. Reduce output verbosity: Quiet mode (NVDA+Alt+Q)
4. Limit command output: Use `| head -20` to show first 20 lines

### Missing Text or Garbled Output

**Issue**: Some text is not announced correctly

**Solutions**:
1. Check terminal encoding: `echo $LANG` (should show UTF-8)
2. Set correct locale: `export LANG=en_US.UTF-8`
3. Update terminal: Use latest Windows Terminal
4. Increase NVDA speech delay: NVDA Settings → Speech → Pauses between words

## Advanced Configuration

### Custom WSL Profile

You can create a custom profile for specific Linux distributions:

1. Open TDSR Settings (NVDA → Preferences → TDSR Settings)
2. Import/Export Profiles → Create New
3. Name: "Ubuntu-Custom" or "Arch-Custom"
4. Customize settings:
   - Punctuation level
   - Cursor tracking mode
   - Window definitions (for specific TUI applications)
5. Save and activate

### Profile JSON Example

```json
{
  "name": "wsl-custom",
  "displayName": "WSL Custom Profile",
  "punctuationLevel": 3,
  "cursorTrackingMode": 1,
  "repeatedSymbols": false,
  "quietMode": false,
  "verboseMode": false,
  "windows": []
}
```

### Distribution-Specific Considerations

**Ubuntu/Debian**:
- Package manager: `apt`
- Default shell: bash
- Systemd: Available on WSL 2 (Ubuntu 22.04+)

**Arch Linux**:
- Package manager: `pacman`
- Rolling release (frequent updates)
- Minimal base installation

**openSUSE**:
- Package manager: `zypper`
- YaST configuration tool
- Enterprise-focused

**Fedora**:
- Package manager: `dnf`
- Cutting-edge packages
- SELinux enabled

## Testing Matrix

| Feature | WSL 1 | WSL 2 | Status |
|---------|-------|-------|--------|
| Terminal detection | ✅ | ✅ | Working |
| Profile activation | ✅ | ✅ | Working |
| Basic commands | ✅ | ✅ | Working |
| Text editors (vim, nano) | ✅ | ✅ | Working |
| Git operations | ✅ | ✅ | Working |
| Package managers | ⚠️ | ✅ | Slower on WSL 1 |
| Terminal multiplexers | ✅ | ✅ | Working |
| systemd support | ❌ | ✅ | WSL 2 only |
| GUI applications | ❌ | ⚠️ | WSLg on Windows 11 |
| SSH connections | ✅ | ✅ | Working |

**Legend**:
- ✅ Fully supported
- ⚠️ Partially supported or requires configuration
- ❌ Not supported

## Reporting Issues

If you encounter issues with WSL support:

1. **Check this guide** for known limitations and solutions
2. **Gather information**:
   - TDSR version (NVDA Add-ons Manager)
   - WSL version (`wsl --version`)
   - Distribution (`cat /etc/os-release` in WSL)
   - Terminal application (Windows Terminal, ConHost, etc.)
   - Application module name (NVDA Python console)
3. **Create a bug report**: Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md)
4. **Include NVDA log**: NVDA+F1 → View Log

## Resources

### Official Documentation

- [WSL Documentation](https://docs.microsoft.com/en-us/windows/wsl/)
- [TDSR Documentation](README.md)
- [TDSR Advanced User Guide](ADVANCED_USER_GUIDE.md)

### Community Support

- [TDSR Issues](https://github.com/PratikP1/Terminal-Access-for-NVDA/issues)
- [NVDA Community](https://www.nvaccess.org/community/)

### Related Guides

- [Third-Party Terminal Support](ADVANCED_USER_GUIDE.md#third-party-terminal-emulator-support)
- [Application Profiles](ADVANCED_USER_GUIDE.md#application-profiles)
- [Troubleshooting](FAQ.md#troubleshooting)

## Contributing

Help improve WSL support by:

1. **Testing**: Try TDSR with different WSL distributions
2. **Reporting**: Share your experience (what works, what doesn't)
3. **Documenting**: Suggest improvements to this guide
4. **Developing**: Submit patches for WSL-specific issues

## Version History

### v1.0.27 (2026-02-21)
- Initial WSL support
- WSL detection in `isTerminalApp()`
- WSL-specific application profile
- WSL testing guide documentation
