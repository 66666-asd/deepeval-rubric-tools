"""Descriptive review tools; these never judge model answers."""

from __future__ import annotations

from dataclasses import asdict

from deepeval.rubric import (
    RubricValidationError,
    compare_rubric_file,
    load_rubric_scores,
)


def review_queue(source, *, minimum_gap=0.0, limit=20, sheet=None):
    """Rank supplied criterion disagreements by absolute normalized gap."""
    import math

    if not math.isfinite(minimum_gap) or not 0 <= minimum_gap <= 100:
        raise RubricValidationError(
            "Minimum gap must be finite and between 0 and 100."
        )
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise RubricValidationError("Limit must be a positive integer.")
    report = compare_rubric_file(source, sheet=sheet)
    queue = []
    for case in report["cases"]:
        for criterion in case["criteria"]:
            gap = abs(criterion["delta_percentage_points"])
            if (
                gap > report["tie_tolerance_percentage_points"]
                and gap >= minimum_gap
            ):
                queue.append(
                    {
                        "case_id": case["case_id"],
                        **criterion,
                        "absolute_gap": gap,
                    }
                )
    queue.sort(
        key=lambda row: (
            -row["absolute_gap"],
            row["case_id"],
            row["criterion_id"],
        )
    )
    return {
        "matching_count": len(queue),
        "shown_count": min(limit, len(queue)),
        "minimum_gap": minimum_gap,
        "items": queue[:limit],
        "interpretation": "Review priority only; not a correctness judgment.",
    }


def diff_scores(before, after):
    """Report additions, removals and field-level edits using stable keys."""

    def index(path):
        return {
            (r.case_id, r.criterion_id): asdict(r)
            for r in load_rubric_scores(path)
        }

    old, new = index(before), index(after)
    changed = []
    for key in sorted(old.keys() & new.keys()):
        fields = {
            field: {"before": old[key][field], "after": new[key][field]}
            for field in old[key]
            if old[key][field] != new[key][field]
        }
        if fields:
            changed.append(
                {"case_id": key[0], "criterion_id": key[1], "fields": fields}
            )
    return {
        "added": [new[key] for key in sorted(new.keys() - old.keys())],
        "removed": [old[key] for key in sorted(old.keys() - new.keys())],
        "changed": changed,
        "unchanged_count": len(old.keys() & new.keys()) - len(changed),
    }
