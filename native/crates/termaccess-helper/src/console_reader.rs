//! Fallback console reader using Win32 Console API.
//!
//! Used when UIA TextPattern is not available for a terminal window
//! (e.g., some conhost configurations, mintty, older PuTTY builds).
//!
//! The approach:
//! 1. `GetWindowThreadProcessId(hwnd)` → get the console process PID
//! 2. `AttachConsole(pid)` → attach our process to the target console
//! 3. `GetConsoleScreenBufferInfo` → get buffer dimensions and cursor
//! 4. `ReadConsoleOutputCharacterW` → read text rows from the buffer
//! 5. `FreeConsole()` on drop (RAII guard)
//!
//! ## Limitations
//!
//! - Only works for processes that own a console (conhost-based terminals).
//! - `AttachConsole` fails if our process is already attached to a different
//!   console, so reads are serialized.
//! - Windows Terminal (WinUI) hosts console processes via ConPTY — the
//!   console buffer may not match the visual content exactly.

use std::io;

use windows::Win32::Foundation::HWND;
use windows::Win32::System::Console::{
    AttachConsole, FreeConsole, GetConsoleScreenBufferInfo, GetStdHandle,
    ReadConsoleOutputCharacterW, CONSOLE_SCREEN_BUFFER_INFO, STD_OUTPUT_HANDLE,
};
use windows::Win32::UI::WindowsAndMessaging::GetWindowThreadProcessId;

/// RAII guard that detaches from the console on drop.
struct ConsoleAttachGuard {
    attached: bool,
}

impl ConsoleAttachGuard {
    /// Attempt to attach to the console owned by `pid`.
    fn attach(pid: u32) -> io::Result<Self> {
        // First detach from any existing console (our own).
        // This is safe — the helper process doesn't need its own console.
        unsafe {
            let _ = FreeConsole();
        }

        unsafe {
            AttachConsole(pid).map_err(|e| {
                io::Error::new(
                    io::ErrorKind::Other,
                    format!("AttachConsole({pid}) failed: {e}"),
                )
            })?;
        }

        Ok(ConsoleAttachGuard { attached: true })
    }
}

impl Drop for ConsoleAttachGuard {
    fn drop(&mut self) {
        if self.attached {
            unsafe {
                let _ = FreeConsole();
            }
        }
    }
}

/// Read text from a console window's screen buffer.
///
/// This is a fallback for terminals that don't expose UIA TextPattern.
/// Returns the visible text content with trailing spaces trimmed per line.
pub fn read_console_text(hwnd: isize) -> io::Result<String> {
    // Get the process ID that owns this window.
    let mut pid: u32 = 0;
    unsafe {
        GetWindowThreadProcessId(HWND(hwnd as *mut _), Some(&mut pid));
    }
    if pid == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "GetWindowThreadProcessId returned 0",
        ));
    }

    // Attach to the target process's console.
    let _guard = ConsoleAttachGuard::attach(pid)?;

    // Get the console screen buffer handle.
    let handle = unsafe {
        GetStdHandle(STD_OUTPUT_HANDLE).map_err(|e| {
            io::Error::new(
                io::ErrorKind::Other,
                format!("GetStdHandle failed: {e}"),
            )
        })?
    };

    // Get buffer info (dimensions, cursor position).
    let mut info = CONSOLE_SCREEN_BUFFER_INFO::default();
    unsafe {
        GetConsoleScreenBufferInfo(handle, &mut info).map_err(|e| {
            io::Error::new(
                io::ErrorKind::Other,
                format!("GetConsoleScreenBufferInfo failed: {e}"),
            )
        })?;
    }

    let width = info.dwSize.X as usize;
    let height = info.dwSize.Y as usize;

    if width == 0 || height == 0 {
        return Ok(String::new());
    }

    // Read the entire buffer line by line.
    let mut result = String::with_capacity(width * height);
    let mut line_buf = vec![0u16; width];

    for row in 0..height {
        let mut chars_read: u32 = 0;
        let coord = windows::Win32::System::Console::COORD {
            X: 0,
            Y: row as i16,
        };

        unsafe {
            ReadConsoleOutputCharacterW(handle, &mut line_buf, coord, &mut chars_read).map_err(
                |e| {
                    io::Error::new(
                        io::ErrorKind::Other,
                        format!("ReadConsoleOutputCharacterW row {row} failed: {e}"),
                    )
                },
            )?;
        }

        let actual = chars_read as usize;
        let line = String::from_utf16_lossy(&line_buf[..actual]);

        // Trim trailing spaces (console buffers are padded to full width).
        let trimmed = line.trim_end();

        if row > 0 {
            result.push('\n');
        }
        result.push_str(trimmed);
    }

    // Trim trailing empty lines that are just padding.
    let trimmed = result.trim_end_matches('\n');
    Ok(trimmed.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_console_attach_guard_detach_on_drop() {
        // Verify the guard doesn't panic on drop even when not attached.
        // (FreeConsole when not attached is a no-op that returns an error
        // code, which we ignore.)
        let guard = ConsoleAttachGuard { attached: true };
        drop(guard); // Should not panic
    }

    #[test]
    fn test_read_console_text_invalid_hwnd() {
        // HWND 0 should fail (GetWindowThreadProcessId returns 0).
        let result = read_console_text(0);
        assert!(result.is_err());
    }

    #[test]
    fn test_read_console_text_nonexistent_hwnd() {
        // A made-up HWND should fail at AttachConsole.
        let result = read_console_text(0x7FFFFFFF);
        assert!(result.is_err());
    }
}
