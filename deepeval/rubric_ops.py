"""Local data preparation operations for rubric score files."""

from __future__ import annotations

from deepeval.rubric import load_rubric_scores, validate_rubric_manifest


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
