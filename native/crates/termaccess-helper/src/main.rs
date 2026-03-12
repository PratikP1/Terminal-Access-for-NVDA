//! termaccess-helper: standalone helper process for Terminal Access for NVDA.
//!
//! Communicates with the NVDA addon over a named pipe using length-prefixed
//! JSON messages. Runs UIA operations in its own COM STA apartment, freeing
//! the NVDA main thread from blocking wx.CallAfter round-trips.
//!
//! ## Thread model
//!
//! Single-threaded event loop using `PeekNamedPipe` for non-blocking reads:
//!
//! ```text
//! Main thread (STA):
//!   CoInitializeEx(STA)
//!   CoCreateInstance(IUIAutomation)
//!   Loop:
//!     PeekNamedPipe → data available?
//!       yes → read request, handle it, write response
//!       no  → check subscriptions (every 50ms)
//!     sleep(5ms) to avoid busy-wait
//! ```
//!
//! A single-threaded design is required because Windows serializes
//! synchronous I/O operations from different threads on the same
//! handle, which would deadlock a reader+writer thread pair.
//!
//! Usage: `termaccess-helper.exe --pipe-name \\.\pipe\termaccess-{pid}-{uuid}`

mod console_reader;
mod pipe_server;
mod protocol;
mod security;
mod uia_events;
mod uia_reader;

use std::env;
use std::io;
use std::process;
use std::thread;
use std::time::{Duration, Instant};

use windows::Win32::System::Com::{CoInitializeEx, CoUninitialize, COINIT_APARTMENTTHREADED};

use crate::pipe_server::PipeServer;
use crate::protocol::{Notification, Request, Response};
use crate::security::PipeSecurity;
use crate::uia_events::SubscriptionManager;
use crate::uia_reader::UiaReader;

/// Interval between subscription checks (50ms).
const SUBSCRIPTION_CHECK_INTERVAL: Duration = Duration::from_millis(50);

/// Sleep duration when no pipe data is available (5ms).
/// Keeps CPU usage minimal while maintaining responsiveness.
const POLL_SLEEP: Duration = Duration::from_millis(5);

fn main() {
    let pipe_name = match parse_pipe_name() {
        Some(name) => name,
        None => {
            eprintln!("Usage: termaccess-helper --pipe-name <name>");
            process::exit(1);
        }
    };

    if let Err(e) = run(&pipe_name) {
        eprintln!("Fatal error: {e}");
        process::exit(2);
    }
}

/// Parse the `--pipe-name` argument from the command line.
fn parse_pipe_name() -> Option<String> {
    let args: Vec<String> = env::args().collect();
    let mut i = 1; // skip program name
    while i < args.len() {
        if args[i] == "--pipe-name" {
            if i + 1 < args.len() {
                return Some(args[i + 1].clone());
            }
            return None; // --pipe-name without value
        }
        i += 1;
    }
    None
}

/// Main run loop: initialise COM, create pipe, handle requests.
fn run(pipe_name: &str) -> io::Result<()> {
    // Initialize COM in Single-Threaded Apartment mode.
    // Required for UIA operations; ensures COM objects are accessed
    // on the correct thread with proper lifetime management.
    unsafe {
        CoInitializeEx(None, COINIT_APARTMENTTHREADED)
            .ok()
            .map_err(|e| {
                io::Error::new(
                    io::ErrorKind::Other,
                    format!("CoInitializeEx failed: {e}"),
                )
            })?;
    }

    let result = run_pipe_loop(pipe_name);

    unsafe {
        CoUninitialize();
    }

    result
}

/// Inner loop: create UIA reader, set up pipe, poll for requests
/// and subscription changes on a single thread.
fn run_pipe_loop(pipe_name: &str) -> io::Result<()> {
    // Create UIA reader. This may fail (e.g. in test environments without
    // a desktop), so we proceed without it — read requests will get errors.
    let uia = match UiaReader::new() {
        Ok(reader) => Some(reader),
        Err(e) => {
            eprintln!("Warning: UIA init failed (read_text will error): {e}");
            None
        }
    };

    // Create named pipe with DACL restricted to current user
    let mut security = PipeSecurity::new()?;
    let mut pipe = PipeServer::create(pipe_name, &mut security)?;

    // Block until the Python addon connects
    pipe.wait_for_connection()?;

    // Tell the client we're ready to accept requests
    pipe.send_notification(Notification::HelperReady)?;

    // Subscription manager for tracking terminal text changes
    let mut subs = SubscriptionManager::new();

    // Track when we last checked subscriptions
    let mut last_sub_check = Instant::now();

    // Single-threaded event loop:
    // - Use PeekNamedPipe to check for available data
    // - Read and handle requests when data is available
    // - Check subscriptions every SUBSCRIPTION_CHECK_INTERVAL
    // - Sleep briefly when idle to avoid burning CPU
    loop {
        // Check if there's data available on the pipe
        match pipe.peek() {
            Ok(0) => {
                // No data available — check subscriptions if interval elapsed
                if subs.has_subscriptions()
                    && last_sub_check.elapsed() >= SUBSCRIPTION_CHECK_INTERVAL
                {
                    last_sub_check = Instant::now();
                    let changes = subs.check(|hwnd| {
                        // Try UIA first, then Console API fallback.
                        if let Some(reader) = uia.as_ref() {
                            if let Ok(text) = reader.read_text(hwnd) {
                                return Ok(text);
                            }
                        }
                        console_reader::read_console_text(hwnd)
                    });
                    for change in changes {
                        let notif = Notification::TextDiff {
                            hwnd: change.hwnd,
                            kind: change.kind as u32,
                            content: change.content,
                        };
                        if pipe.send_notification(notif).is_err() {
                            return Ok(());
                        }
                    }
                }

                // Brief sleep to avoid busy-waiting
                thread::sleep(POLL_SLEEP);
            }
            Ok(_bytes_available) => {
                // Data available — read and handle the request
                let request = match pipe.read_request() {
                    Ok(Some(req)) => req,
                    Ok(None) => break, // Client disconnected
                    Err(e) => {
                        if e.kind() == io::ErrorKind::BrokenPipe {
                            break;
                        }
                        if e.kind() == io::ErrorKind::InvalidData {
                            // Unknown message type or malformed JSON — try to
                            // extract the id and send an error response so the
                            // client doesn't hang.
                            eprintln!("Ignoring invalid request: {e}");
                            let _ = pipe.send_response(Response::Error {
                                id: 0,
                                code: "invalid_request".into(),
                                message: e.to_string(),
                            });
                            continue;
                        }
                        return Err(e);
                    }
                };

                if !handle_request(&pipe, &uia, &mut subs, &request)? {
                    break;
                }
            }
            Err(e) => {
                // Peek failed — pipe is broken
                if e.kind() == io::ErrorKind::BrokenPipe {
                    break;
                }
                return Err(e);
            }
        }
    }

    Ok(())
}

/// Try to read terminal text using UIA first, then Console API fallback.
///
/// Returns the text on success, or an error string on failure.
fn read_text_with_fallback(uia: &Option<UiaReader>, hwnd: isize) -> Result<String, String> {
    // Try UIA first (preferred — richer content, works with ConPTY).
    if let Some(reader) = uia {
        match reader.read_text(hwnd) {
            Ok(text) => return Ok(text),
            Err(e) => {
                eprintln!("UIA read failed for hwnd {hwnd}, trying Console API: {e}");
            }
        }
    }

    // Fallback: Win32 Console API (works for non-UIA conhost terminals).
    match console_reader::read_console_text(hwnd) {
        Ok(text) => Ok(text),
        Err(e) => Err(format!("Both UIA and Console API failed: {e}")),
    }
}

/// Process a single request, send the response, return `true` to continue
/// or `false` on shutdown.
fn handle_request(
    pipe: &PipeServer,
    uia: &Option<UiaReader>,
    subs: &mut SubscriptionManager,
    request: &Request,
) -> io::Result<bool> {
    match request {
        Request::Ping { id } => {
            pipe.send_response(Response::Pong { id: *id })?;
            Ok(true)
        }

        Request::ReadText { id, hwnd } => {
            let response = match read_text_with_fallback(uia, *hwnd) {
                Ok(text) => {
                    let line_count = text.lines().count() as u32;
                    Response::TextResult {
                        id: *id,
                        text,
                        line_count,
                    }
                }
                Err(e) => Response::error(*id, "read_failed", e),
            };
            pipe.send_response(response)?;
            Ok(true)
        }

        Request::ReadLines {
            id,
            hwnd,
            start_row,
            end_row,
        } => {
            let response = match read_text_with_fallback(uia, *hwnd) {
                Ok(all_text) => {
                    let lines: Vec<&str> = all_text.split('\n').collect();
                    let start = (*start_row - 1).max(0) as usize;
                    let end = (*end_row as usize).min(lines.len());
                    if start >= lines.len() {
                        Response::LinesResult {
                            id: *id,
                            lines: Vec::new(),
                        }
                    } else {
                        Response::LinesResult {
                            id: *id,
                            lines: lines[start..end].iter().map(|s| s.to_string()).collect(),
                        }
                    }
                }
                Err(e) => Response::error(*id, "read_failed", e),
            };
            pipe.send_response(response)?;
            Ok(true)
        }

        Request::Subscribe { id, hwnd } => {
            subs.subscribe(*hwnd);
            pipe.send_response(Response::SubscribeOk { id: *id })?;
            Ok(true)
        }

        Request::Unsubscribe { id, hwnd } => {
            subs.unsubscribe(*hwnd);
            pipe.send_response(Response::UnsubscribeOk { id: *id })?;
            Ok(true)
        }

        Request::SearchText {
            id,
            hwnd,
            ref pattern,
            case_sensitive,
            use_regex,
        } => {
            let response = match read_text_with_fallback(uia, *hwnd) {
                Ok(text) => {
                    use termaccess_core::search;
                    let line_count = text.split('\n').count() as u32;
                    match search::search_text(&text, pattern, *case_sensitive, *use_regex) {
                        Ok(matches) => Response::SearchResult {
                            id: *id,
                            matches: matches
                                .into_iter()
                                .map(|m| protocol::SearchMatchResult {
                                    line_index: m.line_index,
                                    char_offset: m.char_offset,
                                    line_text: m.line_text,
                                })
                                .collect(),
                            total_lines: line_count,
                        },
                        Err(search::SearchError::InvalidRegex(msg)) => {
                            Response::error(*id, "invalid_regex", msg)
                        }
                    }
                }
                Err(e) => Response::error(*id, "read_failed", e),
            };
            pipe.send_response(response)?;
            Ok(true)
        }

        Request::Shutdown { id } => {
            // Acknowledge shutdown, then signal exit
            let _ = pipe.send_response(Response::Pong { id: *id });
            Ok(false)
        }
    }
}
