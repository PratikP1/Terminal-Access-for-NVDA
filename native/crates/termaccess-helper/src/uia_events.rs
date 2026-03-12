//! UIA event subscription manager.
//!
//! Tracks subscribed terminal HWNDs and detects text changes using
//! `TextDiffer` from `termaccess-core`. Each subscribed terminal gets
//! its own differ instance that strips ANSI codes before diffing.
//!
//! When the main loop calls [`SubscriptionManager::check`], any
//! changed terminals produce `(hwnd, DiffKind, content)` tuples that
//! are sent as `TextDiff` notifications over the pipe.
//!
//! The check interval (50ms) is controlled by the main loop's
//! `recv_timeout` on the request channel.

use std::collections::HashMap;

use termaccess_core::ansi_strip::strip_ansi;
use termaccess_core::text_differ::{DiffKind, DiffResult, TextDiffer};

/// Per-HWND state: a `TextDiffer` that tracks the last-known text.
struct TerminalState {
    differ: TextDiffer,
}

impl TerminalState {
    fn new() -> Self {
        TerminalState {
            differ: TextDiffer::new(),
        }
    }
}

/// Manages terminal subscriptions and detects text changes.
pub struct SubscriptionManager {
    /// hwnd → per-terminal differ state
    subscriptions: HashMap<isize, TerminalState>,
}

/// A diff result tied to a specific terminal HWND.
pub struct DiffChange {
    pub hwnd: isize,
    pub kind: DiffKind,
    pub content: String,
}

impl SubscriptionManager {
    /// Create a new empty subscription manager.
    pub fn new() -> Self {
        SubscriptionManager {
            subscriptions: HashMap::new(),
        }
    }

    /// Subscribe to text change notifications for a terminal HWND.
    ///
    /// If already subscribed, this is a no-op (preserves existing differ state).
    pub fn subscribe(&mut self, hwnd: isize) {
        self.subscriptions
            .entry(hwnd)
            .or_insert_with(TerminalState::new);
    }

    /// Unsubscribe from text change notifications for a terminal HWND.
    ///
    /// Returns `true` if the HWND was subscribed, `false` otherwise.
    pub fn unsubscribe(&mut self, hwnd: isize) -> bool {
        self.subscriptions.remove(&hwnd).is_some()
    }

    /// Check all subscribed terminals for text changes.
    ///
    /// The `read_text` closure reads the current text for a given HWND.
    /// This abstraction allows the caller to try UIA first, then
    /// Console API, or any other reader — the subscription manager
    /// doesn't care about the source.
    ///
    /// The text is stripped of ANSI escape sequences and diffed.
    /// Returns changes for terminals with non-trivial diffs (Initial
    /// and Unchanged are filtered out).
    ///
    /// Terminals that fail to read (e.g. closed window) are silently
    /// skipped — they remain subscribed for retry on the next check.
    pub fn check<F>(&mut self, mut read_text: F) -> Vec<DiffChange>
    where
        F: FnMut(isize) -> Result<String, std::io::Error>,
    {
        let mut changes = Vec::new();

        for (&hwnd, state) in &mut self.subscriptions {
            match read_text(hwnd) {
                Ok(raw_text) => {
                    let clean = strip_ansi(&raw_text);
                    let result: DiffResult = state.differ.update(&clean);

                    match result.kind {
                        // Skip initial (first read) and unchanged
                        DiffKind::Initial | DiffKind::Unchanged => {}
                        // Report all other diff kinds
                        _ => {
                            changes.push(DiffChange {
                                hwnd,
                                kind: result.kind,
                                content: result.content,
                            });
                        }
                    }
                }
                Err(_) => {
                    // Terminal might be closed or read failed — skip this cycle
                }
            }
        }

        changes
    }

    /// Return `true` if there are any active subscriptions.
    pub fn has_subscriptions(&self) -> bool {
        !self.subscriptions.is_empty()
    }

    /// Return the number of active subscriptions.
    pub fn count(&self) -> usize {
        self.subscriptions.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_subscribe_unsubscribe() {
        let mut mgr = SubscriptionManager::new();
        assert!(!mgr.has_subscriptions());
        assert_eq!(mgr.count(), 0);

        mgr.subscribe(100);
        assert!(mgr.has_subscriptions());
        assert_eq!(mgr.count(), 1);

        // Double subscribe is a no-op
        mgr.subscribe(100);
        assert_eq!(mgr.count(), 1);

        mgr.subscribe(200);
        assert_eq!(mgr.count(), 2);

        assert!(mgr.unsubscribe(100));
        assert_eq!(mgr.count(), 1);

        // Unsubscribe non-existent
        assert!(!mgr.unsubscribe(999));
        assert_eq!(mgr.count(), 1);

        assert!(mgr.unsubscribe(200));
        assert!(!mgr.has_subscriptions());
    }

    #[test]
    fn test_subscribe_creates_fresh_differ() {
        let mut mgr = SubscriptionManager::new();
        mgr.subscribe(100);

        // Each subscribe gets a fresh TextDiffer with no previous snapshot
        let state = mgr.subscriptions.get(&100).unwrap();
        assert!(state.differ.last_text().is_none());
    }

    #[test]
    fn test_double_subscribe_preserves_state() {
        let mut mgr = SubscriptionManager::new();
        mgr.subscribe(100);

        // Manually prime the differ by subscribing and then modifying
        // the internal state
        {
            let state = mgr.subscriptions.get_mut(&100).unwrap();
            state.differ.update("initial text");
        }

        // Double subscribe should NOT reset the differ
        mgr.subscribe(100);
        let state = mgr.subscriptions.get(&100).unwrap();
        assert_eq!(state.differ.last_text(), Some("initial text"));
    }

    #[test]
    fn test_unsubscribe_clears_state() {
        let mut mgr = SubscriptionManager::new();
        mgr.subscribe(100);
        assert!(mgr.unsubscribe(100));
        assert!(!mgr.has_subscriptions());

        // Re-subscribing should give a fresh differ
        mgr.subscribe(100);
        let state = mgr.subscriptions.get(&100).unwrap();
        assert!(state.differ.last_text().is_none());
    }
}
