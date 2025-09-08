"""Build a standalone executable of the Qt GUI using PyInstaller.

This helper script bundles the ``gui.app`` entry point into a single
executable so non-technical users can run METIIN-AI without installing
Python or dependencies.

Usage:
    python tools/build_gui.py

The resulting files are placed under the ``dist/`` directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PyInstaller.__main__ import run as pyinstaller_run  # type: ignore
except Exception as exc:  # pragma: no cover - executed during import errors
    raise SystemExit(
        "PyInstaller is required to build the executable. Install it with 'pip install pyinstaller'."
    ) from exc


def main() -> None:
    """Invoke PyInstaller with default options."""
    root = Path(__file__).resolve().parents[1]
    app_path = root / "gui" / "app.py"

    # ``--windowed`` hides the console window on Windows.
    # ``--onefile`` creates a single executable for easier distribution.
    pyinstaller_run(
        [
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onefile",
            "--name",
            "metiin-ai",
            str(app_path),
        ]
    )


if __name__ == "__main__":
    main()
