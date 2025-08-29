import os
import sys
import types

pyautogui_stub = types.ModuleType("pyautogui")
pyautogui_stub.click = lambda *a, **k: None
pyautogui_stub.press = lambda *a, **k: None
sys.modules.setdefault("pyautogui", pyautogui_stub)

yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda f: {}
yaml_stub.safe_dump = lambda data, f, **k: f.write("dump")
sys.modules["yaml"] = yaml_stub

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agent.teleport_config as tc


def test_change_channel(monkeypatch):
    calls = []
    monkeypatch.setattr(tc, "channel_buttons", {2: (10, 20)})
    monkeypatch.setattr(tc.pyautogui, "click", lambda x, y: calls.append((x, y)))
    monkeypatch.setattr(tc.time, "sleep", lambda s: calls.append(s))
    tc.change_channel(2)
    assert calls == [(10, 20), 5.0]


def test_main(monkeypatch):
    run_calls = []
    change_calls = []
    monkeypatch.setattr(tc, "run_positions", lambda ch: run_calls.append(ch))
    monkeypatch.setattr(tc, "change_channel", lambda ch: change_calls.append(ch))
    tc.main()
    assert run_calls == [1, 2, 3, 4]
    assert change_calls == [2, 3, 4]


def test_save_teleport_config(tmp_path, monkeypatch):
    captured = {}

    def fake_dump(data, fh, **kw):
        captured["data"] = data
        fh.write("written")

    monkeypatch.setattr(tc.yaml, "safe_dump", fake_dump)
    path = tmp_path / "tp.yaml"
    data = {"positions_by_channel": {1: [[1, 2]]}, "channel_buttons": {1: [3, 4]}}
    tc.save_teleport_config(data, path)
    assert path.read_text() == "written"
    assert captured["data"] == data
