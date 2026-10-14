"""Reproducible fingerprints and local verification for score artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from deepeval.rubric import (
    RubricValidationError,
    compare_rubric_file,
    load_rubric_scores,
)


def verify_report(
    report_path, source, *, sheet=None, manifest=None, definition=None
):
    """Recompute a saved JSON report using only caller-supplied source paths."""
    path = Path(report_path)
    if path.stat().st_size > 50 * 1024 * 1024:
        raise RubricValidationError(
            "Report exceeds the 50 MiB verification limit."
        )

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RubricValidationError(f"Duplicate report key: {key!r}.")
            result[key] = value
        return result

    try:
        saved = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=unique_object,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RubricValidationError(f"Invalid report JSON: {exc}") from exc
    if (
        not isinstance(saved, dict)
        or saved.get("schema_version") != 1
        or not isinstance(saved.get("models"), dict)
    ):
        raise RubricValidationError(
            "Expected a schema-version-1 comparison report."
        )
    models = saved["models"]
    if set(models) != {"a", "b"} or not all(
        isinstance(v, str) for v in models.values()
    ):
        raise RubricValidationError("Report model labels are invalid.")
    if ("manifest_check" in saved) != (manifest is not None) or (
        "definition_check" in saved
    ) != (definition is not None):
        raise RubricValidationError(
            "Supply the same manifest/definition validation inputs as the report."
        )
    fresh = compare_rubric_file(
        source,
        models["a"],
        models["b"],
        sheet=sheet,
        manifest=manifest,
        definition=definition,
    )
    # Source paths are relocatable. No path from untrusted report JSON is opened.
    for report in (saved, fresh):
        report.pop("source", None)
        report.pop("source_sheet", None)
        for key in ("manifest_check", "definition_check"):
            if key in report:
                if not isinstance(report[key], dict):
                    raise RubricValidationError(
                        "Invalid report validation metadata."
                    )
                report[key].pop("source", None)
    try:
        left = json.dumps(saved, sort_keys=True, allow_nan=False)
        right = json.dumps(fresh, sort_keys=True, allow_nan=False)
    except ValueError as exc:
        raise RubricValidationError(
            "Report contains nonfinite numbers."
        ) from exc
    if left != right:
        raise RubricValidationError(
            "Saved report differs from recomputed score results."
        )
    return {
        "status": "verified",
        "case_count": fresh["case_count"],
        "criterion_count": fresh["criterion_count"],
        "meaning": "Recomputed values match; not a signature or authorship proof.",
    }


def create_review_bundle(source, output, *, sheet=None):
    """Package canonical scores and recomputable reports, not unrelated files."""
    from io import BytesIO
    from tempfile import TemporaryDirectory
    from zipfile import ZIP_DEFLATED, ZipFile

    from deepeval.rubric_io import write_new_bytes
    from deepeval.rubric_ops import write_score_rows
    from deepeval.rubric_reports import write_html_report

    if Path(output).suffix.lower() != ".zip":
        raise RubricValidationError("Review bundle output must end in .zip.")
    rows = load_rubric_scores(source, sheet)
    with TemporaryDirectory(prefix="rubric-bundle-") as directory:
        root = Path(directory)
        normalized = root / "scores.jsonl"
        write_score_rows(rows, normalized)
        report = compare_rubric_file(normalized)
        report["source"] = "scores.jsonl"
        report_bytes = (
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
            + "\n"
        ).encode("utf-8")
        write_html_report(report, root / "report.html")
        entries = {
            "scores.jsonl": normalized.read_bytes(),
            "report.json": report_bytes,
            "report.html": (root / "report.html").read_bytes(),
            "README.txt": b"Supplied scores and notes are included. Review before sharing.\nVerify: deepeval rubric verify-report report.json scores.jsonl\nChecksums identify bytes, not authorship or a trusted signature.\n",
        }
    inventory = {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        for name, data in entries.items()
    }
    entries["checksums.json"] = json.dumps(
        inventory, indent=2, sort_keys=True
    ).encode("utf-8")
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    write_new_bytes(output, buffer.getvalue())
    return {"files": sorted(entries), "criterion_count": len(rows)}


def fingerprint_scores(source, *, sheet=None):
    """Return raw-file and canonical validated-content SHA-256 fingerprints."""
    source = Path(source)

    def file_hash():
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    before = file_hash()
    rows = load_rubric_scores(source, sheet)
    after = file_hash()
    if before != after:
        raise RubricValidationError(
            "Source changed while computing its fingerprint."
        )
    records = [
        asdict(row)
        for row in sorted(rows, key=lambda row: (row.case_id, row.criterion_id))
    ]
    for row in records:
        for key in ("weight", "max_score", "model_a_score", "model_b_score"):
            if row[key] == 0:
                row[key] = 0.0
    canonical = json.dumps(
        records,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "algorithm": "sha256",
        "canonical_version": 1,
        "file_sha256": before,
        "content_sha256": hashlib.sha256(canonical).hexdigest(),
        "criterion_count": len(rows),
        "case_count": len({r.case_id for r in rows}),
        "selected_sheet": sheet,
        "meaning": "File/content identity only, not authorship or a trusted signature.",
    }
