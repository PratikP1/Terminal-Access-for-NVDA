# Terminal Access for NVDA - Native Bridge Parity Tests
# Copyright (C) 2024 Pratik Patel
# This add-on is covered by the GNU General Public License, version 3.
# See the file LICENSE for more details.

"""
Parity tests for the native Rust bridge.

These tests verify that the Rust implementations (via ctypes) produce
identical results to the pure-Python implementations for all inputs.
Tests are skipped when the native DLL is not available.
"""

import os
import re
import sys
import time
import unittest

# Ensure addon/ is on sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon"))

# Import Python implementations
from globalPlugins.terminalAccess import TextDiffer, PositionCache, ANSIParser

# Try to import native implementations
try:
	from native.termaccess_bridge import (
		native_available,
		NativeTextDiffer,
		native_strip_ansi,
		native_search_text,
		NativePositionCache,
		get_native_version,
		native_char_width,
		native_text_width,
		native_extract_column_range,
		native_find_column_position,
	)
	_HAS_NATIVE = native_available()
except Exception:
	_HAS_NATIVE = False

_skip_msg = "Native DLL not available"


@unittest.skipUnless(_HAS_NATIVE, _skip_msg)
class TestNativeVersion(unittest.TestCase):
	"""Test that the native DLL is loadable and reports a version."""

	def test_version_is_string(self):
		ver = get_native_version()
		self.assertIsInstance(ver, str)
		self.assertTrue(len(ver) > 0)

	def test_version_format(self):
		ver = get_native_version()
		# Should be semver-like: X.Y.Z
		parts = ver.split(".")
		self.assertEqual(len(parts), 3)
		for part in parts:
			self.assertTrue(part.isdigit(), f"Version part '{part}' is not numeric")


@unittest.skipUnless(_HAS_NATIVE, _skip_msg)
class TestTextDifferParity(unittest.TestCase):
	"""Verify that NativeTextDiffer produces identical results to TextDiffer."""

	def _run_parity(self, updates):
		"""Run the same sequence of updates through both and compare results."""
		py = TextDiffer()
		native = NativeTextDiffer()

		for i, text in enumerate(updates):
			py_result = py.update(text)
			native_result = native.update(text)
			self.assertEqual(
				py_result,
				native_result,
				f"Mismatch at update {i} for text={text!r}: "
				f"python={py_result}, native={native_result}",
			)

	def test_initial(self):
		self._run_parity(["hello world"])

	def test_unchanged(self):
		self._run_parity(["hello", "hello"])

	def test_appended(self):
		self._run_parity(["line1\n", "line1\nline2\n"])

	def test_changed(self):
		self._run_parity(["hello", "goodbye"])

	def test_last_line_updated(self):
		self._run_parity([
			"line1\nline2\nprogress: 50%",
			"line1\nline2\nprogress: 75%",
		])

	def test_empty_text(self):
		self._run_parity(["", ""])

	def test_trailing_spaces_normalized(self):
		"""conhost pads lines with trailing spaces."""
		self._run_parity([
			"hello   \nworld   \n",
			"hello\nworld\n",
		])

	def test_unicode(self):
		self._run_parity([
			"hello 世界\n",
			"hello 世界\nnew line\n",
		])

	def test_multiple_appends(self):
		self._run_parity([
			"a\n",
			"a\nb\n",
			"a\nb\nc\n",
			"a\nb\nc\nd\n",
		])

	def test_mixed_operations(self):
		self._run_parity([
			"initial\n",
			"initial\nappended\n",
			"initial\nappended\n",  # unchanged
			"completely different\n",  # changed
			"completely different\nmore stuff\n",  # appended
		])

	def test_reset(self):
		py = TextDiffer()
		native = NativeTextDiffer()

		py.update("hello")
		native.update("hello")

		py.reset()
		native.reset()

		self.assertEqual(py.update("world"), native.update("world"))

	def test_last_text(self):
		py = TextDiffer()
		native = NativeTextDiffer()

		self.assertIsNone(py.last_text)
		self.assertIsNone(native.last_text)

		py.update("hello")
		native.update("hello")

		self.assertEqual(py.last_text, native.last_text)

	def test_large_text(self):
		"""Test with realistic terminal output size."""
		base = "\n".join(f"line {i}: some content here" for i in range(500)) + "\n"
		appended = base + "new output line\n"
		self._run_parity([base, appended])

	def test_progress_bar_simulation(self):
		"""Simulate a progress bar updating the last line."""
		lines = "Building project...\n"
		updates = [lines + f"Progress: [{('=' * i):50s}] {i*2}%" for i in range(51)]
		self._run_parity(updates)


@unittest.skipUnless(_HAS_NATIVE, _skip_msg)
class TestAnsiStripParity(unittest.TestCase):
	"""Verify that native_strip_ansi produces identical results to ANSIParser.stripANSI."""

	def _check(self, text):
		py_result = ANSIParser.stripANSI(text)
		native_result = native_strip_ansi(text)
		self.assertEqual(
			py_result,
			native_result,
			f"Mismatch for input={text!r}: python={py_result!r}, native={native_result!r}",
		)

	def test_no_ansi(self):
		self._check("plain text")

	def test_empty(self):
		self._check("")

	def test_sgr_color(self):
		self._check("\x1b[31mRed text\x1b[0m")

	def test_sgr_bold(self):
		self._check("\x1b[1mBold\x1b[0m normal")

	def test_256_color(self):
		self._check("\x1b[38;5;196mRed 256\x1b[0m")

	def test_rgb_color(self):
		self._check("\x1b[38;2;255;128;0mOrange\x1b[0m")

	def test_cursor_movement(self):
		self._check("\x1b[10;20Htext at position")

	def test_osc_title(self):
		self._check("\x1b]0;Terminal Title\x07rest")

	def test_mixed_sequences(self):
		self._check("\x1b[1;31mBold Red\x1b[0m normal \x1b[32mGreen\x1b[0m end")

	def test_unicode_preserved(self):
		self._check("\x1b[31m日本語テスト\x1b[0m")

	def test_complex_prompt(self):
		"""Realistic terminal prompt with multiple ANSI sequences."""
		prompt = (
			"\x1b[1;32muser@host\x1b[0m:\x1b[1;34m~/project\x1b[0m$ "
			"echo \x1b[33mhello\x1b[0m"
		)
		self._check(prompt)

	def test_hyperlink_osc8(self):
		self._check("\x1b]8;;https://example.com\x07Click here\x1b]8;;\x07")

	def test_only_ansi(self):
		self._check("\x1b[31m\x1b[0m")

	def test_incomplete_sequence(self):
		"""Malformed ANSI sequence at end of string."""
		self._check("text\x1b[")

	def test_large_input(self):
		"""Performance: strip ANSI from large text."""
		line = "\x1b[32m" + "x" * 200 + "\x1b[0m\n"
		text = line * 500
		self._check(text)


@unittest.skipUnless(_HAS_NATIVE, _skip_msg)
class TestSearchParity(unittest.TestCase):
	"""Verify that native_search_text matches the Python search logic."""

	def _python_search(self, text, pattern, case_sensitive=True, use_regex=False):
		"""Replicate the Python search logic from terminalAccess.py."""
		# Strip ANSI
		stripped = ANSIParser.stripANSI(text)
		lines = stripped.split("\n")

		if use_regex:
			flags = 0 if case_sensitive else re.IGNORECASE
			compiled = re.compile(pattern, flags)
			results = []
			for i, line in enumerate(lines):
				m = compiled.search(line)
				if m:
					results.append((i, m.start(), line))
		else:
			search_pattern = pattern if case_sensitive else pattern.lower()
			results = []
			for i, line in enumerate(lines):
				target = line if case_sensitive else line.lower()
				idx = target.find(search_pattern)
				if idx >= 0:
					results.append((i, idx, line))

		return results

	def _check(self, text, pattern, case_sensitive=True, use_regex=False):
		py_result = self._python_search(text, pattern, case_sensitive, use_regex)
		native_result = native_search_text(text, pattern, case_sensitive, use_regex)
		self.assertEqual(
			py_result,
			native_result,
			f"Search mismatch for pattern={pattern!r}, cs={case_sensitive}, regex={use_regex}",
		)

	def test_literal_case_sensitive(self):
		self._check("foo\nbar\nbaz", "bar")

	def test_literal_case_insensitive(self):
		self._check("Hello\nWorld\nhello", "hello", case_sensitive=False)

	def test_literal_no_match(self):
		self._check("foo\nbar", "xyz")

	def test_regex_basic(self):
		self._check("error: file not found\nwarning: unused", r"error|warning", use_regex=True)

	def test_regex_case_insensitive(self):
		self._check("Error: bad\nERROR: worse", "error", case_sensitive=False, use_regex=True)

	def test_ansi_stripped_before_search(self):
		text = "\x1b[31merror\x1b[0m message\nnormal line"
		self._check(text, "error")

	def test_empty_text(self):
		self._check("", "pattern")

	def test_empty_pattern(self):
		# Empty pattern matches every line in both implementations
		self._check("a\nb\nc", "")

	def test_multiple_matches(self):
		text = "apple\nbanana\napricot\navocado"
		self._check(text, "a", case_sensitive=False)

	def test_unicode_search(self):
		self._check("hello\n世界\nfoo", "世界")

	def test_invalid_regex_raises(self):
		with self.assertRaises(ValueError):
			native_search_text("text", r"[invalid", use_regex=True)


@unittest.skipUnless(_HAS_NATIVE, _skip_msg)
class TestPositionCacheParity(unittest.TestCase):
	"""Verify NativePositionCache matches PositionCache behavior."""

	def test_get_set(self):
		py = PositionCache()
		native = NativePositionCache()

		py.set("bm1", 10, 20)
		native.set("bm1", 10, 20)

		self.assertEqual(py.get("bm1"), native.get("bm1"))

	def test_get_miss(self):
		py = PositionCache()
		native = NativePositionCache()

		self.assertEqual(py.get("missing"), native.get("missing"))
		self.assertIsNone(native.get("missing"))

	def test_clear(self):
		py = PositionCache()
		native = NativePositionCache()

		py.set("bm1", 1, 2)
		native.set("bm1", 1, 2)

		py.clear()
		native.clear()

		self.assertEqual(py.get("bm1"), native.get("bm1"))
		self.assertIsNone(native.get("bm1"))

	def test_invalidate(self):
		py = PositionCache()
		native = NativePositionCache()

		py.set("bm1", 1, 2)
		native.set("bm1", 1, 2)

		py.invalidate("bm1")
		native.invalidate("bm1")

		self.assertEqual(py.get("bm1"), native.get("bm1"))
		self.assertIsNone(native.get("bm1"))

	def test_update_existing(self):
		py = PositionCache()
		native = NativePositionCache()

		py.set("bm1", 1, 2)
		native.set("bm1", 1, 2)

		py.set("bm1", 3, 4)
		native.set("bm1", 3, 4)

		self.assertEqual(py.get("bm1"), native.get("bm1"))
		self.assertEqual(native.get("bm1"), (3, 4))

	def test_expiration(self):
		"""Entries expire after timeout."""
		# Use a very short timeout for testing
		native = NativePositionCache(max_size=100, timeout_ms=50)

		native.set("bm1", 1, 2)
		self.assertEqual(native.get("bm1"), (1, 2))

		# Wait for expiration
		time.sleep(0.1)
		self.assertIsNone(native.get("bm1"))

	def test_multiple_keys(self):
		py = PositionCache()
		native = NativePositionCache()

		for i in range(50):
			key = f"bookmark_{i}"
			py.set(key, i, i * 10)
			native.set(key, i, i * 10)

		for i in range(50):
			key = f"bookmark_{i}"
			self.assertEqual(py.get(key), native.get(key))

	def test_negative_coordinates(self):
		"""Position coordinates can be negative in some edge cases."""
		native = NativePositionCache()
		native.set("bm1", -1, -5)
		self.assertEqual(native.get("bm1"), (-1, -5))


@unittest.skipUnless(_HAS_NATIVE, _skip_msg)
class TestNativeResourceCleanup(unittest.TestCase):
	"""Verify that native handles are properly cleaned up."""

	def test_text_differ_close(self):
		d = NativeTextDiffer()
		d.update("test")
		d.close()
		# After close, operations should not crash
		# (handle is None, methods should handle gracefully)

	def test_position_cache_close(self):
		c = NativePositionCache()
		c.set("key", 1, 2)
		c.close()

	def test_many_allocations(self):
		"""Create and destroy many objects to check for leaks."""
		for _ in range(100):
			d = NativeTextDiffer()
			d.update("some text here\n")
			d.update("some text here\nmore output\n")
			d.close()

		for _ in range(100):
			c = NativePositionCache()
			for j in range(20):
				c.set(f"key_{j}", j, j)
			c.close()

	def test_many_strip_ansi_calls(self):
		"""Verify no memory leaks in repeated strip_ansi calls."""
		text = "\x1b[31m" + "x" * 1000 + "\x1b[0m"
		for _ in range(1000):
			result = native_strip_ansi(text)
			self.assertEqual(len(result), 1000)


@unittest.skipUnless(_HAS_NATIVE, _skip_msg)
class TestUnicodeWidth(unittest.TestCase):
	"""Tests for native unicode width functions."""

	def test_native_char_width_ascii(self):
		"""ASCII characters should be width 1."""
		result = native_char_width('A')
		self.assertEqual(result, 1)

	def test_native_char_width_cjk(self):
		"""CJK characters should be width 2."""
		result = native_char_width('\u4e2d')
		self.assertEqual(result, 2)

	def test_native_char_width_empty(self):
		"""Empty string should return 0."""
		result = native_char_width('')
		self.assertEqual(result, 0)

	def test_native_text_width_ascii(self):
		"""Pure ASCII text width equals length."""
		result = native_text_width("Hello")
		self.assertEqual(result, 5)

	def test_native_text_width_cjk(self):
		"""Mixed ASCII and CJK text."""
		result = native_text_width("Hello\u4e16\u754c")
		self.assertEqual(result, 9)  # 5 + 2*2

	def test_native_text_width_empty(self):
		"""Empty text width is 0."""
		result = native_text_width("")
		self.assertEqual(result, 0)

	def test_native_extract_column_range_ascii(self):
		"""Extract from ASCII text."""
		result = native_extract_column_range("Hello World", 1, 5)
		self.assertEqual(result, "Hello")

	def test_native_extract_column_range_middle(self):
		"""Extract middle range from ASCII text."""
		result = native_extract_column_range("Hello World", 7, 11)
		self.assertEqual(result, "World")

	def test_native_extract_column_range_cjk(self):
		"""Extract range with CJK characters."""
		# A=col1, B=col2, \u4e2d=col3-4, \u6587=col5-6, C=col7, D=col8
		result = native_extract_column_range("AB\u4e2d\u6587CD", 3, 6)
		self.assertEqual(result, "\u4e2d\u6587")

	def test_native_extract_column_range_empty(self):
		"""Empty text returns empty."""
		result = native_extract_column_range("", 1, 5)
		self.assertEqual(result, "")

	def test_native_find_column_position(self):
		"""Find char index for column."""
		result = native_find_column_position("Hello", 3)
		self.assertEqual(result, 2)

	def test_native_find_column_position_cjk(self):
		"""Find char index in CJK text."""
		# A=col1, B=col2, \u4e2d=col3-4
		result = native_find_column_position("AB\u4e2d\u6587", 3)
		self.assertEqual(result, 2)

	def test_native_find_column_position_empty(self):
		"""Empty text returns 0."""
		result = native_find_column_position("", 3)
		self.assertEqual(result, 0)


if __name__ == "__main__":
	unittest.main()
