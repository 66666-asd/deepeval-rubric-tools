"""Offline tests for local rubric data preparation commands."""

import csv
import json

import pytest
from typer.testing import CliRunner

from deepeval.cli.main import app
from deepeval.rubric import (
    REQUIRED_COLUMNS,
    RubricValidationError,
    compare_rubric_file,
    load_rubric_scores,
)
from deepeval.rubric_ops import convert_scores, validate_score_file


def test_conversion_roundtrip_and_file_protection(scores, tmp_path):
    xlsx = tmp_path / "scores.xlsx"
    csv_path = tmp_path / "roundtrip.csv"
    assert convert_scores(scores, xlsx) == 3
    result = CliRunner().invoke(
        app, ["rubric", "convert", str(xlsx), str(csv_path)]
    )
    assert result.exit_code == 0, result.output
    assert load_rubric_scores(scores) == load_rubric_scores(csv_path)
    with pytest.raises(FileExistsError):
        convert_scores(scores, xlsx)
    with pytest.raises(RubricValidationError):
        convert_scores(scores, tmp_path / "unsupported.xls")


def test_merge_disjoint_shards_and_reject_overlap(scores, tmp_path):
    from deepeval.rubric_ops import merge_scores

    other = make_csv(
        tmp_path / "other.csv", [["003", "r1", "Extra", 1, 1, 1, 0, ""]]
    )
    output = tmp_path / "merged.csv"
    result = CliRunner().invoke(
        app, ["rubric", "merge", str(scores), str(other), "-o", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert len(load_rubric_scores(output)) == 4
    assert load_rubric_scores(output)[:3] == load_rubric_scores(scores)
    failed = tmp_path / "failed.csv"
    with pytest.raises(RubricValidationError, match="Overlapping"):
        merge_scores([scores, scores], failed)
    assert not failed.exists()
    with pytest.raises(RubricValidationError, match="at least two"):
        merge_scores([scores], failed)


def test_pair_matches_keys_not_row_order_and_keeps_both_notes(tmp_path):
    from deepeval.rubric_ops import pair_scores

    header = [*REQUIRED_COLUMNS[:5], "score", "notes"]
    left = make_csv(
        tmp_path / "a.csv",
        [["01", "r1", "A", 1, 4, 4, "a1"], ["02", "r1", "B", 1, 4, 1, ""]],
        header,
    )
    right = make_csv(
        tmp_path / "b.csv",
        [["02", "r1", "B", 1, 4, 3, ""], ["01", "r1", "A", 1, 4, 2, "b1"]],
        header,
    )
    output = tmp_path / "paired.csv"
    result = CliRunner().invoke(
        app, ["rubric", "pair", str(left), str(right), str(output)]
    )
    assert result.exit_code == 0, result.output
    rows = load_rubric_scores(output)
    assert [(r.model_a_score, r.model_b_score) for r in rows] == [
        (4, 2),
        (1, 3),
    ]
    assert rows[0].notes == "A: a1\nB: b1"
    make_csv(right, [["01", "r1", "A", 1, 4, 2, ""]], header)
    with pytest.raises(RubricValidationError, match="key sets"):
        pair_scores(left, right, tmp_path / "bad.csv")


def test_case_selection_preserves_whole_cases(scores, tmp_path):
    from deepeval.rubric_ops import select_cases

    output = tmp_path / "selected.csv"
    result = CliRunner().invoke(
        app, ["rubric", "select", str(scores), str(output), "--case", "001"]
    )
    assert result.exit_code == 0, result.output
    assert load_rubric_scores(output) == load_rubric_scores(scores)[:2]
    for case_ids in ([], ["001", "unknown"]):
        with pytest.raises(RubricValidationError):
            select_cases(scores, case_ids, tmp_path / "bad.csv")
    assert not (tmp_path / "bad.csv").exists()


def make_csv(path, rows, headers=(*REQUIRED_COLUMNS, "notes")):
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(headers)
        writer.writerows(rows)
    return path


@pytest.fixture()
def scores(tmp_path):
    return make_csv(
        tmp_path / "scores.csv",
        [
            ["001", "r1", "Accuracy", 3, 4, 4, 2, "review"],
            ["001", "r2", "Evidence", 1, 2, 1, 2, ""],
            ["002", "r1", "Coverage", 1, 5, 3, 4, ""],
        ],
    )


def test_validate_file_does_not_claim_completeness(scores):
    result = validate_score_file(scores)
    assert result == {
        "status": "valid",
        "case_count": 2,
        "criterion_count": 3,
        "completeness": "not_checked",
    }


def test_validate_command_manifest_and_errors(scores, tmp_path):
    manifest = make_csv(
        tmp_path / "keys.csv",
        [["001", "r1"], ["001", "r2"], ["002", "r1"]],
        ["case_id", "criterion_id"],
    )
    runner = CliRunner()
    result = runner.invoke(
        app, ["rubric", "validate", str(scores), "--manifest", str(manifest)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["completeness"] == "matched_manifest"
    result = runner.invoke(
        app, ["rubric", "validate", str(tmp_path / "missing.csv")]
    )
    assert result.exit_code == 2
    assert result.stdout == ""


@pytest.mark.parametrize(
    "field,value", [(2, "different standard"), (3, 2), (4, 6), (0, "extra")]
)
def test_definition_check_detects_changed_standard(
    scores, tmp_path, field, value
):
    rows = [
        ["001", "r1", "Accuracy", 3, 4],
        ["001", "r2", "Evidence", 1, 2],
        ["002", "r1", "Coverage", 1, 5],
    ]
    definition = make_csv(
        tmp_path / "definitions.csv", rows, REQUIRED_COLUMNS[:5]
    )
    report = compare_rubric_file(scores, definition=definition)
    assert report["definition_check"]["status"] == "passed"
    rows[0][field] = value
    make_csv(definition, rows, REQUIRED_COLUMNS[:5])
    with pytest.raises(RubricValidationError, match="Definition"):
        compare_rubric_file(scores, definition=definition)
    result = CliRunner().invoke(
        app, ["rubric", "compare", str(scores), "--definition", str(definition)]
    )
    assert result.exit_code == 2
