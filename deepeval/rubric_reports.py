"""Human-readable snapshots of validated rubric comparison results."""

from __future__ import annotations

import html
from pathlib import Path


def _markdown_cell(value):
    text = html.escape(str(value), quote=True)
    for character in ("\\", "`", "*", "_", "[", "]", "~"):
        text = text.replace(character, "\\" + character)
    return text.replace("|", "&#124;").replace("\r", " ").replace("\n", "<br>")


def write_markdown_report(report, output):
    """Write an escaped, portable report; numeric rounding is display only."""

    def table(headers, rows):
        lines = [
            "| " + " | ".join(map(_markdown_cell, headers)) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        lines.extend(
            "| " + " | ".join(map(_markdown_cell, row)) + " |" for row in rows
        )
        return "\n".join(lines)

    lines = [
        "# Rubric comparison",
        "",
        "Snapshot of supplied scores; no model judgments generated.",
        "",
        table(
            ["Metric", "Value"],
            [
                ("Model A", report["models"]["a"]),
                ("Model B", report["models"]["b"]),
                ("A score", f"{report['model_a_score']:.2f}"),
                ("B score", f"{report['model_b_score']:.2f}"),
                ("A minus B (pp)", f"{report['delta_percentage_points']:.2f}"),
                ("Winner", report["winner"]),
                ("Source", report["source"]),
                ("Method", report["method"]),
                (
                    "Manifest",
                    report.get("manifest_check", {}).get(
                        "status", "Not checked"
                    ),
                ),
                (
                    "Definition",
                    report.get("definition_check", {}).get(
                        "status", "Not checked"
                    ),
                ),
            ],
        ),
        "",
        "## Cases",
        "",
        table(
            ["Case", "Criteria", "A", "B", "A minus B (pp)", "Winner"],
            [
                (
                    c["case_id"],
                    c["criterion_count"],
                    f"{c['model_a_score']:.2f}",
                    f"{c['model_b_score']:.2f}",
                    f"{c['delta_percentage_points']:.2f}",
                    c["winner"],
                )
                for c in report["cases"]
            ],
        ),
        "",
        "Display rounded to two decimals. JSON retains calculation precision.",
        "",
    ]
    payload = "\n".join(lines).encode("utf-8")
    with Path(output).open("xb") as target:
        target.write(payload)
