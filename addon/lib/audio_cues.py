# Terminal Access audio cues and braille message formatting.
# Centralizes tone definitions, braille formatting helpers,
# verbosity logic, and buffer change descriptions.

import tones

# ---------------------------------------------------------------------------
# Tone map: event_name -> list of (frequency_hz, duration_ms) tuples
# ---------------------------------------------------------------------------

_TONE_MAP = {
    "command_layer_enter": [(880, 50)],
    "command_layer_exit": [(440, 50)],
    "section_start": [(660, 30)],
    "error": [(220, 50)],
    "warning": [(440, 30)],
    "bookmark_set": [(1000, 20), (1200, 20)],
    "bookmark_jump": [(800, 30)],
    "search_match": [(550, 20)],
    "no_match": [(200, 100)],
}


def play_cue(event_name):
    """Play an audio cue for the given event.

    Looks up *event_name* in the tone map and plays each tone in sequence.
    Unknown event names are silently ignored so callers never need to
    guard against new or removed events.
    """
    tones_list = _TONE_MAP.get(event_name)
    if tones_list is None:
        return
    for freq, dur in tones_list:
        tones.beep(freq, dur)


# ---------------------------------------------------------------------------
# Braille message formatting
# ---------------------------------------------------------------------------

def format_braille_section(section_type):
    """Format a section jump braille message.

    Returns a string like ``"sec: error"`` or ``"sec: prompt"``.
    """
    return f"sec: {section_type}"


def format_braille_search(match_num, total, line_num):
    """Format a search result braille message.

    Returns a string like ``"match 3/15: line 42"``.
    """
    return f"match {match_num}/{total}: line {line_num}"


def format_braille_bookmark(name, label):
    """Format a bookmark braille message.

    When *label* is ``None`` or empty, returns ``"bmN set"``.
    Otherwise returns ``"bmN: <first 20 chars of label>"``.
    """
    if not label:
        return f"bm{name} set"
    truncated = label[:20].rstrip()
    return f"bm{name}: {truncated}"


def format_braille_profile(profile_name):
    """Format a profile change braille message.

    Returns a string like ``"prof: vim"``.
    """
    return f"prof: {profile_name}"


def format_braille_error():
    """Return the braille indicator for an error line."""
    return "ERR"


# ---------------------------------------------------------------------------
# Verbosity helpers
# ---------------------------------------------------------------------------

_VERBOSITY_LABELS = {0: "quiet", 1: "normal", 2: "verbose"}

# Speech categories allowed at each verbosity level.
# Categories not listed are suppressed at that level.
_SPEECH_CATEGORIES = {
    0: {"error", "navigation"},
    1: {"error", "navigation", "section_context", "search_count"},
    2: {"error", "navigation", "section_context", "search_count", "profile_detail"},
}


def cycle_verbosity(current):
    """Return the next verbosity level (0 -> 1 -> 2 -> 0)."""
    return (current + 1) % 3


def verbosity_label(level):
    """Return a human-readable label for a verbosity level."""
    return _VERBOSITY_LABELS.get(level, "normal")


def should_speak(verbosity_level, category):
    """Determine whether a speech category should be announced.

    Returns ``True`` if *category* is allowed at *verbosity_level*,
    ``False`` otherwise.
    """
    allowed = _SPEECH_CATEGORIES.get(verbosity_level, _SPEECH_CATEGORIES[1])
    return category in allowed


# ---------------------------------------------------------------------------
# What-changed diff description
# ---------------------------------------------------------------------------

def describe_changes(old_text, new_text):
    """Describe what changed between two buffer snapshots.

    Returns a human-readable string:
    - ``"No changes"`` when the buffers are identical or *old_text* is None.
    - The changed lines when 1 to 3 lines differ.
    - A count summary (e.g. ``"5 lines changed"``) when more than 3 lines differ.
    """
    if old_text is None or old_text == new_text:
        return "No changes"

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    # Find lines that are new or different
    changed = []
    max_len = max(len(old_lines), len(new_lines))
    for i in range(max_len):
        old_line = old_lines[i] if i < len(old_lines) else None
        new_line = new_lines[i] if i < len(new_lines) else None
        if old_line != new_line and new_line is not None:
            changed.append(new_line)

    if not changed:
        return "No changes"

    count = len(changed)
    if count <= 3:
        lines_text = "; ".join(changed)
        return f"{count} line changed: {lines_text}" if count == 1 else f"{count} lines changed: {lines_text}"

    return f"{count} lines changed"
