# Unchanged NVDA release-2026.2 source segments. GPL-2.0-or-later.
# Sources: source/baseObject.py and source/editableText.py.
# Copyright (C) 2007-2022 NV Access Limited, Christopher Toth, Babbage B.V., Julien Cochuyt
# Copyright (C) 2006-2025 NV Access Limited, Davy Kager, Julien Cochuyt, Rob Meredith, Leonard de Ruijter
# https://github.com/nvaccess/nvda/tree/release-2026.2/source
# Only their platform/service boundary globals are supplied by tests.


class ScriptableType(AutoPropertyType):
	"""A metaclass used for collecting and caching gestures on a ScriptableObject"""
	def __new__(cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], /, **kwargs: Any):
		newCls = super().__new__(cls, name, bases, namespace, **kwargs)
		gesturesDictName = "_%s__gestures" % newCls.__name__
		# #8463: To avoid name mangling conflicts, create a copy of the __gestures dictionary.
		try:
			gestures = getattr(newCls, gesturesDictName).copy()
		except AttributeError:
			# This class currently has no gestures dictionary,
			# because no custom __gestures dictionary has been defined.
			gestures = {}
		for name, script in namespace.items():
			if not name.startswith("script_"):
				continue
			scriptName = name[len("script_") :]
			if hasattr(script, "gestures"):
				for gesture in script.gestures:
					gestures[gesture] = scriptName
		if gestures:
			setattr(newCls, gesturesDictName, gestures)
		return newCls

class ScriptableObject(AutoPropertyObject, metaclass=ScriptableType):
	"""A class that implements NVDA's scripting interface.
	Input gestures are bound to scripts such that the script will be executed when the appropriate input gesture is received.
	Scripts are methods named with a prefix of C{script_}; e.g. C{script_foo}.
	They accept an L{inputCore.InputGesture} as their single argument.
	Gesture bindings can be specified on the class by creating a C{__gestures} dict which maps gesture identifiers to script names.
	They can also be bound on an instance using the L{bindGesture} method.
	@cvar scriptCategory: If present, a translatable string displayed to the user
		as the category for scripts in this class;
		e.g. in the Input Gestures dialog.
		This can be overridden for individual scripts
		by setting a C{category} attribute on the script method.
	@type scriptCategory: str
	"""
	def __init__(self):
		#: Maps input gestures to script functions.
		#: @type: dict
		self._gestureMap = {}
		# Bind gestures specified on the class.
		# This includes gestures specified on decorated scripts.
		# This does not include the gestures that are added when creating a DynamicNVDAObjectType.
		for cls in reversed(self.__class__.__mro__):
			try:
				self.bindGestures(getattr(cls, "_%s__gestures" % cls.__name__))
			except AttributeError:
				pass
			try:
				self.bindGestures(cls._scriptDecoratorGestures)
			except AttributeError:
				pass
		super(ScriptableObject, self).__init__()
	def bindGesture(self, gestureIdentifier, scriptName):
		"""Bind an input gesture to a script.
		@param gestureIdentifier: The identifier of the input gesture.
		@type gestureIdentifier: str
		@param scriptName: The name of the script, which is the name of the method excluding the C{script_} prefix.
		@type scriptName: str
		@raise LookupError: If there is no script with the provided name.
		"""
		scriptAttrName = "script_%s" % scriptName
		# Don't store the instance method, as this causes a circular reference
		# and instance methods are meant to be generated on retrieval anyway.
		func = getattr(self.__class__, scriptAttrName, None)
		if not func:
			raise LookupError(
				"No such script on class {className}. Couldn't find attribute: {scriptAttrName}".format(
					className=self.__class__.__name__,
					scriptAttrName=scriptAttrName,
				),
			)
		# Import late to avoid circular import.
		import inputCore
		self._gestureMap[inputCore.normalizeGestureIdentifier(gestureIdentifier)] = func

	def removeGestureBinding(self, gestureIdentifier):
		"""
		Removes the binding for the given gesture identifier if a binding exists.
		@param gestureIdentifier: The identifier of the input gesture.
		@type gestureIdentifier: str
		@raise LookupError: If there is no binding for this gesture
		"""
		# Import late to avoid circular import.
		import inputCore
		del self._gestureMap[inputCore.normalizeGestureIdentifier(gestureIdentifier)]

	def clearGestureBindings(self):
		"""Remove all input gesture bindings from this object."""
		self._gestureMap.clear()
	def bindGestures(self, gestureMap):
		"""Bind or unbind multiple input gestures.
		This is a convenience method which simply calls L{bindGesture} for each gesture and script pair, logging any errors.
		For the case where script is None, L{removeGestureBinding} is called instead.
		@param gestureMap: A mapping of gesture identifiers to script names.
		@type gestureMap: dict of str to str
		"""
		for gestureIdentifier, scriptName in gestureMap.items():
			if scriptName:
				try:
					self.bindGesture(gestureIdentifier, scriptName)
				except LookupError:
					log.error("Error binding script %s in %r" % (scriptName, self))
			else:
				try:
					self.removeGestureBinding(gestureIdentifier)
				except LookupError:
					pass
	def getScript(self, gesture):
		"""Retrieve the script bound to a given gesture.
		@param gesture: The input gesture in question.
		@type gesture: L{inputCore.InputGesture}
		@return: The script function or C{None} if none was found.
		@rtype: script function
		"""
		for identifier in gesture.normalizedIdentifiers:
			try:
				# Convert to instance method.
				return self._gestureMap[identifier].__get__(self, self.__class__)
			except KeyError:
				continue
			except AttributeError:
				log.exception(
					f"Base class may not have been initialized.\nMRO={self.__class__.__mro__}"
					if not hasattr(self, "_gestureMap")
					else None,
				)
				return None
		else:
			return None
	#: A value for sleepMode which indicates that NVDA should fully sleep for this object;
	#: i.e. braille and speech via NVDA controller client is disabled and the user cannot disable sleep mode.
	SLEEP_FULL = "full"

class EditableText:

	def _caretScriptPostMovedHelper(self, speakUnit, gesture, info=None):
		if isScriptWaiting():
			return
		if not info:
			try:
				info = self.makeTextInfo(textInfos.POSITION_CARET)
			except:  # noqa: E722
				return
		# Forget the word currently being typed as the user has moved the caret somewhere else.
		speech.clearTypedWordBuffer()
		review.handleCaretMove(info)
		if speakUnit and not willSayAllResume(gesture):
			info.expand(speakUnit)
			speech.speakTextInfo(info, unit=speakUnit, reason=controlTypes.OutputReason.CARET)
		braille.handler.handleCaretMove(self)

	def _backspaceScriptHelper(self, unit, gesture):
		try:
			oldInfo = self.makeTextInfo(textInfos.POSITION_CARET)
		except:  # noqa: E722
			gesture.send()
			return
		oldBookmark = oldInfo.bookmark
		testInfo = oldInfo.copy()
		try:
			res = testInfo.move(textInfos.UNIT_CHARACTER, -1)
		except COMError:
			log.exception("Error in testInfo.move")
			gesture.send()
			return
		if res < 0:
			testInfo.expand(unit)
			delChunk = testInfo.text
		else:
			delChunk = ""
		gesture.send()
		caretMoved, newInfo = self._hasCaretMoved(oldBookmark)
		if not caretMoved:
			return
		delChunk = delChunk.replace("\r\n", "\n")  # Occurs with at least with Scintilla
		if len(delChunk) > 1:
			speech.speakMessage(delChunk)
		else:
			speech.speakSpelling(delChunk)
		self._caretScriptPostMovedHelper(None, gesture, newInfo)

	def script_caret_backspaceCharacter(self, gesture):
		self._backspaceScriptHelper(textInfos.UNIT_CHARACTER, gesture)

	def _caretMovementScriptHelper(self, gesture, unit):
		try:
			info = self.makeTextInfo(textInfos.POSITION_CARET)
		except:  # noqa: E722
			gesture.send()
			return
		bookmark = info.bookmark
		gesture.send()
		caretMoved, newInfo = self._hasCaretMoved(bookmark)
		if not caretMoved and self.shouldFireCaretMovementFailedEvents:
			eventHandler.executeEvent("caretMovementFailed", self, gesture=gesture)
		self._caretScriptPostMovedHelper(unit, gesture, newInfo)
