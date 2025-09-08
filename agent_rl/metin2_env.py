from __future__ import annotations

import numpy as np
import gym
from gym import spaces

from agent.wasd import KeyHold
from recorder.window_capture import WindowCapture


class Metin2Env(gym.Env):
    """Minimal Gym environment around the Metin2 game window."""

    metadata = {"render.modes": ["rgb_array"]}

    def __init__(
        self,
        title: str = "Metin2",
        key_map: list[list[str]] | None = None,
        frame_shape: tuple[int, int, int] = (720, 1280, 4),
        dry: bool = True,
    ) -> None:
        super().__init__()
        self.title = title
        self.key_map = key_map or [["w"], ["a"], ["s"], ["d"], ["space"], []]
        self.action_space = spaces.Discrete(len(self.key_map))
        self.observation_space = spaces.Box(
            low=0, high=255, shape=frame_shape, dtype=np.uint8
        )
        self.kb = KeyHold(dry=dry)
        self.wincap: WindowCapture | None = None

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if self.wincap is not None:
            self.wincap.close()
        self.wincap = WindowCapture(self.title)
        self.wincap.locate()
        img = self.wincap.grab()
        frame = np.array(img)
        if frame.shape != self.observation_space.shape:
            self.observation_space = spaces.Box(
                low=0, high=255, shape=frame.shape, dtype=np.uint8
            )
        self.kb.release_all()
        info = {}
        return frame, info

    def step(self, action: int):
        keys = self.key_map[action]
        if keys:
            if len(keys) == 1:
                self.kb.tap(keys[0])
            else:
                self.kb.hotkey(keys)
        img = self.wincap.grab() if self.wincap is not None else None
        frame = np.array(img) if img is not None else np.zeros(
            self.observation_space.shape, dtype=np.uint8
        )
        reward = 0.0
        done = False
        info: dict = {}
        return frame, reward, done, info

    def render(self):
        if self.wincap is None:
            return None
        img = self.wincap.grab()
        return np.array(img)

    def close(self) -> None:
        if self.wincap is not None:
            self.wincap.close()
            self.wincap = None
        self.kb.release_all()
