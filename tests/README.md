# Terminal Access Test Suite

Automated tests for the Terminal Access for NVDA add-on.

## Overview

This directory contains **40 test files** with **778 passing tests** (67 skipped for native bridge). The test suite covers:

- Input validation and security hardening
- Position caching and thread safety
- Configuration management
- Selection operations and terminal detection
- Application profiles and profile management
- Bookmarks, tab management, search, URL extraction
- Error line detection and gesture conflict detection
- Settings panel (progressive disclosure)
- Native bridge and helper process (skipped without Rust DLL)
- Performance benchmarks and regression tests
- Integration workflows

## Python Version Compatibility

Tests run on Python 3.11, matching the NVDA 2025.1+ runtime.

## Quick Start

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run all tests
python run_tests.py

# Or use pytest directly
pytest tests/
```

## Test Files

| File | What it tests |
|------|--------------|
| `conftest.py` | pytest configuration and fixtures |
| `test_additional_coverage.py` | Gap-filling tests for edge cases |
| `test_ansi_unicode_profiles.py` | ANSI parsing, Unicode width, profile logic |
| `test_bookmarks.py` | Bookmark set/jump/list with line content labels |
| `test_cache.py` | PositionCache functionality and thread safety |
| `test_character_reading.py` | Character echo, phonetic, character code |
| `test_code_quality_refactors.py` | Refactoring correctness checks |
| `test_comprehensive_coverage.py` | Broad coverage gap-filling |
| `test_config.py` | Configuration management and sanitization |
| `test_cursor_attributes.py` | Cursor attribute reporting |
| `test_deferred_blank.py` | Deferred blank line handling |
| `test_error_detection.py` | ErrorLineDetector classification |
| `test_gainfocus_refactor.py` | event_gainFocus helper method extraction |
| `test_gesture_conflicts.py` | GestureConflictDetector |
| `test_gestures.py` | Gesture binding and command layer |
| `test_helper_e2e.py` | Helper process end-to-end |
| `test_helper_process.py` | Helper process IPC |
| `test_helper_protocol.py` | Helper protocol serialization |
| `test_hot_path_optimizations.py` | Hot path performance |
| `test_integration.py` | Integration tests for core workflows |
| `test_module_extraction.py` | Module extraction correctness |
| `test_native_bridge.py` | Rust FFI bridge (skipped without DLL) |
| `test_output_search.py` | OutputSearchManager |
| `test_performance.py` | Performance benchmarks |
| `test_performance_regression.py` | Performance regression detection |
| `test_plugin_initialization.py` | Plugin init sequence |
| `test_profile_management_ui.py` | Profile management UI |
| `test_profiles.py` | ApplicationProfile and ProfileManager |
| `test_selection.py` | Selection operations and terminal detection |
| `test_settings_panel.py` | Settings panel progressive disclosure |
| `test_stress.py` | Stress tests |
| `test_tab_management.py` | TabManager |
| `test_terminal_expansion.py` | Terminal app detection expansion |
| `test_terminal_recognition_fix.py` | Terminal recognition edge cases |
| `test_third_party_terminals.py` | Third-party terminal support |
| `test_translation_fallback.py` | Translation fallback behavior |
| `test_ui.py` | UI components |
| `test_unicode_advanced.py` | Advanced Unicode handling |
| `test_url_extractor.py` | URL extraction from terminal output |
| `test_validation.py` | Input validation and resource limits |
| `test_window_monitor.py` | WindowMonitor |

## Coverage

- **Total coverage**: ~54% (measures `terminalAccess.py` + `addon/lib/`)
- **CI threshold**: 70% on covered modules
- **lib/ modules**: Higher coverage since they were extracted for testability

## CI/CD

Tests run automatically via GitHub Actions on every push and pull request.

See `docs/testing/TESTING_GUIDE.md` for the full testing guide.
