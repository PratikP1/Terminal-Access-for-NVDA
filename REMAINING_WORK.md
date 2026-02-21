# TDSR for NVDA - Remaining Work Analysis

**Document Version:** 1.0
**Current Version:** 1.0.14
**Analysis Date:** 2026-02-21
**Status:** Comprehensive roadmap for future development

---

## Executive Summary

TDSR for NVDA has successfully completed **Phase 1 (Quick Wins)** and **Phase 2 (Core Enhancements)**, with critical features from **Phase 3 (Advanced Features)** now implemented. The project is at approximately **70% completion** of the full Speakup-inspired feature set.

### Completed ✅
- ✅ Phase 1: Quick Wins (100%)
- ✅ Phase 2: Core Enhancements (100%)
- ✅ Rectangular Selection with Column Tracking
- ✅ Window Coordinate Tracking System
- ✅ Window Content Reading
- ✅ Position Calculation Infrastructure

### Remaining Work
- 🔄 Performance Optimization (Position Caching)
- 🔄 Enhanced Attribute/Color Reading
- 🔄 Application-Specific Profiles
- 🔄 Automated Testing Infrastructure
- 🔄 Security Hardening
- 🔄 Unicode/CJK Character Support
- 🔄 Documentation Updates

---

## 1. Performance Optimization (Priority: HIGH)

### 1.1 Position Caching System
**Estimated Effort:** 3-5 days
**Priority:** HIGH
**Impact:** Significantly improves responsiveness in large buffers

**Current Issue:**
- Position calculation is O(n) where n = row number
- Row 1000 requires ~1000 TextInfo.move() calls (~500ms)
- Impacts cursor tracking, window checking, and selection

**Implementation Strategy:**
```python
class PositionCache:
    def __init__(self, timeout_ms=1000):
        self._cache = {}  # bookmark -> (row, col, timestamp)
        self._timeout = timeout_ms

    def get(self, bookmark):
        if bookmark in self._cache:
            row, col, timestamp = self._cache[bookmark]
            if (time.time() * 1000 - timestamp) < self._timeout:
                return (row, col)
        return None

    def set(self, bookmark, row, col):
        self._cache[bookmark] = (row, col, time.time() * 1000)

    def invalidate(self):
        """Clear cache on terminal content changes."""
        self._cache.clear()
```

**Cache Invalidation Triggers:**
- New line added to terminal
- Terminal cleared
- Window resized
- Manual refresh command

**Benefits:**
- Near-instant position lookup for repeated queries
- Reduces O(n) to O(1) for cached positions
- Minimal memory overhead (~100 bytes per cached position)

### 1.2 Incremental Position Tracking
**Estimated Effort:** 2-3 days
**Priority:** MEDIUM
**Impact:** Faster cursor tracking updates

**Implementation:**
```python
def _trackIncrementalPosition(self, newInfo):
    """Calculate position incrementally from last known position."""
    if self._lastPosition and self._lastBookmark:
        lastRow, lastCol = self._lastPosition

        # Compare bookmarks to determine movement
        comparison = newInfo.bookmark.compareEndPoints(self._lastBookmark, "startToStart")

        if comparison == 0:
            return (lastRow, lastCol)  # No movement

        # If moved small distance, calculate incrementally
        if abs(comparison) < 10:
            return self._calculateIncremental(newInfo, lastRow, lastCol)

    # Fall back to full calculation
    return self._calculatePosition(newInfo)
```

### 1.3 Background Calculation for Large Selections
**Estimated Effort:** 4-5 days
**Priority:** LOW
**Impact:** Prevents UI freezing on large selections

**Implementation:**
- Use threading for selections > 100 lines
- Show progress indicator during calculation
- Allow cancellation of long-running operations
- Queue selection requests to prevent overlap

---

## 2. Security Hardening (Priority: HIGH)

### 2.1 Input Validation
**Estimated Effort:** 2-3 days
**Priority:** HIGH
**Impact:** Prevents crashes and security issues

**Areas to Validate:**
1. **Configuration Values**
   ```python
   def _validateWindowBounds(self, top, bottom, left, right):
       """Validate window boundary values."""
       if not all(isinstance(x, int) for x in [top, bottom, left, right]):
           raise ValueError("Window bounds must be integers")
       if top < 0 or left < 0:
           raise ValueError("Window bounds cannot be negative")
       if top > bottom or left > right:
           raise ValueError("Invalid window bounds order")
       return True
   ```

2. **User Input Sanitization**
   - Validate punctuation level (0-3 range)
   - Validate cursor delay (0-1000ms range)
   - Validate repeated symbols string (max length, valid characters)

3. **TextInfo Operations**
   - Validate bookmark existence before use
   - Check terminal object validity
   - Ensure positions are within buffer bounds

### 2.2 Resource Limits
**Estimated Effort:** 1-2 days
**Priority:** MEDIUM
**Impact:** Prevents resource exhaustion

**Implementation:**
```python
# Maximum selection size to prevent memory issues
MAX_SELECTION_ROWS = 10000
MAX_SELECTION_COLS = 1000

# Maximum cache size
MAX_POSITION_CACHE_SIZE = 100

# Timeout for long operations
OPERATION_TIMEOUT_MS = 5000
```

### 2.3 Error Recovery
**Estimated Effort:** 2-3 days
**Priority:** MEDIUM
**Impact:** Improved reliability

**Implementation:**
- Add try/except blocks with specific exception types (already done in v1.0.13)
- Log errors to NVDA log for debugging
- Provide user-friendly error messages
- Auto-recovery from common error states
- Reset to safe defaults on critical errors

---

## 3. Feature Enhancements (Priority: MEDIUM-HIGH)

### 3.1 Enhanced Attribute/Color Reading
**Estimated Effort:** 5-7 days
**Priority:** MEDIUM
**Status:** Partially implemented (basic ANSI detection exists)

**Current Limitations:**
- Only basic ANSI color code detection
- No comprehensive color name mapping
- Limited formatting attribute support
- No Windows Terminal API integration

**Enhancement Plan:**
1. **Robust ANSI Escape Sequence Parser**
   ```python
   class ANSIParser:
       def parse(self, text):
           """Parse ANSI codes and extract formatting."""
           codes = re.findall(r'\x1b\[([0-9;]+)m', text)
           return {
               'foreground': self._parseForeground(codes),
               'background': self._parseBackground(codes),
               'bold': '1' in codes,
               'italic': '3' in codes,
               'underline': '4' in codes,
               'strikethrough': '9' in codes,
           }
   ```

2. **Color Name Mapping**
   ```python
   COLOR_NAMES = {
       30: 'black', 31: 'red', 32: 'green', 33: 'yellow',
       34: 'blue', 35: 'magenta', 36: 'cyan', 37: 'white',
       90: 'bright black', 91: 'bright red', # ... etc
   }
   ```

3. **Format Announcement Options**
   - Brief mode: "Red text"
   - Detailed mode: "Red foreground, bold, underlined"
   - Change-only mode: Only announce when attributes change

### 3.2 Unicode and CJK Character Support
**Estimated Effort:** 3-4 days
**Priority:** MEDIUM
**Impact:** Proper column alignment for international text

**Current Issue:**
- Assumes all characters are 1 column wide
- CJK characters are 2 columns wide
- Combining characters are 0 columns wide

**Implementation:**
```python
import wcwidth

def _calculateColumnWidth(self, text):
    """Calculate display width accounting for Unicode."""
    return wcwidth.wcswidth(text)

def _extractColumnRange(self, text, startCol, endCol):
    """Extract column range with Unicode support."""
    width = 0
    startIdx = 0
    endIdx = len(text)

    for i, char in enumerate(text):
        charWidth = wcwidth.wcwidth(char)
        if width < startCol - 1:
            startIdx = i + 1
        if width >= endCol:
            endIdx = i
            break
        width += charWidth

    return text[startIdx:endIdx]
```

**Dependencies:**
- Add `wcwidth` library to requirements
- Test with Chinese, Japanese, Korean text
- Test with emoji and combining characters

### 3.3 Application-Specific Profiles
**Estimated Effort:** 2-3 weeks
**Priority:** LOW
**Impact:** Tailored experience for different applications

**Implementation Plan:**

1. **Profile System Architecture**
   ```python
   class ApplicationProfile:
       def __init__(self, app_name):
           self.app_name = app_name
           self.settings = {
               'punctuationLevel': 2,
               'cursorTrackingMode': 1,
               'keyEcho': True,
               # ... etc
           }
           self.window_definitions = []
           self.custom_gestures = {}
   ```

2. **Profile Detection**
   ```python
   def _detectApplication(self):
       """Detect current terminal application."""
       focus = api.getFocusObject()
       appModule = focus.appModule

       if hasattr(appModule, 'appName'):
           return appModule.appName
       return 'default'
   ```

3. **Default Profiles**
   - **vim/neovim**: Window tracking for status line silence
   - **tmux**: Multiple window definitions for panes
   - **htop**: Window tracking for process list only
   - **less/more**: Optimized reading commands
   - **git**: Enhanced attribute reading for diff colors

4. **Profile Management UI**
   - Create new profile from current settings
   - Edit existing profile
   - Import/export profiles
   - Reset to defaults

### 3.4 Multiple Window Definitions
**Estimated Effort:** 4-5 days
**Priority:** LOW
**Impact:** Support for split panes and complex layouts

**Implementation:**
```python
class WindowManager:
    def __init__(self):
        self.windows = []  # List of window definitions

    def add_window(self, name, top, bottom, left, right, mode='announce'):
        """Add a window definition."""
        window = {
            'name': name,
            'bounds': (top, bottom, left, right),
            'mode': mode,  # 'announce', 'silent', 'monitor'
            'enabled': True
        }
        self.windows.append(window)

    def get_window_at_position(self, row, col):
        """Get window containing position."""
        for window in self.windows:
            if window['enabled']:
                top, bottom, left, right = window['bounds']
                if top <= row <= bottom and left <= col <= right:
                    return window
        return None
```

---

## 4. Testing Infrastructure (Priority: HIGH)

### 4.1 Automated Unit Tests
**Estimated Effort:** 1-2 weeks
**Priority:** HIGH
**Impact:** Catches regressions early

**Current Status:**
- No automated tests exist
- Only manual testing documented in TESTING.md

**Implementation Plan:**

1. **Test Framework Setup**
   ```python
   # tests/test_tdsr.py
   import unittest
   from unittest.mock import Mock, patch

   class TestTDSR(unittest.TestCase):
       def setUp(self):
           """Set up test fixtures."""
           self.plugin = GlobalPlugin()

       def test_calculate_position(self):
           """Test position calculation."""
           # Mock TextInfo objects
           # Test various positions
           pass
   ```

2. **Test Categories**
   - **Unit Tests**: Test individual methods
   - **Integration Tests**: Test feature workflows
   - **Regression Tests**: Prevent known bugs
   - **Performance Tests**: Benchmark critical operations

3. **Test Coverage Goals**
   - Core methods: 80%+ coverage
   - Script handlers: 60%+ coverage
   - Configuration: 70%+ coverage
   - Overall: 70%+ coverage

### 4.2 Continuous Integration
**Estimated Effort:** 3-5 days
**Priority:** MEDIUM
**Impact:** Automated testing on every commit

**Implementation:**
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.7
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Run tests
        run: python -m pytest tests/
      - name: Check code style
        run: python -m flake8 addon/
```

### 4.3 Manual Testing Automation
**Estimated Effort:** 5-7 days
**Priority:** LOW
**Impact:** Faster manual testing cycles

**Implementation:**
- Scripted test scenarios
- Automated terminal setup
- Test data generation
- Result verification helpers

---

## 5. Documentation (Priority: MEDIUM)

### 5.1 User Documentation Updates
**Estimated Effort:** 3-4 days
**Priority:** MEDIUM
**Impact:** Better user adoption

**Areas to Update:**

1. **User Guide** (readme.html)
   - Add v1.0.14 features (rectangular selection, window tracking)
   - Update gesture reference
   - Add usage examples for all features
   - Add troubleshooting section

2. **Quick Start Guide**
   - Update QUICKSTART.md with new features
   - Add common use cases
   - Add tips and tricks section

3. **Feature Comparison Table**
   - Compare TDSR vs. Speakup features
   - Compare TDSR vs. other terminal solutions
   - Highlight unique features

### 5.2 Developer Documentation
**Estimated Effort:** 2-3 days
**Priority:** LOW
**Impact:** Easier contribution

**Areas to Document:**

1. **Architecture Overview**
   - Plugin structure
   - Event handling flow
   - TextInfo API usage patterns
   - Configuration system

2. **API Reference**
   - Public methods
   - Configuration options
   - Extension points
   - Testing utilities

3. **Contribution Guide**
   - Development setup
   - Coding standards
   - Testing requirements
   - Pull request process

### 5.3 Release Notes
**Estimated Effort:** 1 day per release
**Priority:** HIGH
**Impact:** Clear communication

**Template:**
```markdown
## [Version] - Date

### Added
- New feature 1
- New feature 2

### Changed
- Changed behavior 1

### Fixed
- Bug fix 1

### Known Issues
- Issue 1 (workaround: ...)

### Upgrade Notes
- Breaking change 1 (migration: ...)
```

---

## 6. Code Quality Improvements (Priority: LOW-MEDIUM)

### 6.1 Type Hints
**Estimated Effort:** 3-4 days
**Priority:** LOW
**Impact:** Better IDE support and error detection

**Implementation:**
```python
from typing import Tuple, Optional

def _calculatePosition(self, textInfo: textInfos.TextInfo) -> Tuple[int, int]:
    """Calculate row and column coordinates from TextInfo."""
    pass

def _getReviewPosition(self) -> Optional[textInfos.TextInfo]:
    """Return the current review position."""
    pass
```

### 6.2 Code Documentation
**Estimated Effort:** 2-3 days
**Priority:** LOW
**Impact:** Easier maintenance

**Areas to Improve:**
- Add docstrings to all public methods
- Document complex algorithms
- Add inline comments for tricky code
- Document magic numbers and constants

### 6.3 Refactoring Opportunities
**Estimated Effort:** 5-7 days
**Priority:** LOW
**Impact:** Better maintainability

**Opportunities:**

1. **Extract Configuration Manager**
   ```python
   class ConfigManager:
       def get_punctuation_level(self):
           return config.conf["TDSR"]["punctuationLevel"]

       def set_punctuation_level(self, level):
           if 0 <= level <= 3:
               config.conf["TDSR"]["punctuationLevel"] = level
   ```

2. **Extract Window Manager**
   - Move all window-related logic to separate class
   - Cleaner separation of concerns
   - Easier testing

3. **Extract Position Calculator**
   - Move coordinate calculation to helper class
   - Add caching logic
   - Easier optimization

---

## 7. User Experience Polish (Priority: MEDIUM)

### 7.1 Feedback Improvements
**Estimated Effort:** 2-3 days
**Priority:** MEDIUM
**Impact:** Better user understanding

**Enhancements:**

1. **Verbose Mode**
   - More detailed announcements for first-time users
   - Toggle with gesture
   - Gradually reduce verbosity as user learns

2. **Progress Indicators**
   - Show progress for long operations
   - "Calculating..." for slow position queries
   - "Copying... X% complete" for large selections

3. **Contextual Help**
   - On-demand gesture help (press gesture twice for help)
   - Context-sensitive tips
   - Command discovery hints

### 7.2 Gesture Consistency
**Estimated Effort:** 1-2 days
**Priority:** LOW
**Impact:** Easier learning

**Review:**
- Ensure logical gesture grouping
- Consistent modifier key usage
- Avoid conflicts with NVDA core gestures
- Document gesture rationale

### 7.3 Settings UI Enhancement
**Estimated Effort:** 3-4 days
**Priority:** LOW
**Impact:** Better configuration experience

**Improvements:**
- Group related settings in sections
- Add tooltips for each setting
- Add "Reset to defaults" button
- Add "What's this?" help links
- Visual feedback for setting changes

---

## 8. Platform and Compatibility (Priority: LOW)

### 8.1 Terminal Application Support
**Estimated Effort:** Ongoing
**Priority:** LOW
**Impact:** Wider compatibility

**Applications to Test:**
- Windows Terminal (✅ Supported)
- PowerShell (✅ Supported)
- cmd.exe (✅ Supported)
- WSL terminals (🔄 Test needed)
- Third-party terminals (Cmder, ConEmu, etc.)
- SSH clients (PuTTY, KiTTY, etc.)

### 8.2 NVDA Version Compatibility
**Estimated Effort:** Ongoing
**Priority:** LOW
**Impact:** Future-proofing

**Strategy:**
- Test with NVDA alpha/beta releases
- Monitor NVDA API changes
- Maintain compatibility with NVDA 2019.3+
- Add compatibility shims for older versions

---

## 9. Priority Matrix

### Immediate (Next Release - v1.0.15)
1. **Position Caching System** - Critical performance improvement
2. **Input Validation** - Security hardening
3. **Automated Unit Tests** - Foundation for quality
4. **User Documentation Updates** - Communication

**Estimated Timeline:** 2-3 weeks

### Short-term (v1.0.16-1.0.17)
1. **Enhanced Attribute Reading** - Complete Phase 3 feature
2. **Unicode/CJK Support** - International users
3. **Incremental Position Tracking** - Performance
4. **CI/CD Pipeline** - Automation

**Estimated Timeline:** 4-6 weeks

### Medium-term (v1.1.0)
1. **Application Profiles** - Power user feature
2. **Multiple Window Definitions** - Advanced layouts
3. **Type Hints** - Code quality
4. **Developer Documentation** - Contribution

**Estimated Timeline:** 8-12 weeks

### Long-term (v1.2.0+)
1. **Background Calculation** - Large selection support
2. **Platform Expansion** - More terminals
3. **Advanced Testing** - Performance benchmarks
4. **UI Polish** - Professional finish

**Estimated Timeline:** 12+ weeks

---

## 10. Risks and Mitigation

### Risk 1: Performance Degradation
**Probability:** Medium
**Impact:** High
**Mitigation:**
- Implement position caching (top priority)
- Add performance benchmarks
- Profile critical paths
- Set performance budgets

### Risk 2: NVDA API Changes
**Probability:** Low
**Impact:** High
**Mitigation:**
- Monitor NVDA development
- Participate in NVDA community
- Test with alpha/beta releases
- Maintain compatibility layer

### Risk 3: Terminal Application Diversity
**Probability:** High
**Impact:** Medium
**Mitigation:**
- Test with multiple terminals
- Document known limitations
- Provide terminal-specific workarounds
- Use graceful degradation

### Risk 4: User Adoption
**Probability:** Medium
**Impact:** Medium
**Mitigation:**
- Improve documentation
- Create video tutorials
- Provide example use cases
- Gather user feedback actively

---

## 11. Success Metrics

### Technical Metrics
- **Performance**: Position calculation < 100ms for row 100
- **Reliability**: Zero crashes in 100 hours of use
- **Test Coverage**: 70%+ code coverage
- **Code Quality**: Zero critical code smells

### User Metrics
- **Adoption**: 100+ active users
- **Satisfaction**: 4.5+ star rating
- **Support**: < 5% bug report rate
- **Engagement**: Active community discussions

### Feature Metrics
- **Completeness**: 100% of Phase 1-3 features
- **Documentation**: 100% of features documented
- **Testing**: 100% of features tested
- **Accessibility**: WCAG 2.1 AA compliance

---

## 12. Conclusion

TDSR for NVDA has achieved significant progress with **Phase 1** and **Phase 2** fully complete, and critical features from **Phase 3** now implemented. The project is well-positioned for continued development with clear priorities:

**Immediate Focus:**
1. Position caching for performance
2. Security hardening
3. Test infrastructure
4. Documentation updates

**Near-term Goals:**
1. Complete attribute reading
2. Unicode support
3. Application profiles

**Long-term Vision:**
1. Most comprehensive Windows terminal accessibility solution
2. Feature parity with Speakup
3. Active community and contributions
4. Professional-grade reliability

The roadmap is ambitious but achievable with consistent effort. Each phase builds on the solid foundation established in the initial releases.

---

## Appendix A: Feature Completion Status

| Feature | Phase | Status | Version |
|---------|-------|--------|---------|
| Line Navigation | 1 | ✅ Complete | v1.0.0 |
| Word Navigation | 1 | ✅ Complete | v1.0.0 |
| Character Navigation | 1 | ✅ Complete | v1.0.0 |
| Cursor Tracking | 1 | ✅ Complete | v1.0.0 |
| Key Echo | 1 | ✅ Complete | v1.0.0 |
| Settings Panel | 1 | ✅ Complete | v1.0.0 |
| Copy Mode | 1 | ✅ Complete | v1.0.0 |
| Continuous Reading | 1 | ✅ Complete | v1.0.11 |
| Screen Edge Navigation | 1 | ✅ Complete | v1.0.11 |
| Line Indentation | 1 | ✅ Complete | v1.0.11 |
| Position Announcement | 1 | ✅ Complete | v1.0.11 |
| Character Code | 1 | ✅ Complete | v1.0.11 |
| Punctuation Levels | 2 | ✅ Complete | v1.0.12 |
| Read From/To Position | 2 | ✅ Complete | v1.0.12 |
| Enhanced Selection | 2 | ✅ Complete | v1.0.12 |
| Rectangular Selection | 2 | ✅ Complete | v1.0.14 |
| Window Tracking | 3 | ✅ Complete | v1.0.14 |
| Window Reading | 3 | ✅ Complete | v1.0.14 |
| Attribute Reading | 3 | 🔄 Partial | v1.0.0 |
| Highlight Detection | 3 | 🔄 Partial | v1.0.8 |
| Application Profiles | 4 | ⏳ Planned | - |
| Position Caching | Opt | ⏳ Planned | - |
| Unicode Support | Opt | ⏳ Planned | - |

**Legend:**
- ✅ Complete: Fully implemented and tested
- 🔄 Partial: Basic implementation exists, needs enhancement
- ⏳ Planned: Documented but not yet implemented

---

*Document maintained by: TDSR Development Team*
*Last updated: 2026-02-21*
*Next review: After v1.0.15 release*
