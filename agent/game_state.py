from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GameState:
    """Simple container for transient game state flags.

    Tracks whether the player is mounted, equipment panel is open and whether
    the minimap is visible.  Values are reset to the defaults via
    :meth:`reset`.
    """

    mounted: bool = False
    equipment_open: bool = False
    minimap_open: bool = False

    def reset(self) -> None:
        """Return all flags to their default values."""
        self.mounted = False
        self.equipment_open = False
        self.minimap_open = False
