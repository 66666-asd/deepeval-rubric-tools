# Source provenance and downstream changes

- Upstream repository: https://github.com/confident-ai/deepeval
- License: Apache-2.0; the upstream LICENSE.md is retained unchanged.
- Source commit: 016946f6d770f8bc4e2f63f665140aea527d6641
- Upstream commit timestamp: 2026-10-12T19:31:54Z
- Acquisition date: 2026-10-14 (Asia/Shanghai).
- Acquisition: GitHub codeload ZIP of the exact commit. Two Git clone
  attempts failed with connection resets. This directory is a source
  snapshot, NOT a clone with complete Git history.
- ZIP SHA-256: CFB02D3EC85C5E207A533B367DEB2F130F2800E7956FDEC369D1AF257DF7936C

## Downstream scope

Add a local CSV rubric-score comparison engine, expose it as
`deepeval rubric compare`, and provide tests, synthetic example data, and
Chinese usage instructions. Scores are supplied by the user: this feature
does not generate judgments or contact a paid model.

The read-only initialization warning in `deepeval/test_run/test_run.py`
now goes to stderr, so JSON command output stays machine-readable.

This is a derivative of a PUBLIC repository. It is not eligible for a
collection requiring a never-public repository and the submitter's own
historical development. No commit history has been fabricated, imported
as personal work, or rewritten. No platform upload or authorization was
performed.

The original authors retain their attribution. Locally edited upstream
files contain a downstream change notice; new modules are local additions.

## GitHub publication preparation - 2026-10-14

- Destination: https://github.com/66666-asd/deepeval-rubric-tools
- Start a new, honest Git history for this attributed source snapshot and
  downstream work; no claim is made to upstream authorship or Git history.
- The root README identifies this repository as an unofficial derivative.
- `.gitignore` excludes local environments, caches, credential files, upstream
  generated voice recordings, and upstream GitHub Actions workflows. These
  workflows include release/deployment jobs unsuitable for this derivative.
  Excluded upstream files remain in the local downloaded snapshot.
- A downstream `rubric-checks.yml` workflow tests only the local rubric and
  adjacent offline regressions, with read-only permissions and no credentials.
- The synthetic demo report uses a relative source path for portability and
  does not publish the author's local filesystem path.

## Downstream feature development - 2026-10-14

- XLSX score import shares the existing CSV validation and scoring logic.
  Optional openpyxl/defusedxml dependencies, explicit worksheet selection,
  formula rejection, and offline integration tests are included.
- New work is developed on `codex/rubric-excel-manifest`, without rewriting
  remote commits, backdating work, or manufacturing an admission commit count.
- An optional independently supplied CSV manifest checks the exact expected
  case/criterion key set before any report is written. A missing whole case,
  jointly omitted criterion, duplicate manifest key, or unexpected score key
  fails validation. This does not infer missing scores or change scoring policy.
- Optional XLSX comparison exports provide summary, case and criterion sheets
  from the same validated report. User text remains literal, output files are
  exclusively created, and numeric presentation does not alter score precision.
- A definition-driven template command generates blank XLSX score sheets with
  row-relative input validation and usage instructions. It never invents scores.
  Definition validation, completed-workbook round trips and file protection
  are tested together; example definitions are explicitly synthetic.
