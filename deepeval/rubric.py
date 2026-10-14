"""Validate and compare existing human rubric scores without a model call."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = (
    "case_id",
    "criterion_id",
    "criterion",
    "weight",
    "max_score",
    "model_a_score",
    "model_b_score",
)
OPTIONAL_COLUMNS = ("notes",)
TIE_TOLERANCE = 1e-9


class RubricValidationError(ValueError):
    """A score sheet cannot be safely compared."""


@dataclass(frozen=True)
class RubricScore:
    case_id: str
    criterion_id: str
    criterion: str
    weight: float
    max_score: float
    model_a_score: float
    model_b_score: float
    notes: str = ""


def _number(value: str, column: str, line: int) -> float:
    try:
        result = float(value)
    except ValueError:
        raise RubricValidationError(
            f"Line {line}: {column} must be a number; got {value!r}."
        ) from None
    if not math.isfinite(result):
        raise RubricValidationError(f"Line {line}: {column} must be finite.")
    return result


def load_rubric_csv(path: str | Path) -> list[RubricScore]:
    """Load UTF-8 (optionally BOM) CSV; never turn missing scores into zero."""
    rows: list[RubricScore] = []
    seen = set()
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            columns = reader.fieldnames
            if not columns:
                raise RubricValidationError("CSV is empty or has no header.")
            if len(columns) != len(set(columns)):
                raise RubricValidationError("CSV contains duplicate headers.")
            missing = sorted(set(REQUIRED_COLUMNS) - set(columns))
            unknown = sorted(
                set(columns) - set(REQUIRED_COLUMNS) - set(OPTIONAL_COLUMNS)
            )
            if missing or unknown:
                raise RubricValidationError(
                    f"Invalid columns: missing={missing}; unknown={unknown}."
                )
            for record in reader:
                line = reader.line_num
                if None in record or any(
                    value is None for value in record.values()
                ):
                    raise RubricValidationError(
                        f"Line {line}: field count does not match the header."
                    )
                record = {key: value.strip() for key, value in record.items()}
                for column in REQUIRED_COLUMNS:
                    if not record[column]:
                        raise RubricValidationError(
                            f"Line {line}: {column} is required."
                        )
                key = (record["case_id"], record["criterion_id"])
                if key in seen:
                    raise RubricValidationError(
                        f"Line {line}: duplicate case/criterion {key!r}."
                    )
                seen.add(key)
                numbers = {
                    column: _number(record[column], column, line)
                    for column in REQUIRED_COLUMNS[3:]
                }
                for column in ("weight", "max_score"):
                    if numbers[column] <= 0:
                        raise RubricValidationError(
                            f"Line {line}: {column} must be greater than zero."
                        )
                for column in ("model_a_score", "model_b_score"):
                    if not 0 <= numbers[column] <= numbers["max_score"]:
                        raise RubricValidationError(
                            f"Line {line}: {column} must be between zero "
                            "and max_score."
                        )
                rows.append(
                    RubricScore(
                        case_id=key[0],
                        criterion_id=key[1],
                        criterion=record["criterion"],
                        notes=record.get("notes", ""),
                        **numbers,
                    )
                )
    except (UnicodeError, csv.Error) as exc:
        raise RubricValidationError(
            f"Cannot read CSV as valid UTF-8 CSV: {exc}"
        ) from exc
    if not rows:
        raise RubricValidationError("CSV must contain at least one score row.")
    return rows


def _winner(delta: float, model_a: str, model_b: str) -> str:
    if abs(delta) <= TIE_TOLERANCE:
        return "tie"
    return model_a if delta > 0 else model_b


def compare_rubric_csv(
    path: str | Path,
    model_a: str = "model_a",
    model_b: str = "model_b",
) -> dict[str, Any]:
    """Compute per-case weighted percentages, then an equal-case macro mean.

    Input scores are supplied judgments, not judgments made by DeepEval.
    A positive delta always means model A has the higher score.
    """
    model_a, model_b = model_a.strip(), model_b.strip()
    if (
        not model_a
        or not model_b
        or model_a == model_b
        or "tie" in (model_a, model_b)
    ):
        raise RubricValidationError(
            "Model names must be nonempty, distinct, and not 'tie'."
        )
    rows = load_rubric_csv(path)
    groups: dict[str, list[RubricScore]] = {}
    for row in rows:
        groups.setdefault(row.case_id, []).append(row)

    cases = []
    wins = {model_a: 0, model_b: 0, "tie": 0}
    for case_id, criteria in groups.items():
        # Scale before summing so large, finite weights cannot overflow.
        scale = max(row.weight for row in criteria)
        total_weight = math.fsum(row.weight / scale for row in criteria)
        details = []
        for row in criteria:
            share = (row.weight / scale) / total_weight
            a = row.model_a_score / row.max_score * 100
            b = row.model_b_score / row.max_score * 100
            details.append(
                {
                    "criterion_id": row.criterion_id,
                    "criterion": row.criterion,
                    "weight": row.weight,
                    "weight_share": share,
                    "max_score": row.max_score,
                    "model_a_score": row.model_a_score,
                    "model_b_score": row.model_b_score,
                    "model_a_contribution": share * a,
                    "model_b_contribution": share * b,
                    "delta_percentage_points": a - b,
                    "winner": _winner(a - b, model_a, model_b),
                    "notes": row.notes,
                }
            )
        a = math.fsum(item["model_a_contribution"] for item in details)
        b = math.fsum(item["model_b_contribution"] for item in details)
        winner = _winner(a - b, model_a, model_b)
        wins[winner] += 1
        cases.append(
            {
                "case_id": case_id,
                "criterion_count": len(criteria),
                "model_a_score": a,
                "model_b_score": b,
                "delta_percentage_points": a - b,
                "winner": winner,
                "criteria": details,
            }
        )
    a = math.fsum(case["model_a_score"] for case in cases) / len(cases)
    b = math.fsum(case["model_b_score"] for case in cases) / len(cases)
    return {
        "schema_version": 1,
        "source": str(Path(path)),
        "models": {"a": model_a, "b": model_b},
        "method": "weighted normalized criteria; equal-weight case macro mean",
        "score_range": [0, 100],
        "tie_tolerance_percentage_points": TIE_TOLERANCE,
        "case_count": len(cases),
        "criterion_count": len(rows),
        "model_a_score": a,
        "model_b_score": b,
        "delta_percentage_points": a - b,
        "winner": _winner(a - b, model_a, model_b),
        "case_wins": wins,
        "cases": cases,
    }
