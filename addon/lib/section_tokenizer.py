# Semantic Section Tokenizer for terminal output.
# Classifies buffer lines into categories (prompt, error, warning,
# stack_trace, progress, timestamp, heading, output) and provides
# navigation helpers for jumping between sections.

import re
from collections import namedtuple
from typing import Optional

from lib.text_processing import ErrorLineDetector

Section = namedtuple("Section", ["line_num", "category", "text"])
SectionSpan = namedtuple("SectionSpan", ["start_line", "end_line", "category"])


class SectionTokenizer:
	"""Classify terminal buffer lines into semantic sections and navigate them.

	Usage::

		tokenizer = SectionTokenizer()
		sections = tokenizer.tokenize(lines)
		spans = tokenizer.get_spans()
		next_sec = tokenizer.next_section(current_line)
	"""

	# Prompt patterns (checked first, before error detector).
	_PROMPT_PATTERNS = [
		# user@host:path$ or user@host:path#
		re.compile(r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+:[^\$#]*[\$#]\s'),
		# PS C:\path>
		re.compile(r'^PS\s+[A-Za-z]:\\.*>\s*', re.IGNORECASE),
		# "$ " at start of line (common POSIX prompt)
		re.compile(r'^\$\s'),
		# "> " at start of line (cmd.exe, node REPL, etc.)
		re.compile(r'^>\s'),
		# Bare prompt with nothing after it: "$ " at end of line
		re.compile(r'^\$\s*$'),
	]

	# Stack trace patterns.
	_STACK_TRACE_PATTERNS = [
		# Python: '  File "...", line NN, in ...'
		re.compile(r'^\s+File\s+".*",\s+line\s+\d+'),
		# Java/JS: '  at com.example.Class.method(...)'
		re.compile(r'^\s+at\s+'),
		# Ruby/Rust: '  from /path:NN:in ...'
		re.compile(r'^\s+from\s+\S+:\d+'),
	]

	# Progress patterns.
	_PROGRESS_PATTERNS = [
		# Bracket progress bars: [====>    ] or [####    ]
		re.compile(r'\[[\s=>#\-]+\]\s*\d+%'),
		# Percentage at end of line
		re.compile(r'\b\d{1,3}%\s*$'),
		# "Downloading ..." with file/size info
		re.compile(r'^\s*Downloading\s+\S+', re.IGNORECASE),
		# Spinner characters at start: / | \ -
		re.compile(r'^[/|\\]\s+\S'),
	]

	# Timestamp patterns.
	_TIMESTAMP_PATTERNS = [
		# ISO 8601: 2024-01-15T10:30:45Z or with offset
		re.compile(r'^\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'),
	]

	# Heading patterns.
	_HEADING_PATTERNS = [
		# Lines of repeated = or - (at least 5 chars)
		re.compile(r'^[\s]*[=]{5,}[\s\w]*[=]*$'),
		re.compile(r'^[\s]*[-]{5,}[\s]*$'),
		# ALL CAPS header with 3+ words (letters and spaces only)
		re.compile(r'^[A-Z][A-Z ]{4,}$'),
	]

	def __init__(self) -> None:
		self._sections: list[Section] = []
		self._spans: list[SectionSpan] = []

	def tokenize(self, lines: list[str]) -> list[Section]:
		"""Classify each line and return a list of Section namedtuples.

		Args:
			lines: Buffer lines to classify.

		Returns:
			List of Section(line_num, category, text) for every input line.
		"""
		self._sections = []
		self._spans = []

		if not lines:
			return self._sections

		prev_category: Optional[str] = None

		for idx, line in enumerate(lines):
			category = self._classify(line, idx, lines)
			self._sections.append(Section(line_num=idx, category=category, text=line))

		# Build spans from consecutive same-category runs.
		self._build_spans()
		return self._sections

	def get_spans(self) -> list[SectionSpan]:
		"""Return grouped spans of consecutive same-category lines."""
		return list(self._spans)

	# ------------------------------------------------------------------
	# Navigation
	# ------------------------------------------------------------------

	def next_section(self, current_line: int, category: Optional[str] = None) -> Optional[Section]:
		"""Find the next section boundary after *current_line*.

		If *category* is given, skip spans that do not match.

		Returns:
			The first Section of the next (matching) span, or None.
		"""
		if not self._spans:
			return None

		# Find the span that contains current_line.
		current_span_idx = self._span_index_for(current_line)
		if current_span_idx is None:
			return None

		# Walk forward through subsequent spans.
		for i in range(current_span_idx + 1, len(self._spans)):
			span = self._spans[i]
			if category is None or span.category == category:
				return self._sections[span.start_line]
		return None

	def prev_section(self, current_line: int, category: Optional[str] = None) -> Optional[Section]:
		"""Find the previous section boundary before *current_line*.

		If *category* is given, skip spans that do not match.

		Returns:
			The first Section of the previous (matching) span, or None.
		"""
		if not self._spans:
			return None

		current_span_idx = self._span_index_for(current_line)
		if current_span_idx is None:
			return None

		for i in range(current_span_idx - 1, -1, -1):
			span = self._spans[i]
			if category is None or span.category == category:
				return self._sections[span.start_line]
		return None

	def next_error(self, current_line: int) -> Optional[Section]:
		"""Jump to the next error or warning line after *current_line*."""
		for section in self._sections:
			if section.line_num > current_line and section.category in ("error", "warning"):
				return section
		return None

	def prev_error(self, current_line: int) -> Optional[Section]:
		"""Jump to the previous error or warning line before *current_line*."""
		result = None
		for section in self._sections:
			if section.line_num >= current_line:
				break
			if section.category in ("error", "warning"):
				result = section
		return result

	def next_prompt(self, current_line: int) -> Optional[Section]:
		"""Jump to the next prompt line after *current_line*."""
		for section in self._sections:
			if section.line_num > current_line and section.category == "prompt":
				return section
		return None

	def prev_prompt(self, current_line: int) -> Optional[Section]:
		"""Jump to the previous prompt line before *current_line*."""
		result = None
		for section in self._sections:
			if section.line_num >= current_line:
				break
			if section.category == "prompt":
				result = section
		return result

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _classify(self, line: str, idx: int, all_lines: list[str]) -> str:
		"""Return the semantic category for a single line.

		Classification priority:
		1. Prompt (highest, so a prompt line with an error keyword
		   is still treated as a prompt).
		2. Stack trace (structural indentation patterns).
		3. Error / Warning (via ErrorLineDetector).
		4. Progress indicators.
		5. Timestamp prefixes.
		6. Heading / separator.
		7. Output (fallback).
		"""
		# 1. Prompt
		for pat in self._PROMPT_PATTERNS:
			if pat.search(line):
				return "prompt"

		# 2. Stack trace (before error, because indented code lines in
		#    a traceback should not be reclassified as output).
		for pat in self._STACK_TRACE_PATTERNS:
			if pat.search(line):
				return "stack_trace"
		# Also classify indented code that follows a stack_trace File line
		# as stack_trace (the "    result = process(data)" lines).
		if idx > 0 and line.startswith("    "):
			prev_section = self._sections[idx - 1] if idx <= len(self._sections) else None
			if prev_section and prev_section.category == "stack_trace":
				return "stack_trace"

		# 3. Error / Warning (via shared ErrorLineDetector)
		err_class = ErrorLineDetector.classify(line)
		if err_class is not None:
			return err_class

		# 4. Progress
		for pat in self._PROGRESS_PATTERNS:
			if pat.search(line):
				return "progress"

		# 5. Timestamp
		for pat in self._TIMESTAMP_PATTERNS:
			if pat.search(line):
				return "timestamp"

		# 6. Heading
		for pat in self._HEADING_PATTERNS:
			if pat.search(line):
				return "heading"

		# 7. Fallback
		return "output"

	def _build_spans(self) -> None:
		"""Group consecutive same-category sections into SectionSpan objects."""
		if not self._sections:
			return

		spans: list[SectionSpan] = []
		start = 0
		current_cat = self._sections[0].category

		for i in range(1, len(self._sections)):
			if self._sections[i].category != current_cat:
				spans.append(SectionSpan(start_line=start, end_line=i - 1, category=current_cat))
				start = i
				current_cat = self._sections[i].category

		# Close final span.
		spans.append(SectionSpan(start_line=start, end_line=len(self._sections) - 1, category=current_cat))
		self._spans = spans

	def _span_index_for(self, line_num: int) -> Optional[int]:
		"""Return the index into self._spans that contains *line_num*."""
		for i, span in enumerate(self._spans):
			if span.start_line <= line_num <= span.end_line:
				return i
		return None
