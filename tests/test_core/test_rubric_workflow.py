"""Offline tests for local rubric data preparation commands."""

import csv
import json

import pytest
from typer.testing import CliRunner

from deepeval.cli.main import app
from deepeval.rubric import REQUIRED_COLUMNS
from deepeval.rubric_ops import validate_score_file


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
