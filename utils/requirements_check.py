"""Utilities for verifying that required Python packages are installed.

Reads ``requirements.txt`` and checks installed package versions using
``importlib.metadata``.  Missing or incompatible packages trigger an attempt to
install the full requirements file via ``pip``.
"""

from __future__ import annotations

import subprocess
import sys
from importlib import metadata
from importlib.metadata import PackageNotFoundError
from pathlib import Path

from packaging.requirements import Requirement


def check_requirements(requirements_file: Path | None = None) -> None:
    """Verify installed packages against ``requirements.txt``.

    Parameters
    ----------
    requirements_file:
        Path to the ``requirements.txt`` file.  Defaults to the repository root.
    """

    if requirements_file is None:
        requirements_file = Path(__file__).resolve().parents[1] / "requirements.txt"

    if not requirements_file.exists():
        return

    unmet: list[str] = []
    for line in requirements_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        req = Requirement(line)
        try:
            installed = metadata.version(req.name)
        except PackageNotFoundError:
            unmet.append(f"{req.name}{req.specifier}")
            continue

        if req.specifier and not req.specifier.contains(installed, prereleases=True):
            unmet.append(f"{req.name} {installed} does not satisfy {req.specifier}")

    if not unmet:
        return

    print("Unmet dependencies detected:")
    for item in unmet:
        print(f" - {item}")

    print("Attempting to install dependencies from requirements.txt...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        )
    except subprocess.CalledProcessError:
        print(
            "Automatic installation failed. Please run 'pip install -r requirements.txt' manually."
        )
