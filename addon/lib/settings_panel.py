"""
Terminal Access settings panel — extracted from terminalAccess.py.

Provides a progressive-disclosure UI with Basic and Advanced sections.
"""

import os

import config
import gui
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel
import globalPluginHandler
import wx

from lib.config import (
	_validateInteger, _validateString,
	CT_OFF, CT_STANDARD, CT_HIGHLIGHT, CT_WINDOW,
	PUNCT_NONE, PUNCT_SOME, PUNCT_MOST, PUNCT_ALL,
	MAX_REPEATED_SYMBOLS_LENGTH,
)
from lib.profiles import _BUILTIN_PROFILE_NAMES


# ---------------------------------------------------------------------------
# Gesture helpers — shared implementation in lib._runtime
# ---------------------------------------------------------------------------

from lib._runtime import gesture_label as _gestureLabel


# These are intentionally imported late (inside methods that need them) to
# avoid a circular import with the main plugin module.  The two constants
# below are safe to keep at module level because they are plain data.
_DEFAULT_GESTURES = None  # populated lazily
_CONFLICTING_GESTURES = None  # populated lazily
_ALWAYS_BOUND = frozenset({"kb:NVDA+'", "kb:NVDA+shift+f1"})


def _get_default_gestures():
	"""Lazy accessor for _DEFAULT_GESTURES to avoid circular import."""
	global _DEFAULT_GESTURES
	if _DEFAULT_GESTURES is None:
		from globalPlugins.terminalAccess import _DEFAULT_GESTURES as _dg
		_DEFAULT_GESTURES = _dg
	return _DEFAULT_GESTURES


def _get_conflicting_gestures():
	"""Lazy accessor for _CONFLICTING_GESTURES to avoid circular import."""
	global _CONFLICTING_GESTURES
	if _CONFLICTING_GESTURES is None:
		from globalPlugins.terminalAccess import _CONFLICTING_GESTURES as _cg
		_CONFLICTING_GESTURES = _cg
	return _CONFLICTING_GESTURES


class TerminalAccessSettingsPanel(SettingsPanel):
	"""
	Enhanced settings panel for Terminal Access configuration.

	Provides organized UI with progressive disclosure: a Basic section
	(always visible) and an Advanced section (collapsible).
	Follows NVDA GUI guidelines for accessibility and usability.
	"""

	# Translators: Title for the Terminal Access settings category
	title = _("Terminal Settings")

	# Names of the four controls that live in the Basic section.
	BASIC_CONTROLS = (
		"cursorTrackingCheckBox",
		"keyEchoCheckBox",
		"quietModeCheckBox",
		"punctuationLevelChoice",
	)

	# Names of controls that live below the basic section.
	EXTENDED_CONTROLS = (
		"cursorTrackingModeChoice",
		"cursorDelaySpinner",
		"linePauseCheckBox",
		"verboseModeCheckBox",
		"indentationOnLineReadCheckBox",
		"repeatedSymbolsCheckBox",
		"repeatedSymbolsValuesText",
		"defaultProfileChoice",
		"resetButton",
		"gestureCheckList",
	)

	# ------------------------------------------------------------------
	# UI construction
	# ------------------------------------------------------------------

	def makeSettings(self, settingsSizer):
		"""Create the settings UI with flat, labeled groups."""
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		profileManager = self._getProfileManager()

		# === Speech and Tracking ===
		# Translators: Label for speech and tracking settings group
		speechGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Speech and Tracking")),
			wx.VERTICAL
		))
		sHelper.addItem(speechGroup)
		self._makeBasicControls(speechGroup)
		self._makeAdvancedControls(speechGroup, profileManager)

		# === Audio Cues ===
		# Translators: Label for audio cues settings group
		audioCueGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Audio Cues")),
			wx.VERTICAL
		))
		sHelper.addItem(audioCueGroup)
		self._makeAudioCueControls(audioCueGroup)

		# === Gesture Conflicts ===
		# Translators: Label for gesture conflicts group
		gestureGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("NVDA Gesture Conflicts")),
			wx.VERTICAL
		))
		sHelper.addItem(gestureGroup)
		self._makeGestureControls(gestureGroup)

		# === Application Profiles ===
		# Translators: Label for profile management group
		profileGroup = guiHelper.BoxSizerHelper(self, sizer=wx.StaticBoxSizer(
			wx.StaticBox(self, label=_("Application Profiles")),
			wx.VERTICAL
		))
		sHelper.addItem(profileGroup)
		self._makeProfileControls(profileGroup, profileManager)

	# ------------------------------------------------------------------
	# Basic controls
	# ------------------------------------------------------------------

	def _makeBasicControls(self, group):
		"""Populate the Basic section (always visible)."""

		# Cursor tracking checkbox
		# Translators: Label for cursor tracking checkbox
		self.cursorTrackingCheckBox = group.addItem(
			wx.CheckBox(self, label=_("Enable cursor &tracking"))
		)
		self.cursorTrackingCheckBox.SetValue(config.conf["terminalAccess"]["cursorTracking"])
		# Translators: Tooltip for cursor tracking checkbox
		self.cursorTrackingCheckBox.SetToolTip(_(
			"Automatically announce cursor position changes in the terminal"
		))

		# Key echo checkbox
		# Translators: Label for key echo checkbox
		self.keyEchoCheckBox = group.addItem(
			wx.CheckBox(self, label=_("Enable &key echo"))
		)
		self.keyEchoCheckBox.SetValue(config.conf["terminalAccess"]["keyEcho"])
		# Translators: Tooltip for key echo
		self.keyEchoCheckBox.SetToolTip(_(
			"Announce characters as you type in the terminal"
		))

		# Quiet mode checkbox
		# Translators: Label for quiet mode checkbox
		self.quietModeCheckBox = group.addItem(
			wx.CheckBox(self, label=_("&Quiet mode"))
		)
		self.quietModeCheckBox.SetValue(config.conf["terminalAccess"]["quietMode"])
		# Translators: Tooltip for quiet mode
		self.quietModeCheckBox.SetToolTip(_(
			"Suppress most Terminal Access announcements. Use NVDA+Shift+Q to toggle quickly."
		))

		# Punctuation level choice
		# Translators: Label for punctuation level choice
		self.punctuationLevelChoice = group.addLabeledControl(
			_("&Punctuation level:"),
			wx.Choice,
			choices=[
				# Translators: Punctuation level option
				_("None"),
				# Translators: Punctuation level option
				_("Some (.,?!;:)"),
				# Translators: Punctuation level option
				_("Most (adds @#$%^&*()_+=[]{}\\|<>/)"),
				# Translators: Punctuation level option
				_("All")
			]
		)
		self.punctuationLevelChoice.SetSelection(config.conf["terminalAccess"]["punctuationLevel"])
		# Translators: Tooltip for punctuation level
		self.punctuationLevelChoice.SetToolTip(_(
			"Controls which punctuation symbols are announced. "
			"Higher levels announce more symbols. "
			"Use NVDA+minus and NVDA+equals to adjust quickly."
		))

	# ------------------------------------------------------------------
	# Advanced controls
	# ------------------------------------------------------------------

	def _makeAdvancedControls(self, group, profileManager):
		"""Populate the Advanced section (inside the collapsible pane)."""

		# Cursor tracking mode choice
		# Translators: Label for cursor tracking mode choice
		self.cursorTrackingModeChoice = group.addLabeledControl(
			_("Cursor tracking &mode:"),
			wx.Choice,
			choices=[
				# Translators: Cursor tracking mode option
				_("Off"),
				# Translators: Cursor tracking mode option
				_("Standard"),
				# Translators: Cursor tracking mode option
				_("Highlight (deprecated)"),
				# Translators: Cursor tracking mode option
				_("Window")
			]
		)
		self.cursorTrackingModeChoice.SetSelection(config.conf["terminalAccess"]["cursorTrackingMode"])
		# Translators: Tooltip for cursor tracking mode
		self.cursorTrackingModeChoice.SetToolTip(_(
			"Standard: announce line/column changes, "
			"Highlight (deprecated): announce highlighted text, "
			"Window: only announce within defined window"
		))

		# Cursor delay spinner
		# Translators: Label for cursor delay spinner
		self.cursorDelaySpinner = group.addLabeledControl(
			_("Cursor delay (milliseconds):"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=1000,
			initial=config.conf["terminalAccess"]["cursorDelay"]
		)
		# Translators: Tooltip for cursor delay
		self.cursorDelaySpinner.SetToolTip(_(
			"Delay before announcing cursor position (0-1000ms). "
			"Higher values reduce announcement frequency."
		))

		# Line pause checkbox
		# Translators: Label for line pause checkbox
		self.linePauseCheckBox = group.addItem(
			wx.CheckBox(self, label=_("Pause at &newlines"))
		)
		self.linePauseCheckBox.SetValue(config.conf["terminalAccess"]["linePause"])
		# Translators: Tooltip for line pause
		self.linePauseCheckBox.SetToolTip(_(
			"Brief pause when speaking line content to improve clarity"
		))

		# Verbose mode checkbox
		# Translators: Label for verbose mode checkbox
		self.verboseModeCheckBox = group.addItem(
			wx.CheckBox(self, label=_("&Verbose mode (detailed feedback)"))
		)
		self.verboseModeCheckBox.SetValue(config.conf["terminalAccess"]["verboseMode"])
		# Translators: Tooltip for verbose mode
		self.verboseModeCheckBox.SetToolTip(_(
			"Include position and context information with announcements. "
			"Useful for debugging and understanding terminal layout."
		))

		# Indentation announcement checkbox
		# Translators: Label for indentation announcement checkbox
		self.indentationOnLineReadCheckBox = group.addItem(
			wx.CheckBox(self, label=_("Announce &indentation when reading lines"))
		)
		self.indentationOnLineReadCheckBox.SetValue(config.conf["terminalAccess"]["indentationOnLineRead"])
		# Translators: Tooltip for indentation announcement
		self.indentationOnLineReadCheckBox.SetToolTip(_(
			"Automatically announce indentation level when reading lines. "
			"Use NVDA+F5 to toggle quickly. NVDA+I pressed twice still reads indentation."
		))

		# Repeated symbols checkbox
		# Translators: Label for repeated symbols checkbox
		self.repeatedSymbolsCheckBox = group.addItem(
			wx.CheckBox(self, label=_("Condense &repeated symbols"))
		)
		self.repeatedSymbolsCheckBox.SetValue(config.conf["terminalAccess"]["repeatedSymbols"])
		# Translators: Tooltip for repeated symbols
		self.repeatedSymbolsCheckBox.SetToolTip(_(
			"Condense runs of repeated symbols (e.g., '====' becomes '4 equals')"
		))

		# Repeated symbols values text field
		# Translators: Label for repeated symbols values
		self.repeatedSymbolsValuesText = group.addLabeledControl(
			_("Repeated symbols to condense:"),
			wx.TextCtrl
		)
		self.repeatedSymbolsValuesText.SetValue(config.conf["terminalAccess"]["repeatedSymbolsValues"])
		# Translators: Tooltip for repeated symbols values
		self.repeatedSymbolsValuesText.SetToolTip(_(
			"Characters that will be condensed when repeated. "
			"Example: -_=! (max 50 characters)"
		))

		# Default profile dropdown
		# Translators: Label for default profile choice
		defaultProfileChoices = [_("None (use global settings)")] + self._getProfileNames()
		self.defaultProfileChoice = group.addLabeledControl(
			_("&Default profile:"),
			wx.Choice,
			choices=defaultProfileChoices
		)
		currentDefault = config.conf["terminalAccess"].get("defaultProfile", "")
		if currentDefault and profileManager and currentDefault in profileManager.profiles:
			profileNames = self._getProfileNames()
			if currentDefault in profileNames:
				self.defaultProfileChoice.SetSelection(profileNames.index(currentDefault) + 1)
			else:
				self.defaultProfileChoice.SetSelection(0)
		else:
			self.defaultProfileChoice.SetSelection(0)
		# Translators: Tooltip for default profile
		self.defaultProfileChoice.SetToolTip(_(
			"Profile to use when no application-specific profile is detected. "
			"Use NVDA+F10 to check which profile is active."
		))

		# Reset to Defaults button
		# Translators: Label for reset to defaults button
		self.resetButton = group.addItem(
			wx.Button(self, label=_("&Reset to Defaults"))
		)
		# Translators: Tooltip for reset button
		self.resetButton.SetToolTip(_(
			"Reset all Terminal Access settings to their default values"
		))
		self.resetButton.Bind(wx.EVT_BUTTON, self.onResetToDefaults)

	# ------------------------------------------------------------------
	# Audio cue controls
	# ------------------------------------------------------------------

	def _makeAudioCueControls(self, group):
		"""Populate the Audio Cues section."""

		# Error/warning audio cues checkbox
		# Translators: Label for error audio cues checkbox
		self.errorAudioCuesCheckBox = group.addItem(
			wx.CheckBox(self, label=_("Error and &warning audio cues"))
		)
		self.errorAudioCuesCheckBox.SetValue(config.conf["terminalAccess"].get("errorAudioCues", True))
		# Translators: Tooltip for error audio cues
		self.errorAudioCuesCheckBox.SetToolTip(_(
			"Play a low tone on error lines and a higher tone on warning lines during navigation."
		))

		# Error audio cues in quiet mode
		# Translators: Label for quiet mode error cues checkbox
		self.errorCuesQuietModeCheckBox = group.addItem(
			wx.CheckBox(self, label=_("Error audio cues in &quiet mode"))
		)
		self.errorCuesQuietModeCheckBox.SetValue(config.conf["terminalAccess"].get("errorAudioCuesInQuietMode", False))
		# Translators: Tooltip for quiet mode error cues
		self.errorCuesQuietModeCheckBox.SetToolTip(_(
			"Play error and warning tones on caret events while quiet mode is active. "
			"Lets you hear errors during fast output without speech."
		))

		# Output activity tones
		# Translators: Label for output activity tones checkbox
		self.outputActivityTonesCheckBox = group.addItem(
			wx.CheckBox(self, label=_("Output &activity tones"))
		)
		self.outputActivityTonesCheckBox.SetValue(config.conf["terminalAccess"].get("outputActivityTones", False))
		# Translators: Tooltip for output activity tones
		self.outputActivityTonesCheckBox.SetToolTip(_(
			"Play two ascending tones when new program output appears on screen. "
			"Does not play for characters you type."
		))

		# Output activity debounce
		# Translators: Label for activity debounce spinner
		self.outputDebounceSpinner = group.addLabeledControl(
			_("Activity tone &debounce (ms):"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=100,
			max=10000,
			initial=config.conf["terminalAccess"].get("outputActivityDebounce", 1000),
		)
		# Translators: Tooltip for activity debounce
		self.outputDebounceSpinner.SetToolTip(_(
			"Milliseconds between activity tone repeats. "
			"Higher values mean fewer tones during sustained output."
		))

	# ------------------------------------------------------------------
	# Gesture binding controls
	# ------------------------------------------------------------------

	def _makeGestureControls(self, group):
		"""Populate the Gesture Bindings section.

		Only gestures that conflict with NVDA's default global commands
		are shown here. Users can disable them to restore the NVDA
		default behavior. All other gesture customization should be done
		through NVDA's Input Gestures dialog (Preferences > Input Gestures).
		"""
		defaultGestures = _get_default_gestures()
		conflicting = _get_conflicting_gestures()
		self._gestureItems = [
			(g, s) for g, s in sorted(defaultGestures.items(), key=lambda x: x[1])
			if g in conflicting
		]
		labels = [_gestureLabel(g, s) for g, s in self._gestureItems]

		# Translators: Label for conflicting gesture bindings checklist
		self.gestureCheckList = group.addLabeledControl(
			_("&Gestures that override NVDA defaults:"),
			nvdaControls.CustomCheckListBox,
			choices=labels,
		)

		try:
			raw = config.conf["terminalAccess"]["unboundGestures"]
		except (KeyError, TypeError):
			raw = ""
		excluded = set(g.strip() for g in raw.split(",") if g.strip())
		for i, (gesture, _script) in enumerate(self._gestureItems):
			self.gestureCheckList.Check(i, gesture not in excluded)
		if labels:
			self.gestureCheckList.Select(0)

		# Translators: Help text for gesture bindings
		group.addItem(
			wx.StaticText(self, label=_(
				"Checked gestures override the NVDA default inside terminals.\n"
				"Unchecked gestures restore the NVDA default. You can still\n"
				"use unchecked commands through the command layer (NVDA+').\n"
				"To customize other gestures, use NVDA Preferences > Input Gestures."
			))
		)

	# ------------------------------------------------------------------
	# Profile management controls
	# ------------------------------------------------------------------

	def _makeProfileControls(self, profileGroup, profileManager):
		"""Populate the Application Profiles section."""

		# Profile list
		# Translators: Label for profile list
		self.profileList = profileGroup.addLabeledControl(
			_("Installed &profiles:"),
			wx.Choice,
			choices=self._getProfileNames(withIndicators=True)
		)
		if len(self._getProfileNames()) > 0:
			self.profileList.SetSelection(0)
		# Translators: Tooltip for profile list
		self.profileList.SetToolTip(_(
			"Select an application profile to view or edit. "
			"Profiles customize Terminal Access behavior for specific applications. "
			"Active and default profiles are marked."
		))

		# Profile action buttons
		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)

		# Translators: Label for new profile button
		self.newProfileButton = wx.Button(self, label=_("&New Profile..."))
		self.newProfileButton.Bind(wx.EVT_BUTTON, self.onNewProfile)
		# Translators: Tooltip for new profile button
		self.newProfileButton.SetToolTip(_(
			"Create a new application profile with custom settings"
		))
		buttonSizer.Add(self.newProfileButton, flag=wx.RIGHT, border=5)

		# Translators: Label for edit profile button
		self.editProfileButton = wx.Button(self, label=_("&Edit Profile..."))
		self.editProfileButton.Bind(wx.EVT_BUTTON, self.onEditProfile)
		# Translators: Tooltip for edit profile button
		self.editProfileButton.SetToolTip(_(
			"Edit the selected application profile"
		))
		buttonSizer.Add(self.editProfileButton, flag=wx.RIGHT, border=5)

		# Translators: Label for delete profile button
		self.deleteProfileButton = wx.Button(self, label=_("&Delete Profile"))
		self.deleteProfileButton.Bind(wx.EVT_BUTTON, self.onDeleteProfile)
		# Translators: Tooltip for delete profile button
		self.deleteProfileButton.SetToolTip(_(
			"Delete the selected custom profile (default profiles cannot be deleted)"
		))
		buttonSizer.Add(self.deleteProfileButton, flag=wx.RIGHT, border=5)

		profileGroup.sizer.Add(buttonSizer, flag=wx.TOP, border=5)

		# Import/Export buttons
		importExportSizer = wx.BoxSizer(wx.HORIZONTAL)

		# Translators: Label for import profile button
		self.importProfileButton = wx.Button(self, label=_("&Import..."))
		self.importProfileButton.Bind(wx.EVT_BUTTON, self.onImportProfile)
		# Translators: Tooltip for import profile button
		self.importProfileButton.SetToolTip(_(
			"Import a profile from a JSON file"
		))
		importExportSizer.Add(self.importProfileButton, flag=wx.RIGHT, border=5)

		# Translators: Label for export profile button
		self.exportProfileButton = wx.Button(self, label=_("E&xport..."))
		self.exportProfileButton.Bind(wx.EVT_BUTTON, self.onExportProfile)
		# Translators: Tooltip for export profile button
		self.exportProfileButton.SetToolTip(_(
			"Export the selected profile to a JSON file"
		))
		importExportSizer.Add(self.exportProfileButton)

		profileGroup.sizer.Add(importExportSizer, flag=wx.TOP, border=5)

		# Update button states based on selection
		self.profileList.Bind(wx.EVT_CHOICE, self.onProfileSelection)
		self.onProfileSelection(None)  # Initialize button states

	# ------------------------------------------------------------------
	# Event handlers
	# ------------------------------------------------------------------

	def onResetToDefaults(self, event):
		"""Reset all settings to their default values."""
		# Translators: Confirmation dialog for resetting settings
		result = gui.messageBox(
			_("Are you sure you want to reset all Terminal Access settings to their default values?"),
			_("Confirm Reset"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
		)

		if result == wx.YES:
			# Reset all settings to defaults
			config.conf["terminalAccess"]["cursorTracking"] = True
			config.conf["terminalAccess"]["cursorTrackingMode"] = CT_STANDARD
			config.conf["terminalAccess"]["keyEcho"] = True
			config.conf["terminalAccess"]["linePause"] = True
			config.conf["terminalAccess"]["punctuationLevel"] = PUNCT_MOST
			config.conf["terminalAccess"]["repeatedSymbols"] = False
			config.conf["terminalAccess"]["repeatedSymbolsValues"] = "-_=!"
			config.conf["terminalAccess"]["cursorDelay"] = 20
			config.conf["terminalAccess"]["quietMode"] = False
			config.conf["terminalAccess"]["verboseMode"] = False
			config.conf["terminalAccess"]["indentationOnLineRead"] = False

			# Update UI to reflect defaults
			self.cursorTrackingCheckBox.SetValue(True)
			self.cursorTrackingModeChoice.SetSelection(CT_STANDARD)
			self.keyEchoCheckBox.SetValue(True)
			self.linePauseCheckBox.SetValue(True)
			self.punctuationLevelChoice.SetSelection(PUNCT_MOST)
			self.repeatedSymbolsCheckBox.SetValue(False)
			self.repeatedSymbolsValuesText.SetValue("-_=!")
			self.cursorDelaySpinner.SetValue(20)
			self.quietModeCheckBox.SetValue(False)
			self.verboseModeCheckBox.SetValue(False)
			self.indentationOnLineReadCheckBox.SetValue(False)
			config.conf["terminalAccess"]["errorAudioCues"] = True
			config.conf["terminalAccess"]["errorAudioCuesInQuietMode"] = False
			config.conf["terminalAccess"]["outputActivityTones"] = False
			config.conf["terminalAccess"]["outputActivityDebounce"] = 1000
			self.errorAudioCuesCheckBox.SetValue(True)
			self.errorCuesQuietModeCheckBox.SetValue(False)
			self.outputActivityTonesCheckBox.SetValue(False)
			self.outputDebounceSpinner.SetValue(1000)

			config.conf["terminalAccess"]["unboundGestures"] = ""
			# Check all items in the gesture checklist (re-enable all gestures)
			for i in range(self.gestureCheckList.GetCount()):
				self.gestureCheckList.Check(i, True)

			# Translators: Message after resetting to defaults
			gui.messageBox(
				_("All settings have been reset to their default values."),
				_("Settings Reset"),
				wx.OK | wx.ICON_INFORMATION
			)

	def onSave(self):
		"""Save the settings when the user clicks OK with validation."""
		# Validate and save cursor tracking mode
		trackingMode = self.cursorTrackingModeChoice.GetSelection()
		config.conf["terminalAccess"]["cursorTracking"] = self.cursorTrackingCheckBox.GetValue()
		config.conf["terminalAccess"]["cursorTrackingMode"] = _validateInteger(
			trackingMode, 0, 3, 1, "cursorTrackingMode"
		)

		# Boolean settings (no validation needed)
		config.conf["terminalAccess"]["keyEcho"] = self.keyEchoCheckBox.GetValue()
		config.conf["terminalAccess"]["linePause"] = self.linePauseCheckBox.GetValue()
		config.conf["terminalAccess"]["repeatedSymbols"] = self.repeatedSymbolsCheckBox.GetValue()
		config.conf["terminalAccess"]["quietMode"] = self.quietModeCheckBox.GetValue()
		config.conf["terminalAccess"]["verboseMode"] = self.verboseModeCheckBox.GetValue()
		config.conf["terminalAccess"]["indentationOnLineRead"] = self.indentationOnLineReadCheckBox.GetValue()

		# Validate and save punctuation level
		punctLevel = self.punctuationLevelChoice.GetSelection()
		config.conf["terminalAccess"]["punctuationLevel"] = _validateInteger(
			punctLevel, 0, 3, 2, "punctuationLevel"
		)

		# Validate and save repeated symbols string
		repeatedSymbolsValue = self.repeatedSymbolsValuesText.GetValue()
		config.conf["terminalAccess"]["repeatedSymbolsValues"] = _validateString(
			repeatedSymbolsValue, MAX_REPEATED_SYMBOLS_LENGTH, "-_=!", "repeatedSymbolsValues"
		)

		# Validate and save cursor delay
		cursorDelay = self.cursorDelaySpinner.GetValue()
		config.conf["terminalAccess"]["cursorDelay"] = _validateInteger(
			cursorDelay, 0, 1000, 20, "cursorDelay"
		)

		# Save default profile setting
		defaultProfileIndex = self.defaultProfileChoice.GetSelection()
		if defaultProfileIndex == 0:
			config.conf["terminalAccess"]["defaultProfile"] = ""
		else:
			profileNames = self._getProfileNames()
			if defaultProfileIndex - 1 < len(profileNames):
				config.conf["terminalAccess"]["defaultProfile"] = profileNames[defaultProfileIndex - 1]
			else:
				config.conf["terminalAccess"]["defaultProfile"] = ""

		# Save audio cue settings
		config.conf["terminalAccess"]["errorAudioCues"] = self.errorAudioCuesCheckBox.GetValue()
		config.conf["terminalAccess"]["errorAudioCuesInQuietMode"] = self.errorCuesQuietModeCheckBox.GetValue()
		config.conf["terminalAccess"]["outputActivityTones"] = self.outputActivityTonesCheckBox.GetValue()
		config.conf["terminalAccess"]["outputActivityDebounce"] = _validateInteger(
			self.outputDebounceSpinner.GetValue(), 100, 10000, 1000, "outputActivityDebounce"
		)

		# Save gesture exclusions
		unchecked = []
		for i, (gesture, _script) in enumerate(self._gestureItems):
			if not self.gestureCheckList.IsChecked(i):
				unchecked.append(gesture)
		config.conf["terminalAccess"]["unboundGestures"] = ",".join(unchecked)

		# Live-reload gesture bindings
		try:
			from globalPlugins.terminalAccess import GlobalPlugin
			for plugin in globalPluginHandler.runningPlugins:
				if isinstance(plugin, GlobalPlugin):
					plugin._reloadGestures()
					break
		except (StopIteration, Exception):
			pass

	# ------------------------------------------------------------------
	# Profile helpers
	# ------------------------------------------------------------------

	def _getProfileManager(self):
		"""Return the shared ProfileManager from the running global plugin, if available."""
		try:
			from globalPlugins import terminalAccess
			for plugin in globalPluginHandler.runningPlugins:
				if isinstance(plugin, terminalAccess.GlobalPlugin):
					return getattr(plugin, "_profileManager", None)
		except Exception:
			return None
		return None

	def _getProfileNames(self, withIndicators=False):
		"""Get list of profile names for the dropdown.

		Args:
			withIndicators: If True, add indicators for active/default profiles
		"""
		try:
			from globalPlugins import terminalAccess
			for plugin in globalPluginHandler.runningPlugins:
				if isinstance(plugin, terminalAccess.GlobalPlugin):
					if hasattr(plugin, '_profileManager') and plugin._profileManager:
						names = list(plugin._profileManager.profiles.keys())
						default_profiles = _BUILTIN_PROFILE_NAMES
						defaults = [n for n in names if n in default_profiles]
						customs = [n for n in names if n not in default_profiles]
						sortedNames = sorted(defaults) + sorted(customs)

						if withIndicators:
							activeProfile = plugin._currentProfile
							defaultProfileName = config.conf["terminalAccess"].get("defaultProfile", "")

							indicatorNames = []
							for name in sortedNames:
								indicators = []
								if activeProfile and activeProfile.appName == name:
									# Translators: Indicator for currently active profile
									indicators.append(_("Active"))
								if name == defaultProfileName:
									# Translators: Indicator for default profile
									indicators.append(_("Default"))

								if indicators:
									indicatorNames.append(f"{name} ({', '.join(indicators)})")
								else:
									indicatorNames.append(name)
							return indicatorNames
						else:
							return sortedNames
			return []
		except Exception:
			return []

	def _getSelectedProfileName(self):
		"""Get the currently selected profile name (without indicators)."""
		selection = self.profileList.GetSelection()
		if selection != wx.NOT_FOUND:
			displayName = self.profileList.GetString(selection)
			if ' (' in displayName:
				return displayName.split(' (')[0]
			return displayName
		return None

	def _isDefaultProfile(self, profileName):
		"""Check if a profile is a default (built-in) profile."""
		return profileName in _BUILTIN_PROFILE_NAMES

	def onProfileSelection(self, event):
		"""Update button states when profile selection changes."""
		profileName = self._getSelectedProfileName()
		hasSelection = profileName is not None
		isDefault = self._isDefaultProfile(profileName) if profileName else False

		self.editProfileButton.Enable(hasSelection)
		self.deleteProfileButton.Enable(hasSelection and not isDefault)
		self.exportProfileButton.Enable(hasSelection)

	def onNewProfile(self, event):
		"""Create a new application profile."""
		# Translators: Message for profile creation
		gui.messageBox(
			_("Profile creation dialog will be implemented soon. "
			  "For now, profiles can be created programmatically via the ProfileManager API."),
			_("Feature In Development"),
			wx.OK | wx.ICON_INFORMATION
		)

	def onEditProfile(self, event):
		"""Edit the selected profile."""
		profileName = self._getSelectedProfileName()
		if not profileName:
			return

		# Translators: Message for profile editing
		gui.messageBox(
			_("Profile editing dialog will be implemented soon. "
			  "Selected profile: {name}").format(name=profileName),
			_("Feature In Development"),
			wx.OK | wx.ICON_INFORMATION
		)

	def onDeleteProfile(self, event):
		"""Delete the selected custom profile."""
		profileName = self._getSelectedProfileName()
		if not profileName or self._isDefaultProfile(profileName):
			return

		# Translators: Confirmation dialog for deleting profile
		result = gui.messageBox(
			_("Are you sure you want to delete the profile '{name}'?").format(name=profileName),
			_("Confirm Delete"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
		)

		if result == wx.YES:
			try:
				from globalPlugins import terminalAccess
				for plugin in globalPluginHandler.runningPlugins:
					if isinstance(plugin, terminalAccess.GlobalPlugin):
						if hasattr(plugin, '_profileManager') and plugin._profileManager:
							plugin._profileManager.removeProfile(profileName)
							self.profileList.SetItems(self._getProfileNames())
							if len(self._getProfileNames()) > 0:
								self.profileList.SetSelection(0)
							self.onProfileSelection(None)
							# Translators: Message after deleting profile
							gui.messageBox(
								_("Profile '{name}' has been deleted.").format(name=profileName),
								_("Profile Deleted"),
								wx.OK | wx.ICON_INFORMATION
							)
							return
			except Exception as e:
				import logHandler
				logHandler.log.error(f"Terminal Access: Failed to delete profile: {e}")
				# Translators: Error message for profile deletion
				gui.messageBox(
					_("Failed to delete profile. See NVDA log for details."),
					_("Error"),
					wx.OK | wx.ICON_ERROR
				)

	def onImportProfile(self, event):
		"""Import a profile from a JSON file."""
		# Translators: File dialog for importing profile
		with wx.FileDialog(
			self,
			_("Import Profile"),
			defaultDir=os.path.expanduser("~"),
			wildcard=_("JSON files (*.json)|*.json"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
		) as fileDialog:
			if fileDialog.ShowModal() == wx.ID_CANCEL:
				return

			pathname = fileDialog.GetPath()
			try:
				import json
				with open(pathname, 'r', encoding='utf-8') as f:
					profileData = json.load(f)

				from globalPlugins import terminalAccess
				for plugin in globalPluginHandler.runningPlugins:
					if isinstance(plugin, terminalAccess.GlobalPlugin):
						if hasattr(plugin, '_profileManager') and plugin._profileManager:
							profile = plugin._profileManager.importProfile(profileData)
							self.profileList.SetItems(self._getProfileNames())
							profileIndex = self.profileList.FindString(profile.appName)
							if profileIndex != wx.NOT_FOUND:
								self.profileList.SetSelection(profileIndex)
							self.onProfileSelection(None)
							# Translators: Message after importing profile
							gui.messageBox(
								_("Profile '{name}' has been imported successfully.").format(
									name=profile.displayName
								),
								_("Profile Imported"),
								wx.OK | wx.ICON_INFORMATION
							)
							return
			except Exception as e:
				import logHandler
				logHandler.log.error(f"Terminal Access: Failed to import profile: {e}")
				# Translators: Error message for profile import
				gui.messageBox(
					_("Failed to import profile. The file may be invalid or corrupted."),
					_("Import Error"),
					wx.OK | wx.ICON_ERROR
				)

	def onExportProfile(self, event):
		"""Export the selected profile to a JSON file."""
		profileName = self._getSelectedProfileName()
		if not profileName:
			return

		try:
			from globalPlugins import terminalAccess
			for plugin in globalPluginHandler.runningPlugins:
				if isinstance(plugin, terminalAccess.GlobalPlugin):
					if hasattr(plugin, '_profileManager') and plugin._profileManager:
						profileData = plugin._profileManager.exportProfile(profileName)
						if not profileData:
							return

						# Translators: File dialog for exporting profile
						with wx.FileDialog(
							self,
							_("Export Profile"),
							defaultDir=os.path.expanduser("~"),
							defaultFile=f"{profileName}_profile.json",
							wildcard=_("JSON files (*.json)|*.json"),
							style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
						) as fileDialog:
							if fileDialog.ShowModal() == wx.ID_CANCEL:
								return

							pathname = fileDialog.GetPath()
							import json
							with open(pathname, 'w', encoding='utf-8') as f:
								json.dump(profileData, f, indent=2, ensure_ascii=False)

							# Translators: Message after exporting profile
							gui.messageBox(
								_("Profile '{name}' has been exported successfully.").format(name=profileName),
								_("Profile Exported"),
								wx.OK | wx.ICON_INFORMATION
							)
							return
		except Exception as e:
			import logHandler
			logHandler.log.error(f"Terminal Access: Failed to export profile: {e}")
			# Translators: Error message for profile export
			gui.messageBox(
				_("Failed to export profile. See NVDA log for details."),
				_("Export Error"),
				wx.OK | wx.ICON_ERROR
			)
