# Terminal Access for NVDA - Native Bridge
# Copyright (C) 2024 Pratik Patel
# This add-on is covered by the GNU General Public License, version 3.
# See the file LICENSE for more details.

"""
ctypes wrapper around the Rust ``termaccess.dll``.

Provides drop-in replacements for the CPU-bound Python classes:

* :class:`NativeTextDiffer` — replaces :class:`TextDiffer`
* :func:`native_strip_ansi` — replaces :meth:`ANSIParser.stripANSI`
* :func:`native_search_text` — replaces the search loop in
  :class:`OutputSearchManager`
* :class:`NativePositionCache` — replaces :class:`PositionCache`

All functions are designed to fail gracefully: if the DLL cannot be loaded,
:func:`native_available` returns ``False`` and callers should fall back to
the pure-Python implementations.
"""

from __future__ import annotations

import ctypes
import logging
import os
import struct
import threading
from ctypes import (
	POINTER,
	Structure,
	byref,
	c_int32,
	c_uint32,
	c_size_t,
	c_ubyte,
)
from typing import Any

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Error codes (must match ffi_types.rs)
# ═══════════════════════════════════════════════════════════════

ERR_OK = 0
ERR_NULL_POINTER = 1
ERR_INVALID_UTF8 = 2
ERR_NOT_FOUND = 3
ERR_INVALID_REGEX = 4

_ERROR_MESSAGES = {
	ERR_NULL_POINTER: "Internal error: null pointer passed to native function",
	ERR_INVALID_UTF8: "Invalid UTF-8 in input text",
	ERR_NOT_FOUND: "Key not found or expired",
	ERR_INVALID_REGEX: "Invalid regular expression",
}

# ═══════════════════════════════════════════════════════════════
#  DLL loading
# ═══════════════════════════════════════════════════════════════

_dll_lock = threading.Lock()
_dll: ctypes.CDLL | None = None
_dll_load_attempted = False


def _find_dll() -> str | None:
	"""Locate ``termaccess.dll`` for the running architecture."""
	arch = "x64" if struct.calcsize("P") == 8 else "x86"
	# Walk up from this file's directory to find addon/lib/<arch>/termaccess.dll
	here = os.path.dirname(os.path.abspath(__file__))
	# Expected: addon/native/termaccess_bridge.py → addon/lib/<arch>/termaccess.dll
	addon_dir = os.path.dirname(here)  # addon/
	dll_path = os.path.join(addon_dir, "lib", arch, "termaccess.dll")
	if os.path.isfile(dll_path):
		return dll_path
	log.debug("Native DLL not found at %s", dll_path)
	return None


def _get_dll() -> ctypes.CDLL | None:
	"""Lazy-load the native DLL.  Thread-safe, loads at most once."""
	global _dll, _dll_load_attempted
	if _dll is not None:
		return _dll
	if _dll_load_attempted:
		return None

	with _dll_lock:
		# Double-check after acquiring lock
		if _dll is not None:
			return _dll
		if _dll_load_attempted:
			return None

		_dll_load_attempted = True
		dll_path = _find_dll()
		if dll_path is None:
			return None

		try:
			lib = ctypes.CDLL(dll_path)
			_setup_signatures(lib)
			# Verify it loaded correctly by checking version
			ver_ptr = lib.ta_version()
			ver_len = lib.ta_version_len()
			ver = ctypes.string_at(ver_ptr, ver_len).decode("utf-8")
			log.info("Native DLL loaded: termaccess v%s from %s", ver, dll_path)
			_dll = lib
			return lib
		except (OSError, AttributeError, UnicodeDecodeError) as e:
			log.warning("Failed to load native DLL from %s: %s", dll_path, e)
			return None


def _setup_signatures(lib: ctypes.CDLL) -> None:
	"""Declare argument and return types for all exported functions."""

	# Version
	lib.ta_version.argtypes = []
	lib.ta_version.restype = POINTER(c_ubyte)

	lib.ta_version_len.argtypes = []
	lib.ta_version_len.restype = c_size_t

	# Memory management
	lib.ta_free_string.argtypes = [POINTER(c_ubyte), c_size_t]
	lib.ta_free_string.restype = None

	# TextDiffer
	lib.ta_text_differ_new.argtypes = []
	lib.ta_text_differ_new.restype = ctypes.c_void_p

	lib.ta_text_differ_free.argtypes = [ctypes.c_void_p]
	lib.ta_text_differ_free.restype = None

	lib.ta_text_differ_update.argtypes = [
		ctypes.c_void_p,   # handle
		POINTER(c_ubyte),  # text_ptr
		c_size_t,          # text_len
		POINTER(c_uint32), # out_kind
		POINTER(POINTER(c_ubyte)),  # out_content_ptr
		POINTER(c_size_t), # out_content_len
	]
	lib.ta_text_differ_update.restype = c_int32

	lib.ta_text_differ_reset.argtypes = [ctypes.c_void_p]
	lib.ta_text_differ_reset.restype = None

	lib.ta_text_differ_last_text.argtypes = [
		ctypes.c_void_p,            # handle
		POINTER(POINTER(c_ubyte)),  # out_ptr
		POINTER(c_size_t),          # out_len
	]
	lib.ta_text_differ_last_text.restype = c_int32

	# ANSI stripping
	lib.ta_strip_ansi.argtypes = [
		POINTER(c_ubyte),  # text_ptr
		c_size_t,          # text_len
		POINTER(POINTER(c_ubyte)),  # out_ptr
		POINTER(c_size_t),          # out_len
	]
	lib.ta_strip_ansi.restype = c_int32

	# Search
	lib.ta_search_text.argtypes = [
		POINTER(c_ubyte),  # text_ptr
		c_size_t,          # text_len
		POINTER(c_ubyte),  # pattern_ptr
		c_size_t,          # pattern_len
		c_uint32,          # case_sensitive
		c_uint32,          # use_regex
		ctypes.c_void_p,   # out_results (pointer to TaSearchResults)
	]
	lib.ta_search_text.restype = c_int32

	lib.ta_search_results_free.argtypes = [ctypes.c_void_p]
	lib.ta_search_results_free.restype = None

	# PositionCache
	lib.ta_position_cache_new.argtypes = [c_uint32, c_uint32]
	lib.ta_position_cache_new.restype = ctypes.c_void_p

	lib.ta_position_cache_free.argtypes = [ctypes.c_void_p]
	lib.ta_position_cache_free.restype = None

	lib.ta_position_cache_get.argtypes = [
		ctypes.c_void_p,   # handle
		POINTER(c_ubyte),  # key_ptr
		c_size_t,          # key_len
		POINTER(c_int32),  # out_row
		POINTER(c_int32),  # out_col
	]
	lib.ta_position_cache_get.restype = c_int32

	lib.ta_position_cache_set.argtypes = [
		ctypes.c_void_p,   # handle
		POINTER(c_ubyte),  # key_ptr
		c_size_t,          # key_len
		c_int32,           # row
		c_int32,           # col
	]
	lib.ta_position_cache_set.restype = None

	lib.ta_position_cache_clear.argtypes = [ctypes.c_void_p]
	lib.ta_position_cache_clear.restype = None

	lib.ta_position_cache_invalidate.argtypes = [
		ctypes.c_void_p,   # handle
		POINTER(c_ubyte),  # key_ptr
		c_size_t,          # key_len
	]
	lib.ta_position_cache_invalidate.restype = None

	# Unicode width
	lib.ta_char_width.argtypes = [c_uint32]
	lib.ta_char_width.restype = c_uint32

	lib.ta_text_width.argtypes = [POINTER(c_ubyte), c_size_t]
	lib.ta_text_width.restype = c_uint32

	lib.ta_extract_column_range.argtypes = [
		POINTER(c_ubyte),  # text_ptr
		c_size_t,          # text_len
		c_uint32,          # start_col
		c_uint32,          # end_col
		POINTER(POINTER(c_ubyte)),  # out_ptr
		POINTER(c_size_t),          # out_len
	]
	lib.ta_extract_column_range.restype = c_int32

	lib.ta_find_column_position.argtypes = [
		POINTER(c_ubyte),  # text_ptr
		c_size_t,          # text_len
		c_uint32,          # target_col
	]
	lib.ta_find_column_position.restype = c_uint32


def native_available() -> bool:
	"""Return True if the native DLL is loaded and ready."""
	return _get_dll() is not None


def get_native_version() -> str | None:
	"""Return the native DLL version string, or None if unavailable."""
	lib = _get_dll()
	if lib is None:
		return None
	ver_ptr = lib.ta_version()
	ver_len = lib.ta_version_len()
	return ctypes.string_at(ver_ptr, ver_len).decode("utf-8")


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _str_to_utf8(s: str) -> tuple[ctypes.Array | None, int]:
	"""Encode a Python str to a ctypes byte buffer.

	Returns (buffer, length).  If the string is empty, returns (None, 0).
	"""
	if not s:
		return None, 0
	encoded = s.encode("utf-8")
	buf = (c_ubyte * len(encoded))(*encoded)
	return buf, len(encoded)


def _read_ffi_string(lib: ctypes.CDLL, ptr: Any, length: int) -> str:
	"""Read a UTF-8 string from an FFI pointer and free it.

	Args:
		lib: The loaded DLL handle.
		ptr: Pointer to the string bytes (POINTER(c_ubyte)).
		length: Length in bytes.

	Returns:
		The decoded Python string.
	"""
	if not ptr or length == 0:
		return ""
	try:
		result = ctypes.string_at(ptr, length).decode("utf-8")
	finally:
		lib.ta_free_string(ptr, c_size_t(length))
	return result


def _check_rc(rc: int, fn_name: str) -> None:
	"""Raise RuntimeError if a native function returned an error."""
	if rc != ERR_OK:
		msg = _ERROR_MESSAGES.get(rc, f"Unknown error code {rc}")
		raise RuntimeError(f"{fn_name} failed: {msg}")


# ═══════════════════════════════════════════════════════════════
#  NativeTextDiffer
# ═══════════════════════════════════════════════════════════════

# DiffKind values from Rust (must match text_differ.rs enum)
_DIFF_KIND_MAP = {
	0: "initial",
	1: "unchanged",
	2: "appended",
	3: "changed",
	4: "last_line_updated",
}


class NativeTextDiffer:
	"""Drop-in replacement for :class:`TextDiffer` backed by Rust.

	Uses the same ``update()`` / ``reset()`` / ``last_text`` API so
	callers can swap implementations without changes.

	The underlying Rust TextDiffer is destroyed when this object is
	garbage-collected or when :meth:`close` is called.
	"""

	# Expose the same KIND_* constants for compatibility
	KIND_INITIAL = "initial"
	KIND_UNCHANGED = "unchanged"
	KIND_APPENDED = "appended"
	KIND_CHANGED = "changed"
	KIND_LAST_LINE_UPDATED = "last_line_updated"

	__slots__ = ("_handle", "_lib")

	def __init__(self) -> None:
		lib = _get_dll()
		if lib is None:
			raise RuntimeError("Native DLL not available")
		self._lib = lib
		self._handle = lib.ta_text_differ_new()
		if not self._handle:
			raise RuntimeError("ta_text_differ_new returned null")

	def update(self, current_text: str) -> tuple[str, str]:
		"""Compare *current_text* against the stored snapshot.

		Returns:
			tuple: ``(kind, new_content)`` where *kind* is one of the
			``KIND_*`` string constants.
		"""
		text_buf, text_len = _str_to_utf8(current_text)

		out_kind = c_uint32(0)
		out_ptr = POINTER(c_ubyte)()
		out_len = c_size_t(0)

		rc = self._lib.ta_text_differ_update(
			self._handle,
			text_buf,
			c_size_t(text_len),
			byref(out_kind),
			byref(out_ptr),
			byref(out_len),
		)
		_check_rc(rc, "ta_text_differ_update")

		kind_str = _DIFF_KIND_MAP.get(out_kind.value, "changed")
		content = _read_ffi_string(self._lib, out_ptr, out_len.value)
		return (kind_str, content)

	def reset(self) -> None:
		"""Discard the stored snapshot."""
		if self._handle:
			self._lib.ta_text_differ_reset(self._handle)

	@property
	def last_text(self) -> str | None:
		"""The last snapshot text, or ``None`` if no snapshot."""
		if not self._handle:
			return None

		out_ptr = POINTER(c_ubyte)()
		out_len = c_size_t(0)

		rc = self._lib.ta_text_differ_last_text(
			self._handle,
			byref(out_ptr),
			byref(out_len),
		)
		_check_rc(rc, "ta_text_differ_last_text")

		if not out_ptr or out_len.value == 0:
			return None
		return _read_ffi_string(self._lib, out_ptr, out_len.value)

	def close(self) -> None:
		"""Explicitly release the native handle."""
		if self._handle:
			self._lib.ta_text_differ_free(self._handle)
			self._handle = None

	def __del__(self) -> None:
		self.close()


# ═══════════════════════════════════════════════════════════════
#  ANSI stripping
# ═══════════════════════════════════════════════════════════════

def native_strip_ansi(text: str) -> str:
	"""Strip all ANSI escape sequences from *text*.

	Drop-in replacement for ``ANSIParser.stripANSI(text)``.
	"""
	lib = _get_dll()
	if lib is None:
		raise RuntimeError("Native DLL not available")

	text_buf, text_len = _str_to_utf8(text)

	out_ptr = POINTER(c_ubyte)()
	out_len = c_size_t(0)

	rc = lib.ta_strip_ansi(
		text_buf,
		c_size_t(text_len),
		byref(out_ptr),
		byref(out_len),
	)
	_check_rc(rc, "ta_strip_ansi")

	return _read_ffi_string(lib, out_ptr, out_len.value)


# ═══════════════════════════════════════════════════════════════
#  Search
# ═══════════════════════════════════════════════════════════════

class _TaSearchMatch(Structure):
	"""Mirrors the C ``TaSearchMatch`` struct."""
	_fields_ = [
		("line_index", c_uint32),
		("char_offset", c_uint32),
		("line_text_ptr", POINTER(c_ubyte)),
		("line_text_len", c_size_t),
	]


class _TaSearchResults(Structure):
	"""Mirrors the C ``TaSearchResults`` struct."""
	_fields_ = [
		("matches", POINTER(_TaSearchMatch)),
		("match_count", c_size_t),
	]


def native_search_text(
	text: str,
	pattern: str,
	case_sensitive: bool = True,
	use_regex: bool = False,
) -> list[tuple[int, int, str]]:
	"""Search *text* for *pattern* with optional regex and case flags.

	Returns a list of ``(line_index, char_offset, line_text)`` tuples
	for each matching line.  ANSI codes are stripped before matching.

	Raises ``ValueError`` if *use_regex* is True and *pattern* is invalid.
	"""
	lib = _get_dll()
	if lib is None:
		raise RuntimeError("Native DLL not available")

	text_buf, text_len = _str_to_utf8(text)
	pat_buf, pat_len = _str_to_utf8(pattern)

	results = _TaSearchResults()

	rc = lib.ta_search_text(
		text_buf,
		c_size_t(text_len),
		pat_buf,
		c_size_t(pat_len),
		c_uint32(1 if case_sensitive else 0),
		c_uint32(1 if use_regex else 0),
		ctypes.byref(results),
	)

	if rc == ERR_INVALID_REGEX:
		raise ValueError(f"Invalid regex pattern: {pattern}")
	_check_rc(rc, "ta_search_text")

	# Copy results into Python before freeing
	matches: list[tuple[int, int, str]] = []
	try:
		for i in range(results.match_count):
			m = results.matches[i]
			line_text = ""
			if m.line_text_ptr and m.line_text_len > 0:
				line_text = ctypes.string_at(
					m.line_text_ptr, m.line_text_len
				).decode("utf-8")
			matches.append((m.line_index, m.char_offset, line_text))
	finally:
		lib.ta_search_results_free(ctypes.byref(results))

	return matches


# ═══════════════════════════════════════════════════════════════
#  NativePositionCache
# ═══════════════════════════════════════════════════════════════

class NativePositionCache:
	"""Drop-in replacement for :class:`PositionCache` backed by Rust.

	Uses the same ``get()`` / ``set()`` / ``clear()`` / ``invalidate()``
	API.  The Rust implementation uses an LRU cache with timestamp-based
	expiration, matching the Python semantics.
	"""

	# Default values matching the Python PositionCache
	MAX_CACHE_SIZE = 100
	CACHE_TIMEOUT_MS = 1000  # 1 second, matches CACHE_TIMEOUT_S = 1.0

	__slots__ = ("_handle", "_lib")

	def __init__(
		self,
		max_size: int | None = None,
		timeout_ms: int | None = None,
	) -> None:
		lib = _get_dll()
		if lib is None:
			raise RuntimeError("Native DLL not available")
		self._lib = lib

		size = max_size if max_size is not None else self.MAX_CACHE_SIZE
		timeout = timeout_ms if timeout_ms is not None else self.CACHE_TIMEOUT_MS

		self._handle = lib.ta_position_cache_new(
			c_uint32(size), c_uint32(timeout)
		)
		if not self._handle:
			raise RuntimeError("ta_position_cache_new returned null")

	def get(self, bookmark: Any) -> tuple[int, int] | None:
		"""Retrieve cached ``(row, col)`` for *bookmark*, or ``None``."""
		if not self._handle:
			return None

		key = str(bookmark)
		key_buf, key_len = _str_to_utf8(key)

		out_row = c_int32(0)
		out_col = c_int32(0)

		rc = self._lib.ta_position_cache_get(
			self._handle,
			key_buf,
			c_size_t(key_len),
			byref(out_row),
			byref(out_col),
		)

		if rc == ERR_NOT_FOUND:
			return None
		_check_rc(rc, "ta_position_cache_get")

		return (out_row.value, out_col.value)

	def set(self, bookmark: Any, row: int, col: int) -> None:
		"""Store ``(row, col)`` for *bookmark*."""
		if not self._handle:
			return

		key = str(bookmark)
		key_buf, key_len = _str_to_utf8(key)

		self._lib.ta_position_cache_set(
			self._handle,
			key_buf,
			c_size_t(key_len),
			c_int32(row),
			c_int32(col),
		)

	def clear(self) -> None:
		"""Clear all cached positions."""
		if self._handle:
			self._lib.ta_position_cache_clear(self._handle)

	def invalidate(self, bookmark: Any) -> None:
		"""Remove a specific *bookmark* from the cache."""
		if not self._handle:
			return

		key = str(bookmark)
		key_buf, key_len = _str_to_utf8(key)

		self._lib.ta_position_cache_invalidate(
			self._handle,
			key_buf,
			c_size_t(key_len),
		)

	def close(self) -> None:
		"""Explicitly release the native handle."""
		if self._handle:
			self._lib.ta_position_cache_free(self._handle)
			self._handle = None

	def __del__(self) -> None:
		self.close()


# ═══════════════════════════════════════════════════════════════
#  Unicode Width
# ═══════════════════════════════════════════════════════════════

def native_char_width(char: str) -> int:
	"""Get display width of a single Unicode character (0, 1, or 2).

	Drop-in replacement for ``UnicodeWidthHelper.getCharWidth(char)``.
	"""
	lib = _get_dll()
	if lib is None:
		raise RuntimeError("Native DLL not available")

	if not char:
		return 0
	codepoint = ord(char[0])
	return lib.ta_char_width(c_uint32(codepoint))


def native_text_width(text: str) -> int:
	"""Calculate total display width of a text string.

	Drop-in replacement for ``UnicodeWidthHelper.getTextWidth(text)``.
	"""
	lib = _get_dll()
	if lib is None:
		raise RuntimeError("Native DLL not available")

	text_buf, text_len = _str_to_utf8(text)
	result = lib.ta_text_width(text_buf, c_size_t(text_len))
	if result == 0xFFFFFFFF:  # u32::MAX = error
		raise RuntimeError("ta_text_width failed")
	return result


def native_extract_column_range(text: str, start_col: int, end_col: int) -> str:
	"""Extract text from column range (1-based, inclusive), respecting Unicode widths.

	Drop-in replacement for ``UnicodeWidthHelper.extractColumnRange(text, startCol, endCol)``.
	"""
	lib = _get_dll()
	if lib is None:
		raise RuntimeError("Native DLL not available")

	if not text:
		return ""

	text_buf, text_len = _str_to_utf8(text)

	out_ptr = POINTER(c_ubyte)()
	out_len = c_size_t(0)

	rc = lib.ta_extract_column_range(
		text_buf,
		c_size_t(text_len),
		c_uint32(start_col),
		c_uint32(end_col),
		byref(out_ptr),
		byref(out_len),
	)
	_check_rc(rc, "ta_extract_column_range")

	return _read_ffi_string(lib, out_ptr, out_len.value)


def native_find_column_position(text: str, target_col: int) -> int:
	"""Find the char index for a target column position (1-based).

	Drop-in replacement for ``UnicodeWidthHelper.findColumnPosition(text, targetCol)``.
	"""
	lib = _get_dll()
	if lib is None:
		raise RuntimeError("Native DLL not available")

	if not text:
		return 0

	text_buf, text_len = _str_to_utf8(text)
	result = lib.ta_find_column_position(text_buf, c_size_t(text_len), c_uint32(target_col))
	if result == 0xFFFFFFFF:  # u32::MAX = error
		raise RuntimeError("ta_find_column_position failed")
	return result


# ═══════════════════════════════════════════════════════════════
#  Helper process integration (Phase 2)
# ═══════════════════════════════════════════════════════════════

_helper_instance = None
_helper_lock = threading.Lock()


def helper_available() -> bool:
	"""Return True if the helper process is running and ready."""
	h = _helper_instance
	return h is not None and h.is_running


def get_helper():
	"""Get or create the singleton HelperProcess instance.

	Uses double-check locking for thread safety.  The helper is
	started lazily on first call.  Returns the running instance,
	or None if unavailable.

	If the helper exists but is not running (crashed and auto-restarting),
	returns None so callers fall back gracefully.  The existing instance
	handles its own restart via ``_maybe_restart()``.
	"""
	global _helper_instance
	if _helper_instance is not None:
		return _helper_instance if _helper_instance.is_running else None
	with _helper_lock:
		if _helper_instance is not None:
			return _helper_instance if _helper_instance.is_running else None
		try:
			from native.helper_process import HelperProcess
			helper = HelperProcess()
			if helper.start():
				_helper_instance = helper
				return _helper_instance
			return None
		except Exception:
			log.debug("Failed to start helper process", exc_info=True)
			return None


def start_helper_eagerly():
	"""Start the helper process in the background so it's ready when needed.

	Called from ``GlobalPlugin.__init__()`` on a daemon thread so it
	doesn't block addon startup.  If the helper fails to start, this is
	not fatal — it will be retried on first use via :func:`get_helper`.
	"""
	try:
		get_helper()
	except Exception:
		pass  # not fatal — will retry on first use


def stop_helper():
	"""Stop the helper process if running."""
	global _helper_instance
	with _helper_lock:
		if _helper_instance is not None:
			try:
				_helper_instance.stop()
			except Exception:
				pass
			_helper_instance = None
