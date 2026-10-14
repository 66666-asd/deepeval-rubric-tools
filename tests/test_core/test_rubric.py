"""Tests for the downstream offline rubric comparison feature."""

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deepeval.cli.main import app
from deepeval.rubric import (
    REQUIRED_COLUMNS,
    RubricValidationError,
    compare_rubric_csv,
    load_rubric_csv,
)


def make_csv(tmp_path, rows=None, columns=None, encoding="utf-8"):
    path = tmp_path / "scores.csv"
    if rows is None:
        rows = [["q1", "r1", "Accuracy", 3, 4, 4, 2]]
    with path.open("w", encoding=encoding, newline="") as target:
        writer = csv.writer(target)
        writer.writerow(columns or REQUIRED_COLUMNS)
        writer.writerows(rows)
    return path


def test_weighted_normalization_and_macro_mean(tmp_path):
    path = make_csv(
        tmp_path,
        [
            ["q1", "r1", "Accuracy", 3, 4, 4, 2],
            ["q1", "r2", "Evidence", 1, 2, 1, 2],
            ["q2", "r1", "Coverage", 1, 5, 3, 4],
            ["q2", "r2", "Clarity", 1, 2, 2, 1],
        ],
    )
    report = compare_rubric_csv(path, "baseline", "candidate")
    assert report["model_a_score"] == pytest.approx(83.75)
    assert report["model_b_score"] == pytest.approx(63.75)
    assert report["delta_percentage_points"] == pytest.approx(20)
    assert report["case_wins"] == {"baseline": 2, "candidate": 0, "tie": 0}
    assert report["cases"][0]["model_a_score"] == pytest.approx(87.5)
    assert report["cases"][1]["model_a_score"] == pytest.approx(80)
    assert report["cases"][0]["criteria"][0]["model_a_contribution"] == 75
    assert report["cases"][0]["criteria"][1]["winner"] == "candidate"


def test_cases_are_equally_weighted_regardless_of_size(tmp_path):
    path = make_csv(
        tmp_path,
        [
            ["q1", "r1", "First", 100, 1, 1, 0],
            ["q1", "r2", "Second", 100, 1, 1, 0],
            ["q2", "r1", "Third", 1, 1, 0, 1],
        ],
    )
    report = compare_rubric_csv(path)
    assert report["model_a_score"] == report["model_b_score"] == 50
    assert report["winner"] == "tie"


@pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-inf", "1e999", "x"])
@pytest.mark.parametrize("index", [3, 4, 5, 6])
def test_reject_nonfinite_or_nonnumeric_scores(tmp_path, index, value):
    row = ["q1", "r1", "Accuracy", 3, 4, 4, 2]
    row[index] = value
    with pytest.raises(RubricValidationError, match="Line 2"):
        load_rubric_csv(make_csv(tmp_path, [row]))


@pytest.mark.parametrize("index", range(7))
def test_required_values_cannot_be_blank(tmp_path, index):
    row = ["q1", "r1", "Accuracy", 3, 4, 4, 2]
    row[index] = " "
    with pytest.raises(RubricValidationError, match="required"):
        load_rubric_csv(make_csv(tmp_path, [row]))


@pytest.mark.parametrize(
    "index,value", [(3, 0), (3, -1), (4, 0), (4, -1), (5, -1), (6, 5)]
)
def test_reject_invalid_numeric_ranges(tmp_path, index, value):
    row = ["q1", "r1", "Accuracy", 3, 4, 4, 2]
    row[index] = value
    with pytest.raises(RubricValidationError):
        load_rubric_csv(make_csv(tmp_path, [row]))


def test_duplicate_composite_keys_are_rejected(tmp_path):
    path = make_csv(
        tmp_path,
        [
            ["q1", "r1", "Accuracy", 1, 1, 1, 0],
            [" q1 ", "r1", "Accuracy", 1, 1, 0, 1],
        ],
    )
    with pytest.raises(RubricValidationError, match="duplicate"):
        load_rubric_csv(path)


@pytest.mark.parametrize("row", [[], ["q1"], ["q1"] * 8])
def test_empty_or_ragged_csv_is_rejected(tmp_path, row):
    with pytest.raises(RubricValidationError):
        load_rubric_csv(make_csv(tmp_path, [row]))


@pytest.mark.parametrize(
    "columns",
    [
        list(REQUIRED_COLUMNS) + ["case_id"],
        list(REQUIRED_COLUMNS) + ["typo_column"],
        list(REQUIRED_COLUMNS)[:-1],
    ],
)
def test_invalid_headers_are_rejected(tmp_path, columns):
    with pytest.raises(RubricValidationError):
        load_rubric_csv(make_csv(tmp_path, columns=columns))


@pytest.mark.parametrize("content", ["", "\n", ",,,", 'case_id\n"unclosed'])
def test_invalid_csv_content_is_rejected(tmp_path, content):
    path = tmp_path / "invalid.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(RubricValidationError):
        load_rubric_csv(path)


def test_invalid_encoding_is_rejected(tmp_path):
    path = tmp_path / "invalid.csv"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(RubricValidationError, match="UTF-8"):
        load_rubric_csv(path)


def test_bom_unicode_quoted_newlines_and_notes(tmp_path):
    text = "\u51c6\u786e\u6027, \u8bc1\u636e\nsecond line"
    path = make_csv(
        tmp_path,
        [["q1", "r1", text, 1, 1, 1, 1, "reviewed"]],
        columns=list(REQUIRED_COLUMNS) + ["notes"],
        encoding="utf-8-sig",
    )
    report = compare_rubric_csv(path)
    detail = report["cases"][0]["criteria"][0]
    assert detail["criterion"] == text
    assert detail["notes"] == "reviewed"
    assert report["case_wins"]["tie"] == 1


@pytest.mark.parametrize("names", [("", "B"), ("A", "A"), ("tie", "B")])
def test_model_labels_must_be_unambiguous(tmp_path, names):
    with pytest.raises(RubricValidationError, match="Model names"):
        compare_rubric_csv(make_csv(tmp_path), *names)


def test_extreme_finite_weights_do_not_overflow(tmp_path):
    path = make_csv(
        tmp_path,
        [
            ["q1", "r1", "First", "1e308", 1, 1, 0],
            ["q1", "r2", "Second", "1e308", 1, 0, 1],
        ],
    )
    report = compare_rubric_csv(path)
    assert report["model_a_score"] == report["model_b_score"] == 50
    json.dumps(report, allow_nan=False)


def test_cli_runs_without_network_and_emits_json(tmp_path, socket_disabled):
    path = make_csv(tmp_path)
    result = CliRunner().invoke(app, ["rubric", "compare", str(path)])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["winner"] == "model_a"
    assert report["model_a_score"] == 100


def test_cli_writes_report(tmp_path):
    source = make_csv(tmp_path)
    output = tmp_path / "report.json"
    result = CliRunner().invoke(
        app,
        ["rubric", "compare", str(source), "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text(encoding="utf-8"))["case_count"] == 1


def test_cli_does_not_overwrite_existing_output(tmp_path):
    source = make_csv(tmp_path)
    output = tmp_path / "report.json"
    output.write_text("keep me", encoding="utf-8")
    result = CliRunner().invoke(
        app, ["rubric", "compare", str(source), "-o", str(output)]
    )
    assert result.exit_code == 2
    assert output.read_text(encoding="utf-8") == "keep me"


def test_cli_does_not_overwrite_input(tmp_path):
    source = make_csv(tmp_path)
    before = source.read_bytes()
    result = CliRunner().invoke(
        app, ["rubric", "compare", str(source), "-o", str(source)]
    )
    assert result.exit_code == 2
    assert source.read_bytes() == before


def test_cli_invalid_input_leaves_no_output(tmp_path):
    source = make_csv(tmp_path, [["q1", "r1", "Accuracy", 1, 1, "", 0]])
    output = tmp_path / "report.json"
    result = CliRunner().invoke(
        app, ["rubric", "compare", str(source), "-o", str(output)]
    )
    assert result.exit_code == 2
    assert "required" in result.output
    assert not output.exists()


def test_cli_missing_file_is_a_friendly_error(tmp_path):
    result = CliRunner().invoke(
        app, ["rubric", "compare", str(tmp_path / "missing.csv")]
    )
    assert result.exit_code == 2
    assert "Rubric comparison failed" in result.output


def test_bundled_example_has_expected_result():
    source = Path(__file__).resolve().parents[2] / "examples"
    report = compare_rubric_csv(source / "rubric" / "paired_scores.csv")
    assert report["case_count"] == 2
    assert report["criterion_count"] == 4
    assert report["delta_percentage_points"] == 20


def test_cli_cold_start_is_offline_and_stdout_is_json(tmp_path):
    source = make_csv(tmp_path)
    environment = os.environ.copy()
    environment.update(
        DEEPEVAL_TELEMETRY_OPT_OUT="1",
        DEEPEVAL_DISABLE_DOTENV="1",
        DEEPEVAL_UPDATE_WARNING_OPT_IN="0",
        DEEPEVAL_FILE_SYSTEM="READ_ONLY",
        CONFIDENT_OPEN_BROWSER="0",
        PYTHONUTF8="1",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import pytest_socket; pytest_socket.disable_socket(); "
                "from deepeval.cli.main import app; app()"
            ),
            "rubric",
            "compare",
            str(source),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["model_a_score"] == 100
    assert "read only environment" in result.stderr
    assert not (tmp_path / ".deepeval" / ".deepeval").exists()
