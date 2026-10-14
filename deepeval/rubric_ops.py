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


def write_score_rows(rows, output):
    """Serialize validated rows to an import-compatible new CSV or XLSX."""
    output = Path(output)
    fields = (*REQUIRED_COLUMNS, "notes")
    if output.suffix.lower() == ".csv":
        buffer = StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
        payload = buffer.getvalue().encode("utf-8")
        with output.open("xb") as target:
            target.write(payload)
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
        raise RubricValidationError("Score output must end in .csv or .xlsx.")


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
