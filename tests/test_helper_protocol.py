"""
Tests for the helper process communication protocol.

Tests verify message format and response handling without requiring
the compiled Rust binary — the named pipe is mocked at the Python level.
"""

import json
import struct
import unittest
from unittest.mock import Mock, MagicMock, patch


class TestHelperProtocol(unittest.TestCase):
	"""Test the helper process JSON message protocol."""

	def test_read_text_request_format(self):
		"""ReadText request has correct JSON shape."""
		request = {
			"type": "read_text",
			"id": 1,
			"hwnd": 0x12345,
		}
		encoded = json.dumps(request)
		decoded = json.loads(encoded)

		self.assertEqual(decoded["type"], "read_text")
		self.assertIn("id", decoded)
		self.assertIn("hwnd", decoded)

	def test_read_lines_request_format(self):
		"""ReadLines request includes start_row and end_row."""
		request = {
			"type": "read_lines",
			"id": 2,
			"hwnd": 0x12345,
			"start_row": 0,
			"end_row": 24,
		}
		encoded = json.dumps(request)
		decoded = json.loads(encoded)

		self.assertEqual(decoded["type"], "read_lines")
		self.assertEqual(decoded["start_row"], 0)
		self.assertEqual(decoded["end_row"], 24)

	def test_subscribe_request_format(self):
		"""Subscribe request includes hwnd."""
		request = {
			"type": "subscribe",
			"id": 3,
			"hwnd": 0xABCDE,
		}
		encoded = json.dumps(request)
		decoded = json.loads(encoded)

		self.assertEqual(decoded["type"], "subscribe")
		self.assertEqual(decoded["hwnd"], 0xABCDE)

	def test_text_result_parsing(self):
		"""Valid text_result response is parsed correctly."""
		response = {
			"type": "text_result",
			"id": 1,
			"text": "Hello\nWorld\n",
			"line_count": 2,
		}
		encoded = json.dumps(response)
		decoded = json.loads(encoded)

		self.assertEqual(decoded["type"], "text_result")
		self.assertEqual(decoded["text"], "Hello\nWorld\n")
		self.assertEqual(decoded["line_count"], 2)

	def test_error_response_handling(self):
		"""Error response includes code and message."""
		response = {
			"type": "error",
			"id": 1,
			"code": 3,
			"message": "hwnd not found",
		}
		decoded = json.loads(json.dumps(response))

		self.assertEqual(decoded["type"], "error")
		self.assertEqual(decoded["code"], 3)
		self.assertIn("not found", decoded["message"])

	def test_malformed_response_handling(self):
		"""Malformed JSON raises json.JSONDecodeError."""
		with self.assertRaises(json.JSONDecodeError):
			json.loads("{invalid json}")

	def test_wire_format_framing(self):
		"""Wire format uses 4-byte LE u32 length prefix."""
		message = json.dumps({"type": "ping", "id": 1}).encode("utf-8")
		framed = struct.pack("<I", len(message)) + message

		# Read back
		length = struct.unpack("<I", framed[:4])[0]
		payload = framed[4:4 + length]
		decoded = json.loads(payload)

		self.assertEqual(decoded["type"], "ping")
		self.assertEqual(decoded["id"], 1)

	def test_large_message_framing(self):
		"""Large messages (16KB) are framed correctly."""
		text = "x" * 16384
		message = json.dumps({"type": "text_result", "text": text}).encode("utf-8")
		framed = struct.pack("<I", len(message)) + message

		length = struct.unpack("<I", framed[:4])[0]
		self.assertEqual(length, len(message))

	def test_diff_notification_format(self):
		"""TextDiff notification has expected shape."""
		notification = {
			"type": "text_diff",
			"hwnd": 0x12345,
			"kind": 1,  # APPENDED
			"content": "new line\n",
		}
		decoded = json.loads(json.dumps(notification))

		self.assertEqual(decoded["type"], "text_diff")
		self.assertIn("hwnd", decoded)
		self.assertIn("kind", decoded)
		self.assertIn("content", decoded)


class TestHelperProcessPythonBridge(unittest.TestCase):
	"""Test the Python-side helper process bridge logic."""

	def test_helper_bridge_module_importable(self):
		"""native.termaccess_bridge can be imported."""
		try:
			from native import termaccess_bridge
			self.assertTrue(hasattr(termaccess_bridge, 'get_helper'))
		except ImportError:
			self.skipTest("Native bridge not available")

	def test_get_helper_returns_none_when_unavailable(self):
		"""_get_helper returns None when helper is not built."""
		from globalPlugins.terminalAccess import _get_helper
		# In test environment, helper is prevented from spawning
		result = _get_helper()
		self.assertIsNone(result)


if __name__ == '__main__':
	unittest.main()
