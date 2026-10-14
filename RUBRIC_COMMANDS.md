# Local rubric workflow commands

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
