# TDSR for NVDA - Global Plugin
# Copyright (C) 2024 TDSR for NVDA Contributors
# This add-on is covered by the GNU General Public License, version 3.
# See the file LICENSE for more details.

"""
TDSR (Terminal Data Structure Reader) Global Plugin for NVDA

This plugin provides enhanced accessibility features for Windows Terminal and PowerShell,
including navigation by line/word/character, cursor tracking, and symbol processing.
"""

import globalPluginHandler
import api
import ui
import config
import gui
import textInfos
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel
import addonHandler
import wx
import os
from scriptHandler import script
import scriptHandler
import globalCommands
import speech

try:
	addonHandler.initTranslation()
except:
	pass

# Cursor tracking mode constants
CT_OFF = 0
CT_STANDARD = 1
CT_HIGHLIGHT = 2
CT_WINDOW = 3

# Punctuation level constants and sets
PUNCT_NONE = 0
PUNCT_SOME = 1
PUNCT_MOST = 2
PUNCT_ALL = 3

# Punctuation character sets for each level
PUNCTUATION_SETS = {
	PUNCT_NONE: set(),  # No punctuation
	PUNCT_SOME: set('.,?!;:'),  # Basic punctuation
	PUNCT_MOST: set('.,?!;:@#$%^&*()_+=[]{}\\|<>/'),  # Most punctuation
	PUNCT_ALL: None  # All punctuation (process everything)
}

# Configuration spec for TDSR settings
confspec = {
	"cursorTracking": "boolean(default=True)",
	"cursorTrackingMode": "integer(default=1, min=0, max=3)",  # 0=Off, 1=Standard, 2=Highlight, 3=Window
	"keyEcho": "boolean(default=True)",
	"linePause": "boolean(default=True)",
	"processSymbols": "boolean(default=False)",  # Deprecated, use punctuationLevel
	"punctuationLevel": "integer(default=2, min=0, max=3)",  # 0=None, 1=Some, 2=Most, 3=All
	"repeatedSymbols": "boolean(default=False)",
	"repeatedSymbolsValues": "string(default='-_=!')",
	"cursorDelay": "integer(default=20, min=0, max=1000)",
	"quietMode": "boolean(default=False)",
	"windowTop": "integer(default=0, min=0)",
	"windowBottom": "integer(default=0, min=0)",
	"windowLeft": "integer(default=0, min=0)",
	"windowRight": "integer(default=0, min=0)",
	"windowEnabled": "boolean(default=False)",
}

# Register configuration
config.conf.spec["TDSR"] = confspec


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""
	TDSR Global Plugin for NVDA
	
	Provides terminal accessibility enhancements for Windows Terminal and PowerShell.
	"""
	
	def __init__(self):
		"""Initialize the TDSR global plugin."""
		super(GlobalPlugin, self).__init__()

		# Migrate old processSymbols setting to punctuationLevel (one-time migration)
		if "processSymbols" in config.conf["TDSR"] and "punctuationLevel" not in config.conf["TDSR"]:
			oldValue = config.conf["TDSR"]["processSymbols"]
			# True -> Level 2 (most punctuation), False -> Level 0 (no punctuation)
			config.conf["TDSR"]["punctuationLevel"] = PUNCT_MOST if oldValue else PUNCT_NONE

		# Initialize state variables
		self.lastTerminalAppName = None
		self.announcedHelp = False
		self.selectionStart = None
		self.copyMode = False
		self._boundTerminal = None
		self._cursorTrackingTimer = None
		self._lastCaretPosition = None
		self._lastTypedChar = None
		self._repeatedCharCount = 0

		# Window definition state
		self._windowDefining = False
		self._windowStartSet = False

		# Highlight tracking state
		self._lastHighlightedText = None
		self._lastHighlightPosition = None

		# Enhanced selection state
		self._markStart = None
		self._markEnd = None

		# Add settings panel to NVDA preferences
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(TDSRSettingsPanel)
	
	def terminate(self):
		"""Clean up when the plugin is terminated."""
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(TDSRSettingsPanel)
		except:
			pass
		super(GlobalPlugin, self).terminate()
	
	def isTerminalApp(self, obj=None):
		"""
		Check if the current application is a supported terminal.
		
		Args:
			obj: The object to check. If None, uses the foreground object.
			
		Returns:
			bool: True if in a supported terminal application.
		"""
		if obj is None:
			obj = api.getForegroundObject()
		
		if not obj or not obj.appModule:
			return False
		
		appName = obj.appModule.appName.lower()
		
		# Supported terminal applications
		supportedTerminals = [
			"windowsterminal",  # Windows Terminal
			"cmd",              # Command Prompt
			"powershell",       # Windows PowerShell
			"pwsh",             # PowerShell Core
			"conhost",          # Console Host
		]
		
		return any(term in appName for term in supportedTerminals)
	
	def event_gainFocus(self, obj, nextHandler):
		"""
		Handle focus gain events.

		Announces help availability when entering a terminal for the first time.
		Binds the review cursor to the focused terminal window.
		"""
		nextHandler()

		if self.isTerminalApp(obj):
			appName = obj.appModule.appName

			# Store the terminal object and route the review cursor to it via the navigator
			self._boundTerminal = obj
			api.setNavigatorObject(obj)
			# Bind review cursor to the terminal; try caret first, fall back to last position
			try:
				info = obj.makeTextInfo(textInfos.POSITION_CARET)
				api.setReviewPosition(info)
			except Exception:
				try:
					info = obj.makeTextInfo(textInfos.POSITION_LAST)
					api.setReviewPosition(info)
				except Exception:
					pass

			# Announce help on first focus to a terminal
			if not self.announcedHelp or appName != self.lastTerminalAppName:
				self.lastTerminalAppName = appName
				self.announcedHelp = True
				# Translators: Message announced when entering a terminal application
				ui.message(_("TDSR terminal support active. Press NVDA+shift+f1 for help."))

	def event_typedCharacter(self, obj, nextHandler, ch):
		"""
		Handle typed character events.

		Announces characters as they are typed if keyEcho is enabled.
		Uses processSymbols setting to determine whether to speak symbol names.
		Uses repeatedSymbols to condense sequences of repeated symbols.
		"""
		nextHandler()

		# Only handle if in a terminal and keyEcho is enabled
		if not self.isTerminalApp(obj) or not config.conf["TDSR"]["keyEcho"]:
			return

		# Don't echo if in quiet mode
		if config.conf["TDSR"]["quietMode"]:
			return

		# Process the character for speech
		if ch:
			# Check if we should condense repeated symbols
			if config.conf["TDSR"]["repeatedSymbols"]:
				repeatedSymbolsValues = config.conf["TDSR"]["repeatedSymbolsValues"]

				# Check if this character is in the list of symbols to condense
				if ch in repeatedSymbolsValues:
					# If it's the same as the last character, increment count
					if ch == self._lastTypedChar:
						self._repeatedCharCount += 1
						# Don't announce yet - wait to see if more come
						return
					else:
						# Different character - announce any pending repeated symbols
						if self._repeatedCharCount > 0:
							self._announceRepeatedSymbol(self._lastTypedChar, self._repeatedCharCount)
						# Reset for this new character
						self._lastTypedChar = ch
						self._repeatedCharCount = 1
						# Don't announce yet
						return
				else:
					# Not a symbol to condense - announce any pending repeated symbols first
					if self._repeatedCharCount > 0:
						self._announceRepeatedSymbol(self._lastTypedChar, self._repeatedCharCount)
						self._lastTypedChar = None
						self._repeatedCharCount = 0

			# Use processSymbols setting to determine if we should speak symbol names
			if config.conf["TDSR"]["processSymbols"]:
				charToSpeak = self._processSymbol(ch)
			else:
				charToSpeak = ch

			# Speak space as "space" instead of silence
			if ch == ' ':
				ui.message(_("space"))
			else:
				ui.message(charToSpeak)

	def _announceRepeatedSymbol(self, char, count):
		"""
		Announce a repeated symbol with its count.

		Args:
			char: The repeated character.
			count: The number of times it was repeated.
		"""
		if count > 1:
			# Get symbol name if processSymbols is enabled
			if config.conf["TDSR"]["processSymbols"]:
				symbolName = self._processSymbol(char)
			else:
				symbolName = char

			# Translators: Message format for repeated symbols, e.g. "3 dash"
			ui.message(_("{count} {symbol}").format(count=count, symbol=symbolName))
		elif count == 1:
			# Just one - announce normally
			if config.conf["TDSR"]["processSymbols"]:
				charToSpeak = self._processSymbol(char)
			else:
				charToSpeak = char
			ui.message(charToSpeak)

	def event_caret(self, obj, nextHandler):
		"""
		Handle caret movement events.

		Announces cursor position changes if cursorTracking is enabled.
		Uses cursorDelay to debounce rapid movements.
		"""
		nextHandler()

		# Only handle if in a terminal and cursor tracking is enabled
		if not self.isTerminalApp(obj) or not config.conf["TDSR"]["cursorTracking"]:
			return

		# Don't track if in quiet mode
		if config.conf["TDSR"]["quietMode"]:
			return

		# Cancel any pending cursor tracking announcement
		if self._cursorTrackingTimer:
			self._cursorTrackingTimer.Stop()
			self._cursorTrackingTimer = None

		# Get cursor delay setting
		delay = config.conf["TDSR"]["cursorDelay"]

		# Schedule announcement with delay
		self._cursorTrackingTimer = wx.CallLater(delay, self._announceCursorPosition, obj)

	def _announceCursorPosition(self, obj):
		"""
		Announce the current cursor position based on the tracking mode.

		Args:
			obj: The terminal object.
		"""
		try:
			# Get cursor tracking mode
			trackingMode = config.conf["TDSR"]["cursorTrackingMode"]

			# Handle different tracking modes
			if trackingMode == CT_OFF:
				return
			elif trackingMode == CT_STANDARD:
				self._announceStandardCursor(obj)
			elif trackingMode == CT_HIGHLIGHT:
				self._announceHighlightCursor(obj)
			elif trackingMode == CT_WINDOW:
				self._announceWindowCursor(obj)
		except Exception:
			# Silently fail - cursor tracking is a non-critical feature
			pass

	def _announceStandardCursor(self, obj):
		"""
		Standard cursor tracking - announce character at cursor position.

		Args:
			obj: The terminal object.
		"""
		# Get the current caret position
		info = obj.makeTextInfo(textInfos.POSITION_CARET)

		# Check if position has actually changed
		currentPos = (info.bookmark.startOffset if hasattr(info, 'bookmark') else None)
		if currentPos == self._lastCaretPosition:
			return

		self._lastCaretPosition = currentPos

		# Expand to get the character at cursor
		info.expand(textInfos.UNIT_CHARACTER)
		char = info.text

		if char and char.strip():
			# Use processSymbols setting if enabled
			if config.conf["TDSR"]["processSymbols"]:
				charToSpeak = self._processSymbol(char)
			else:
				charToSpeak = char
			ui.message(charToSpeak)
		elif char == ' ':
			ui.message(_("space"))

	def _announceHighlightCursor(self, obj):
		"""
		Highlight tracking - announce highlighted/inverse text at cursor.

		Args:
			obj: The terminal object.
		"""
		try:
			# Get the current caret position
			info = obj.makeTextInfo(textInfos.POSITION_CARET)

			# Check if position has actually changed
			currentPos = (info.bookmark.startOffset if hasattr(info, 'bookmark') else None)
			if currentPos == self._lastCaretPosition:
				return

			self._lastCaretPosition = currentPos

			# Expand to current line to detect highlighting
			info.expand(textInfos.UNIT_LINE)
			lineText = info.text

			# Try to detect ANSI escape codes for highlighting (inverse video: ESC[7m)
			# This is a simplified detection - real implementation would need more robust parsing
			if '\x1b[7m' in lineText or 'ESC[7m' in lineText:
				# Extract highlighted portion
				highlightedText = self._extractHighlightedText(lineText)
				if highlightedText and highlightedText != self._lastHighlightedText:
					self._lastHighlightedText = highlightedText
					ui.message(_("Highlighted: {text}").format(text=highlightedText))
			else:
				# Fall back to standard cursor announcement
				self._announceStandardCursor(obj)
		except Exception:
			# Fall back to standard tracking on error
			self._announceStandardCursor(obj)

	def _announceWindowCursor(self, obj):
		"""
		Window tracking - only announce if cursor is within defined window.

		Args:
			obj: The terminal object.
		"""
		if not config.conf["TDSR"]["windowEnabled"]:
			# Window not enabled, fall back to standard tracking
			self._announceStandardCursor(obj)
			return

		try:
			# Get the current caret position
			info = obj.makeTextInfo(textInfos.POSITION_CARET)

			# Try to get cursor coordinates (this may not be available in all terminals)
			# For now, we'll use a simplified approach
			currentPos = (info.bookmark.startOffset if hasattr(info, 'bookmark') else None)
			if currentPos == self._lastCaretPosition:
				return

			self._lastCaretPosition = currentPos

			# Check if position is within window bounds
			# Note: This is a simplified implementation. In a real implementation,
			# we would need to track actual row/column coordinates
			self._announceStandardCursor(obj)
		except Exception:
			self._announceStandardCursor(obj)

	def _extractHighlightedText(self, text):
		"""
		Extract highlighted text from a line containing ANSI codes.

		Args:
			text: The text to process.

		Returns:
			str: The highlighted text, or None if no highlighting detected.
		"""
		# This is a simplified implementation
		# Real implementation would need robust ANSI escape sequence parsing
		import re
		# Remove ANSI escape codes to get clean text
		ansiPattern = re.compile(r'\x1b\[[0-9;]*m')
		cleanText = ansiPattern.sub('', text)
		return cleanText.strip() if cleanText.strip() else None

	@script(
		# Translators: Description for the show help gesture
		description=_("Opens the TDSR user guide"),
		gesture="kb:NVDA+shift+f1"
	)
	def script_showHelp(self, gesture):
		"""Open the TDSR user guide."""
		# Get the add-on directory
		addon = addonHandler.getCodeAddon()
		if addon:
			# Open the user guide HTML file
			docPath = os.path.join(addon.path, "doc", "en", "readme.html")
			if os.path.exists(docPath):
				os.startfile(docPath)
			else:
				# Translators: Error message when help file is not found
				ui.message(_("Help file not found. Please reinstall the add-on."))
		else:
			# Translators: Error message when add-on is not properly installed
			ui.message(_("TDSR add-on not properly installed."))
	
	@script(
		# Translators: Description for reading the previous line
		description=_("Read previous line in terminal"),
		gesture="kb:NVDA+alt+u"
	)
	def script_readPreviousLine(self, gesture):
		"""Read the previous line in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_previousLine(gesture)

	@script(
		# Translators: Description for reading the current line
		description=_("Read current line in terminal. Press twice for indentation level."),
		gesture="kb:NVDA+alt+i"
	)
	def script_readCurrentLine(self, gesture):
		"""Read the current line in the terminal. Double-press announces indentation level."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Check if this is a double-press for indentation
		if scriptHandler.getLastScriptRepeatCount() == 1:
			self._announceIndentation()
		else:
			# Use NVDA's built-in review cursor functionality
			globalCommands.commands.script_review_currentLine(gesture)

	@script(
		# Translators: Description for reading the next line
		description=_("Read next line in terminal"),
		gesture="kb:NVDA+alt+o"
	)
	def script_readNextLine(self, gesture):
		"""Read the next line in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_nextLine(gesture)
	
	@script(
		# Translators: Description for reading the previous word
		description=_("Read previous word in terminal"),
		gesture="kb:NVDA+alt+j"
	)
	def script_readPreviousWord(self, gesture):
		"""Read the previous word in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_previousWord(gesture)

	@script(
		# Translators: Description for reading the current word
		description=_("Read current word in terminal"),
		gesture="kb:NVDA+alt+k"
	)
	def script_readCurrentWord(self, gesture):
		"""Read the current word in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_currentWord(gesture)

	@script(
		# Translators: Description for spelling the current word
		description=_("Spell current word in terminal"),
		gesture="kb:NVDA+alt+k,kb:NVDA+alt+k"
	)
	def script_spellCurrentWord(self, gesture):
		"""Spell out the current word letter by letter."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_spellingCurrentWord(gesture)

	@script(
		# Translators: Description for reading the next word
		description=_("Read next word in terminal"),
		gesture="kb:NVDA+alt+l"
	)
	def script_readNextWord(self, gesture):
		"""Read the next word in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_nextWord(gesture)
	
	@script(
		# Translators: Description for reading the previous character
		description=_("Read previous character in terminal"),
		gesture="kb:NVDA+alt+m"
	)
	def script_readPreviousChar(self, gesture):
		"""Read the previous character in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_previousCharacter(gesture)

	@script(
		# Translators: Description for reading the current character
		description=_("Read current character in terminal. Press twice for phonetic. Press three times for character code."),
		gesture="kb:NVDA+alt+comma"
	)
	def script_readCurrentChar(self, gesture):
		"""Read the current character. Double-press for phonetic. Triple-press for character code."""
		if not self.isTerminalApp():
			gesture.send()
			return

		repeatCount = scriptHandler.getLastScriptRepeatCount()

		if repeatCount == 2:
			# Triple press - announce character code
			self._announceCharacterCode()
		elif repeatCount == 1:
			# Double press - phonetic reading
			globalCommands.commands.script_review_currentCharacter(gesture)
		else:
			# Single press - read character
			globalCommands.commands.script_review_currentCharacter(gesture)

	@script(
		# Translators: Description for reading the current character phonetically
		description=_("Read current character phonetically in terminal"),
		gesture="kb:NVDA+alt+comma,kb:NVDA+alt+comma"
	)
	def script_readCurrentCharPhonetic(self, gesture):
		"""Read the current character using the phonetic alphabet."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality for phonetic reading
		globalCommands.commands.script_review_currentCharacter(gesture)

	@script(
		# Translators: Description for reading the next character
		description=_("Read next character in terminal"),
		gesture="kb:NVDA+alt+period"
	)
	def script_readNextChar(self, gesture):
		"""Read the next character in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
		globalCommands.commands.script_review_nextCharacter(gesture)
	
	@script(
		# Translators: Description for toggling quiet mode
		description=_("Toggle quiet mode in terminal"),
		gesture="kb:NVDA+alt+q"
	)
	def script_toggleQuietMode(self, gesture):
		"""Toggle quiet mode on/off."""
		if not self.isTerminalApp():
			gesture.send()
			return
		
		currentState = config.conf["TDSR"]["quietMode"]
		config.conf["TDSR"]["quietMode"] = not currentState
		
		if config.conf["TDSR"]["quietMode"]:
			# Translators: Message when quiet mode is enabled
			ui.message(_("Quiet mode on"))
		else:
			# Translators: Message when quiet mode is disabled
			ui.message(_("Quiet mode off"))
	
	@script(
		# Translators: Description for starting/ending selection
		description=_("Start or end selection in terminal"),
		gesture="kb:NVDA+alt+r"
	)
	def script_toggleSelection(self, gesture):
		"""Start or end a selection in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Error message when unable to set selection
				ui.message(_("Unable to set selection"))
				return

			if self.selectionStart is None:
				# Start selection - create a bookmark to mark the position
				self.selectionStart = reviewPos.bookmark
				# Translators: Message when selection starts
				ui.message(_("Selection started"))
			else:
				# End selection - copy text between markers to clipboard
				try:
					# Get terminal object
					terminal = self._boundTerminal
					if not terminal:
						ui.message(_("Unable to copy selection"))
						self.selectionStart = None
						return

					# Create text info from start marker
					startInfo = terminal.makeTextInfo(self.selectionStart)
					# Create text info at current review position (end marker)
					endInfo = reviewPos.copy()

					# Set range from start to end
					startInfo.setEndPoint(endInfo, "endToEnd")

					# Get the selected text
					selectedText = startInfo.text

					# Copy to clipboard
					if selectedText and self._copyToClipboard(selectedText):
						# Translators: Message when selection is copied to clipboard
						ui.message(_("Selection copied to clipboard"))
					else:
						# Translators: Error message when unable to copy
						ui.message(_("Unable to copy selection"))
				except Exception:
					# Translators: Error message when unable to copy
					ui.message(_("Unable to copy selection"))
				finally:
					# Always clear the selection marker
					self.selectionStart = None
		except Exception:
			ui.message(_("Unable to set selection"))
	
	@script(
		# Translators: Description for copy mode
		description=_("Enter copy mode in terminal"),
		gesture="kb:NVDA+alt+v"
	)
	def script_copyMode(self, gesture):
		"""Enter copy mode to copy line or screen."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Enter copy mode
		self.copyMode = True
		# Bind keys for copy mode
		self.bindGesture("kb:l", "copyLine")
		self.bindGesture("kb:s", "copyScreen")
		self.bindGesture("kb:escape", "exitCopyMode")
		# Translators: Message entering copy mode
		ui.message(_("Copy mode. Press L to copy line, S to copy screen, or Escape to cancel."))

	@script(
		# Translators: Description for copying line
		description=_("Copy line in copy mode")
	)
	def script_copyLine(self, gesture):
		"""Copy the current line to clipboard."""
		if not self.copyMode:
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to copy"))
				self._exitCopyModeBindings()
				return
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_LINE)
			text = info.text
			if text and self._copyToClipboard(text):
				# Translators: Message when line is copied
				ui.message(_("Line copied"))
			else:
				# Translators: Error message when unable to copy
				ui.message(_("Unable to copy"))
		except Exception:
			ui.message(_("Unable to copy"))
		finally:
			self._exitCopyModeBindings()

	@script(
		# Translators: Description for copying screen
		description=_("Copy screen in copy mode")
	)
	def script_copyScreen(self, gesture):
		"""Copy the entire screen to clipboard."""
		if not self.copyMode:
			gesture.send()
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to copy"))
				return

			# Get the entire text from the terminal
			info = terminal.makeTextInfo(textInfos.POSITION_ALL)
			text = info.text
			if text and self._copyToClipboard(text):
				# Translators: Message when screen is copied
				ui.message(_("Screen copied"))
			else:
				# Translators: Error message when unable to copy
				ui.message(_("Unable to copy"))
		except Exception:
			ui.message(_("Unable to copy"))
		finally:
			self._exitCopyModeBindings()

	@script(
		# Translators: Description for exiting copy mode
		description=_("Exit copy mode")
	)
	def script_exitCopyMode(self, gesture):
		"""Exit copy mode."""
		if not self.copyMode:
			gesture.send()
			return

		# Translators: Message when copy mode is canceled
		ui.message(_("Copy mode canceled"))
		self._exitCopyModeBindings()

	def _exitCopyModeBindings(self):
		"""Exit copy mode and unbind the copy mode keys."""
		self.copyMode = False
		try:
			self.removeGestureBinding("kb:l")
			self.removeGestureBinding("kb:s")
			self.removeGestureBinding("kb:escape")
		except:
			pass
	
	@script(
		# Translators: Description for opening terminal settings
		description=_("Open TDSR terminal settings"),
		gesture="kb:NVDA+alt+c"
	)
	def script_openSettings(self, gesture):
		"""Open the TDSR settings dialog."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Open NVDA settings dialog to TDSR category
		wx.CallAfter(gui.mainFrame._popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, TDSRSettingsPanel)

	@script(
		# Translators: Description for cycling cursor tracking modes
		description=_("Cycle cursor tracking mode"),
		gesture="kb:NVDA+alt+asterisk"
	)
	def script_cycleCursorTrackingMode(self, gesture):
		"""Cycle through cursor tracking modes: Off -> Standard -> Highlight -> Window -> Off."""
		if not self.isTerminalApp():
			gesture.send()
			return

		# Get current mode
		currentMode = config.conf["TDSR"]["cursorTrackingMode"]

		# Cycle to next mode
		nextMode = (currentMode + 1) % 4

		# Update configuration
		config.conf["TDSR"]["cursorTrackingMode"] = nextMode

		# Announce new mode
		modeNames = {
			CT_OFF: _("Cursor tracking off"),
			CT_STANDARD: _("Standard cursor tracking"),
			CT_HIGHLIGHT: _("Highlight tracking"),
			CT_WINDOW: _("Window tracking")
		}
		ui.message(modeNames.get(nextMode, _("Unknown mode")))

	@script(
		# Translators: Description for setting screen window
		description=_("Set screen window boundaries"),
		gesture="kb:NVDA+alt+f2"
	)
	def script_setWindow(self, gesture):
		"""Set screen window boundaries (two-step process: start position, then end position)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to set window"))
				return

			if not self._windowStartSet:
				# Set start position
				self._windowStartBookmark = reviewPos.bookmark
				self._windowStartSet = True
				# Translators: Message when window start is set
				ui.message(_("Window start set. Move to end position and press again."))
			else:
				# Set end position
				startInfo = self._boundTerminal.makeTextInfo(self._windowStartBookmark)
				endInfo = reviewPos.copy()

				# Store window boundaries (simplified - storing bookmarks instead of coordinates)
				config.conf["TDSR"]["windowEnabled"] = True
				self._windowStartSet = False
				# Translators: Message when window is defined
				ui.message(_("Window defined"))
		except Exception:
			ui.message(_("Unable to set window"))
			self._windowStartSet = False

	@script(
		# Translators: Description for clearing screen window
		description=_("Clear screen window"),
		gesture="kb:NVDA+alt+f3"
	)
	def script_clearWindow(self, gesture):
		"""Clear the defined screen window."""
		if not self.isTerminalApp():
			gesture.send()
			return

		config.conf["TDSR"]["windowEnabled"] = False
		self._windowStartSet = False
		# Translators: Message when window is cleared
		ui.message(_("Window cleared"))

	@script(
		# Translators: Description for reading window content
		description=_("Read window content"),
		gesture="kb:NVDA+alt+plus"
	)
	def script_readWindow(self, gesture):
		"""Read the content within the defined window."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not config.conf["TDSR"]["windowEnabled"]:
			# Translators: Message when no window is defined
			ui.message(_("No window defined"))
			return

		# For now, this is a simplified implementation
		# A full implementation would track actual row/column coordinates
		# Translators: Message placeholder for window reading
		ui.message(_("Window reading not fully implemented"))

	@script(
		# Translators: Description for reading text attributes
		description=_("Read text attributes at cursor"),
		gesture="kb:NVDA+alt+shift+a"
	)
	def script_readAttributes(self, gesture):
		"""Read color and formatting attributes at cursor position."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read attributes"))
				return

			# Expand to get character at cursor
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text

			# Try to detect ANSI color codes in the surrounding text
			lineInfo = reviewPos.copy()
			lineInfo.expand(textInfos.UNIT_LINE)
			lineText = lineInfo.text

			# Simple ANSI code detection
			import re
			colorPattern = re.compile(r'\x1b\[([0-9;]+)m')
			matches = colorPattern.findall(lineText)

			if matches:
				# Parse the most recent color code
				colorCode = matches[-1] if matches else None
				attributeMsg = self._parseColorCode(colorCode)
				ui.message(attributeMsg)
			else:
				# Translators: Message when no color attributes detected
				ui.message(_("No color attributes detected"))
		except Exception:
			ui.message(_("Unable to read attributes"))

	def _parseColorCode(self, code):
		"""
		Parse ANSI color code and return human-readable description.

		Args:
			code: The ANSI color code (e.g., "31" for red).

		Returns:
			str: Human-readable color/attribute description.
		"""
		if not code:
			return _("Default color")

		# Basic ANSI color codes
		colorMap = {
			'30': _('Black text'),
			'31': _('Red text'),
			'32': _('Green text'),
			'33': _('Yellow text'),
			'34': _('Blue text'),
			'35': _('Magenta text'),
			'36': _('Cyan text'),
			'37': _('White text'),
			'40': _('Black background'),
			'41': _('Red background'),
			'42': _('Green background'),
			'43': _('Yellow background'),
			'44': _('Blue background'),
			'45': _('Magenta background'),
			'46': _('Cyan background'),
			'47': _('White background'),
			'1': _('Bold'),
			'4': _('Underline'),
			'7': _('Inverse video'),
			'0': _('Reset'),
		}

		codes = code.split(';')
		attributes = [colorMap.get(c, c) for c in codes]
		return ', '.join(attributes)

	# Phase 1 Quick Win Features

	@script(
		# Translators: Description for continuous reading (say all)
		description=_("Read continuously from cursor to end of buffer"),
		gesture="kb:NVDA+alt+a"
	)
	def script_sayAll(self, gesture):
		"""Read continuously from current review cursor position to end of buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when unable to start continuous reading
				ui.message(_("Unable to read"))
				return

			# Get text from current position to end
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_STORY)

			# Move to current position
			info.setEndPoint(reviewPos, "startToStart")

			text = info.text
			if not text or not text.strip():
				# Translators: Message when buffer is empty
				ui.message(_("Nothing to read"))
				return

			# Use NVDA's speech system to read the text
			# This allows for proper interruption
			speech.speakText(text)
		except Exception:
			# Translators: Message when continuous reading fails
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for jumping to start of line
		description=_("Move to first character of current line"),
		gesture="kb:NVDA+alt+home"
	)
	def script_reviewHome(self, gesture):
		"""Move review cursor to first character of current line."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when unable to move
				ui.message(_("Unable to move"))
				return

			# Move to start of line
			info = reviewPos.copy()
			info.collapse()
			info.move(textInfos.UNIT_LINE, -1)
			info.move(textInfos.UNIT_LINE, 1)
			api.setReviewPosition(info)

			# Read character at new position
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text
			if char and char != '\n' and char != '\r':
				speech.speakText(char)
			else:
				# Translators: Message for blank line
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to end of line
		description=_("Move to last character of current line"),
		gesture="kb:NVDA+alt+end"
	)
	def script_reviewEnd(self, gesture):
		"""Move review cursor to last character of current line."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to move"))
				return

			# Expand to line and move to end
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_LINE)
			# Collapse to end
			info.collapse(end=True)
			# Move back one character to be on the last character, not after it
			info.move(textInfos.UNIT_CHARACTER, -1)
			api.setReviewPosition(info)

			# Read character at new position
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text
			if char and char != '\n' and char != '\r':
				speech.speakText(char)
			else:
				# Translators: Message for blank line
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to top
		description=_("Move to top of terminal buffer"),
		gesture="kb:NVDA+alt+pageUp"
	)
	def script_reviewTop(self, gesture):
		"""Move review cursor to top of terminal buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to move"))
				return

			# Move to first position
			info = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			api.setReviewPosition(info)

			# Read character at new position
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text
			if char and char != '\n' and char != '\r':
				speech.speakText(char)
			else:
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for jumping to bottom
		description=_("Move to bottom of terminal buffer"),
		gesture="kb:NVDA+alt+pageDown"
	)
	def script_reviewBottom(self, gesture):
		"""Move review cursor to bottom of terminal buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to move"))
				return

			# Move to last position
			info = terminal.makeTextInfo(textInfos.POSITION_LAST)
			api.setReviewPosition(info)

			# Read character at new position
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text
			if char and char != '\n' and char != '\r':
				speech.speakText(char)
			else:
				ui.message(_("Blank"))
		except Exception:
			ui.message(_("Unable to move"))

	@script(
		# Translators: Description for announcing position
		description=_("Announce current row and column position"),
		gesture="kb:NVDA+alt+p"
	)
	def script_announcePosition(self, gesture):
		"""Announce current row and column coordinates of review cursor."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when position unavailable
				ui.message(_("Position unavailable"))
				return

			# Calculate row (line number)
			# Create info from start to current position
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Position unavailable"))
				return

			startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			currentInfo = reviewPos.copy()

			# Count lines from start to current position
			lineCount = 1
			try:
				testInfo = startInfo.copy()
				while testInfo.compareEndPoints(currentInfo, "startToStart") < 0:
					moved = testInfo.move(textInfos.UNIT_LINE, 1)
					if moved == 0:
						break
					lineCount += 1
			except:
				pass

			# Calculate column (character position in line)
			lineInfo = reviewPos.copy()
			lineInfo.expand(textInfos.UNIT_LINE)
			lineInfo.collapse()

			colCount = 1
			try:
				testInfo = lineInfo.copy()
				while testInfo.compareEndPoints(reviewPos, "startToStart") < 0:
					moved = testInfo.move(textInfos.UNIT_CHARACTER, 1)
					if moved == 0:
						break
					colCount += 1
			except:
				pass

			# Translators: Message announcing row and column position
			ui.message(_("Row {row}, column {col}").format(row=lineCount, col=colCount))
		except Exception:
			ui.message(_("Position unavailable"))

	def _announceIndentation(self):
		"""Announce the indentation level of the current line."""
		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when unable to read indentation
				ui.message(_("Unable to read indentation"))
				return

			# Get current line text
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_LINE)
			lineText = info.text

			if not lineText:
				# Translators: Message for empty line
				ui.message(_("Empty line"))
				return

			# Remove trailing newline if present
			if lineText.endswith('\n') or lineText.endswith('\r'):
				lineText = lineText.rstrip('\n\r')

			if not lineText:
				ui.message(_("Empty line"))
				return

			# Count leading spaces and tabs
			spaces = 0
			tabs = 0
			for char in lineText:
				if char == ' ':
					spaces += 1
				elif char == '\t':
					tabs += 1
				else:
					break

			# Announce indentation
			if spaces == 0 and tabs == 0:
				# Translators: Message when line has no indentation
				ui.message(_("No indentation"))
			elif tabs > 0 and spaces > 0:
				# Translators: Message for mixed indentation
				ui.message(_("{tabs} tab, {spaces} spaces").format(tabs=tabs, spaces=spaces) if tabs == 1 else _("{tabs} tabs, {spaces} spaces").format(tabs=tabs, spaces=spaces))
			elif tabs > 0:
				# Translators: Message for tab indentation
				ui.message(_("{count} tab").format(count=tabs) if tabs == 1 else _("{count} tabs").format(count=tabs))
			else:
				# Translators: Message for space indentation
				ui.message(_("{count} space").format(count=spaces) if spaces == 1 else _("{count} spaces").format(count=spaces))
		except Exception:
			ui.message(_("Unable to read indentation"))

	def _announceCharacterCode(self):
		"""Announce the ASCII/Unicode code of the current character."""
		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				# Translators: Message when unable to read character
				ui.message(_("Unable to read character"))
				return

			# Get character at cursor
			info = reviewPos.copy()
			info.expand(textInfos.UNIT_CHARACTER)
			char = info.text

			if not char or char == '\n' or char == '\r':
				# Translators: Message when no character at position
				ui.message(_("No character"))
				return

			# Get character code
			charCode = ord(char)
			hexCode = hex(charCode)[2:].upper()

			# Get character name for common control characters
			charName = char
			if charCode == 32:
				charName = "space"
			elif charCode == 9:
				charName = "tab"
			elif charCode == 10:
				charName = "line feed"
			elif charCode == 13:
				charName = "carriage return"
			elif charCode < 32:
				charName = "control character"

			# Translators: Message announcing character code
			ui.message(_("Character {decimal}, hex {hex}, {name}").format(
				decimal=charCode,
				hex=hexCode,
				name=charName
			))
		except Exception:
			ui.message(_("Unable to read character"))

	# Phase 2 Core Enhancement Features

	def _shouldProcessSymbol(self, char):
		"""
		Determine if a symbol should be processed/announced based on current punctuation level.

		Args:
			char: The character to check.

		Returns:
			bool: True if the symbol should be announced, False otherwise.
		"""
		level = config.conf["TDSR"]["punctuationLevel"]

		if level == PUNCT_ALL:
			# Level 3: Process all symbols
			return True
		if level == PUNCT_NONE:
			# Level 0: Process no symbols
			return False

		# Level 1 or 2: Check if character is in the level's punctuation set
		punctSet = PUNCTUATION_SETS.get(level, set())
		return char in punctSet

	@script(
		# Translators: Description for decreasing punctuation level
		description=_("Decrease punctuation level"),
		gesture="kb:NVDA+alt+["
	)
	def script_decreasePunctuationLevel(self, gesture):
		"""Decrease the punctuation level (wraps from 0 to 3)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentLevel = config.conf["TDSR"]["punctuationLevel"]
		newLevel = (currentLevel - 1) % 4
		config.conf["TDSR"]["punctuationLevel"] = newLevel

		# Announce new level
		levelNames = {
			PUNCT_NONE: _("Punctuation level none"),
			PUNCT_SOME: _("Punctuation level some"),
			PUNCT_MOST: _("Punctuation level most"),
			PUNCT_ALL: _("Punctuation level all")
		}
		ui.message(levelNames.get(newLevel, _("Punctuation level unknown")))

	@script(
		# Translators: Description for increasing punctuation level
		description=_("Increase punctuation level"),
		gesture="kb:NVDA+alt+]"
	)
	def script_increasePunctuationLevel(self, gesture):
		"""Increase the punctuation level (wraps from 3 to 0)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		currentLevel = config.conf["TDSR"]["punctuationLevel"]
		newLevel = (currentLevel + 1) % 4
		config.conf["TDSR"]["punctuationLevel"] = newLevel

		# Announce new level
		levelNames = {
			PUNCT_NONE: _("Punctuation level none"),
			PUNCT_SOME: _("Punctuation level some"),
			PUNCT_MOST: _("Punctuation level most"),
			PUNCT_ALL: _("Punctuation level all")
		}
		ui.message(levelNames.get(newLevel, _("Punctuation level unknown")))

	@script(
		# Translators: Description for reading to left edge
		description=_("Read from cursor to beginning of line"),
		gesture="kb:NVDA+alt+shift+leftArrow"
	)
	def script_readToLeft(self, gesture):
		"""Read from current cursor position to beginning of line."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			# Get the current line
			lineInfo = reviewPos.copy()
			lineInfo.expand(textInfos.UNIT_LINE)

			# Create range from line start to cursor
			lineInfo.setEndPoint(reviewPos, "endToStart")

			text = lineInfo.text
			if not text or not text.strip():
				# Translators: Message when region is empty
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to right edge
		description=_("Read from cursor to end of line"),
		gesture="kb:NVDA+alt+shift+rightArrow"
	)
	def script_readToRight(self, gesture):
		"""Read from current cursor position to end of line."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			# Get the current line
			lineInfo = reviewPos.copy()
			lineInfo.expand(textInfos.UNIT_LINE)

			# Create range from cursor to line end
			lineInfo.setEndPoint(reviewPos, "startToStart")

			text = lineInfo.text
			if not text or not text.strip():
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to top
		description=_("Read from cursor to top of buffer"),
		gesture="kb:NVDA+alt+shift+upArrow"
	)
	def script_readToTop(self, gesture):
		"""Read from current cursor position to top of buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to read"))
				return

			# Get range from buffer start to cursor
			startInfo = terminal.makeTextInfo(textInfos.POSITION_FIRST)
			startInfo.setEndPoint(reviewPos, "endToStart")

			text = startInfo.text
			if not text or not text.strip():
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for reading to bottom
		description=_("Read from cursor to bottom of buffer"),
		gesture="kb:NVDA+alt+shift+downArrow"
	)
	def script_readToBottom(self, gesture):
		"""Read from current cursor position to bottom of buffer."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to read"))
				return

			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to read"))
				return

			# Get range from cursor to buffer end
			endInfo = terminal.makeTextInfo(textInfos.POSITION_LAST)
			reviewPos.setEndPoint(endInfo, "endToEnd")

			text = reviewPos.text
			if not text or not text.strip():
				ui.message(_("Nothing"))
				return

			speech.speakText(text)
		except Exception:
			ui.message(_("Unable to read"))

	@script(
		# Translators: Description for toggling mark position
		description=_("Toggle mark for selection (enhanced)"),
		gesture="kb:NVDA+alt+r"
	)
	def script_toggleMark(self, gesture):
		"""Toggle marking positions for enhanced selection."""
		if not self.isTerminalApp():
			gesture.send()
			return

		try:
			reviewPos = self._getReviewPosition()
			if reviewPos is None:
				ui.message(_("Unable to set mark"))
				return

			if self._markStart is None:
				# Set start mark
				self._markStart = reviewPos.bookmark
				# Translators: Message when start mark is set
				ui.message(_("Mark start set"))
			elif self._markEnd is None:
				# Set end mark
				self._markEnd = reviewPos.bookmark
				# Translators: Message when end mark is set
				ui.message(_("Mark end set"))
			else:
				# Clear marks and start over
				self._markStart = None
				self._markEnd = None
				# Translators: Message when marks are cleared
				ui.message(_("Marks cleared"))
		except Exception:
			ui.message(_("Unable to set mark"))

	@script(
		# Translators: Description for copying linear selection
		description=_("Copy linear selection between marks"),
		gesture="kb:NVDA+alt+c"
	)
	def script_copyLinearSelection(self, gesture):
		"""Copy text from start mark to end mark (continuous selection)."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._markStart or not self._markEnd:
			# Translators: Message when marks are not set
			ui.message(_("Set start and end marks first"))
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to copy"))
				return

			# Get text from start to end mark
			startInfo = terminal.makeTextInfo(self._markStart)
			endInfo = terminal.makeTextInfo(self._markEnd)
			startInfo.setEndPoint(endInfo, "endToEnd")

			text = startInfo.text
			if text and self._copyToClipboard(text):
				# Translators: Message when selection copied
				ui.message(_("Selection copied"))
			else:
				ui.message(_("Unable to copy"))
		except Exception:
			ui.message(_("Unable to copy"))

	@script(
		# Translators: Description for copying rectangular selection
		description=_("Copy rectangular selection between marks"),
		gesture="kb:NVDA+alt+shift+c"
	)
	def script_copyRectangularSelection(self, gesture):
		"""Copy rectangular region (column-based) between marks."""
		if not self.isTerminalApp():
			gesture.send()
			return

		if not self._markStart or not self._markEnd:
			ui.message(_("Set start and end marks first"))
			return

		try:
			terminal = self._boundTerminal
			if not terminal:
				ui.message(_("Unable to copy"))
				return

			# Get start and end positions
			startInfo = terminal.makeTextInfo(self._markStart)
			endInfo = terminal.makeTextInfo(self._markEnd)

			# Calculate row and column bounds
			# This is a simplified implementation - a full implementation would
			# need to accurately track row/column coordinates
			startInfo.expand(textInfos.UNIT_LINE)
			endInfo.expand(textInfos.UNIT_LINE)

			# For now, just copy the lines (simplified rectangular selection)
			startInfo.setEndPoint(endInfo, "endToEnd")
			text = startInfo.text

			if text and self._copyToClipboard(text):
				# Translators: Message for rectangular selection
				ui.message(_("Rectangular selection copied"))
			else:
				ui.message(_("Unable to copy"))
		except Exception:
			ui.message(_("Unable to copy"))

	@script(
		# Translators: Description for clearing marks
		description=_("Clear selection marks"),
		gesture="kb:NVDA+alt+x"
	)
	def script_clearMarks(self, gesture):
		"""Clear the selection marks."""
		if not self.isTerminalApp():
			gesture.send()
			return

		self._markStart = None
		self._markEnd = None
		# Translators: Message when marks cleared
		ui.message(_("Marks cleared"))


	def _copyToClipboard(self, text):
		"""
		Copy text to the Windows clipboard using NVDA's clipboard API.

		Args:
			text: The text to copy to the clipboard.
		"""
		try:
			result = api.copyToClip(text, notify=False)
			return result if isinstance(result, bool) else True
		except TypeError:
			# Older NVDA versions do not support the notify parameter
			try:
				result = api.copyToClip(text)
				return result if isinstance(result, bool) else True
			except Exception:
				return False
		except Exception:
			return False

	def _getReviewPosition(self):
		"""
		Return the current review position, re-binding to the terminal if None.

		Returns:
			textInfos.TextInfo or None if no terminal is bound.
		"""
		info = api.getReviewPosition()
		if info is not None:
			return info
		if self._boundTerminal is None:
			return None
		try:
			info = self._boundTerminal.makeTextInfo(textInfos.POSITION_CARET)
		except Exception:
			try:
				info = self._boundTerminal.makeTextInfo(textInfos.POSITION_LAST)
			except Exception:
				return None
		api.setReviewPosition(info)
		return info

	def _processSymbol(self, char):
		"""
		Process a symbol character for speech.
		
		Args:
			char: The character to process.
			
		Returns:
			str: The processed symbol name or the original character.
		"""
		# Map common symbols to their names
		symbolMap = {
			'!': 'exclamation',
			'@': 'at',
			'#': 'hash',
			'$': 'dollar',
			'%': 'percent',
			'^': 'caret',
			'&': 'ampersand',
			'*': 'asterisk',
			'(': 'left paren',
			')': 'right paren',
			'-': 'dash',
			'_': 'underscore',
			'=': 'equals',
			'+': 'plus',
			'[': 'left bracket',
			']': 'right bracket',
			'{': 'left brace',
			'}': 'right brace',
			'\\': 'backslash',
			'|': 'pipe',
			';': 'semicolon',
			':': 'colon',
			"'": 'apostrophe',
			'"': 'quote',
			',': 'comma',
			'.': 'dot',
			'/': 'slash',
			'<': 'less than',
			'>': 'greater than',
			'?': 'question',
			'~': 'tilde',
			'`': 'backtick',
		}
		
		return symbolMap.get(char, char)


class TDSRSettingsPanel(SettingsPanel):
	"""
	Settings panel for TDSR terminal configuration.
	
	Provides UI for configuring all TDSR options within NVDA's settings dialog.
	"""
	
	# Translators: Title for the TDSR settings category
	title = _("Terminal Settings")
	
	def makeSettings(self, settingsSizer):
		"""Create the settings UI elements."""
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Cursor tracking checkbox
		# Translators: Label for cursor tracking checkbox
		self.cursorTrackingCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("Enable cursor &tracking"))
		)
		self.cursorTrackingCheckBox.SetValue(config.conf["TDSR"]["cursorTracking"])

		# Cursor tracking mode choice
		# Translators: Label for cursor tracking mode choice
		self.cursorTrackingModeChoice = sHelper.addLabeledControl(
			_("Cursor tracking &mode:"),
			wx.Choice,
			choices=[
				_("Off"),
				_("Standard"),
				_("Highlight"),
				_("Window")
			]
		)
		self.cursorTrackingModeChoice.SetSelection(config.conf["TDSR"]["cursorTrackingMode"])

		# Key echo checkbox
		# Translators: Label for key echo checkbox
		self.keyEchoCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("Enable &key echo"))
		)
		self.keyEchoCheckBox.SetValue(config.conf["TDSR"]["keyEcho"])

		# Line pause checkbox
		# Translators: Label for line pause checkbox
		self.linePauseCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("Pause at &newlines"))
		)
		self.linePauseCheckBox.SetValue(config.conf["TDSR"]["linePause"])

		# Punctuation level choice
		# Translators: Label for punctuation level choice
		self.punctuationLevelChoice = sHelper.addLabeledControl(
			_("&Punctuation level:"),
			wx.Choice,
			choices=[
				_("None"),
				_("Some (.,?!;:)"),
				_("Most (adds @#$%^&*()_+=[]{}\\|<>/)"),
				_("All")
			]
		)
		self.punctuationLevelChoice.SetSelection(config.conf["TDSR"]["punctuationLevel"])

		# Repeated symbols checkbox
		# Translators: Label for repeated symbols checkbox
		self.repeatedSymbolsCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("Condense &repeated symbols"))
		)
		self.repeatedSymbolsCheckBox.SetValue(config.conf["TDSR"]["repeatedSymbols"])

		# Repeated symbols values text field
		# Translators: Label for repeated symbols values
		self.repeatedSymbolsValuesText = sHelper.addLabeledControl(
			_("Repeated symbols to condense:"),
			wx.TextCtrl
		)
		self.repeatedSymbolsValuesText.SetValue(config.conf["TDSR"]["repeatedSymbolsValues"])

		# Cursor delay spinner
		# Translators: Label for cursor delay spinner
		self.cursorDelaySpinner = sHelper.addLabeledControl(
			_("Cursor delay (milliseconds):"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=1000,
			initial=config.conf["TDSR"]["cursorDelay"]
		)
	
	def onSave(self):
		"""Save the settings when the user clicks OK."""
		config.conf["TDSR"]["cursorTracking"] = self.cursorTrackingCheckBox.GetValue()
		config.conf["TDSR"]["cursorTrackingMode"] = self.cursorTrackingModeChoice.GetSelection()
		config.conf["TDSR"]["keyEcho"] = self.keyEchoCheckBox.GetValue()
		config.conf["TDSR"]["linePause"] = self.linePauseCheckBox.GetValue()
		config.conf["TDSR"]["punctuationLevel"] = self.punctuationLevelChoice.GetSelection()
		config.conf["TDSR"]["repeatedSymbols"] = self.repeatedSymbolsCheckBox.GetValue()
		config.conf["TDSR"]["repeatedSymbolsValues"] = self.repeatedSymbolsValuesText.GetValue()
		config.conf["TDSR"]["cursorDelay"] = self.cursorDelaySpinner.GetValue()
