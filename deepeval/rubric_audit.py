"""Reproducible fingerprints and local verification for score artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from deepeval.rubric import RubricValidationError, load_rubric_scores


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
