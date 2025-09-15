from __future__ import annotations

"""High level game controller coordinating window focus and input.

The :class:`GameController` centralises all interaction with the Metin2
window. It owns a :class:`~agent.wasd.KeyHold` instance for keyboard events and
provides a safe :meth:`click` method that focuses the window before emitting
mouse actions. Strategies can register callbacks for disconnection or death
via :meth:`add_on_disconnect` and :meth:`add_on_death`.

Fail‑safe recovery helpers such as :meth:`teleport` and :meth:`relog` are
exposed for strategies to reuse. ``relog`` releases all keys, invokes the
registered callbacks and teleports to the first configured slot.
"""

from typing import Callable, List, TYPE_CHECKING
import logging

import pyautogui

from recorder.window_capture import WindowCapture

from . import AgentConfig, get_config
from .wasd import KeyHold

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from .teleport import Teleporter, TeleportResult
else:  # pragma: no cover - runtime import inside property
    Teleporter = None  # type: ignore
    TeleportResult = None  # type: ignore

logger = logging.getLogger(__name__)


class GameController:
    """Coordinate window focus, keyboard/mouse input and fail‑safe resets."""

    def __init__(
        self,
        win: WindowCapture,
        cfg: AgentConfig | dict | None = None,
    ) -> None:
        if cfg is None:
            cfg = get_config()
        elif isinstance(cfg, dict):
            cfg = AgentConfig(**cfg)
        self.cfg = cfg
        self.win = win
        self.dry = cfg.dry_run
        pyautogui.PAUSE = cfg.controls.mouse_pause
        self.keys = KeyHold(dry=self.dry, active_fn=getattr(self.win, "is_foreground", None))
        self._teleporter: Teleporter | None = None
        self._on_disconnect: List[Callable[[], None]] = []
        self._on_death: List[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # basic window helpers
    # ------------------------------------------------------------------
    def focus(self) -> None:
        """Bring the game window to the foreground."""
        self.win.focus()

    def is_foreground(self) -> bool:
        """Return ``True`` when the game window is in the foreground."""
        fn = getattr(self.win, "is_foreground", None)
        return bool(fn()) if fn else True

    # ------------------------------------------------------------------
    # low level input helpers
    # ------------------------------------------------------------------
    def click(self, x: int, y: int, duration: float | None = None) -> None:
        """Focus the window and click at ``(x, y)`` if not ``dry``."""
        if self.dry:
            return
        self.focus()
        if not self.is_foreground():
            return
        pyautogui.moveTo(x, y, duration=duration or self.cfg.teleport.click_duration)
        pyautogui.click()

    # ------------------------------------------------------------------
    # fail‑safe helpers
    # ------------------------------------------------------------------
    @property
    def teleporter(self) -> "Teleporter":
        from .teleport import Teleporter  # local import to avoid cycle
        if self._teleporter is None:
            self._teleporter = Teleporter(self.win, cfg=self.cfg, controller=self)
        return self._teleporter

    def teleport(self, slot: int) -> "TeleportResult":
        """Teleport using the configured :class:`Teleporter`."""
        return self.teleporter.teleport_slot(slot)

    def relog(self) -> None:
        """Reset after a disconnect by teleporting to the first slot."""
        self.keys.release_all()
        for cb in list(self._on_disconnect):
            try:
                cb()
            except Exception:  # pragma: no cover - best effort
                logger.warning("disconnect handler failed", exc_info=True)
        if self.cfg.teleport.slots:
            self.teleport(self.cfg.teleport.slots[0].slot)
        for cb in list(self._on_death):
            try:
                cb()
            except Exception:  # pragma: no cover - best effort
                logger.warning("death handler failed", exc_info=True)

    # ------------------------------------------------------------------
    # event hook registration
    # ------------------------------------------------------------------
    def add_on_disconnect(self, callback: Callable[[], None]) -> None:
        """Register ``callback`` for disconnect events."""
        self._on_disconnect.append(callback)

    def add_on_death(self, callback: Callable[[], None]) -> None:
        """Register ``callback`` for death events."""
        self._on_death.append(callback)


controller: GameController | None = None


def create_controller(win: WindowCapture, cfg: AgentConfig | dict | None = None) -> GameController:
    """Create and store a global :class:`GameController` instance."""
    global controller
    controller = GameController(win, cfg)
    return controller


__all__ = ["GameController", "controller", "create_controller"]
