# Terminal Access for NVDA - Helper Process Manager
# Copyright (C) 2024 Pratik Patel
# This add-on is covered by the GNU General Public License, version 3.
# See the file LICENSE for more details.

"""
Manages the ``termaccess-helper.exe`` subprocess.

The helper process runs UIA terminal reads in its own COM STA apartment,
eliminating the need to block NVDA's main wxPython thread with
``wx.CallAfter`` + ``threading.Event.wait()`` round-trips.

Communication uses a named pipe with length-prefixed JSON messages::

    [4-byte LE u32 length][UTF-8 JSON payload]

Usage::

    from native.helper_process import HelperProcess

    helper = HelperProcess()
    helper.start()

    # Read terminal text without blocking the main thread
    text = helper.read_text(hwnd)

    # Clean shutdown
    helper.stop()
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import logging
import os
import struct
import subprocess
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Win32 constants and kernel32 setup
# ═══════════════════════════════════════════════════════════════

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1).value

_k32: Optional[ctypes.WinDLL] = None
_k32_lock = threading.Lock()


def _get_kernel32() -> ctypes.WinDLL:
    """Get a properly typed kernel32 handle (singleton)."""
    global _k32
    if _k32 is not None:
        return _k32
    with _k32_lock:
        if _k32 is not None:
            return _k32
        k = ctypes.WinDLL("kernel32", use_last_error=True)

        k.CreateFileW.restype = ctypes.wintypes.HANDLE
        k.CreateFileW.argtypes = [
            ctypes.wintypes.LPCWSTR,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.HANDLE,
        ]

        k.ReadFile.restype = ctypes.wintypes.BOOL
        k.ReadFile.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.wintypes.DWORD,
            ctypes.POINTER(ctypes.wintypes.DWORD),
            ctypes.c_void_p,
        ]

        k.WriteFile.restype = ctypes.wintypes.BOOL
        k.WriteFile.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.wintypes.DWORD,
            ctypes.POINTER(ctypes.wintypes.DWORD),
            ctypes.c_void_p,
        ]

        k.CloseHandle.restype = ctypes.wintypes.BOOL
        k.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

        _k32 = k
        return _k32


# ═══════════════════════════════════════════════════════════════
#  Helper executable discovery
# ═══════════════════════════════════════════════════════════════

def _find_helper_exe() -> Optional[str]:
    """Find the termaccess-helper executable.

    Searches in the addon's lib directory, matching the current
    architecture (x64 or x86).
    """
    import struct as _struct
    is_64 = _struct.calcsize("P") * 8 == 64
    arch = "x64" if is_64 else "x86"

    # Look relative to this file: addon/native/ → addon/lib/{arch}/
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = os.path.join(base, "lib", arch, "termaccess-helper.exe")
    if os.path.exists(exe):
        return exe

    # Development fallback: look in native/target/release/
    dev_base = os.path.dirname(base)
    for profile in ("release", "debug"):
        exe = os.path.join(dev_base, "native", "target", profile, "termaccess-helper.exe")
        if os.path.exists(exe):
            return exe

    return None


# ═══════════════════════════════════════════════════════════════
#  HelperProcess class
# ═══════════════════════════════════════════════════════════════

class HelperProcess:
    """Manages the termaccess-helper subprocess and pipe communication.

    Thread-safe: all public methods acquire locks as needed.
    """

    # Auto-restart backoff parameters
    _RESTART_DELAYS = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._pipe_handle: Optional[int] = None
        self._pipe_name: Optional[str] = None
        self._started = False
        self._ready = threading.Event()
        self._request_id = 0
        self._id_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._read_lock = threading.Lock()
        self._notification_thread: Optional[threading.Thread] = None
        self._notification_callbacks: Dict[str, List[Callable]] = {}
        self._stopping = False
        self._restart_count = 0
        self._exe_path = _find_helper_exe()

    # ───────────────────────────────────────────────────────────
    #  Lifecycle
    # ───────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start the helper process and connect via named pipe.

        Returns True if the helper started and sent helper_ready,
        False if the helper could not be started.
        """
        if self._started:
            return True

        if not self._exe_path:
            log.warning("Helper EXE not found; helper unavailable")
            return False

        try:
            self._start_process()
            return True
        except Exception:
            log.exception("Failed to start helper process")
            return False

    def stop(self):
        """Stop the helper process gracefully."""
        self._stopping = True

        # Send shutdown if connected
        if self._pipe_handle is not None:
            try:
                self._send_request("shutdown")
            except Exception:
                pass

        self._close_pipe()

        if self._proc is not None:
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                try:
                    self._proc.wait(timeout=2)
                except Exception:
                    pass
            self._proc = None

        self._started = False
        self._ready.clear()

    @property
    def is_running(self) -> bool:
        """True if the helper process is running and ready."""
        return self._started and self._ready.is_set()

    # ───────────────────────────────────────────────────────────
    #  Terminal operations
    # ───────────────────────────────────────────────────────────

    def read_text(self, hwnd: int) -> Optional[str]:
        """Read all text from a terminal window.

        Returns the text, or None on error.
        """
        if not self.is_running:
            return None

        try:
            resp = self._send_request("read_text", hwnd=hwnd)
            if resp and resp.get("type") == "text_result":
                return resp["text"]
            if resp and resp.get("type") == "error":
                log.debug(
                    "read_text error: %s: %s",
                    resp.get("code"),
                    resp.get("message"),
                )
            return None
        except Exception:
            log.debug("read_text failed", exc_info=True)
            return None

    def read_lines(
        self, hwnd: int, start_row: int, end_row: int
    ) -> Optional[List[str]]:
        """Read a range of lines from a terminal window.

        Lines are 1-based, inclusive. Returns the lines, or None on error.
        """
        if not self.is_running:
            return None

        try:
            resp = self._send_request(
                "read_lines",
                hwnd=hwnd,
                start_row=start_row,
                end_row=end_row,
            )
            if resp and resp.get("type") == "lines_result":
                return resp["lines"]
            return None
        except Exception:
            log.debug("read_lines failed", exc_info=True)
            return None

    def ping(self) -> bool:
        """Send a ping and wait for pong. Returns True if alive."""
        if not self.is_running:
            return False

        try:
            resp = self._send_request("ping")
            return resp is not None and resp.get("type") == "pong"
        except Exception:
            return False

    # ───────────────────────────────────────────────────────────
    #  Internal: process and pipe management
    # ───────────────────────────────────────────────────────────

    def _start_process(self):
        """Spawn the helper and connect to its pipe."""
        pid = os.getpid()
        uid = uuid.uuid4().hex[:8]
        self._pipe_name = f"\\\\.\\pipe\\termaccess-{pid}-{uid}"

        self._proc = subprocess.Popen(
            [self._exe_path, "--pipe-name", self._pipe_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # Connect to the pipe (retry until helper creates it)
        k32 = _get_kernel32()
        deadline = time.monotonic() + 5.0
        connected = False

        while time.monotonic() < deadline:
            handle = k32.CreateFileW(
                self._pipe_name,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None,
            )
            if handle != INVALID_HANDLE_VALUE:
                self._pipe_handle = handle
                connected = True
                break
            # Check if process died
            if self._proc.poll() is not None:
                raise RuntimeError(
                    f"Helper exited with code {self._proc.returncode}"
                )
            time.sleep(0.05)

        if not connected:
            if self._proc.poll() is None:
                self._proc.kill()
            raise RuntimeError("Timed out connecting to helper pipe")

        # Read HelperReady notification
        msg = self._read_response()
        if msg is None or msg.get("type") != "helper_ready":
            raise RuntimeError(f"Expected helper_ready, got: {msg}")

        self._started = True
        self._ready.set()
        self._restart_count = 0
        log.info("Helper process started (PID %d)", self._proc.pid)

    def _close_pipe(self):
        """Close the pipe handle."""
        if self._pipe_handle is not None:
            try:
                _get_kernel32().CloseHandle(self._pipe_handle)
            except Exception:
                pass
            self._pipe_handle = None

    def _next_id(self) -> int:
        """Generate a monotonically increasing request id."""
        with self._id_lock:
            self._request_id += 1
            return self._request_id

    def _send_request(self, msg_type: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Send a request and wait for the matching response."""
        req_id = self._next_id()
        msg = {"type": msg_type, "id": req_id, **kwargs}

        with self._write_lock:
            self._write_message(msg)

        with self._read_lock:
            return self._read_response()

    def _write_message(self, msg: Dict[str, Any]):
        """Write a length-prefixed JSON message to the pipe."""
        payload = json.dumps(msg).encode("utf-8")
        length = struct.pack("<I", len(payload))
        data = length + payload

        k32 = _get_kernel32()
        written = ctypes.wintypes.DWORD(0)
        ok = k32.WriteFile(
            self._pipe_handle,
            data,
            len(data),
            ctypes.byref(written),
            None,
        )
        if not ok:
            err = ctypes.get_last_error()
            raise IOError(f"WriteFile failed: error {err}")

    def _read_exact(self, nbytes: int) -> bytes:
        """Read exactly nbytes from the pipe."""
        k32 = _get_kernel32()
        buf = ctypes.create_string_buffer(nbytes)
        total = 0

        while total < nbytes:
            chunk_size = nbytes - total
            chunk = ctypes.create_string_buffer(chunk_size)
            bytes_read = ctypes.wintypes.DWORD(0)
            ok = k32.ReadFile(
                self._pipe_handle,
                chunk,
                chunk_size,
                ctypes.byref(bytes_read),
                None,
            )
            if not ok:
                err = ctypes.get_last_error()
                raise IOError(f"ReadFile failed: error {err}")
            if bytes_read.value == 0:
                raise IOError("Pipe closed")
            ctypes.memmove(
                ctypes.addressof(buf) + total,
                chunk,
                bytes_read.value,
            )
            total += bytes_read.value

        return buf.raw[:nbytes]

    def _read_response(self) -> Optional[Dict[str, Any]]:
        """Read one length-prefixed JSON response from the pipe."""
        try:
            header = self._read_exact(4)
            length = struct.unpack("<I", header)[0]
            if length > 16 * 1024 * 1024:
                raise IOError(f"Response too large: {length} bytes")
            payload = self._read_exact(length)
            return json.loads(payload.decode("utf-8"))
        except Exception:
            log.debug("Failed to read response", exc_info=True)
            return None

    # ───────────────────────────────────────────────────────────
    #  Auto-restart (for future use)
    # ───────────────────────────────────────────────────────────

    def _maybe_restart(self):
        """Attempt to restart the helper after a crash.

        Uses exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (cap).
        """
        if self._stopping:
            return

        idx = min(self._restart_count, len(self._RESTART_DELAYS) - 1)
        delay = self._RESTART_DELAYS[idx]
        self._restart_count += 1

        log.warning(
            "Helper crashed, restarting in %.1fs (attempt %d)",
            delay,
            self._restart_count,
        )

        self._close_pipe()
        self._started = False
        self._ready.clear()

        time.sleep(delay)

        try:
            self._start_process()
            log.info("Helper restarted successfully")
        except Exception:
            log.exception("Failed to restart helper")
