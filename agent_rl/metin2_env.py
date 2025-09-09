from __future__ import annotations

import logging
import warnings

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from PIL import Image

from agent.wasd import KeyHold
from recorder.window_capture import WindowCapture

try:  # ``ObjectDetector`` uses ``ultralytics`` which might be unavailable in tests
    from agent.detector import ObjectDetector, Detection
except Exception:  # pragma: no cover - fallback for minimal environments
    ObjectDetector = None  # type: ignore
    Detection = dict  # type: ignore


class Metin2Env(gym.Env):
    """Minimal Gym environment around the Metin2 game window.

    Frames are returned in ``(height, width, channel)`` RGB format. When using
    Stable-Baselines3, wrap this environment with ``VecTransposeImage`` or a
    similar wrapper to obtain channel-first tensors.
    """

    metadata = {"render_modes": ["rgb_array"]}

    def __init__(
        self,
        title: str = "Metin2",
        key_map: list[list[str]] | None = None,
        frame_shape: tuple[int, int, int] = (84, 84, 3),
        dry: bool = True,
        detector_model: str | None = None,
        hp_bar: tuple[slice, slice] | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.key_map = key_map or [["w"], ["a"], ["s"], ["d"], ["space"], []]
        self.action_space = spaces.Discrete(len(self.key_map))
        self.frame_shape = frame_shape
        self.observation_space = spaces.Box(
            low=0, high=255, shape=self.frame_shape, dtype=np.uint8
        )
        self.kb = KeyHold(dry=dry)
        self.wincap: WindowCapture | None = None
        self.detector = (
            ObjectDetector(detector_model)
            if (detector_model and ObjectDetector is not None)
            else None
        )
        if detector_model and self.detector is None:
            warnings.warn("Detector initialization failed; proceeding without it")
        self._last_dets: list[Detection] = []
        self._last_hp = 1.0
        # Region of the HP bar within the frame. Defaults assume top-left bar
        self.hp_bar = hp_bar or (slice(0, 20), slice(0, 200))

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if self.wincap is not None:
            self.wincap.close()
        self.wincap = WindowCapture(self.title)
        self.wincap.locate()
        img = self.wincap.grab()
        frame = self._preprocess(
            np.frombuffer(img.rgb, dtype=np.uint8).reshape(img.height, img.width, 3)
        )
        self.kb.release_all()
        info = {}
        return frame, info

    # --- helpers ---------------------------------------------------------
    def _detect_monsters(self, frame: np.ndarray) -> list[Detection]:
        """Run the configured detector on the frame and return detections.

        Returns an empty list when no detector is available. The frame is
        expected in RGBA/RGB format and converted to BGR for YOLO."""

        if self.detector is None:
            return []
        # convert RGB(A) -> BGR
        bgr = frame[..., :3][:, :, ::-1]
        try:
            return self.detector.infer(bgr)
        except Exception as exc:
            logging.exception("Detector inference failed", exc_info=exc)
            return []

    def _read_hp(self, frame: np.ndarray) -> float:
        """Estimate current HP from the HUD.

        This simplistic implementation computes the fraction of red pixels in
        a predefined screen region. It returns a value in ``[0, 1]``."""

        bar = frame[self.hp_bar]
        if bar.size == 0:
            return 0.0
        red = bar[..., 0]
        filled = np.count_nonzero(red > 200)
        return float(filled) / float(red.size)

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        keys = self.key_map[action]
        if keys:
            if len(keys) == 1:
                self.kb.tap(keys[0])
            else:
                self.kb.hotkey(keys)
        img = self.wincap.grab() if self.wincap is not None else None
        raw = (
            np.frombuffer(img.rgb, dtype=np.uint8).reshape(img.height, img.width, 3)
            if img is not None
            else np.zeros(self.frame_shape, dtype=np.uint8)
        )
        frame = self._preprocess(raw)

        reward = 0.0
        terminated = False
        truncated = False

        # monster detection -------------------------------------------------
        dets = self._detect_monsters(frame)
        prev = len(self._last_dets)
        curr = len(dets)
        if prev and curr < prev:
            reward += float(prev - curr)
        self._last_dets = dets

        # HP tracking -------------------------------------------------------
        hp = self._read_hp(frame)
        if hp < self._last_hp:
            reward -= self._last_hp - hp
        if hp <= 0.0:
            terminated = True
            reward -= 1.0
        self._last_hp = hp

        # idle/time penalty -------------------------------------------------
        reward -= 0.01

        info: dict = {"hp": hp, "monsters": curr}
        return frame, reward, terminated, truncated, info

    def render(self):
        if self.wincap is None:
            return None
        img = self.wincap.grab()
        return np.frombuffer(img.rgb, dtype=np.uint8).reshape(img.height, img.width, 3)

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Drop alpha channel and resize to the configured frame shape."""
        img = Image.fromarray(frame)
        img = img.resize(self.frame_shape[1::-1], Image.BILINEAR)
        arr = np.array(img, dtype=np.uint8)
        return arr

    def close(self) -> None:
        if self.wincap is not None:
            self.wincap.close()
            self.wincap = None
        self.kb.release_all()
