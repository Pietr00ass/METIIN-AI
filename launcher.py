"""Entrypoint for launching the GUI with dependency verification."""

from __future__ import annotations

import sys

import keyboard

from utils import check_requirements, update_repository
from agent.teleport_config import run_positions


current_channel = 1
_teleport_in_progress = False


def _handle_teleport() -> None:
    global _teleport_in_progress
    if _teleport_in_progress:
        return
    _teleport_in_progress = True
    try:
        run_positions(current_channel)
    finally:
        _teleport_in_progress = False


def main() -> None:
    """Run environment checks then start the GUI application."""

    update_repository()

    if not check_requirements():
        sys.exit(1)

    keyboard.add_hotkey("ctrl+x", _handle_teleport)

    from gui.app import main as run_app

    run_app()


if __name__ == "__main__":
    main()

