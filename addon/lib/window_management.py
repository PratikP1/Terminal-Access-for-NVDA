# Terminal Access window management classes.
# Extracted from terminalAccess.py for modularization.

import time
import threading
import textInfos
import ui
from typing import Any

from lib.config import ConfigManager, MAX_WINDOW_DIMENSION
from lib.caching import TextDiffer
import lib._runtime as _rt


class WindowManager:
	"""
	Centralized window tracking and management for Terminal Access.

	Handles window definition, position tracking, and state management.
	Windows are rectangular regions of the terminal screen that can be
	tracked separately with different speech modes.

	Thread Safety:
		All operations are thread-safe through config manager.

	State Management:
		Window state is persisted via ConfigManager.
		Changes are immediately saved to NVDA configuration.
	"""

	def __init__(self, config_manager: ConfigManager) -> None:
		"""
		Initialize the window manager.

		Args:
			config_manager: ConfigManager instance for config access
		"""
		self._config = config_manager
		self._defining = False
		self._start_set = False

	def is_defining(self) -> bool:
		"""Check if currently in window definition mode."""
		return self._defining

	def start_definition(self) -> None:
		"""Start window definition mode."""
		self._defining = True
		self._start_set = False

	def cancel_definition(self) -> None:
		"""Cancel window definition mode."""
		self._defining = False
		self._start_set = False

	def set_window_start(self, row: int, col: int) -> bool:
		"""
		Set the window start position.

		Args:
			row: Starting row (1-based)
			col: Starting column (1-based)

		Returns:
			True if set successfully
		"""
		if not self._defining:
			return False

		if not self._validate_coordinates(row, col):
			return False

		self._config.set("windowTop", row)
		self._config.set("windowLeft", col)
		self._start_set = True
		return True

	def set_window_end(self, row: int, col: int) -> bool:
		"""
		Set the window end position and complete definition.

		Args:
			row: Ending row (1-based)
			col: Ending column (1-based)

		Returns:
			True if set successfully
		"""
		if not self._defining or not self._start_set:
			return False

		if not self._validate_coordinates(row, col):
			return False

		self._config.set("windowBottom", row)
		self._config.set("windowRight", col)
		self._defining = False
		return True

	def _validate_coordinates(self, row: int, col: int) -> bool:
		"""
		Validate row and column coordinates.

		Args:
			row: Row number
			col: Column number

		Returns:
			True if valid
		"""
		return (1 <= row <= MAX_WINDOW_DIMENSION and
				1 <= col <= MAX_WINDOW_DIMENSION)

	def enable_window(self) -> None:
		"""Enable window tracking."""
		self._config.set("windowEnabled", True)

	def disable_window(self) -> None:
		"""Disable window tracking."""
		self._config.set("windowEnabled", False)

	def is_window_enabled(self) -> bool:
		"""Check if window tracking is enabled."""
		return self._config.get("windowEnabled", False)

	def is_position_in_window(self, row: int, col: int) -> bool:
		"""
		Check if a position is within the defined window.

		Args:
			row: Row number (1-based)
			col: Column number (1-based)

		Returns:
			True if position is in window and window is enabled
		"""
		if not self.is_window_enabled():
			return False

		top = self._config.get("windowTop", 0)
		bottom = self._config.get("windowBottom", 0)
		left = self._config.get("windowLeft", 0)
		right = self._config.get("windowRight", 0)

		# Window not properly defined
		if top == 0 or bottom == 0 or left == 0 or right == 0:
			return False

		return (top <= row <= bottom and left <= col <= right)

	def get_window_bounds(self) -> dict[str, int]:
		"""
		Get the current window bounds.

		Returns:
			Dictionary with 'top', 'bottom', 'left', 'right' keys
		"""
		return {
			'top': self._config.get("windowTop", 0),
			'bottom': self._config.get("windowBottom", 0),
			'left': self._config.get("windowLeft", 0),
			'right': self._config.get("windowRight", 0),
		}

	def clear_window(self) -> None:
		"""Clear window definition and disable tracking."""
		self._config.set("windowTop", 0)
		self._config.set("windowBottom", 0)
		self._config.set("windowLeft", 0)
		self._config.set("windowRight", 0)
		self._config.set("windowEnabled", False)
		self._defining = False
		self._start_set = False


class PositionCalculator:
	"""
	Centralized position calculation for terminal coordinates.

	Handles calculation of (row, col) coordinates from TextInfo objects,
	with performance optimization through caching and incremental tracking.

	Performance:
		- First calculation: O(n) where n = row number
		- Cached calculation: O(1)
		- Incremental calculation: O(k) where k = distance moved

	Thread Safety:
		All operations are thread-safe through PositionCache locking.

	Caching Strategy:
		- Cache entries expire after 1000ms
		- Maximum 100 cached positions
		- Automatic invalidation on content changes
	"""

	def __init__(self) -> None:
		"""Initialize the position calculator with empty cache."""
		self._cache = _rt.make_position_cache()
		self._last_known_position: tuple[Any, int, int] | None = None

	def calculate(self, textInfo: Any, terminal: Any) -> tuple[int, int]:
		"""
		Calculate row and column coordinates from TextInfo.

		Uses multi-tiered approach:
		1. Check position cache (1000ms timeout)
		2. Try incremental tracking from last position
		3. Fall back to full calculation from buffer start

		Args:
			textInfo: TextInfo object to calculate position for
			terminal: Terminal object for context

		Returns:
			Tuple of (row, col) as 1-based integers, or (0, 0) on error
		"""
		if not terminal:
			return (0, 0)

		try:
			bookmark = textInfo.bookmark

			# Check cache first
			cached = self._cache.get(bookmark)
			if cached is not None:
				return cached

			# Try incremental tracking
			if self._last_known_position is not None:
				result = self._try_incremental_calculation(
					textInfo, terminal, bookmark
				)
				if result is not None:
					return result

			# Fall back to full calculation
			return self._calculate_full(textInfo, terminal, bookmark)

		except (RuntimeError, AttributeError) as e:
			import logHandler
			logHandler.log.error(f"Terminal Access PositionCalculator: Position access error - {type(e).__name__}: {e}")
			return (0, 0)
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access PositionCalculator: Unexpected error - {type(e).__name__}: {e}")
			return (0, 0)

	def _try_incremental_calculation(self, textInfo: Any, terminal: Any,
									 bookmark: Any) -> tuple[int, int] | None:
		"""
		Try to calculate position incrementally from last known position.

		Args:
			textInfo: Target TextInfo
			terminal: Terminal object
			bookmark: TextInfo bookmark

		Returns:
			(row, col) tuple if successful, None if incremental not possible
		"""
		try:
			lastBookmark, lastRow, lastCol = self._last_known_position
			lastInfo = terminal.makeTextInfo(lastBookmark)

			# Calculate distance between positions
			comparison = lastInfo.compareEndPoints(textInfo, "startToStart")

			# If close enough (within 10 lines), use incremental
			if abs(comparison) <= 10:
				result = self._calculate_incremental(
					textInfo, lastInfo, lastRow, lastCol, comparison
				)
				if result is not None:
					row, col = result
					# Cache and store
					self._cache.set(bookmark, row, col)
					self._last_known_position = (bookmark, row, col)
					return (row, col)

		except Exception:
			pass

		return None

	def _calculate_incremental(self, targetInfo: Any, lastInfo: Any,
							   lastRow: int, lastCol: int,
							   comparison: int) -> tuple[int, int] | None:
		"""
		Calculate position incrementally from known position.

		Args:
			targetInfo: Target TextInfo
			lastInfo: Last known TextInfo
			lastRow: Last known row
			lastCol: Last known column
			comparison: Comparison result from compareEndPoints

		Returns:
			(row, col) tuple if successful, None if failed
		"""
		try:
			if comparison == 0:
				return (lastRow, lastCol)  # Same position

			# Clone the last info to avoid modifying it
			workingInfo = lastInfo.copy()

			# Move forward or backward by lines
			if comparison > 0:  # Target is after last position
				linesMovedForward = workingInfo.move(textInfos.UNIT_LINE, comparison)
				newRow = lastRow + linesMovedForward

				# Calculate column
				lineStart = workingInfo.copy()
				lineStart.collapse()
				lineStart.expand(textInfos.UNIT_LINE)
				lineStart.collapse()

				targetCopy = targetInfo.copy()
				targetCopy.collapse()

				# Create range from line start to target and count characters
				charRange = lineStart.copy()
				charRange.setEndPoint(targetCopy, "endToEnd")
				charsFromLineStart = len(charRange.text) if charRange.text else 0
				newCol = charsFromLineStart + 1

				return (newRow, newCol)

			else:  # Target is before last position
				linesMovedBack = abs(workingInfo.move(textInfos.UNIT_LINE, comparison))
				newRow = max(1, lastRow - linesMovedBack)

				# Calculate column
				lineStart = workingInfo.copy()
				lineStart.collapse()
				lineStart.expand(textInfos.UNIT_LINE)
				lineStart.collapse()

				targetCopy = targetInfo.copy()
				targetCopy.collapse()

				# Create range from line start to target and count characters
				charRange = lineStart.copy()
				charRange.setEndPoint(targetCopy, "endToEnd")
				charsFromLineStart = len(charRange.text) if charRange.text else 0
				newCol = charsFromLineStart + 1

				return (newRow, newCol)

		except Exception:
			return None

	@staticmethod
	def _needs_scrollback_compensation(terminal) -> bool:
		"""Return True if the terminal needs scrollback compensation.

		Windows Terminal's POSITION_FIRST is already viewport-relative, so
		no compensation is needed.  conhost includes scrollback, so we need
		to estimate the viewport offset.
		"""
		try:
			appName = terminal.appModule.appName.lower()
		except (AttributeError, TypeError):
			return False
		# Windows Terminal is already viewport-relative
		if "windowsterminal" in appName:
			return False
		# conhost, cmd, powershell, etc. may include scrollback
		return any(t in appName for t in ("cmd", "powershell", "pwsh", "conhost"))

	@staticmethod
	def _to_viewport_row(buffer_row: int, total_lines: int, terminal) -> int:
		"""Convert buffer-absolute row to viewport-relative row on conhost.

		conhost's POSITION_FIRST includes scrollback, so buffer_row may be
		inflated by thousands.  We estimate the viewport height from the
		terminal window's pixel dimensions and subtract the scrollback offset.

		Args:
			buffer_row: Row number counted from POSITION_FIRST (1-based).
			total_lines: Total line count in the buffer.
			terminal: NVDA terminal NVDAObject.

		Returns:
			Viewport-relative row (1-based), or *buffer_row* unchanged on failure.
		"""
		try:
			loc = getattr(terminal, 'location', None)
			if loc is None:
				return buffer_row
			pixel_height = loc[3] if len(loc) >= 4 else getattr(loc, 'height', 0)
			if pixel_height <= 0:
				return buffer_row
			# ~18px per character cell is a reasonable estimate for common DPI / font combos
			viewport_rows = max(1, pixel_height // 18)
			scrollback = max(0, total_lines - viewport_rows)
			return max(1, buffer_row - scrollback)
		except Exception:
			return buffer_row

	def _calculate_full(self, textInfo: Any, terminal: Any,
					   bookmark: Any) -> tuple[int, int]:
		"""
		Perform full O(n) position calculation from buffer start.

		Args:
			textInfo: TextInfo to calculate position for
			terminal: Terminal object
			bookmark: TextInfo bookmark

		Returns:
			(row, col) tuple
		"""
		# Start from beginning of buffer and count lines forward to the target
		startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
		startInfo.collapse()

		# Calculate row by counting lines
		targetCopy = textInfo.copy()
		targetCopy.collapse()

		# Count how many lines from buffer start until target
		lineCount = 0
		while startInfo.compareEndPoints(targetCopy, "startToStart") < 0:
			moved = startInfo.move(textInfos.UNIT_LINE, 1)
			if moved == 0:
				break
			lineCount += 1

		buffer_row = lineCount + 1

		# Compensate for scrollback on conhost.  Only do the expensive
		# POSITION_ALL read when the terminal actually needs it — Windows
		# Terminal is already viewport-relative, so we skip the extra UIA call.
		if self._needs_scrollback_compensation(terminal):
			total_lines = 1
			try:
				all_info = terminal.makeTextInfo(textInfos.POSITION_ALL)
				all_text = all_info.text
				if all_text:
					total_lines = all_text.count('\n') + 1
			except Exception:
				pass
			row = self._to_viewport_row(buffer_row, total_lines, terminal)
		else:
			row = buffer_row

		# Calculate column by counting characters from line start
		lineStart = targetCopy.copy()
		lineStart.expand(textInfos.UNIT_LINE)
		lineStart.collapse()

		# Create range from line start to target and count characters
		charRange = lineStart.copy()
		charRange.setEndPoint(targetCopy, "endToEnd")
		charsFromLineStart = len(charRange.text) if charRange.text else 0
		col = charsFromLineStart + 1

		# Cache and store
		self._cache.set(bookmark, row, col)
		self._last_known_position = (bookmark, row, col)

		return (row, col)

	def clear_cache(self) -> None:
		"""Clear all cached positions."""
		self._cache.clear()
		self._last_known_position = None

	def invalidate_position(self, bookmark: Any) -> None:
		"""
		Invalidate a specific cached position.

		Args:
			bookmark: TextInfo bookmark to invalidate
		"""
		self._cache.invalidate(bookmark)


class WindowMonitor:
	"""
	Monitor multiple windows for content changes with background polling.

	Section 6.1: Multiple Simultaneous Window Monitoring (v1.0.28+)

	This class enables monitoring of multiple terminal windows/regions simultaneously,
	detecting changes and announcing them to the user. Useful for monitoring:
	- Build output in split panes
	- Log file tails in tmux/screen
	- System status bars
	- Chat messages in IRC clients
	- Background processes

	Features:
	- Multiple simultaneous window monitoring
	- Configurable polling intervals per window
	- Change detection with diff strategies
	- Rate limiting to prevent announcement spam
	- Background thread-based monitoring
	- Thread-safe operations

	Example usage:
		>>> monitor = WindowMonitor(terminal_obj, position_calculator)
		>>> monitor.add_monitor("build", (1, 1, 10, 80), interval_ms=1000)
		>>> monitor.add_monitor("logs", (11, 1, 20, 80), interval_ms=500)
		>>> monitor.start_monitoring()
		>>> # ... monitoring runs in background ...
		>>> monitor.stop_monitoring()
	"""

	def __init__(self, terminal_obj, position_calculator, debounce_ms=100):
		"""
		Initialize the WindowMonitor.

		Args:
			terminal_obj: Terminal TextInfo object for content extraction
			position_calculator: PositionCalculator instance for coordinate mapping
			debounce_ms: Debounce interval in milliseconds (default 100).
				Rapid updates arriving within this interval are coalesced
				so only the last one is announced.
		"""
		self._terminal = terminal_obj
		self._position_calculator = position_calculator  # Reserved for future content extraction by coordinates
		self._monitors = []  # List of monitor configurations
		self._last_content = {}  # window_name -> content mapping
		self._last_announcement = {}  # window_name -> timestamp of last announcement
		self._monitor_thread = None
		self._monitoring_active = False
		self._lock = threading.Lock()
		self._min_announcement_interval = 2000  # Minimum 2 seconds between announcements (rate limiting)
		self._debounce_ms = debounce_ms
		self._debounce_pending = {}  # window_name -> (content, timestamp)
		self._debounce_last_announced = {}  # window_name -> last announced content

	def add_monitor(self, name: str, window_bounds: tuple, interval_ms: int = 500, mode: str = 'changes'):
		"""
		Add a window to monitor.

		Args:
			name: Unique identifier for this monitor
			window_bounds: Tuple of (top, left, bottom, right) coordinates (1-based)
			interval_ms: Polling interval in milliseconds (default: 500ms)
			mode: Announcement mode - 'changes' (announce changes), 'silent' (track only)

		Returns:
			bool: True if monitor added successfully
		"""
		with self._lock:
			# Check if monitor with this name already exists
			if any(m['name'] == name for m in self._monitors):
				return False

			# Validate window bounds
			top, left, bottom, right = window_bounds
			if not (1 <= top <= bottom and 1 <= left <= right):
				return False

			monitor = {
				'name': name,
				'bounds': window_bounds,
				'interval': interval_ms,
				'mode': mode,
				'last_check': 0,
				'enabled': True,
				'differ': _rt.make_text_differ(),  # Per-monitor differ for change detection
			}
			self._monitors.append(monitor)
			self._last_content[name] = None
			self._last_announcement[name] = 0
			return True

	def remove_monitor(self, name: str) -> bool:
		"""
		Remove a monitor by name.

		Args:
			name: Monitor identifier

		Returns:
			bool: True if monitor removed successfully
		"""
		with self._lock:
			for i, monitor in enumerate(self._monitors):
				if monitor['name'] == name:
					self._monitors.pop(i)
					self._last_content.pop(name, None)
					self._last_announcement.pop(name, None)
					return True
			return False

	def enable_monitor(self, name: str) -> bool:
		"""Enable a specific monitor."""
		with self._lock:
			for monitor in self._monitors:
				if monitor['name'] == name:
					monitor['enabled'] = True
					return True
			return False

	def disable_monitor(self, name: str) -> bool:
		"""Disable a specific monitor."""
		with self._lock:
			for monitor in self._monitors:
				if monitor['name'] == name:
					monitor['enabled'] = False
					return True
			return False

	def start_monitoring(self) -> bool:
		"""
		Start background monitoring thread.

		Returns:
			bool: True if monitoring started successfully
		"""
		with self._lock:
			if self._monitoring_active:
				return False

			if not self._monitors:
				return False

			self._monitoring_active = True
			self._monitor_thread = threading.Thread(
				target=self._monitor_loop,
				daemon=True
			)
			self._monitor_thread.start()
			return True

	def stop_monitoring(self) -> None:
		"""Stop background monitoring thread."""
		with self._lock:
			self._monitoring_active = False

		# Wait for thread to finish
		if self._monitor_thread and self._monitor_thread.is_alive():
			self._monitor_thread.join(timeout=2.0)
		self._monitor_thread = None

	def is_monitoring(self) -> bool:
		"""Check if monitoring is active."""
		with self._lock:
			return self._monitoring_active

	def _monitor_loop(self) -> None:
		"""Background monitoring loop."""
		while True:
			# Collect monitors that are due for a check while holding the
			# lock, then release it *before* any I/O.  _check_window calls
			# _read_terminal_text_on_main which blocks waiting for the main
			# thread -- holding the lock during that call would deadlock if
			# the main thread tried to acquire it (e.g. stop_monitoring).
			due_monitors = []
			with self._lock:
				if not self._monitoring_active:
					break

				current_time = time.time() * 1000  # Convert to milliseconds

				for monitor in self._monitors:
					if not monitor['enabled']:
						continue
					time_since_check = current_time - monitor['last_check']
					if time_since_check >= monitor['interval']:
						due_monitors.append(monitor)

			# Perform I/O outside the lock to avoid deadlock.
			for monitor in due_monitors:
				current_time = time.time() * 1000
				self._check_window(monitor, current_time)
				monitor['last_check'] = current_time

			# Sleep briefly to avoid busy-waiting
			time.sleep(0.1)

	def _check_window(self, monitor: dict, current_time: float) -> None:
		"""
		Check if window content changed using TextDiffer.

		For appended output (the common case) only the new lines are announced.
		For non-trivial changes (screen clears, edits in the middle) the
		full region content is announced.

		Args:
			monitor: Monitor configuration dictionary
			current_time: Current timestamp in milliseconds
		"""
		try:
			# Extract window content
			content = self._extract_window_content(monitor['bounds'])
			name = monitor['name']

			# Use per-monitor TextDiffer for change detection
			differ: TextDiffer = monitor['differ']
			kind, new_content = differ.update(content)

			# Nothing to do for initial snapshot or unchanged content
			if kind in (TextDiffer.KIND_INITIAL, TextDiffer.KIND_UNCHANGED):
				return

			# Keep legacy _last_content dict in sync for external callers
			self._last_content[name] = content

			# Only announce in 'changes' mode and when rate-limit allows it
			if monitor['mode'] != 'changes':
				return

			time_since_announcement = current_time - self._last_announcement.get(name, 0)
			if time_since_announcement < self._min_announcement_interval:
				return

			if kind == TextDiffer.KIND_APPENDED:
				# Speak only the newly appended portion
				self._announce_change(name, new_content, content)
			else:
				# Non-trivial change (clear / mid-edit): speak the full region
				self._announce_change(name, content, None)
			self._last_announcement[name] = current_time

		except Exception:
			# Silently ignore errors to avoid disrupting monitoring
			pass

	def _extract_window_content(self, bounds: tuple) -> str:
		"""
		Extract text content from window bounds.

		Args:
			bounds: Tuple of (top, left, bottom, right) coordinates

		Returns:
			str: Window content as text
		"""
		if not self._terminal:
			return ""

		top, left, bottom, right = bounds
		lines = []

		try:
			# Uses helper process if available; falls back to main-thread marshaling.
			all_text = _rt.read_terminal_text(self._terminal)
			if all_text is None:
				return ""

			# Split into lines
			all_lines = all_text.split('\n')

			# Extract lines within bounds (convert from 1-based to 0-based)
			for row_idx in range(top - 1, min(bottom, len(all_lines))):
				if row_idx < len(all_lines):
					line = all_lines[row_idx]
					# Extract columns within bounds (1-based to 0-based)
					col_start = max(0, left - 1)
					col_end = min(len(line), right)
					lines.append(line[col_start:col_end])

			return '\n'.join(lines)

		except Exception:
			return ""

	def _announce_change(self, name: str, new_content: str, old_content) -> None:
		"""
		Announce content change to user.

		When called with the appended text as *new_content* and the full
		region as *old_content*, the appended text is spoken directly.
		When *old_content* is ``None`` (non-trivial change / full region), a
		brief summary is spoken instead.

		Args:
			name: Monitor name
			new_content: Appended text or full region content
			old_content: Previous window content, or None for non-trivial changes
		"""
		try:
			if old_content is None:
				# Non-trivial change (clear / edit): speak the region content
				text = new_content.strip()
				if text:
					ui.message(text)
			else:
				# Appended output: speak only the new portion
				text = new_content.strip()
				if text:
					ui.message(text)
		except Exception:
			pass

	def debounce_update(self, name: str, content: str) -> None:
		"""
		Submit a content update with debouncing.

		If updates arrive faster than the debounce interval, only the
		latest content is announced once the interval elapses. Identical
		content is suppressed entirely.

		Args:
			name: Monitor/window name
			content: New content text
		"""
		now = time.time() * 1000  # milliseconds

		# Suppress identical content
		if self._debounce_last_announced.get(name) == content:
			return

		last_pending = self._debounce_pending.get(name)
		if last_pending is not None:
			_, pending_time = last_pending
			elapsed = now - pending_time
			if elapsed < self._debounce_ms:
				# Within debounce window: replace pending content, don't announce yet
				self._debounce_pending[name] = (content, now)
				return

		# Either no pending update or debounce interval elapsed: announce
		self._debounce_pending[name] = (content, now)
		self._debounce_last_announced[name] = content
		self._announce_change(name, content, None)

	def get_monitor_status(self) -> list:
		"""
		Get status of all monitors.

		Returns:
			list: List of monitor status dictionaries
		"""
		with self._lock:
			return [
				{
					'name': m['name'],
					'bounds': m['bounds'],
					'interval': m['interval'],
					'mode': m['mode'],
					'enabled': m['enabled']
				}
				for m in self._monitors
			]
