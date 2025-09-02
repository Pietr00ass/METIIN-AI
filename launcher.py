"""Entrypoint for launching the GUI with dependency verification."""

from __future__ import annotations

import sys

from utils import check_requirements, update_repository


def main() -> None:
    """Run environment checks then start the GUI application."""

    update_repository()

    if not check_requirements():
        sys.exit(1)

    from gui.app import main as run_app

    run_app()


if __name__ == "__main__":
    main()

