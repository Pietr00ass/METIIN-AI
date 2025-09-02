"""Helpers for updating the local Git repository.

Provides a tiny interface by logging status messages and, if PySide6 is
available, showing a message box with the result."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def _notify(message: str, level: int = logging.INFO) -> None:
    """Show ``message`` using a message box when PySide6 is available."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except Exception:
        if level == logging.ERROR:
            logger.error(message)
        else:
            logger.info(message)
        return

    app = QApplication.instance() or QApplication([])
    QMessageBox.information(None, "Updater", message)
    if not QApplication.instance():
        app.quit()


def update_repository(repo_dir: Path | None = None) -> bool:
    """Fetch and merge updates from the remote Git repository."""
    if repo_dir is None:
        repo_dir = Path(__file__).resolve().parents[1]

    try:
        logger.info("Checking for updates from GitHub...")
        subprocess.check_call(["git", "pull", "--ff-only"], cwd=repo_dir)
        _notify("Repository is up to date.")
        return True
    except subprocess.CalledProcessError:
        _notify("Failed to update repository.", level=logging.ERROR)
        return False
