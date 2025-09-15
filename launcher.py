"""Entrypoint for launching the GUI with dependency verification."""

from __future__ import annotations

import argparse
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


def main(argv: list[str] | None = None) -> None:
    """Run environment checks then start the GUI application.

    When ``--multi`` is provided, run the HuntDestroy strategy in
    multi‑client mode instead of starting the GUI.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--multi", type=int, default=0, help="number of clients")
    args = parser.parse_args(argv)

    update_repository()

    if not check_requirements():
        sys.exit(1)

    if args.multi:
        from agent.multi_client import ClientManager
        from agent.hunt_destroy import HuntDestroy

        titles = [str(i + 1) for i in range(args.multi)]
        mgr = ClientManager(titles)
        mgr.run_cycle(HuntDestroy)
        return

    keyboard.add_hotkey("ctrl+x", _handle_teleport)

    from gui.app import main as run_app

    run_app()


if __name__ == "__main__":
    main()

