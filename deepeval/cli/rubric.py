"""CLI for comparing supplied rubric scores; no judge or upload required."""

# ruff: noqa: FA100 -- Typer resolves runtime Optional types on Python 3.9.

import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from deepeval.rubric import RubricValidationError, compare_rubric_file
from deepeval.rubric_excel import (
    write_rubric_excel_report,
    write_rubric_excel_template,
)
from deepeval.rubric_ops import convert_scores, validate_score_file

app = typer.Typer(help="Validate and compare existing rubric scores locally.")


@app.command("check")
def check_command(
    source: Path,
    minimum_b: Annotated[float, typer.Option("--minimum-b")],
    maximum_regression: Annotated[float, typer.Option("--maximum-regression")],
    manifest: Optional[Path] = None,
    sheet: Optional[str] = None,
):
    """Check explicit thresholds for candidate B; exit 1 when a gate fails."""
    from deepeval.rubric_review import check_quality_gate

    try:
        result = check_quality_gate(
            source,
            minimum_b=minimum_b,
            maximum_regression=maximum_regression,
            manifest=manifest,
            sheet=sheet,
        )
        typer.echo(json.dumps(result, allow_nan=False))
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Quality check failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not result["passed"]:
        raise typer.Exit(1)


@app.command("describe")
def describe_command(source: Path, sheet: Optional[str] = None):
    """Describe the distribution of case-level scores and paired deltas."""
    from deepeval.rubric_review import describe_scores

    try:
        typer.echo(
            json.dumps(describe_scores(source, sheet=sheet), allow_nan=False)
        )
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Description failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("review")
def review_command(
    source: Path,
    minimum_gap: float = 0.0,
    limit: int = 20,
    sheet: Optional[str] = None,
):
    """Prioritize criteria with the largest normalized model score gaps."""
    from deepeval.rubric_review import review_queue

    try:
        result = review_queue(
            source, minimum_gap=minimum_gap, limit=limit, sheet=sheet
        )
        typer.echo(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Review queue failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("diff")
def diff_command(before: Path, after: Path):
    """Show key-aligned changes between validated score files as JSON."""
    from deepeval.rubric_review import diff_scores

    try:
        typer.echo(
            json.dumps(
                diff_scores(before, after), ensure_ascii=False, allow_nan=False
            )
        )
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Score diff failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("sample")
def sample_command(
    source: Path,
    output: Path,
    count: Annotated[int, typer.Option("--count")],
    seed: Annotated[str, typer.Option("--seed")],
    sheet: Optional[str] = None,
):
    """Sample complete cases reproducibly using an explicit seed."""
    from deepeval.rubric_ops import sample_cases

    try:
        keys = sample_cases(source, count, seed, output, sheet=sheet)
        typer.echo(json.dumps({"selected_cases": keys, "seed": seed}))
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Sampling failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("select")
def select_command(
    source: Path,
    output: Path,
    case: Annotated[list[str], typer.Option("--case")],
    sheet: Optional[str] = None,
):
    """Select whole cases, preserving every criterion in each chosen case."""
    from deepeval.rubric_ops import select_cases

    try:
        count = select_cases(source, case, output, sheet=sheet)
        typer.echo(f"Selected {count} criterion rows to {output}")
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Case selection failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("pair")
def pair_command(model_a: Path, model_b: Path, output: Path):
    """Pair two single-model CSV score files by case and criterion IDs."""
    from deepeval.rubric_ops import pair_scores

    try:
        count = pair_scores(model_a, model_b, output)
        typer.echo(f"Paired {count} criteria to {output}")
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Pairing failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("merge")
def merge_command(
    sources: list[Path], output: Annotated[Path, typer.Option("--output", "-o")]
):
    """Merge disjoint single-sheet score files, rejecting duplicate keys."""
    from deepeval.rubric_ops import merge_scores

    try:
        count = merge_scores(sources, output)
        typer.echo(f"Merged {count} rows to {output}")
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Merge failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("convert")
def convert_command(source: Path, output: Path, sheet: Optional[str] = None):
    """Convert validated scores between CSV and XLSX without rescoring."""
    try:
        count = convert_scores(source, output, sheet=sheet)
        typer.echo(f"Wrote {count} score rows to {output}")
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Score conversion failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc


@app.command("validate")
def validate_command(
    scores: Path,
    sheet: Optional[str] = None,
    manifest: Optional[Path] = None,
):
    """Check scores and optional expected keys without producing rankings."""
    try:
        result = validate_score_file(scores, sheet=sheet, manifest=manifest)
        typer.echo(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Rubric validation failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc


@app.command("compare")
def compare_command(
    scores: Annotated[
        Path, typer.Argument(help="UTF-8 CSV or XLSX with paired scores.")
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Write JSON or XLSX to a new file; infer format from extension.",
        ),
    ] = None,
    model_a: Annotated[
        str, typer.Option(help="Name of the first model.")
    ] = "model_a",
    model_b: Annotated[
        str, typer.Option(help="Name of the second model.")
    ] = "model_b",
    sheet: Annotated[
        Optional[str],
        typer.Option(
            help="Excel worksheet name; required for multiple sheets."
        ),
    ] = None,
    definition: Optional[Path] = None,
    manifest: Annotated[
        Optional[Path],
        typer.Option(
            help="Independent CSV of every expected case_id/criterion_id."
        ),
    ] = None,
):
    """Check every row, then report per-case scores and an overall comparison.

    An output file must not already exist. No partial report is emitted for
    invalid input. Set DEEPEVAL_TELEMETRY_OPT_OUT=1 before invoking DeepEval
    to disable the upstream CLI's telemetry.
    """
    try:
        if output is not None and output.suffix.lower() not in (
            ".json",
            ".xlsx",
            ".md",
        ):
            raise RubricValidationError(
                "Output must end in .json, .xlsx or .md."
            )
        if output is not None and output.resolve() == scores.resolve():
            raise RubricValidationError("Output must not replace the input.")
        if (
            output is not None
            and manifest is not None
            and output.resolve() == manifest.resolve()
        ):
            raise RubricValidationError("Output must not replace the manifest.")
        report = compare_rubric_file(
            scores,
            model_a,
            model_b,
            sheet=sheet,
            manifest=manifest,
            definition=definition,
        )
        if output is not None and output.suffix.lower() == ".xlsx":
            write_rubric_excel_report(report, output)
        elif output is not None and output.suffix.lower() == ".md":
            from deepeval.rubric_reports import write_markdown_report

            write_markdown_report(report, output)
        else:
            payload = json.dumps(
                report, ensure_ascii=False, indent=2, allow_nan=False
            )
            if output is None:
                typer.echo(payload)
            else:
                with output.open("x", encoding="utf-8", newline="\n") as target:
                    target.write(payload + "\n")
        if output is not None:
            typer.echo(f"Report written to {output}")
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Rubric comparison failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc


@app.command("template")
def template_command(
    definition: Annotated[
        Path,
        typer.Argument(help="UTF-8 CSV rubric definitions without scores."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="New XLSX scoring template path."),
    ],
):
    """Create a Scores sheet with blank model scores, plus instructions."""
    try:
        count = write_rubric_excel_template(definition, output)
        typer.echo(
            f"Blank scoring template written to {output} ({count} criteria)"
        )
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Rubric template failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
