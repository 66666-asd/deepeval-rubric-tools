"""Downstream Excel reports and blank scoring templates."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from deepeval.rubric import (
    REQUIRED_COLUMNS,
    RubricValidationError,
    load_rubric_template_csv,
)
from deepeval.rubric_io import write_new_bytes

_INVALID_XML_TEXT = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]"
)
_MAX_EXCEL_ROWS = 1048576


def _new_workbook():
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RubricValidationError(
            "Excel output is optional. Install requirements-rubric-excel.txt."
        ) from exc
    return Workbook()


def _append_literals(sheet, values):
    """Write user strings as literal text, never executable Excel formulas."""
    if sheet.max_row >= _MAX_EXCEL_ROWS:
        raise RubricValidationError("Report exceeds the Excel row limit.")
    for value in values:
        if isinstance(value, str):
            if _INVALID_XML_TEXT.search(value):
                raise RubricValidationError(
                    "Report text contains characters not supported by Excel."
                )
            if len(value.encode("utf-16-le")) // 2 > 32767:
                raise RubricValidationError(
                    "Report text exceeds the Excel cell limit (32767 units)."
                )
    sheet.append(values)
    for cell in sheet[sheet.max_row]:
        if isinstance(cell.value, str):
            cell.data_type = "s"


def _style_sheet(sheet, widths, numeric_columns=(), filtered=True):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    edge = Side(style="thin", color="D0D5DD")
    for cell in sheet[1]:
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1D2330")
        cell.border = Border(bottom=edge)
    sheet.row_dimensions[1].height = 24
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Calibri", size=11, color="222222")
            cell.alignment = Alignment(
                vertical="top",
                horizontal="right"
                if cell.column in numeric_columns
                else "left",
            )
            if cell.column in numeric_columns and isinstance(
                cell.value, (int, float)
            ):
                cell.number_format = "0.00"
    if filtered:
        sheet.auto_filter.ref = sheet.dimensions


def _save_new_workbook(workbook, output):
    """Serialize first; exclusive create never overwrites an existing file."""
    output = Path(output)
    if output.suffix.lower() != ".xlsx":
        raise RubricValidationError("Excel output path must end in .xlsx.")
    buffer = BytesIO()
    try:
        workbook.save(buffer)
        write_new_bytes(output, buffer.getvalue())
    finally:
        buffer.close()
        workbook.close()


def write_rubric_excel_report(report, output):
    """Export a snapshot of validated scores without changing their precision.

    These are result values, not spreadsheet calculations. The input data and
    JSON calculation retain full precision; two decimals are display-only.
    """
    workbook = _new_workbook()
    try:
        summary = workbook.active
        summary.title = "Summary"
        _append_literals(summary, ["Metric", "Value"])
        summary_rows = [
            ("Model A", report["models"]["a"]),
            ("Model B", report["models"]["b"]),
            ("Model A score (0-100)", report["model_a_score"]),
            ("Model B score (0-100)", report["model_b_score"]),
            (
                "A minus B (percentage points)",
                report["delta_percentage_points"],
            ),
            ("Winner", report["winner"]),
            ("Cases", report["case_count"]),
            ("Criteria", report["criterion_count"]),
            ("Method", report["method"]),
            ("Source", report["source"]),
            ("Source worksheet", report.get("source_sheet", "Not specified")),
            ("Schema version", report["schema_version"]),
            (
                "Tie tolerance (percentage points)",
                report["tie_tolerance_percentage_points"],
            ),
        ]
        manifest = report.get("manifest_check")
        summary_rows.append(
            (
                "Manifest check",
                "Not requested" if manifest is None else manifest["status"],
            )
        )
        if manifest is not None:
            summary_rows.extend(
                [
                    ("Manifest source", manifest["source"]),
                    ("Expected criteria", manifest["expected_criterion_count"]),
                    ("Matched criteria", manifest["matched_criterion_count"]),
                ]
            )
        for row in summary_rows:
            _append_literals(summary, row)
        _style_sheet(summary, [38, 100], filtered=False)
        for row in (4, 5, 6):
            summary.cell(row, 2).number_format = "0.00"

        cases = workbook.create_sheet("Cases")
        _append_literals(
            cases,
            [
                "case_id",
                "criterion_count",
                "model_a_score",
                "model_b_score",
                "delta_percentage_points",
                "winner",
            ],
        )
        criteria = workbook.create_sheet("Criteria")
        fields = (
            "criterion_id",
            "criterion",
            "weight",
            "weight_share",
            "max_score",
            "model_a_score",
            "model_b_score",
            "model_a_contribution",
            "model_b_contribution",
            "delta_percentage_points",
            "winner",
            "notes",
        )
        _append_literals(criteria, ["case_id", *fields])
        for case in report["cases"]:
            _append_literals(
                cases,
                [
                    case["case_id"],
                    case["criterion_count"],
                    case["model_a_score"],
                    case["model_b_score"],
                    case["delta_percentage_points"],
                    case["winner"],
                ],
            )
            for criterion in case["criteria"]:
                _append_literals(
                    criteria,
                    [case["case_id"], *(criterion[field] for field in fields)],
                )
        _style_sheet(cases, [22, 18, 22, 22, 28, 26], numeric_columns=(3, 4, 5))
        _style_sheet(
            criteria,
            [22, 22, 55, 16, 18, 16, 20, 20, 24, 24, 28, 26, 65],
            numeric_columns=range(4, 12),
        )
        for row in criteria.iter_rows(min_row=2):
            row[4].number_format = "0.0%"
        _save_new_workbook(workbook, output)
    finally:
        workbook.close()


def write_rubric_excel_template(definition, output):
    """Build a blank score workbook from a validated independent definition.

    Excel validation is an editing aid only. The importer still checks every
    score because pasted values can bypass spreadsheet validation.
    """
    rows = load_rubric_template_csv(definition)
    workbook = _new_workbook()
    try:
        from openpyxl.styles import Font, PatternFill
        from openpyxl.worksheet.datavalidation import DataValidation

        scores = workbook.active
        scores.title = "Scores"
        _append_literals(scores, [*REQUIRED_COLUMNS, "notes"])
        for row in rows:
            _append_literals(
                scores,
                [
                    row["case_id"],
                    row["criterion_id"],
                    row["criterion"],
                    row["weight"],
                    row["max_score"],
                    None,
                    None,
                    row["notes"],
                ],
            )
        _style_sheet(
            scores,
            [22, 22, 65, 16, 16, 20, 20, 65],
            numeric_columns=(4, 5, 6, 7),
        )
        for row in scores.iter_rows(min_row=2):
            for index in (0, 1, 2, 7):
                row[index].number_format = "@"
            for cell in row[5:7]:
                cell.font = Font(name="Calibri", size=11, color="0070C0")
                cell.fill = PatternFill("solid", fgColor="E8F1FC")
                cell.number_format = "0.00"
        validation = DataValidation(
            type="decimal",
            operator="between",
            formula1="0",
            formula2="$E2",
            allow_blank=True,
            showErrorMessage=True,
            showInputMessage=True,
            errorStyle="stop",
            errorTitle="Invalid score",
            error="Enter a number from zero to this row's max_score.",
            promptTitle="Human score required",
            prompt="Fill both model scores before comparing. Blank is not zero.",
        )
        scores.add_data_validation(validation)
        validation.add(f"F2:G{len(rows) + 1}")

        guidance = workbook.create_sheet("Instructions")
        _append_literals(guidance, ["Item", "Guidance"])
        for row in (
            (
                "Status",
                "Blank template; no model evaluation has been performed.",
            ),
            ("Definition source", str(Path(definition))),
            ("Criteria", len(rows)),
            (
                "Scores",
                "Fill model_a_score and model_b_score on the Scores sheet.",
            ),
            (
                "Range",
                "Each score must be a number from 0 to that row's max_score.",
            ),
            (
                "Missing scores",
                "Leave unreviewed scores blank; comparison rejects blanks.",
            ),
            (
                "Identifiers",
                "Keep case_id and criterion_id as text to preserve leading zeros.",
            ),
            (
                "Definitions",
                "Keep the supplied criterion, weight and max_score unchanged.",
            ),
            ("Import", 'deepeval rubric compare "filled.xlsx" --sheet Scores'),
            (
                "Completeness",
                "Use --manifest with an independent complete key inventory.",
            ),
            (
                "Validation",
                "Excel validation is an aid; pasted values are rechecked on import.",
            ),
            (
                "Formulas",
                "Enter values only. Formula cells are rejected by the importer.",
            ),
        ):
            _append_literals(guidance, row)
        _style_sheet(guidance, [24, 100], filtered=False)
        _save_new_workbook(workbook, output)
    finally:
        workbook.close()
    return len(rows)
