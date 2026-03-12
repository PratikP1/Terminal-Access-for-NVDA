//! Text differ for detecting new terminal output.
//!
//! Port of the Python `TextDiffer` class from `terminalAccess.py` (lines 709-823).
//! Stores a snapshot of the last-known terminal text and compares it against
//! current text to identify newly appended content.

use regex::Regex;
use std::sync::OnceLock;

/// The kind of change detected by the differ.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u32)]
pub enum DiffKind {
    /// First snapshot — no previous state.
    Initial = 0,
    /// Text identical to last snapshot.
    Unchanged = 1,
    /// New text was appended after old text.
    Appended = 2,
    /// Non-trivial change (edit, clear, etc.).
    Changed = 3,
    /// Only the last line changed (progress bars, spinners).
    LastLineUpdated = 4,
}

/// Result of a diff operation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DiffResult {
    pub kind: DiffKind,
    pub content: String,
}

/// Lightweight text differ for detecting new terminal output.
///
/// The common case — output being appended to the end — is handled in O(n)
/// time, where n is the length of the new suffix. For edits in the middle
/// or full screen clears, the differ reports a "changed" state without
/// computing a detailed diff.
pub struct TextDiffer {
    last_text: Option<String>,
    last_len: usize,
}

/// Compiled regex for stripping trailing spaces per line.
/// conhost pads UNIT_LINE text to screen width with trailing spaces.
fn trailing_spaces_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m) +$").unwrap())
}

/// Strip trailing spaces from each line for padding-agnostic comparison.
fn normalize(text: &str) -> String {
    trailing_spaces_re().replace_all(text, "").into_owned()
}

impl TextDiffer {
    /// Create a new differ with no previous snapshot.
    pub fn new() -> Self {
        Self {
            last_text: None,
            last_len: 0,
        }
    }

    /// Compare `current_text` to the stored snapshot and return a diff result.
    ///
    /// Uses length pre-checks to avoid expensive full-string comparisons
    /// on the common unchanged and append cases.
    pub fn update(&mut self, current_text: &str) -> DiffResult {
        let current_text = normalize(current_text);
        let cur_len = current_text.len();

        let old = match &self.last_text {
            None => {
                self.last_text = Some(current_text);
                self.last_len = cur_len;
                return DiffResult {
                    kind: DiffKind::Initial,
                    content: String::new(),
                };
            }
            Some(old) => old,
        };

        let old_len = self.last_len;

        // Fast identity check: same length -> likely unchanged.
        if cur_len == old_len && current_text == *old {
            return DiffResult {
                kind: DiffKind::Unchanged,
                content: String::new(),
            };
        }

        // Fast append detection: new text is longer and starts with old text.
        if cur_len > old_len && current_text.starts_with(old.as_str()) {
            let appended = current_text[old_len..].to_string();
            self.last_text = Some(current_text);
            self.last_len = cur_len;
            return DiffResult {
                kind: DiffKind::Appended,
                content: appended,
            };
        }

        // Last-line overwrite detection: everything before the last newline is
        // identical, only the trailing content differs (progress bars, spinners).
        // Skip the expensive rpartition if the lengths differ dramatically.
        if cur_len.abs_diff(old_len) <= 500 {
            if let (Some(old_nl), Some(new_nl)) =
                (old.rfind('\n'), current_text.rfind('\n'))
            {
                let old_prefix = &old[..old_nl];
                let new_prefix = &current_text[..new_nl];
                if old_prefix == new_prefix {
                    let new_tail = current_text[new_nl + 1..].to_string();
                    self.last_text = Some(current_text);
                    self.last_len = cur_len;
                    return DiffResult {
                        kind: DiffKind::LastLineUpdated,
                        content: new_tail,
                    };
                }
            }
        }

        // Non-trivial change.
        self.last_text = Some(current_text);
        self.last_len = cur_len;
        DiffResult {
            kind: DiffKind::Changed,
            content: String::new(),
        }
    }

    /// Discard the stored snapshot so the next `update` is treated as initial.
    pub fn reset(&mut self) {
        self.last_text = None;
        self.last_len = 0;
    }

    /// The last snapshot text, or `None` if no snapshot has been taken.
    pub fn last_text(&self) -> Option<&str> {
        self.last_text.as_deref()
    }
}

impl Default for TextDiffer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial() {
        let mut differ = TextDiffer::new();
        let result = differ.update("hello\nworld\n");
        assert_eq!(result.kind, DiffKind::Initial);
        assert_eq!(result.content, "");
    }

    #[test]
    fn test_unchanged() {
        let mut differ = TextDiffer::new();
        differ.update("hello\nworld\n");
        let result = differ.update("hello\nworld\n");
        assert_eq!(result.kind, DiffKind::Unchanged);
        assert_eq!(result.content, "");
    }

    #[test]
    fn test_appended() {
        let mut differ = TextDiffer::new();
        differ.update("line1\nline2\n");
        let result = differ.update("line1\nline2\nline3\n");
        assert_eq!(result.kind, DiffKind::Appended);
        assert_eq!(result.content, "line3\n");
    }

    #[test]
    fn test_changed() {
        let mut differ = TextDiffer::new();
        differ.update("hello\nworld\n");
        let result = differ.update("completely different");
        assert_eq!(result.kind, DiffKind::Changed);
        assert_eq!(result.content, "");
    }

    #[test]
    fn test_last_line_updated() {
        let mut differ = TextDiffer::new();
        differ.update("line1\nline2\nprogress: 50%");
        let result = differ.update("line1\nline2\nprogress: 75%");
        assert_eq!(result.kind, DiffKind::LastLineUpdated);
        assert_eq!(result.content, "progress: 75%");
    }

    #[test]
    fn test_reset() {
        let mut differ = TextDiffer::new();
        differ.update("hello");
        differ.reset();
        assert!(differ.last_text().is_none());
        let result = differ.update("world");
        assert_eq!(result.kind, DiffKind::Initial);
    }

    #[test]
    fn test_trailing_spaces_normalized() {
        let mut differ = TextDiffer::new();
        differ.update("hello   \nworld   \n");
        // Same content with different trailing spaces should be unchanged
        let result = differ.update("hello\nworld\n");
        assert_eq!(result.kind, DiffKind::Unchanged);
    }

    #[test]
    fn test_empty_text() {
        let mut differ = TextDiffer::new();
        let result = differ.update("");
        assert_eq!(result.kind, DiffKind::Initial);
        let result = differ.update("");
        assert_eq!(result.kind, DiffKind::Unchanged);
    }

    #[test]
    fn test_append_single_char() {
        let mut differ = TextDiffer::new();
        differ.update("abc");
        let result = differ.update("abcd");
        assert_eq!(result.kind, DiffKind::Appended);
        assert_eq!(result.content, "d");
    }

    #[test]
    fn test_last_line_not_triggered_for_large_diff() {
        let mut differ = TextDiffer::new();
        let old = "a".repeat(1000) + "\nlast";
        differ.update(&old);
        // Change prefix significantly (> 500 chars difference)
        let new = "b".repeat(600) + "\nnew_last";
        let result = differ.update(&new);
        assert_eq!(result.kind, DiffKind::Changed);
    }

    #[test]
    fn test_last_text_property() {
        let mut differ = TextDiffer::new();
        assert!(differ.last_text().is_none());
        differ.update("hello");
        assert_eq!(differ.last_text(), Some("hello"));
    }

    #[test]
    fn test_multiple_appends() {
        let mut differ = TextDiffer::new();
        differ.update("line1\n");
        let r = differ.update("line1\nline2\n");
        assert_eq!(r.kind, DiffKind::Appended);
        assert_eq!(r.content, "line2\n");
        let r = differ.update("line1\nline2\nline3\n");
        assert_eq!(r.kind, DiffKind::Appended);
        assert_eq!(r.content, "line3\n");
    }

    #[test]
    fn test_unicode_text() {
        let mut differ = TextDiffer::new();
        differ.update("hello\n");
        let result = differ.update("hello\nworld\n");
        assert_eq!(result.kind, DiffKind::Appended);
        assert_eq!(result.content, "world\n");
    }

    #[test]
    fn test_cjk_text() {
        let mut differ = TextDiffer::new();
        differ.update("\u{4f60}\u{597d}\n");
        let result = differ.update("\u{4f60}\u{597d}\n\u{4e16}\u{754c}\n");
        assert_eq!(result.kind, DiffKind::Appended);
        assert_eq!(result.content, "\u{4e16}\u{754c}\n");
    }
}
