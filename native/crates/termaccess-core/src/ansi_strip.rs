//! ANSI escape sequence stripping.
//!
//! Port of `ANSIParser.stripANSI()` from `terminalAccess.py` (lines 1121-1132).
//! Uses a hand-written state machine for maximum performance instead of regex.

/// Strip all ANSI escape sequences from the input text.
///
/// Handles:
/// - CSI sequences: `ESC [ params letter` (e.g., colors, cursor movement)
/// - OSC sequences: `ESC ] ... BEL` or `ESC ] ... ESC \` (e.g., window title)
/// - DCS sequences: `ESC P ... ESC \` (device control strings)
/// - Charset designation: `ESC ( char` or `ESC ) char`
/// - Two-character ESC sequences: `ESC letter`
pub fn strip_ansi(input: &str) -> String {
    let bytes = input.as_bytes();
    let len = bytes.len();
    let mut out = Vec::with_capacity(len);
    let mut i = 0;

    while i < len {
        if bytes[i] != 0x1B {
            out.push(bytes[i]);
            i += 1;
            continue;
        }

        // ESC found — record position so we can restore on incomplete sequence
        let esc_start = i;
        i += 1;
        if i >= len {
            // Lone ESC at end — preserve it (Python regex wouldn't match it)
            out.push(0x1B);
            break;
        }

        match bytes[i] {
            // CSI sequence: ESC [ params final_byte
            b'[' => {
                i += 1;
                // Skip parameter bytes (0x30-0x3F: digits, semicolons, ?)
                while i < len && (bytes[i] >= 0x30 && bytes[i] <= 0x3F) {
                    i += 1;
                }
                // Skip intermediate bytes (0x20-0x2F)
                while i < len && (bytes[i] >= 0x20 && bytes[i] <= 0x2F) {
                    i += 1;
                }
                // Final byte (0x40-0x7E) completes the sequence
                if i < len && (bytes[i] >= 0x40 && bytes[i] <= 0x7E) {
                    i += 1;
                } else {
                    // Incomplete CSI — restore all bytes (Python regex wouldn't match)
                    out.extend_from_slice(&bytes[esc_start..i]);
                }
            }

            // OSC sequence: ESC ] ... BEL or ESC ] ... ESC backslash
            b']' => {
                i += 1;
                while i < len {
                    if bytes[i] == 0x07 {
                        // BEL terminates OSC
                        i += 1;
                        break;
                    }
                    if bytes[i] == 0x1B && i + 1 < len && bytes[i + 1] == b'\\' {
                        // ESC \ terminates OSC (ST - String Terminator)
                        i += 2;
                        break;
                    }
                    i += 1;
                }
            }

            // DCS sequence: ESC P ... ESC backslash
            b'P' => {
                i += 1;
                while i < len {
                    if bytes[i] == 0x1B && i + 1 < len && bytes[i + 1] == b'\\' {
                        i += 2;
                        break;
                    }
                    i += 1;
                }
            }

            // Charset designation: ESC ( char or ESC ) char
            b'(' | b')' => {
                i += 1;
                if i < len {
                    i += 1; // Skip the charset designator
                }
            }

            // Two-character ESC sequences: ESC + letter/digit/symbol
            c if c.is_ascii_alphanumeric() || c == b'=' || c == b'>' || c == b'<' || c == b'~' => {
                i += 1;
            }

            // Unknown ESC sequence — skip just the ESC character
            // (the byte after ESC will be processed normally)
            _ => {}
        }
    }

    // SAFETY: We only copied ASCII bytes or passed through valid UTF-8 bytes unchanged.
    // The input was valid UTF-8 (&str), and we only removed bytes belonging to
    // ANSI escape sequences (which are all ASCII). The remaining bytes form valid UTF-8.
    unsafe { String::from_utf8_unchecked(out) }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_no_ansi() {
        assert_eq!(strip_ansi("hello world"), "hello world");
    }

    #[test]
    fn test_sgr_colors() {
        assert_eq!(strip_ansi("\x1b[31mred\x1b[0m"), "red");
    }

    #[test]
    fn test_complex_sgr() {
        assert_eq!(
            strip_ansi("\x1b[1;4;32mgreen bold underline\x1b[0m"),
            "green bold underline"
        );
    }

    #[test]
    fn test_256_color() {
        assert_eq!(strip_ansi("\x1b[38;5;196mred256\x1b[0m"), "red256");
    }

    #[test]
    fn test_rgb_color() {
        assert_eq!(
            strip_ansi("\x1b[38;2;255;0;0mtruecolor\x1b[0m"),
            "truecolor"
        );
    }

    #[test]
    fn test_cursor_movement() {
        assert_eq!(strip_ansi("\x1b[2Jhello\x1b[1;1H"), "hello");
    }

    #[test]
    fn test_osc_title() {
        assert_eq!(
            strip_ansi("\x1b]0;My Terminal\x07text after"),
            "text after"
        );
    }

    #[test]
    fn test_osc_st_terminator() {
        assert_eq!(
            strip_ansi("\x1b]0;My Terminal\x1b\\text after"),
            "text after"
        );
    }

    #[test]
    fn test_dcs_sequence() {
        assert_eq!(strip_ansi("\x1bPsome data\x1b\\visible"), "visible");
    }

    #[test]
    fn test_charset_designation() {
        assert_eq!(strip_ansi("\x1b(Bhello\x1b)0world"), "helloworld");
    }

    #[test]
    fn test_two_char_escape() {
        // ESC = (Application Keypad), ESC > (Normal Keypad)
        assert_eq!(strip_ansi("\x1b=hello\x1b>world"), "helloworld");
    }

    #[test]
    fn test_mixed_sequences() {
        let input = "\x1b[31m\x1b]0;title\x07red text\x1b[0m normal\x1b[2J";
        assert_eq!(strip_ansi(input), "red text normal");
    }

    #[test]
    fn test_empty_string() {
        assert_eq!(strip_ansi(""), "");
    }

    #[test]
    fn test_only_ansi() {
        assert_eq!(strip_ansi("\x1b[0m\x1b[31m\x1b[0m"), "");
    }

    #[test]
    fn test_unicode_preserved() {
        assert_eq!(
            strip_ansi("\x1b[31m\u{4f60}\u{597d}\x1b[0m"),
            "\u{4f60}\u{597d}"
        );
    }

    #[test]
    fn test_question_mark_params() {
        // e.g., \x1b[?25h (show cursor), \x1b[?25l (hide cursor)
        assert_eq!(strip_ansi("\x1b[?25hvisible\x1b[?25l"), "visible");
    }

    #[test]
    fn test_osc8_hyperlink() {
        // OSC 8 hyperlink: \x1b]8;params;url\x1b\\text\x1b]8;;\x1b\\
        let input = "\x1b]8;;https://example.com\x1b\\link text\x1b]8;;\x1b\\";
        assert_eq!(strip_ansi(input), "link text");
    }

    #[test]
    fn test_large_input() {
        let base = "\x1b[31mred\x1b[0m normal ";
        let input: String = base.repeat(10000);
        let expected: String = "red normal ".repeat(10000);
        assert_eq!(strip_ansi(&input), expected);
    }

    #[test]
    fn test_incomplete_csi_preserved() {
        // Incomplete CSI at end of string: ESC [ without final byte
        // Should be preserved (matches Python regex behavior)
        assert_eq!(strip_ansi("text\x1b["), "text\x1b[");
    }

    #[test]
    fn test_lone_esc_preserved() {
        // Lone ESC at end of string should be preserved
        assert_eq!(strip_ansi("text\x1b"), "text\x1b");
    }
}
