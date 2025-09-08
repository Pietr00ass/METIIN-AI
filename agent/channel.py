from __future__ import annotations

from pathlib import Path
import asyncio
import time
from typing import Callable, Optional, Tuple

import numpy as np

from recorder.window_capture import WindowCapture

from .template_matcher import TemplateMatch, TemplateMatcher
from .wasd import KeyHold, pydirectinput


class ChannelSwitcher:
    """Utility for switching channels in the in‑game minimap.

    Template images ``ch1.png`` … ``ch8.png`` stored within ``templates_dir`` are
    used by helper methods to locate and identify minimap buttons.  Actual
    channel switching is performed via configurable keyboard hotkeys emitted
    through :mod:`pydirectinput`.  A ``dry`` mode can be enabled to skip real
    keyboard events for testing purposes.
    """

    def __init__(
        self,
        win: WindowCapture,
        templates_dir: str | Path,
        dry: bool = False,
        *,
        keys: KeyHold | None = None,
        hotkeys: dict[int, str] | None = None,
    ):
        self.win = win
        templates_path = Path(templates_dir)
        if not templates_path.is_dir():
            raise FileNotFoundError(
                f"Brak katalogu z szablonami: {templates_path}"
            )
        required = [f"ch{i}.png" for i in range(1, 9)]
        missing = [p for p in required if not (templates_path / p).is_file()]
        if missing:
            raise FileNotFoundError(
                f"Brak plików w {templates_path}: {', '.join(missing)}"
            )
        self.tm = TemplateMatcher(templates_path)
        self.dry = dry

        # ``KeyHold`` relies on ``pydirectinput`` for reliable keyboard events.
        # When it is not available we refuse to construct a switcher in order
        # to avoid sending incomplete input sequences which could leave the
        # game in an inconsistent state.
        if keys is None:
            if pydirectinput is None and not dry:
                raise RuntimeError(
                    "pydirectinput is required to switch channels; install the "
                    "dependency or use dry mode"
                )
            keys = KeyHold(dry=dry, active_fn=getattr(win, "is_foreground", None))

        self.keys = keys
        # Default to numeric keypad hotkeys (``numpad1`` … ``numpad8``)
        self.hotkeys = hotkeys or {i: f"numpad{i}" for i in range(1, 9)}

    def _ensure_active_window(self) -> bool:
        """Ensure the game window is focused and in the foreground.

        Returns ``True`` if the window appears to be active, ``False``
        otherwise.  When possible the window is focused twice with a small
        delay to give the system time to bring it to the front.
        """

        if hasattr(self.win, "focus"):
            self.win.focus()
        if hasattr(self.win, "is_foreground") and not self.win.is_foreground():
            time.sleep(0.1)
            if hasattr(self.win, "focus"):
                self.win.focus()
            if hasattr(self.win, "is_foreground") and not self.win.is_foreground():
                return False
        return True

    # ------------------------------------------------------------------
    # Frame helpers
    def _frame(self) -> np.ndarray:
        """Return the current game frame as an RGB numpy array."""

        fr = self.win.grab()
        return np.array(fr)[:, :, :3].copy()

    def _minimap_roi(self) -> Tuple[int, int, int, int]:
        """Region of interest containing the minimap in the top‑right corner."""

        _, _, w, h = self.win.region
        return max(0, w - 260), 20, 240, 240

    # ------------------------------------------------------------------
    # Low level helpers
    def find_button(
        self,
        frame: np.ndarray,
        ch: int,
        thresh: float = 0.82,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> TemplateMatch | None:
        """Find channel button ``ch`` within ``frame``.

        Returns
        -------
        TemplateMatch | None
            ``TemplateMatch`` containing ``rect``, ``center`` and ``score`` when
            the button is found; ``None`` otherwise.
        """

        if roi is None:
            roi = self._minimap_roi()
        name = f"ch{ch}"
        res = self.tm.find(frame, name, thresh=thresh, roi=roi, multi_scale=True)
        return res

    def color_at(
        self, x: int, y: int, frame: Optional[np.ndarray] = None
    ) -> Tuple[int, int, int]:
        """Return RGB colour at coordinates relative to the minimap ROI."""

        if frame is None:
            frame = self._frame()
        rx, ry, _, _ = self._minimap_roi()
        px = rx + int(x)
        py = ry + int(y)
        r, g, b = frame[py, px]
        return int(r), int(g), int(b)

    @staticmethod
    def is_gold(color: Tuple[int, int, int]) -> bool:
        """Heuristic check whether ``color`` resembles the gold selection colour."""

        r, g, b = color
        return r > 200 and g > 170 and b < 80

    # ------------------------------------------------------------------
    # Channel operations
    def switch(
        self,
        ch: int,
        post_wait: float = 5.0,
    ) -> bool:
        """Switch to channel ``ch`` using the configured hotkey.

        The implementation relies solely on :mod:`pydirectinput` via
        :class:`KeyHold`. ``post_wait`` seconds are waited after the keypress
        to give the game time to perform the switch.
        """

        if not (1 <= ch <= 8):
            raise ValueError("Kanał poza zakresem 1..8")
        if not self.keys:
            return False

        key = self.hotkeys.get(ch)
        if not key:
            return False

        self.win.focus()

        if not self._ensure_active_window():
            return False

        # Hold the channel hotkey briefly to ensure it registers
        self.keys.hotkey([key], duration=0.05)
        if post_wait:
            time.sleep(post_wait)
        return True

    def current_channel_guess(self, thresh: float = 0.82) -> Optional[int]:
        """Guess currently selected channel by looking for gold buttons."""

        frame = self._frame()
        roi = self._minimap_roi()
        for ch in range(1, 9):
            m = self.find_button(frame, ch, thresh=thresh, roi=roi)
            if m:
                cx, cy = m.center
                color = self.color_at(cx, cy, frame)
                if self.is_gold(color):
                    return ch
        return None

    @staticmethod
    def next(ch: int) -> int:
        """Return the next channel number, cycling 8 → 1."""

        if not (1 <= ch <= 8):
            raise ValueError("Kanał poza zakresem 1..8")
        return 1 if ch == 8 else ch + 1

    def cycle_until_target_seen(
        self,
        check_fn: Callable[[], bool],
        *,
        settle: float = 5.0,
        timeout_per_ch: float = 5.0,
        max_rounds: int = 1,
    ) -> bool:
        """Cycle through channels until ``check_fn`` returns ``True``.

        Parameters
        ----------
        check_fn:
            Callable returning ``True`` when the desired target is detected.
        settle:
            Seconds to wait after each channel switch before checking.
        timeout_per_ch:
            How long to keep checking each channel for the target.
        max_rounds:
            Maximum number of full CH1..CH8 cycles to perform.
        """

        current = self.current_channel_guess() or 1
        start_ch = current
        rounds = 0

        if check_fn():
            return True

        while rounds < max_rounds:
            current = self.next(current)
            self.switch(current, post_wait=settle)
            t_end = time.time() + timeout_per_ch
            while True:
                if check_fn():
                    return True
                if time.time() >= t_end:
                    break
                time.sleep(0.1)
            if current == start_ch:
                rounds += 1
        return False

    async def cycle_until_target_seen_async(
        self,
        check_fn: Callable[[], bool],
        *,
        settle: float = 5.0,
        timeout_per_ch: float = 5.0,
        max_rounds: int = 1,
    ) -> bool:
        """Asynchronous variant of :meth:`cycle_until_target_seen`.

        Uses ``asyncio.sleep`` for cooperative waiting so the event loop
        can schedule other tasks (e.g. detector inference) while cycling
        through channels.
        """

        current = self.current_channel_guess() or 1
        start_ch = current
        rounds = 0

        if check_fn():
            return True

        while rounds < max_rounds:
            current = self.next(current)
            # ``switch`` is a blocking call; run it in a thread to avoid
            # stalling the event loop.
            await asyncio.to_thread(self.switch, current, post_wait=settle)
            t_end = time.time() + timeout_per_ch
            while True:
                if check_fn():
                    return True
                if time.time() >= t_end:
                    break
                await asyncio.sleep(0.1)
            if current == start_ch:
                rounds += 1
        return False
