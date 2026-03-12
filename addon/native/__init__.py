# Terminal Access for NVDA - Native Components
# Copyright (C) 2024 Pratik Patel
# This add-on is covered by the GNU General Public License, version 3.
# See the file LICENSE for more details.

"""
Native (Rust) acceleration layer for Terminal Access.

This package provides optional drop-in replacements for CPU-bound
Python classes.  If the native DLL is not found or fails to load,
the caller should fall back to the pure-Python implementations.

Usage::

    from addon.native.termaccess_bridge import (
        native_available,
        NativeTextDiffer,
        native_strip_ansi,
        native_search_text,
        NativePositionCache,
    )

    if native_available():
        differ = NativeTextDiffer()
    else:
        differ = TextDiffer()  # Python fallback
"""
