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
import globalCommands

try:
	addonHandler.initTranslation()
except:
	pass

# Configuration spec for TDSR settings
confspec = {
	"cursorTracking": "boolean(default=True)",
	"keyEcho": "boolean(default=True)",
	"linePause": "boolean(default=True)",
	"processSymbols": "boolean(default=False)",
	"repeatedSymbols": "boolean(default=False)",
	"repeatedSymbolsValues": "string(default='-_=!')",
	"cursorDelay": "integer(default=20, min=0, max=1000)",
	"quietMode": "boolean(default=False)",
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
		Announce the current cursor position.

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
		except Exception:
			# Silently fail - cursor tracking is a non-critical feature
			pass

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
		description=_("Read current line in terminal"),
		gesture="kb:NVDA+alt+i"
	)
	def script_readCurrentLine(self, gesture):
		"""Read the current line in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
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
		description=_("Read current character in terminal"),
		gesture="kb:NVDA+alt+comma"
	)
	def script_readCurrentChar(self, gesture):
		"""Read the current character in the terminal."""
		if not self.isTerminalApp():
			gesture.send()
			return
		# Use NVDA's built-in review cursor functionality
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
		# Use NVDA's built-in review cursor functionality (repeating current character gives phonetic)
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
				# End selection
				self.selectionStart = None
				# Translators: Message when selection ends
				ui.message(_("Selection ended"))
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
		
		# Process symbols checkbox
		# Translators: Label for process symbols checkbox
		self.processSymbolsCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("Process &symbols"))
		)
		self.processSymbolsCheckBox.SetValue(config.conf["TDSR"]["processSymbols"])
		
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
		config.conf["TDSR"]["keyEcho"] = self.keyEchoCheckBox.GetValue()
		config.conf["TDSR"]["linePause"] = self.linePauseCheckBox.GetValue()
		config.conf["TDSR"]["processSymbols"] = self.processSymbolsCheckBox.GetValue()
		config.conf["TDSR"]["repeatedSymbols"] = self.repeatedSymbolsCheckBox.GetValue()
		config.conf["TDSR"]["repeatedSymbolsValues"] = self.repeatedSymbolsValuesText.GetValue()
		config.conf["TDSR"]["cursorDelay"] = self.cursorDelaySpinner.GetValue()
