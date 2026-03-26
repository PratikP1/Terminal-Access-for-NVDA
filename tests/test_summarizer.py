"""Tests for the OutputSummarizer in lib/summarizer.py.

RED phase: all tests written before implementation exists.
"""
import sys
import pytest


class TestSummarizeEmpty:
    """test_summarize_empty_input: returns empty list for empty input."""

    def test_empty_list(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        assert s.summarize_lines([]) == []

    def test_none_like_input(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        assert s.summarize_lines([""]) == []


class TestSummarizeSingleLine:
    """test_summarize_single_line: a single non-blank line is returned as-is."""

    def test_single_line(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        result = s.summarize_lines(["hello world"])
        assert result == ["hello world"]

    def test_single_line_with_whitespace(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        result = s.summarize_lines(["  hello world  "])
        assert result == ["  hello world  "]


class TestSummarizeErrorLinesPrioritized:
    """test_summarize_error_lines_prioritized: error lines score highest."""

    def test_error_lines_included(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "Compiling project...",
            "src/main.rs:10: warning: unused variable",
            "src/main.rs:25: error: cannot find value",
            "Building dependencies...",
            "Linking...",
            "Some normal output here",
            "More normal output here",
            "Even more output",
        ]
        result = s.summarize_lines(lines, max_sentences=3)
        # Error and warning lines must appear in the result
        assert any("error:" in line for line in result)

    def test_warning_lines_included(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "Compiling project...",
            "src/main.rs:10: warning: unused variable",
            "Building dependencies...",
            "Linking...",
            "Some normal output here",
            "More normal output here",
            "Even more output",
            "Final output line",
        ]
        result = s.summarize_lines(lines, max_sentences=3)
        assert any("warning:" in line for line in result)


class TestSummarizeUrlLinesIncluded:
    """test_summarize_url_lines_included: lines with URLs score high."""

    def test_url_lines(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "Starting server...",
            "Loading config...",
            "Listening on http://localhost:3000",
            "Ready.",
            "Processing request 1...",
            "Processing request 2...",
            "Processing request 3...",
            "Processing request 4...",
        ]
        result = s.summarize_lines(lines, max_sentences=3)
        assert any("http://localhost:3000" in line for line in result)

    def test_https_url(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "Downloading...",
            "Fetching from https://example.com/api/v2",
            "Processing...",
            "Done.",
            "Cleanup...",
            "Extra line 1",
            "Extra line 2",
            "Extra line 3",
        ]
        result = s.summarize_lines(lines, max_sentences=3)
        assert any("https://example.com" in line for line in result)


class TestSummarizeHeadingLinesIncluded:
    """test_summarize_heading_lines_included: headings score high."""

    def test_separator_heading(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "some output",
            "=============================",
            "TEST RESULTS",
            "=============================",
            "passed: 10",
            "failed: 2",
            "extra line 1",
            "extra line 2",
        ]
        result = s.summarize_lines(lines, max_sentences=4)
        assert any("TEST RESULTS" in line for line in result)


class TestSummarizeProgressBarsExcluded:
    """test_summarize_progress_bars_excluded: progress indicators score zero."""

    def test_progress_bars_excluded(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "Starting download...",
            "[====>    ] 50%",
            "[======>  ] 75%",
            "[========>] 100%",
            "Download complete.",
        ]
        result = s.summarize_lines(lines, max_sentences=3)
        # Progress bar lines should not appear in the summary
        for line in result:
            assert "====>" not in line
            assert "======>" not in line


class TestSummarizeBlankLinesExcluded:
    """test_summarize_blank_lines_excluded: blank lines score zero."""

    def test_blank_lines_excluded(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "Line 1",
            "",
            "   ",
            "Line 4",
            "",
        ]
        result = s.summarize_lines(lines, max_sentences=5)
        for line in result:
            assert line.strip() != ""


class TestSummarizeFirstLastBonus:
    """test_summarize_first_last_bonus: first/last non-blank get a bonus."""

    def test_first_and_last_included(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "Build started at 10:00",
            "Compiling module A...",
            "Compiling module B...",
            "Compiling module C...",
            "Compiling module D...",
            "Compiling module E...",
            "Compiling module F...",
            "Build finished at 10:05",
        ]
        result = s.summarize_lines(lines, max_sentences=3)
        # First and last non-blank lines should appear due to bonus
        assert "Build started at 10:00" in result
        assert "Build finished at 10:05" in result


class TestSummarizeRespectsMaxSentences:
    """test_summarize_respects_max_sentences: at most max_sentences returned."""

    def test_max_sentences_limit(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [f"Line {i}" for i in range(20)]
        result = s.summarize_lines(lines, max_sentences=5)
        assert len(result) <= 5

    def test_max_sentences_default(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [f"Line {i}" for i in range(20)]
        result = s.summarize_lines(lines)
        assert len(result) <= 5

    def test_max_sentences_one(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = ["Line A", "Line B", "Line C"]
        result = s.summarize_lines(lines, max_sentences=1)
        assert len(result) == 1


class TestSummarizePreservesOrder:
    """test_summarize_preserves_order: results in original line order."""

    def test_order_preserved(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "First line of output",
            "error: something went wrong",
            "Middle content",
            "warning: check this",
            "Last line of output",
        ]
        result = s.summarize_lines(lines, max_sentences=5)
        # Get original indices of returned lines
        indices = [lines.index(r) for r in result]
        assert indices == sorted(indices)


class TestSummarizeStripsAnsi:
    """test_summarize_strips_ansi: ANSI codes removed from output."""

    def test_ansi_stripped(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "\x1b[31merror: bad input\x1b[0m",
            "\x1b[32mSuccess\x1b[0m",
        ]
        result = s.summarize_lines(lines, max_sentences=5)
        for line in result:
            assert "\x1b[" not in line

    def test_ansi_stripped_preserves_text(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "\x1b[1;31merror: compile failed\x1b[0m",
        ]
        result = s.summarize_lines(lines)
        assert any("error: compile failed" in line for line in result)


class TestSummarizeRealisticBuildOutput:
    """test_summarize_realistic_build_output: cargo build summary contains errors."""

    def test_cargo_build(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "   Compiling serde v1.0.160",
            "   Compiling tokio v1.28.0",
            "   Compiling my-project v0.1.0",
            "error[E0308]: mismatched types",
            "  --> src/main.rs:42:5",
            "   |",
            "42 |     let x: u32 = \"hello\";",
            "   |                  ^^^^^^^ expected `u32`, found `&str`",
            "",
            "error: aborting due to previous error",
            "",
            "For more information about this error, try `rustc --explain E0308`.",
        ]
        result = s.summarize_lines(lines, max_sentences=5)
        # Should include the main error lines
        assert any("mismatched types" in line for line in result)
        assert any("aborting" in line for line in result)


class TestSummarizeRealisticTestOutput:
    """test_summarize_realistic_test_output: pytest summary contains FAILED lines."""

    def test_pytest_output(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        lines = [
            "============================= test session starts ==============================",
            "collected 45 items",
            "",
            "tests/test_api.py .....",
            "tests/test_auth.py ..F..",
            "tests/test_models.py ........",
            "tests/test_views.py ...F...",
            "",
            "FAILED tests/test_auth.py::test_login_invalid",
            "FAILED tests/test_views.py::test_dashboard_access",
            "==================== 2 failed, 43 passed in 3.45s =============================",
        ]
        result = s.summarize_lines(lines, max_sentences=5)
        # FAILED lines must be in summary
        assert any("FAILED" in line for line in result)


class TestPrivacySettingExists:
    """test_privacy_setting_exists: confspec has summarizationEnabled."""

    def test_setting_in_confspec(self):
        from lib.config import confspec
        assert "summarizationEnabled" in confspec


class TestPrivacyDefaultFalse:
    """test_privacy_default_false: default is False."""

    def test_default_false(self):
        from lib.config import confspec
        spec_value = confspec["summarizationEnabled"]
        assert "default=False" in spec_value


class TestSummarizeDisabledAnnounces:
    """test_summarize_disabled_announces: disabled state gives message."""

    def test_disabled_message(self):
        from lib.summarizer import OutputSummarizer
        s = OutputSummarizer()
        msg = s.get_disabled_message()
        assert "disabled" in msg.lower() or "Disabled" in msg
        assert "enable" in msg.lower() or "Enable" in msg
