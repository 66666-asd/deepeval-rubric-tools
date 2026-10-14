"""Downstream XLSX importer tests; fixtures contain synthetic scores only."""

import csv
import json
from datetime import datetime

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from deepeval.cli.main import app
from deepeval.rubric import (
    REQUIRED_COLUMNS,
    RubricValidationError,
    compare_rubric_csv,
    compare_rubric_file,
    load_rubric_scores,
)


def make_workbook(tmp_path, rows=None, extra_sheet=False):
    path = tmp_path / "scores.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Scores"
    sheet.append(list(REQUIRED_COLUMNS))
    if rows is None:
        rows = [["001", "r1", "Accuracy", 1, 4, 4, 2]]
    for row in rows:
        sheet.append(row)
    if extra_sheet:
        book.create_sheet("Instructions")
    book.save(path)
    book.close()
    return path


def test_excel_and_csv_have_identical_scores(tmp_path, socket_disabled):
    rows = [
        ["001", "r1", "Accuracy", 3, 4, 4, 2],
        ["001", "r2", "Evidence", 1, 2, 1, 2],
        ["002", "r1", "Clarity", 1, 2, 1, 1],
    ]
    excel_path = make_workbook(tmp_path, rows)
    csv_path = tmp_path / "scores.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(REQUIRED_COLUMNS)
        writer.writerows(rows)
    excel = compare_rubric_file(excel_path)
    csv_report = compare_rubric_csv(csv_path)
    excel.pop("source")
    csv_report.pop("source")
    assert excel == csv_report
    assert excel["cases"][0]["case_id"] == "001"


def test_multiple_sheets_require_explicit_selection(tmp_path):
    path = make_workbook(tmp_path, extra_sheet=True)
    with pytest.raises(RubricValidationError, match="multiple sheets"):
        compare_rubric_file(path)
    report = compare_rubric_file(path, sheet="Scores")
    assert report["source_sheet"] == "Scores"
    assert report["model_a_score"] == 100


def test_unknown_sheet_is_rejected(tmp_path):
    with pytest.raises(RubricValidationError, match="was not found"):
        load_rubric_scores(make_workbook(tmp_path), sheet="Missing")


@pytest.mark.parametrize(
    "index,value,message",
    [
        (0, 1, "must be text"),
        (0, datetime(2026, 1, 1), "must be text"),
        (2, True, "booleans"),
        (3, False, "booleans"),
        (4, 0, "greater than zero"),
        (5, "=2+2", "formulas"),
        (5, "#DIV/0!", "Excel errors"),
        (5, None, "required"),
        (5, -1, "between zero"),
        (6, 5, "between zero"),
        (6, "N/A", "must be a number"),
    ],
)
def test_invalid_excel_values_are_rejected(tmp_path, index, value, message):
    row = ["001", "r1", "Accuracy", 1, 4, 4, 2]
    row[index] = value
    with pytest.raises(RubricValidationError, match=message):
        load_rubric_scores(make_workbook(tmp_path, [row]))


def test_excel_duplicate_keys_are_rejected(tmp_path):
    row = ["001", "r1", "Accuracy", 1, 4, 4, 2]
    with pytest.raises(RubricValidationError, match="duplicate"):
        load_rubric_scores(make_workbook(tmp_path, [row, row]))


def test_blank_rows_are_skipped_but_partial_rows_are_validated(tmp_path):
    valid = ["001", "r1", "Accuracy", 1, 4, 4, 2]
    path = make_workbook(tmp_path, [[None] * 7, valid, [None] * 7])
    assert len(load_rubric_scores(path)) == 1
    path = make_workbook(tmp_path, [valid, ["002"]])
    with pytest.raises(RubricValidationError, match="required"):
        load_rubric_scores(path)


def test_extra_data_cells_are_not_silently_lost(tmp_path):
    path = make_workbook(
        tmp_path, [["001", "r1", "Accuracy", 1, 4, 4, 2, "extra"]]
    )
    with pytest.raises(RubricValidationError, match="extra cells"):
        load_rubric_scores(path)


def test_empty_workbook_is_rejected(tmp_path):
    with pytest.raises(RubricValidationError, match="at least one"):
        load_rubric_scores(make_workbook(tmp_path, []))


def test_corrupt_workbook_is_a_validation_error(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"not a zip")
    with pytest.raises(RubricValidationError, match="valid XLSX"):
        load_rubric_scores(path)


def test_unsupported_format_and_csv_sheet_are_rejected(tmp_path):
    with pytest.raises(RubricValidationError, match="formats"):
        load_rubric_scores(tmp_path / "scores.xls")
    with pytest.raises(RubricValidationError, match="only be used"):
        load_rubric_scores(tmp_path / "scores.csv", sheet="Scores")


def test_excel_cli_writes_json_without_network(tmp_path, socket_disabled):
    path = make_workbook(tmp_path, extra_sheet=True)
    output = tmp_path / "report.json"
    result = CliRunner().invoke(
        app,
        [
            "rubric",
            "compare",
            str(path),
            "--sheet",
            "Scores",
            "-o",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text(encoding="utf-8"))["model_b_score"] == 50


def test_invalid_excel_creates_no_output(tmp_path):
    path = make_workbook(tmp_path, [["001", "r1", "Accuracy", 1, 4, "=4", 2]])
    output = tmp_path / "report.json"
    result = CliRunner().invoke(
        app, ["rubric", "compare", str(path), "-o", str(output)]
    )
    assert result.exit_code == 2
    assert not output.exists()
