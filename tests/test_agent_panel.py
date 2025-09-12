import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from gui.widgets.agent_panel import AgentPanel


def test_get_config_autopress():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = AgentPanel()
    panel.auto_press_chk.setChecked(True)
    panel.auto_press_key.setText("x")
    panel.auto_press_interval.setValue(2.5)
    cfg = panel.get_config()
    assert cfg["auto_press"] == {
        "enabled": True,
        "key": "x",
        "interval_sec": 2.5,
    }
