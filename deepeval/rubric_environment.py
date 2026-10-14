"""Redacted local diagnostics for downstream rubric functionality."""

from __future__ import annotations

import os
import platform
from importlib import metadata


def describe_schema(kind="scores"):
    """Expose a versioned field contract without importing optional Excel code."""
    from deepeval.rubric import (
        MAX_SCORE_ROWS,
        MAX_TEXT_BYTES,
        OPTIONAL_COLUMNS,
        REQUIRED_COLUMNS,
        TEMPLATE_REQUIRED_COLUMNS,
        RubricValidationError,
    )

    required_by_kind = {
        "scores": REQUIRED_COLUMNS,
        "definition": TEMPLATE_REQUIRED_COLUMNS,
        "manifest": ("case_id", "criterion_id"),
    }
    if kind not in required_by_kind:
        raise RubricValidationError(
            "Schema kind must be scores, definition or manifest."
        )
    required = required_by_kind[kind]
    optional = OPTIONAL_COLUMNS if kind != "manifest" else ()
    constraints = {
        "case_id": "Nonempty text; preserve leading zeros.",
        "criterion_id": "Nonempty text; unique in combination with case_id.",
        "criterion": "Nonempty text describing the scoring standard.",
        "weight": "Finite number greater than zero; relative within each case.",
        "max_score": "Finite number greater than zero.",
        "model_a_score": "Finite number from zero through max_score; blank is not zero.",
        "model_b_score": "Finite number from zero through max_score; blank is not zero.",
        "notes": "Optional text; empty is permitted.",
    }
    return {
        "contract_version": 1,
        "kind": kind,
        "fields": [
            {
                "name": field,
                "required": field in required,
                "type": "number" if field in REQUIRED_COLUMNS[3:] else "text",
                "constraint": constraints[field],
            }
            for field in (*required, *optional)
        ],
        "unique_key": ["case_id", "criterion_id"],
        "unknown_fields": "rejected",
        "input_formats": ["csv", "xlsx", "jsonl"]
        if kind == "scores"
        else ["csv"],
        "text_input_limits": {
            "bytes": MAX_TEXT_BYTES,
            "data_rows": MAX_SCORE_ROWS,
        },
        "encoding": "UTF-8; optional BOM for text input",
        "description": "Application field contract, not a JSON Schema validation document.",
    }


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
