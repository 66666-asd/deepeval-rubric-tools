"""Regression tests for independently supplied complete rubric inventories."""

import csv
import json

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from deepeval.cli.main import app
from deepeval.rubric import (
    REQUIRED_COLUMNS,
    RubricValidationError,
    compare_rubric_file,
)


def write_csv(path, columns, rows, encoding="utf-8"):
    with path.open("w", encoding=encoding, newline="") as target:
        writer = csv.writer(target)
        writer.writerow(columns)
        writer.writerows(rows)
    return path


@pytest.fixture()
def scores(tmp_path):
    return write_csv(
        tmp_path / "scores.csv",
        REQUIRED_COLUMNS,
        [
            ["001", "r1", "Accuracy", 1, 2, 2, 1],
            ["002", "r1", "Coverage", 1, 4, 1, 4],
        ],
    )


def manifest(tmp_path, rows=None, columns=("case_id", "criterion_id")):
    if rows is None:
        rows = [["001", "r1"], ["002", "r1"]]
    return write_csv(tmp_path / "expected.csv", columns, rows)


def test_manifest_success_is_recorded_without_changing_scores(tmp_path, scores):
    before = compare_rubric_file(scores)
    after = compare_rubric_file(scores, manifest=manifest(tmp_path))
    check = after.pop("manifest_check")
    assert after == before
    assert check["status"] == "passed"
    assert (
        check["expected_criterion_count"]
        == check["matched_criterion_count"]
        == 2
    )


def test_jointly_missing_whole_case_is_detected(tmp_path, scores):
    expected = manifest(tmp_path, [["001", "r1"], ["002", "r1"], ["003", "r1"]])
    with pytest.raises(RubricValidationError, match="missing=1.*003"):
        compare_rubric_file(scores, manifest=expected)


def test_missing_and_unexpected_keys_are_both_reported(tmp_path, scores):
    expected = manifest(tmp_path, [["001", "r1"], ["002", "r2"]])
    with pytest.raises(RubricValidationError) as error:
        compare_rubric_file(scores, manifest=expected)
    assert "missing=1 [('002', 'r2')]" in str(error.value)
    assert "unexpected=1 [('002', 'r1')]" in str(error.value)


@pytest.mark.parametrize(
    "rows,message",
    [
        ([], "at least one key"),
        ([["001", "r1"], [" 001 ", "r1"]], "duplicate"),
        ([["", "r1"]], "case_id is required"),
        ([["001", ""]], "criterion_id is required"),
        ([["001"]], "field count"),
        ([["001", "r1", "extra"]], "field count"),
    ],
)
def test_malformed_manifest_is_rejected(tmp_path, scores, rows, message):
    with pytest.raises(RubricValidationError, match=message):
        compare_rubric_file(scores, manifest=manifest(tmp_path, rows))


@pytest.mark.parametrize(
    "columns",
    [
        ("case_id",),
        ("case_id", "criterion_id", "notes"),
        ("case_id", "case_id"),
    ],
)
def test_manifest_headers_are_strict(tmp_path, scores, columns):
    with pytest.raises(RubricValidationError):
        compare_rubric_file(
            scores, manifest=manifest(tmp_path, columns=columns)
        )


def test_bom_manifest_order_does_not_matter(tmp_path, scores):
    path = write_csv(
        tmp_path / "expected.csv",
        ("criterion_id", "case_id"),
        [["r1", "002"], ["r1", "001"]],
        encoding="utf-8-sig",
    )
    assert (
        compare_rubric_file(scores, manifest=path)["manifest_check"]["status"]
        == "passed"
    )


def test_manifest_requires_csv(tmp_path, scores):
    with pytest.raises(RubricValidationError, match="must be a UTF-8 CSV"):
        compare_rubric_file(scores, manifest=tmp_path / "expected.xlsx")


def test_manifest_applies_to_excel_input(tmp_path, socket_disabled):
    book = Workbook()
    book.active.append(list(REQUIRED_COLUMNS))
    book.active.append(["001", "r1", "Accuracy", 1, 2, 2, 1])
    path = tmp_path / "scores.xlsx"
    book.save(path)
    book.close()
    report = compare_rubric_file(
        path, manifest=manifest(tmp_path, [["001", "r1"]])
    )
    assert report["manifest_check"]["matched_criterion_count"] == 1


def test_cli_mismatch_does_not_create_report(tmp_path, scores):
    expected = manifest(tmp_path, [["001", "r1"]])
    output = tmp_path / "report.json"
    result = CliRunner().invoke(
        app,
        [
            "rubric",
            "compare",
            str(scores),
            "--manifest",
            str(expected),
            "-o",
            str(output),
        ],
    )
    assert result.exit_code == 2
    assert "unexpected=1" in result.output
    assert not output.exists()


def test_cli_matches_manifest_offline(tmp_path, scores, socket_disabled):
    expected = manifest(tmp_path)
    result = CliRunner().invoke(
        app, ["rubric", "compare", str(scores), "--manifest", str(expected)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["manifest_check"]["status"] == "passed"


def test_cli_never_overwrites_manifest(tmp_path, scores):
    expected = manifest(tmp_path)
    before = expected.read_bytes()
    result = CliRunner().invoke(
        app,
        [
            "rubric",
            "compare",
            str(scores),
            "--manifest",
            str(expected),
            "-o",
            str(expected),
        ],
    )
    assert result.exit_code == 2
    assert expected.read_bytes() == before


def test_large_mismatch_message_is_bounded(tmp_path, scores):
    expected = manifest(tmp_path, [[f"q{i:04d}", "r1"] for i in range(100)])
    with pytest.raises(RubricValidationError) as error:
        compare_rubric_file(scores, manifest=expected)
    assert "missing=100" in str(error.value)
    assert "q0019" in str(error.value)
    assert "q0020" not in str(error.value)
