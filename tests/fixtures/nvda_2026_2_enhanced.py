# Frozen unchanged NVDA release-2026.2 terminal input contract for tests.
# Source: nvaccess/nvda, source/NVDAObjects/behaviors.py.
# Copyright NV Access Limited and contributors. GPL-2.0-or-later.
# Copyright (C) 2006-2025 NV Access Limited, Peter Vágner, Joseph Lee, Bill Dengler,
# Burman's Computer and Education Ltd, Cary-rowen, Cyrille Bougot
# https://github.com/nvaccess/nvda/blob/release-2026.2/source/NVDAObjects/behaviors.py
# Loaded with controlled Terminal/config/speech/script/TypingEcho boundaries.

class EnhancedTermTypedCharSupport(Terminal):
	"""A Terminal object with keyboard support enhancements for console applications.
	Notably, it suppresses duplicate typed character announcements and can
	hold typed characters in a queue and only dispatch once the screen updates.
	This is useful for suppression of passwords, etc."""

	#: Whether this object quickly and reliably sends textChange events
	#: when its contents update.
	#: Timely and reliable textChange events are required
	#: to support password suppression.
	_supportsTextChange = True
	#: A queue of typed characters, to be dispatched on C{textChange}.
	#: This queue allows NVDA to suppress typed passwords when needed.
	_queuedChars = []
	#: Whether the last typed character is a tab.
	#: If so, we should temporarily disable filtering as completions may
	#: be short.
	_hasTab = False

	def _reportNewLines(self, lines):
		# Perform typed character filtering, as typed characters are handled with events.
		if (
			len(lines) == 1
			and not self._hasTab
			and len(lines[0].strip()) < max(len(speech.speech._curWordChars) + 1, 3)
		):
			return
		# Clear the typed word buffer for new text lines.
		speech.clearTypedWordBuffer()
		self._queuedChars = []
		super()._reportNewLines(lines)

	def event_typedCharacter(self, ch):
		if ch == "\t":
			self._hasTab = True
			# Clear the typed word buffer for tab completion.
			speech.clearTypedWordBuffer()
		else:
			self._hasTab = False
		if (
			(
				config.conf["keyboard"]["speakTypedCharacters"] != TypingEcho.OFF.value
				or config.conf["keyboard"]["speakTypedWords"] != TypingEcho.OFF.value
			)
			and not config.conf["terminals"]["speakPasswords"]
			and self._supportsTextChange
		):
			self._queuedChars.append(ch)
		else:
			super().event_typedCharacter(ch)

	def event_textChange(self):
		self._dispatchQueue()
		super().event_textChange()

	@script(
		gestures=[
			"kb:enter",
			"kb:numpadEnter",
			"kb:tab",
			"kb:control+c",
			"kb:control+d",
			"kb:control+pause",
		],
	)
	def script_flush_queuedChars(self, gesture):
		"""
		Flushes the typed word buffer and queue of typedCharacter events if present.
		Since these gestures clear the current word/line, we should flush the
		queue to avoid erroneously reporting these chars.
		"""
		self._queuedChars = []
		speech.clearTypedWordBuffer()
		gesture.send()

	def _dispatchQueue(self):
		"""Sends queued typedCharacter events through to NVDA."""
		while self._queuedChars:
			ch = self._queuedChars.pop(0)
			super().event_typedCharacter(ch)
