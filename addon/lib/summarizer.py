# Extractive summarizer for terminal output.
# Pure Python, offline only. Scores lines by heuristics and returns
# the top N in original order.

import re
from typing import List

from lib.text_processing import ANSIParser, ErrorLineDetector
from lib.section_tokenizer import SectionTokenizer


class OutputSummarizer:
    """Extract the most important lines from terminal output.

    Scoring heuristics (no ML, no network):
    - Lines containing errors/warnings score highest (via ErrorLineDetector)
    - Lines containing URLs score high
    - Lines that are headings or section boundaries score high
    - Lines with numbers/statistics score medium
    - Progress bars and blank lines score zero
    - First and last non-blank lines get a bonus for context
    """

    # URL pattern for scoring
    _URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)

    # Heading patterns (separator lines, ALL CAPS headers)
    _HEADING_PATTERNS = [
        re.compile(r'^[\s]*[=]{5,}[\s\w]*[=]*$'),
        re.compile(r'^[\s]*[-]{5,}[\s]*$'),
        re.compile(r'^[A-Z][A-Z ]{4,}$'),
    ]

    # Progress bar patterns (score zero)
    _PROGRESS_PATTERNS = [
        re.compile(r'\[[\s=>#\-]+\]\s*\d+%'),
        re.compile(r'\b\d{1,3}%\s*$'),
        re.compile(r'^\s*Downloading\s+\S+', re.IGNORECASE),
    ]

    # Lines with numbers/statistics
    _STAT_PATTERN = re.compile(r'\b\d+\b')

    def summarize_lines(self, lines: List[str], max_sentences: int = 5) -> List[str]:
        """Extract the most important lines from terminal output.

        Args:
            lines: List of terminal output lines (may contain ANSI codes).
            max_sentences: Maximum number of lines to return.

        Returns:
            List of the top-scoring lines, in their original order,
            with ANSI codes stripped.
        """
        if not lines:
            return []

        # Strip ANSI from all lines first
        cleaned = [ANSIParser.stripANSI(line) for line in lines]

        # Find first and last non-blank indices
        first_nonblank = None
        last_nonblank = None
        for i, line in enumerate(cleaned):
            if line.strip():
                if first_nonblank is None:
                    first_nonblank = i
                last_nonblank = i

        # If all lines are blank, return empty
        if first_nonblank is None:
            return []

        # Score each line
        scored = []
        for i, line in enumerate(cleaned):
            score = self._score_line(line)

            # First/last non-blank bonus
            if i == first_nonblank:
                score += 3
            if i == last_nonblank and last_nonblank != first_nonblank:
                score += 3

            scored.append((i, score, line))

        # Filter out zero-score lines
        nonzero = [(i, score, line) for i, score, line in scored if score > 0]

        if not nonzero:
            return []

        # Sort by score descending, then by original index ascending for ties
        nonzero.sort(key=lambda x: (-x[1], x[0]))

        # Take top N
        top = nonzero[:max_sentences]

        # Return in original order
        top.sort(key=lambda x: x[0])

        return [line for _, _, line in top]

    def _score_line(self, line: str) -> int:
        """Score a single line for importance.

        Args:
            line: A line of text (already ANSI-stripped).

        Returns:
            Integer score (higher means more important). Zero means
            the line should be excluded from summaries.
        """
        # Blank lines score zero
        if not line.strip():
            return 0

        # Progress bars score zero
        for pat in self._PROGRESS_PATTERNS:
            if pat.search(line):
                return 0

        score = 1  # Base score for non-blank, non-progress lines

        # Error/warning detection (highest priority)
        classification = ErrorLineDetector.classify(line)
        if classification == 'error':
            score += 10
        elif classification == 'warning':
            score += 7

        # URL detection
        if self._URL_PATTERN.search(line):
            score += 5

        # Heading detection
        for pat in self._HEADING_PATTERNS:
            if pat.search(line):
                score += 5
                break

        # Numbers/statistics (mild boost)
        if self._STAT_PATTERN.search(line):
            score += 1

        return score

    @staticmethod
    def get_disabled_message() -> str:
        """Return the message to announce when summarization is disabled."""
        try:
            return _("Summarization is disabled. Enable in Terminal Access settings.")
        except NameError:
            return "Summarization is disabled. Enable in Terminal Access settings."
