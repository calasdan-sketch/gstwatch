# Round 4: the stranger's first hour

Honest note on method: this round was done by one agent working through eight reviewer roles in turn. I had no tool for spawning independent sub-agents, so the roles are separate passes by the same author, not separate minds. Every finding below was produced by running a command, quoted next to it. Nothing was published, tagged, pushed or uploaded.

Baseline: 96 tests passed (`PYTHONPATH=src python3 -m pytest -q`; note that bare `pytest` failed at collection on a checkout until `pythonpath` was configured, fixed below). Registry: `pip index versions gstwatch` -> only `0.1.0`; repo was `0.2.0` (unreleased).

## Specialist findings

| Role | Finding | Proof |
|---|---|---|
| First-time user (README only, clean venv) | `python -m gstwatch` fails; README quick-start commands otherwise all work from the built wheel on Python 3.13 and 3.9 | `python -m gstwatch --version` -> "No module named gstwatch.__main__" |
| First-time user | README says `pip install gstwatch`, which installs 0.1.0 and lacks most documented features | `pip index versions gstwatch`; wheel 0.1.0 has no `--json`, no transactions |
| Release engineer | `requires = ["setuptools>=68"]` but `license = "MIT"` (SPDX string) needs setuptools 77+ | PEP 639 support landed in setuptools 77; pip's isolated build fetched a new one, so it built, but the declared floor was wrong |
| Release engineer | No `py.typed`, no project URLs, author was only a GitHub handle, no Python-version/OS classifiers, LICENSE holder differed from author | `unzip -p dist/*.whl '*/METADATA'`; `unzip -l` |
| Release engineer | `pytest` from a fresh clone failed collection (package not on path) | `python3 -m pytest -q` -> "4 errors during collection" |
| Supply-chain | Zero runtime dependencies (`pip install` of the wheel pulls nothing; `pip check` clean). Wheel has no tests, secrets or personal paths (`grep -rI "/root\|/home"` on the build tree: no hits). CI actions pinned by tag, not commit SHA (NOT fixed: I cannot look up SHAs offline) | `unzip -l`, `pip check` |
| Docs/DX | Output footer used an em dash; legacy Windows consoles show `?` | `LC_ALL=C PYTHONIOENCODING=ascii gstwatch check ...` printed `?` |
| CI/CD integrator | `check ... \| head` returned 0 instead of 3 (hid "register") | `gstwatch check --quarter 2026Q1=40000 \| head -1; echo ${PIPESTATUS[0]}` -> 0 |
| CI/CD integrator | argparse usage errors under `--json` were not JSON; no stdin input; JSON had no version for consumers | `gstwatch --json freq abc` |
| Hostile-input fuzzer | Disk full printed a traceback; a repeated CSV header silently used the last column; 200 KB field, NUL byte, escape sequences, UTF-16 and CRLF handled or rejected cleanly | `gstwatch check ... > /dev/full`; `date,amount,date` CSV |
| Hostile-input fuzzer | `freq 1_000` accepted but `freq 1,400,000` rejected (inconsistent with strict parser) | `gstwatch freq 1_000` |
| Performance | 150,000-row transaction CSV ~3.0 s; per-row work for absent `associates`/`excluded` columns and per-row calendar calls | cProfile of `load_quarters` |
| Competitor's maintainer | gst-hst-tracker: four-quarter test only, no effective date or 29-day deadline (README as fetched); yourincomecalculator.com home page lists UK VAT tools, no GST/HST calculator found | WebFetch, 2026-11-07 |
| Primary-source check | canada.ca "when to register and charge": single-quarter, four-quarter, "end of the month following the quarter", associates, taxi, C$50,000 PSB all re-confirmed as quoted in README | WebFetch of the page, 2026-11-07 |

## Windows (static review only, NOT run on Windows)

Checked by reading the code and grepping: no `shell=True`/subprocess, no `signal`, no `os.replace`/rename of open files, no writes at all (nothing to lock), CSV read as bytes then decoded (CRLF and BOM safe, tested), paths only passed to `os.stat`/`open`, `NUL`/`CON` are character devices and are refused by the regular-file check, stdout/stderr switched to `errors="replace"` so a cp437/cp1252 console cannot raise `UnicodeEncodeError`, footer now ASCII. Added UTF-16 (Excel "Unicode Text") and a "Save As CSV UTF-8" hint for the old-code-page case. CI now includes `windows-latest`; that is the first real Windows run and I have not seen its result.

## Scored ideas (value / differentiation / effort / risk: 1 low to 5 high)

| # | Idea | Value | Diff | Effort | Risk | Status |
|---|---|---|---|---|---|---|
| 1 | `python -m gstwatch` | 3 | 1 | 1 | 1 | DONE |
| 2 | Keep exit code 3 through `\| head` | 4 | 2 | 1 | 1 | DONE |
| 3 | Setuptools floor 77, URLs, classifiers, py.typed, author | 4 | 1 | 1 | 1 | DONE |
| 4 | Read CSV from stdin (`-`) | 4 | 2 | 1 | 1 | DONE |
| 5 | Excel UTF-16 "Unicode Text" input | 3 | 3 | 1 | 1 | DONE |
| 6 | "Save As CSV UTF-8" hint on non-UTF-8 | 3 | 2 | 1 | 1 | DONE |
| 7 | JSON usage errors, `schema_version`, `gstwatch_version` | 4 | 3 | 1 | 1 | DONE |
| 8 | Reject repeated CSV column names | 3 | 2 | 1 | 1 | DONE |
| 9 | No traceback on write failure (disk full) | 2 | 1 | 1 | 1 | DONE |
| 10 | `freq` uses the strict money parser | 2 | 1 | 1 | 1 | DONE |
| 11 | Note when `--crossing` is ignored | 2 | 2 | 1 | 1 | DONE |
| 12 | ASCII-safe output (Windows consoles) | 3 | 1 | 1 | 1 | DONE |
| 13 | CSV loading ~1.5x faster | 2 | 1 | 2 | 2 | DONE |
| 14 | mypy-clean source (ships `py.typed`) | 2 | 1 | 2 | 1 | DONE |
| 15 | CI on Windows + install built wheel in clean venv | 4 | 2 | 1 | 1 | DONE (unseen) |
| 16 | README library example that is executed by a test | 3 | 2 | 1 | 1 | DONE |
| 17 | `pytest` works from a fresh clone (`pythonpath`) | 3 | 1 | 1 | 1 | DONE |
| 18 | Pin CI actions to commit SHAs | 3 | 1 | 1 | 1 | NOT-DONE (needs online SHA lookup) |
| 19 | PyPI Trusted Publishing workflow (no token on disk) | 4 | 2 | 2 | 3 | NOT-DONE (publishing path is Dan's decision) |
| 20 | `--fail-within DAYS` style exit code for "register soon" | 3 | 4 | 2 | 3 | NOT-DONE (changes exit-code contract) |
| 21 | French-language output (fr-CA users) | 4 | 5 | 4 | 2 | NOT-DONE |
| 22 | Province-aware rates / net tax / ITCs | 4 | 3 | 5 | 5 | NOT-DONE (out of scope; error-prone) |
| 23 | Netting of credit notes per CRA | 3 | 2 | 2 | 4 | NOT-DONE (rule not found on CRA pages) |
| 24 | Voluntary-registration date and one-year minimum | 3 | 3 | 3 | 4 | NOT-DONE (needs primary source) |
| 25 | Quebec QST small-supplier threshold sibling check | 3 | 4 | 3 | 4 | NOT-DONE (needs Revenu Quebec primary source) |
| 26 | Shell completion | 1 | 1 | 2 | 1 | NOT-DONE |
| 27 | Read accounting-software exports (QuickBooks/Wave/Square column names) | 4 | 4 | 3 | 3 | NOT-DONE (needs sample exports I do not have) |

## Verification and checks run

- Tests: 96 before, 111 after. Passed on Python 3.13 (working tree), and 3.9 and 3.12 (run from the unpacked sdist against a venv with the built wheel installed; note the repo's `pythonpath` setting means the tests import `src`, not the installed copy, so install correctness is covered by the README-command run below). Python 3.10 and 3.11 interpreters exist here but the suite was not run on them.
- Benchmark: 0 mismatches vs the oracle on 20,000 cases (unchanged). Loading 100,000 transaction rows: about 1.9 s before, about 1.1 s after, side by side on a noisy machine (`evaluate` timing 2-6 ms in both: noise, no code change to the algorithm).
- Lint: lint `ruff check --isolated --select E9,F,B` clean except a `zip(strict=)` style note in an old test (that keyword needs 3.10, package supports 3.9); `mypy src` clean.
- Built sdist+wheel offline-style into a scratch dir, `twine check` PASSED for both, contents inspected, wheel installed into fresh non-editable venvs on Python 3.13 and 3.9, every README command and the entry point run from there.
- Pass B: rebuilt, `twine check` PASSED, re-ran every README command plus `python -m gstwatch`, stdin and the library example from the new wheel on 3.13 and 3.9: all exit codes as documented (0/3/3/3/0...).
- Pass B fixes found by re-attacking: the em-dash footer replacement had missed the real string (found by the ASCII-locale run), and the first BrokenPipe fix swallowed the real exit code in a sibling `except` order (found by the closed-pipe test).

## Could NOT test

- Windows and macOS (static review only).
- Python 3.10, 3.11, 3.12 install-and-run only where noted in the report; others unverified.
- The GitHub Actions workflow itself (never executed here).
- Any CRA rule beyond what the cited canada.ca page says; credit-note netting, voluntary registration and the "year" meaning for retention stay unverified.
- Competitor claims beyond the pages fetched; accounting-software columns remain unverified.
- PyPI rendering of the README (only `twine check`).
