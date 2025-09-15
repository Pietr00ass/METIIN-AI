from __future__ import annotations

import time
from typing import Iterable, Type

from recorder.window_capture import WindowCapture
from .strategy import AgentStrategy


class ClientManager:
    """Manage multiple client windows and run a strategy sequentially."""

    def __init__(self, windows: Iterable[str | WindowCapture]):
        self.clients: list[WindowCapture] = []
        for w in windows:
            if isinstance(w, str):
                self.clients.append(WindowCapture(w))
            else:
                self.clients.append(w)

    def run_cycle(
        self,
        strategy_cls: Type[AgentStrategy],
        per_client_sec: float = 300.0,
    ) -> None:
        """Run ``strategy_cls`` on each client for ``per_client_sec`` seconds.

        Each client is processed sequentially. The strategy is instantiated
        with the window capture instance and ``step`` is called repeatedly
        for the requested duration. After the time elapses the strategy is
        stopped and the next client is processed.
        """

        for win in self.clients:
            strategy = strategy_cls(window_capture=win)
            start = time.monotonic()
            while True:
                strategy.step()
                if time.monotonic() - start >= per_client_sec:
                    break
                time.sleep(0.1)
            try:
                strategy.stop()
            except Exception:
                pass
