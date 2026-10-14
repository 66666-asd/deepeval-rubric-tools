"""Local data preparation operations for rubric score files."""

from __future__ import annotations

import csv
from dataclasses import asdict
from io import StringIO
from pathlib import Path

from deepeval.rubric import (
    REQUIRED_COLUMNS,
    RubricValidationError,
    load_rubric_scores,
    validate_rubric_manifest,
)
from deepeval.rubric_io import write_new_bytes


def write_score_rows(rows, output):
    """Serialize validated rows to an import-compatible new CSV or XLSX."""
    output = Path(output)
    fields = (*REQUIRED_COLUMNS, "notes")
    if output.suffix.lower() == ".jsonl":
        import json

        payload = "".join(
            json.dumps(asdict(row), ensure_ascii=False, allow_nan=False) + "\n"
            for row in rows
        ).encode("utf-8")
        write_new_bytes(output, payload)
        return
    if output.suffix.lower() == ".csv":
        buffer = StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
        payload = buffer.getvalue().encode("utf-8")
        write_new_bytes(output, payload)
    elif output.suffix.lower() == ".xlsx":
        from deepeval.rubric_excel import (
            _append_literals,
            _new_workbook,
            _save_new_workbook,
            _style_sheet,
        )

        book = _new_workbook()
        try:
            sheet = book.active
            sheet.title = "Scores"
            _append_literals(sheet, fields)
            for row in rows:
                _append_literals(sheet, [asdict(row)[key] for key in fields])
            _style_sheet(
                sheet,
                [22, 22, 60, 15, 15, 20, 20, 60],
                numeric_columns=(4, 5, 6, 7),
            )
            _save_new_workbook(book, output)
        finally:
            book.close()
    else:
        raise RubricValidationError(
            "Score output must end in .csv, .xlsx or .jsonl."
        )


def convert_scores(source, output, *, sheet=None):
    rows = load_rubric_scores(source, sheet)
    write_score_rows(rows, output)
    return len(rows)


def merge_scores(sources, output):
    """Merge disjoint score shards; duplicates are errors even when identical."""
    if len(sources) < 2:
        raise RubricValidationError("Merge requires at least two input files.")
    rows, seen = [], set()
    for source in sources:
        for row in load_rubric_scores(source):
            key = (row.case_id, row.criterion_id)
            if key in seen:
                raise RubricValidationError(f"Overlapping shard key: {key!r}.")
            seen.add(key)
            rows.append(row)
    write_score_rows(rows, output)
    return len(rows)


def pair_scores(model_a, model_b, output):
    """Join independently supplied single-model CSV scores by explicit keys."""
    from dataclasses import replace

    from deepeval.rubric import _read_csv, _score_records

    def read_single(path):
        records = _read_csv(
            path, required=(*REQUIRED_COLUMNS[:5], "score"), optional=("notes",)
        )

        def paired_records():
            for line, record in records:
                score = record.pop("score")
                yield (
                    line,
                    {**record, "model_a_score": score, "model_b_score": score},
                )

        return _score_records(paired_records())

    left, right = read_single(model_a), read_single(model_b)
    other = {(row.case_id, row.criterion_id): row for row in right}
    if {(row.case_id, row.criterion_id) for row in left} != other.keys():
        raise RubricValidationError("Single-model score key sets differ.")
    result = []
    for row in left:
        paired = other[(row.case_id, row.criterion_id)]
        if (row.criterion, row.weight, row.max_score) != (
            paired.criterion,
            paired.weight,
            paired.max_score,
        ):
            raise RubricValidationError(
                f"Scoring standards differ for {(row.case_id, row.criterion_id)!r}."
            )
        notes = "\n".join(
            text
            for text in (
                f"A: {row.notes}" if row.notes else "",
                f"B: {paired.notes}" if paired.notes else "",
            )
            if text
        )
        result.append(
            replace(row, model_b_score=paired.model_a_score, notes=notes)
        )
    write_score_rows(result, output)
    return len(result)


def select_cases(source, case_ids, output, *, sheet=None):
    """Select complete cases in source order, rejecting unknown requested IDs."""
    rows = load_rubric_scores(source, sheet)
    requested = set(case_ids)
    if not requested:
        raise RubricValidationError("Select at least one case ID.")
    missing = requested - {row.case_id for row in rows}
    if missing:
        raise RubricValidationError(f"Unknown cases: {sorted(missing)[:20]!r}.")
    selected = [row for row in rows if row.case_id in requested]
    write_score_rows(selected, output)
    return len(selected)


def sample_cases(source, count, seed, output, *, sheet=None):
    """Select a reproducible case sample, independent of source row order."""
    import hashlib
    import json

    rows = load_rubric_scores(source, sheet)
    cases = {row.case_id for row in rows}
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or not 1 <= count <= len(cases)
    ):
        raise RubricValidationError(
            f"Count must be an integer from 1 to {len(cases)}."
        )
    ranked = sorted(
        cases,
        key=lambda key: (
            hashlib.sha256(
                json.dumps([str(seed), key], ensure_ascii=True).encode()
            ).digest(),
            key,
        ),
    )
    selected = set(ranked[:count])
    write_score_rows([row for row in rows if row.case_id in selected], output)
    return sorted(selected)


def import_mapped_csv(source, mapping_path, output):
    """Normalize explicit source-header mappings; never guess semantic fields."""
    import json

    from deepeval.rubric import OPTIONAL_COLUMNS, _read_csv, _score_records

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RubricValidationError(f"Duplicate mapping key: {key!r}.")
            result[key] = value
        return result

    try:
        mapping = json.loads(
            Path(mapping_path).read_text(encoding="utf-8-sig"),
            object_pairs_hook=unique_pairs,
        )
    except (ValueError, UnicodeError) as exc:
        raise RubricValidationError(f"Invalid mapping JSON: {exc}") from exc
    if (
        not isinstance(mapping, dict)
        or not mapping
        or not all(
            isinstance(k, str) and isinstance(v, str) and k and v
            for k, v in mapping.items()
        )
    ):
        raise RubricValidationError(
            "Mapping must be a nonempty JSON object of source names to canonical names."
        )
    values = list(mapping.values())
    if (
        len(set(values)) != len(values)
        or not set(REQUIRED_COLUMNS) <= set(values)
        or not set(values) <= set(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    ):
        raise RubricValidationError(
            "Mapping must cover required columns exactly once; only notes is optional."
        )
    records = (
        (line, {mapping[key]: value for key, value in record.items()})
        for line, record in _read_csv(
            source, required=tuple(mapping), optional=()
        )
    )
    rows = _score_records(records)
    write_score_rows(rows, output)
    return len(rows)


def create_manifest(definition, output):
    """Derive expected keys from independently supplied rubric definitions."""
    from deepeval.rubric import load_rubric_template_csv

    if Path(output).suffix.lower() != ".csv":
        raise RubricValidationError("Manifest output must end in .csv.")
    rows = load_rubric_template_csv(definition)
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["case_id", "criterion_id"])
    writer.writerows((row["case_id"], row["criterion_id"]) for row in rows)
    write_new_bytes(output, buffer.getvalue().encode("utf-8"))
    return len(rows)


def scoring_progress(source, *, sheet=None, definition=None):
    """Check partially filled scores without imputing scores or ranking models."""
    from deepeval.rubric import (
        _read_csv,
        _read_jsonl,
        _read_xlsx,
        _score_records,
        validate_rubric_definition,
    )

    suffix = Path(source).suffix.lower()
    if sheet is not None and suffix != ".xlsx":
        raise RubricValidationError("--sheet can only be used with XLSX input.")
    if suffix == ".csv":
        records = _read_csv(source)
    elif suffix == ".xlsx":
        records = _read_xlsx(source, sheet)
    elif suffix == ".jsonl":
        records = _read_jsonl(source)
    else:
        raise RubricValidationError("Unsupported progress input format.")
    normalized, missing = [], []
    complete_cases = {}
    for line, record in records:
        absent = [
            column
            for column in ("model_a_score", "model_b_score")
            if not record[column]
        ]
        complete_cases[record["case_id"]] = (
            complete_cases.get(record["case_id"], True) and not absent
        )
        if absent:
            missing.append(
                {
                    "case_id": record["case_id"],
                    "criterion_id": record["criterion_id"],
                    "fields": absent,
                }
            )
        # Zero is used ONLY to validate metadata and supplied values; no scores
        # are persisted, returned, or used in comparison calculations.
        normalized.append((line, {**record, **dict.fromkeys(absent, "0")}))
    rows = _score_records(normalized)
    if definition is not None:
        validate_rubric_definition(rows, definition)
    return {
        "criterion_count": len(rows),
        "completed_criteria": len(rows) - len(missing),
        "case_count": len(complete_cases),
        "completed_cases": sum(complete_cases.values()),
        "missing_score_cells": sum(len(item["fields"]) for item in missing),
        "missing_criteria": len(missing),
        "missing_preview": missing[:50],
        "definition_status": "matched"
        if definition is not None
        else "not_checked",
    }


def validate_score_file(path, *, sheet=None, manifest=None):
    """Validate input without computing model rankings or calling a judge."""
    rows = load_rubric_scores(path, sheet)
    result = {
        "status": "valid",
        "case_count": len({row.case_id for row in rows}),
        "criterion_count": len(rows),
        "completeness": "not_checked",
    }
    if manifest is not None:
        result["manifest_check"] = validate_rubric_manifest(rows, manifest)
        result["completeness"] = "matched_manifest"
    return result
