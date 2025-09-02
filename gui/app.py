"""Application entry point for the GUI."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on ``sys.path``
ROOT_DIR = Path(__file__).resolve()
for parent in ROOT_DIR.parents:
    if (parent / "agent").exists() and (parent / "recorder").exists():
        ROOT_DIR = parent
        break
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6 import QtWidgets

from gui.main_window import MainWindow


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

