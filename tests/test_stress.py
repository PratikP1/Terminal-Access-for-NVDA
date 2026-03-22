"""
Stress and load tests for Terminal Access performance-critical components.

All tests are marked with @pytest.mark.stress and @pytest.mark.slow
so they can be excluded from fast test runs:
    pytest tests/ -m "not stress"
"""

import time
import threading
import unittest
import pytest
from unittest.mock import Mock


@pytest.mark.stress
@pytest.mark.slow
class TestCacheStress(unittest.TestCase):
	"""Stress test PositionCache under concurrent load."""

	def test_1000_concurrent_sets(self):
		"""10 threads x 100 cache.set operations don't crash or corrupt."""
		from globalPlugins.terminalAccess import PositionCache

		cache = PositionCache()
		errors = []

		def writer(thread_id):
			try:
				for i in range(100):
					key = f"bk_{thread_id}_{i}"
					cache.set(key, thread_id, i)
			except Exception as e:
				errors.append(e)

		threads = [threading.Thread(target=writer, args=(t,)) for t in range(10)]
		for t in threads:
			t.start()
		for t in threads:
			t.join(timeout=10)

		self.assertEqual(len(errors), 0, f"Cache errors: {errors}")

	def test_cache_expiry_under_load(self):
		"""Cache entries expire after CACHE_TIMEOUT_S."""
		from globalPlugins.terminalAccess import PositionCache

		cache = PositionCache()
		original_timeout = PositionCache.CACHE_TIMEOUT_S
		PositionCache.CACHE_TIMEOUT_S = 0.05

		try:
			for i in range(50):
				cache.set(f"key_{i}", i, i)
			time.sleep(0.1)
			expired_count = sum(1 for i in range(50) if cache.get(f"key_{i}") is None)
			self.assertEqual(expired_count, 50, "All entries should have expired")
		finally:
			PositionCache.CACHE_TIMEOUT_S = original_timeout

	def test_lru_eviction(self):
		"""Cache evicts oldest entries when exceeding MAX_CACHE_SIZE."""
		from globalPlugins.terminalAccess import PositionCache

		cache = PositionCache()
		max_size = PositionCache.MAX_CACHE_SIZE

		for i in range(max_size + 50):
			cache.set(f"key_{i}", i, i)

		self.assertIsNone(cache.get("key_0"))
		self.assertIsNotNone(cache.get(f"key_{max_size + 49}"))


@pytest.mark.stress
@pytest.mark.slow
class TestTextDifferStress(unittest.TestCase):
	"""Stress test TextDiffer with rapid terminal output."""

	def test_100_rapid_updates(self):
		"""100 screen updates in tight loop all produce valid diff kinds."""
		from globalPlugins.terminalAccess import TextDiffer

		differ = TextDiffer()
		base = "line 1\nline 2\nline 3\n"

		for i in range(100):
			text = base + f"output line {i}\n"
			kind, content = differ.update(text)
			self.assertIsNotNone(kind)

	def test_large_buffer_diff(self):
		"""10,000-line buffer diff completes promptly."""
		from globalPlugins.terminalAccess import TextDiffer

		differ = TextDiffer()
		lines = [f"line {i}: {'x' * 80}" for i in range(10000)]
		text1 = "\n".join(lines)
		differ.update(text1)

		text2 = text1 + "\nnew line appended"

		start = time.time()
		kind, content = differ.update(text2)
		elapsed = time.time() - start

		self.assertLess(elapsed, 5.0, f"Diff took {elapsed:.2f}s")


@pytest.mark.stress
@pytest.mark.slow
class TestANSIStress(unittest.TestCase):
	"""Stress test ANSI parsing with adversarial input."""

	def test_adversarial_nested_sequences(self):
		"""Deeply nested/malformed ANSI sequences don't hang."""
		from globalPlugins.terminalAccess import ANSIParser

		malformed = "\x1b[" * 5000 + "m" * 5000

		start = time.time()
		result = ANSIParser.stripANSI(malformed)
		elapsed = time.time() - start

		self.assertLess(elapsed, 5.0, f"Adversarial ANSI took {elapsed:.2f}s")
		self.assertIsInstance(result, str)

	def test_large_clean_strip(self):
		"""100KB plain text through stripANSI."""
		from globalPlugins.terminalAccess import ANSIParser

		text = "Hello world! " * 8000

		start = time.time()
		result = ANSIParser.stripANSI(text)
		elapsed = time.time() - start

		self.assertLess(elapsed, 2.0, f"Large strip took {elapsed:.2f}s")
		self.assertEqual(result, text)

	def test_rgb_color_heavy(self):
		"""Text with RGB color on every character."""
		from globalPlugins.terminalAccess import ANSIParser

		colored = "".join(f"\x1b[38;2;{i%256};{(i*7)%256};{(i*13)%256}mX" for i in range(10000))
		colored += "\x1b[0m"

		start = time.time()
		result = ANSIParser.stripANSI(colored)
		elapsed = time.time() - start

		self.assertLess(elapsed, 5.0)
		self.assertEqual(len(result), 10000)


if __name__ == '__main__':
	unittest.main()
