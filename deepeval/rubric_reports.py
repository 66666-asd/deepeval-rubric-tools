"""Human-readable snapshots of validated rubric comparison results."""

from __future__ import annotations

import html

from deepeval.rubric_io import write_new_bytes


def write_html_report(report, output):
    """Write escaped offline tables without scripts or external resources."""

    def table(headers, rows):
        head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
        body = "".join(
            "<tr>"
            + "".join(f"<td>{html.escape(str(c))}</td>" for c in row)
            + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    summary = table(
        ["Metric", "Value"],
        [
            ("Model A", report["models"]["a"]),
            ("Model B", report["models"]["b"]),
            ("A score", f"{report['model_a_score']:.2f}"),
            ("B score", f"{report['model_b_score']:.2f}"),
            ("Winner", report["winner"]),
            ("Source", report["source"]),
            ("Method", report["method"]),
            (
                "Manifest",
                report.get("manifest_check", {}).get("status", "Not checked"),
            ),
            (
                "Definition",
                report.get("definition_check", {}).get("status", "Not checked"),
            ),
        ],
    )
    cases = table(
        ["Case", "A", "B", "A minus B (pp)"],
        [
            (
                c["case_id"],
                f"{c['model_a_score']:.2f}",
                f"{c['model_b_score']:.2f}",
                f"{c['delta_percentage_points']:.2f}",
            )
            for c in report["cases"]
        ],
    )
    criteria = table(
        [
            "Case",
            "Criterion",
            "Description",
            "Weight",
            "Maximum",
            "A",
            "B",
            "Notes",
        ],
        [
            (
                case["case_id"],
                c["criterion_id"],
                c["criterion"],
                c["weight"],
                c["max_score"],
                c["model_a_score"],
                c["model_b_score"],
                c["notes"],
            )
            for case in report["cases"]
            for c in case["criteria"]
        ],
    )
    payload = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>Rubric comparison</title><style>body{font:16px system-ui;margin:24px;color:#222;background:#fff}"
        "table{border-collapse:collapse;width:100%;margin-bottom:24px}th,td{padding:8px;border:1px solid #ccc;text-align:left;overflow-wrap:anywhere;white-space:pre-wrap}"
        "th{background:#eee}h1{font-size:24px}h2{font-size:20px}</style></head><body>"
        "<h1>Rubric comparison</h1><p>Snapshot of supplied human scores. No automated judgments or significance claims.</p>"
        + summary
        + "<h2>Cases</h2>"
        + cases
        + "<h2>Criteria</h2>"
        + criteria
        + "<p>Summary display rounded to two decimals. JSON retains calculation precision.</p></body></html>"
    ).encode("utf-8")
    write_new_bytes(output, payload)


def write_case_csv(report, output):
    """Export case-level results with spreadsheet-safe text cells."""
    import csv
    from io import StringIO

    fields = (
        "case_id",
        "criterion_count",
        "model_a_score",
        "model_b_score",
        "delta_percentage_points",
        "winner",
    )

    def safe(value):
        if isinstance(value, str) and value.lstrip().startswith(
            ("=", "+", "-", "@")
        ):
            return "'" + value
        return value

    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(fields)
    for case in report["cases"]:
        writer.writerow([safe(case[field]) for field in fields])
    payload = buffer.getvalue().encode("utf-8-sig")
    write_new_bytes(output, payload)


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
    write_new_bytes(output, payload)
