"""Tests for output search behavior."""

import api
import textInfos


def test_search_moves_review_without_bookmarks():
	"""Ensure search moves the review cursor even when bookmarks aren't supported."""
	textInfos.POSITION_ALL = "all"
	textInfos.POSITION_FIRST = "first"
	textInfos.UNIT_LINE = "line"

	from globalPlugins.terminalAccess import OutputSearchManager

	class DummyTextInfo:
		"""Minimal TextInfo replacement without bookmark support."""

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
		"""Terminal stub that cannot recreate positions from bookmarks."""

		def __init__(self, text):
			self.text = text

		def makeTextInfo(self, arg):
			if arg == textInfos.POSITION_ALL:
				return DummyTextInfo(self.text, 0)
			if arg == textInfos.POSITION_FIRST:
				return DummyTextInfo(self.text, 0)
			# Simulate bookmark-based retrieval not being supported
			raise ValueError("Bookmarks not supported")

	api.setReviewPosition.reset_mock()

	manager = OutputSearchManager(DummyTerminal("alpha\nbeta\ngamma"))

	assert manager.search("beta") == 1
	assert manager.first_match() is True
	api.setReviewPosition.assert_called_once()
	position = api.setReviewPosition.call_args[0][0]
	assert getattr(position, "line_index", None) == 1
	assert manager.get_current_match_info() == (1, 1, "beta", 2)
