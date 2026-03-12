//! Named pipe server: create, accept connections, read/write messages.

use std::io::{self, Read, Write};

use windows::core::HSTRING;
use windows::Win32::Foundation::*;
use windows::Win32::Storage::FileSystem::*;
use windows::Win32::System::Pipes::*;

use crate::protocol::{self, Outgoing, Request};
use crate::security::PipeSecurity;

/// Buffer size for pipe I/O (64 KB).
const PIPE_BUFFER_SIZE: u32 = 65536;

/// A named pipe server that handles one client at a time.
pub struct PipeServer {
    handle: HANDLE,
    connected: bool,
}

/// Wrapper around a pipe handle to implement `Read` and `Write`.
struct PipeIO {
    handle: HANDLE,
}

impl Read for PipeIO {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        let mut bytes_read: u32 = 0;
        unsafe {
            ReadFile(self.handle, Some(buf), Some(&mut bytes_read), None)
                .map_err(|e| {
                    let code = e.code().0 as u32;
                    if code == ERROR_BROKEN_PIPE.0 || code == ERROR_NO_DATA.0 {
                        io::Error::new(io::ErrorKind::BrokenPipe, "Pipe disconnected")
                    } else {
                        io::Error::new(io::ErrorKind::Other, e.to_string())
                    }
                })?;
        }
        Ok(bytes_read as usize)
    }
}

impl Write for PipeIO {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        let mut bytes_written: u32 = 0;
        unsafe {
            WriteFile(self.handle, Some(buf), Some(&mut bytes_written), None)
                .map_err(|e| {
                    let code = e.code().0 as u32;
                    if code == ERROR_BROKEN_PIPE.0 || code == ERROR_NO_DATA.0 {
                        io::Error::new(io::ErrorKind::BrokenPipe, "Pipe disconnected")
                    } else {
                        io::Error::new(io::ErrorKind::Other, e.to_string())
                    }
                })?;
        }
        Ok(bytes_written as usize)
    }

    fn flush(&mut self) -> io::Result<()> {
        unsafe {
            FlushFileBuffers(self.handle)
                .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
        }
        Ok(())
    }
}

impl PipeServer {
    /// Create a named pipe server with the given name and security attributes.
    ///
    /// The pipe is created with `PIPE_ACCESS_DUPLEX` and `PIPE_TYPE_BYTE`.
    /// Only one instance is allowed (`nMaxInstances = 1`).
    pub fn create(pipe_name: &str, security: &mut PipeSecurity) -> io::Result<Self> {
        let wide_name = HSTRING::from(pipe_name);

        let handle = unsafe {
            CreateNamedPipeW(
                &wide_name,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                1,                // max instances
                PIPE_BUFFER_SIZE, // out buffer
                PIPE_BUFFER_SIZE, // in buffer
                0,                // default timeout
                Some(&security.attrs),
            )
        };

        // CreateNamedPipeW returns INVALID_HANDLE_VALUE on failure
        if handle.is_invalid() {
            return Err(io::Error::last_os_error());
        }

        Ok(PipeServer {
            handle,
            connected: false,
        })
    }

    /// Wait for a client to connect. Blocks until connection or error.
    pub fn wait_for_connection(&mut self) -> io::Result<()> {
        unsafe {
            match ConnectNamedPipe(self.handle, None) {
                Ok(()) => {}
                Err(e) => {
                    // ERROR_PIPE_CONNECTED means client connected before we called
                    let code = e.code().0 as u32;
                    if code != ERROR_PIPE_CONNECTED.0 {
                        return Err(io::Error::new(io::ErrorKind::Other, e.to_string()));
                    }
                }
            }
        }
        self.connected = true;
        Ok(())
    }

    /// Read one request message from the connected client.
    ///
    /// Returns `Ok(None)` on client disconnect.
    pub fn read_request(&self) -> io::Result<Option<Request>> {
        let mut io = PipeIO {
            handle: self.handle,
        };
        protocol::read_message(&mut io)
    }

    /// Write one outgoing message (response or notification) to the client.
    pub fn write_message(&self, msg: &Outgoing) -> io::Result<()> {
        let mut io = PipeIO {
            handle: self.handle,
        };
        protocol::write_message(&mut io, msg)
    }

    /// Send a response message.
    pub fn send_response(&self, resp: protocol::Response) -> io::Result<()> {
        self.write_message(&Outgoing::Response(resp))
    }

    /// Send a notification message.
    pub fn send_notification(&self, notif: protocol::Notification) -> io::Result<()> {
        self.write_message(&Outgoing::Notification(notif))
    }

    /// Check if a client is currently connected.
    pub fn is_connected(&self) -> bool {
        self.connected
    }

    /// Disconnect the current client (allows a new client to connect).
    pub fn disconnect(&mut self) {
        if self.connected {
            unsafe {
                let _ = DisconnectNamedPipe(self.handle);
            }
            self.connected = false;
        }
    }
}

impl Drop for PipeServer {
    fn drop(&mut self) {
        self.disconnect();
        if !self.handle.is_invalid() {
            unsafe {
                let _ = CloseHandle(self.handle);
            }
        }
    }
}

// Send PipeServer across threads (the handle is valid across threads)
unsafe impl Send for PipeServer {}
