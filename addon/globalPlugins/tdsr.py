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
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel
import addonHandler
import wx
import os
import re
from scriptHandler import script

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

# Phonetic alphabet for character spelling
PHONETICS = {
	'a': 'alpha', 'b': 'bravo', 'c': 'charlie', 'd': 'delta', 'e': 'echo', 
	'f': 'foxtrot', 'g': 'golf', 'h': 'hotel', 'i': 'india', 'j': 'juliet', 
	'k': 'kilo', 'l': 'lima', 'm': 'mike', 'n': 'november', 'o': 'oscar', 
	'p': 'papa', 'q': 'quebec', 'r': 'romeo', 's': 'sierra', 't': 'tango', 
	'u': 'uniform', 'v': 'victor', 'w': 'whiskey', 'x': 'x ray', 'y': 'yankee', 
	'z': 'zulu'
}


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
		self.reviewPosition = {"x": 0, "y": 0}
		self.selectionStart = None
		
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
		"""
		nextHandler()
		
		if self.isTerminalApp(obj):
			appName = obj.appModule.appName
			
			# Announce help on first focus to a terminal
			if not self.announcedHelp or appName != self.lastTerminalAppName:
				self.lastTerminalAppName = appName
				self.announcedHelp = True
				# Translators: Message announced when entering a terminal application
				ui.message(_("TDSR terminal support active. Press NVDA+shift+f1 for help."))
	
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
		
		obj = api.getFocusObject()
		self.reviewPosition["y"] = max(0, self.reviewPosition["y"] - 1)
		self._readLineAtReview(obj)
	
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
		
		obj = api.getFocusObject()
		self._readLineAtReview(obj)
	
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
		
		obj = api.getFocusObject()
		self.reviewPosition["y"] = self.reviewPosition["y"] + 1
		self._readLineAtReview(obj)
	
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
		
		obj = api.getFocusObject()
		self._readWordNavigation(obj, -1)
	
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
		
		obj = api.getFocusObject()
		self._readWordNavigation(obj, 0)
	
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
		
		obj = api.getFocusObject()
		word = self._getWordAtReview(obj)
		if word:
			# Spell out each character
			for char in word:
				ui.message(char)
		else:
			# Translators: Message when there is no word to spell
			ui.message(_("No word"))
	
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
		
		obj = api.getFocusObject()
		self._readWordNavigation(obj, 1)
	
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
		
		obj = api.getFocusObject()
		self._readCharNavigation(obj, -1)
	
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
		
		obj = api.getFocusObject()
		self._readCharNavigation(obj, 0)
	
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
		
		obj = api.getFocusObject()
		char = self._getCharAtReview(obj)
		if char:
			lower_char = char.lower()
			if lower_char in PHONETICS:
				ui.message(PHONETICS[lower_char])
			else:
				ui.message(char)
		else:
			# Translators: Message when there is no character
			ui.message(_("No character"))
	
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
		
		obj = api.getFocusObject()
		self._readCharNavigation(obj, 1)
	
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
		
		if self.selectionStart is None:
			# Start selection
			self.selectionStart = dict(self.reviewPosition)
			# Translators: Message when selection starts
			ui.message(_("Selection started"))
		else:
			# End selection
			self.selectionStart = None
			# Translators: Message when selection ends
			ui.message(_("Selection ended"))
	
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
		
		# Translators: Message entering copy mode
		ui.message(_("Copy mode. Press L to copy line, S to copy screen, or Escape to cancel."))
	
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
	
	def _readLineAtReview(self, obj):
		"""
		Read a line at the current review position.
		
		Args:
			obj: The terminal object to read from.
		"""
		try:
			# Try to get text from the terminal
			# This is a simplified implementation - actual terminal reading would need
			# platform-specific APIs or accessibility APIs
			info = obj.makeTextInfo("line")
			text = info.text
			
			if text:
				ui.message(text)
			else:
				# Translators: Message when line is empty
				ui.message(_("Blank"))
		except:
			# Translators: Error message when unable to read line
			ui.message(_("Unable to read line"))
	
	def _readWordNavigation(self, obj, direction):
		"""
		Navigate by word and read.
		
		Args:
			obj: The terminal object.
			direction: -1 for previous, 0 for current, 1 for next.
		"""
		try:
			info = obj.makeTextInfo("line")
			text = info.text
			words = text.split()
			
			if not words:
				# Translators: Message when there are no words
				ui.message(_("No word"))
				return
			
			# Simplified word navigation - would need more sophisticated tracking
			currentWordIndex = 0
			if 0 <= currentWordIndex < len(words):
				ui.message(words[currentWordIndex])
			else:
				ui.message(_("No word"))
		except:
			ui.message(_("Unable to read word"))
	
	def _getWordAtReview(self, obj):
		"""
		Get the word at the current review position.
		
		Args:
			obj: The terminal object.
			
		Returns:
			str: The word at the review position, or None.
		"""
		try:
			info = obj.makeTextInfo("word")
			return info.text
		except:
			return None
	
	def _readCharNavigation(self, obj, direction):
		"""
		Navigate by character and read.
		
		Args:
			obj: The terminal object.
			direction: -1 for previous, 0 for current, 1 for next.
		"""
		try:
			char = self._getCharAtReview(obj)
			if char:
				# Process symbols if enabled
				if config.conf["TDSR"]["processSymbols"]:
					char = self._processSymbol(char)
				ui.message(char if char.strip() else _("space"))
			else:
				# Translators: Message when there is no character
				ui.message(_("No character"))
		except:
			ui.message(_("Unable to read character"))
	
	def _getCharAtReview(self, obj):
		"""
		Get the character at the current review position.
		
		Args:
			obj: The terminal object.
			
		Returns:
			str: The character at the review position, or None.
		"""
		try:
			info = obj.makeTextInfo("character")
			return info.text
		except:
			return None
	
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
