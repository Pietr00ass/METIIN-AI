from __future__ import annotations

"""High level game controller coordinating window focus and input.

The :class:`GameController` centralises all interaction with the Metin2
window. It owns a :class:`~agent.wasd.KeyHold` instance for keyboard events and
provides a safe :meth:`click` method that focuses the window before emitting
mouse actions. Strategies can register callbacks for disconnection or death
via :meth:`add_on_disconnect` and :meth:`add_on_death`.

Fail‑safe recovery helpers such as :meth:`teleport`, :meth:`login`,
``reset_camera`` and :meth:`relog` are exposed for strategies to reuse.
``relog`` releases all keys, invokes the registered callbacks, performs a
minimal login and teleports to the first configured slot while restoring the
camera orientation.
"""

from typing import Callable, List, TYPE_CHECKING
from pathlib import Path

import time
import pyautogui

from recorder.window_capture import WindowCapture

from . import AgentConfig, get_config, reload_config as _reload_cfg
from utils.humanizer import random_pause
from .game_state import GameState
from .hud_ocr import HudOcr
from .wasd import KeyHold
from utils.logging_config import logger

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from .teleport import Teleporter, TeleportResult
    from .strategy import AgentStrategy
else:  # pragma: no cover - runtime import inside property
    Teleporter = None  # type: ignore
    TeleportResult = None  # type: ignore


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
        self.keys = KeyHold(
            dry=self.dry, active_fn=getattr(self.win, "is_foreground", None)
        )
        self._teleporter: Teleporter | None = None
        self._on_disconnect: List[Callable[[], None]] = []
        self._on_death: List[Callable[[], None]] = []
        self._camera_pos: tuple[int, int] | None = None
        self._cam_yaw = 0.0
        self._cam_pitch = 0.0
        self.state = GameState()
        self._hud_ocr = HudOcr(cfg.ocr)
        self._strategies: List["AgentStrategy"] = []
        if not self.dry:
            try:
                self._camera_pos = pyautogui.position()
            except Exception:  # pragma: no cover - best effort
                self._camera_pos = None

    # ------------------------------------------------------------------
    # configuration helpers
    # ------------------------------------------------------------------
    def add_strategy(self, strategy: "AgentStrategy") -> None:
        """Register an active strategy for configuration updates."""

        self._strategies.append(strategy)

    def reload_config(self, path: str | Path = "config/agent.yaml") -> AgentConfig:
        """Reload configuration and update registered strategies."""

        cfg = _reload_cfg(path)
        self.cfg = cfg
        self.dry = cfg.dry_run
        self.keys.dry = self.dry
        pyautogui.PAUSE = cfg.controls.mouse_pause
        self._teleporter = None
        self._hud_ocr.update_config(cfg.ocr)
        for strat in list(self._strategies):
            try:
                strat.setup(cfg, getattr(strat, "win", self.win))
            except Exception:  # pragma: no cover - defensive
                logger.opt(exception=True).warning("strategy reload failed")
        return cfg

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
        random_pause(0)

    def login(self) -> None:
        """Attempt to log into the game after a disconnect.

        The implementation assumes the credentials are persisted by the game and
        that pressing ``Enter`` on the login screen is sufficient.  It performs
        best effort window focusing before sending the key press.
        """
        if self.dry:
            return
        self.focus()
        if not self.is_foreground():
            self.focus()
            if not self.is_foreground():
                logger.warning("login failed: inactive window")
                return
        pyautogui.press("enter")

    def remember_camera(self) -> None:
        """Record current mouse position as the reference camera angle."""
        if self.dry:
            return
        try:
            self._camera_pos = pyautogui.position()
        except Exception:  # pragma: no cover - best effort
            self._camera_pos = None

    def reset_camera(self) -> None:
        """Return the camera to the last recorded position if possible."""
        if self.dry or self._camera_pos is None:
            return
        self.focus()
        if not self.is_foreground():
            self.focus()
            if not self.is_foreground():
                logger.warning("reset_camera failed: inactive window")
                return
        pyautogui.moveTo(*self._camera_pos, duration=self.cfg.teleport.click_duration)

    def move_camera_left(self, press_time: float) -> None:
        """Rotate camera left for ``press_time`` seconds."""
        self._cam_yaw -= press_time
        if self.dry:
            return
        self.focus()
        pyautogui.keyDown("left")
        time.sleep(press_time)
        pyautogui.keyUp("left")

    def move_camera_right(self, press_time: float) -> None:
        """Rotate camera right for ``press_time`` seconds."""
        self._cam_yaw += press_time
        if self.dry:
            return
        self.focus()
        pyautogui.keyDown("right")
        time.sleep(press_time)
        pyautogui.keyUp("right")

    def move_camera_up(self, press_time: float) -> None:
        """Tilt camera up for ``press_time`` seconds."""
        self._cam_pitch += press_time
        if self.dry:
            return
        self.focus()
        pyautogui.keyDown("up")
        time.sleep(press_time)
        pyautogui.keyUp("up")

    def move_camera_down(self, press_time: float) -> None:
        """Tilt camera down for ``press_time`` seconds."""
        self._cam_pitch -= press_time
        if self.dry:
            return
        self.focus()
        pyautogui.keyDown("down")
        time.sleep(press_time)
        pyautogui.keyUp("down")

    def calibrate_camera(self) -> None:
        """Return camera to the last neutral orientation."""
        if self.dry:
            self._cam_yaw = 0.0
            self._cam_pitch = 0.0
            return
        self.focus()
        if self._cam_yaw > 0:
            pyautogui.keyDown("left")
            time.sleep(self._cam_yaw)
            pyautogui.keyUp("left")
        elif self._cam_yaw < 0:
            pyautogui.keyDown("right")
            time.sleep(-self._cam_yaw)
            pyautogui.keyUp("right")
        if self._cam_pitch > 0:
            pyautogui.keyDown("down")
            time.sleep(self._cam_pitch)
            pyautogui.keyUp("down")
        elif self._cam_pitch < 0:
            pyautogui.keyDown("up")
            time.sleep(-self._cam_pitch)
            pyautogui.keyUp("up")
        self._cam_yaw = 0.0
        self._cam_pitch = 0.0

    # ------------------------------------------------------------------
    # state helpers
    # ------------------------------------------------------------------
    def reset_state(self) -> None:
        """Restore :class:`GameState` to its default values."""
        self.state.reset()

    def update_hud_state(self, frame) -> None:
        """Refresh HUD OCR state from ``frame``."""
        if self._hud_ocr:
            self._hud_ocr.update_state(frame, self.state)

    def apply_hud_potions(self) -> None:
        """Use potions based on HUD OCR state."""
        pot_cfg = getattr(self.cfg, "potions", None)
        if pot_cfg is None:
            return
        if self.state.hp_ratio is not None and pot_cfg.hp_key:
            if self.state.hp_ratio < pot_cfg.hp_threshold:
                self.keys.tap(pot_cfg.hp_key)
        if self.state.mp_ratio is not None and pot_cfg.mp_key:
            if self.state.mp_ratio < pot_cfg.mp_threshold:
                self.keys.tap(pot_cfg.mp_key)

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
                logger.opt(exception=True).warning("disconnect handler failed")
        self.login()
        if self.cfg.teleport.slots:
            self.teleport(self.cfg.teleport.slots[0].slot)
        for cb in list(self._on_death):
            try:
                cb()
            except Exception:  # pragma: no cover - best effort
                logger.opt(exception=True).warning("death handler failed")

    # simple recovery helpers -------------------------------------------------
    def restart_game(self) -> None:
        """Best effort recovery when the client is logged out.

        The implementation delegates to :meth:`relog`, which releases all
        pressed keys, performs the minimal login sequence and teleports to the
        first configured slot.  The routine is intentionally lightweight and
        suitable for unit tests where the real game client is not available.
        """

        logger.info("restart_game invoked")
        try:
            self.relog()
        except Exception:  # pragma: no cover - defensive
            logger.opt(exception=True).warning("relog failed during restart")

    def ensure_logged_in(self) -> None:
        """Attempt to ensure the account is logged in after a loading screen."""

        logger.debug("ensure_logged_in invoked")
        try:
            self.login()
        except Exception:  # pragma: no cover - defensive
            logger.opt(exception=True).warning("login failed in ensure_logged_in")

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


def create_controller(
    win: WindowCapture, cfg: AgentConfig | dict | None = None
) -> GameController:
    """Create and store a global :class:`GameController` instance."""
    global controller
    controller = GameController(win, cfg)
    return controller


__all__ = ["GameController", "controller", "create_controller"]
