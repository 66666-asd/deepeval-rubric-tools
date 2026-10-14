# Local rubric workflow commands

## Explicit source column mapping

`deepeval rubric import-csv external.csv mapping.json normalized.xlsx`

Mapping JSON maps each external header to a canonical header, for example
`{"ID":"case_id", ...}`. All required columns must appear exactly once;
only `notes` is optional. Extra source columns, duplicate mappings and missing
fields fail. No implicit column guessing, discarded data or score coercion.

## Case results for spreadsheet analysis

`deepeval rubric compare scores.csv --output cases.csv`

Exports one row per case, not a re-importable criterion score sheet. UTF-8 BOM
supports Excel. Formula-like text is prefixed with an apostrophe for safer
viewing; numerical results retain precision. Use JSON for unchanged identifiers.

## Standalone HTML report

`deepeval rubric compare scores.csv --output report.html`

Produces summary, case and criterion tables with escaped user content and a
restrictive content policy. No JavaScript, remote assets or external requests.
The file can be viewed offline; it is a result snapshot, not an editing UI.

## Markdown comparison reports

`deepeval rubric compare scores.csv --output report.md`

Produces an escaped summary and case table with source, scoring method and
completeness status. Display uses two decimals; JSON remains full precision.
User strings are not interpreted as HTML or Markdown links.

## Explicit candidate quality gate

`deepeval rubric check scores.csv --minimum-b 70 --maximum-regression 2`

Candidate B must meet the supplied minimum score and may trail A by no more
than the specified percentage points. Both thresholds are required (0-100).
Exit 0 passes, 1 fails a threshold, 2 is invalid data/configuration. Optional
`--manifest` verifies completeness. This is your policy, not an external gate.

## Describe case-level scores

`deepeval rubric describe scores.csv`

Reports mean, median, minimum, maximum and population standard deviation for
both models and paired deltas. Each case has equal weight, irrespective of
criterion count. A single case has zero population spread; no inference is made.

## Prioritize disagreements

`deepeval rubric review scores.csv --minimum-gap 20 --limit 50`

Ranks non-tied criteria by absolute normalized score gap (percentage points),
then case/criterion IDs. Returns total matches and truncated review items.
A large gap is a review priority, not evidence that either score is wrong.

## Audit score edits

`deepeval rubric diff before.csv after.csv`

Emits added/removed rows and field-level before/after values aligned on IDs.
Reordering alone is not a change. Both inputs must be valid completed scores.

## Reproducible review sample

`deepeval rubric sample scores.csv sample.csv --count 20 --seed review-2026`

Selects whole cases by SHA-256 ordering of seed and case ID, independent of
input order. Requires a positive count no greater than the population and an
explicit seed. This is a reproducible review subset, not statistical inference.

## Select complete cases

`deepeval rubric select scores.csv subset.csv --case 001 --case 002`

Preserves every criterion of requested cases and input ordering. Missing case
IDs fail, rather than silently producing a smaller sample. IDs remain text.

## Pair independently scored models

`deepeval rubric pair model-a.csv model-b.csv paired.xlsx`

Each input has `case_id,criterion_id,criterion,weight,max_score,score` and optional
`notes`. Keys and scoring definitions must match exactly; row order may differ.
A's order is retained. Notes are labeled A/B, with no overwriting or inferred scores.

## Merge score shards

`deepeval rubric merge shard1.csv shard2.xlsx --output merged.csv`

Requires two or more validated files with disjoint case/criterion keys. Even
identical duplicate rows are rejected. Source order is preserved; no partial
output is written when later shards are invalid. XLSX shards need one sheet.

These commands run on supplied human scores, not model answers. Install the
project and follow the offline environment setup in README.local.zh-CN.md.
All output paths must be new; no command rewrites source data.

## Validate scores without ranking

`deepeval rubric validate scores.csv --manifest expected.csv`

Accepts CSV/XLSX (use `--sheet` for multiple worksheets). Emits JSON counts,
exits 2 on invalid input. Without a manifest, completeness is not asserted.
No scores or model judgments are generated.

## Verify a scoring standard

`deepeval rubric compare scores.csv --definition definitions.csv`

Checks the exact key set, criterion wording, weight and maximum score against
an independently maintained definition CSV before comparison. Notes need not
match. Numeric equivalents (1 and 1.0) match; changed standards fail with exit 2.

## Convert score files

`deepeval rubric convert scores.csv scores.xlsx`

CSV/XLSX conversion validates every row first; XLSX IDs and text are literal.
Use `--sheet Scores` for multi-sheet inputs. Raw CSV is intended for program
interchange; use XLSX for formula-safe spreadsheet viewing. Existing files fail.
