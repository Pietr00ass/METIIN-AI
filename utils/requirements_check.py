"""Helpers for validating and updating Python dependencies.

The module reads :mod:`requirements.txt` and verifies that installed packages
match the declared version constraints using :mod:`importlib.metadata`. When a
package is missing or its version is incompatible, the module can attempt to
install the needed packages via ``pip``.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from importlib import metadata
from importlib.metadata import PackageNotFoundError
from pathlib import Path

from packaging.requirements import Requirement

logger = logging.getLogger(__name__)


def update_requirements(
    requirements: list[Requirement] | None = None,
    requirements_file: Path | None = None,
) -> bool:
    """Install packages using ``pip``.

    Parameters
    ----------
    requirements:
        Specific requirement objects to install. If ``None`` the entire
        ``requirements.txt`` file is installed.
    requirements_file:
        Location of the ``requirements.txt`` file used when ``requirements`` is
        ``None``. Defaults to the repository root.

    Returns
    -------
    bool
        ``True`` if installation succeeded, otherwise ``False``.
    """

    if requirements is None:
        if requirements_file is None:
            requirements_file = Path(__file__).resolve().parents[1] / "requirements.txt"
        if not requirements_file.exists():
            return False
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
    else:
        cmd = [sys.executable, "-m", "pip", "install"] + [str(r) for r in requirements]

    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def check_requirements(requirements_file: Path | None = None) -> bool:
    """Verify installed packages against ``requirements.txt`` and update if needed.

    Returns
    -------
    bool
        ``True`` if all dependencies are satisfied, otherwise ``False``.
    """

    if requirements_file is None:
        requirements_file = Path(__file__).resolve().parents[1] / "requirements.txt"

    if not requirements_file.exists():
        return True

    unmet: list[Requirement] = []
    for line in requirements_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        req = Requirement(line)
        try:
            installed = metadata.version(req.name)
        except PackageNotFoundError:
            unmet.append(req)
            continue

        if req.specifier and not req.specifier.contains(installed, prereleases=True):
            unmet.append(req)

    if not unmet:
        return True

    logger.error("Unmet dependencies detected:")
    for item in unmet:
        logger.error(" - %s", item)

    logger.info("Attempting to install missing dependencies...")
    if update_requirements(unmet):
        return check_requirements(requirements_file)

    logger.error(
        "Automatic installation failed. Please run 'pip install -r requirements.txt' manually."
    )
    return False


def ensure_tesseract_available(pytesseract_module=None) -> None:
    """Validate that the Tesseract OCR binary can be executed.

    Parameters
    ----------
    pytesseract_module:
        Optional module-like object exposing ``tesseract_cmd``. When ``None`` the
        real :mod:`pytesseract` package is imported.
    """

    if pytesseract_module is None:
        try:
            import pytesseract as pytesseract_module  # type: ignore
        except ImportError as exc:  # pragma: no cover - defensive
            message = (
                "pytesseract is not installed. Install project dependencies from "
                "requirements.txt and ensure the package is available."
            )
            logger.error(message)
            raise RuntimeError(message) from exc

    pytesseract_attr = getattr(pytesseract_module, "pytesseract", pytesseract_module)

    # Lightweight guard for tests where a stub replaces pytesseract.
    if not hasattr(pytesseract_attr, "TesseractNotFoundError"):
        return

    tesseract_cmd = getattr(pytesseract_attr, "tesseract_cmd", None)
    if not tesseract_cmd:
        tesseract_cmd = getattr(pytesseract_module, "tesseract_cmd", None)
    if not tesseract_cmd:
        tesseract_cmd = "tesseract"

    if shutil.which(tesseract_cmd):
        return

    message = (
        "Tesseract OCR executable not found on the PATH. Install Tesseract and ensure "
        f"the '{tesseract_cmd}' command is available (run 'tesseract --version' to verify)."
    )
    logger.error(message)
    raise FileNotFoundError(message)
