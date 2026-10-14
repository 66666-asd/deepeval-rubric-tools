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
