"""End-to-end test for the termaccess-helper process.

Spawns the helper, connects via named pipe, sends messages,
and verifies correct responses.
"""

import ctypes
import ctypes.wintypes
import json
import os
import struct
import subprocess
import time
import unittest
import uuid


def _pipe_name():
    """Generate a unique pipe name."""
    uid = uuid.uuid4().hex[:8]
    return "\\\\.\\pipe\\termaccess-test-" + uid


def _helper_exe():
    """Find the helper executable."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    release = os.path.join(base, "native", "target", "release", "termaccess-helper.exe")
    debug = os.path.join(base, "native", "target", "debug", "termaccess-helper.exe")
    if os.path.exists(release):
        return release
    if os.path.exists(debug):
        return debug
    return None


# Win32 constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1).value


def _setup_kernel32():
    """Set up kernel32 function signatures for proper 64-bit handles."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    k32.CreateFileW.restype = ctypes.wintypes.HANDLE
    k32.CreateFileW.argtypes = [
        ctypes.wintypes.LPCWSTR,   # lpFileName
        ctypes.wintypes.DWORD,     # dwDesiredAccess
        ctypes.wintypes.DWORD,     # dwShareMode
        ctypes.c_void_p,           # lpSecurityAttributes
        ctypes.wintypes.DWORD,     # dwCreationDisposition
        ctypes.wintypes.DWORD,     # dwFlagsAndAttributes
        ctypes.wintypes.HANDLE,    # hTemplateFile
    ]

    k32.ReadFile.restype = ctypes.wintypes.BOOL
    k32.ReadFile.argtypes = [
        ctypes.wintypes.HANDLE,                  # hFile
        ctypes.c_void_p,                         # lpBuffer
        ctypes.wintypes.DWORD,                   # nNumberOfBytesToRead
        ctypes.POINTER(ctypes.wintypes.DWORD),   # lpNumberOfBytesRead
        ctypes.c_void_p,                         # lpOverlapped
    ]

    k32.WriteFile.restype = ctypes.wintypes.BOOL
    k32.WriteFile.argtypes = [
        ctypes.wintypes.HANDLE,                  # hFile
        ctypes.c_void_p,                         # lpBuffer
        ctypes.wintypes.DWORD,                   # nNumberOfBytesToWrite
        ctypes.POINTER(ctypes.wintypes.DWORD),   # lpNumberOfBytesWritten
        ctypes.c_void_p,                         # lpOverlapped
    ]

    k32.CloseHandle.restype = ctypes.wintypes.BOOL
    k32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

    return k32


class PipeClient:
    """Simple named pipe client for testing."""

    def __init__(self):
        self._k32 = _setup_kernel32()
        self._handle = None

    def connect(self, pipe_name, timeout=5.0):
        """Connect to a named pipe, retrying until timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            handle = self._k32.CreateFileW(
                pipe_name,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None,
            )
            if handle != INVALID_HANDLE_VALUE:
                self._handle = handle
                return True
            time.sleep(0.1)
        return False

    def _read_exact(self, nbytes):
        """Read exactly nbytes from the pipe, blocking until complete."""
        buf = ctypes.create_string_buffer(nbytes)
        total = 0
        while total < nbytes:
            chunk_size = nbytes - total
            chunk = ctypes.create_string_buffer(chunk_size)
            bytes_read = ctypes.wintypes.DWORD(0)
            ok = self._k32.ReadFile(
                self._handle,
                chunk,
                chunk_size,
                ctypes.byref(bytes_read),
                None,
            )
            if not ok:
                err = ctypes.get_last_error()
                raise IOError(f"ReadFile failed: error {err}")
            if bytes_read.value == 0:
                raise IOError("ReadFile returned 0 bytes (pipe closed)")
            ctypes.memmove(
                ctypes.addressof(buf) + total,
                chunk,
                bytes_read.value,
            )
            total += bytes_read.value
        return buf.raw[:nbytes]

    def read_message(self):
        """Read one length-prefixed JSON message."""
        try:
            header = self._read_exact(4)
        except IOError:
            return None
        length = struct.unpack("<I", header)[0]
        try:
            payload = self._read_exact(length)
        except IOError:
            return None
        return json.loads(payload.decode("utf-8"))

    def write_message(self, msg):
        """Write one length-prefixed JSON message."""
        payload = json.dumps(msg).encode("utf-8")
        length = struct.pack("<I", len(payload))
        data = length + payload
        written = ctypes.wintypes.DWORD(0)
        ok = self._k32.WriteFile(
            self._handle,
            data,
            len(data),
            ctypes.byref(written),
            None,
        )
        if not ok:
            err = ctypes.get_last_error()
            raise IOError(f"WriteFile failed: error {err}")

    def close(self):
        if self._handle is not None:
            self._k32.CloseHandle(self._handle)
            self._handle = None


_exe_path = _helper_exe()
_skip_msg = "Helper EXE not built (run: cargo build --release -p termaccess-helper)"


@unittest.skipUnless(_exe_path, _skip_msg)
class TestHelperProcess(unittest.TestCase):
    """End-to-end tests for the helper process."""

    def setUp(self):
        self.pipe_name = _pipe_name()
        self.proc = subprocess.Popen(
            [_exe_path, "--pipe-name", self.pipe_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.client = PipeClient()
        connected = self.client.connect(self.pipe_name, timeout=5.0)
        if not connected:
            stderr = ""
            try:
                _, stderr_bytes = self.proc.communicate(timeout=1)
                stderr = stderr_bytes.decode("utf-8", errors="replace")
            except Exception:
                pass
            self.fail(f"Failed to connect to helper pipe. stderr: {stderr}")

    def tearDown(self):
        self.client.close()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()

    def test_helper_ready_notification(self):
        """Helper sends helper_ready on connection."""
        msg = self.client.read_message()
        self.assertIsNotNone(msg)
        self.assertEqual(msg["type"], "helper_ready")

    def test_ping_pong(self):
        """Ping gets a pong response with matching id."""
        # Consume helper_ready
        self.client.read_message()

        self.client.write_message({"type": "ping", "id": 1})
        resp = self.client.read_message()
        self.assertIsNotNone(resp)
        self.assertEqual(resp["type"], "pong")
        self.assertEqual(resp["id"], 1)

    def test_multiple_pings(self):
        """Multiple pings get correct responses."""
        self.client.read_message()  # helper_ready

        for i in range(10):
            self.client.write_message({"type": "ping", "id": i + 100})
            resp = self.client.read_message()
            self.assertIsNotNone(resp)
            self.assertEqual(resp["type"], "pong")
            self.assertEqual(resp["id"], i + 100)

    def test_shutdown(self):
        """Shutdown causes helper to exit cleanly."""
        self.client.read_message()  # helper_ready

        self.client.write_message({"type": "shutdown", "id": 42})
        resp = self.client.read_message()
        self.assertIsNotNone(resp)
        self.assertEqual(resp["type"], "pong")
        self.assertEqual(resp["id"], 42)

        # Helper should exit
        exit_code = self.proc.wait(timeout=5)
        self.assertEqual(exit_code, 0)

    def test_subscribe_not_implemented(self):
        """Subscribe returns not_implemented error (Step 3)."""
        self.client.read_message()  # helper_ready

        self.client.write_message({"type": "subscribe", "id": 5, "hwnd": 12345})
        resp = self.client.read_message()
        self.assertIsNotNone(resp)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["id"], 5)
        self.assertEqual(resp["code"], "not_implemented")

    def test_unsubscribe_not_implemented(self):
        """Unsubscribe returns not_implemented error (Step 3)."""
        self.client.read_message()  # helper_ready

        self.client.write_message({"type": "unsubscribe", "id": 6, "hwnd": 12345})
        resp = self.client.read_message()
        self.assertIsNotNone(resp)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["id"], 6)
        self.assertEqual(resp["code"], "not_implemented")

    def test_read_text_invalid_hwnd(self):
        """ReadText with invalid HWND returns error."""
        self.client.read_message()  # helper_ready

        self.client.write_message({"type": "read_text", "id": 7, "hwnd": 0})
        resp = self.client.read_message()
        self.assertIsNotNone(resp)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["id"], 7)

    def test_read_lines_invalid_hwnd(self):
        """ReadLines with invalid HWND returns error."""
        self.client.read_message()  # helper_ready

        self.client.write_message({
            "type": "read_lines",
            "id": 8,
            "hwnd": 0,
            "start_row": 1,
            "end_row": 5,
        })
        resp = self.client.read_message()
        self.assertIsNotNone(resp)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["id"], 8)


if __name__ == "__main__":
    unittest.main()
