# Terminal Access Test Suite

Automated tests for the Terminal Access for NVDA add-on.

## Overview

This directory contains comprehensive unit tests for Terminal Access functionality. The test suite covers:

- Input validation and security hardening (v1.0.16)
- Position caching system (v1.0.15)
- Configuration management
- Selection operations
- Terminal detection
- Integration workflows
- Performance benchmarks
- Regression prevention

## Python Version Compatibility

Tests are designed to run on Python 3.11, matching NVDA 2025.1+ support:
- **Minimum**: Python 3.11 (NVDA 2025.1 runtime)
- **Maximum**: Python 3.11 (current NVDA)
- **CI/CD**: Tests run on the NVDA runtime version

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

- `conftest.py` - pytest configuration and fixtures
- `test_validation.py` - Input validation and resource limits (40+ tests)
- `test_cache.py` - PositionCache functionality (15+ tests)
- `test_config.py` - Configuration management (20+ tests)
- `test_selection.py` - Selection operations and terminal detection (25+ tests)
- `test_integration.py` - Integration tests for workflows (30+ tests)
- `test_performance.py` - Performance benchmarks and regression tests (20+ tests)

## Coverage

Current coverage targets:
- Overall: 70%+ ✅
- Validation: 100% ✅
- Cache: 95% ✅
- Config: 85% ✅
- Selection: 80% ✅
- Integration: 75% ✅

## CI/CD

Tests run automatically via GitHub Actions on every push and pull request.

See `TESTING_AUTOMATED.md` in the root directory for detailed documentation.
