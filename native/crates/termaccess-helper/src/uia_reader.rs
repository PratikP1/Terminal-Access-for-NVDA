//! UIA text reading: read terminal content given an HWND.
//!
//! Uses `IUIAutomation::ElementFromHandle` to get a UIA element,
//! then `IUIAutomationTextPattern::DocumentRange` to read all text.

use std::io;

use windows::core::Interface;
use windows::Win32::Foundation::*;
use windows::Win32::UI::Accessibility::*;

use crate::security;

/// A UIA reader that holds a reference to the automation instance.
pub struct UiaReader {
    automation: IUIAutomation,
}

impl UiaReader {
    /// Create a new UIA reader.
    ///
    /// Must be called after `CoInitializeEx` on the same thread.
    pub fn new() -> io::Result<Self> {
        unsafe {
            let automation: IUIAutomation = windows::Win32::System::Com::CoCreateInstance(
                &CUIAutomation,
                None,
                windows::Win32::System::Com::CLSCTX_INPROC_SERVER,
            )
            .map_err(|e| io::Error::new(io::ErrorKind::Other, format!("CoCreateInstance failed: {e}")))?;

            Ok(UiaReader { automation })
        }
    }

    /// Read all text from a terminal identified by its HWND.
    pub fn read_text(&self, hwnd: isize) -> io::Result<String> {
        security::validate_hwnd(hwnd)?;

        unsafe {
            let wnd = HWND(hwnd as *mut _);

            // Get UIA element from HWND
            let element = self
                .automation
                .ElementFromHandle(wnd)
                .map_err(|e| io::Error::new(io::ErrorKind::Other, format!("ElementFromHandle failed: {e}")))?;

            // Get text pattern
            let pattern_obj = element
                .GetCurrentPattern(UIA_TextPatternId)
                .map_err(|e| io::Error::new(io::ErrorKind::Other, format!("GetCurrentPattern(Text) failed: {e}")))?;

            let text_pattern: IUIAutomationTextPattern = pattern_obj
                .cast()
                .map_err(|e| io::Error::new(io::ErrorKind::Other, format!("Cast to TextPattern failed: {e}")))?;

            // Get document range
            let range = text_pattern
                .DocumentRange()
                .map_err(|e| io::Error::new(io::ErrorKind::Other, format!("DocumentRange failed: {e}")))?;

            // Get text (-1 = no length limit)
            let text = range
                .GetText(-1)
                .map_err(|e| io::Error::new(io::ErrorKind::Other, format!("GetText failed: {e}")))?;

            Ok(text.to_string())
        }
    }

    /// Read a range of lines from a terminal.
    ///
    /// `start_row` and `end_row` are 1-based, inclusive.
    pub fn read_lines(&self, hwnd: isize, start_row: i32, end_row: i32) -> io::Result<Vec<String>> {
        // Read all text and extract the requested line range
        let all_text = self.read_text(hwnd)?;
        let lines: Vec<&str> = all_text.split('\n').collect();

        let start = (start_row - 1).max(0) as usize;
        let end = (end_row as usize).min(lines.len());

        if start >= lines.len() {
            return Ok(Vec::new());
        }

        Ok(lines[start..end].iter().map(|s| s.to_string()).collect())
    }

    /// Get a reference to the underlying IUIAutomation instance.
    pub fn automation(&self) -> &IUIAutomation {
        &self.automation
    }
}
