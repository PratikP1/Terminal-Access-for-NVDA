//! Terminal text search functionality.
//!
//! Port of the text-matching logic from `OutputSearchManager.search()`
//! in `terminalAccess.py` (lines 4386-4398). The Python side continues
//! handling TextInfo bookmark collection; this module only handles the
//! pure text search: finding matching line indices and character offsets.

use crate::ansi_strip;
use regex::RegexBuilder;

/// A single search match result.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SearchMatch {
    /// 0-based line index in the text.
    pub line_index: u32,
    /// Character offset within the line where the match starts.
    pub char_offset: u32,
    /// The full text of the matching line.
    pub line_text: String,
}

/// Search error types.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SearchError {
    /// The regex pattern is invalid.
    InvalidRegex(String),
}

/// Search for a pattern in terminal text.
///
/// The input text is first stripped of ANSI escape sequences, then split
/// into lines. Each line is checked for the pattern (literal or regex).
/// Returns a list of matches with line indices and character offsets.
///
/// # Arguments
/// * `text` - Full terminal text (may contain ANSI sequences)
/// * `pattern` - Search pattern (literal string or regex)
/// * `case_sensitive` - Whether the search is case-sensitive
/// * `use_regex` - Whether to interpret `pattern` as a regex
///
/// # Returns
/// A `Vec<SearchMatch>` with all matching lines, or a `SearchError`.
pub fn search_text(
    text: &str,
    pattern: &str,
    case_sensitive: bool,
    use_regex: bool,
) -> Result<Vec<SearchMatch>, SearchError> {
    // Strip ANSI codes from the full text
    let stripped = ansi_strip::strip_ansi(text);
    let lines: Vec<&str> = stripped.split('\n').collect();

    let mut matches = Vec::new();

    if use_regex {
        let re = RegexBuilder::new(pattern)
            .case_insensitive(!case_sensitive)
            .size_limit(10 * 1024 * 1024) // 10 MB limit to prevent ReDoS
            .build()
            .map_err(|e| SearchError::InvalidRegex(e.to_string()))?;

        for (i, line) in lines.iter().enumerate() {
            if let Some(m) = re.find(line) {
                matches.push(SearchMatch {
                    line_index: i as u32,
                    char_offset: line[..m.start()].chars().count() as u32,
                    line_text: line.to_string(),
                });
            }
        }
    } else {
        // Literal search — pre-normalize the pattern once for case-insensitive mode.
        let normalized_pattern = if case_sensitive { pattern.to_string() } else { pattern.to_lowercase() };
        let normalize_line: fn(&str) -> String = if case_sensitive {
            |l| l.to_string()
        } else {
            |l| l.to_lowercase()
        };

        for (i, line) in lines.iter().enumerate() {
            let haystack = normalize_line(line);
            if let Some(byte_offset) = haystack.find(&*normalized_pattern) {
                let char_offset = haystack[..byte_offset].chars().count() as u32;
                matches.push(SearchMatch {
                    line_index: i as u32,
                    char_offset,
                    line_text: line.to_string(),
                });
            }
        }
    }

    Ok(matches)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_pattern() {
        // Empty pattern matches every line (parity with Python: "" in line == True)
        let result = search_text("hello\nworld", "", false, false).unwrap();
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].line_index, 0);
        assert_eq!(result[1].line_index, 1);
    }

    #[test]
    fn test_literal_search_case_insensitive() {
        let result = search_text("Hello World\nFoo Bar\nHello Again", "hello", false, false).unwrap();
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].line_index, 0);
        assert_eq!(result[0].char_offset, 0);
        assert_eq!(result[1].line_index, 2);
    }

    #[test]
    fn test_literal_search_case_sensitive() {
        let result = search_text("Hello World\nFoo Bar\nhello again", "hello", true, false).unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].line_index, 2);
    }

    #[test]
    fn test_regex_search() {
        let result = search_text("error: something\nwarning: other\nerror: again", "^error:", false, true).unwrap();
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].line_index, 0);
        assert_eq!(result[1].line_index, 2);
    }

    #[test]
    fn test_invalid_regex() {
        let result = search_text("text", "[invalid", false, true);
        assert!(result.is_err());
        if let Err(SearchError::InvalidRegex(_)) = result {
            // Expected
        } else {
            panic!("Expected InvalidRegex error");
        }
    }

    #[test]
    fn test_ansi_stripped_before_search() {
        let text = "\x1b[31merror\x1b[0m: something failed\nnormal line";
        let result = search_text(text, "error", false, false).unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].line_index, 0);
        assert_eq!(result[0].char_offset, 0);
        // The line text should be ANSI-stripped
        assert_eq!(result[0].line_text, "error: something failed");
    }

    #[test]
    fn test_char_offset_with_unicode() {
        let text = "abc def\n\u{4f60}\u{597d} error here";
        let result = search_text(text, "error", false, false).unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].line_index, 1);
        // "\u{4f60}\u{597d} " = 3 characters
        assert_eq!(result[0].char_offset, 3);
    }

    #[test]
    fn test_no_matches() {
        let result = search_text("hello\nworld", "notfound", false, false).unwrap();
        assert!(result.is_empty());
    }

    #[test]
    fn test_multiple_matches_per_line_returns_first() {
        let result = search_text("error error error", "error", false, false).unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].char_offset, 0);
    }

    #[test]
    fn test_regex_case_insensitive() {
        let result = search_text("ERROR: test\nerror: test", "error:", false, true).unwrap();
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn test_regex_case_sensitive() {
        let result = search_text("ERROR: test\nerror: test", "error:", true, true).unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].line_index, 1);
    }
}
