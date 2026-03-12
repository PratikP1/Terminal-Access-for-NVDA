//! Error codes and type aliases for the C ABI layer.

/// Success.
pub const ERR_OK: i32 = 0;

/// A required pointer argument was null.
pub const ERR_NULL_POINTER: i32 = 1;

/// Input bytes were not valid UTF-8.
pub const ERR_INVALID_UTF8: i32 = 2;

/// Cache lookup: key not found or entry expired.
pub const ERR_NOT_FOUND: i32 = 3;

/// Regex compilation failed (invalid pattern).
pub const ERR_INVALID_REGEX: i32 = 4;
