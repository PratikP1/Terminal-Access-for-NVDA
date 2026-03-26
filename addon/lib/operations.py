# Terminal Access operation classes.
# Extracted from terminalAccess.py for modularization.

import wx
import threading
from typing import Any


import lib  # noqa: F401 — ensures translation fallback is initialized


class SelectionProgressDialog:
	"""
	Properly managed progress dialog with cancellation support.

	This class provides thread-safe progress dialog management for long-running
	selection operations. It handles wx threading issues by ensuring all dialog
	operations happen on the main GUI thread.

	Features:
	- Thread-safe updates using wx.CallAfter
	- User cancellation support
	- Automatic cleanup on completion or cancellation
	- Progress percentage with elapsed/remaining time
	"""

	def __init__(self, parent, title: str, maximum: int) -> None:
		"""
		Initialize progress dialog.

		Args:
			parent: Parent window (typically gui.mainFrame)
			title: Dialog title
			maximum: Maximum progress value (typically 100 for percentage)
		"""
		self._dialog: Any | None = None
		self._cancelled: bool = False
		self._lock: threading.Lock = threading.Lock()
		self._ready: threading.Event = threading.Event()
		# Create dialog on main thread
		wx.CallAfter(self._create, parent, title, maximum)
		# Wait for the main thread to actually create the dialog (up to 2s).
		# This replaces a fixed sleep(0.1) which could lose the race.
		self._ready.wait(timeout=2.0)

	def _create(self, parent, title: str, maximum: int) -> None:
		"""
		Create the progress dialog (must be called on main thread).

		Args:
			parent: Parent window
			title: Dialog title
			maximum: Maximum progress value
		"""
		try:
			self._dialog = wx.ProgressDialog(
				title,
				_("Initializing..."),
				maximum=maximum,
				parent=parent,
				style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE |
				      wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME |
				      wx.PD_REMAINING_TIME
			)
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Failed to create progress dialog: {e}")
		finally:
			self._ready.set()

	def update(self, value: int, message: str) -> bool:
		"""
		Update progress dialog (thread-safe).

		Args:
			value: Current progress value (0 to maximum)
			message: Status message to display

		Returns:
			True if operation should continue, False if cancelled
		"""
		with self._lock:
			if self._cancelled:
				return False

			if self._dialog:
				# Schedule update on main thread
				wx.CallAfter(self._safe_update, value, message)

			return not self._cancelled

	def _safe_update(self, value: int, message: str) -> None:
		"""
		Perform the actual dialog update (called on main thread).

		Args:
			value: Current progress value
			message: Status message to display
		"""
		if self._dialog and not self._cancelled:
			try:
				cont, skip = self._dialog.Update(value, message)
				if not cont:
					# User clicked cancel
					with self._lock:
						self._cancelled = True
			except Exception as e:
				import logHandler
				logHandler.log.error(f"Terminal Access: Progress dialog update failed: {e}")
				with self._lock:
					self._cancelled = True

	def is_cancelled(self) -> bool:
		"""
		Check if operation was cancelled by user.

		Returns:
			True if cancelled, False otherwise
		"""
		with self._lock:
			return self._cancelled

	def close(self) -> None:
		"""
		Close and destroy the progress dialog (thread-safe).
		"""
		with self._lock:
			dialog = self._dialog
			self._dialog = None
		if dialog:
			wx.CallAfter(self._destroy, dialog)

	def _destroy(self, dialog) -> None:
		"""
		Destroy the dialog (called on main thread).

		Receives the dialog reference explicitly so it is not lost
		when ``close()`` clears ``self._dialog`` before this runs.
		"""
		try:
			dialog.Destroy()
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Failed to destroy progress dialog: {e}")


class OperationQueue:
	"""
	Queue system to prevent overlapping background operations.

	Ensures only one long-running operation executes at a time, preventing
	resource exhaustion and UI confusion from multiple simultaneous progress dialogs.
	"""

	def __init__(self) -> None:
		"""Initialize the operation queue."""
		self._active_operation: threading.Thread | None = None
		self._lock: threading.Lock = threading.Lock()

	def is_busy(self) -> bool:
		"""
		Check if an operation is currently running.

		Returns:
			True if operation in progress, False otherwise
		"""
		with self._lock:
			return self._active_operation is not None and self._active_operation.is_alive()

	def start_operation(self, thread: threading.Thread) -> bool:
		"""
		Start a new operation if queue is free.

		Args:
			thread: Thread to start

		Returns:
			True if operation started, False if queue busy
		"""
		with self._lock:
			# Clean up completed thread
			if self._active_operation and not self._active_operation.is_alive():
				self._active_operation = None

			# Check if queue is free
			if self._active_operation:
				return False

			# Start new operation
			self._active_operation = thread
			thread.start()
			return True

	def clear(self) -> None:
		"""
		Clear the active operation reference.

		Note: This does not stop the thread, just clears the reference.
		The thread should complete or be cancelled naturally.
		"""
		with self._lock:
			self._active_operation = None
