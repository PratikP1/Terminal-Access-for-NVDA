# Terminal Access search and command history classes.
# Extracted from terminalAccess.py for modularization.

import collections
import re

import api
import textInfos
import ui
import wx

import lib  # noqa: F401 — ensures translation fallback is initialized
import lib._runtime as _rt

_PROMPT_PATTERNS: list[re.Pattern[str]] = [
	# Bash prompts: user@host:~$, root@host:#, simple $/#
	re.compile(r'^[\w\-\.]+@[\w\-\.]+:[^\$#]*[\$#]\s*(.+)$'),
	re.compile(r'^[\$#]\s*(.+)$'),
	# PowerShell prompts: PS>, PS C:\>, PS /home/user>
	re.compile(r'^PS\s+[A-Za-z]:[^>]*>\s*(.+)$'),
	re.compile(r'^PS\s+/[^>]*>\s*(.+)$'),
	re.compile(r'^PS>\s*(.+)$'),
	# Windows CMD prompts: C:\>, D:\Users\name>
	re.compile(r'^[A-Za-z]:[^>]*>\s*(.+)$'),
	# Generic prompt with colon or arrow
	re.compile(r'^[^\s>:]+[>:]\s*(.+)$'),
]

# Compiled URL extraction patterns for UrlExtractorManager.
# OSC 8 hyperlinks embedded by modern terminals: ESC]8;;URL BEL display_text ESC]8;; BEL
_OSC8_URL_PATTERN: re.Pattern[str] = re.compile(
	r'\x1b\]8;'           # OSC 8 start
	r'[^;]*;'             # optional params (id=xxx, etc.)
	r'([^\x07\x1b]+)'     # capture the URL
	r'(?:\x07|\x1b\\)'    # BEL or ST terminator
)

# Plain-text URL pattern applied after ANSI stripping.
_URL_PATTERN: re.Pattern[str] = re.compile(
	r'(?:'
	# Standard http/https/ftp URLs
	r'(?:https?|ftp)://[^\s<>\[\]()\"\'`{}|\\^]+'
	r'|'
	# www. prefixed URLs (common in terminal output)
	r'www\.[^\s<>\[\]()\"\'`{}|\\^]+'
	r'|'
	# file:// protocol
	r'file://[^\s<>\[\]()\"\'`{}|\\^]+'
	r')',
	re.IGNORECASE
)


def _clean_url(url: str) -> str:
	"""Strip trailing punctuation that is likely not part of the URL."""
	_TRAILING_PUNCT = '.,;:!?'

	# Strip trailing punctuation
	while url and url[-1] in _TRAILING_PUNCT:
		url = url[:-1]
	# Strip unbalanced trailing bracket/paren characters
	pairs = {'(': ')', '[': ']', '<': '>'}
	for open_char, close_char in pairs.items():
		while url.endswith(close_char) and url.count(close_char) > url.count(open_char):
			url = url[:-1]
	# Bracket stripping may expose trailing punctuation
	while url and url[-1] in _TRAILING_PUNCT:
		url = url[:-1]
	return url


class OutputSearchManager:
	"""
	Search and filter terminal output with pattern matching.

	Section 8.2: Output Filtering and Search (v1.0.30+)

	This class enables users to search through terminal output using text patterns
	or regular expressions, navigate between matches, and filter output. Useful for:
	- Finding error messages in logs
	- Locating specific command output
	- Filtering build output for warnings
	- Searching through help text
	- Finding specific entries in terminal history

	Features:
	- Text search with case sensitivity option
	- Regular expression support
	- Navigate forward/backward through matches
	- Show match count
	- Jump to first/last match
	- Wrap-around search

	Example usage:
		>>> manager = OutputSearchManager(terminal_obj)
		>>> manager.search("error", case_sensitive=False)
		>>> manager.next_match()  # Jump to next occurrence
		>>> manager.previous_match()  # Jump to previous occurrence
		>>> manager.get_match_count()  # Get total matches
	"""

	def __init__(self, terminal_obj, tab_manager=None):
		"""
		Initialize the OutputSearchManager.

		Args:
			terminal_obj: Terminal TextInfo object for searching
			tab_manager: Optional TabManager for tab-aware search storage
		"""
		self._terminal = terminal_obj
		# tab_manager is accepted for API compatibility but no longer keys
		# the search state. See _get_search_state.
		self._tab_manager = tab_manager
		# Cached ANSI-stripped, length-capped buffer lines. Reused across
		# searches until the plugin signals new output via
		# note_content_changed(), so a search / refine / search-again loop
		# does not re-read and re-strip the whole buffer each time.
		self._cached_lines = None
		self._cached_lines_gen = -1
		self._cached_lines_offsets_valid = False
		self._content_generation = 0
		# Search history (most recent first, max 10 entries)
		self._search_history: list[str] = []
		# Message from the last search (e.g. fuzzy fallback notification)
		self._last_search_message: str = ""
		# Active search per terminal window, keyed on the stable window
		# handle (windowHandle). Keying on the window handle instead of the
		# old tab id (a hash of the volatile window title and focused object
		# id) means the search survives refocus and is restored when you
		# switch to another window and back. Terminals without a handle fall
		# back to the None key, a single shared slot.
		self._window_searches = {}  # hwnd -> state dict

	@staticmethod
	def _blank_search_state():
		return {
			'pattern': None,
			'matches': [],
			'current_match_index': -1,
			'case_sensitive': False,
			'use_regex': False,
			'scope': 'buffer',
			'current_line': 0,
			# Content generation the results were computed against, so a
			# later navigate can tell whether new output made them stale.
			'generation': None,
		}

	def _search_key(self):
		return getattr(self._terminal, "windowHandle", None) or None

	def _get_search_state(self):
		"""Return the active search state for the current terminal window."""
		key = self._search_key()
		if key not in self._window_searches:
			self._window_searches[key] = self._blank_search_state()
		return self._window_searches[key]

	def _save_search_state(self, state):
		"""Persist the active search state for the current terminal window."""
		self._window_searches[self._search_key()] = state

	# Safety limits for search input validation
	MAX_PATTERN_LENGTH = 500
	MAX_MATCHES = 1000
	MAX_LINE_LENGTH = 10000
	# Only the most recent MAX_SEARCH_LINES are scanned, so a huge scrollback
	# cannot make a single search unbounded. Line numbers stay absolute so
	# lazy jump still resolves correctly.
	MAX_SEARCH_LINES = 50000
	# The fuzzy "did you mean" fallback is skipped above this many scanned
	# lines: on a big buffer it is both costly and rarely useful.
	FUZZY_MAX_LINES = 20000

	# A search whose total exceeds this (milliseconds) logs a timing
	# breakdown at INFO so a slow search is diagnosable from the NVDA log.
	_TIMING_LOG_THRESHOLD_MS = 150

	def _log_search_timing(self, total_ms, match_ms):
		"""Log a one-line timing breakdown when a search is slow."""
		if total_ms < self._TIMING_LOG_THRESHOLD_MS:
			return
		try:
			import logHandler
			logHandler.log.info(
				"Terminal Access search timing: total=%.0fms read_path=%s "
				"read=%.0fms strip=%.0fms match=%.0fms "
				"chars=%d cache_hit=%s",
				total_ms,
				getattr(self, "_last_read_path", "?"),
				getattr(self, "_last_read_ms", 0.0),
				getattr(self, "_last_strip_ms", 0.0),
				match_ms,
				getattr(self, "_last_read_chars", 0),
				getattr(self, "_last_cache_hit", False),
			)
		except Exception:
			pass

	def note_content_changed(self):
		"""Signal that the terminal produced new output.

		Invalidates the cached buffer lines so the next search re-reads.
		Cheap enough to call from every text-change event (an int bump).
		"""
		self._content_generation += 1

	def _acquire_raw_text(self):
		"""Read the full terminal buffer as a single string, or None.

		Reads in-process via makeTextInfo. This is a COM/UIA call that
		NVDA's own watchdog can cancel, unlike the retired helper-process
		read whose blocked pipe I/O could only be freed by killing the
		helper (and in the field it hung for seconds on every search).
		Main-thread-affine: must not run on a worker thread. Records
		timing/path for the search-timing summary.
		"""
		import time as _time
		t0 = _time.perf_counter()
		all_text = None
		read_path = "makeTextInfo"
		# Legacy console: NVDA only exposes the visible window, so searching
		# through it can never see scrollback. Read the full screen buffer
		# ourselves; None falls through to the normal path.
		from lib.legacy_console import is_attached_console, read_full_buffer_lines
		if is_attached_console(self._terminal):
			lines = read_full_buffer_lines()
			if lines:
				all_text = "\n".join(lines)
				read_path = "consoleBuffer"
		if all_text is None:
			try:
				info = self._terminal.makeTextInfo(textInfos.POSITION_ALL)
				all_text = info.text
			except Exception:
				all_text = None
		self._last_read_ms = (_time.perf_counter() - t0) * 1000.0
		self._last_read_path = read_path
		self._last_read_chars = len(all_text) if all_text else 0
		return all_text

	def _get_buffer_lines(self, raw_text=None):
		"""Return the ANSI-stripped, length-capped lines of the buffer.

		Cached across searches keyed on the content generation. When
		*raw_text* is given (a buffer already read by the caller, e.g. on the
		main thread before handing matching to a worker), it is used directly
		instead of reading the terminal.
		"""
		import time as _time
		gen = self._content_generation
		if (raw_text is None and self._cached_lines is not None
				and self._cached_lines_gen == gen):
			self._last_cache_hit = True
			self._last_read_path = "cache"
			self._last_read_chars = 0
			self._last_read_ms = 0.0
			self._last_strip_ms = 0.0
			return self._cached_lines
		self._last_cache_hit = False

		if raw_text is None:
			raw_text = self._acquire_raw_text()
		else:
			self._last_read_path = "provided"
			self._last_read_chars = len(raw_text)
			self._last_read_ms = 0.0
		if raw_text is None:
			# A failed acquisition is not a completed, empty search.
			return None
		if not raw_text:
			# Retry empty reads, but never reuse content preceding an empty
			# supplied snapshot when no text-change event has arrived yet.
			self._cached_lines = None
			self._cached_lines_gen = -1
			return []

		# Skip the ANSI strip entirely when there are no escape sequences:
		# a full-buffer regex sub is wasted work on clean output.
		t0 = _time.perf_counter()
		source_length = len(raw_text)
		if '\x1b' in raw_text:
			raw_text = _rt.strip_ansi(raw_text)
		self._last_strip_ms = (_time.perf_counter() - t0) * 1000.0

		max_line = self.MAX_LINE_LENGTH
		lines = raw_text.split('\n')
		truncated = any(len(line) > max_line for line in lines)
		self._cached_lines_offsets_valid = len(raw_text) == source_length and not truncated
		if truncated:
			lines = [line[:max_line] for line in lines]
		self._cached_lines = lines
		self._cached_lines_gen = gen
		return lines

	def search(self, pattern: str, case_sensitive: bool = False,
			  use_regex: bool = False, scope: str = "buffer",
			  current_line: int = 0, raw_text: str = None) -> int:
		"""
		Search for pattern in terminal output.

		Args:
			pattern: Search pattern (text or regex)
			case_sensitive: Case sensitive search
			use_regex: Use regular expression
			scope: Search scope, either "buffer" (whole terminal) or
				"section" (current section only, determined by
				SectionTokenizer)
			current_line: Current cursor line (used when scope="section"
				to determine section boundaries)
			raw_text: Pre-read buffer text. When given, matching runs on it
				directly instead of reading the terminal, so the caller can
				do the (main-thread) read and hand matching to a worker.

		Returns:
			int: Number of matches found

		Raises:
			ValueError: If pattern exceeds MAX_PATTERN_LENGTH or is an
				invalid regex.
		"""
		self._last_search_message = ""

		import time as _time
		search_t0 = _time.perf_counter()

		if not self._terminal or not pattern:
			return 0

		# Reject patterns that exceed the safety cap
		if len(pattern) > self.MAX_PATTERN_LENGTH:
			raise ValueError(
				f"Search pattern too long ({len(pattern)} chars, "
				f"max {self.MAX_PATTERN_LENGTH})"
			)

		# Validate regex early so callers get a clear error instead of a
		# silent 0-match result buried inside the broad except below.
		if use_regex:
			try:
				flags = 0 if case_sensitive else re.IGNORECASE
				re.compile(pattern, flags)
			except re.error as exc:
				try:
					import logHandler
					logHandler.log.warning(f"Terminal Access: Invalid regex '{pattern}': {exc}")
				except Exception:
					pass
				raise ValueError(f"Invalid regular expression: {exc}") from exc

		# Use a local list so matches aren't saved until search completes.
		# Matches are stored as lightweight tuples without TextInfo bookmarks.
		# The TextInfo is resolved lazily only when jumping to a match,
		# avoiding the expensive full-buffer walk that froze NVDA.
		matches = []

		max_line = self.MAX_LINE_LENGTH
		max_matches = self.MAX_MATCHES

		def _store_match(line_text, line_num, char_offset):
			"""Store a search match as a lightweight tuple.

			No TextInfo or bookmark is created here. The TextInfo is resolved
			lazily in _jump_to_match_index() when the user selects a match.
			Line text is truncated to MAX_LINE_LENGTH for safety.
			"""
			if len(matches) >= max_matches:
				return
			if len(line_text) > max_line:
				line_text = line_text[:max_line]
			matches.append((None, line_text, line_num, None, char_offset))

		def _find_match_offset(line_text, pattern, case_sensitive, use_regex):
			"""Find the character offset of the first match in the line."""
			if use_regex:
				flags = 0 if case_sensitive else re.IGNORECASE
				match = re.search(pattern, line_text, flags)
				return match.start() if match else 0
			else:
				search_pattern = pattern if case_sensitive else pattern.lower()
				search_text = line_text if case_sensitive else line_text.lower()
				offset = search_text.find(search_pattern)
				if offset >= 0 and len(search_text) != len(line_text):
					# Lowercasing can expand a codepoint (e.g. U+0130). Store
					# the source offset, not an index into the expanded text.
					lower_offset = 0
					for index, char in enumerate(line_text):
						lower_offset += len(char.lower())
						if lower_offset > offset:
							return index
				return offset if offset >= 0 else 0

		try:
			# ─── Acquire the buffer lines ───
			# Cached, ANSI-stripped, length-capped. Reads in-process via
			# makeTextInfo; matching runs in Python.
			lines = self._get_buffer_lines(raw_text)
			match_t0 = _time.perf_counter()
			if lines is None:
				self._log_search_timing(
					(_time.perf_counter() - search_t0) * 1000.0, 0.0)
				return 0

			# ─── Bound the scan to the most recent lines ───
			# A huge scrollback would otherwise make a single search scan
			# unbounded work. Indices stay absolute so line numbers (used for
			# lazy jump) remain correct.
			total_lines = len(lines)
			if total_lines > self.MAX_SEARCH_LINES:
				scan_start = total_lines - self.MAX_SEARCH_LINES
				self._last_search_message = (
					f"Searched the most recent {self.MAX_SEARCH_LINES} lines."
				)
			else:
				scan_start = 0

			if use_regex:
				flags = 0 if case_sensitive else re.IGNORECASE
				compiled = re.compile(pattern, flags)
				matching_indices = [
					i for i in range(scan_start, total_lines)
					if compiled.search(lines[i])
				]
			else:
				search_pattern = pattern if case_sensitive else pattern.lower()
				matching_indices = [
					i for i in range(scan_start, total_lines)
					if search_pattern in (
						lines[i] if case_sensitive else lines[i].lower())
				]

			# ─── Section scoping ───
			# When scope="section", restrict matching_indices to lines
			# within the current section span. Initialise the span bounds
			# before the try so the fuzzy fallback below can read them even
			# if tokenization raises early.
			section_start = None
			section_end = None
			if scope == "section":
				try:
					from lib.section_tokenizer import SectionTokenizer
					section_lines = lines
					tokenizer = SectionTokenizer()
					tokenizer.tokenize(section_lines)
					spans = tokenizer.get_spans()
					# Find the span containing current_line.
					for sp in spans:
						if sp.start_line <= current_line <= sp.end_line:
							section_start = sp.start_line
							section_end = sp.end_line
							break
					if section_start is not None:
						matching_indices = [
							i for i in matching_indices
							if section_start <= i <= section_end
						]
					else:
						matching_indices = []
				except Exception:
					# If section scoping fails, fall back to no matches
					# rather than returning unscoped results.
					matching_indices = []

			# ─── Fuzzy fallback ───
			# If exact search returned nothing, try fuzzy matching
			# (Levenshtein distance <= 1 on each word in each line). Skipped
			# on very large buffers where it is costly and rarely useful.
			fuzzy_fallback = False
			scanned_lines = total_lines - scan_start
			fuzzy_allowed = scanned_lines <= self.FUZZY_MAX_LINES
			if (not matching_indices and not use_regex and not case_sensitive
					and fuzzy_allowed):
				fuzzy_lines = lines

				# Apply section scoping to fuzzy search too. In section scope
				# with no containing span, fuzzy-match nothing rather than
				# leaking to the whole buffer (mirrors the exact path above).
				if scope == "section":
					if section_start is not None:
						fuzzy_candidate_indices = range(section_start, section_end + 1)
					else:
						fuzzy_candidate_indices = range(0)
				else:
					fuzzy_candidate_indices = range(scan_start, total_lines)

				for i in fuzzy_candidate_indices:
					if i >= len(fuzzy_lines):
						break
					line = fuzzy_lines[i]
					if self._line_fuzzy_matches(pattern, line):
						matching_indices.append(i)
						if len(matching_indices) >= max_matches:
							break

				if matching_indices:
					fuzzy_fallback = True
					self._last_search_message = (
						f"No exact matches. Found {len(matching_indices)} "
						f"fuzzy match{'es' if len(matching_indices) != 1 else ''}."
					)

			# ─── Store matches without TextInfo ───
			# Matches are stored as lightweight tuples. No bookmark walk
			# is performed here. The TextInfo is resolved lazily in
			# _jump_to_match_index() when the user selects a match.
			def _get_line_text(line_index):
				"""Get line text for a matched line index."""
				if 0 <= line_index < len(lines):
					return lines[line_index]
				return ""

			for line_index in matching_indices:
				line_text = _get_line_text(line_index)
				char_offset = _find_match_offset(
					line_text, pattern, case_sensitive, use_regex
				)
				_store_match(line_text, line_index + 1, char_offset)

			# Record pattern in search history.
			self.add_to_history(pattern)

			# Save results for the current window, tagged with the content
			# generation so a later navigate can detect stale results.
			self._save_search_state({
				'pattern': pattern,
				'matches': matches,
				'current_match_index': -1,
				'case_sensitive': case_sensitive,
				'use_regex': use_regex,
				'scope': scope,
				'current_line': current_line,
				'generation': self._content_generation,
			})

			self._log_search_timing(
				(_time.perf_counter() - search_t0) * 1000.0,
				(_time.perf_counter() - match_t0) * 1000.0)
			return len(matches)

		except Exception:
			try:
				import logHandler
				logHandler.log.error("Terminal Access: search() failed", exc_info=True)
			except Exception:
				pass
			return 0

	def refresh_search_if_stale(self) -> bool:
		"""Re-run the active search if the buffer changed since it ran.

		Search results are a snapshot: after the program prints more output
		the stored matches can point at moved lines and new matches are
		missed. Called before find next/previous so navigation reflects the
		live buffer. The user's place is preserved by re-locating the current
		match's text in the refreshed results. Returns True if it refreshed.
		"""
		state = self._get_search_state()
		pattern = state.get('pattern')
		if not pattern:
			return False
		if state.get('generation') == self._content_generation:
			return False  # results are current

		prev = self.get_current_match_info()
		prev_text = prev[2] if prev else None
		try:
			self.search(
				pattern,
				case_sensitive=state.get('case_sensitive', False),
				use_regex=state.get('use_regex', False),
				scope=state.get('scope', 'buffer'),
				current_line=state.get('current_line', 0),
			)
		except Exception:
			return False

		# Restore the position to the same line text where possible.
		if prev_text:
			new_state = self._get_search_state()
			for i, match in enumerate(new_state['matches']):
				if self._unpack_match(match)[1] == prev_text:
					new_state['current_match_index'] = i
					self._save_search_state(new_state)
					break
		return True

	def next_match(self) -> bool:
		"""
		Jump to next match.

		Returns:
			bool: True if jumped to next match
		"""
		state = self._get_search_state()
		matches = state['matches']
		if not matches:
			return False

		# Move to next match (wrap around)
		state['current_match_index'] = (state['current_match_index'] + 1) % len(matches)
		self._save_search_state(state)
		return self._jump_to_current_match()

	def previous_match(self) -> bool:
		"""
		Jump to previous match.

		Returns:
			bool: True if jumped to previous match
		"""
		state = self._get_search_state()
		matches = state['matches']
		if not matches:
			return False

		# Move to previous match (wrap around)
		state['current_match_index'] = (state['current_match_index'] - 1) % len(matches)
		self._save_search_state(state)
		return self._jump_to_current_match()

	def first_match(self) -> bool:
		"""
		Jump to first match.

		Returns:
			bool: True if jumped to first match
		"""
		state = self._get_search_state()
		if not state['matches']:
			return False

		state['current_match_index'] = 0
		self._save_search_state(state)
		return self._jump_to_current_match()

	def last_match(self) -> bool:
		"""
		Jump to last match.

		Returns:
			bool: True if jumped to last match
		"""
		state = self._get_search_state()
		if not state['matches']:
			return False

		state['current_match_index'] = len(state['matches']) - 1
		self._save_search_state(state)
		return self._jump_to_current_match()

	def _unpack_match(self, match):
		"""Handle legacy (bookmark, text, line), (bookmark, text, line, pos), and new (bookmark, text, line, pos, offset) tuples."""
		if len(match) == 5:
			return match[0], match[1], match[2], match[3], match[4]
		elif len(match) == 4:
			return match[0], match[1], match[2], match[3], 0
		bookmark, line_text, line_num = match
		return bookmark, line_text, line_num, None, 0

	def _jump_to_current_match(self) -> bool:
		"""
		Jump to current match index and position cursor at the search term.

		TextInfo is resolved lazily here (not during search). This avoids
		walking the entire buffer during search, which froze NVDA on large
		scrollback buffers.

		Returns:
			bool: True if jump successful
		"""
		state = self._get_search_state()
		matches = state['matches']
		current_index = state['current_match_index']
		if not matches or current_index < 0:
			return False

		try:
			bookmark, line_text, line_num, pos_info, char_offset = self._unpack_match(
				matches[current_index]
			)

			# Resolve TextInfo lazily: navigate from POSITION_FIRST
			# to the target line. Only one move() call per jump.
			pos = None
			if bookmark is not None:
				try:
					pos = self._terminal.makeTextInfo(bookmark)
				except (RuntimeError, AttributeError, TypeError, ValueError):
					pos = None

			if pos is None and pos_info is not None:
				try:
					pos = pos_info.copy()
				except (RuntimeError, AttributeError):
					pos = pos_info

			if pos is None and line_num is not None:
				# Resolve by the matched line's text rather than by counting
				# lines. The buffer was searched from POSITION_ALL.text split
				# on newlines, but navigation counts UNIT_LINE, and in a
				# terminal those disagree (wrapped rows, blank padding rows),
				# so "line N of the split" lands on a different (often blank)
				# row than "N lines down". Walking to the line that actually
				# contains the text sidesteps the mismatch.
				# Try the codepoint offset first (one call, unambiguous even
				# when the same text repeats); it verifies itself against
				# line_text and falls through to the walk if it does not
				# check out, e.g. when ANSI codes shifted the story text.
				pos = self._resolve_line_by_content(
					line_text, line_num,
					offset=self._absolute_offset_for(line_num, char_offset or 0),
				)
				if pos is None:
					# Last-resort positional fallback (may drift).
					try:
						pos = self._terminal.makeTextInfo(textInfos.POSITION_FIRST)
						if line_num > 1:
							pos.move(textInfos.UNIT_LINE, line_num - 1)
					except (RuntimeError, AttributeError, TypeError):
						pos = None

			if pos:
				# Land at the beginning of the matched line, like a bookmark
				# jump, rather than on the search term itself. Expanding to the
				# line unit puts the review cursor at the line start and lets
				# NVDA read the whole line. (char_offset is retained on the
				# match tuple for display but no longer moves the cursor.)
				try:
					pos.expand(textInfos.UNIT_LINE)
				except (RuntimeError, AttributeError, TypeError):
					pass

				_rt.api_module.setReviewPosition(pos)
				return True
		except (RuntimeError, AttributeError, TypeError, IndexError):
			pass

		return False

	def _resolve_line_by_content(self, line_text, line_hint, offset=None):
		"""Return a TextInfo on the buffer line whose text matches
		*line_text*, or None. See lib.line_resolve.resolve_line_by_content.

		*offset* is an absolute codepoint offset when the caller knows
		one; it resolves in a single call instead of walking the buffer,
		and is verified against *line_text* before being trusted.
		"""
		from lib.line_resolve import resolve_line_by_content
		return resolve_line_by_content(
			self._terminal, line_text, line_hint, self.MAX_SEARCH_LINES,
			offset=offset)

	def _absolute_offset_for(self, line_num, char_offset=0):
		"""Absolute codepoint offset of a match, or None if unavailable.

		Match line numbers are one-based. If ANSI removal or truncation
		shortened the cached text, use content resolution instead: even a
		verified offset can otherwise land on the wrong duplicate line.
		"""
		from lib.line_resolve import absolute_offset
		lines = self._cached_lines
		if not lines or not self._cached_lines_offsets_valid:
			return None
		return absolute_offset(lines, line_num - 1, char_offset)

	def get_match_count(self) -> int:
		"""
		Get total number of matches.

		Returns:
			int: Number of matches
		"""
		state = self._get_search_state()
		return len(state['matches'])

	def get_current_match_info(self) -> tuple:
		"""
		Get information about current match.

		Returns:
			tuple: (match_number, total_matches, line_text, line_num) or None
		"""
		state = self._get_search_state()
		matches = state['matches']
		current_index = state['current_match_index']
		if not matches or current_index < 0:
			return None

		_, line_text, line_num, _, _ = self._unpack_match(matches[current_index])
		return (current_index + 1, len(matches), line_text, line_num)

	def get_all_matches(self) -> list:
		"""Get all search matches as structured dicts for dialog display.

		Returns:
			List of dicts with keys: num, line_num, text, bookmark, pos, offset.
			Empty list if no search has been performed or no matches found.
		"""
		state = self._get_search_state()
		matches = state['matches']
		results = []
		for i, match in enumerate(matches):
			bookmark, line_text, line_num, pos_info, char_offset = self._unpack_match(match)
			truncated = (line_text[:100] + "...") if len(line_text) > 100 else line_text
			results.append({
				"num": i + 1,
				"line_num": line_num,
				"text": truncated,
				"bookmark": bookmark,
				"pos": pos_info,
				"offset": char_offset,
			})
		return results

	def clear_search(self) -> None:
		"""Clear current search results."""
		self._save_search_state({
			'pattern': None,
			'matches': [],
			'current_match_index': -1,
			'case_sensitive': False,
			'use_regex': False
		})

	# ------------------------------------------------------------------
	# Search history
	# ------------------------------------------------------------------

	def add_to_history(self, pattern: str) -> None:
		"""Record a search pattern in the history list.

		Duplicates are removed so the pattern appears only once, at the
		front (most recent position). The history is capped at 10 entries.
		"""
		if not pattern:
			return
		# Remove existing occurrence to avoid duplicates.
		try:
			self._search_history.remove(pattern)
		except ValueError:
			pass
		# Insert at the front (most recent first).
		self._search_history.insert(0, pattern)
		# Cap at 10 entries.
		if len(self._search_history) > 10:
			self._search_history = self._search_history[:10]

	def get_history(self) -> list[str]:
		"""Return the search history list, most recent first."""
		return list(self._search_history)

	# ------------------------------------------------------------------
	# Fuzzy matching
	# ------------------------------------------------------------------

	@staticmethod
	def _levenshtein_distance(s1: str, s2: str) -> int:
		"""Compute Damerau-Levenshtein (optimal string alignment) distance.

		Counts insertions, deletions, substitutions, and adjacent
		transpositions as single edits. This means "erorr" vs "error"
		(which involves a transposition) counts as fewer edits than
		standard Levenshtein. Intended for word-level fuzzy comparisons.
		"""
		len1, len2 = len(s1), len(s2)
		# Build a full matrix so we can look back two rows for
		# transposition detection.
		d = [[0] * (len2 + 1) for _ in range(len1 + 1)]
		for i in range(len1 + 1):
			d[i][0] = i
		for j in range(len2 + 1):
			d[0][j] = j

		for i in range(1, len1 + 1):
			for j in range(1, len2 + 1):
				cost = 0 if s1[i - 1] == s2[j - 1] else 1
				d[i][j] = min(
					d[i - 1][j] + 1,      # deletion
					d[i][j - 1] + 1,      # insertion
					d[i - 1][j - 1] + cost,  # substitution
				)
				# Transposition check.
				if (i > 1 and j > 1
						and s1[i - 1] == s2[j - 2]
						and s1[i - 2] == s2[j - 1]):
					d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)

		return d[len1][len2]

	@staticmethod
	def _within_one_edit(left: str, right: str) -> bool:
		"""Accept at most one insertion, deletion, substitution or swap.

		Only the first differing position needs a decision. The remaining
		suffix must match exactly, so work is linear in the word length.
		"""
		if abs(len(left) - len(right)) > 1:
			return False
		if len(left) > len(right):
			left, right = right, left
		index = 0
		while index < len(left) and left[index] == right[index]:
			index += 1
		if index == len(left):
			return True
		if len(left) != len(right):
			return left[index:] == right[index + 1:]
		if left[index + 1:] == right[index + 1:]:
			return True  # one substitution
		return (
			index + 1 < len(left)
			and left[index] == right[index + 1]
			and left[index + 1] == right[index]
			and left[index + 2:] == right[index + 2:]
		)

	def _line_fuzzy_matches(self, pattern: str, line: str) -> bool:
		"""Check whether any word in *line* is within Levenshtein
		distance 1 of *pattern* (case-insensitive)."""
		pat_lower = pattern.lower()
		# Split on whitespace and common punctuation to get words.
		words = re.split(r'[\s:;,.()\[\]{}=<>!@#$%^&*|/\\]+', line)
		for word in words:
			if not word:
				continue
			if self._within_one_edit(pat_lower, word.lower()):
				return True
		return False

	def fuzzy_search(self, pattern: str, lines: list[str]) -> list[str]:
		"""Search *lines* for fuzzy matches of *pattern*.

		Returns a list of matching line texts where at least one word is
		within Levenshtein distance 1 of the pattern (case-insensitive).
		"""
		if not pattern:
			return []
		results = []
		for line in lines:
			if self._line_fuzzy_matches(pattern, line):
				results.append(line)
		return results

	def get_last_search_message(self) -> str:
		"""Return the informational message from the last search.

		This is set when a fuzzy fallback occurs, containing a note like
		'No exact matches. Found N fuzzy matches.'
		"""
		return self._last_search_message

	def update_terminal(self, terminal_obj):
		"""
		Update the terminal reference.

		This should be called when the terminal is rebound to ensure
		searches can be properly performed.

		Args:
			terminal_obj: New terminal TextInfo object
		"""
		# Search state is keyed on the window handle, so a rebind (a fresh
		# NVDAObject for the same window on every focus event) automatically
		# resolves to the same window's search, and switching to another
		# window selects that window's own search. Nothing to clear here.
		# The buffer cache is per-content, so it is dropped: output may have
		# changed while focus was elsewhere.
		self._terminal = terminal_obj
		self.note_content_changed()
		self._cached_lines = None

	def set_tab_manager(self, tab_manager):
		"""
		Set or update the tab manager for tab-aware search storage.

		Args:
			tab_manager: TabManager instance
		"""
		self._tab_manager = tab_manager


# ── URL entry data structure ─────────────────────────────────────────
UrlEntry = collections.namedtuple('UrlEntry', ['url', 'line_num', 'line_text', 'source', 'count'])


class UrlExtractorManager:
	"""
	Extract and manage URLs found in terminal output.

	Scans terminal buffer for URLs (HTTP/HTTPS/FTP, www-prefixed,
	file:// protocol, and OSC 8 terminal hyperlinks) and provides
	a navigable list with copy/open/move-to actions.
	"""

	def __init__(self, terminal_obj, tab_manager=None):
		self._terminal = terminal_obj
		self._tab_manager = tab_manager
		self._urls: list = []  # list of UrlEntry

	def extract_urls(self) -> list:
		"""Scan terminal buffer and return deduplicated URLs with context.

		Returns:
			List of UrlEntry namedtuples ordered by first occurrence.
		"""
		if not self._terminal:
			return []

		try:
			text_info = self._terminal.makeTextInfo(textInfos.POSITION_ALL)
			raw_text = text_info.text
		except (RuntimeError, AttributeError, TypeError):
			try:
				import logHandler
				logHandler.log.debugWarning("UrlExtractorManager: failed to read terminal text", exc_info=True)
			except (ImportError, AttributeError):
				pass
			return []

		if not raw_text:
			return []

		# Phase 1: Extract OSC 8 hyperlinks from raw text (before ANSI strip)
		osc8_urls: dict[str, int] = {}  # url -> first line_num
		raw_lines = raw_text.split('\n')
		for line_num, line in enumerate(raw_lines, start=1):
			for match in _OSC8_URL_PATTERN.finditer(line):
				url = _clean_url(match.group(1).strip())
				if url and url not in osc8_urls:
					osc8_urls[url] = line_num

		# Phase 2: Extract plain-text URLs after ANSI stripping
		clean_text = _rt.strip_ansi(raw_text)
		lines = clean_text.split('\n')

		# Deduplicate preserving first-occurrence order
		seen: collections.OrderedDict = collections.OrderedDict()

		# Add OSC 8 URLs first
		for url, line_num in osc8_urls.items():
			line_text = lines[line_num - 1].strip() if line_num <= len(lines) else ''
			seen[url] = {'line_num': line_num, 'line_text': line_text, 'source': 'osc8', 'count': 1}

		# Scan each line for plain-text URLs
		for line_num, line in enumerate(lines, start=1):
			for match in _URL_PATTERN.finditer(line):
				url = _clean_url(match.group(0).strip())
				if not url:
					continue
				if url in seen:
					seen[url]['count'] += 1
				else:
					seen[url] = {
						'line_num': line_num,
						'line_text': line.strip(),
						'source': 'text',
						'count': 1,
					}

		self._urls = [
			UrlEntry(url=url, line_num=meta['line_num'], line_text=meta['line_text'],
			         source=meta['source'], count=meta['count'])
			for url, meta in seen.items()
		]
		return list(self._urls)

	def get_url_count(self) -> int:
		"""Return number of extracted URLs."""
		return len(self._urls)

	def copy_url(self, index: int) -> bool:
		"""Copy URL at index to clipboard."""
		if 0 <= index < len(self._urls):
			_rt.api_module.copyToClip(self._urls[index].url)
			return True
		return False

	# Schemes considered safe to open in a browser.
	_SAFE_SCHEMES = ('http://', 'https://', 'ftp://')

	# Schemes that are always blocked regardless of user settings.
	_BLOCKED_SCHEMES = ('file://', 'javascript:', 'data:')

	@classmethod
	def _is_safe_url(cls, url: str) -> bool:
		"""Check whether a URL uses a safe scheme.

		Returns True for http://, https://, and ftp:// URLs.
		Returns False for file://, javascript:, data:, and any other
		unrecognized scheme.
		"""
		lower = url.lower()
		if any(lower.startswith(s) for s in cls._BLOCKED_SCHEMES):
			return False
		# www. URLs are treated as safe (will get https:// prepended)
		if lower.startswith('www.'):
			return True
		return lower.startswith(cls._SAFE_SCHEMES)

	@classmethod
	def _prepare_safe_url(cls, url: str):
		"""Normalize *url* and return it if safe to open, else None.

		Single source of truth shared by ``open_url`` and the URL-list
		dialog's Open action so the two paths cannot drift apart. Strips
		surrounding whitespace, prepends ``https://`` to bare ``www.``
		links, then applies the blocklist+allowlist scheme check.
		"""
		url = url.strip()
		if url.lower().startswith('www.'):
			url = 'https://' + url
		if not cls._is_safe_url(url):
			return None
		return url

	def open_url(self, index: int) -> bool:
		"""Open URL at index in default browser.

		Only http://, https://, and ftp:// URLs are opened.  Other schemes
		(file://, javascript:, etc.) are rejected to prevent a malicious
		terminal from launching local executables.
		"""
		if 0 <= index < len(self._urls):
			safe_url = self._prepare_safe_url(self._urls[index].url)
			if safe_url is None:
				return False
			try:
				_rt.webbrowser_module.open(safe_url)
				return True
			except (OSError, ValueError):
				return False
		return False

	def update_terminal(self, terminal_obj):
		"""Update terminal reference and clear cached URLs."""
		self._terminal = terminal_obj
		self._urls = []

	def set_tab_manager(self, tab_manager):
		"""Set or update tab manager."""
		self._tab_manager = tab_manager


def UrlListDialog(parent, urls, manager):
	"""Dialog for displaying and interacting with URLs found in terminal output.

	Thin wrapper: builds # / URL / Line / Context rows and delegates to
	BrowsableListDialog. Enter or the Open button opens the selected URL in
	the browser (unsafe schemes are blocked), the Copy URL and Move to line
	buttons act on the selection and close, a type-to-filter box matches the
	URL and context columns, and Escape closes.

	Modeled after NVDA's Elements List (NVDA+F7) but designed for terminal
	focus mode where the Elements List is unavailable.

	Args:
		parent: Parent window.
		urls: List of UrlEntry namedtuples with url, line_num, line_text.
		manager: The UrlExtractorManager (kept for signature compatibility).

	Returns:
		A BrowsableListDialog instance ready for ShowModal().
	"""
	from lib.list_dialogs import BrowsableListDialog, build_url_rows

	rows = build_url_rows(urls)

	def on_open(original_index):
		entry = urls[original_index]
		# Use the shared normalize+scheme check so this path stays in sync
		# with UrlExtractorManager.open_url (blocklist + allowlist).
		safe_url = UrlExtractorManager._prepare_safe_url(entry.url)
		if safe_url is None:
			# Translators: Announced when a URL with an unsafe scheme is blocked
			ui.message(_("Cannot open this URL type for security reasons"))
			return
		try:
			_rt.webbrowser_module.open(safe_url)
		except Exception:
			pass

	def on_copy(original_index):
		_rt.api_module.copyToClip(urls[original_index].url)
		# Translators: Announced after URL is copied
		ui.message(_("URL copied"))
		return True

	def on_move(original_index):
		entry = urls[original_index]
		# Translators: Announced when moving to a URL line
		ui.message(_("Line {num}: {text}").format(
			num=entry.line_num, text=(entry.line_text or "")[:100]))
		return True

	return BrowsableListDialog(
		parent,
		# Translators: Title for URL list dialog
		title=_("URL List - Terminal Access"),
		columns=[
			# Translators: Column header for URL list index
			(_("#"), 40),
			# Translators: Column header for URL
			(_("URL"), 320),
			# Translators: Column header for line number
			(_("Line"), 55),
			# Translators: Column header for line context
			(_("Context"), 220),
		],
		rows=rows,
		on_activate=on_open,
		extra_buttons=[
			# Translators: Button to copy URL to clipboard
			(_("&Copy URL"), on_copy),
			# Translators: Button to move cursor to URL line
			(_("&Move to line"), on_move),
		],
		enable_search=True,
		search_columns=(1, 3),
	)


def SearchResultsDialog(parent, search_manager, on_jump_callback=None):
	"""Dialog for browsing and jumping to search results.

	Thin wrapper: builds # / Line / Content rows and delegates to
	BrowsableListDialog. Enter or the Activate button records the chosen
	match as the manager's current index (so findNext/findPrevious continue
	from there), jumps to it, and closes. Escape closes. The match count and
	pattern go in the dialog title so they are announced on open.

	Args:
		parent: Parent window.
		search_manager: Manager exposing get_all_matches(),
			_get_search_state(), _save_search_state() and
			_jump_to_current_match().
		on_jump_callback: Optional callable() fired after a jump.

	Returns:
		A BrowsableListDialog instance ready for ShowModal().
	"""
	from lib.list_dialogs import BrowsableListDialog, build_search_rows

	matches = search_manager.get_all_matches()
	rows = build_search_rows(matches)
	state = search_manager._get_search_state()
	pattern = state.get('pattern', '')
	# Translators: Title for search results dialog, with the match count and pattern
	title = _("Search Results: {count} matches for '{pattern}'").format(
		count=len(matches), pattern=pattern)

	def on_jump(original_index):
		# Set the search manager's current index so findNext/findPrevious
		# continue from this position after the dialog closes.
		jump_state = search_manager._get_search_state()
		jump_state['current_match_index'] = original_index
		search_manager._save_search_state(jump_state)
		search_manager._jump_to_current_match()
		if on_jump_callback:
			on_jump_callback()

	return BrowsableListDialog(
		parent,
		title=title,
		columns=[
			# Translators: Column header for match number
			(_("#"), 50),
			# Translators: Column header for line number
			(_("Line"), 60),
			# Translators: Column header for line content
			(_("Content"), 400),
		],
		rows=rows,
		on_activate=on_jump,
	)

