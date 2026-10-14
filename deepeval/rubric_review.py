"""Descriptive review tools; these never judge model answers."""

from __future__ import annotations

from dataclasses import asdict

from deepeval.rubric import load_rubric_scores


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
