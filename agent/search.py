from __future__ import annotations

import logging
import time

from .channel import ChannelSwitcher
from .teleport import Teleporter

logger = logging.getLogger(__name__)


class SearchManager:
    """Handle teleportation and channel switching when no target is detected."""

    def __init__(
        self,
        teleporter: Teleporter,
        channel_switcher: ChannelSwitcher,
        tp_slots: list[int],
        tp_page: str | None,
        channels: list[int],
        no_target_sec: float,
        channel_every: int,
    ):
        self.teleporter = teleporter
        self.channel_switcher = channel_switcher
        self.tp_slots = tp_slots
        self.tp_page = tp_page
        self.channels = channels
        self.no_target_sec = no_target_sec
        self.channel_every = channel_every
        self.last_target_time = time.time()
        self.location_idx = 0
        self.channel_idx = 0
        self._teleports = 0

    def update_last_target(self) -> None:
        self.last_target_time = time.time()

    def handle_no_target(self, spin_done: bool) -> None:
        """Teleport and optionally change channel when no target for a while.

        Parameters
        ----------
        spin_done: bool
            Whether a full rotation search was completed. If ``False`` the
            method returns immediately without performing any action.
        """
        if not spin_done:
            return
        now = time.time()
        if now - self.last_target_time <= self.no_target_sec:
            return
        slot = None
        try:
            if self.tp_slots:
                slot = self.tp_slots[self.location_idx % len(self.tp_slots)]
                self.teleporter.teleport_slot(slot, self.tp_page)
                self._teleports += 1
                self.location_idx = (self.location_idx + 1) % len(self.tp_slots)
                if self._teleports % self.channel_every == 0 or self.location_idx == 0:
                    if self.channels:
                        ch = self.channels[self.channel_idx % len(self.channels)]
                        try:
                            self.channel_switcher.switch(ch)
                        except Exception:
                            logger.warning("Nie udało si zmienić kanału na %s", ch)
                        self.channel_idx = (self.channel_idx + 1) % len(self.channels)
            else:
                logger.debug("Lista slotów teleportu jest pusta")
        except Exception:
            logger.warning("Teleportacja na slot %s nie powiodła się", slot)
        self.last_target_time = now
