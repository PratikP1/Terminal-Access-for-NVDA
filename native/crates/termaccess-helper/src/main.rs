//! termaccess-helper: standalone helper process for Terminal Access for NVDA.
//!
//! Communicates with the NVDA addon over a named pipe using length-prefixed
//! JSON messages. Runs UIA operations in its own COM STA apartment, freeing
//! the NVDA main thread from blocking wx.CallAfter round-trips.
//!
//! Usage: `termaccess-helper.exe --pipe-name \\.\pipe\termaccess-{pid}-{uuid}`

mod pipe_server;
mod protocol;
mod security;
mod uia_events;
mod uia_reader;

use std::env;
use std::io;
use std::process;

use windows::Win32::System::Com::{CoInitializeEx, CoUninitialize, COINIT_APARTMENTTHREADED};

use crate::pipe_server::PipeServer;
use crate::protocol::{Notification, Request, Response};
use crate::security::PipeSecurity;
use crate::uia_reader::UiaReader;

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

/// Inner loop: create UIA reader, set up pipe, process requests.
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

    // Request–response loop
    loop {
        let request = match pipe.read_request() {
            Ok(Some(req)) => req,
            Ok(None) => {
                // Client disconnected cleanly (EOF)
                break;
            }
            Err(e) => {
                if e.kind() == io::ErrorKind::BrokenPipe {
                    // Client crashed or closed its end
                    break;
                }
                return Err(e);
            }
        };

        // handle_request returns false on Shutdown
        if !handle_request(&pipe, &uia, &request)? {
            break;
        }
    }

    Ok(())
}

/// Process a single request, send the response, return `true` to continue
/// or `false` on shutdown.
fn handle_request(
    pipe: &PipeServer,
    uia: &Option<UiaReader>,
    request: &Request,
) -> io::Result<bool> {
    match request {
        Request::Ping { id } => {
            pipe.send_response(Response::Pong { id: *id })?;
            Ok(true)
        }

        Request::ReadText { id, hwnd } => {
            let response = match uia {
                Some(reader) => match reader.read_text(*hwnd) {
                    Ok(text) => {
                        let line_count = text.lines().count() as u32;
                        Response::TextResult {
                            id: *id,
                            text,
                            line_count,
                        }
                    }
                    Err(e) => Response::error(*id, "uia_error", e.to_string()),
                },
                None => Response::error(*id, "not_ready", "UIA not initialized"),
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
            let response = match uia {
                Some(reader) => match reader.read_lines(*hwnd, *start_row, *end_row) {
                    Ok(lines) => Response::LinesResult { id: *id, lines },
                    Err(e) => Response::error(*id, "uia_error", e.to_string()),
                },
                None => Response::error(*id, "not_ready", "UIA not initialized"),
            };
            pipe.send_response(response)?;
            Ok(true)
        }

        Request::Subscribe { id, .. } => {
            // Step 3: UIA event subscription
            pipe.send_response(Response::error(
                *id,
                "not_implemented",
                "Subscribe not yet implemented",
            ))?;
            Ok(true)
        }

        Request::Unsubscribe { id, .. } => {
            // Step 3: UIA event subscription
            pipe.send_response(Response::error(
                *id,
                "not_implemented",
                "Unsubscribe not yet implemented",
            ))?;
            Ok(true)
        }

        Request::Shutdown { id } => {
            // Acknowledge shutdown, then signal exit
            let _ = pipe.send_response(Response::Pong { id: *id });
            Ok(false)
        }
    }
}
