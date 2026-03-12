# Terminal Access for NVDA - Native Components
# Copyright (C) 2024 Pratik Patel
# This add-on is covered by the GNU General Public License, version 3.
# See the file LICENSE for more details.

"""
Native (Rust) acceleration layer for Terminal Access.

Phase 1 — DLL-based drop-in replacements for CPU-bound algorithms::

    from native.termaccess_bridge import (
        native_available,
        NativeTextDiffer,
        native_strip_ansi,
        native_search_text,
        NativePositionCache,
    )

Phase 2 — Helper process for off-main-thread UIA reads::

    from native.termaccess_bridge import (
        helper_available,
        get_helper,
        stop_helper,
    )

    helper = get_helper()
    if helper:
        text = helper.read_text(hwnd)

If the DLL or helper cannot be loaded, callers should fall back to
the pure-Python implementations.
"""
