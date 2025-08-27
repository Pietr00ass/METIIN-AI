import os
import sys
import types

# Make repository root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub pyautogui so interaction module can be imported without the real dependency
pyautogui_stub = types.SimpleNamespace(moveTo=lambda *a, **k: None, click=lambda *a, **k: None)
sys.modules.setdefault("pyautogui", pyautogui_stub)
sys.modules.setdefault("yaml", types.ModuleType("yaml"))

import agent.interaction as interaction


def test_burst_click_executes_requested_number_of_clicks(monkeypatch):
    clicks = []

    monkeypatch.setattr(interaction.pyautogui, "moveTo", lambda *a, **k: None)
    monkeypatch.setattr(interaction.pyautogui, "click", lambda *a, **k: clicks.append(1))
    monkeypatch.setattr(interaction, "_rate_limit_ok", lambda: False)
    monkeypatch.setattr(interaction.time, "sleep", lambda *a, **k: None)

    interaction.burst_click((0, 0, 1, 1), (0, 0, 100, 100), n=5, interval=0)

    assert len(clicks) == 5
