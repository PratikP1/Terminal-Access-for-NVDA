"""
Tests for safety and IPC validation hardening.

Covers:
1. Input validation for search and regex
2. URL safety
3. Named pipe JSON hardening
4. Native fallback reliability
"""
import json
import re
import struct
import time
import logging
from unittest.mock import Mock, MagicMock, patch

import pytest


# ================================================================
#  1. Search input validation
# ================================================================


class TestSearchPatternMaxLength:
    """test_search_pattern_max_length: pattern > 500 chars rejected."""

    def test_search_rejects_pattern_over_500_chars(self):
        from lib.search import OutputSearchManager

        terminal = Mock()
        # Provide a terminal with matching text so we know it returns 0
        # specifically because the pattern is too long, not because of
        # a missing terminal or empty buffer.
        terminal.makeTextInfo.return_value = Mock(text="a" * 600)
        mgr = OutputSearchManager(terminal)
        long_pattern = "a" * 501
        with pytest.raises(ValueError, match="too long"):
            mgr.search(long_pattern)

    def test_search_accepts_pattern_at_500_chars(self):
        from lib.search import OutputSearchManager

        terminal = Mock()
        terminal.makeTextInfo.return_value = Mock(text="a" * 500 + "\nother line")
        mgr = OutputSearchManager(terminal)
        pattern = "a" * 500
        result = mgr.search(pattern)
        # Should not be rejected for length
        assert result >= 0


class TestSearchMaxMatches:
    """test_search_max_matches: returns at most 1000 matches."""

    def test_search_caps_matches_at_1000(self):
        from lib.search import OutputSearchManager

        terminal = Mock()
        # Create text with 2000 lines each containing "error"
        lines = ["error on this line"] * 2000
        terminal.makeTextInfo.return_value = Mock(text="\n".join(lines))
        mgr = OutputSearchManager(terminal)
        result = mgr.search("error")
        assert result <= 1000


class TestSearchInvalidRegex:
    """test_search_invalid_regex: bad regex returns error, not crash."""

    def test_search_invalid_regex_raises_value_error(self):
        from lib.search import OutputSearchManager

        terminal = Mock()
        mgr = OutputSearchManager(terminal)
        with pytest.raises(ValueError, match="Invalid regular expression"):
            mgr.search("[invalid(", use_regex=True)

    def test_search_invalid_regex_no_crash(self):
        from lib.search import OutputSearchManager

        terminal = Mock()
        mgr = OutputSearchManager(terminal)
        # Should raise ValueError, not re.error or anything else
        try:
            mgr.search("(unclosed", use_regex=True)
        except ValueError:
            pass  # expected
        except Exception as e:
            pytest.fail(f"Unexpected exception type: {type(e).__name__}: {e}")


class TestSearchLineLengthCap:
    """test_search_line_length_cap: lines > 10000 chars truncated."""

    def test_long_lines_truncated_in_match_results(self):
        from lib.search import OutputSearchManager

        terminal = Mock()
        long_line = "x" * 15000
        terminal.makeTextInfo.return_value = Mock(text=long_line)
        mgr = OutputSearchManager(terminal)
        result = mgr.search("x")
        assert result >= 1
        # Check that stored match line_text is capped
        state = mgr._get_search_state()
        for match in state['matches']:
            line_text = match[1]  # line_text is at index 1
            assert len(line_text) <= 10000


# ================================================================
#  2. URL safety
# ================================================================


class TestUrlSafeHttp:
    """test_url_safe_http: http:// URLs are safe."""

    def test_http_url_is_safe(self):
        from lib.search import UrlExtractorManager

        mgr = UrlExtractorManager(Mock())
        assert mgr._is_safe_url("http://example.com") is True


class TestUrlSafeHttps:
    """test_url_safe_https: https:// URLs are safe."""

    def test_https_url_is_safe(self):
        from lib.search import UrlExtractorManager

        mgr = UrlExtractorManager(Mock())
        assert mgr._is_safe_url("https://example.com") is True


class TestUrlUnsafeFile:
    """test_url_unsafe_file: file:// URLs blocked."""

    def test_file_url_blocked(self):
        from lib.search import UrlExtractorManager

        mgr = UrlExtractorManager(Mock())
        assert mgr._is_safe_url("file:///etc/passwd") is False

    def test_file_url_case_insensitive(self):
        from lib.search import UrlExtractorManager

        mgr = UrlExtractorManager(Mock())
        assert mgr._is_safe_url("FILE:///C:/Windows/System32") is False


class TestUrlUnsafeJavascript:
    """test_url_unsafe_javascript: javascript: URLs blocked."""

    def test_javascript_url_blocked(self):
        from lib.search import UrlExtractorManager

        mgr = UrlExtractorManager(Mock())
        assert mgr._is_safe_url("javascript:alert(1)") is False


class TestUrlUnsafeData:
    """test_url_unsafe_data: data: URLs blocked."""

    def test_data_url_blocked(self):
        from lib.search import UrlExtractorManager

        mgr = UrlExtractorManager(Mock())
        assert mgr._is_safe_url("data:text/html,<h1>hi</h1>") is False


class TestUrlWarningSettingExists:
    """test_url_warning_setting_exists: confspec has urlOpenWarning."""

    def test_confspec_has_url_open_warning(self):
        from lib.config import confspec

        assert "urlOpenWarning" in confspec
        # Should default to True
        assert "default=True" in confspec["urlOpenWarning"]


# ================================================================
#  3. Named pipe JSON hardening
# ================================================================


class TestHelperPayloadMaxSize:
    """test_helper_payload_max_size: >1MB payload rejected."""

    def test_oversized_payload_rejected(self):
        from native.helper_process import HelperProcess

        hp = HelperProcess()
        # Simulate reading a message with payload > 1MB
        # The _read_message method should reject it
        oversized_length = 2 * 1024 * 1024  # 2MB
        header = struct.pack("<I", oversized_length)

        with patch.object(hp, '_read_exact', side_effect=[header]):
            result = hp._read_message()
            assert result is None


class TestHelperMalformedJson:
    """test_helper_malformed_json: bad JSON handled gracefully."""

    def test_malformed_json_returns_none(self):
        from native.helper_process import HelperProcess

        hp = HelperProcess()
        # Valid length header but invalid JSON payload
        bad_payload = b"not valid json{{"
        header = struct.pack("<I", len(bad_payload))

        with patch.object(hp, '_read_exact', side_effect=[header, bad_payload]):
            result = hp._read_message()
            assert result is None


class TestHelperBackoffIncreases:
    """test_helper_backoff_increases: restart delay doubles each time."""

    def test_backoff_doubles(self):
        from native.helper_process import HelperProcess

        hp = HelperProcess()
        # Check that _get_restart_delay returns exponentially increasing values
        assert hp._get_restart_delay(0) == 1.0
        assert hp._get_restart_delay(1) == 2.0
        assert hp._get_restart_delay(2) == 4.0
        assert hp._get_restart_delay(3) == 8.0

    def test_backoff_capped_at_30(self):
        from native.helper_process import HelperProcess

        hp = HelperProcess()
        # After many restarts, delay should not exceed 30 seconds
        assert hp._get_restart_delay(10) <= 30.0


class TestHelperMaxRestartAttempts:
    """test_helper_max_restart_attempts: stops after 5 attempts in 60s."""

    def test_max_restart_attempts_is_5(self):
        from native.helper_process import HelperProcess

        hp = HelperProcess()
        assert hp._MAX_RESTART_ATTEMPTS == 5

    def test_restart_window_is_60s(self):
        from native.helper_process import HelperProcess

        hp = HelperProcess()
        assert hp._RESTART_WINDOW == 60.0

    def test_should_not_restart_after_5_in_60s(self):
        from native.helper_process import HelperProcess

        hp = HelperProcess()
        now = time.monotonic()
        # Simulate 5 restarts within the window
        hp._restart_timestamps = [now - i for i in range(5)]
        assert hp._should_restart() is False

    def test_should_restart_if_old_attempts_expired(self):
        from native.helper_process import HelperProcess

        hp = HelperProcess()
        now = time.monotonic()
        # All restarts are older than 60s
        hp._restart_timestamps = [now - 120 for _ in range(5)]
        assert hp._should_restart() is True


# ================================================================
#  4. Native fallback reliability
# ================================================================


class TestNativeFallbackOnFfiError:
    """test_native_fallback_on_ffi_error: FFI error sets _native_available=False."""

    def test_ffi_error_disables_native(self):
        from native import termaccess_bridge as bridge

        # Save originals
        orig_dll = bridge._dll
        orig_attempted = bridge._dll_load_attempted
        orig_native_avail = getattr(bridge, '_native_available', None)

        try:
            # Create a mock DLL that raises on call
            mock_dll = Mock()
            mock_dll.ta_strip_ansi.side_effect = OSError("FFI crash")
            bridge._dll = mock_dll
            bridge._dll_load_attempted = True
            bridge._native_available = True

            bridge.safe_native_strip_ansi("test")

            assert bridge._native_available is False
        finally:
            bridge._dll = orig_dll
            bridge._dll_load_attempted = orig_attempted
            if orig_native_avail is not None:
                bridge._native_available = orig_native_avail
            elif hasattr(bridge, '_native_available'):
                delattr(bridge, '_native_available')


class TestNativeFallbackLoggedOnce:
    """test_native_fallback_logged_once: error logged only once, not every call."""

    def test_ffi_error_logged_once(self):
        from native import termaccess_bridge as bridge

        orig_dll = bridge._dll
        orig_attempted = bridge._dll_load_attempted
        orig_native_avail = getattr(bridge, '_native_available', None)
        orig_logged = getattr(bridge, '_ffi_error_logged', None)

        try:
            mock_dll = Mock()
            mock_dll.ta_strip_ansi.side_effect = OSError("FFI crash")
            bridge._dll = mock_dll
            bridge._dll_load_attempted = True
            bridge._native_available = True
            bridge._ffi_error_logged = False

            with patch.object(bridge.log, 'error') as mock_log:
                bridge.safe_native_strip_ansi("test1")
                bridge.safe_native_strip_ansi("test2")
                # Error should be logged only once
                assert mock_log.call_count == 1
        finally:
            bridge._dll = orig_dll
            bridge._dll_load_attempted = orig_attempted
            if orig_native_avail is not None:
                bridge._native_available = orig_native_avail
            elif hasattr(bridge, '_native_available'):
                delattr(bridge, '_native_available')
            if orig_logged is not None:
                bridge._ffi_error_logged = orig_logged
            elif hasattr(bridge, '_ffi_error_logged'):
                delattr(bridge, '_ffi_error_logged')


class TestNativeFallbackCount:
    """test_native_fallback_count: _fallback_count increments."""

    def test_fallback_count_increments(self):
        from native import termaccess_bridge as bridge

        orig_dll = bridge._dll
        orig_attempted = bridge._dll_load_attempted
        orig_native_avail = getattr(bridge, '_native_available', None)
        orig_count = getattr(bridge, '_fallback_count', None)

        try:
            bridge._dll = None
            bridge._dll_load_attempted = True
            bridge._native_available = False
            bridge._fallback_count = 0

            bridge.safe_native_strip_ansi("test1")
            bridge.safe_native_strip_ansi("test2")
            bridge.safe_native_strip_ansi("test3")

            assert bridge._fallback_count == 3
        finally:
            bridge._dll = orig_dll
            bridge._dll_load_attempted = orig_attempted
            if orig_native_avail is not None:
                bridge._native_available = orig_native_avail
            elif hasattr(bridge, '_native_available'):
                delattr(bridge, '_native_available')
            if orig_count is not None:
                bridge._fallback_count = orig_count
            elif hasattr(bridge, '_fallback_count'):
                delattr(bridge, '_fallback_count')
