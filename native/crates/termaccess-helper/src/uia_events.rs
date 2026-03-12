//! UIA event subscription manager.
//!
//! Tracks subscribed terminal HWNDs and detects text changes by
//! comparing current content against the last known snapshot.
//! When the main loop calls [`SubscriptionManager::check`], any
//! changed terminals produce `(hwnd, new_text)` pairs that are
//! sent as `TextChanged` notifications over the pipe.
//!
//! The check interval (50ms) is controlled by the main loop's
//! `recv_timeout` on the request channel.

use std::collections::HashMap;

use crate::uia_reader::UiaReader;

/// Manages terminal subscriptions and detects text changes.
pub struct SubscriptionManager {
    /// hwnd → last known text content
    subscriptions: HashMap<isize, String>,
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
    /// If already subscribed, this is a no-op.
    pub fn subscribe(&mut self, hwnd: isize) {
        self.subscriptions.entry(hwnd).or_insert_with(String::new);
    }

    /// Unsubscribe from text change notifications for a terminal HWND.
    ///
    /// Returns `true` if the HWND was subscribed, `false` otherwise.
    pub fn unsubscribe(&mut self, hwnd: isize) -> bool {
        self.subscriptions.remove(&hwnd).is_some()
    }

    /// Check all subscribed terminals for text changes.
    ///
    /// Reads current text from each subscribed HWND via UIA and compares
    /// against the last known snapshot. Returns a list of `(hwnd, text)`
    /// pairs for terminals whose content has changed.
    ///
    /// Terminals that fail to read (e.g. closed window) are silently
    /// skipped — they remain subscribed for retry on the next check.
    pub fn check(&mut self, reader: &UiaReader) -> Vec<(isize, String)> {
        let mut changes = Vec::new();

        for (&hwnd, last_text) in &mut self.subscriptions {
            match reader.read_text(hwnd) {
                Ok(text) => {
                    if text != *last_text {
                        *last_text = text.clone();
                        // Skip the initial empty → first-read transition
                        // to avoid flooding on subscribe.
                        if !last_text.is_empty() || !changes.is_empty() {
                            changes.push((hwnd, text));
                        }
                    }
                }
                Err(_) => {
                    // Terminal might be closed or UIA failed — skip this cycle
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
}
