//! Unicode display-width utilities.
//!
//! Provides functions to compute the visual column width of characters
//! and strings, extract column ranges, and map column positions to
//! character indices. All column numbers are **1-based, inclusive**.

use unicode_width::UnicodeWidthChar;

/// Get display width of a single Unicode codepoint (0, 1, or 2 columns).
/// Control chars return 0.
pub fn char_width(c: char) -> u32 {
    UnicodeWidthChar::width(c).unwrap_or(0) as u32
}

/// Calculate total display width of a text string.
/// Returns the total columns. Control chars are 0-width.
///
/// We iterate char-by-char rather than using `UnicodeWidthStr::width`
/// directly because the latter returns `None` for strings containing
/// control characters. Per-char iteration gives robust results that
/// match the Python-side behaviour.
pub fn text_width(text: &str) -> u32 {
    text.chars().map(char_width).sum()
}

/// Extract text from a column range (1-based, inclusive), respecting
/// Unicode display widths.
///
/// `start_col` and `end_col` are 1-based inclusive column numbers.
/// Characters whose display span overlaps `[start_col, end_col]` are
/// included in the result.
pub fn extract_column_range(text: &str, start_col: u32, end_col: u32) -> String {
    let mut result = String::new();
    let mut current_col: u32 = 1;

    for ch in text.chars() {
        let w = char_width(ch);
        let char_end_col = current_col + w.saturating_sub(1);

        if char_end_col < start_col {
            // entirely before the range
        } else if current_col > end_col {
            break;
        } else {
            result.push(ch);
        }

        current_col += w;
    }

    result
}

/// Find the character index that corresponds to a target column
/// position (1-based).
///
/// Returns the 0-based char index for the character at or past
/// `target_col`. If `target_col` is beyond the string, returns the
/// total number of characters.
pub fn find_column_position(text: &str, target_col: u32) -> u32 {
    let mut current_col: u32 = 1;

    for (i, ch) in text.chars().enumerate() {
        if current_col >= target_col {
            return i as u32;
        }
        current_col += char_width(ch);
    }

    text.chars().count() as u32
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_char_width_ascii() {
        assert_eq!(char_width('A'), 1);
    }

    #[test]
    fn test_char_width_cjk() {
        assert_eq!(char_width('\u{4E2D}'), 2); // '中'
    }

    #[test]
    fn test_char_width_combining() {
        // U+0301 COMBINING ACUTE ACCENT
        assert_eq!(char_width('\u{0301}'), 0);
    }

    #[test]
    fn test_char_width_control() {
        assert_eq!(char_width('\0'), 0);
        assert_eq!(char_width('\n'), 0);
    }

    #[test]
    fn test_text_width_mixed() {
        // "Hello" = 5, "世界" = 2*2 = 4  => total 9
        assert_eq!(text_width("Hello\u{4E16}\u{754C}"), 9);
    }

    #[test]
    fn test_text_width_empty() {
        assert_eq!(text_width(""), 0);
    }

    #[test]
    fn test_extract_column_range_ascii() {
        assert_eq!(extract_column_range("Hello World", 1, 5), "Hello");
    }

    #[test]
    fn test_extract_column_range_cjk() {
        // A=col1, B=col2, 中=col3-4, 文=col5-6, C=col7, D=col8
        assert_eq!(
            extract_column_range("AB\u{4E2D}\u{6587}CD", 3, 6),
            "\u{4E2D}\u{6587}"
        );
    }

    #[test]
    fn test_extract_column_range_partial() {
        assert_eq!(extract_column_range("Hello World", 7, 11), "World");
    }

    #[test]
    fn test_find_column_position() {
        // "Hello": H=col1, e=col2, l=col3 => column 3 is char index 2
        assert_eq!(find_column_position("Hello", 3), 2);
    }

    #[test]
    fn test_find_column_position_cjk() {
        // A=col1, B=col2, 中=col3-4 => column 3 starts at char index 2
        assert_eq!(find_column_position("AB\u{4E2D}\u{6587}", 3), 2);
    }
}
