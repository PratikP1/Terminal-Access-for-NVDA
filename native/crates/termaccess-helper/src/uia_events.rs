//! UIA event subscription (to be implemented in Step 3).
//!
//! Will implement `IUIAutomationTextEditTextChangedEventHandler`
//! with a 50ms coalesce window for terminal text change notifications.
//! This replaces 300ms polling with event-driven updates.
