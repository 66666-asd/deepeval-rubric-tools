"""Redacted local diagnostics for downstream rubric functionality."""

from __future__ import annotations

import os
import platform
from importlib import metadata


def diagnose_environment():
    """Report versions and safe flags only, never paths, keys or full config."""
    packages = {}
    for name in ("deepeval", "typer", "openpyxl", "defusedxml"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    expected = {
        "DEEPEVAL_TELEMETRY_OPT_OUT": "1",
        "DEEPEVAL_DISABLE_DOTENV": "1",
        "DEEPEVAL_UPDATE_WARNING_OPT_IN": "0",
        "CONFIDENT_OPEN_BROWSER": "0",
        "DEEPEVAL_FILE_SYSTEM": "READ_ONLY",
    }
    checks = {
        name: os.environ.get(name) == value for name, value in expected.items()
    }
    return {
        "python": platform.python_version(),
        "operating_system": platform.system(),
        "packages": packages,
        "offline_configuration": checks,
        "excel_dependencies_installed": all(
            packages[name] is not None for name in ("openpyxl", "defusedxml")
        ),
        "limitations": "Configuration snapshot only; not a firewall or network-isolation guarantee.",
    }
