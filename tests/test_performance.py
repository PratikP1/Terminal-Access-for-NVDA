"""
Performance and regression tests for Terminal Access.

Tests for performance benchmarks and known bug prevention.
"""
import unittest
from unittest.mock import Mock, patch
import time
import sys


class TestPerformanceBenchmarks(unittest.TestCase):
    """Test performance of critical operations."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_cache_lookup_performance(self):
        """Test cache lookup is fast."""
        cache = self.terminalAccess.PositionCache()
        bookmark = Mock()
        bookmark.__str__ = Mock(return_value="perf_test")

        # Populate cache
        cache.set(bookmark, 100, 50)

        # Measure lookup time
        start = time.time()
        for _ in range(1000):
            cache.get(bookmark)
        elapsed = time.time() - start

        # Should be very fast (< 0.1 seconds for 1000 lookups)
        self.assertLess(elapsed, 0.1, f"Cache lookups too slow: {elapsed}s for 1000 lookups")

    def test_cache_set_performance(self):
        """Test cache set operations are fast."""
        cache = self.terminalAccess.PositionCache()

        start = time.time()
        for i in range(100):
            bookmark = Mock()
            bookmark.__str__ = Mock(return_value=f"perf_{i}")
            cache.set(bookmark, i, i)
        elapsed = time.time() - start

        # Should be fast (< 0.1 seconds for 100 sets)
        self.assertLess(elapsed, 0.1, f"Cache set operations too slow: {elapsed}s for 100 sets")

    def test_validation_performance(self):
        """Test validation functions are fast."""
        start = time.time()
        for i in range(1000):
            self.terminalAccess._validateInteger(i % 100, 0, 100, 50, "test")
        elapsed = time.time() - start

        # Should be very fast (< 0.05 seconds for 1000 validations)
        self.assertLess(elapsed, 0.05, f"Validation too slow: {elapsed}s for 1000 validations")


class TestRegressionPrevention(unittest.TestCase):
    """Tests to prevent known bugs from recurring."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_cache_expiration_regression(self):
        """Regression test: Cache entries must expire after timeout."""
        cache = self.terminalAccess.PositionCache()
        bookmark = Mock()
        bookmark.__str__ = Mock(return_value="regression_expire")

        # Set very short timeout
        original_timeout = cache.CACHE_TIMEOUT_MS
        cache.CACHE_TIMEOUT_MS = 50  # 50ms

        cache.set(bookmark, 10, 5)

        # Should be valid immediately
        result1 = cache.get(bookmark)
        self.assertIsNotNone(result1, "Cache entry should be valid immediately")

        # Wait for expiration
        time.sleep(0.1)  # 100ms

        # Should be expired
        result2 = cache.get(bookmark)
        self.assertIsNone(result2, "Cache entry should expire after timeout")

        cache.CACHE_TIMEOUT_MS = original_timeout

    def test_cache_size_limit_regression(self):
        """Regression test: Cache must respect size limit."""
        cache = self.terminalAccess.PositionCache()

        # Fill to max size
        for i in range(cache.MAX_CACHE_SIZE):
            bookmark = Mock()
            bookmark.__str__ = Mock(return_value=f"reg_{i}")
            cache.set(bookmark, i, i)

        self.assertEqual(len(cache._cache), cache.MAX_CACHE_SIZE,
                         "Cache should be at max size")

        # Add one more
        extra_bookmark = Mock()
        extra_bookmark.__str__ = Mock(return_value="extra")
        cache.set(extra_bookmark, 999, 999)

        # Size should not exceed max
        self.assertEqual(len(cache._cache), cache.MAX_CACHE_SIZE,
                         "Cache size should not exceed MAX_CACHE_SIZE")

    def test_validation_boundary_regression(self):
        """Regression test: Validation must handle boundary values correctly."""
        # At boundaries
        self.assertEqual(self.terminalAccess._validateInteger(0, 0, 10, 5, "test"), 0)
        self.assertEqual(self.terminalAccess._validateInteger(10, 0, 10, 5, "test"), 10)

        # Outside boundaries
        self.assertEqual(self.terminalAccess._validateInteger(-1, 0, 10, 5, "test"), 5)
        self.assertEqual(self.terminalAccess._validateInteger(11, 0, 10, 5, "test"), 5)

    def test_selection_size_validation_regression(self):
        """Regression test: Selection size validation must work correctly."""
        # Valid selection
        valid, msg = self.terminalAccess._validateSelectionSize(1, 100, 1, 80)
        self.assertTrue(valid, "Valid selection should pass")
        self.assertIsNone(msg, "Valid selection should have no error message")

        # Exceeds row limit
        invalid_rows, msg_rows = self.terminalAccess._validateSelectionSize(1, 10001, 1, 80)
        self.assertFalse(invalid_rows, "Oversized row selection should fail")
        self.assertIsNotNone(msg_rows, "Oversized row selection should have error message")

        # Exceeds column limit
        invalid_cols, msg_cols = self.terminalAccess._validateSelectionSize(1, 100, 1, 1001)
        self.assertFalse(invalid_cols, "Oversized column selection should fail")
        self.assertIsNotNone(msg_cols, "Oversized column selection should have error message")

    def test_string_truncation_regression(self):
        """Regression test: String validation must truncate long strings."""
        long_string = "a" * 100
        result = self.terminalAccess._validateString(long_string, 50, "default", "test")

        self.assertEqual(len(result), 50, "Long string should be truncated to max length")
        self.assertEqual(result, "a" * 50, "Truncated string should contain correct characters")

    def test_config_sanitization_regression(self):
        """Regression test: Config sanitization must fix invalid values."""
        from globalPlugins.terminalAccess import GlobalPlugin

        config_mock = sys.modules['config']
        config_dict = config_mock.conf["terminalAccess"]

        # Set invalid values
        config_dict["cursorTrackingMode"] = 999
        config_dict["punctuationLevel"] = -5
        config_dict["cursorDelay"] = 5000

        with patch('gui.settingsDialogs.NVDASettingsDialog'):
            plugin = GlobalPlugin()

            # Should be sanitized to valid defaults
            self.assertGreaterEqual(config_dict["cursorTrackingMode"], 0)
            self.assertLessEqual(config_dict["cursorTrackingMode"], 3)
            self.assertGreaterEqual(config_dict["punctuationLevel"], 0)
            self.assertLessEqual(config_dict["punctuationLevel"], 3)
            self.assertGreaterEqual(config_dict["cursorDelay"], 0)
            self.assertLessEqual(config_dict["cursorDelay"], 1000)


class TestThreadSafety(unittest.TestCase):
    """Test thread safety of concurrent operations."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_cache_concurrent_access(self):
        """Test cache handles concurrent read/write safely."""
        import threading

        cache = self.terminalAccess.PositionCache()
        bookmark = Mock()
        bookmark.__str__ = Mock(return_value="concurrent_test")

        errors = []

        def writer():
            try:
                for i in range(50):
                    cache.set(bookmark, i, i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(50):
                    cache.get(bookmark)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(3):
            t1 = threading.Thread(target=writer)
            t2 = threading.Thread(target=reader)
            threads.extend([t1, t2])

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join(timeout=5.0)

        # Should complete without errors
        self.assertEqual(len(errors), 0, f"Concurrent access caused errors: {errors}")

    def test_cache_clear_while_reading(self):
        """Test cache can be cleared while being read."""
        import threading

        cache = self.terminalAccess.PositionCache()

        # Populate cache
        for i in range(10):
            bookmark = Mock()
            bookmark.__str__ = Mock(return_value=f"clear_test_{i}")
            cache.set(bookmark, i, i)

        errors = []

        def reader():
            try:
                for i in range(100):
                    bookmark = Mock()
                    bookmark.__str__ = Mock(return_value=f"clear_test_{i % 10}")
                    cache.get(bookmark)
            except Exception as e:
                errors.append(e)

        def clearer():
            try:
                for _ in range(10):
                    time.sleep(0.01)
                    cache.clear()
            except Exception as e:
                errors.append(e)

        # Run concurrently
        t1 = threading.Thread(target=reader)
        t2 = threading.Thread(target=clearer)

        t1.start()
        t2.start()

        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        # Should complete without errors
        self.assertEqual(len(errors), 0, f"Clear while reading caused errors: {errors}")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess

    def test_validate_integer_with_float(self):
        """Test _validateInteger handles float input."""
        # Float that can be converted to int
        result = self.terminalAccess._validateInteger(5.7, 0, 10, 5, "test")
        self.assertEqual(result, 5, "Float should be converted to int")

    def test_validate_integer_with_none(self):
        """Test _validateInteger handles None input."""
        result = self.terminalAccess._validateInteger(None, 0, 10, 5, "test")
        self.assertEqual(result, 5, "None should return default")

    def test_validate_string_with_none(self):
        """Test _validateString handles None input."""
        result = self.terminalAccess._validateString(None, 10, "default", "test")
        self.assertEqual(result, "default", "None should return default")

    def test_validate_selection_with_negative_coordinates(self):
        """Test _validateSelectionSize handles negative coordinates."""
        # Should work with absolute values
        valid, msg = self.terminalAccess._validateSelectionSize(-5, 5, -10, 10)
        # Since we use abs() in the function, this should be valid
        self.assertTrue(valid)

    def test_cache_with_invalid_bookmark(self):
        """Test cache handles invalid bookmark gracefully."""
        cache = self.terminalAccess.PositionCache()

        # Try to get with None (should handle str() call)
        try:
            result = cache.get(None)
            # Should either return None or handle gracefully
            self.assertIsNone(result)
        except (AttributeError, TypeError):
            # This is also acceptable
            pass

    def test_empty_punctuation_sets(self):
        """Test PUNCT_NONE has truly empty set."""
        punct_none = self.terminalAccess.PUNCTUATION_SETS[self.terminalAccess.PUNCT_NONE]
        self.assertIsInstance(punct_none, set)
        self.assertEqual(len(punct_none), 0)
        self.assertFalse(punct_none)  # Empty set is falsy


if __name__ == '__main__':
    unittest.main()
