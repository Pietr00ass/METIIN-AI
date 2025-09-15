import sys
from pathlib import Path
import os

from PySide6 import QtWidgets

# ensure repo root on path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import types
sys.modules.setdefault("pyautogui", types.SimpleNamespace(FAILSAFE=False))
class DummyListener:
    def __init__(self, *a, **k):
        self.daemon = False

    def start(self):
        return None

keyboard_stub = types.SimpleNamespace(Listener=DummyListener, Key=types.SimpleNamespace(f12="f12"))
sys.modules.setdefault("pynput", types.SimpleNamespace(keyboard=keyboard_stub))
sys.modules.setdefault("mss", types.SimpleNamespace(mss=lambda: None))
sys.modules.setdefault("pygetwindow", types.SimpleNamespace(getAllWindows=lambda: []))

import agent
from gui import main_window


def make_app():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_auto_loot_binding(monkeypatch):
    make_app()
    cfg = agent.AgentConfig()
    cfg.auto_loot = False

    monkeypatch.setattr(agent, "get_config", lambda: cfg)
    saved: dict = {}
    monkeypatch.setattr(main_window, "save_agent_config", lambda c: saved.update(c.dict()))

    mw = main_window.MainWindow()
    assert mw.advanced_panel.auto_loot_chk.isChecked() is False
    mw.advanced_panel.auto_loot_chk.setChecked(True)
    assert cfg.auto_loot is True
    assert saved["auto_loot"] is True


def test_buff_validation(monkeypatch):
    make_app()
    cfg = agent.AgentConfig()
    monkeypatch.setattr(agent, "get_config", lambda: cfg)
    monkeypatch.setattr(main_window, "save_agent_config", lambda c: None)
    warned = {}
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *a, **k: warned.setdefault("called", True))
    mw = main_window.MainWindow()
    rows = mw.advanced_panel.buff_table.rowCount()
    mw.advanced_panel.buff_key_input.setText("")
    mw.advanced_panel.add_buff()
    assert mw.advanced_panel.buff_table.rowCount() == rows
    assert warned.get("called")
