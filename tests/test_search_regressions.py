"""Search state and real result navigation after new output or a failed query."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
import textInfos

from lib.search import OutputSearchManager
from lib.text_processing import ANSIParser
import lib._runtime as rt


class Terminal:
	"""TextInfo boundary with explicit codepoint and line movement semantics."""
	windowHandle = 1

	def __init__(self, text):
		self.text = text
		self.fail_reads = False

	def makeTextInfo(self, position):
		if self.fail_reads:
			raise RuntimeError("provider unavailable")
		if position == textInfos.POSITION_ALL:
			return SimpleNamespace(text=self.text)
		assert position == textInfos.POSITION_FIRST
		return LineInfo(self)


class LineInfo:
	"""Line identity remains observable when identical text appears twice."""

	def __init__(self, terminal, row=0):
		self.terminal = terminal
		self.row = row

	@property
	def text(self):
		return self.terminal.text.split('\n')[self.row]

	def moveToCodepointOffset(self, offset):
		if offset > len(self.terminal.text):
			raise ValueError(offset)
		return LineInfo(self.terminal, self.terminal.text[:offset].count('\n'))

	def expand(self, unit):
		assert unit == textInfos.UNIT_LINE

	def copy(self):
		return LineInfo(self.terminal, self.row)

	def move(self, unit, count):
		assert unit == textInfos.UNIT_LINE
		previous = self.row
		self.row = min(max(self.row + count, 0), len(self.terminal.text.split('\n')) - 1)
		return self.row - previous


@pytest.mark.parametrize('raw', ['ordinary output', ''])
def test_completed_no_match_replaces_previous_query_and_results(raw):
	"""Find Next cannot navigate a query that has been replaced by no results."""
	manager = OutputSearchManager(Terminal('needle'))
	assert manager.search('needle') == 1
	assert manager.search('missing', raw_text=raw) == 0
	assert manager.get_match_count() == 0
	assert manager.next_match() is False
	assert manager._get_search_state()['pattern'] == 'missing'
	assert manager.get_history()[0] == 'missing'
	assert manager.refresh_search_if_stale() is False


def test_empty_supplied_buffer_cannot_resurrect_previous_cached_content():
	terminal = Terminal('needle')
	manager = OutputSearchManager(terminal)
	assert manager.search('needle') == 1
	terminal.text = ''
	assert manager.search('needle', raw_text='') == 0
	assert manager.search('needle') == 0


def test_failed_read_and_rejected_queries_preserve_previous_search():
	terminal = Terminal('needle')
	manager = OutputSearchManager(terminal)
	assert manager.search('needle') == 1
	terminal.fail_reads = True
	manager.note_content_changed()
	assert manager.search('missing') == 0
	with pytest.raises(ValueError):
		manager.search('[', use_regex=True)
	with pytest.raises(ValueError):
		manager.search('x' * 501)
	assert manager.search('') == 0
	assert manager.get_match_count() == 1
	assert manager._get_search_state()['pattern'] == 'needle'


def test_refresh_that_removes_last_match_completes_once():
	terminal = Terminal('needle')
	manager = OutputSearchManager(terminal)
	manager.search('needle')
	terminal.text = 'ordinary'
	manager.note_content_changed()
	assert manager.refresh_search_if_stale() is True
	assert manager.get_match_count() == 0
	assert manager.refresh_search_if_stale() is False


def test_refresh_keeps_section_scope_after_other_section_grows():
	terminal = Terminal('$ first\nerror one\n$ second\nerror two')
	manager = OutputSearchManager(terminal)
	assert manager.search('error', scope='section', current_line=1) == 1
	terminal.text += '\nerror three'
	manager.note_content_changed()
	assert manager.refresh_search_if_stale() is True
	assert manager.get_match_count() == 1
	assert manager.first_match()
	assert manager.get_current_match_info()[2] == 'error one'


def test_public_navigation_lands_on_each_consecutive_duplicate():
	manager = OutputSearchManager(Terminal('needle\nneedle\nend'))
	assert manager.search('needle') == 2
	positions = []
	with patch.object(rt.api_module, 'setReviewPosition', side_effect=lambda info: positions.append(info.row)):
		assert manager.first_match()
		assert manager.next_match()
		assert manager.previous_match()
	assert positions == [0, 1, 0]


@pytest.mark.parametrize('prefix', ['x' * 10001, '\x1b[0mx'])
def test_navigation_after_shortened_line_preserves_duplicate_occurrences(prefix, monkeypatch):
	"""Truncation and ANSI stripping cannot shift a duplicate result's target."""
	monkeypatch.setattr(rt, 'strip_ansi', ANSIParser.stripANSI)
	manager = OutputSearchManager(Terminal(prefix + '\nneedle\nneedle'))
	assert manager.search('needle') == 2
	positions = []
	with patch.object(rt.api_module, 'setReviewPosition', side_effect=lambda info: positions.append(info.row)):
		assert manager.first_match()
		assert manager.next_match()
	assert positions == [1, 2]


def test_case_insensitive_offset_uses_original_unicode_codepoints():
	manager = OutputSearchManager(Terminal('\u0130 x'))
	assert manager.search('x') == 1
	assert manager._get_search_state()['matches'][0][4] == 2


@pytest.mark.parametrize('word,expected', [
	('cat', True), ('bat', True), ('cats', True), ('at', True),
	('cta', True), ('act', True), ('cut', True), ('dog', False),
	('caats', False), ('tac', False), ('', False),
])
def test_fuzzy_preserves_single_edit_and_transposition_semantics(word, expected):
	manager = OutputSearchManager(Terminal(''))
	assert bool(manager.fuzzy_search('cat', [word])) is expected


def test_unicode_fuzzy_length_check_uses_the_compared_lowercase_words():
	manager = OutputSearchManager(Terminal(''))
	assert manager.fuzzy_search('i\u0307i\u0307x', ['\u0130\u0130']) == ['\u0130\u0130']


def test_distance_one_comparison_has_linear_character_access():
	"""Reject quadratic distance work without depending on machine timings."""
	class CountedText(str):
		accessed = 0

		def __getitem__(self, index):
			if isinstance(index, slice):
				self.accessed += len(range(*index.indices(len(self))))
			else:
				self.accessed += 1
			return super().__getitem__(index)

	left = CountedText('a' * 499 + 'b')
	right = CountedText('a' * 499 + 'c')
	assert OutputSearchManager._within_one_edit(left, right) is True
	assert left.accessed + right.accessed <= 5000


def test_fuzzy_cap_keeps_absolute_line_numbers_and_fallback_offsets():
	manager = OutputSearchManager(Terminal('prefix\n' + '\n'.join(['an erro'] * 1005)))
	assert manager.search('error') == 1000
	matches = manager._get_search_state()['matches']
	assert matches[0][2:] == (2, None, 0)
	assert matches[-1][2:] == (1001, None, 0)
