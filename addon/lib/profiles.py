# Terminal Access application profiles.
# Extracted from terminalAccess.py for modularization.

from typing import Any

from lib.config import (
	_validateInteger, _validateString,
	CT_STANDARD, CT_WINDOW,
	PUNCT_SOME, PUNCT_MOST, PUNCT_ALL,
	MAX_WINDOW_DIMENSION, MAX_REPEATED_SYMBOLS_LENGTH,
)

# Frozenset of all supported terminal application names (used in isTerminalApp)
_SUPPORTED_TERMINALS: frozenset[str] = frozenset([
	# Built-in Windows terminal applications
	"windowsterminal",  # Windows Terminal
	"cmd",              # Command Prompt
	"powershell",       # Windows PowerShell
	"pwsh",             # PowerShell Core
	"conhost",          # Console Host
	# Third-party terminal emulators
	"cmder",            # Cmder
	"conemu",           # ConEmu (32-bit)
	"conemu64",         # ConEmu (64-bit)
	"mintty",           # Git Bash (mintty)
	"putty",            # PuTTY
	"kitty",            # KiTTY (PuTTY fork)
	"terminus",         # Terminus
	"hyper",            # Hyper
	"alacritty",        # Alacritty
	"wezterm",          # WezTerm
	"wezterm-gui",      # WezTerm GUI
	"tabby",            # Tabby
	"fluent",           # FluentTerminal
	# WSL (Windows Subsystem for Linux)
	"wsl",              # WSL executable
	"bash",             # WSL bash
	# Modern GPU-accelerated terminals
	"ghostty",          # Ghostty
	"rio",              # Rio
	"waveterm",         # Wave Terminal
	"contour",          # Contour Terminal
	"cool-retro-term",  # Cool Retro Term
	# Remote access / professional terminals
	"mobaxterm",        # MobaXterm
	"securecrt",        # SecureCRT
	"ttermpro",         # Tera Term
	"mremoteng",        # mRemoteNG
	"royalts",          # Royal TS
])

# Applications that share a process name prefix with a supported terminal
# but are NOT terminals themselves.  Checked before _SUPPORTED_TERMINALS.
_NON_TERMINAL_APPS: frozenset[str] = frozenset([
	"securefx",         # VanDyke SecureFX (SFTP client, shares branding with SecureCRT)
	"sfxcl",            # SecureFX command-line utility
	"microsoft.cmdpal", # PowerToys Command Palette ("cmd" substring false positive)
	"powertoys",        # PowerToys settings and utilities
])

# Frozenset of built-in profile names that cannot be removed
_BUILTIN_PROFILE_NAMES: frozenset[str] = frozenset([
	'vim', 'tmux', 'htop', 'less', 'git', 'nano', 'irssi',
	'claude', 'lazygit', 'btop', 'btm', 'yazi', 'k9s',
	'kubectl', 'npm', 'pytest', 'cargo', 'docker',
])

# Terminals that strip ANSI escape codes from UIA text (highlight detection is pointless)
_ANSI_STRIPPING_TERMINALS: frozenset[str] = frozenset([
	"windowsterminal", "alacritty", "wezterm", "wezterm-gui",
	"ghostty", "rio", "contour",
])


class WindowDefinition:
	"""
	Definition of a window region in terminal output.

	Used for tracking specific regions of terminal display (e.g., tmux panes,
	vim status line, htop process list).

	Window Modes:
		- 'announce': Read content normally (default)
		- 'silent': Suppress all speech for this region
		- 'monitor': Track changes but announce differently

	Coordinate System:
		All coordinates are 1-based (row 1, col 1 is top-left).
	"""

	__slots__ = ('name', 'top', 'bottom', 'left', 'right', 'mode', 'enabled')

	def __init__(self, name: str, top: int, bottom: int, left: int, right: int,
				 mode: str = 'announce', enabled: bool = True) -> None:
		"""
		Initialize a window definition.

		Args:
			name: Window name (e.g., "main pane", "status line")
			top: Top row (1-based)
			bottom: Bottom row (1-based)
			left: Left column (1-based)
			right: Right column (1-based)
			mode: Window mode ('announce', 'silent', 'monitor')
			enabled: Whether window is currently active
		"""
		self.name: str = name
		self.top: int = top
		self.bottom: int = bottom
		self.left: int = left
		self.right: int = right
		self.mode: str = mode  # 'announce' = read content, 'silent' = suppress, 'monitor' = track changes
		self.enabled: bool = enabled

	def contains(self, row: int, col: int) -> bool:
		"""
		Check if a position is within this window.

		Args:
			row: Row number (1-based)
			col: Column number (1-based)

		Returns:
			bool: True if position is within window bounds
		"""
		return (self.enabled and
				self.top <= row <= self.bottom and
				self.left <= col <= self.right)

	def to_dict(self) -> dict[str, Any]:
		"""Convert window definition to dictionary for serialization."""
		return {
			'name': self.name,
			'top': self.top,
			'bottom': self.bottom,
			'left': self.left,
			'right': self.right,
			'mode': self.mode,
			'enabled': self.enabled,
		}

	# Deprecated camelCase alias
	toDict = to_dict

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> 'WindowDefinition':
		"""Create window definition from dictionary with validation."""
		return cls(
			name=_validateString(data.get('name', ''), 64, '', 'windowName'),
			top=_validateInteger(data.get('top', 0), 0, MAX_WINDOW_DIMENSION, 0, 'windowTop'),
			bottom=_validateInteger(data.get('bottom', 0), 0, MAX_WINDOW_DIMENSION, 0, 'windowBottom'),
			left=_validateInteger(data.get('left', 0), 0, MAX_WINDOW_DIMENSION, 0, 'windowLeft'),
			right=_validateInteger(data.get('right', 0), 0, MAX_WINDOW_DIMENSION, 0, 'windowRight'),
			mode=data.get('mode', 'announce') if data.get('mode') in ('announce', 'monitor', 'silent') else 'announce',
			enabled=bool(data.get('enabled', True)),
		)

	# Deprecated camelCase alias
	fromDict = from_dict


class ApplicationProfile:
	"""
	Application-specific configuration profile for terminal applications.

	Allows customizing Terminal Access behavior for different applications (vim, tmux, htop, etc.).

	Profile Inheritance:
		Settings set to None inherit from global Terminal Access settings.
		Non-None values override global settings for this application.

	Window Tracking:
		Profiles can define multiple non-overlapping windows.
		Windows are checked in order; first match wins.
	"""

	def __init__(self, appName: str, displayName: str | None = None) -> None:
		"""
		Initialize an application profile.

		Args:
			appName: Application identifier (e.g., "vim", "tmux", "htop")
			displayName: Human-readable name (e.g., "Vim/Neovim")
		"""
		self.appName: str = appName
		self.displayName: str = displayName or appName

		# Settings overrides (None = use global setting)
		self.punctuationLevel: int | None = None
		self.cursorTrackingMode: int | None = None
		self.keyEcho: bool | None = None
		self.linePause: bool | None = None
		self.processSymbols: bool | None = None
		self.repeatedSymbols: bool | None = None
		self.repeatedSymbolsValues: str | None = None
		self.cursorDelay: int | None = None
		self.quietMode: bool | None = None
		self.announceIndentation: bool | None = None
		self.indentationOnLineRead: bool | None = None

		# Multiplexer-specific: only announce content from the focused pane
		self.focusedPaneOnly: bool | None = None

		# Window definitions (list of WindowDefinition objects)
		self.windows: list[WindowDefinition] = []

		# Custom gestures (dict of gesture -> function name)
		self.customGestures: dict[str, str] = {}

	def add_window(self, name: str, top: int, bottom: int, left: int, right: int,
				  mode: str = 'announce') -> WindowDefinition:
		"""Add a window definition to this profile."""
		window = WindowDefinition(name, top, bottom, left, right, mode)
		self.windows.append(window)
		return window

	# Deprecated camelCase alias
	addWindow = add_window

	def get_window_at_position(self, row: int, col: int) -> WindowDefinition | None:
		"""Get the window containing the specified position."""
		for window in self.windows:
			if window.contains(row, col):
				return window
		return None

	# Deprecated camelCase alias
	getWindowAtPosition = get_window_at_position

	def to_dict(self) -> dict[str, Any]:
		"""Convert profile to dictionary for serialization."""
		return {
			'appName': self.appName,
			'displayName': self.displayName,
			'punctuationLevel': self.punctuationLevel,
			'cursorTrackingMode': self.cursorTrackingMode,
			'keyEcho': self.keyEcho,
			'linePause': self.linePause,
			'processSymbols': self.processSymbols,
			'repeatedSymbols': self.repeatedSymbols,
			'repeatedSymbolsValues': self.repeatedSymbolsValues,
			'cursorDelay': self.cursorDelay,
			'quietMode': self.quietMode,
			'announceIndentation': self.announceIndentation,
			'indentationOnLineRead': self.indentationOnLineRead,
			'windows': [w.to_dict() for w in self.windows],
			'customGestures': self.customGestures,
		}

	# Deprecated camelCase alias
	toDict = to_dict

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> 'ApplicationProfile':
		"""Create profile from dictionary with field validation."""
		profile = cls(
			_validateString(data.get('appName', ''), 64, '', 'appName'),
			_validateString(data.get('displayName', ''), 128, None, 'displayName'),
		)

		# Validate integer fields with known ranges (None = use global)
		raw = data.get('punctuationLevel')
		profile.punctuationLevel = _validateInteger(raw, 0, 3, 2, 'punctuationLevel') if raw is not None else None
		raw = data.get('cursorTrackingMode')
		profile.cursorTrackingMode = _validateInteger(raw, 0, 3, 1, 'cursorTrackingMode') if raw is not None else None
		raw = data.get('linePause')
		profile.linePause = _validateInteger(raw, 0, 1000, 20, 'linePause') if raw is not None else None
		raw = data.get('cursorDelay')
		profile.cursorDelay = _validateInteger(raw, 50, 2000, 200, 'cursorDelay') if raw is not None else None

		# Validate boolean fields (None = use global)
		for field in ('keyEcho', 'processSymbols', 'repeatedSymbols', 'quietMode',
		              'announceIndentation', 'indentationOnLineRead'):
			val = data.get(field)
			setattr(profile, field, bool(val) if val is not None else None)

		raw = data.get('repeatedSymbolsValues')
		profile.repeatedSymbolsValues = _validateString(raw, MAX_REPEATED_SYMBOLS_LENGTH, '-_=!', 'repeatedSymbolsValues') if raw is not None else None

		# Restore windows
		windows_data = data.get('windows', [])
		if isinstance(windows_data, list):
			for winData in windows_data:
				if isinstance(winData, dict):
					profile.windows.append(WindowDefinition.from_dict(winData))

		# Validate customGestures: only allow known gesture pattern -> script name
		raw_gestures = data.get('customGestures', {})
		if isinstance(raw_gestures, dict):
			safe_gestures = {}
			for gesture, script_name in raw_gestures.items():
				# Gesture keys must be "kb:..." strings; script names must be alphanumeric
				if (isinstance(gesture, str) and isinstance(script_name, str)
						and gesture.startswith('kb:') and script_name.isidentifier()):
					safe_gestures[gesture] = script_name
			profile.customGestures = safe_gestures
		else:
			profile.customGestures = {}

		return profile

	# Deprecated camelCase alias
	fromDict = from_dict


class ProfileManager:
	"""
	Manager for application-specific profiles.

	Handles profile creation, detection, loading, and application.

	Default Profiles:
		Includes pre-configured profiles for:
		- vim/nvim: Editor with status line suppression
		- tmux: Terminal multiplexer with status bar
		- htop: Process viewer with header/process regions
		- less/more: Pager with quiet mode
		- git: Version control with diff support
		- nano: Editor with shortcut bar suppression
		- irssi: IRC client with status bar

	Profile Detection:
		1. Check app module name (focusObject.appModule.appName)
		2. Check window title for common patterns
		3. Return 'default' if no match found
	"""

	def __init__(self) -> None:
		"""Initialize the profile manager with default profiles."""
		self.profiles: dict[str, ApplicationProfile] = {}
		self.activeProfile: ApplicationProfile | None = None
		self._initializeDefaultProfiles()

	def _initializeDefaultProfiles(self) -> None:
		"""Create default profiles for popular terminal applications."""

		# Vim/Neovim profile
		vim = ApplicationProfile('vim', 'Vim/Neovim')
		vim.punctuationLevel = PUNCT_MOST  # More punctuation for code
		vim.cursorTrackingMode = CT_WINDOW  # Use window tracking
		# Silence bottom two lines (status line and command line)
		vim.add_window('editor', 1, 9999, 1, 9999, mode='announce')
		vim.add_window('status', 9999, 9999, 1, 9999, mode='silent')
		self.profiles['vim'] = vim
		self.profiles['nvim'] = vim  # Same profile for neovim

		# tmux profile
		tmux = ApplicationProfile('tmux', 'tmux (Terminal Multiplexer)')
		tmux.cursorTrackingMode = CT_STANDARD
		tmux.focusedPaneOnly = True
		# Status bar at bottom (typically last line)
		tmux.add_window('status', 9999, 9999, 1, 9999, mode='silent')
		self.profiles['tmux'] = tmux

		# htop profile
		htop = ApplicationProfile('htop', 'htop (Process Viewer)')
		htop.repeatedSymbols = False  # Lots of repeated characters in bars
		# Header area (first ~4 lines with CPU/Memory meters)
		htop.add_window('header', 1, 4, 1, 9999, mode='announce')
		# Process list (main area)
		htop.add_window('processes', 5, 9999, 1, 9999, mode='announce')
		self.profiles['htop'] = htop

		# less/more pager profile
		less = ApplicationProfile('less', 'less/more (Pager)')
		less.quietMode = True  # Reduce verbosity for reading
		less.keyEcho = False  # Don't echo navigation keys
		self.profiles['less'] = less
		self.profiles['more'] = less

		# git profile (for git diff, log, etc.)
		git = ApplicationProfile('git', 'Git')
		git.punctuationLevel = PUNCT_MOST  # Show symbols in diffs
		git.repeatedSymbols = False  # Many dashes and equals signs
		self.profiles['git'] = git

		# nano editor profile
		nano = ApplicationProfile('nano', 'GNU nano')
		nano.cursorTrackingMode = CT_STANDARD
		# Silence bottom two lines (status and shortcuts)
		nano.add_window('editor', 1, 9997, 1, 9999, mode='announce')
		nano.add_window('shortcuts', 9998, 9999, 1, 9999, mode='silent')
		self.profiles['nano'] = nano

		# irssi (IRC client) profile
		irssi = ApplicationProfile('irssi', 'irssi (IRC Client)')
		irssi.punctuationLevel = PUNCT_SOME  # Basic punctuation for chat
		irssi.linePause = False  # Fast reading for chat
		# Status bar at bottom
		irssi.add_window('status', 9999, 9999, 1, 9999, mode='silent')
		self.profiles['irssi'] = irssi

		# Third-party terminal profiles (Sections 5.1, 5.2, 5.3, 5.4)
		# Data-driven: each entry is (appName, displayName, aliases, punct_override)
		# All use CT_STANDARD; punct defaults to PUNCT_SOME unless overridden.
		_SIMPLE_TERMINAL_PROFILES = [
			# Section 5.1: Third-party terminal emulators (v1.0.26+)
			('cmder',          'Cmder',                     (),              None),
			('conemu',         'ConEmu',                    ('conemu64',),   None),
			('mintty',         'Git Bash (mintty)',          (),              PUNCT_MOST),
			('putty',          'PuTTY',                     ('kitty',),      None),
			('terminus',       'Terminus',                   (),              None),
			('hyper',          'Hyper',                      (),              None),
			('alacritty',      'Alacritty',                  (),              None),
			('wezterm',        'WezTerm',                    ('wezterm-gui',), None),
			('tabby',          'Tabby',                      (),              None),
			('fluent',         'FluentTerminal',             (),              None),
			# Section 5.3: Modern GPU-accelerated terminals (v1.0.49+)
			('ghostty',        'Ghostty',                    (),              None),
			('rio',            'Rio',                        (),              None),
			('waveterm',       'Wave Terminal',              (),              None),
			('contour',        'Contour Terminal',           (),              None),
			('cool-retro-term', 'Cool Retro Term',           (),              None),
			# Section 5.4: Remote access / professional terminals (v1.0.49+)
			('mobaxterm',      'MobaXterm',                  (),              None),
			('securecrt',      'SecureCRT',                  (),              None),
			('ttermpro',       'Tera Term',                  (),              None),
			('mremoteng',      'mRemoteNG',                  (),              None),
			('royalts',        'Royal TS',                   (),              None),
		]

		for appName, displayName, aliases, punct_override in _SIMPLE_TERMINAL_PROFILES:
			profile = ApplicationProfile(appName, displayName)
			profile.punctuationLevel = punct_override if punct_override is not None else PUNCT_SOME
			profile.cursorTrackingMode = CT_STANDARD
			self.profiles[appName] = profile
			for alias in aliases:
				self.profiles[alias] = profile

		# Section 5.2: WSL (Windows Subsystem for Linux) profile (v1.0.27+)
		# Optimized for Linux command-line environment (custom settings beyond simple)
		wsl = ApplicationProfile('wsl', 'Windows Subsystem for Linux')
		wsl.punctuationLevel = PUNCT_MOST  # Code-friendly for Linux commands
		wsl.cursorTrackingMode = CT_STANDARD
		wsl.repeatedSymbols = False  # Common in command output (progress bars, etc.)
		self.profiles['wsl'] = wsl
		self.profiles['bash'] = wsl  # Use same profile for bash

		# Section 5.5: TUI Application profiles (v1.0.49+)

		# Claude CLI profile
		claude = ApplicationProfile('claude', 'Claude CLI')
		claude.punctuationLevel = PUNCT_MOST  # Code-heavy output needs punctuation
		claude.repeatedSymbols = False  # Markdown-style separators in output
		claude.linePause = False  # Fast reading for streaming responses
		claude.keyEcho = False  # Don't echo typing during input
		# Silence bottom status bar region
		claude.add_window('conversation', 1, 9997, 1, 9999, mode='announce')
		claude.add_window('statusbar', 9998, 9999, 1, 9999, mode='silent')
		self.profiles['claude'] = claude

		# lazygit profile
		lazygit = ApplicationProfile('lazygit', 'lazygit')
		lazygit.punctuationLevel = PUNCT_MOST  # Git diff symbols
		lazygit.repeatedSymbols = False  # Many repeated chars in borders/diffs
		lazygit.keyEcho = False  # Single-key shortcuts
		lazygit.cursorTrackingMode = CT_WINDOW
		# Panel layout: announce all content
		lazygit.add_window('main', 1, 9999, 1, 9999, mode='announce')
		self.profiles['lazygit'] = lazygit

		# btop/btm profile (system monitor)
		btop = ApplicationProfile('btop', 'btop/btm (System Monitor)')
		btop.repeatedSymbols = False  # Progress bars, box-drawing
		btop.keyEcho = False  # Single-key navigation
		btop.linePause = False  # Fast refresh rates
		# Header with CPU/memory meters
		btop.add_window('header', 1, 6, 1, 9999, mode='announce')
		btop.add_window('processes', 7, 9999, 1, 9999, mode='announce')
		self.profiles['btop'] = btop
		self.profiles['btm'] = btop  # bottom uses same profile

		# yazi profile (file manager)
		yazi = ApplicationProfile('yazi', 'yazi (File Manager)')
		yazi.punctuationLevel = PUNCT_SOME
		yazi.keyEcho = False  # Single-key shortcuts
		yazi.repeatedSymbols = False  # File listing separators
		yazi.cursorTrackingMode = CT_STANDARD
		self.profiles['yazi'] = yazi

		# k9s profile (Kubernetes TUI)
		k9s = ApplicationProfile('k9s', 'k9s (Kubernetes)')
		k9s.punctuationLevel = PUNCT_MOST  # Namespace/pod names with symbols
		k9s.repeatedSymbols = False  # Table borders
		k9s.keyEcho = False  # Single-key navigation
		k9s.linePause = False  # Fast status updates
		self.profiles['k9s'] = k9s

		# Section 5.6: CLI tool profiles (v1.4.1+)

		# kubectl profile (kubectl logs, kubectl get, etc.)
		kubectl = ApplicationProfile('kubectl', 'kubectl (Kubernetes CLI)')
		kubectl.punctuationLevel = PUNCT_MOST  # Timestamp prefixes, error codes
		kubectl.cursorTrackingMode = CT_STANDARD
		kubectl.repeatedSymbols = False  # Log separators
		kubectl.linePause = False  # Streaming logs
		self.profiles['kubectl'] = kubectl

		# npm/yarn profile
		npm = ApplicationProfile('npm', 'npm/yarn (Node Package Manager)')
		npm.punctuationLevel = PUNCT_MOST  # ERR!, WARN markers
		npm.cursorTrackingMode = CT_STANDARD
		npm.repeatedSymbols = False  # Progress bars
		self.profiles['npm'] = npm
		self.profiles['yarn'] = npm

		# pytest profile
		pytest_prof = ApplicationProfile('pytest', 'pytest (Python Test Runner)')
		pytest_prof.punctuationLevel = PUNCT_MOST  # PASSED/FAILED markers, assertions
		pytest_prof.cursorTrackingMode = CT_STANDARD
		pytest_prof.repeatedSymbols = False  # Separator lines (===, ---)
		self.profiles['pytest'] = pytest_prof

		# cargo profile (Rust build tool)
		cargo = ApplicationProfile('cargo', 'cargo (Rust Build Tool)')
		cargo.punctuationLevel = PUNCT_MOST  # Compiler output, error codes
		cargo.cursorTrackingMode = CT_STANDARD
		cargo.repeatedSymbols = False  # Compiler output separators
		cargo.linePause = False  # Fast build output
		self.profiles['cargo'] = cargo

		# docker profile
		docker = ApplicationProfile('docker', 'Docker')
		docker.punctuationLevel = PUNCT_MOST  # Build step markers, image tags
		docker.cursorTrackingMode = CT_STANDARD
		docker.repeatedSymbols = False  # Build step output
		self.profiles['docker'] = docker

	def detect_application(self, focusObject: Any) -> str:
		"""
		Detect the current terminal application.

		Args:
			focusObject: NVDA focus object

		Returns:
			str: Application name or 'default'
		"""
		try:
			# Try to get app name from app module
			if hasattr(focusObject, 'appModule') and hasattr(focusObject.appModule, 'appName'):
				appName = focusObject.appModule.appName.lower()

				# Check if we have a profile for this app
				if appName in self.profiles:
					return appName

			# Try to detect from window title
			if hasattr(focusObject, 'name'):
				title = focusObject.name.lower()

				# Check for common patterns
				# Note: more specific matches (lazygit) must come before
				# less specific ones (git) to avoid false positives.
				if 'vim' in title or 'nvim' in title:
					return 'vim'
				elif 'tmux' in title:
					return 'tmux'
				elif 'btop' in title or 'btm' in title:
					return 'btop'
				elif 'htop' in title:
					return 'htop'
				elif 'less' in title or 'more' in title:
					return 'less'
				elif 'lazygit' in title:
					return 'lazygit'
				elif 'git' in title:
					return 'git'
				elif 'nano' in title:
					return 'nano'
				elif 'irssi' in title:
					return 'irssi'
				# TUI applications (detected by window title)
				elif 'claude' in title:
					return 'claude'
				elif 'yazi' in title:
					return 'yazi'
				elif 'k9s' in title:
					return 'k9s'
				# CLI tool profiles (detected by window title)
				elif 'kubectl' in title:
					return 'kubectl'
				elif 'pytest' in title:
					return 'pytest'
				elif 'npm' in title:
					return 'npm'
				elif 'yarn' in title:
					return 'npm'
				elif 'cargo' in title:
					return 'cargo'
				elif 'docker' in title:
					return 'docker'

		except (AttributeError, TypeError):
			pass

		return 'default'

	# Deprecated camelCase alias
	detectApplication = detect_application

	def get_profile(self, appName: str) -> ApplicationProfile | None:
		"""Get profile for specified application."""
		return self.profiles.get(appName)

	# Deprecated camelCase alias
	getProfile = get_profile

	def set_active_profile(self, appName: str) -> None:
		"""Set the currently active profile."""
		self.activeProfile = self.profiles.get(appName)

	# Deprecated camelCase alias
	setActiveProfile = set_active_profile

	def add_profile(self, profile: ApplicationProfile) -> None:
		"""Add or update a profile."""
		self.profiles[profile.appName] = profile

	# Deprecated camelCase alias
	addProfile = add_profile

	def remove_profile(self, appName: str) -> None:
		"""Remove a profile."""
		if appName in self.profiles and appName not in _BUILTIN_PROFILE_NAMES:
			del self.profiles[appName]

	# Deprecated camelCase alias
	removeProfile = remove_profile

	def export_profile(self, appName: str) -> dict[str, Any] | None:
		"""Export profile to dictionary."""
		profile = self.profiles.get(appName)
		if profile:
			return profile.to_dict()
		return None

	# Deprecated camelCase alias
	exportProfile = export_profile

	def import_profile(self, data: dict[str, Any]) -> ApplicationProfile:
		"""Import profile from dictionary."""
		profile = ApplicationProfile.from_dict(data)
		self.add_profile(profile)
		return profile

	# Deprecated camelCase alias
	importProfile = import_profile

	def get_profile_names(self) -> list[str]:
		"""Return sorted list of unique profile display names."""
		seen = set()
		names = []
		for profile in self.profiles.values():
			if profile.displayName not in seen:
				seen.add(profile.displayName)
				names.append(profile.appName)
		names.sort()
		return names


try:
	import wx

	class ProfileSelectionDialog(wx.Dialog):
		"""Dialog for selecting and activating an application profile.

		Shows all available profiles in a list. Press Enter or the Activate
		button to switch to the selected profile. Press Escape or Close to
		cancel.
		"""

		def __init__(self, parent, profile_manager, on_activate):
			super().__init__(
				parent,
				title=_("Select Profile"),
				style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
			)
			self._manager = profile_manager
			self._on_activate = on_activate
			self._profile_names = []
			self._build_ui()
			self._populate()
			self.Raise()

		def _build_ui(self):
			sizer = wx.BoxSizer(wx.VERTICAL)

			self._list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
			self._list.InsertColumn(0, _("Profile"), width=150)
			self._list.InsertColumn(1, _("Description"), width=300)
			sizer.Add(self._list, proportion=1, flag=wx.EXPAND | wx.ALL, border=8)

			btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
			self._activate_btn = wx.Button(self, label=_("&Activate"))
			self._close_btn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
			btn_sizer.Add(self._activate_btn, flag=wx.RIGHT, border=4)
			btn_sizer.Add(self._close_btn)
			sizer.Add(btn_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=8)

			self.SetSizer(sizer)
			self.SetSize(500, 350)

			self._activate_btn.Bind(wx.EVT_BUTTON, self._on_activate_click)
			self._close_btn.Bind(wx.EVT_BUTTON, self._on_close)
			self._list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_activate_click)
			self._list.Bind(wx.EVT_KEY_DOWN, self._on_key)

		def _populate(self):
			self._list.DeleteAllItems()
			self._profile_names = self._manager.get_profile_names()
			for app_name in self._profile_names:
				profile = self._manager.get_profile(app_name)
				if not profile:
					continue
				idx = self._list.InsertItem(self._list.GetItemCount(), profile.displayName)
				description = getattr(profile, 'description', '') or app_name
				self._list.SetItem(idx, 1, description)
			if self._profile_names:
				self._list.Select(0)
				self._list.Focus(0)

		def _get_selected_app_name(self):
			sel = self._list.GetFirstSelected()
			if sel == -1 or sel >= len(self._profile_names):
				return None
			return self._profile_names[sel]

		def _on_activate_click(self, event):
			app_name = self._get_selected_app_name()
			if app_name:
				self._on_activate(app_name)
				self.Close()

		def _on_close(self, event):
			self.Close()

		def _on_key(self, event):
			if event.GetKeyCode() == wx.WXK_ESCAPE:
				self.Close()
			else:
				event.Skip()

except ImportError:
	pass
