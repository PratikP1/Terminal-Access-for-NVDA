"""Tests verifying Rust-native and Python-fallback search paths produce identical results."""

import re
from unittest.mock import patch

import api
import textInfos

textInfos.POSITION_ALL = "all"
textInfos.POSITION_FIRST = "first"
textInfos.UNIT_LINE = "line"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummyTextInfo:
	"""Minimal TextInfo with bookmark support for parity tests."""

	def __init__(self, source_text, line_index=0):
		self._source_text = source_text
		self.line_index = line_index
		self.text = source_text

	@property
	def bookmark(self):
		return None

	def move(self, unit, count):
		self.line_index += count
		return True

	def copy(self):
		return DummyTextInfo(self._source_text, self.line_index)


class DummyTerminal:
	"""Terminal stub for search parity tests."""

	def __init__(self, text):
		self.text = text

	def makeTextInfo(self, arg):
		if arg == textInfos.POSITION_ALL:
			return DummyTextInfo(self.text, 0)
		if arg == textInfos.POSITION_FIRST:
			return DummyTextInfo(self.text, 0)
		raise ValueError("Bookmarks not supported")


def _simulate_native_search(stripped_text, pattern, case_sensitive, use_regex):
	"""Pure-Python emulation of what the Rust native_search_text returns.

	Returns list of (line_index, char_offset, line_text) tuples, matching
	the Rust FFI contract.
	"""
	lines = stripped_text.split('\n')
	results = []
	if use_regex:
		flags = 0 if case_sensitive else re.IGNORECASE
		compiled = re.compile(pattern, flags)
		for i, line in enumerate(lines):
			m = compiled.search(line)
			if m:
				results.append((i, m.start(), line))
	else:
		search_pat = pattern if case_sensitive else pattern.lower()
		for i, line in enumerate(lines):
			target = line if case_sensitive else line.lower()
			offset = target.find(search_pat)
			if offset >= 0:
				results.append((i, offset, line))
	return results


def _collect_match_data(manager):
	"""Extract the stored match data from an OutputSearchManager after search."""
	state = manager._get_search_state()
	matches = state['matches']
	result = []
	for match in matches:
		bookmark, line_text, line_num, pos_info, char_offset = manager._unpack_match(match)
		result.append({
			'line_num': line_num,
			'line_text': line_text,
			'char_offset': char_offset,
		})
	return result


def _run_search(text, pattern, case_sensitive=False, use_regex=False,
                native_available=False):
	"""Run a search and return (count, match_data)."""
	from globalPlugins.terminalAccess import OutputSearchManager

	import lib._runtime as _rt

	terminal = DummyTerminal(text)
	manager = OutputSearchManager(terminal)

	orig_native = _rt.native_available
	orig_search = _rt.native_search_text
	try:
		if native_available:
			_rt.native_available = True
			_rt.native_search_text = _simulate_native_search
		else:
			_rt.native_available = False
			_rt.native_search_text = None

		count = manager.search(pattern, case_sensitive=case_sensitive,
		                       use_regex=use_regex)
	finally:
		_rt.native_available = orig_native
		_rt.native_search_text = orig_search

	return count, _collect_match_data(manager)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSearchPathParity:
	"""Native and fallback search paths must produce identical results."""

	def test_literal_case_insensitive_same_results(self):
		"""Native and fallback find the same lines for case-insensitive literal."""
		text = "Hello World\nfoo bar\nhello again\nnothing here"

		count_fb, data_fb = _run_search(text, "hello", case_sensitive=False,
		                                native_available=False)
		count_na, data_na = _run_search(text, "hello", case_sensitive=False,
		                                native_available=True)

		assert count_fb == count_na
		assert len(data_fb) == len(data_na)
		for fb, na in zip(data_fb, data_na):
			assert fb['line_num'] == na['line_num']
			assert fb['char_offset'] == na['char_offset']
			assert fb['line_text'] == na['line_text']

	def test_literal_case_sensitive_same_results(self):
		"""Native and fallback find the same lines for case-sensitive literal."""
		text = "Hello World\nhello world\nHELLO WORLD"

		count_fb, data_fb = _run_search(text, "Hello", case_sensitive=True,
		                                native_available=False)
		count_na, data_na = _run_search(text, "Hello", case_sensitive=True,
		                                native_available=True)

		assert count_fb == count_na
		for fb, na in zip(data_fb, data_na):
			assert fb['line_num'] == na['line_num']
			assert fb['char_offset'] == na['char_offset']
			assert fb['line_text'] == na['line_text']

	def test_regex_same_results(self):
		"""Native and fallback find the same lines for regex search."""
		text = "error: file not found\nwarning: deprecated\nerror: timeout"

		count_fb, data_fb = _run_search(text, r"error:\s+\w+", use_regex=True,
		                                native_available=False)
		count_na, data_na = _run_search(text, r"error:\s+\w+", use_regex=True,
		                                native_available=True)

		assert count_fb == count_na
		for fb, na in zip(data_fb, data_na):
			assert fb['line_num'] == na['line_num']
			assert fb['char_offset'] == na['char_offset']
			assert fb['line_text'] == na['line_text']

	def test_ansi_text_same_results(self):
		"""Both paths handle ANSI codes identically."""
		text = "normal\n\x1b[31merror\x1b[0m occurred\n\x1b[32mok\x1b[0m done"

		count_fb, data_fb = _run_search(text, "error", native_available=False)
		count_na, data_na = _run_search(text, "error", native_available=True)

		assert count_fb == count_na
		for fb, na in zip(data_fb, data_na):
			assert fb['line_num'] == na['line_num']
			assert fb['char_offset'] == na['char_offset']
			assert fb['line_text'] == na['line_text']
			assert '\x1b' not in fb['line_text']

	def test_unicode_same_results(self):
		"""Both paths handle Unicode/CJK the same."""
		text = "ascii line\n\u4f60\u597d\u4e16\u754c\nmore text\n\u3053\u3093\u306b\u3061\u306f"

		count_fb, data_fb = _run_search(text, "\u4f60\u597d",
		                                native_available=False)
		count_na, data_na = _run_search(text, "\u4f60\u597d",
		                                native_available=True)

		assert count_fb == count_na
		for fb, na in zip(data_fb, data_na):
			assert fb['line_num'] == na['line_num']
			assert fb['char_offset'] == na['char_offset']
			assert fb['line_text'] == na['line_text']

	def test_no_matches_same_results(self):
		"""Both paths return zero matches for non-existent pattern."""
		text = "alpha\nbeta\ngamma"

		count_fb, data_fb = _run_search(text, "zzzzz", native_available=False)
		count_na, data_na = _run_search(text, "zzzzz", native_available=True)

		assert count_fb == 0
		assert count_na == 0
		assert data_fb == data_na == []

	def test_multiple_matches_on_different_lines(self):
		"""Both paths find matches spread across many lines."""
		lines = [f"line {i} target" if i % 3 == 0 else f"line {i} filler"
		         for i in range(20)]
		text = "\n".join(lines)

		count_fb, data_fb = _run_search(text, "target", native_available=False)
		count_na, data_na = _run_search(text, "target", native_available=True)

		assert count_fb == count_na == 7  # lines 0,3,6,9,12,15,18
		for fb, na in zip(data_fb, data_na):
			assert fb['line_num'] == na['line_num']
			assert fb['char_offset'] == na['char_offset']
			assert fb['line_text'] == na['line_text']


class TestSearchPerformance:
	"""Search must not walk every line in the buffer."""

	def test_search_does_not_walk_entire_buffer(self):
		"""Search with 5000 lines should not call move() 5000 times.

		The bookmark walk was iterating every line in the terminal buffer
		to collect TextInfo bookmarks. On large buffers this froze NVDA
		because each move() is a UIA round-trip on the main thread.

		Search should store line indices and resolve TextInfo on jump,
		not upfront.
		"""
		from globalPlugins.terminalAccess import OutputSearchManager
		import lib._runtime as _rt

		# Build a 5000-line buffer with "error" on lines 100 and 4900
		lines = [f"output line {i}" for i in range(5000)]
		lines[100] = "error: something failed"
		lines[4900] = "error: another failure"
		text = "\n".join(lines)

		move_count = 0
		original_move = DummyTextInfo.move

		def counting_move(self_ti, unit, count):
			nonlocal move_count
			move_count += 1
			return original_move(self_ti, unit, count)

		terminal = DummyTerminal(text)
		manager = OutputSearchManager(terminal)

		orig_native = _rt.native_available
		_rt.native_available = False
		try:
			DummyTextInfo.move = counting_move
			count = manager.search("error", case_sensitive=False)
			DummyTextInfo.move = original_move
		finally:
			_rt.native_available = orig_native

		assert count == 2, f"Expected 2 matches, got {count}"
		# The critical assertion: move() should NOT be called for every
		# line in the buffer. With lazy resolution, move() should only
		# be called when jumping to a match, not during search().
		assert move_count < 100, (
			f"search() called move() {move_count} times on a 5000-line buffer. "
			f"This causes NVDA to freeze. Search should not walk the full buffer."
		)

	def test_search_results_have_line_info(self):
		"""Search results must include line number and text even without bookmarks."""
		from globalPlugins.terminalAccess import OutputSearchManager
		import lib._runtime as _rt

		text = "line one\nerror here\nline three"
		terminal = DummyTerminal(text)
		manager = OutputSearchManager(terminal)

		orig_native = _rt.native_available
		_rt.native_available = False
		try:
			count = manager.search("error", case_sensitive=False)
		finally:
			_rt.native_available = orig_native

		assert count == 1
		data = _collect_match_data(manager)
		assert data[0]['line_num'] == 2
		assert data[0]['line_text'] == "error here"
