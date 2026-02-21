---
name: Terminal Support Request
about: Request support for a new terminal emulator
title: '[TERMINAL] Support for [Terminal Name]'
labels: enhancement, terminal-support
assignees: ''

---

## Terminal Information
- **Terminal Name**: [e.g., Alacritty, WezTerm]
- **Terminal Version**: [if known]
- **Official Website**: [URL]
- **Platform**: Windows / Cross-platform
- **Open Source**: Yes / No
- **Repository** (if applicable): [GitHub URL]

## Terminal Features
Describe the terminal's key features:
- [ ] Tab support
- [ ] Split panes
- [ ] GPU acceleration
- [ ] SSH/Remote support
- [ ] Customizable themes
- [ ] Plugin/extension system
- [ ] Other: [describe]

## Current Status with TDSR
- [ ] Works partially
- [ ] Doesn't work at all
- [ ] Untested

If partially working, describe what works and what doesn't.

## Application Module Name
Help us add support by providing the application module name:

1. With the terminal in focus, open NVDA Python console (NVDA+Control+Z)
2. Run: `api.getForegroundObject().appModule.appName`
3. Paste the result here:

```
[Paste appModule name here]
```

## Why This Terminal?
Explain why you prefer this terminal over supported alternatives:
- **Unique Features**: What makes this terminal special?
- **Workflow**: How does it fit into your workflow?
- **Accessibility**: Are there accessibility features in the terminal itself?

## Proposed Profile Settings
If you have preferences for how TDSR should behave with this terminal:
- **Punctuation Level**: None / Some / Most / All
- **Cursor Tracking**: Off / Standard / Highlight / Window
- **Special Regions**: Any status bars or UI elements that should be silenced?

## Additional Context
- Screenshots (if helpful)
- Links to terminal documentation
- Any known accessibility considerations
- Similar terminals already supported

## Related Issues
Link any related terminal support requests: #
