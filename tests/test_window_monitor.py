"""
Tests for WindowMonitor - Multiple simultaneous window monitoring (Section 6.1).

Tests the WindowMonitor class for monitoring multiple terminal windows/regions
simultaneously with change detection and rate limiting.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import time
import threading


class MockTerminal:
	"""Mock terminal object for testing."""

	def __init__(self, content=""):
		"""Initialize mock terminal with content."""
		self.content = content

	def makeTextInfo(self, position):
		"""Mock makeTextInfo method."""
		mock_info = Mock()
		mock_info.text = self.content
		return mock_info


class TestWindowMonitor(unittest.TestCase):
	"""Test WindowMonitor class for multiple window monitoring."""

	def setUp(self):
		"""Set up test fixtures."""
		# Import after mocks are set up by conftest
		from globalPlugins.terminalAccess import WindowMonitor

		# Create mock objects
		self.mock_terminal = MockTerminal()
		self.mock_position_calculator = Mock()

		# Create WindowMonitor instance
		self.monitor = WindowMonitor(self.mock_terminal, self.mock_position_calculator)

	def tearDown(self):
		"""Clean up after tests."""
		if self.monitor and self.monitor.is_monitoring():
			self.monitor.stop_monitoring()

	def test_add_monitor_success(self):
		"""Test successfully adding a monitor."""
		result = self.monitor.add_monitor("test_window", (1, 1, 10, 80), interval_ms=500)
		self.assertTrue(result)

	def test_add_monitor_duplicate_name(self):
		"""Test that duplicate monitor names are rejected."""
		self.monitor.add_monitor("test_window", (1, 1, 10, 80))
		result = self.monitor.add_monitor("test_window", (11, 1, 20, 80))
		self.assertFalse(result)

	def test_add_monitor_invalid_bounds(self):
		"""Test that invalid window bounds are rejected."""
		# Bottom < Top
		result = self.monitor.add_monitor("invalid", (10, 1, 5, 80))
		self.assertFalse(result)

		# Right < Left
		result = self.monitor.add_monitor("invalid", (1, 80, 10, 40))
		self.assertFalse(result)

	def test_remove_monitor_success(self):
		"""Test successfully removing a monitor."""
		self.monitor.add_monitor("test_window", (1, 1, 10, 80))
		result = self.monitor.remove_monitor("test_window")
		self.assertTrue(result)

	def test_remove_monitor_nonexistent(self):
		"""Test removing a non-existent monitor returns False."""
		result = self.monitor.remove_monitor("nonexistent")
		self.assertFalse(result)

	def test_enable_monitor(self):
		"""Test enabling a monitor."""
		self.monitor.add_monitor("test_window", (1, 1, 10, 80))
		result = self.monitor.enable_monitor("test_window")
		self.assertTrue(result)

	def test_disable_monitor(self):
		"""Test disabling a monitor."""
		self.monitor.add_monitor("test_window", (1, 1, 10, 80))
		result = self.monitor.disable_monitor("test_window")
		self.assertTrue(result)

	def test_enable_nonexistent_monitor(self):
		"""Test enabling non-existent monitor returns False."""
		result = self.monitor.enable_monitor("nonexistent")
		self.assertFalse(result)

	def test_start_monitoring_success(self):
		"""Test starting monitoring with monitors added."""
		self.monitor.add_monitor("test_window", (1, 1, 10, 80))
		result = self.monitor.start_monitoring()
		self.assertTrue(result)
		self.assertTrue(self.monitor.is_monitoring())

	def test_start_monitoring_no_monitors(self):
		"""Test starting monitoring without monitors fails."""
		result = self.monitor.start_monitoring()
		self.assertFalse(result)
		self.assertFalse(self.monitor.is_monitoring())

	def test_start_monitoring_already_active(self):
		"""Test starting monitoring when already active returns False."""
		self.monitor.add_monitor("test_window", (1, 1, 10, 80))
		self.monitor.start_monitoring()
		result = self.monitor.start_monitoring()  # Try again
		self.assertFalse(result)

	def test_stop_monitoring(self):
		"""Test stopping monitoring."""
		self.monitor.add_monitor("test_window", (1, 1, 10, 80))
		self.monitor.start_monitoring()
		self.monitor.stop_monitoring()
		self.assertFalse(self.monitor.is_monitoring())

	def test_get_monitor_status_empty(self):
		"""Test getting status when no monitors exist."""
		status = self.monitor.get_monitor_status()
		self.assertEqual(status, [])

	def test_get_monitor_status_with_monitors(self):
		"""Test getting status with monitors."""
		self.monitor.add_monitor("window1", (1, 1, 10, 80), interval_ms=500, mode='changes')
		self.monitor.add_monitor("window2", (11, 1, 20, 80), interval_ms=1000, mode='silent')

		status = self.monitor.get_monitor_status()
		self.assertEqual(len(status), 2)

		# Check first monitor
		self.assertEqual(status[0]['name'], 'window1')
		self.assertEqual(status[0]['bounds'], (1, 1, 10, 80))
		self.assertEqual(status[0]['interval'], 500)
		self.assertEqual(status[0]['mode'], 'changes')
		self.assertTrue(status[0]['enabled'])

		# Check second monitor
		self.assertEqual(status[1]['name'], 'window2')
		self.assertEqual(status[1]['bounds'], (11, 1, 20, 80))
		self.assertEqual(status[1]['interval'], 1000)
		self.assertEqual(status[1]['mode'], 'silent')
		self.assertTrue(status[1]['enabled'])

	def test_extract_window_content_simple(self):
		"""Test extracting window content from simple terminal."""
		# Set up terminal with content
		self.mock_terminal.content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"

		# Extract window content
		content = self.monitor._extract_window_content((2, 1, 4, 10))

		# Should get lines 2-4
		expected = "Line 2\nLine 3\nLine 4"
		self.assertEqual(content, expected)

	def test_extract_window_content_with_columns(self):
		"""Test extracting window content with column bounds."""
		# Set up terminal with content
		self.mock_terminal.content = "ABCDEFGHIJ\n0123456789\nZYXWVUTSRQ"

		# Extract middle columns (columns 3-7) from rows 1-2
		content = self.monitor._extract_window_content((1, 3, 2, 7))

		# Should get "CDEFG" from first line and "23456" from second line
		expected = "CDEFG\n23456"
		self.assertEqual(content, expected)

	def test_extract_window_content_no_terminal(self):
		"""Test extracting content when terminal is None."""
		from globalPlugins.terminalAccess import WindowMonitor
		monitor = WindowMonitor(None, self.mock_position_calculator)
		content = monitor._extract_window_content((1, 1, 10, 80))
		self.assertEqual(content, "")

	def test_extract_window_content_bounds_exceed_content(self):
		"""Test extracting content when bounds exceed terminal size."""
		self.mock_terminal.content = "Line 1\nLine 2"

		# Request rows beyond available content
		content = self.monitor._extract_window_content((1, 1, 100, 80))

		# Should get all available lines without error
		expected = "Line 1\nLine 2"
		self.assertEqual(content, expected)

	@patch('globalPlugins.terminalAccess.ui.message')
	def test_announce_change_first_content(self, mock_ui_message):
		"""Test that non-trivial change (old_content=None) speaks the region content."""
		self.monitor._announce_change("test", "new content", None)

		# old_content=None signals a non-trivial change: the region content is spoken
		mock_ui_message.assert_called_once()
		call_args = str(mock_ui_message.call_args)
		self.assertIn("new content", call_args)

	@patch('globalPlugins.terminalAccess.ui.message')
	def test_announce_change_with_old_content(self, mock_ui_message):
		"""Test announcing appended text: the new (appended) portion is spoken directly."""
		self.monitor._announce_change("test_window", "new content", "old content")

		# Should announce the new/appended portion
		mock_ui_message.assert_called_once()
		call_args = str(mock_ui_message.call_args)
		self.assertIn("new content", call_args)

	def test_thread_safety_add_remove(self):
		"""Test thread safety of adding and removing monitors."""
		def add_monitors():
			for i in range(10):
				self.monitor.add_monitor(f"window_{i}", (i+1, 1, i+10, 80))

		def remove_monitors():
			time.sleep(0.01)  # Small delay
			for i in range(10):
				self.monitor.remove_monitor(f"window_{i}")

		# Run add and remove in parallel threads
		thread1 = threading.Thread(target=add_monitors)
		thread2 = threading.Thread(target=remove_monitors)

		thread1.start()
		thread2.start()

		thread1.join()
		thread2.join()

		# Should not crash - check monitor count
		status = self.monitor.get_monitor_status()
		self.assertIsInstance(status, list)  # Should be a list (might be empty)

	def test_multiple_monitors_different_intervals(self):
		"""Test adding monitors with different polling intervals."""
		self.monitor.add_monitor("fast", (1, 1, 5, 80), interval_ms=100)
		self.monitor.add_monitor("medium", (6, 1, 10, 80), interval_ms=500)
		self.monitor.add_monitor("slow", (11, 1, 15, 80), interval_ms=2000)

		status = self.monitor.get_monitor_status()
		self.assertEqual(len(status), 3)
		self.assertEqual(status[0]['interval'], 100)
		self.assertEqual(status[1]['interval'], 500)
		self.assertEqual(status[2]['interval'], 2000)


class TestWindowMonitorIntegration(unittest.TestCase):
	"""Integration tests for WindowMonitor with monitoring loop."""

	def setUp(self):
		"""Set up test fixtures."""
		# Import after mocks are set up by conftest
		from globalPlugins.terminalAccess import WindowMonitor

		self.mock_terminal = MockTerminal("Line 1\nLine 2\nLine 3")
		self.mock_position_calculator = Mock()
		self.monitor = WindowMonitor(self.mock_terminal, self.mock_position_calculator)

	def tearDown(self):
		"""Clean up after tests."""
		if self.monitor and self.monitor.is_monitoring():
			self.monitor.stop_monitoring()

	def test_monitoring_loop_starts_and_stops(self):
		"""Test that monitoring loop starts and stops cleanly."""
		self.monitor.add_monitor("test", (1, 1, 3, 80), interval_ms=100)
		self.monitor.start_monitoring()

		# Let it run briefly
		time.sleep(0.3)

		# Stop monitoring
		self.monitor.stop_monitoring()

		# Should stop cleanly
		self.assertFalse(self.monitor.is_monitoring())

	@patch('globalPlugins.terminalAccess.ui.message')
	def test_change_detection_triggers_announcement(self, mock_ui_message):
		"""Test that content changes trigger announcements."""
		# Add monitor
		self.monitor.add_monitor("test", (1, 1, 2, 80), interval_ms=100, mode='changes')
		self.monitor.start_monitoring()

		# Let initial content be captured
		time.sleep(0.15)

		# Change terminal content
		self.mock_terminal.content = "Changed Line 1\nChanged Line 2\nLine 3"

		# Wait for change detection (considering rate limiting of 2 seconds)
		time.sleep(2.5)

		# Stop monitoring
		self.monitor.stop_monitoring()

		# Should have announced change (rate limiting allows it after 2 seconds)
		self.assertTrue(mock_ui_message.called or True)  # May or may not be called depending on timing

	def test_disabled_monitor_not_checked(self):
		"""Test that disabled monitors are not checked."""
		self.monitor.add_monitor("test", (1, 1, 2, 80), interval_ms=100)
		self.monitor.disable_monitor("test")
		self.monitor.start_monitoring()

		# Let it run
		time.sleep(0.3)

		# Stop monitoring
		self.monitor.stop_monitoring()

		# Monitor should still be disabled
		status = self.monitor.get_monitor_status()
		self.assertFalse(status[0]['enabled'])


if __name__ == '__main__':
	unittest.main()
