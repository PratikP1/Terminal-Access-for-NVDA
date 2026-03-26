"""Tests for ErrorLineDetector — error/warning keyword detection in terminal lines."""

import pytest
from unittest.mock import MagicMock
from lib.text_processing import ErrorLineDetector


class TestErrorLineDetector:
	def setup_method(self):
		self.detector = ErrorLineDetector()

	# -- Real errors that MUST trigger --

	def test_gcc_error(self):
		assert self.detector.classify("main.c:5:12: error: expected ';' before 'int'") == "error"

	def test_gcc_warning(self):
		assert self.detector.classify("main.c:5:12: warning: unused variable 'x' [-Wunused]") == "warning"

	def test_clang_fatal_error(self):
		assert self.detector.classify("test.c:1:10: fatal error: 'missing.h' file not found") == "error"

	def test_msvc_error(self):
		assert self.detector.classify("main.cpp(15,5) : error C2001: newline in constant") == "error"

	def test_msvc_warning(self):
		assert self.detector.classify("main.cpp(15,5) : warning C4996: deprecated function") == "warning"

	def test_rust_error(self):
		assert self.detector.classify("error[E0308]: expected `i32`, found `&str`") == "error"

	def test_rust_warning(self):
		assert self.detector.classify("warning: unused variable: `x`") == "warning"

	def test_python_traceback(self):
		assert self.detector.classify("Traceback (most recent call last):") == "error"

	def test_python_exception(self):
		assert self.detector.classify("ValueError: invalid literal for int()") == "error"

	def test_python_syntax_error(self):
		assert self.detector.classify("SyntaxError: invalid syntax") == "error"

	def test_pytest_failed(self):
		assert self.detector.classify("FAILED tests/test_main.py::test_login - AssertionError") == "error"

	def test_mypy_error(self):
		assert self.detector.classify("script.py:5: error: Name 'x' is not defined [name-defined]") == "error"

	def test_typescript_error(self):
		assert self.detector.classify("error TS2322: Type 'string' is not assignable to type 'number'.") == "error"

	def test_eslint_error(self):
		assert self.detector.classify("  3:16  error  Unexpected space before unary operator  space-unary-ops") == "error"

	def test_eslint_warning(self):
		assert self.detector.classify("  3:16  warning  Unexpected console statement  no-console") == "warning"

	def test_node_error(self):
		assert self.detector.classify("Error: Cannot find module 'express'") == "error"

	def test_git_fatal(self):
		assert self.detector.classify("fatal: 'origin' does not appear to be a git repository") == "error"

	def test_git_error(self):
		assert self.detector.classify("error: Your local changes would be overwritten") == "error"

	def test_git_warning(self):
		assert self.detector.classify("warning: refname 'main' is ambiguous") == "warning"

	def test_maven_error(self):
		assert self.detector.classify("[ERROR] Failed to execute goal") == "error"

	def test_maven_warning(self):
		assert self.detector.classify("[WARNING] Using platform encoding") == "warning"

	def test_bash_permission_denied(self):
		assert self.detector.classify("bash: ./script.sh: Permission denied") == "error"

	def test_bash_command_not_found(self):
		assert self.detector.classify("bash: foo: command not found") == "error"

	def test_bash_no_such_file(self):
		assert self.detector.classify("ls: cannot access '/missing': No such file or directory") == "error"

	def test_npm_err(self):
		assert self.detector.classify("npm ERR! 404 Not Found") == "error"

	def test_docker_error(self):
		assert self.detector.classify("ERROR: COPY failed: forbidden path") == "error"

	def test_make_error(self):
		assert self.detector.classify("make: *** [Makefile:10: all] Error 2") == "error"

	def test_cmake_error(self):
		assert self.detector.classify("CMake Error at CMakeLists.txt:5:") == "error"

	def test_cmake_warning(self):
		assert self.detector.classify("CMake Warning at CMakeLists.txt:5:") == "warning"

	def test_gradle_failure(self):
		assert self.detector.classify("FAILURE: Build failed with an exception.") == "error"

	def test_go_build_error_with_keyword(self):
		"""Go errors with explicit 'error' keyword are detected."""
		assert self.detector.classify("main.go:10: error: undefined reference") == "error"

	def test_go_build_bare_message_not_detected(self):
		"""Go errors without 'error' keyword can't be reliably distinguished from grep output."""
		# ./main.go:10:5: undefined: fmt — no "error" keyword
		# Same format as grep -n output, so we can't detect it without false positives.
		assert self.detector.classify("./main.go:10:5: undefined: fmt") is None

	def test_java_error(self):
		assert self.detector.classify("Main.java:5: error: ';' expected") == "error"

	def test_java_warning(self):
		assert self.detector.classify("Main.java:5: warning: [deprecation] method deprecated") == "warning"

	def test_pylint_error(self):
		assert self.detector.classify("main.py:12: E0001: Parsing failed (syntax-error)") == "error"

	def test_flake8_error(self):
		assert self.detector.classify("main.py:1:1: E302 expected 2 blank lines") == "error"

	def test_connection_refused(self):
		assert self.detector.classify("Connection refused") == "error"

	def test_segfault(self):
		assert self.detector.classify("Segmentation fault (core dumped)") == "error"

	def test_panic(self):
		assert self.detector.classify("panic: runtime error: index out of range") == "error"

	def test_deprecated_warning(self):
		assert self.detector.classify("DeprecationWarning: old API is deprecated") == "warning"

	# -- FALSE POSITIVES that must NOT trigger --

	def test_no_false_positive_mirror(self):
		"""'mirror' contains 'error' as substring — must not trigger."""
		assert self.detector.classify("Downloading from mirror.example.com") is None

	def test_no_false_positive_terrorist(self):
		"""'terrorist' contains 'error' substring — must not trigger."""
		assert self.detector.classify("counterterrorist operations") is None

	def test_no_false_positive_canonical(self):
		"""'canonical' contains 'cannot' substring — must not trigger."""
		assert self.detector.classify("The canonical form of the URL") is None

	def test_no_false_positive_forewarning(self):
		"""'forewarning' contains 'warning' substring — must not trigger."""
		assert self.detector.classify("This was a forewarning of things to come") is None

	def test_no_false_positive_earring(self):
		"""'earring' contains 'err' — must not trigger."""
		assert self.detector.classify("She wore a gold earring") is None

	def test_no_false_positive_errand(self):
		"""'errand' contains 'err' — must not trigger."""
		assert self.detector.classify("Running an errand downtown") is None

	def test_no_false_positive_aterra(self):
		"""'terra' won't match but 'error' inside other words should not."""
		assert self.detector.classify("The terra firma was solid") is None

	def test_no_false_positive_warned(self):
		"""'warned' contains 'warn' — must not trigger."""
		assert self.detector.classify("I warned you about this") is None

	def test_no_false_positive_rewarning(self):
		assert self.detector.classify("rewarning the system") is None

	def test_no_false_positive_unable_to_prose(self):
		"""'unable to' in normal prose — no trigger."""
		assert self.detector.classify("He was unable to attend the meeting") is None

	def test_no_false_positive_help_text_cannot(self):
		"""Help text with 'cannot' in normal prose — no trigger."""
		assert self.detector.classify("This option cannot be used with --verbose") is None

	def test_no_false_positive_man_page(self):
		"""Man page text with 'not found' in explanatory context — no trigger."""
		assert self.detector.classify("If no match is found, the exit status is 1") is None

	def test_no_false_positive_refused_normal(self):
		"""'refused' in normal context — check it carefully."""
		assert self.detector.classify("He refused the offer politely") is None

	def test_no_false_positive_failures_noun(self):
		"""'failures' as a noun in normal context."""
		assert self.detector.classify("The report documents past failures and successes") is None

	# -- Normal output that must not trigger --

	def test_normal_git_status(self):
		assert self.detector.classify("$ git status") is None

	def test_normal_ls_output(self):
		assert self.detector.classify("drwxr-xr-x 2 user group 4096 Jan 1 readme.md") is None

	def test_normal_python_version(self):
		assert self.detector.classify("Python 3.11.5") is None

	def test_normal_prompt(self):
		assert self.detector.classify("user@host:~$") is None

	def test_normal_pip_success(self):
		assert self.detector.classify("Successfully installed requests-2.31.0") is None

	def test_empty_line(self):
		assert self.detector.classify("") is None

	def test_none(self):
		assert self.detector.classify(None) is None

	def test_error_takes_priority_over_warning(self):
		assert self.detector.classify("error: deprecated warning here") == "error"


class TestErrorLineDetectorSetting:
	"""Audio cues must be controlled by a setting."""

	def test_setting_exists_in_confspec(self):
		"""errorAudioCues setting must exist in the config spec."""
		from lib.config import confspec
		assert "errorAudioCues" in confspec, (
			"errorAudioCues setting must exist for users to disable audio cues"
		)

	def test_beep_skipped_when_setting_disabled(self):
		"""When errorAudioCues is False, no beep should play."""
		import tones
		tones.beep = MagicMock()

		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		plugin._configManager.set("errorAudioCues", False)

		pos = MagicMock()
		line_info = MagicMock()
		line_info.text = "ERROR: something went wrong"
		pos.copy.return_value = line_info
		plugin._getReviewPosition = MagicMock(return_value=pos)

		gesture = MagicMock()
		move_fn = MagicMock()
		plugin._readLineWithIndentation(gesture, move_fn)

		tones.beep.assert_not_called()


class TestErrorLineDetectorTiming:
	"""Beep plays after moveFunction because we need the new line's text."""

	def test_beep_plays_after_move_for_correct_line(self):
		"""Audio cue must play for the line we navigated TO, not FROM.

		moveFunction moves the review cursor and speaks the line.
		The beep must use the text at the new position, so it plays
		immediately after moveFunction.
		"""
		import tones

		call_order = []
		tones.beep = MagicMock(side_effect=lambda *a: call_order.append('beep'))

		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)

		pos = MagicMock()
		line_info = MagicMock()
		line_info.text = "ERROR: something broke"
		pos.copy.return_value = line_info
		plugin._getReviewPosition = MagicMock(return_value=pos)

		gesture = MagicMock()
		move_fn = MagicMock(side_effect=lambda g: call_order.append('speak'))

		plugin._readLineWithIndentation(gesture, move_fn)

		assert 'speak' in call_order, "moveFunction must be called"
		assert 'beep' in call_order, "Beep must play for error line"
		assert call_order.index('speak') < call_order.index('beep'), (
			f"moveFunction must run first (to move cursor), then beep. Order: {call_order}"
		)


class TestErrorLineDetectorIntegration:
	"""Test that ErrorLineDetector is actually called during line navigation."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		return plugin

	def _setup_review_position(self, plugin, line_text):
		import textInfos
		pos = MagicMock()
		line_info = MagicMock()
		line_info.text = line_text
		pos.copy.return_value = line_info
		plugin._getReviewPosition = MagicMock(return_value=pos)
		return pos

	def test_error_line_triggers_low_beep(self):
		import tones
		tones.beep = MagicMock()
		plugin = self._make_plugin()
		self._setup_review_position(plugin, "ERROR: something went wrong")
		gesture = MagicMock()
		move_fn = MagicMock()
		plugin._readLineWithIndentation(gesture, move_fn)
		tones.beep.assert_called_once_with(220, 50)

	def test_warning_line_triggers_high_beep(self):
		import tones
		tones.beep = MagicMock()
		plugin = self._make_plugin()
		self._setup_review_position(plugin, "warning: deprecated function used")
		gesture = MagicMock()
		move_fn = MagicMock()
		plugin._readLineWithIndentation(gesture, move_fn)
		tones.beep.assert_called_once_with(440, 30)

	def test_normal_line_no_beep(self):
		import tones
		tones.beep = MagicMock()
		plugin = self._make_plugin()
		self._setup_review_position(plugin, "total 42")
		gesture = MagicMock()
		move_fn = MagicMock()
		plugin._readLineWithIndentation(gesture, move_fn)
		tones.beep.assert_not_called()

	def test_moveFunction_is_called(self):
		import tones
		tones.beep = MagicMock()
		plugin = self._make_plugin()
		self._setup_review_position(plugin, "ERROR: test")
		gesture = MagicMock()
		move_fn = MagicMock()
		plugin._readLineWithIndentation(gesture, move_fn)
		move_fn.assert_called_once_with(gesture)

	def test_error_detector_uses_real_instance(self):
		from lib.text_processing import ErrorLineDetector
		plugin = self._make_plugin()
		assert isinstance(plugin._errorDetector, ErrorLineDetector)


class TestErrorCueContextBehavior:
	"""Error audio cues must behave differently depending on context."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		return plugin

	def _make_terminal_obj(self, line_text):
		"""Create a mock terminal object whose caret is on a line with given text."""
		import textInfos
		obj = MagicMock()
		obj.appModule = MagicMock()
		obj.appModule.appName = "windowsterminal"

		text_info = MagicMock()
		text_info.text = line_text
		text_info.copy.return_value = text_info
		text_info.expand = MagicMock()

		obj.makeTextInfo = MagicMock(return_value=text_info)
		return obj

	# -- Cursor tracking (non-quiet) should NOT beep --

	def test_no_beep_during_cursor_tracking(self):
		"""Cursor tracking auto-announces should not trigger error beeps.

		Rapid output (apt install, cargo build) would flood beeps.
		"""
		import tones
		tones.beep = MagicMock()

		plugin = self._make_plugin()
		obj = self._make_terminal_obj("ERROR: something failed")
		plugin._boundTerminal = obj

		# Simulate cursor tracking announcement
		plugin._announceCursorPosition = MagicMock()
		plugin.event_caret(obj, lambda: None)

		tones.beep.assert_not_called()

	# -- Quiet mode + setting enabled: beep on error lines --

	def test_quiet_mode_setting_exists(self):
		"""errorAudioCuesInQuietMode setting must exist in confspec."""
		from lib.config import confspec
		assert "errorAudioCuesInQuietMode" in confspec, (
			"errorAudioCuesInQuietMode setting must exist"
		)

	def test_quiet_mode_beep_on_error_when_enabled(self):
		"""In quiet mode with setting enabled, overlay checks for error cues."""
		from unittest.mock import patch, Mock
		from lib.terminal_overlay import TerminalAccessTerminal

		obj = TerminalAccessTerminal()
		obj._event = Mock()
		obj._configManager = Mock()
		obj._configManager.get = Mock(side_effect=lambda k, d=None: {
			"quietMode": True,
			"errorAudioCuesInQuietMode": True,
			"errorAudioCues": True,
			"outputActivityTones": False,
		}.get(k, d))
		obj._checkErrorAudioCue = Mock()

		obj.event_textChange()

		obj._checkErrorAudioCue.assert_called_once()
		obj._event.set.assert_not_called()

	def test_quiet_mode_no_beep_when_setting_disabled(self):
		"""In quiet mode with setting disabled, no beep even on error lines."""
		from unittest.mock import Mock
		from lib.terminal_overlay import TerminalAccessTerminal

		obj = TerminalAccessTerminal()
		obj._event = Mock()
		obj._configManager = Mock()
		obj._configManager.get = Mock(side_effect=lambda k, d=None: {
			"quietMode": True,
			"errorAudioCuesInQuietMode": False,
			"errorAudioCues": True,
			"outputActivityTones": False,
		}.get(k, d))
		obj._checkErrorAudioCue = Mock()

		obj.event_textChange()

		obj._checkErrorAudioCue.assert_not_called()

	def test_quiet_mode_no_speech_only_beep(self):
		"""In quiet mode, overlay does not wake monitor thread (no speech)."""
		from unittest.mock import Mock
		from lib.terminal_overlay import TerminalAccessTerminal

		obj = TerminalAccessTerminal()
		obj._event = Mock()
		obj._configManager = Mock()
		obj._configManager.get = Mock(side_effect=lambda k, d=None: {
			"quietMode": True,
			"errorAudioCues": False,
			"errorAudioCuesInQuietMode": False,
			"outputActivityTones": False,
		}.get(k, d))

		obj.event_textChange()

		obj._event.set.assert_not_called()

	def test_quiet_mode_warning_beep(self):
		"""Warning lines produce 440 Hz via overlay _reportNewLines."""
		from unittest.mock import patch, Mock, MagicMock
		from lib.terminal_overlay import TerminalAccessTerminal

		obj = TerminalAccessTerminal()
		obj._configManager = Mock()
		obj._configManager.get = Mock(side_effect=lambda k, d=None: {
			"errorAudioCues": True,
		}.get(k, d))

		mock_tones = MagicMock()
		with patch("lib.terminal_overlay.tones", mock_tones):
			obj._reportNewLines(["warning: deprecated function"])
			mock_tones.beep.assert_called_once_with(440, 30)

	def test_quiet_mode_normal_line_no_beep(self):
		"""In quiet mode, normal lines should produce no beep."""
		import tones
		import config as config_mod
		tones.beep = MagicMock()

		plugin = self._make_plugin()
		config_mod.conf["terminalAccess"]["quietMode"] = True
		config_mod.conf["terminalAccess"]["errorAudioCuesInQuietMode"] = True
		config_mod.conf["terminalAccess"]["errorAudioCues"] = True

		obj = self._make_terminal_obj("total 42")
		plugin._boundTerminal = obj

		pos = MagicMock()
		line_info = MagicMock()
		line_info.text = "total 42"
		pos.copy.return_value = line_info
		plugin._getReviewPosition = MagicMock(return_value=pos)

		plugin.event_caret(obj, lambda: None)

		tones.beep.assert_not_called()


class TestOutputActivityTones:
	"""Two ascending tones when new output appears on screen."""

	def _make_plugin(self):
		from globalPlugins.terminalAccess import GlobalPlugin
		plugin = GlobalPlugin()
		plugin.isTerminalApp = MagicMock(return_value=True)
		return plugin

	def _make_terminal_obj(self):
		obj = MagicMock()
		obj.appModule = MagicMock()
		obj.appModule.appName = "windowsterminal"
		return obj

	def test_setting_exists(self):
		"""outputActivityTones setting must exist in confspec."""
		from lib.config import confspec
		assert "outputActivityTones" in confspec

	def test_activity_tone_on_new_output(self):
		"""Two ascending tones via overlay event_textChange."""
		from unittest.mock import patch, Mock, MagicMock
		from lib.terminal_overlay import TerminalAccessTerminal

		obj = TerminalAccessTerminal()
		obj._event = Mock()
		obj._configManager = Mock()
		obj._configManager.get = Mock(side_effect=lambda k, d=None: {
			"quietMode": False,
			"outputActivityTones": True,
			"outputActivityDebounce": 1000,
		}.get(k, d))
		obj._lastActivityToneTime = 0
		obj._lastTypedCharTime = 0

		mock_tones = MagicMock()
		with patch("lib.terminal_overlay.tones", mock_tones):
			obj.event_textChange()
			assert mock_tones.beep.call_count == 2
			first = mock_tones.beep.call_args_list[0][0][0]
			second = mock_tones.beep.call_args_list[1][0][0]
			assert first < second

	def test_no_activity_tone_when_setting_disabled(self):
		"""No activity tones when outputActivityTones is False."""
		import tones
		import config as config_mod
		tones.beep = MagicMock()

		plugin = self._make_plugin()
		config_mod.conf["terminalAccess"]["outputActivityTones"] = False
		config_mod.conf["terminalAccess"]["quietMode"] = True

		obj = self._make_terminal_obj()
		plugin._boundTerminal = obj
		plugin._lastTypedCharTime = 0.0
		plugin._lastOutputActivityTime = 0.0

		plugin.event_caret(obj, lambda: None)

		tones.beep.assert_not_called()

	def test_no_activity_tone_during_typing(self):
		"""Activity tones should not play when user is typing (echo, not output)."""
		import tones
		import time
		import config as config_mod
		tones.beep = MagicMock()

		plugin = self._make_plugin()
		config_mod.conf["terminalAccess"]["outputActivityTones"] = True
		config_mod.conf["terminalAccess"]["quietMode"] = True

		obj = self._make_terminal_obj()
		plugin._boundTerminal = obj

		# User just typed (within grace period)
		plugin._lastTypedCharTime = time.time()
		plugin._lastOutputActivityTime = 0.0

		plugin.event_caret(obj, lambda: None)

		tones.beep.assert_not_called()

	def test_no_repeated_tones_during_burst(self):
		"""Activity tones debounce on rapid textChange events via overlay."""
		import time
		from unittest.mock import patch, Mock, MagicMock
		from lib.terminal_overlay import TerminalAccessTerminal

		obj = TerminalAccessTerminal()
		obj._event = Mock()
		obj._configManager = Mock()
		obj._configManager.get = Mock(side_effect=lambda k, d=None: {
			"quietMode": False,
			"outputActivityTones": True,
			"outputActivityDebounce": 1000,
		}.get(k, d))
		obj._lastActivityToneTime = 0
		obj._lastTypedCharTime = 0

		mock_tones = MagicMock()
		with patch("lib.terminal_overlay.tones", mock_tones):
			obj.event_textChange()
			assert mock_tones.beep.call_count == 2

			mock_tones.beep.reset_mock()
			obj.event_textChange()
			mock_tones.beep.assert_not_called()

	def test_activity_tones_distinct_from_error(self):
		"""Activity tones must use different frequencies than error/warning."""
		import tones
		import config as config_mod
		tones.beep = MagicMock()

		plugin = self._make_plugin()
		config_mod.conf["terminalAccess"]["outputActivityTones"] = True
		config_mod.conf["terminalAccess"]["quietMode"] = True

		obj = self._make_terminal_obj()
		plugin._boundTerminal = obj
		plugin._lastTypedCharTime = 0.0
		plugin._lastOutputActivityTime = 0.0

		plugin.event_caret(obj, lambda: None)

		# Activity tones must not be 220 Hz (error) or 440 Hz (warning)
		for call in tones.beep.call_args_list:
			freq = call[0][0]
			assert freq not in (220, 440), (
				f"Activity tone {freq} Hz conflicts with error/warning tones"
			)

	def test_debounce_setting_exists(self):
		"""outputActivityDebounce setting must exist in confspec."""
		from lib.config import confspec
		assert "outputActivityDebounce" in confspec

	def test_custom_debounce_interval(self):
		"""User-configured debounce interval controls repeat suppression via overlay."""
		import time
		from unittest.mock import patch, Mock, MagicMock
		from lib.terminal_overlay import TerminalAccessTerminal

		obj = TerminalAccessTerminal()
		obj._event = Mock()
		obj._configManager = Mock()
		obj._configManager.get = Mock(side_effect=lambda k, d=None: {
			"quietMode": False,
			"outputActivityTones": True,
			"outputActivityDebounce": 5000,
		}.get(k, d))
		obj._lastTypedCharTime = 0

		mock_tones = MagicMock()
		with patch("lib.terminal_overlay.tones", mock_tones):
			obj._lastActivityToneTime = 0
			obj.event_textChange()
			assert mock_tones.beep.call_count == 2

			mock_tones.beep.reset_mock()
			obj._lastActivityToneTime = time.time() - 2.0
			obj.event_textChange()
			mock_tones.beep.assert_not_called()

			mock_tones.beep.reset_mock()
			obj._lastActivityToneTime = time.time() - 6.0
			obj.event_textChange()
			assert mock_tones.beep.call_count == 2

	def test_activity_tones_in_normal_mode_when_enabled(self):
		"""Activity tones work in normal mode via overlay event_textChange."""
		from unittest.mock import patch, Mock, MagicMock
		from lib.terminal_overlay import TerminalAccessTerminal

		obj = TerminalAccessTerminal()
		obj._event = Mock()
		obj._configManager = Mock()
		obj._configManager.get = Mock(side_effect=lambda k, d=None: {
			"quietMode": False,
			"outputActivityTones": True,
			"outputActivityDebounce": 1000,
		}.get(k, d))
		obj._lastActivityToneTime = 0
		obj._lastTypedCharTime = 0

		mock_tones = MagicMock()
		with patch("lib.terminal_overlay.tones", mock_tones):
			obj.event_textChange()
			assert mock_tones.beep.call_count >= 2
