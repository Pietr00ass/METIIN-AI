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
    inventory_slots: int = 0
    inventory_occupied: int = 0
    inventory_full: bool = False
    hp_ratio: float | None = None
    mp_ratio: float | None = None
    arrows_empty: bool = False
    player_pos: tuple[int, int] | None = None

    def reset(self) -> None:
        """Return all flags to their default values."""
        self.mounted = False
        self.equipment_open = False
        self.minimap_open = False
        self.inventory_occupied = 0
        self.inventory_full = False
        self.hp_ratio = None
        self.mp_ratio = None
        self.arrows_empty = False
        self.player_pos = None

    # ------------------------------------------------------------------
    @property
    def inventory_free(self) -> int:
        """Number of free slots in the inventory."""

        return max(0, self.inventory_slots - self.inventory_occupied)

    def add_items(self, count: int = 1) -> None:
        """Increase occupied inventory slots by ``count``."""

        self.inventory_occupied = min(
            self.inventory_slots, self.inventory_occupied + count
        )

    def remove_items(self, count: int = 1) -> None:
        """Decrease occupied inventory slots by ``count``."""

        self.inventory_occupied = max(0, self.inventory_occupied - count)
