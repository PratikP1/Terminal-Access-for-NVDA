# Tests for the Semantic Section Tokenizer.
# RED phase: these tests define the expected API before implementation.

import pytest
from lib.section_tokenizer import SectionTokenizer, Section, SectionSpan


# ---------------------------------------------------------------------------
# Realistic terminal output fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cargo_build_session():
    """A cargo build session with prompts, commands, errors, and warnings."""
    return [
        "user@dev:~/project$ cargo build",
        "   Compiling myproject v0.1.0 (/home/user/project)",
        "warning: unused variable: `x`",
        " --> src/main.rs:10:9",
        "  |",
        "10 |     let x = 42;",
        "  |         ^ help: if this is intentional, prefix it with an underscore: `_x`",
        "  |",
        "  = note: `#[warn(unused_variables)]` on by default",
        "",
        "error[E0382]: borrow of moved value: `data`",
        " --> src/main.rs:25:20",
        "  |",
        "23 |     let data = vec![1, 2, 3];",
        "  |         ---- move occurs because `data` has type `Vec<i32>`",
        "24 |     consume(data);",
        "25 |     println!(\"{:?}\", data);",
        "  |                    ^^^^ value borrowed here after move",
        "error: aborting due to 1 previous error; 1 warning emitted",
        "user@dev:~/project$ ",
    ]


@pytest.fixture
def pip_install_session():
    """A pip install session with progress bars and download indicators."""
    return [
        "$ pip install requests",
        "Collecting requests",
        "  Downloading requests-2.31.0-py3-none-any.whl (62 kB)",
        "     [=============================>           ] 45%",
        "     [========================================] 100%",
        "Collecting urllib3<3,>=1.21.1",
        "  Downloading urllib3-2.1.0-py3-none-any.whl (104 kB)",
        "     [========================================] 100%",
        "Installing collected packages: urllib3, requests",
        "Successfully installed requests-2.31.0 urllib3-2.1.0",
        "$ ",
    ]


@pytest.fixture
def python_traceback():
    """A Python traceback with file references and stack frames."""
    return [
        "$ python app.py",
        "Starting server...",
        "Traceback (most recent call last):",
        '  File "app.py", line 45, in main',
        "    result = process(data)",
        '  File "app.py", line 32, in process',
        "    return transform(data)",
        '  File "lib/transform.py", line 12, in transform',
        "    raise ValueError('Invalid input')",
        "ValueError: Invalid input",
        "$ ",
    ]


@pytest.fixture
def git_log_output():
    """A git log output with timestamps."""
    return [
        "$ git log --oneline --format='%aI %s'",
        "2024-01-15T10:30:45-05:00 Fix null pointer in parser",
        "2024-01-14T16:22:10-05:00 Add unit tests for tokenizer",
        "2024-01-13T09:15:00-05:00 Initial commit",
        "$ ",
    ]


@pytest.fixture
def kubectl_logs_output():
    """A kubectl logs output with JSON timestamps."""
    return [
        "$ kubectl logs my-pod",
        '{"timestamp":"2024-01-15T10:30:45Z","level":"INFO","msg":"Server started"}',
        '{"timestamp":"2024-01-15T10:30:46Z","level":"ERROR","msg":"Connection refused"}',
        '{"timestamp":"2024-01-15T10:30:47Z","level":"WARN","msg":"Retry attempt 1"}',
        "$ ",
    ]


@pytest.fixture
def mixed_session():
    """A mixed session with prompt, command, output, error, prompt, command, output."""
    return [
        "$ ls -la",
        "total 48",
        "drwxr-xr-x  5 user staff  160 Jan 15 10:30 .",
        "drwxr-xr-x  3 user staff   96 Jan 14 09:00 ..",
        "-rw-r--r--  1 user staff 1024 Jan 15 10:30 app.py",
        "$ cat missing.txt",
        "cat: missing.txt: No such file or directory",
        "$ echo done",
        "done",
        "$ ",
    ]


# ---------------------------------------------------------------------------
# Classification tests
# ---------------------------------------------------------------------------

class TestClassifyPrompt:
    """Tests for prompt line classification."""

    def test_classify_prompt_dollar(self):
        """Lines starting with '$ ' should be classified as prompt."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["$ ls -la"])
        assert sections[0].category == "prompt"

    def test_classify_prompt_ps(self):
        """Lines starting with 'PS C:\\>' should be classified as prompt."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["PS C:\\Users\\dev> Get-Process"])
        assert sections[0].category == "prompt"

    def test_classify_prompt_user_at_host(self):
        """Lines matching 'user@host:path$ ...' should be classified as prompt."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["user@dev:~/project$ cargo build"])
        assert sections[0].category == "prompt"

    def test_classify_prompt_chevron(self):
        """Lines starting with '> ' should be classified as prompt."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["> command"])
        assert sections[0].category == "prompt"

    def test_classify_prompt_hash_root(self):
        """Lines matching 'root@host:path# ...' should be classified as prompt."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["root@server:/var/log# tail syslog"])
        assert sections[0].category == "prompt"

    def test_classify_empty_prompt(self):
        """A bare prompt with no command should still be classified as prompt."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["$ "])
        assert sections[0].category == "prompt"


class TestClassifyError:
    """Tests for error line classification."""

    def test_classify_error_line(self):
        """Lines matching error patterns should be classified as error."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["error[E0382]: borrow of moved value: `data`"])
        assert sections[0].category == "error"

    def test_classify_error_aborting(self):
        """Error summary lines should be classified as error."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["error: aborting due to 1 previous error"])
        assert sections[0].category == "error"

    def test_classify_no_such_file(self):
        """Shell errors like 'No such file or directory' should be error."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["cat: missing.txt: No such file or directory"])
        assert sections[0].category == "error"


class TestClassifyWarning:
    """Tests for warning line classification."""

    def test_classify_warning_line(self):
        """Lines matching warning patterns should be classified as warning."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["warning: unused variable: `x`"])
        assert sections[0].category == "warning"


class TestClassifyStackTrace:
    """Tests for stack trace line classification."""

    def test_classify_stack_trace_python_file(self):
        """Python stack trace 'File ...' lines should be classified as stack_trace."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(['  File "app.py", line 45, in main'])
        assert sections[0].category == "stack_trace"

    def test_classify_stack_trace_traceback_header(self):
        """The 'Traceback (most recent call last):' line should be error (via ErrorLineDetector)."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["Traceback (most recent call last):"])
        # Traceback header is matched by ErrorLineDetector as error
        assert sections[0].category == "error"

    def test_classify_stack_trace_indented_code(self):
        """Indented code in a stack trace following a File line should be stack_trace."""
        tokenizer = SectionTokenizer()
        lines = [
            '  File "app.py", line 45, in main',
            "    result = process(data)",
        ]
        sections = tokenizer.tokenize(lines)
        assert sections[0].category == "stack_trace"
        assert sections[1].category == "stack_trace"

    def test_classify_stack_trace_at_keyword(self):
        """Java/JS style '  at ...' lines should be stack_trace."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["    at com.example.Main.run(Main.java:42)"])
        assert sections[0].category == "stack_trace"

    def test_classify_stack_trace_from_keyword(self):
        """Ruby/Rust style 'from ...' stack trace lines should be stack_trace."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["        from /usr/lib/ruby/main.rb:10:in `call'"])
        assert sections[0].category == "stack_trace"


class TestClassifyProgress:
    """Tests for progress indicator classification."""

    def test_classify_progress_bar(self):
        """Lines with '[===...] NN%' should be classified as progress."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["     [=============================>           ] 45%"])
        assert sections[0].category == "progress"

    def test_classify_progress_percentage(self):
        """Lines with standalone percentages should be classified as progress."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["Downloading... 73%"])
        assert sections[0].category == "progress"

    def test_classify_progress_downloading(self):
        """Lines containing 'Downloading' with size info should be progress."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["  Downloading requests-2.31.0-py3-none-any.whl (62 kB)"])
        assert sections[0].category == "progress"

    def test_classify_progress_spinner(self):
        """Lines with spinner characters should be classified as progress."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["/ Loading modules..."])
        assert sections[0].category == "progress"


class TestClassifyTimestamp:
    """Tests for timestamp line classification."""

    def test_classify_timestamp_iso(self):
        """Lines starting with ISO timestamps should be classified as timestamp."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["2024-01-15T10:30:45Z INFO Starting server"])
        assert sections[0].category == "timestamp"

    def test_classify_timestamp_with_offset(self):
        """Lines with ISO timestamps with timezone offset should be timestamp."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["2024-01-15T10:30:45-05:00 Fix null pointer in parser"])
        assert sections[0].category == "timestamp"

    def test_classify_timestamp_bracketed(self):
        """Lines with bracketed timestamps should be classified as timestamp."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["[2024-01-15 10:30:45] Server started on port 8080"])
        assert sections[0].category == "timestamp"


class TestClassifyHeading:
    """Tests for heading/separator line classification."""

    def test_classify_heading_equals(self):
        """Lines of '=====' should be classified as heading."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["====== RESULTS ======"])
        assert sections[0].category == "heading"

    def test_classify_heading_dashes(self):
        """Lines of '-----' should be classified as heading."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["----------------------------------------"])
        assert sections[0].category == "heading"

    def test_classify_heading_all_caps(self):
        """Lines in ALL CAPS with 3+ words should be classified as heading."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["TEST RESULTS SUMMARY"])
        assert sections[0].category == "heading"


class TestClassifyOutput:
    """Tests for normal output classification."""

    def test_classify_normal_output(self):
        """Regular text should be classified as output."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["total 48"])
        assert sections[0].category == "output"

    def test_classify_blank_line(self):
        """Blank lines should be classified as output."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize([""])
        assert sections[0].category == "output"


# ---------------------------------------------------------------------------
# Section grouping and span tests
# ---------------------------------------------------------------------------

class TestSectionGrouping:
    """Tests for grouping consecutive same-type lines into spans."""

    def test_section_grouping(self, mixed_session):
        """Consecutive same-type lines should be grouped into spans."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(mixed_session)
        spans = tokenizer.get_spans()
        # The first span should be a prompt (line 0: "$ ls -la")
        assert spans[0].category == "prompt"
        assert spans[0].start_line == 0
        assert spans[0].end_line == 0
        # The next span should be output (lines 1-4: "total 48" and dir listings)
        assert spans[1].category == "output"
        assert spans[1].start_line == 1
        assert spans[1].end_line == 4

    def test_section_spans(self, cargo_build_session):
        """Verify span start/end line numbers for a cargo build session."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(cargo_build_session)
        spans = tokenizer.get_spans()
        # First span: prompt at line 0
        assert spans[0].category == "prompt"
        assert spans[0].start_line == 0
        assert spans[0].end_line == 0
        # Verify we have multiple spans covering all lines
        assert spans[-1].end_line == len(cargo_build_session) - 1


# ---------------------------------------------------------------------------
# Navigation tests
# ---------------------------------------------------------------------------

class TestNavigation:
    """Tests for section navigation (next/prev)."""

    def test_next_section(self, mixed_session):
        """next_section should jump to the start of the next different section."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(mixed_session)
        # From line 0 (prompt), next section should be line 1 (output)
        result = tokenizer.next_section(0)
        assert result is not None
        assert result.line_num == 1

    def test_prev_section(self, mixed_session):
        """prev_section should jump to the start of the previous different section."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(mixed_session)
        # From line 2 (output), prev section should be line 0 (prompt)
        result = tokenizer.prev_section(2)
        assert result is not None
        assert result.line_num == 0

    def test_next_section_with_filter(self, cargo_build_session):
        """next_section with a category filter should jump to the next section of that type."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(cargo_build_session)
        # From line 0, find next error section
        result = tokenizer.next_section(0, category="error")
        assert result is not None
        assert result.category == "error"

    def test_next_section_at_end_returns_none(self, mixed_session):
        """next_section at the last line should return None."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(mixed_session)
        last = len(mixed_session) - 1
        result = tokenizer.next_section(last)
        assert result is None

    def test_prev_section_at_start_returns_none(self, mixed_session):
        """prev_section at line 0 should return None."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(mixed_session)
        result = tokenizer.prev_section(0)
        assert result is None


class TestErrorNavigation:
    """Tests for error/warning navigation convenience methods."""

    def test_next_error(self, cargo_build_session):
        """next_error should jump to the next error or warning line."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(cargo_build_session)
        result = tokenizer.next_error(0)
        assert result is not None
        assert result.category in ("error", "warning")

    def test_prev_error(self, cargo_build_session):
        """prev_error should jump to the previous error or warning line."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(cargo_build_session)
        # Jump from the last line backward
        result = tokenizer.prev_error(len(cargo_build_session) - 1)
        assert result is not None
        assert result.category in ("error", "warning")

    def test_next_error_returns_none_when_no_errors(self):
        """next_error should return None when there are no error lines."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(["$ ls", "file1.txt", "file2.txt", "$ "])
        result = tokenizer.next_error(0)
        assert result is None


class TestPromptNavigation:
    """Tests for prompt navigation convenience methods."""

    def test_next_prompt(self, mixed_session):
        """next_prompt should jump to the next prompt line."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(mixed_session)
        # From line 0, next prompt should be the second prompt
        result = tokenizer.next_prompt(0)
        assert result is not None
        assert result.category == "prompt"
        assert result.line_num > 0

    def test_prev_prompt(self, mixed_session):
        """prev_prompt should jump to the previous prompt line."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(mixed_session)
        # From the last line, previous prompt should be before it
        result = tokenizer.prev_prompt(len(mixed_session) - 1)
        assert result is not None
        assert result.category == "prompt"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_buffer(self):
        """Empty input should return an empty list of sections."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize([])
        assert sections == []

    def test_single_line(self):
        """A single line should produce a single section."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["$ echo hello"])
        assert len(sections) == 1
        assert sections[0].category == "prompt"

    def test_section_namedtuple_fields(self):
        """Section namedtuple should have line_num, category, and text fields."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(["hello world"])
        section = sections[0]
        assert hasattr(section, "line_num")
        assert hasattr(section, "category")
        assert hasattr(section, "text")
        assert section.line_num == 0
        assert section.text == "hello world"

    def test_span_namedtuple_fields(self):
        """SectionSpan namedtuple should have start_line, end_line, and category."""
        tokenizer = SectionTokenizer()
        tokenizer.tokenize(["hello", "world"])
        spans = tokenizer.get_spans()
        span = spans[0]
        assert hasattr(span, "start_line")
        assert hasattr(span, "end_line")
        assert hasattr(span, "category")


# ---------------------------------------------------------------------------
# Full session integration tests
# ---------------------------------------------------------------------------

class TestFullSession:
    """Integration tests with realistic multi-section sessions."""

    def test_pip_install_has_progress(self, pip_install_session):
        """A pip install session should contain progress sections."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(pip_install_session)
        categories = {s.category for s in sections}
        assert "progress" in categories
        assert "prompt" in categories

    def test_python_traceback_has_stack_trace(self, python_traceback):
        """A Python traceback should contain stack_trace sections."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(python_traceback)
        categories = {s.category for s in sections}
        assert "stack_trace" in categories
        assert "error" in categories

    def test_git_log_has_timestamps(self, git_log_output):
        """A git log output should contain timestamp sections."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(git_log_output)
        categories = {s.category for s in sections}
        assert "timestamp" in categories

    def test_kubectl_has_errors_and_warnings(self, kubectl_logs_output):
        """Kubectl logs with JSON should detect errors and warnings."""
        tokenizer = SectionTokenizer()
        sections = tokenizer.tokenize(kubectl_logs_output)
        categories = {s.category for s in sections}
        assert "error" in categories or "warning" in categories
