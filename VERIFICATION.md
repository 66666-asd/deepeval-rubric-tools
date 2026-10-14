# Local verification - 2026-10-14

## Environment

- Windows, Python 3.12.7, isolated `.venv`.
- Editable DeepEval installation from the local source snapshot.
- No model API requests, platform uploads, repository authorization, or
  Git commits were performed.

## Checks performed

1. `pytest` on `tests/test_core/test_rubric.py`,
   `tests/test_core/test_cli`, and `tests/test_core/test_run`:
   **143 passed, 2 warnings in 9.40 seconds**.
2. All selected tests ran with `pytest-socket --disable-socket`.
   A separate cold-start test blocks sockets BEFORE importing DeepEval,
   then validates pure JSON stdout with read-only configuration enabled.
3. The two warnings concern upstream `TestRun` and `TestRunManager`
   classes that pytest cannot collect because they define constructors.
   No test failed or was skipped in this selected run.
4. Ruff lint with `--target-version py39` passed for all three new Python
   files; Ruff formatting check passed for the same files.
5. `pip check`: no broken requirements found.
6. PowerShell launcher: example input yields A=83.75, B=63.75 and delta=20.
   JSON stdout parses successfully. All six temporary environment settings
   are restored, including variables originally absent from the environment.
7. `examples/rubric/demo-report.json` was produced through the real CLI
   from the bundled synthetic example, using Baseline/Candidate labels.
8. Every extracted upstream file was compared against the downloaded ZIP.
   No upstream file is missing; `LICENSE.md` is byte-for-byte unchanged.
   Exactly three upstream files differ: `README.md`, `deepeval/cli/main.py`,
   and `deepeval/test_run/test_run.py`. All other additions are downstream.

## Limits

- Only Python 3.12.7 was executed; other upstream-supported Python versions
  have not been runtime-tested. A Python 3.9 lint target is not a runtime test.
- The full upstream integration suite was not run; it includes tests that
  require provider packages, credentials, or external services.
- No user scoring data was available. Demonstration scores are synthetic
  and do not establish real model quality or financial evaluation results.
- This is a public-source derivative snapshot without Git history, not an
  eligible submission for the never-public repository collection project.
