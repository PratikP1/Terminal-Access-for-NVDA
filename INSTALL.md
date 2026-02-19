# Installation Guide

## Prerequisites

- Windows 10 or Windows 11
- NVDA screen reader version 2019.3 or later
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
   - NVDA will display an installation confirmation dialog
   - Press Enter to confirm the installation

3. **Restart NVDA**
   - NVDA will prompt you to restart
   - Press Enter to restart now, or Tab to "Restart later"
   - The add-on will be active after NVDA restarts

4. **Verify Installation**
   - Open a supported terminal application (e.g., Windows Terminal or PowerShell)
   - NVDA should announce: "TDSR terminal support active. Press NVDA+shift+f1 for help."
   - If you hear this message, the installation was successful!

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
   - The add-on will be loaded automatically

## Verifying Installation

To verify the add-on is installed and working:

1. Press `NVDA+N` to open the NVDA menu
2. Navigate to "Tools" > "Manage add-ons"
3. Look for "TDSR" in the list of installed add-ons
4. Ensure it is not disabled

## First Use

1. **Open a Terminal**
   - Launch Windows Terminal, PowerShell, or Command Prompt
   - NVDA will announce that TDSR terminal support is active

2. **Access Help**
   - Press `NVDA+Shift+F1` to open the comprehensive user guide
   - This guide contains all keyboard commands and settings information

3. **Configure Settings**
   - Press `NVDA+Alt+C` while in a terminal, or
   - Press `NVDA+N` > "Preferences" > "Settings" > "Terminal Settings"
   - Adjust settings to your preferences

## Uninstallation

If you need to uninstall the add-on:

1. Press `NVDA+N` to open the NVDA menu
2. Navigate to "Tools" > "Manage add-ons"
3. Find "TDSR" in the list
4. Press the "Remove" button (or press Alt+R)
5. Confirm removal when prompted
6. Restart NVDA

## Troubleshooting Installation

### Add-on Won't Install
- Ensure you're using NVDA 2019.3 or later
- Check that the file downloaded completely (not corrupted)
- Try downloading the file again
- Ensure NVDA has proper permissions to write to its configuration directory

### Add-on Not Working After Installation
- Verify the add-on is enabled in the Add-ons Manager
- Ensure you've restarted NVDA after installation
- Check that you're using a supported terminal application
- Review the troubleshooting section in the user guide

### Permission Issues
- If running NVDA with elevated privileges, ensure the add-on installation is also performed with elevated privileges
- Check that NVDA has write access to its configuration directory

## Updating

To update to a newer version:

1. Install the new version following the standard installation steps above
2. NVDA will automatically replace the old version
3. Restart NVDA when prompted
4. Your settings will be preserved

## Getting Help

If you encounter issues during installation:

1. Check the troubleshooting section in the user guide (press `NVDA+Shift+F1` in a terminal)
2. Visit the project repository: https://github.com/PratikP1/TDSR-for-NVDA
3. Report issues on the project's issue tracker

---

**Note:** This add-on requires only NVDA and a supported terminal application. No additional software or dependencies are needed.
