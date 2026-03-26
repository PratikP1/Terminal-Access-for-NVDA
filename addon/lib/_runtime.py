"""Runtime dependency registry for Terminal Access.

Holds references to native acceleration functions and helpers that
lib modules need but cannot import directly (to avoid circular imports).
Populated by terminalAccess.py during module initialization.
"""

import re

from lib.caching import TextDiffer


def gesture_label(gesture: str, script_name: str) -> str:
	"""Format a gesture and script name into a human-readable label.

	Example: 'kb:NVDA+shift+c' + 'copyRectangularSelection'
	returns 'NVDA+Shift+C \u2014 Copy Rectangular Selection'
	"""
	key = gesture.replace("kb:", "")
	parts = key.split("+")
	formatted = []
	for p in parts:
		if p.upper() == "NVDA":
			formatted.append("NVDA")
		elif len(p) > 1:
			formatted.append(p.capitalize())
		else:
			formatted.append(p.upper())
	key_display = "+".join(formatted)
	label = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', script_name)
	return f"{key_display} \u2014 {label.title()}"

# Text processing
strip_ansi = lambda text: text
make_text_differ = TextDiffer

# Native acceleration
native_available = False
native_search_text = None

# Helper process
get_helper = lambda: None

# Terminal text reading
read_terminal_text = None

# Position caching
make_position_cache = None

# API modules (populated by terminalAccess.py, defaults used in tests)
api_module = None  # set to NVDA's api module at startup
webbrowser_module = None  # set to Python's webbrowser at startup
