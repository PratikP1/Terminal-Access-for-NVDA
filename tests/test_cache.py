"""
Unit tests for PositionCache class.

Tests the position caching system added in v1.0.15.
"""
import unittest
from unittest.mock import Mock, patch
import time
import threading


class TestPositionCache(unittest.TestCase):
    """Test PositionCache class."""

    def setUp(self):
        """Set up test fixtures."""
        from globalPlugins import terminalAccess
        self.terminalAccess = terminalAccess
        self.cache = terminalAccess.PositionCache()

    def test_cache_initialization(self):
        """Test cache initializes empty."""
        self.assertEqual(len(self.cache._cache), 0)

    def test_cache_set_and_get(self):
        """Test setting and getting a cached position."""
        bookmark = Mock()
        bookmark.__str__ = Mock(return_value="test_bookmark_1")

        self.cache.set(bookmark, 10, 5)
        result = self.cache.get(bookmark)

        self.assertIsNotNone(result)
        self.assertEqual(result, (10, 5))

    def test_cache_get_nonexistent(self):
        """Test getting a non-existent cache entry."""
        bookmark = Mock()
        bookmark.__str__ = Mock(return_value="nonexistent")

        result = self.cache.get(bookmark)
        self.assertIsNone(result)

    def test_cache_expiration(self):
        """Test cache entries expire after timeout."""
        bookmark = Mock()
        bookmark.__str__ = Mock(return_value="test_bookmark_expire")

        # Set timeout to very small value for testing
        original_timeout = self.cache.CACHE_TIMEOUT_MS
        self.cache.CACHE_TIMEOUT_MS = 10  # 10ms

        self.cache.set(bookmark, 10, 5)

        # Should be valid immediately
        result = self.cache.get(bookmark)
        self.assertIsNotNone(result)

        # Wait for expiration
        time.sleep(0.02)  # 20ms

        # Should be expired
        result = self.cache.get(bookmark)
        self.assertIsNone(result)

        # Restore original timeout
        self.cache.CACHE_TIMEOUT_MS = original_timeout

    def test_cache_max_size_limit(self):
        """Test cache respects maximum size limit."""
        # Fill cache to max size
        for i in range(self.cache.MAX_CACHE_SIZE):
            bookmark = Mock()
            bookmark.__str__ = Mock(return_value=f"bookmark_{i}")
            self.cache.set(bookmark, i, i)

        self.assertEqual(len(self.cache._cache), self.cache.MAX_CACHE_SIZE)

        # Add one more - should evict oldest
        new_bookmark = Mock()
        new_bookmark.__str__ = Mock(return_value="new_bookmark")
        self.cache.set(new_bookmark, 999, 999)

        # Cache size should remain at max
        self.assertEqual(len(self.cache._cache), self.cache.MAX_CACHE_SIZE)

    def test_cache_clear(self):
        """Test clearing the cache."""
        # Add some entries
        for i in range(5):
            bookmark = Mock()
            bookmark.__str__ = Mock(return_value=f"bookmark_{i}")
            self.cache.set(bookmark, i, i)

        self.assertEqual(len(self.cache._cache), 5)

        self.cache.clear()

        self.assertEqual(len(self.cache._cache), 0)

    def test_cache_invalidate_specific(self):
        """Test invalidating a specific cache entry."""
        bookmark1 = Mock()
        bookmark1.__str__ = Mock(return_value="bookmark_1")
        bookmark2 = Mock()
        bookmark2.__str__ = Mock(return_value="bookmark_2")

        self.cache.set(bookmark1, 10, 5)
        self.cache.set(bookmark2, 20, 10)

        self.assertEqual(len(self.cache._cache), 2)

        self.cache.invalidate(bookmark1)

        self.assertEqual(len(self.cache._cache), 1)
        self.assertIsNone(self.cache.get(bookmark1))
        self.assertIsNotNone(self.cache.get(bookmark2))

    def test_cache_thread_safety(self):
        """Test cache is thread-safe."""
        bookmark = Mock()
        bookmark.__str__ = Mock(return_value="thread_test")

        def writer_thread():
            for i in range(100):
                self.cache.set(bookmark, i, i)

        def reader_thread():
            for i in range(100):
                self.cache.get(bookmark)

        threads = []
        for _ in range(5):
            t1 = threading.Thread(target=writer_thread)
            t2 = threading.Thread(target=reader_thread)
            threads.extend([t1, t2])
            t1.start()
            t2.start()

        for t in threads:
            t.join()

        # Should complete without errors

    def test_cache_multiple_bookmarks(self):
        """Test caching multiple different bookmarks."""
        bookmarks = []
        for i in range(10):
            bookmark = Mock()
            bookmark.__str__ = Mock(return_value=f"bookmark_{i}")
            bookmarks.append(bookmark)
            self.cache.set(bookmark, i * 10, i * 5)

        # Verify all are cached
        for i, bookmark in enumerate(bookmarks):
            result = self.cache.get(bookmark)
            self.assertIsNotNone(result)
            self.assertEqual(result, (i * 10, i * 5))

    def test_cache_update_existing(self):
        """Test updating an existing cache entry."""
        bookmark = Mock()
        bookmark.__str__ = Mock(return_value="update_test")

        self.cache.set(bookmark, 10, 5)
        result1 = self.cache.get(bookmark)
        self.assertEqual(result1, (10, 5))

        # Update with new values
        self.cache.set(bookmark, 20, 10)
        result2 = self.cache.get(bookmark)
        self.assertEqual(result2, (20, 10))


if __name__ == '__main__':
    unittest.main()
