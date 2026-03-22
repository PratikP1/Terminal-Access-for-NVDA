# Testing Guide for Terminal Access for NVDA

This guide covers automated and manual testing procedures for the Terminal Access add-on.

---

## Part 1: Automated Testing

### Python Version Requirements

**Terminal Access requires NVDA 2025.1 or later**, which uses Python 3.11.

The test suite runs on Python 3.11 via CI/CD.

### Quick Start

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
python run_tests.py

# Or use pytest directly
pytest tests/
```

### Test Suite Overview

The test suite has **40 test files** with **778 passing tests** (67 skipped for native bridge).

Tests cover:
- Input validation and security hardening
- Position caching and thread safety
- Configuration management
- Selection operations and terminal detection
- Application profiles and profile management
- Bookmarks, search, URL extraction
- Error line detection
- Gesture conflict detection
- Settings panel
- Native bridge (skipped when Rust DLL unavailable)
- Performance benchmarks and regression tests
- Integration workflows

#### Coverage

- **Total coverage**: ~54% (measures both `terminalAccess.py` and `addon/lib/`)
- **CI threshold**: 70% on covered modules
- **lib/ modules**: Higher coverage since they were extracted for testability

### Running Tests

#### Run All Tests
```bash
python run_tests.py
```

This runs all tests with verbose output and generates a coverage report.

#### Run Specific Test Files
```bash
pytest tests/test_validation.py -v
pytest tests/test_gesture_conflicts.py -v
```

#### Run Specific Test Methods
```bash
pytest tests/test_validation.py::TestValidation::test_integer_range -v
```

#### Run with Coverage Report
```bash
# Generate HTML coverage report
pytest --cov=addon --cov-report=html tests/

# Open coverage report
# Windows: start htmlcov/index.html
```

### CI/CD Testing

Tests run automatically on:
- Every push to `main`, `develop`, and feature branches
- Every pull request

#### GitHub Actions Workflow
- **Test Matrix**: Python 3.11 on Windows
- **Linting**: flake8 on Ubuntu
- **Coverage**: 70%+ required (enforced)
- **Build**: scons build verification

View test results in the Actions tab on GitHub.

### Writing Tests

#### Test Structure
```python
import unittest
from unittest.mock import MagicMock

class TestFeature(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        pass

    def test_feature_behavior(self):
        """Test specific behavior."""
        # Arrange
        expected = "value"

        # Act
        result = some_function()

        # Assert
        self.assertEqual(result, expected)
```

#### Mocking NVDA Modules
Use fixtures from `tests/conftest.py`:
```python
def test_with_terminal(mock_terminal):
    """Test with mocked terminal."""
    result = mock_terminal.makeTextInfo()
    assert result is not None
```

---

## Part 2: Manual Testing

### Pre-Testing Setup

#### Required Environment
- [ ] Windows 10 or Windows 11
- [ ] NVDA 2025.1 or later installed
- [ ] At least one supported terminal application
- [ ] Terminal Access add-on installed

#### Supported Terminal Applications
**Built-in Terminals:**
- Windows Terminal
- PowerShell (5.x)
- PowerShell Core (7.x+)
- Command Prompt (cmd.exe)
- Console Host (conhost.exe)

**Third-Party Terminals:**
- Cmder, ConEmu, mintty (Git Bash)
- PuTTY, KiTTY
- Terminus, Hyper, Alacritty, WezTerm, Tabby, FluentTerminal

### Test Categories

### 1. Installation Testing

#### Test 1.1: Fresh Installation
**Steps:**
1. Download terminalAccess-*.nvda-addon file
2. Press Enter on the file
3. Confirm installation

**Expected Result:**
- Installation completes without errors
- NVDA prompts to restart
- After restart, add-on appears in Add-ons Manager

**Status:** [ ] Pass [ ] Fail

#### Test 1.2: Upgrade Installation
**Steps:**
1. Install older version
2. Install newer version (simulating upgrade)

**Expected Result:**
- Installation replaces existing version
- Settings are preserved
- No errors occur

**Status:** [ ] Pass [ ] Fail

#### Test 1.3: Uninstallation
**Steps:**
1. Open NVDA menu > Tools > Manage Add-ons
2. Select Terminal Access
3. Click Remove
4. Restart NVDA

**Expected Result:**
- Add-on removed successfully
- Terminal Access features no longer available
- No NVDA errors after restart

**Status:** [ ] Pass [ ] Fail

---

### 2. Terminal Detection Testing

#### Test 2.1: Automatic Terminal Detection
**Steps:**
1. Open Windows Terminal
2. Observe NVDA behavior

**Expected Result:**
- NVDA announces "Terminal Access support active. Press NVDA+Shift+F1 for help."
- Terminal Access features become available

**Status:** [ ] Pass [ ] Fail

#### Test 2.2: Third-Party Terminal Detection
**Repeat for each supported terminal:**
- [ ] Cmder
- [ ] ConEmu
- [ ] mintty (Git Bash)
- [ ] PuTTY
- [ ] Terminus
- [ ] Hyper
- [ ] Alacritty

**Status:** [ ] Pass [ ] Fail

---

### 3. Navigation Testing

#### Test 3.1: Line Navigation
**Steps:**
1. Open terminal with multiple lines of output
2. Press `NVDA+U` (previous line)
3. Press `NVDA+O` (next line)
4. Press `NVDA+I` (current line)
5. Press `NVDA+I` twice quickly (indentation level)

**Expected Result:**
- Previous line reads previous line content
- Next line reads next line content
- Current line reads current line content
- Double-press announces indentation level

**Status:** [ ] Pass [ ] Fail

#### Test 3.2: Word Navigation
**Steps:**
1. Position on a line with multiple words
2. Press `NVDA+J` (previous word)
3. Press `NVDA+L` (next word)
4. Press `NVDA+K` (current word)

**Expected Result:**
- Navigation moves by word correctly
- Word boundaries detected properly

**Status:** [ ] Pass [ ] Fail

#### Test 3.3: Character Navigation
**Steps:**
1. Position on text
2. Press `NVDA+Alt+M` (previous character)
3. Press `NVDA+Alt+Period` (next character)
4. Press `NVDA+Comma` (current character)
5. Press `NVDA+Comma` twice (phonetic)
6. Press `NVDA+Comma` three times (character code)

**Expected Result:**
- Character navigation works correctly
- Double-press gives phonetic spelling
- Triple-press announces character code

**Status:** [ ] Pass [ ] Fail

---

### 4. Reading Mode Testing

#### Test 4.1: Say All
**Steps:**
1. Position at top of terminal buffer
2. Press `NVDA+Alt+A`

**Expected Result:**
- Continuous reading from current position to end
- Reading can be stopped with Ctrl

**Status:** [ ] Pass [ ] Fail

#### Test 4.2: Directional Reading
**Steps:**
1. Position mid-screen
2. Press `NVDA+Alt+Shift+Left` (read to start of line)
3. Press `NVDA+Alt+Shift+Right` (read to end of line)
4. Press `NVDA+Shift+Up` (read to top)
5. Press `NVDA+Shift+Down` (read to bottom)

**Expected Result:**
- Each direction reads correctly from cursor to boundary

**Status:** [ ] Pass [ ] Fail

---

### 5. Selection and Copy Testing

#### Test 5.1: Mark-Based Selection
**Steps:**
1. Press `NVDA+Alt+R` (set start mark)
2. Navigate to different position
3. Press `NVDA+Alt+R` (set end mark)
4. Press `NVDA+C` (copy linear selection)

**Expected Result:**
- Marks set successfully
- Selection copied to clipboard
- Clipboard contains expected text

**Status:** [ ] Pass [ ] Fail

---

### 6. Color and Formatting Testing

#### Test 6.1: ANSI Color Detection
**Steps:**
1. Run command with colored output (e.g., `ls --color` on Git Bash)
2. Position on colored text
3. Press `NVDA+Alt+Shift+A`

**Expected Result:**
- Color announced (e.g., "red foreground", "blue background")
- Format attributes announced if present

**Status:** [ ] Pass [ ] Fail

---

### 7. Application Profile Testing

#### Test 7.1: Vim Profile
**Steps:**
1. Open Vim in terminal
2. Verify Terminal Access detects Vim
3. Check status line behavior

**Expected Result:**
- Vim profile activated
- Status line announcements suppressed
- Enhanced punctuation for code

**Status:** [ ] Pass [ ] Fail

#### Test 7.2: tmux Profile
**Steps:**
1. Start tmux session
2. Verify profile detection

**Expected Result:**
- tmux profile activated
- Status bar suppressed

**Status:** [ ] Pass [ ] Fail

---

### 8. Window Monitoring Testing

#### Test 8.1: Define Window
**Steps:**
1. Press `NVDA+Alt+F2` (define window - first corner)
2. Press `NVDA+Alt+F2` again (second corner)

**Expected Result:**
- Window defined successfully
- Window content announced on changes

**Status:** [ ] Pass [ ] Fail

---

### 9. Search and Bookmarks Testing

#### Test 9.1: Output Search
**Steps:**
1. Press `NVDA+Alt+F`
2. Enter search text
3. Press `NVDA+F3` (next match)
4. Press `NVDA+Shift+F3` (previous match)

**Expected Result:**
- Search finds matches
- Navigation between matches works
- Match count announced

**Status:** [ ] Pass [ ] Fail

#### Test 9.2: Bookmarks
**Steps:**
1. Press `NVDA+Alt+1` (set bookmark 1)
2. Navigate away
3. Press `Alt+1` (jump to bookmark 1)

**Expected Result:**
- Bookmark set at position with line content label
- Jump returns to bookmarked position
- Bookmark list (NVDA+Shift+B) shows number and line content

**Status:** [ ] Pass [ ] Fail

---

### 10. Settings Testing

#### Test 10.1: Settings Dialog
**Steps:**
1. Open NVDA menu > Preferences > Settings > Terminal Access
2. Verify Basic/Advanced toggle works
3. Modify punctuation level
4. Change cursor tracking mode
5. Click OK

**Expected Result:**
- Settings dialog opens with Basic view by default
- "Show advanced" expands additional settings
- Changes apply immediately
- Settings persist after NVDA restart

**Status:** [ ] Pass [ ] Fail

---

### 11. Translation Testing

#### Test 11.1: Language Support
**Steps:**
1. Change NVDA language (if translations available)
2. Restart NVDA
3. Test Terminal Access messages in new language

**Expected Result:**
- Terminal Access messages appear in selected language
- Fallback to English for untranslated strings

**Status:** [ ] Pass [ ] Fail

---

## Performance Testing

### Test P.1: Large Buffer Performance
**Steps:**
1. Generate large terminal output (e.g., `dir /s C:\Windows`)
2. Navigate through buffer
3. Measure response time

**Expected Result:**
- Navigation stays responsive (<100ms per operation)
- No noticeable lag

**Status:** [ ] Pass [ ] Fail

---

## Regression Testing

After any code changes, run these critical tests:
1. [ ] Terminal detection (Test 2.1)
2. [ ] Line navigation (Test 3.1)
3. [ ] Selection and copy (Test 5.1)
4. [ ] Settings persistence (Test 10.1)

---

## Reporting Issues

If any test fails:
1. Note the test number and description
2. Record exact steps to reproduce
3. Include NVDA version, Windows version, terminal application
4. Check NVDA log (NVDA menu > Tools > View Log)
5. Report via GitHub: https://github.com/PratikP1/Terminal-Access-for-NVDA/issues

---

## Additional Resources

- **User Guide**: See `docs/user/ADVANCED_USER_GUIDE.md`
- **FAQ**: See `docs/user/FAQ.md`
- **API Reference**: See `docs/developer/API_REFERENCE.md`
- **Architecture**: See `docs/developer/ARCHITECTURE.md`
