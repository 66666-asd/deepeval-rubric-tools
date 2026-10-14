"""CLI for comparing supplied rubric scores; no judge or upload required."""

import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from deepeval.rubric import RubricValidationError, compare_rubric_csv

app = typer.Typer(help="Validate and compare existing rubric scores locally.")


@app.command("compare")
def compare_command(
    scores: Annotated[
        Path, typer.Argument(help="UTF-8 CSV with paired scores.")
    ],
    output: Annotated[
        Optional[Path],  # noqa: FA100 - Typer evaluates types on Python 3.9.
        typer.Option(
            "--output", "-o", help="Write JSON to a new file instead of stdout."
        ),
    ] = None,
    model_a: Annotated[
        str, typer.Option(help="Name of the first model.")
    ] = "model_a",
    model_b: Annotated[
        str, typer.Option(help="Name of the second model.")
    ] = "model_b",
):
    """Check every row, then report per-case scores and an overall comparison.

    An output file must not already exist. No partial report is emitted for
    invalid input. Set DEEPEVAL_TELEMETRY_OPT_OUT=1 before invoking DeepEval
    to disable the upstream CLI's telemetry.
    """
    try:
        if output is not None and output.resolve() == scores.resolve():
            raise RubricValidationError("Output must not replace the input.")
        report = compare_rubric_csv(scores, model_a, model_b)
        payload = json.dumps(
            report, ensure_ascii=False, indent=2, allow_nan=False
        )
        if output is None:
            typer.echo(payload)
        else:
            with output.open("x", encoding="utf-8", newline="\n") as target:
                target.write(payload + "\n")
            typer.echo(f"Report written to {output}")
    except (RubricValidationError, OSError) as exc:
        typer.echo(f"Rubric comparison failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
