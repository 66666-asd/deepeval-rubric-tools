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


def test_case_sampling_is_reproducible_and_keeps_criteria(scores, tmp_path):
    from deepeval.rubric_ops import sample_cases, write_score_rows

    one, two = tmp_path / "one.csv", tmp_path / "two.csv"
    reordered = tmp_path / "reordered.csv"
    rows = load_rubric_scores(scores)
    write_score_rows(list(reversed(rows)), reordered)
    keys = sample_cases(scores, 1, "review-2026", one)
    assert sample_cases(reordered, 1, "review-2026", two) == keys
    assert load_rubric_scores(one) == [
        row for row in rows if row.case_id in keys
    ]
    for invalid in (0, -1, 3, True, 1.5):
        with pytest.raises(RubricValidationError):
            sample_cases(scores, invalid, "seed", tmp_path / "bad.csv")
    result = CliRunner().invoke(
        app,
        [
            "rubric",
            "sample",
            str(scores),
            str(tmp_path / "all.csv"),
            "--count",
            "2",
            "--seed",
            "test",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["selected_cases"] == ["001", "002"]


def test_score_diff_aligns_keys_and_reports_actual_fields(scores, tmp_path):
    from dataclasses import replace

    from deepeval.rubric_ops import write_score_rows
    from deepeval.rubric_review import diff_scores

    rows = load_rubric_scores(scores)
    output = tmp_path / "edited.csv"
    write_score_rows(
        [
            rows[2],
            replace(rows[0], model_a_score=3, notes="rechecked"),
            replace(rows[1], case_id="new"),
        ],
        output,
    )
    result = diff_scores(scores, output)
    assert (
        len(result["added"])
        == len(result["removed"])
        == len(result["changed"])
        == 1
    )
    assert result["unchanged_count"] == 1
    assert result["changed"][0]["fields"]["model_a_score"] == {
        "before": 4,
        "after": 3,
    }
    cli = CliRunner().invoke(app, ["rubric", "diff", str(scores), str(output)])
    assert cli.exit_code == 0, cli.output
    assert json.loads(cli.stdout) == result


def test_review_queue_ranks_normalized_gaps(scores):
    from deepeval.rubric_review import review_queue

    result = review_queue(scores, minimum_gap=40, limit=1)
    assert result["matching_count"] == 2
    assert result["shown_count"] == 1
    assert result["items"][0]["criterion_id"] == "r1"
    assert result["items"][0]["absolute_gap"] == 50
    assert review_queue(scores, minimum_gap=100)["items"] == []
    for gap in (-1, float("nan"), float("inf"), 101):
        with pytest.raises(RubricValidationError):
            review_queue(scores, minimum_gap=gap)
    cli = CliRunner().invoke(
        app, ["rubric", "review", str(scores), "--limit", "0"]
    )
    assert cli.exit_code == 2


def test_descriptive_statistics_use_case_not_criterion_weights(
    scores, tmp_path
):
    from deepeval.rubric_review import describe_scores

    result = describe_scores(scores)
    assert result["model_a"]["mean"] == 73.75
    assert result["model_a"]["median"] == 73.75
    assert result["model_a"]["population_stddev"] == 13.75
    assert result["model_b"]["mean"] == 71.25
    single = make_csv(tmp_path / "one.csv", [["a", "r", "A", 1, 1, 1, 0, ""]])
    assert describe_scores(single)["delta"]["population_stddev"] == 0
    cli = CliRunner().invoke(app, ["rubric", "describe", str(scores)])
    assert cli.exit_code == 0, cli.output
    assert json.loads(cli.stdout) == result


@pytest.mark.parametrize(
    "minimum,regression,exit_code",
    [(71.25, 2.5, 0), (72, 3, 1), (70, 2, 1), (101, 2, 2), (70, -1, 2)],
)
def test_quality_gate_boundaries_and_exit_codes(
    scores, minimum, regression, exit_code
):
    result = CliRunner().invoke(
        app,
        [
            "rubric",
            "check",
            str(scores),
            "--minimum-b",
            str(minimum),
            "--maximum-regression",
            str(regression),
        ],
    )
    assert result.exit_code == exit_code, result.output
    if exit_code != 2:
        payload = json.loads(result.stdout)
        assert payload["passed"] is (exit_code == 0)
        assert payload["completeness"] == "not_checked"


def test_markdown_report_escapes_user_content_and_protects_output(
    scores, tmp_path
):
    from deepeval.rubric_reports import write_markdown_report

    report = compare_rubric_file(
        scores, model_a="<script>|[click](url)\nsecond"
    )
    output = tmp_path / "report.md"
    write_markdown_report(report, output)
    text = output.read_text(encoding="utf-8")
    assert "<script>" not in text
    assert "&lt;script&gt;&#124;" in text
    assert "73.75" in text and "001" in text
    with pytest.raises(FileExistsError):
        write_markdown_report(report, output)
    cli = CliRunner().invoke(
        app, ["rubric", "compare", str(scores), "-o", str(tmp_path / "cli.md")]
    )
    assert cli.exit_code == 0, cli.output


def test_html_report_contains_no_user_markup(scores, tmp_path):
    from html.parser import HTMLParser

    from deepeval.rubric_reports import write_html_report

    report = compare_rubric_file(
        scores, model_a='<img src=x onerror="alert(1)">'
    )
    report["cases"][0]["criteria"][0]["notes"] = (
        "</td><script>alert(1)</script>"
    )
    output = tmp_path / "report.html"
    write_html_report(report, output)
    text = output.read_text(encoding="utf-8")

    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)

    parser = Tags()
    parser.feed(text)
    assert "script" not in parser.tags and "img" not in parser.tags
    assert parser.tags.count("table") == 3
    assert "Content-Security-Policy" in text
    with pytest.raises(FileExistsError):
        write_html_report(report, output)
    result = CliRunner().invoke(
        app,
        ["rubric", "compare", str(scores), "-o", str(tmp_path / "cli.html")],
    )
    assert result.exit_code == 0, result.output


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
