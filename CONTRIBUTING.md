# Contributing to Terminal Access for NVDA

Thanks for your interest in contributing. This document covers guidelines, setup, and coding standards.

## Code of Conduct

- Be respectful and inclusive
- Give constructive feedback
- Focus on what helps the community
- Show empathy towards other contributors

## How to Contribute

### Reporting Bugs

Create a GitHub issue with:

1. **Clear title** describing the issue
2. **Detailed description** of the problem
3. **Steps to reproduce** the issue
4. **Expected vs. actual behavior**
5. **Environment info:**
   - Windows version (10 or 11)
   - NVDA version
   - Terminal application and version
   - Terminal Access add-on version

### Suggesting Features

Feature requests are welcome. Include:

1. **Clear description** of the feature
2. **Use case** explaining why it's needed
3. **Proposed implementation** (if you have ideas)
4. **Alternatives considered**

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch** from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following the coding standards below
4. **Test your changes**
5. **Commit with clear messages**
   ```bash
   git commit -m "Add feature: brief description"
   ```
6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Create a Pull Request** on GitHub

## Development Setup

### Prerequisites

- **Python 3.11 or later** (matches NVDA 2025.1 runtime)
- **NVDA screen reader** (2025.1 or later) for testing
- **Git** for version control
- **Text editor or IDE** (VS Code recommended with Python extension)

### Setting Up

1. **Clone the repository**:
   ```bash
   git clone https://github.com/PratikP1/Terminal-Access-for-NVDA.git
   cd Terminal-Access-for-NVDA
   ```

2. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

   This installs:
   - pytest (testing framework)
   - pytest-cov (coverage reporting)
   - flake8 (code quality)
   - wcwidth (Unicode support)
   - scons (build system)
   - markdown (documentation)

3. **Project structure**:
   ```
   Terminal-Access-for-NVDA/
   ├── addon/
   │   ├── globalPlugins/
   │   │   └── terminalAccess.py    # Main plugin (~3773 lines)
   │   ├── lib/
   │   │   ├── _runtime.py          # Dependency injection registry
   │   │   ├── caching.py           # PositionCache, TextDiffer
   │   │   ├── config.py            # Config constants, confspec, ConfigManager
   │   │   ├── gesture_conflicts.py # GestureConflictDetector
   │   │   ├── navigation.py        # TabManager, BookmarkManager, BookmarkListDialog
   │   │   ├── operations.py        # SelectionProgressDialog, OperationQueue
   │   │   ├── profiles.py          # ApplicationProfile, WindowDefinition, ProfileManager
   │   │   ├── search.py            # OutputSearchManager, UrlExtractorManager
   │   │   ├── settings_panel.py    # Settings panel (Basic/Advanced progressive disclosure)
   │   │   ├── text_processing.py   # ANSIParser, UnicodeWidthHelper, ErrorLineDetector
   │   │   └── window_management.py # WindowMonitor, WindowManager
   │   ├── locale/                   # Translation files (17 languages)
   │   └── doc/
   │       └── en/
   │           └── readme.html       # User guide
   ├── tests/                        # pytest suite (40 test files, 778 tests)
   ├── docs/                         # Developer, testing, and user documentation
   ├── native/                       # Rust workspace for FFI acceleration
   ├── manifest.ini                  # Add-on metadata
   ├── buildVars.py                  # Build configuration (version source of truth)
   ├── CHANGELOG.md                  # Version history
   └── requirements-dev.txt          # Dev dependencies
   ```

4. **Build the add-on**:
   ```bash
   # Using scons (preferred)
   scons

   # Or using build.py
   python build.py

   # Non-interactive build (CI)
   python build.py --non-interactive
   ```

5. **Install and test**:
   - Build creates `terminalAccess-{version}.nvda-addon` file
   - Press Enter on the file to install in NVDA
   - Test in Windows Terminal, PowerShell, or cmd.exe
   - Check NVDA log (NVDA+F1) for errors

### Running Tests

**Run all tests**:
```bash
python run_tests.py
# or
pytest tests/
```

**Run specific test file**:
```bash
pytest tests/test_cache.py
```

**Run with coverage**:
```bash
pytest --cov=addon --cov-report=html tests/
# View htmlcov/index.html for coverage report
```

### Code Quality Checks

**Run linter**:
```bash
flake8 addon/
```

**Configuration**: See `setup.cfg` for flake8 settings
- Max line length: 120 characters
- Ignored: E501 (line length), W503 (line break before binary operator)

### CI/CD Pipeline

Tests run automatically on:
- Push to main, develop, claude/* branches
- All pull requests

**Workflow stages**:
1. **Test**: pytest on Python 3.11 (Windows)
2. **Lint**: flake8 code quality check (Ubuntu)
3. **Build**: scons build verification

**Requirements**:
- All tests must pass
- Code coverage >= 70%
- No linting errors
- Successful build

## Coding Standards

### Python Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use tabs for indentation (NVDA convention)
- Maximum line length: 120 characters (per setup.cfg)
- Use descriptive variable and function names
- **New code uses snake_case.** Legacy code uses camelCase; both are accepted. The `profiles.py` module provides camelCase aliases for backward compatibility.

### Dependency Injection with `_runtime.py`

The `lib/_runtime.py` module provides a centralized dependency registry. Instead of importing NVDA modules directly (which breaks in tests), register and retrieve dependencies through the runtime:

```python
from addon.lib._runtime import runtime

# Registration (at plugin startup)
runtime.register('speech', speech)

# Retrieval (in library code)
speech = runtime.get('speech')
```

This pattern keeps library modules testable without NVDA running.

### Documentation

- Add docstrings to all functions and classes
- Use clear, concise comments
- Update user guide if adding features
- Keep CHANGELOG.md updated

### Example Code Style

```python
def myFunction(param1, param2):
	"""
	Brief description of what the function does.

	Args:
		param1: Description of first parameter
		param2: Description of second parameter

	Returns:
		Description of return value
	"""
	# Implementation
	result = param1 + param2
	return result
```

## Testing

### Manual Testing Checklist

Before submitting a pull request, test:

- [ ] All keyboard shortcuts work correctly
- [ ] Settings save and load properly
- [ ] Help system opens correctly
- [ ] No errors in NVDA log
- [ ] Works in Windows Terminal
- [ ] Works in PowerShell
- [ ] Works in Command Prompt
- [ ] All speech output is clear and accurate

### Testing in NVDA

1. Enable NVDA's Python console for debugging:
   - NVDA menu > Tools > Python console

2. Check NVDA log for errors:
   - NVDA menu > Tools > View log

3. Test with different NVDA versions if possible

## Commit Messages

Write clear, descriptive commit messages:

**Good:**
```
Add word spelling feature

- Implement spell-out functionality for current word
- Add NVDA+Alt+K double-press gesture
- Update user guide with new command
```

**Bad:**
```
Fixed stuff
Update code
Changes
```

## Documentation

When adding features:

1. Update `addon/doc/en/readme.html` with user-facing documentation
2. Add entry to `CHANGELOG.md` under appropriate version
3. Update `README.md` if it affects quick start or key features
4. Update `ARCHITECTURE.md` for architectural changes
5. Update `API_REFERENCE.md` for new public APIs
6. Update `ROADMAP.md` for significant features

### Documentation Standards

- **User docs**: Focus on "how to use" with examples
- **Developer docs**: Focus on "how it works" with code samples
- **API docs**: Include parameters, returns, and usage examples
- **Changelog**: Follow "Added/Changed/Fixed" format

## Architecture & Extension Points

### Key Components

Terminal Access is split across `terminalAccess.py` (command layer, events, scripts) and `addon/lib/` (11 modules). See `ARCHITECTURE.md` for details.

1. **PositionCache** (`lib/caching.py`): Performance optimization for position calculations
2. **ANSIParser** (`lib/text_processing.py`): Color and formatting detection
3. **UnicodeWidthHelper** (`lib/text_processing.py`): CJK and combining character support
4. **ErrorLineDetector** (`lib/text_processing.py`): Classifies lines as error/warning for audio cues
5. **ApplicationProfile** (`lib/profiles.py`): App-specific settings and window definitions
6. **ProfileManager** (`lib/profiles.py`): Profile detection and management
7. **GestureConflictDetector** (`lib/gesture_conflicts.py`): Detects and reports gesture collisions with other add-ons
8. **TerminalAccessSettingsPanel** (`lib/settings_panel.py`): Basic/Advanced progressive disclosure settings

### Adding New Features

**Navigation Commands**:
```python
@script(
    description=_("Your command description"),
    gesture="kb:NVDA+alt+yourkey"
)
def script_yourCommand(self, gesture):
    if not self.isTerminalApp():
        gesture.send()
        return
    # Your implementation
```

**Application Profiles**:
```python
# In ProfileManager._initializeDefaultProfiles()
myapp = ApplicationProfile('myapp', 'My Application')
myapp.punctuationLevel = PUNCT_MOST
myapp.addWindow('status', 1, 2, 1, 80, mode='silent')
self.profiles['myapp'] = myapp
```

**Window Definitions**:
```python
window = WindowDefinition('name', top, bottom, left, right, mode='announce')
profile.windows.append(window)
```

### Code Organization

- **Private methods**: Prefix with `_` (e.g., `_calculatePosition`)
- **Scripts**: Prefix with `script_` (e.g., `script_readCurrentLine`)
- **Event handlers**: Prefix with `event_` (e.g., `event_gainFocus`)
- **Constants**: UPPER_CASE (e.g., `CT_STANDARD`)
- **Classes**: PascalCase (e.g., `PositionCache`)

### Performance Guidelines

1. **Cache expensive operations**: Use PositionCache for coordinate calculations
2. **Background threading**: Use for operations >100ms (e.g., large selections)
3. **Lazy loading**: Load resources on demand
4. **Early returns**: Check fast conditions first

### Error Handling Pattern

```python
try:
    # Operation
    result = operation()
except (RuntimeError, AttributeError) as e:
    # Specific exceptions
    import logHandler
    logHandler.log.error(f"Terminal Access: Operation failed - {type(e).__name__}: {e}")
    ui.message(_("Specific error message"))
except Exception as e:
    # Generic fallback
    import logHandler
    logHandler.log.error(f"Terminal Access: Unexpected error - {type(e).__name__}: {e}")
    ui.message(_("Generic error message"))
```

## License

By contributing, you agree that your contributions will be licensed under the GNU General Public License v3.0, the same license as the project.

## Questions?

- Check existing issues on GitHub
- Create a new issue for questions
- Reach out to maintainers

## Recognition

Contributors are recognized in:
- CHANGELOG.md
- GitHub contributors page
- Project documentation

Thanks for helping make terminals more accessible.
