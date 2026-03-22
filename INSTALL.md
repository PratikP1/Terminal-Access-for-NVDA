# Installation Guide - Terminal Access for NVDA

## Prerequisites

- Windows 10 or Windows 11
- NVDA screen reader version 2025.1 or later
- One or more supported terminal applications:
  - Windows Terminal
  - PowerShell
  - PowerShell Core
  - Command Prompt
  - Console Host

## Installation Steps

### Method 1: Standard Installation (Recommended)

1. **Download the Add-on**
   - Download the latest `.nvda-addon` file from the releases page
   - Save it to a location you can easily access

2. **Install the Add-on**
   - Navigate to the downloaded `.nvda-addon` file
   - Press Enter to open it
   - NVDA displays an installation confirmation dialog
   - Press Enter to confirm

3. **Restart NVDA**
   - NVDA prompts you to restart
   - Press Enter to restart now, or Tab to "Restart later"
   - The add-on activates after NVDA restarts

4. **Verify Installation**
   - Open a supported terminal application (e.g., Windows Terminal or PowerShell)
   - NVDA announces: "Terminal Access support active. Press NVDA+shift+f1 for help."

### Method 2: Manual Installation

1. **Locate NVDA User Configuration Directory**
   - Press `NVDA+N` to open the NVDA menu
   - Navigate to "Preferences" > "Manage add-ons"
   - In the Add-ons Manager, press `Alt+O` for "Open add-ons folder"

2. **Extract the Add-on**
   - Rename the `.nvda-addon` file to `.zip`
   - Extract the contents
   - Copy the extracted folder to the NVDA add-ons directory

3. **Restart NVDA**
   - Press `NVDA+Q` to quit NVDA
   - Start NVDA again
   - The add-on loads automatically

## Verifying Installation

To verify the add-on is installed and working:

1. Press `NVDA+N` to open the NVDA menu
2. Navigate to "Tools" > "Manage add-ons"
3. Look for "Terminal Access" or "terminalAccess" in the list of installed add-ons
4. Confirm it is not disabled

## First Use

1. **Open a Terminal**
   - Launch Windows Terminal, PowerShell, or Command Prompt
   - NVDA announces that Terminal Access support is active

2. **Access Help**
   - Press `NVDA+Shift+F1` to open the user guide
   - The guide covers all keyboard commands and settings

3. **Configure Settings**
   - Press `NVDA+N` > "Preferences" > "Settings" > "Terminal Settings"
   - Adjust settings to your preferences

## Uninstallation

If you need to uninstall the add-on:

1. Press `NVDA+N` to open the NVDA menu
2. Navigate to "Tools" > "Manage add-ons"
3. Find "Terminal Access" or "terminalAccess" in the list
4. Press the "Remove" button (or press Alt+R)
5. Confirm removal when prompted
6. Restart NVDA

## Troubleshooting Installation

### Add-on Won't Install
- Confirm you're using NVDA 2025.1 or later
- Check that the file downloaded completely (not corrupted)
- Try downloading the file again
- Check that NVDA has write access to its configuration directory

### Add-on Not Working After Installation
- Verify the add-on is enabled in the Add-ons Manager
- Restart NVDA after installation
- Check that you're using a supported terminal application
- Review the troubleshooting section in the user guide

### Permission Issues
- If running NVDA with elevated privileges, install the add-on with elevated privileges too
- Check that NVDA has write access to its configuration directory

## Updating

To update to a newer version:

1. Install the new version following the standard installation steps above
2. NVDA replaces the old version automatically
3. Restart NVDA when prompted
4. Your settings carry over

## Getting Help

If you encounter issues during installation:

1. Check the troubleshooting section in the user guide (press `NVDA+Shift+F1` in a terminal)
2. Visit the project repository: https://github.com/PratikP1/Terminal-Access-for-NVDA
3. Report issues on the project's issue tracker

