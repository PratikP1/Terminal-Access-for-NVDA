# Terminal Access addon library modules.

# Ensure the translation function is available for extracted modules.
# In NVDA, addonHandler.initTranslation() sets builtins._; in tests,
# conftest.py sets it. This fallback catches the edge case where
# neither has run yet.
try:
	_("")
except (NameError, TypeError):
	import builtins
	builtins._ = lambda text: text
