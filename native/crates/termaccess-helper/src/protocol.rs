//! Named pipe protocol: message types and length-prefix framing.
//!
//! Wire format: `[4-byte LE u32 length][UTF-8 JSON payload]`
//!
//! Maximum message size: 16 MB.

use serde::{Deserialize, Serialize};
use std::io::{self, Read, Write};

/// Maximum message payload size (16 MB).
pub const MAX_MESSAGE_SIZE: u32 = 16 * 1024 * 1024;

// ═══════════════════════════════════════════════════════════════
//  Request messages (Python → Rust)
// ═══════════════════════════════════════════════════════════════

/// A request sent from the Python addon to the helper process.
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Request {
    Ping {
        id: u64,
    },
    ReadText {
        id: u64,
        hwnd: isize,
    },
    ReadLines {
        id: u64,
        hwnd: isize,
        start_row: i32,
        end_row: i32,
    },
    Subscribe {
        id: u64,
        hwnd: isize,
    },
    Unsubscribe {
        id: u64,
        hwnd: isize,
    },
    /// Search terminal text for a pattern.
    ///
    /// The helper reads the terminal buffer via UIA and searches it
    /// in a single round-trip — no buffer transfer to Python needed.
    SearchText {
        id: u64,
        hwnd: isize,
        pattern: String,
        case_sensitive: bool,
        use_regex: bool,
    },
    Shutdown {
        id: u64,
    },
}

impl Request {
    /// Return the request id for response correlation.
    pub fn id(&self) -> u64 {
        match self {
            Request::Ping { id, .. }
            | Request::ReadText { id, .. }
            | Request::ReadLines { id, .. }
            | Request::Subscribe { id, .. }
            | Request::Unsubscribe { id, .. }
            | Request::SearchText { id, .. }
            | Request::Shutdown { id, .. } => *id,
        }
    }
}

// ═══════════════════════════════════════════════════════════════
//  Response messages (Rust → Python)
// ═══════════════════════════════════════════════════════════════

/// A single search match in a `SearchResult` response.
#[derive(Debug, Clone, Serialize)]
pub struct SearchMatchResult {
    /// 0-based line index in the text.
    pub line_index: u32,
    /// Character offset within the line where the match starts.
    pub char_offset: u32,
    /// The full (ANSI-stripped) text of the matching line.
    pub line_text: String,
}

/// A response sent from the helper process to the Python addon.
#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Response {
    Pong {
        id: u64,
    },
    TextResult {
        id: u64,
        text: String,
        line_count: u32,
    },
    LinesResult {
        id: u64,
        lines: Vec<String>,
    },
    SubscribeOk {
        id: u64,
    },
    UnsubscribeOk {
        id: u64,
    },
    /// Search results: matching lines with their indices and offsets.
    SearchResult {
        id: u64,
        matches: Vec<SearchMatchResult>,
        /// Total number of lines in the terminal buffer.
        /// Used by the Python bookmark walk to know how many lines to traverse.
        total_lines: u32,
    },
    Error {
        id: u64,
        code: String,
        message: String,
    },
}

// ═══════════════════════════════════════════════════════════════
//  Notification messages (Rust → Python, unsolicited)
// ═══════════════════════════════════════════════════════════════

/// An unsolicited notification pushed from the helper to the addon.
#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Notification {
    HelperReady,
    TextChanged { hwnd: isize, text: String },
    /// Diff-based text change notification.
    ///
    /// `kind` maps to `DiffKind` from `termaccess-core`:
    ///   0 = Initial, 1 = Unchanged, 2 = Appended,
    ///   3 = Changed, 4 = LastLineUpdated.
    ///
    /// `content` holds the appended text (kind=2), updated last line
    /// (kind=4), or is empty for other kinds.
    TextDiff {
        hwnd: isize,
        kind: u32,
        content: String,
    },
}

// ═══════════════════════════════════════════════════════════════
//  Outgoing message (wraps Response or Notification)
// ═══════════════════════════════════════════════════════════════

/// Anything we can send to the Python side.
#[derive(Debug, Clone, Serialize)]
#[serde(untagged)]
pub enum Outgoing {
    Response(Response),
    Notification(Notification),
}

impl From<Response> for Outgoing {
    fn from(r: Response) -> Self {
        Outgoing::Response(r)
    }
}

impl From<Notification> for Outgoing {
    fn from(n: Notification) -> Self {
        Outgoing::Notification(n)
    }
}

// ═══════════════════════════════════════════════════════════════
//  Length-prefixed framing
// ═══════════════════════════════════════════════════════════════

/// Read one length-prefixed JSON message from a byte stream.
///
/// Returns `Ok(None)` on clean EOF (zero-length read on the header).
pub fn read_message<R: Read>(reader: &mut R) -> io::Result<Option<Request>> {
    // Read 4-byte LE length header
    let mut header = [0u8; 4];
    match reader.read_exact(&mut header) {
        Ok(()) => {}
        Err(e) if e.kind() == io::ErrorKind::UnexpectedEof => return Ok(None),
        Err(e) if e.kind() == io::ErrorKind::BrokenPipe => return Ok(None),
        Err(e) => return Err(e),
    }

    let length = u32::from_le_bytes(header);
    if length > MAX_MESSAGE_SIZE {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            format!("Message too large: {length} bytes (max {MAX_MESSAGE_SIZE})"),
        ));
    }

    // Read payload
    let mut payload = vec![0u8; length as usize];
    reader.read_exact(&mut payload)?;

    // Deserialize
    serde_json::from_slice(&payload).map(Some).map_err(|e| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!("Invalid JSON: {e}"),
        )
    })
}

/// Write one length-prefixed JSON message to a byte stream.
pub fn write_message<W: Write>(writer: &mut W, msg: &Outgoing) -> io::Result<()> {
    let payload = serde_json::to_vec(msg).map_err(|e| {
        io::Error::new(io::ErrorKind::InvalidData, format!("Serialize error: {e}"))
    })?;

    let length = payload.len() as u32;
    if length > MAX_MESSAGE_SIZE {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            format!("Message too large: {length} bytes"),
        ));
    }

    writer.write_all(&length.to_le_bytes())?;
    writer.write_all(&payload)?;
    writer.flush()
}

// ═══════════════════════════════════════════════════════════════
//  Error response helpers
// ═══════════════════════════════════════════════════════════════

impl Response {
    pub fn error(id: u64, code: &str, message: impl Into<String>) -> Self {
        Response::Error {
            id,
            code: code.to_string(),
            message: message.into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn test_ping_roundtrip() {
        let json = br#"{"type":"ping","id":1}"#;
        let req: Request = serde_json::from_slice(json).unwrap();
        assert!(matches!(req, Request::Ping { id: 1 }));
        assert_eq!(req.id(), 1);
    }

    #[test]
    fn test_read_text_request() {
        let json = br#"{"type":"read_text","id":42,"hwnd":12345}"#;
        let req: Request = serde_json::from_slice(json).unwrap();
        match req {
            Request::ReadText { id, hwnd } => {
                assert_eq!(id, 42);
                assert_eq!(hwnd, 12345);
            }
            _ => panic!("Wrong variant"),
        }
    }

    #[test]
    fn test_read_lines_request() {
        let json = br#"{"type":"read_lines","id":3,"hwnd":99,"start_row":5,"end_row":10}"#;
        let req: Request = serde_json::from_slice(json).unwrap();
        match req {
            Request::ReadLines {
                id,
                hwnd,
                start_row,
                end_row,
            } => {
                assert_eq!(id, 3);
                assert_eq!(hwnd, 99);
                assert_eq!(start_row, 5);
                assert_eq!(end_row, 10);
            }
            _ => panic!("Wrong variant"),
        }
    }

    #[test]
    fn test_subscribe_request() {
        let json = br#"{"type":"subscribe","id":4,"hwnd":55}"#;
        let req: Request = serde_json::from_slice(json).unwrap();
        assert!(matches!(req, Request::Subscribe { id: 4, hwnd: 55 }));
    }

    #[test]
    fn test_shutdown_request() {
        let json = br#"{"type":"shutdown","id":99}"#;
        let req: Request = serde_json::from_slice(json).unwrap();
        assert!(matches!(req, Request::Shutdown { id: 99 }));
    }

    #[test]
    fn test_pong_response_serialization() {
        let resp = Response::Pong { id: 1 };
        let json = serde_json::to_string(&Outgoing::Response(resp)).unwrap();
        assert!(json.contains("\"type\":\"pong\""));
        assert!(json.contains("\"id\":1"));
    }

    #[test]
    fn test_text_result_response() {
        let resp = Response::TextResult {
            id: 2,
            text: "hello\nworld".to_string(),
            line_count: 2,
        };
        let json = serde_json::to_string(&Outgoing::Response(resp)).unwrap();
        assert!(json.contains("\"type\":\"text_result\""));
        assert!(json.contains("\"line_count\":2"));
    }

    #[test]
    fn test_error_response() {
        let resp = Response::error(5, "invalid_hwnd", "Window not found");
        let json = serde_json::to_string(&Outgoing::Response(resp)).unwrap();
        assert!(json.contains("\"code\":\"invalid_hwnd\""));
    }

    #[test]
    fn test_notification_serialization() {
        let notif = Notification::TextChanged {
            hwnd: 123,
            text: "new output".to_string(),
        };
        let json = serde_json::to_string(&Outgoing::Notification(notif)).unwrap();
        assert!(json.contains("\"type\":\"text_changed\""));
        assert!(json.contains("\"hwnd\":123"));
    }

    #[test]
    fn test_helper_ready_notification() {
        let notif = Notification::HelperReady;
        let json = serde_json::to_string(&Outgoing::Notification(notif)).unwrap();
        assert!(json.contains("\"type\":\"helper_ready\""));
    }

    #[test]
    fn test_text_diff_notification_appended() {
        let notif = Notification::TextDiff {
            hwnd: 456,
            kind: 2, // Appended
            content: "new line\n".to_string(),
        };
        let json = serde_json::to_string(&Outgoing::Notification(notif)).unwrap();
        assert!(json.contains("\"type\":\"text_diff\""));
        assert!(json.contains("\"hwnd\":456"));
        assert!(json.contains("\"kind\":2"));
        assert!(json.contains("\"content\":\"new line\\n\""));
    }

    #[test]
    fn test_text_diff_notification_changed() {
        let notif = Notification::TextDiff {
            hwnd: 789,
            kind: 3, // Changed
            content: String::new(),
        };
        let json = serde_json::to_string(&Outgoing::Notification(notif)).unwrap();
        assert!(json.contains("\"type\":\"text_diff\""));
        assert!(json.contains("\"kind\":3"));
        assert!(json.contains("\"content\":\"\""));
    }

    #[test]
    fn test_text_diff_notification_last_line_updated() {
        let notif = Notification::TextDiff {
            hwnd: 100,
            kind: 4, // LastLineUpdated
            content: "progress: 75%".to_string(),
        };
        let json = serde_json::to_string(&Outgoing::Notification(notif)).unwrap();
        assert!(json.contains("\"type\":\"text_diff\""));
        assert!(json.contains("\"kind\":4"));
        assert!(json.contains("progress: 75%"));
    }

    #[test]
    fn test_length_prefix_write_read() {
        let msg = Outgoing::Response(Response::Pong { id: 42 });

        // Write to buffer
        let mut buf = Vec::new();
        write_message(&mut buf, &msg).unwrap();

        // Should have 4-byte header + payload
        assert!(buf.len() > 4);
        let expected_len = u32::from_le_bytes([buf[0], buf[1], buf[2], buf[3]]);
        assert_eq!(expected_len as usize, buf.len() - 4);

        // Read back — read_message reads Request, so let's test the framing manually
        let payload = &buf[4..];
        let json: serde_json::Value = serde_json::from_slice(payload).unwrap();
        assert_eq!(json["type"], "pong");
        assert_eq!(json["id"], 42);
    }

    #[test]
    fn test_read_message_ping() {
        let json = br#"{"type":"ping","id":7}"#;
        let mut buf = Vec::new();
        buf.extend_from_slice(&(json.len() as u32).to_le_bytes());
        buf.extend_from_slice(json);

        let mut cursor = Cursor::new(buf);
        let req = read_message(&mut cursor).unwrap().unwrap();
        assert!(matches!(req, Request::Ping { id: 7 }));
    }

    #[test]
    fn test_read_message_eof() {
        let mut cursor = Cursor::new(Vec::<u8>::new());
        let result = read_message(&mut cursor).unwrap();
        assert!(result.is_none());
    }

    #[test]
    fn test_read_message_too_large() {
        let mut buf = Vec::new();
        buf.extend_from_slice(&(MAX_MESSAGE_SIZE + 1).to_le_bytes());
        let mut cursor = Cursor::new(buf);
        let result = read_message(&mut cursor);
        assert!(result.is_err());
    }

    #[test]
    fn test_read_message_invalid_json() {
        let payload = b"not valid json";
        let mut buf = Vec::new();
        buf.extend_from_slice(&(payload.len() as u32).to_le_bytes());
        buf.extend_from_slice(payload);

        let mut cursor = Cursor::new(buf);
        let result = read_message(&mut cursor);
        assert!(result.is_err());
    }

    #[test]
    fn test_unicode_text() {
        let resp = Response::TextResult {
            id: 1,
            text: "hello 世界 🌍".to_string(),
            line_count: 1,
        };
        let json = serde_json::to_string(&Outgoing::Response(resp)).unwrap();
        assert!(json.contains("世界"));
    }

    #[test]
    fn test_large_text_result() {
        let big_text = "x".repeat(100_000);
        let resp = Response::TextResult {
            id: 1,
            text: big_text.clone(),
            line_count: 1,
        };
        let msg = Outgoing::Response(resp);

        let mut buf = Vec::new();
        write_message(&mut buf, &msg).unwrap();

        // Verify the length prefix is correct
        let len = u32::from_le_bytes([buf[0], buf[1], buf[2], buf[3]]);
        assert_eq!(len as usize, buf.len() - 4);
    }

    #[test]
    fn test_search_text_request() {
        let json = br#"{"type":"search_text","id":10,"hwnd":555,"pattern":"error","case_sensitive":false,"use_regex":false}"#;
        let req: Request = serde_json::from_slice(json).unwrap();
        match req {
            Request::SearchText {
                id,
                hwnd,
                pattern,
                case_sensitive,
                use_regex,
            } => {
                assert_eq!(id, 10);
                assert_eq!(hwnd, 555);
                assert_eq!(pattern, "error");
                assert!(!case_sensitive);
                assert!(!use_regex);
            }
            _ => panic!("Wrong variant"),
        }
    }

    #[test]
    fn test_search_text_request_regex() {
        let json = br#"{"type":"search_text","id":11,"hwnd":123,"pattern":"^err.*","case_sensitive":true,"use_regex":true}"#;
        let req: Request = serde_json::from_slice(json).unwrap();
        match req {
            Request::SearchText {
                id,
                case_sensitive,
                use_regex,
                ..
            } => {
                assert_eq!(id, 11);
                assert!(case_sensitive);
                assert!(use_regex);
            }
            _ => panic!("Wrong variant"),
        }
    }

    #[test]
    fn test_search_result_response() {
        let resp = Response::SearchResult {
            id: 10,
            matches: vec![
                SearchMatchResult {
                    line_index: 0,
                    char_offset: 5,
                    line_text: "test error here".to_string(),
                },
                SearchMatchResult {
                    line_index: 3,
                    char_offset: 0,
                    line_text: "error: again".to_string(),
                },
            ],
            total_lines: 5,
        };
        let json = serde_json::to_string(&Outgoing::Response(resp)).unwrap();
        assert!(json.contains("\"type\":\"search_result\""));
        assert!(json.contains("\"id\":10"));
        assert!(json.contains("\"line_index\":0"));
        assert!(json.contains("\"char_offset\":5"));
        assert!(json.contains("test error here"));
        assert!(json.contains("\"line_index\":3"));
        assert!(json.contains("\"total_lines\":5"));
    }

    #[test]
    fn test_search_result_empty() {
        let resp = Response::SearchResult {
            id: 12,
            matches: vec![],
            total_lines: 10,
        };
        let json = serde_json::to_string(&Outgoing::Response(resp)).unwrap();
        assert!(json.contains("\"type\":\"search_result\""));
        assert!(json.contains("\"matches\":[]"));
        assert!(json.contains("\"total_lines\":10"));
    }
}
