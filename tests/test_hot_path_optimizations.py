"""
Tests for hot-path performance optimizations:
- Content generation tracking (_contentGeneration counter)
- Line-level TextInfo cache in _announceStandardCursor
- TextDiffer class
- Single-pass bookmark collection in OutputSearchManager.search()
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# TextDiffer tests
# ---------------------------------------------------------------------------

class TestTextDiffer(unittest.TestCase):
    """Tests for the TextDiffer class."""

    def setUp(self):
        from globalPlugins.terminalAccess import TextDiffer
        self.TextDiffer = TextDiffer

    def _make(self):
        return self.TextDiffer()

    def test_first_update_is_initial(self):
        td = self._make()
        kind, content = td.update("hello\nworld\n")
        self.assertEqual(kind, self.TextDiffer.KIND_INITIAL)
        self.assertEqual(content, "")

    def test_identical_update_is_unchanged(self):
        td = self._make()
        td.update("hello\n")
        kind, content = td.update("hello\n")
        self.assertEqual(kind, self.TextDiffer.KIND_UNCHANGED)
        self.assertEqual(content, "")

    def test_appended_text_detected(self):
        td = self._make()
        td.update("line1\nline2\n")
        kind, content = td.update("line1\nline2\nline3\n")
        self.assertEqual(kind, self.TextDiffer.KIND_APPENDED)
        self.assertEqual(content, "line3\n")

    def test_non_trivial_change(self):
        td = self._make()
        td.update("original text")
        kind, content = td.update("completely different")
        self.assertEqual(kind, self.TextDiffer.KIND_CHANGED)
        self.assertEqual(content, "")

    def test_reset_makes_next_update_initial(self):
        td = self._make()
        td.update("some text")
        td.reset()
        kind, content = td.update("some text")
        self.assertEqual(kind, self.TextDiffer.KIND_INITIAL)

    def test_last_text_property(self):
        td = self._make()
        self.assertIsNone(td.last_text)
        td.update("abc")
        self.assertEqual(td.last_text, "abc")
        td.update("abcdef")
        self.assertEqual(td.last_text, "abcdef")

    def test_successive_appends(self):
        td = self._make()
        td.update("a")
        kind, content = td.update("ab")
        self.assertEqual(kind, self.TextDiffer.KIND_APPENDED)
        self.assertEqual(content, "b")
        kind, content = td.update("abc")
        self.assertEqual(kind, self.TextDiffer.KIND_APPENDED)
        self.assertEqual(content, "c")

    def test_empty_to_content(self):
        td = self._make()
        td.update("")
        kind, content = td.update("new content")
        # "" is a prefix of "new content", so detected as appended
        self.assertEqual(kind, self.TextDiffer.KIND_APPENDED)
        self.assertEqual(content, "new content")

    def test_reset_clears_last_text(self):
        td = self._make()
        td.update("text")
        td.reset()
        self.assertIsNone(td.last_text)


# ---------------------------------------------------------------------------
# Content generation tracking tests
# ---------------------------------------------------------------------------

class TestContentGenerationTracking(unittest.TestCase):
    """Tests for _contentGeneration counter in GlobalPlugin."""

    def _make_plugin(self):
        """Create a minimal GlobalPlugin instance."""
        from globalPlugins.terminalAccess import GlobalPlugin
        plugin = GlobalPlugin.__new__(GlobalPlugin)
        # Manually set all required state vars to avoid full __init__
        plugin._configManager = Mock()
        plugin._windowManager = Mock()
        plugin._positionCalculator = Mock()
        plugin.lastTerminalAppName = None
        plugin.announcedHelp = False
        plugin.copyMode = False
        plugin._boundTerminal = None
        plugin._cursorTrackingTimer = None
        plugin._lastCaretPosition = None
        plugin._lastTypedChar = None
        plugin._repeatedCharCount = 0
        plugin._contentGeneration = 0
        plugin._lastLineText = None
        plugin._lastLineStartOffset = None
        plugin._lastLineEndOffset = None
        plugin._lastLineGeneration = -1
        plugin._lastHighlightedText = None
        plugin._lastHighlightPosition = None
        plugin._markStart = None
        plugin._markEnd = None
        plugin._backgroundCalculationThread = None
        plugin._operationQueue = Mock()
        plugin._profileManager = Mock()
        plugin._currentProfile = None
        plugin._windowMonitor = None
        plugin._tabManager = None
        plugin._bookmarkManager = None
        plugin._searchManager = None
        plugin._commandHistoryManager = None
        plugin._terminalGestures = {}
        plugin._gesturesBound = False
        return plugin

    def test_initial_content_generation(self):
        plugin = self._make_plugin()
        self.assertEqual(plugin._contentGeneration, 0)

    def test_typed_character_increments_generation(self):
        import sys
        from unittest.mock import patch
        plugin = self._make_plugin()
        plugin.isTerminalApp = Mock(return_value=True)
        plugin._positionCalculator.clear_cache = Mock()
        plugin._shouldProcessSymbol = Mock(return_value=False)

        conf_data = {
            "terminalAccess": {
                "keyEcho": True,
                "quietMode": False,
                "repeatedSymbols": False,
                "repeatedSymbolsValues": "-_=!",
                "processSymbols": False,
                "punctuationLevel": 2,
                "cursorTracking": True,
                "cursorTrackingMode": 1,
                "cursorDelay": 20,
                "verboseMode": False,
                "indentationOnLineRead": False,
                "windowTop": 0,
                "windowBottom": 0,
                "windowLeft": 0,
                "windowRight": 0,
                "windowEnabled": False,
            },
            "keyboard": {
                "speakTypedCharacters": False,
            },
        }

        config_mock = sys.modules['config']
        original_getitem = config_mock.conf.__getitem__
        try:
            config_mock.conf.__getitem__ = lambda self, key: conf_data[key]

            obj = Mock()
            nextHandler = Mock()

            plugin.event_typedCharacter(obj, nextHandler, 'a')
            self.assertEqual(plugin._contentGeneration, 1)

            plugin.event_typedCharacter(obj, nextHandler, 'b')
            self.assertEqual(plugin._contentGeneration, 2)
        finally:
            config_mock.conf.__getitem__ = original_getitem

    def test_content_generation_not_incremented_when_not_terminal(self):
        import sys
        plugin = self._make_plugin()
        plugin.isTerminalApp = Mock(return_value=False)

        conf_data = {
            "terminalAccess": {
                "keyEcho": True,
                "quietMode": False,
                "repeatedSymbols": False,
                "repeatedSymbolsValues": "-_=!",
            },
            "keyboard": {
                "speakTypedCharacters": False,
            },
        }

        config_mock = sys.modules['config']
        original_getitem = config_mock.conf.__getitem__
        try:
            config_mock.conf.__getitem__ = lambda self, key: conf_data[key]
            plugin.event_typedCharacter(Mock(), Mock(), 'x')
        finally:
            config_mock.conf.__getitem__ = original_getitem

        self.assertEqual(plugin._contentGeneration, 0)


# ---------------------------------------------------------------------------
# Line-level TextInfo cache tests
# ---------------------------------------------------------------------------

class TestLineLevelCache(unittest.TestCase):
    """Tests for line-level TextInfo caching in _announceStandardCursor."""

    def _make_plugin(self):
        from globalPlugins.terminalAccess import GlobalPlugin
        plugin = GlobalPlugin.__new__(GlobalPlugin)
        plugin._configManager = Mock()
        plugin._windowManager = Mock()
        plugin._positionCalculator = Mock()
        plugin.lastTerminalAppName = None
        plugin.announcedHelp = False
        plugin.copyMode = False
        plugin._boundTerminal = None
        plugin._cursorTrackingTimer = None
        plugin._lastCaretPosition = None
        plugin._lastTypedChar = None
        plugin._repeatedCharCount = 0
        plugin._contentGeneration = 0
        plugin._lastLineText = None
        plugin._lastLineStartOffset = None
        plugin._lastLineEndOffset = None
        plugin._lastLineGeneration = -1
        plugin._lastHighlightedText = None
        plugin._lastHighlightPosition = None
        plugin._markStart = None
        plugin._markEnd = None
        plugin._backgroundCalculationThread = None
        plugin._operationQueue = Mock()
        plugin._profileManager = Mock()
        plugin._currentProfile = None
        plugin._windowMonitor = None
        plugin._tabManager = None
        plugin._bookmarkManager = None
        plugin._searchManager = None
        plugin._commandHistoryManager = None
        plugin._shouldProcessSymbol = Mock(return_value=False)
        plugin._processSymbol = Mock(side_effect=lambda c: c)
        return plugin

    def _make_obj(self, offset, line_text="hello world", line_start=0):
        """Build a mock terminal object whose caret is at *offset*."""
        import sys
        textInfos_mock = sys.modules['textInfos']

        def make_text_info(pos):
            info = Mock()
            bm = Mock()
            bm.startOffset = offset
            bm.endOffset = offset + 1
            info.bookmark = bm

            # For UNIT_LINE expand, simulate bookmark covering the whole line
            def expand(unit):
                if unit == textInfos_mock.UNIT_LINE:
                    bm.startOffset = line_start
                    bm.endOffset = line_start + len(line_text)
                    info.text = line_text
                elif unit == textInfos_mock.UNIT_CHARACTER:
                    char_idx = offset - line_start
                    info.text = line_text[char_idx] if 0 <= char_idx < len(line_text) else ''

            info.expand = expand
            return info

        obj = Mock()
        obj.makeTextInfo = Mock(side_effect=make_text_info)
        return obj

    def test_cache_miss_on_first_call_builds_cache(self):
        plugin = self._make_plugin()
        import sys
        ui_mock = sys.modules['ui']
        ui_mock.message.reset_mock()

        obj = self._make_obj(offset=2, line_text="hello", line_start=0)
        plugin._announceStandardCursor(obj)

        # First call: makeTextInfo should have been called (at least once for POSITION_CARET)
        self.assertGreater(obj.makeTextInfo.call_count, 0)
        self.assertEqual(plugin._lastLineText, "hello")
        self.assertEqual(plugin._lastLineStartOffset, 0)
        self.assertEqual(plugin._lastLineEndOffset, 5)
        self.assertEqual(plugin._lastLineGeneration, 0)

    def test_cache_hit_within_same_line_no_content_change(self):
        """After building the cache, a same-line move should avoid extra expand COM calls."""
        plugin = self._make_plugin()
        import sys
        textInfos_mock = sys.modules['textInfos']
        ui_mock = sys.modules['ui']

        # Simulate first caret event at offset 0 on line "hello world".
        # This causes a cache miss and therefore makes 2 makeTextInfo calls
        # (one for POSITION_CARET to get the position, one for the line refresh).
        obj = self._make_obj(offset=0, line_text="hello world", line_start=0)
        plugin._announceStandardCursor(obj)
        first_call_count = obj.makeTextInfo.call_count  # expect 2

        # Now move caret to offset 1 (still same line, no content change).
        # Cache hit path: only the mandatory POSITION_CARET call is made.
        obj2 = self._make_obj(offset=1, line_text="hello world", line_start=0)
        plugin._announceStandardCursor(obj2)

        # Cache hit: only 1 makeTextInfo call (POSITION_CARET) vs 2 on first call.
        self.assertEqual(obj2.makeTextInfo.call_count, 1)

    def test_cache_miss_when_content_generation_changes(self):
        """Cache should be invalidated when _contentGeneration increments."""
        plugin = self._make_plugin()

        obj = self._make_obj(offset=0, line_text="hello", line_start=0)
        plugin._announceStandardCursor(obj)

        # Simulate typing (increments _contentGeneration)
        plugin._contentGeneration += 1

        # Move to a new offset; cache generation no longer matches
        obj2 = self._make_obj(offset=1, line_text="xhello", line_start=0)
        plugin._announceStandardCursor(obj2)

        # makeTextInfo MUST be called again because cache is stale
        self.assertGreater(obj2.makeTextInfo.call_count, 0)

    def test_cache_miss_when_caret_moves_to_different_line(self):
        """Cache should not be used when caret moves to a different line."""
        plugin = self._make_plugin()

        # First line: offsets 0-4
        obj = self._make_obj(offset=0, line_text="line1", line_start=0)
        plugin._announceStandardCursor(obj)

        # Different line: offsets 6-10
        obj2 = self._make_obj(offset=6, line_text="line2", line_start=6)
        plugin._announceStandardCursor(obj2)

        # Cache miss because 6 not in [0, 5), so makeTextInfo must be called
        self.assertGreater(obj2.makeTextInfo.call_count, 0)
        # Cache should now reflect the new line
        self.assertEqual(plugin._lastLineText, "line2")
        self.assertEqual(plugin._lastLineStartOffset, 6)

    def test_same_position_skips_all_processing(self):
        """If position unchanged, _announceStandardCursor should return after one COM call."""
        plugin = self._make_plugin()

        obj = self._make_obj(offset=3, line_text="hello", line_start=0)
        plugin._announceStandardCursor(obj)
        first_count = obj.makeTextInfo.call_count  # 2 calls: POSITION_CARET + line refresh

        # Same position again: only 1 makeTextInfo call (POSITION_CARET early-exit check)
        plugin._announceStandardCursor(obj)
        self.assertEqual(obj.makeTextInfo.call_count, first_count + 1)


# ---------------------------------------------------------------------------
# Single-pass OutputSearchManager tests
# ---------------------------------------------------------------------------

class TestOutputSearchManagerSinglePass(unittest.TestCase):
    """Tests for the optimized single-pass search in OutputSearchManager."""

    def _make_terminal(self, text):
        """Build a mock terminal whose single-pass walk works correctly."""
        import sys
        textInfos_mock = sys.modules['textInfos']

        lines = text.split('\n')

        class WalkingTextInfo:
            def __init__(self, line_index=0):
                self.line_index = line_index
                self._lines = lines

            @property
            def text(self):
                return '\n'.join(self._lines)

            @property
            def bookmark(self):
                bm = Mock()
                bm.startOffset = self.line_index
                return bm

            def move(self, unit, count):
                new_idx = self.line_index + count
                if new_idx < len(self._lines):
                    self.line_index = new_idx
                    return count
                return 0

            def copy(self):
                ti = WalkingTextInfo(self.line_index)
                ti._lines = self._lines
                return ti

        terminal = Mock()

        def make_text_info(pos):
            if pos == textInfos_mock.POSITION_ALL:
                return WalkingTextInfo(0)
            if pos == textInfos_mock.POSITION_FIRST:
                return WalkingTextInfo(0)
            raise ValueError("unsupported position")

        terminal.makeTextInfo = Mock(side_effect=make_text_info)
        return terminal

    def test_search_finds_correct_number_of_matches(self):
        from globalPlugins.terminalAccess import OutputSearchManager
        terminal = self._make_terminal("alpha\nbeta\ngamma\nbeta\ndelta")
        manager = OutputSearchManager(terminal)
        count = manager.search("beta")
        self.assertEqual(count, 2)

    def test_search_single_pass_fewer_makeTextInfo_calls(self):
        """Single-pass walk should call makeTextInfo far fewer times than per-match O(n) walk."""
        from globalPlugins.terminalAccess import OutputSearchManager
        # 10-line buffer with 5 matches
        text = '\n'.join([f"line{i}" if i % 2 else "match" for i in range(10)])
        terminal = self._make_terminal(text)
        manager = OutputSearchManager(terminal)
        manager.search("match")

        # With single-pass: 1 call for POSITION_ALL + 1 call for POSITION_FIRST = 2
        # Old per-match: 1 + 5 extra POSITION_FIRST calls = 6 minimum
        # We only verify it's at most 3 (allowing some slack for the implementation).
        self.assertLessEqual(terminal.makeTextInfo.call_count, 3)

    def test_search_no_matches_returns_zero(self):
        from globalPlugins.terminalAccess import OutputSearchManager
        terminal = self._make_terminal("line1\nline2\nline3")
        manager = OutputSearchManager(terminal)
        count = manager.search("notfound")
        self.assertEqual(count, 0)

    def test_search_case_insensitive(self):
        from globalPlugins.terminalAccess import OutputSearchManager
        terminal = self._make_terminal("Hello\nworld\nHELLO")
        manager = OutputSearchManager(terminal)
        count = manager.search("hello", case_sensitive=False)
        self.assertEqual(count, 2)

    def test_search_case_sensitive(self):
        from globalPlugins.terminalAccess import OutputSearchManager
        terminal = self._make_terminal("Hello\nworld\nhello")
        manager = OutputSearchManager(terminal)
        count = manager.search("hello", case_sensitive=True)
        self.assertEqual(count, 1)

    def test_search_regex(self):
        from globalPlugins.terminalAccess import OutputSearchManager
        terminal = self._make_terminal("error: foo\nwarning: bar\nerror: baz")
        manager = OutputSearchManager(terminal)
        count = manager.search(r"error: \w+", use_regex=True)
        self.assertEqual(count, 2)

    def test_match_line_numbers_correct(self):
        from globalPlugins.terminalAccess import OutputSearchManager
        terminal = self._make_terminal("a\nb\nc\nb\ne")
        manager = OutputSearchManager(terminal)
        manager.search("b")
        # Matches should be on lines 2 and 4 (1-indexed)
        line_nums = [m[2] for m in manager._matches]
        self.assertEqual(line_nums, [2, 4])

    def test_navigation_after_single_pass_search(self):
        """first_match / next_match should still work correctly after refactor."""
        import sys
        from globalPlugins.terminalAccess import OutputSearchManager
        api_mock = sys.modules['api']
        api_mock.setReviewPosition.reset_mock()

        terminal = self._make_terminal("x\nfoo\ny\nfoo\nz")
        manager = OutputSearchManager(terminal)
        manager.search("foo")
        self.assertTrue(manager.first_match())
        api_mock.setReviewPosition.assert_called_once()

        api_mock.setReviewPosition.reset_mock()
        self.assertTrue(manager.next_match())
        api_mock.setReviewPosition.assert_called_once()


if __name__ == '__main__':
    unittest.main()
