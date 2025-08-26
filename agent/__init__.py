"""Agent configuration helpers.

This module provides a small wrapper around the YAML configuration file used by
the project.  It parses the teleport locations and channel list during
initialisation and exposes helper methods allowing the user to modify these
lists and save the configuration back to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any

import yaml


@dataclass
class TeleportSlot:
    """Single teleport location defined by page and slot number."""

    page: str
    slot: int


@dataclass
class AgentConfig:
    """Wrapper around the agent configuration dictionary.

    Attributes
    ----------
    data:
        Raw configuration dictionary used by the rest of the codebase.
    teleport_slots:
        List of :class:`TeleportSlot` objects parsed from ``teleport.slots``.
    channels:
        List of channel numbers available to the agent.
    """

    data: Dict[str, Any]
    teleport_slots: List[TeleportSlot] = field(default_factory=list)
    channels: List[int] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Loading / saving
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: str = "config/agent.yaml") -> "AgentConfig":
        """Load configuration from ``path`` and parse custom fields."""

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        slots = [TeleportSlot(**s) for s in raw.get("teleport", {}).get("slots", [])]
        channels = list(raw.get("channels", []))
        return cls(raw, slots, channels)

    def save(self, path: str = "config/agent.yaml") -> None:
        """Serialise configuration back to YAML file."""

        self.data.setdefault("teleport", {})["slots"] = [s.__dict__ for s in self.teleport_slots]
        self.data["channels"] = list(self.channels)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.data, f, allow_unicode=True)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------
    def add_channel(self, ch: int) -> None:
        """Add a channel number if it is not already present."""

        if ch not in self.channels:
            self.channels.append(ch)

    def remove_channel(self, ch: int) -> None:
        """Remove channel number if present."""

        if ch in self.channels:
            self.channels.remove(ch)

    def add_slot(self, page: str, slot: int) -> None:
        """Append a new teleport slot definition."""

        self.teleport_slots.append(TeleportSlot(page, slot))

    def remove_slot(self, page: str, slot: int) -> None:
        """Remove a teleport slot matching ``page`` and ``slot``."""

        self.teleport_slots = [s for s in self.teleport_slots if not (s.page == page and s.slot == slot)]
