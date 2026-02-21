"""
Test runner script for Terminal Access tests.

Run with: python run_tests.py
"""
import sys
import pytest

if __name__ == '__main__':
    # Run pytest with coverage
    exit_code = pytest.main([
        'tests/',
        '--verbose',
        '--cov=addon/globalPlugins',
        '--cov-report=term-missing',
        '--cov-report=html',
    ])
    sys.exit(exit_code)
