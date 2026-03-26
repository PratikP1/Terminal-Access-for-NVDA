# Terminal Access caching and diffing utilities.
# Extracted from terminalAccess.py for modularization.

import re
import time
import threading
from collections import OrderedDict
from typing import Any

_TRAILING_SPACES_RE: re.Pattern[str] = re.compile(r' +$', re.MULTILINE)

class PositionCache:
	"""
	Cache for terminal position calculations with timestamp-based invalidation.

	Stores bookmark→(row, col, timestamp) mappings to avoid repeated O(n) calculations.
	Cache entries expire after CACHE_TIMEOUT_MS milliseconds.

	Example usage:
		>>> cache = PositionCache()
		>>> bookmark = textInfo.bookmark
		>>>
		>>> # First calculation (cache miss)
		>>> cached_pos = cache.get(bookmark)  # Returns None
		>>> row, col = expensive_calculation(bookmark)
		>>> cache.set(bookmark, row, col)
		>>>
		>>> # Second calculation (cache hit)
		>>> cached_pos = cache.get(bookmark)  # Returns (row, col)
		>>> if cached_pos:
		>>>     row, col = cached_pos  # No expensive recalculation needed
		>>>
		>>> # After CACHE_TIMEOUT_MS milliseconds
		>>> cached_pos = cache.get(bookmark)  # Returns None (expired)

	Thread Safety:
		All operations are thread-safe using internal locking.

	Performance:
		- get(): O(1) average case
		- set(): O(1) average case
		- Space complexity: O(min(n, MAX_CACHE_SIZE)) where n = unique bookmarks
	"""

	CACHE_TIMEOUT_S: float = 1.0  # Seconds (avoids per-call ms conversion)
	MAX_CACHE_SIZE = 100  # Maximum number of cached positions

	def __init__(self) -> None:
		"""Initialize an empty position cache."""
		self._cache: OrderedDict[str, tuple[int, int, float]] = OrderedDict()
		self._lock: threading.Lock = threading.Lock()

	def get(self, bookmark: Any) -> tuple[int, int] | None:
		"""
		Retrieve cached position for a bookmark if valid.

		Uses LRU eviction: a cache hit moves the entry to the end so
		frequently accessed positions stay in the cache longer.

		Args:
			bookmark: TextInfo bookmark object

		Returns:
			tuple: (row, col) if cache hit and not expired, None otherwise
		"""
		with self._lock:
			key = str(bookmark)
			entry = self._cache.get(key)
			if entry is not None:
				row, col, timestamp = entry
				if (time.time() - timestamp) < self.CACHE_TIMEOUT_S:
					# LRU: move to end so this entry is evicted last
					self._cache.move_to_end(key)
					return (row, col)
				# Expired entry, remove it
				del self._cache[key]
		return None

	def set(self, bookmark: Any, row: int, col: int) -> None:
		"""
		Store position in cache with current timestamp.

		Uses LRU eviction: when the cache is full, the least-recently
		used entry is evicted instead of the oldest by insertion time.

		Args:
			bookmark: TextInfo bookmark object
			row: Row number
			col: Column number
		"""
		with self._lock:
			key = str(bookmark)
			# If already present, update and move to end (LRU refresh)
			if key in self._cache:
				self._cache.move_to_end(key)
			elif len(self._cache) >= self.MAX_CACHE_SIZE:
				# Evict the least-recently used entry (front of OrderedDict)
				self._cache.popitem(last=False)

			self._cache[key] = (row, col, time.time())

	def clear(self) -> None:
		"""Clear all cached positions."""
		with self._lock:
			self._cache.clear()

	def invalidate(self, bookmark: Any) -> None:
		"""
		Invalidate a specific cached position.

		Args:
			bookmark: TextInfo bookmark to invalidate
		"""
		with self._lock:
			key = str(bookmark)
			if key in self._cache:
				del self._cache[key]


class TextDiffer:
	"""
	Lightweight text differ for detecting new terminal output.

	Stores a snapshot of the last-known terminal text and compares it
	against the current text to identify newly appended content.

	The common case—output being appended to the end—is handled in O(n)
	time, where n is the length of the new suffix.  For edits in the
	middle or full screen clears the differ reports a ``"changed"`` state
	without computing a detailed diff.

	This class is opt-in; callers must call :meth:`update` explicitly.
	No UIA/COM calls are made here.

	Example usage:
		>>> differ = TextDiffer()
		>>> differ.update("line1\\nline2\\n")
		('initial', '')
		>>> differ.update("line1\\nline2\\nline3\\n")
		('appended', 'line3\\n')
		>>> differ.update("completely different")
		('changed', '')

	Thread Safety:
		Not internally thread-safe; callers must synchronise if needed.
	"""

	# Possible diff result kinds
	KIND_INITIAL = "initial"    # First snapshot — no previous state
	KIND_UNCHANGED = "unchanged"  # Text identical to last snapshot
	KIND_APPENDED = "appended"  # New text was appended after old text
	KIND_CHANGED = "changed"    # Non-trivial change (edit, clear, etc.)
	KIND_LAST_LINE_UPDATED = "last_line_updated"  # Only the last line changed (progress bars, spinners)

	__slots__ = ('_last_text', '_last_len')

	def __init__(self) -> None:
		"""Initialise with no previous snapshot."""
		self._last_text: str | None = None
		self._last_len: int = 0

	@staticmethod
	def _normalize(text: str) -> str:
		"""Strip trailing spaces from each line for padding-agnostic comparison.

		conhost pads UNIT_LINE text to screen width (80/120 chars) with trailing
		spaces. When padding shifts between reads, the prefix comparison fails.
		Normalizing before comparison prevents false KIND_CHANGED results.
		"""
		return _TRAILING_SPACES_RE.sub('', text)

	def update(self, current_text: str) -> tuple[str, str]:
		"""
		Compare *current_text* to the stored snapshot and return a diff result.

		Uses length pre-checks to avoid expensive full-string comparisons
		on the common unchanged and append cases.

		Args:
			current_text: The full current terminal text.

		Returns:
			tuple: ``(kind, new_content)`` where *kind* is one of the
			``KIND_*`` constants and *new_content* is the appended portion
			(non-empty for :attr:`KIND_APPENDED` and :attr:`KIND_LAST_LINE_UPDATED`).
		"""
		current_text = self._normalize(current_text)
		old = self._last_text
		if old is None:
			self._last_text = current_text
			self._last_len = len(current_text)
			return (self.KIND_INITIAL, "")

		cur_len = len(current_text)

		# Fast identity check: same length → likely unchanged.
		if cur_len == self._last_len and current_text == old:
			return (self.KIND_UNCHANGED, "")

		# Fast append detection: new text is longer and starts with old text.
		old_len = self._last_len
		if cur_len > old_len and current_text[:old_len] == old:
			appended = current_text[old_len:]
			self._last_text = current_text
			self._last_len = cur_len
			return (self.KIND_APPENDED, appended)

		# Last-line overwrite detection: everything before the last newline is
		# identical, only the trailing content differs (progress bars, spinners).
		# Skip the expensive rpartition if the lengths differ dramatically.
		if abs(cur_len - old_len) <= 500:
			old_prefix, old_sep, _old_tail = old.rpartition('\n')
			new_prefix, new_sep, new_tail = current_text.rpartition('\n')
			if old_sep and new_sep and old_prefix == new_prefix:
				self._last_text = current_text
				self._last_len = cur_len
				return (self.KIND_LAST_LINE_UPDATED, new_tail)

		# Non-trivial change.
		self._last_text = current_text
		self._last_len = cur_len
		return (self.KIND_CHANGED, "")

	def reset(self) -> None:
		"""Discard the stored snapshot so the next :meth:`update` is treated as initial."""
		self._last_text = None
		self._last_len = 0

	@property
	def last_text(self) -> str | None:
		"""The last snapshot text, or ``None`` if no snapshot has been taken."""
		return self._last_text

