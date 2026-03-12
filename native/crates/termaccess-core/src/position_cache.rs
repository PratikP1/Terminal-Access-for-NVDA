//! LRU position cache with time-based expiration.
//!
//! Port of `PositionCache` from `terminalAccess.py` (lines 600-708).
//! Caches (row, col) positions keyed by bookmark strings, with LRU
//! eviction and TTL-based expiration.

use lru::LruCache;
use std::num::NonZeroUsize;
use std::sync::Mutex;
use std::time::{Duration, Instant};

/// A cached position entry with timestamp.
struct CacheEntry {
    row: i32,
    col: i32,
    timestamp: Instant,
}

/// Thread-safe LRU cache for terminal cursor positions.
///
/// Each entry maps a bookmark key (string) to a (row, col) pair with a
/// timestamp. Entries expire after `timeout` duration. When the cache
/// exceeds `max_size`, the least recently used entry is evicted.
pub struct PositionCache {
    inner: Mutex<LruCache<String, CacheEntry>>,
    timeout: Duration,
}

impl PositionCache {
    /// Create a new cache with the given maximum size and timeout.
    ///
    /// # Arguments
    /// * `max_size` - Maximum number of entries before LRU eviction
    /// * `timeout_ms` - Expiration timeout in milliseconds
    pub fn new(max_size: usize, timeout_ms: u32) -> Self {
        let cap = NonZeroUsize::new(max_size.max(1)).unwrap();
        Self {
            inner: Mutex::new(LruCache::new(cap)),
            timeout: Duration::from_millis(timeout_ms as u64),
        }
    }

    /// Get a cached position by key.
    ///
    /// Returns `Some((row, col))` if the key exists and hasn't expired.
    /// Returns `None` if the key is missing or expired. Expired entries
    /// are removed. Successful lookups promote the entry in the LRU order.
    pub fn get(&self, key: &str) -> Option<(i32, i32)> {
        let mut cache = self.inner.lock().unwrap();
        if let Some(entry) = cache.get(key) {
            if entry.timestamp.elapsed() < self.timeout {
                let row = entry.row;
                let col = entry.col;
                return Some((row, col));
            }
            // Expired — remove
            cache.pop(key);
        }
        None
    }

    /// Set a cached position for the given key.
    ///
    /// If the key already exists, it is updated and promoted. If the
    /// cache is full, the least recently used entry is evicted.
    pub fn set(&self, key: &str, row: i32, col: i32) {
        let mut cache = self.inner.lock().unwrap();
        cache.put(
            key.to_string(),
            CacheEntry {
                row,
                col,
                timestamp: Instant::now(),
            },
        );
    }

    /// Clear all entries from the cache.
    pub fn clear(&self) {
        let mut cache = self.inner.lock().unwrap();
        cache.clear();
    }

    /// Remove a specific key from the cache.
    pub fn invalidate(&self, key: &str) {
        let mut cache = self.inner.lock().unwrap();
        cache.pop(key);
    }

    /// Return the number of entries currently in the cache.
    pub fn len(&self) -> usize {
        let cache = self.inner.lock().unwrap();
        cache.len()
    }

    /// Return whether the cache is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;

    #[test]
    fn test_get_set() {
        let cache = PositionCache::new(100, 1000);
        cache.set("key1", 10, 20);
        assert_eq!(cache.get("key1"), Some((10, 20)));
    }

    #[test]
    fn test_missing_key() {
        let cache = PositionCache::new(100, 1000);
        assert_eq!(cache.get("missing"), None);
    }

    #[test]
    fn test_expiration() {
        let cache = PositionCache::new(100, 50); // 50ms timeout
        cache.set("key1", 10, 20);
        assert_eq!(cache.get("key1"), Some((10, 20)));
        thread::sleep(Duration::from_millis(80));
        assert_eq!(cache.get("key1"), None);
    }

    #[test]
    fn test_lru_eviction() {
        let cache = PositionCache::new(3, 10000);
        cache.set("a", 1, 1);
        cache.set("b", 2, 2);
        cache.set("c", 3, 3);
        // Cache is full. Adding "d" should evict "a" (LRU)
        cache.set("d", 4, 4);
        assert_eq!(cache.get("a"), None);
        assert_eq!(cache.get("b"), Some((2, 2)));
        assert_eq!(cache.get("c"), Some((3, 3)));
        assert_eq!(cache.get("d"), Some((4, 4)));
    }

    #[test]
    fn test_lru_promotion() {
        let cache = PositionCache::new(3, 10000);
        cache.set("a", 1, 1);
        cache.set("b", 2, 2);
        cache.set("c", 3, 3);
        // Access "a" to promote it
        cache.get("a");
        // Now "b" is LRU. Adding "d" should evict "b"
        cache.set("d", 4, 4);
        assert_eq!(cache.get("a"), Some((1, 1)));
        assert_eq!(cache.get("b"), None);
    }

    #[test]
    fn test_update_existing() {
        let cache = PositionCache::new(100, 1000);
        cache.set("key1", 10, 20);
        cache.set("key1", 30, 40);
        assert_eq!(cache.get("key1"), Some((30, 40)));
    }

    #[test]
    fn test_clear() {
        let cache = PositionCache::new(100, 1000);
        cache.set("a", 1, 1);
        cache.set("b", 2, 2);
        cache.clear();
        assert_eq!(cache.get("a"), None);
        assert_eq!(cache.get("b"), None);
        assert!(cache.is_empty());
    }

    #[test]
    fn test_invalidate() {
        let cache = PositionCache::new(100, 1000);
        cache.set("a", 1, 1);
        cache.set("b", 2, 2);
        cache.invalidate("a");
        assert_eq!(cache.get("a"), None);
        assert_eq!(cache.get("b"), Some((2, 2)));
    }

    #[test]
    fn test_len() {
        let cache = PositionCache::new(100, 1000);
        assert_eq!(cache.len(), 0);
        cache.set("a", 1, 1);
        assert_eq!(cache.len(), 1);
        cache.set("b", 2, 2);
        assert_eq!(cache.len(), 2);
    }

    #[test]
    fn test_thread_safety() {
        use std::sync::Arc;

        let cache = Arc::new(PositionCache::new(100, 1000));
        let mut handles = vec![];

        for i in 0..10 {
            let cache = Arc::clone(&cache);
            handles.push(thread::spawn(move || {
                let key = format!("key{}", i);
                cache.set(&key, i, i * 2);
                assert_eq!(cache.get(&key), Some((i, i * 2)));
            }));
        }

        for h in handles {
            h.join().unwrap();
        }

        assert_eq!(cache.len(), 10);
    }
}
