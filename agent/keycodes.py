"""Centralised keyboard scan code definitions and helpers.

This module exposes the mapping between human readable key names and the
corresponding Windows scan codes used by the project.  Keeping the mapping in
a dedicated module allows other parts of the codebase (for example the
``agent`` runtime and the ``recorder`` utilities) to share a single source of
truth for key identifiers.
"""

from __future__ import annotations

# Mapping from a human‑friendly key name to its Windows scan code.  Only the
# keys required by the project are included here.
SCANCODES = {
    "w": 0x11,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "space": 0x39,
    "shift": 0x2A,
    "ctrl": 0x1D,
    "alt": 0x38,
    "x": 0x2D,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
}

# Keys that require the extended flag when sent via ``SendInput``.  These keys
# are not currently associated with scan codes in ``SCANCODES`` but are part of
# the normalised key set understood by the project.
EXTENDED_KEYS = {"up", "down", "left", "right"}

# Backwards compatibility: expose ``VK_CODES`` under the same name that was
# previously defined in :mod:`agent.wasd`.
VK_CODES = SCANCODES


# ---------------------------------------------------------------------------
# ``pynput`` helpers
# ---------------------------------------------------------------------------

# Mapping of ``str(pynput.keyboard.Key)`` representations to the canonical key
# names used above.  Character keys are handled separately.
_PYNPUT_NAME_MAP = {
    "Key.space": "space",
    "Key.shift": "shift",
    "Key.shift_r": "shift",
    "Key.ctrl": "ctrl",
    "Key.ctrl_r": "ctrl",
    "Key.alt": "alt",
    "Key.alt_r": "alt",
    "Key.up": "up",
    "Key.down": "down",
    "Key.left": "left",
    "Key.right": "right",
}


def pynput_key_name(key) -> str | None:
    """Return a canonical key name for a ``pynput`` key object.

    If the key is a character it is returned in lower case.  For special keys
    the mapping above is used.  ``None`` is returned for keys that are not
    recognised by the project.
    """

    try:
        if hasattr(key, "char") and key.char is not None:
            return key.char.lower()
        return _PYNPUT_NAME_MAP.get(str(key))
    except Exception:
        return None

