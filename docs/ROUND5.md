# Round 5: the accountant's desk

Honest note on method: I had no tool for spawning independent sub-agents, so the specialists below are separate passes by one author, played in sequence. Each finding names the command that produced it. Nothing was published, tagged, pushed or uploaded; no paid service and no credentials were touched (the only network use was read-only: `pip download`/`pip index`, and fetching public canada.ca, GitHub and competitor pages).

Starting point: branch `expert-2`, 111 tests passing, benchmark 0 mismatches, registry holds only 0.1.0 (`pip index versions gstwatch`), tree is 0.2.0 (unreleased).

## 0. Author line

The author/maintainer name is "Calas Automations Inc." everywhere (no email: none exists for this project, none invented). Round 4 had already set `authors` and the LICENSE; round 5 added `maintainers`, `__author__`, a maintainer line in `--help`, and tests that pin all of it.

| Where | Proof |
|---|---|
| Registry today | `curl -s https://pypi.org/pypi/gstwatch/json` -> author is the old GitHub handle (0.1.0). The next upload fixes the label. |
| Built wheel | `unzip -p dist/*.whl '*/METADATA' \| grep -E '^(Author\|Maintainer)'` -> `Author: Calas Automations Inc.` and `Maintainer: Calas Automations Inc.` |
| LICENSE | `Copyright (c) 2026 Calas Automations Inc.` (test `test_author_everywhere`) |
| Old handle left over | `tests/test_round5.py::test_old_handle_only_appears_inside_github_urls` walks the tree; the handle may appear only inside real github.com URLs of the repo |
| Repo public or private? | Not determinable here (`curl` to github.com returned 403 through the proxy). The URLs stay, and `PUBLISH-CHECKLIST.md` tells Dan to check and delete the `[project.urls]` block if the repo is private. |

## 1. Specialists and findings

| Specialist | Finding | Proving command / evidence |
|---|---|---|
| QA / test-methodology (property-based) | **Real defect.** Sums used binary floats, so a history adding to exactly C$30,000.00 could be 30000.000000000004 and be called "over". The "headroom is exactly the edge" property failed on the first run. Fixed with exact decimals (`dec`, `dsum`, integer cents for transactions). | `pytest tests/test_round5.py::test_property_headroom_is_exactly_the_edge` failed with `total=30000.000000000004`; passes now |
| QA (mutation) | 23 one-rule-at-a-time breakages (threshold, 29 days, bands, exit code, exact sums...). First run: 18/23 killed. Four survivors exposed missing tests (short-history estimate, exactly-four-quarters basis, negative quarter, tie-breaking), which were added; one more survivor was a test passing for the wrong reason (`match="negative"` also matched "non-negative"). Final: 22/23 killed; the 23rd (headroom clamped at zero) cannot change an output because a small supplier never has negative room. | `python3 bench/mutation.py --write`; `bench/mutation_results.json` |
| Canadian CPA / GST-HST specialist | Mid-quarter run is wrong: with `--as-of` inside the quarter that went over C$30,000, "latest possible effective date" was the quarter end, a date in the future; the supply has already happened, so the latest is today. Fixed (clamped, with a "still running" basis and a note). Stale data (quarters missing before `--as-of`) was silently treated as nothing; now flagged "NOT counted as C$0". | `gstwatch check --quarter 2026Q2=35000 --as-of 2026-05-10` -> register-by 2026-06-08 (was 2026-07-29); golden `tests/golden/check_midquarter.txt` |
| CRA-rules researcher | Filing frequency was described as based on worldwide supplies. canada.ca's reporting-period page (as fetched 2026-11-08) says taxable supplies **made in Canada** in the **preceding fiscal year**, including zero-rated and associates', excluding supplies outside Canada, zero-rated exports, exempt supplies, capital real property, goodwill. The threshold test is a different measure (worldwide). README, `freq` and `check` now say so; the `check` figure is labelled an approximation. | WebFetch of `.../gst-hst-account/change-account.html` and `.../when-register-charge.html`, 2026-11-08 |
| CRA-rules researcher | Re-verified: single-quarter and four-quarter tests, "no later than the day of the supply", 29 days, associates (if associated at the start of the quarter), financial services / capital property / goodwill excluded, taxi rule, 6 years "from the end of the year to which they relate" (page does not say calendar vs fiscal: still unverified), bands 1.5M/6M, periods do not auto-adjust. **Not on the pages:** whether the C$30,000 is counted with or without GST/HST, credit-note netting, one-year minimum after voluntary registration. Output now carries an "enter sales before GST/HST (unverified)" note instead of a claim. | same fetches, plus `.../gst-hst-records-keep.html` |
| Small-business bookkeeper | A Shopify-style export (`Created at` with a time and zone, `Subtotal` vs tax-inclusive `Total`, voided orders, `(500.00)` refunds) could not be read at all, and the obvious column ("Total") would have been wrong. Added `--date-column`, `--amount-column` (user must choose; never guessed), `--skip-where`, datetimes taken as written, month-name dates, accounting parentheses. | `gstwatch check orders.csv --date-column "Created at" --amount-column Subtotal --skip-where "Financial Status=voided" --table` |
| Small-business bookkeeper | No way to see *why* a verdict came out. Added `--table` (and `table` in `--json`): amount and trailing 2/3/4-quarter totals per quarter, marking which test trips. | golden `check_single.txt`, `check_rolling.json` |
| Accounting-software integrator | Numeric dates (`03/04/2026`) are ambiguous across QuickBooks (US) and Canadian locales. Rule: refuse unless some date in the file can only be read one way, or the user passes `--date-order dmy\|mdy`; mixed orders refused. | `gstwatch check amb.csv` -> exit 2 with a plain message; `test_ambiguous_numeric_dates_fail_closed_unless_certain` |
| Accounting-software integrator | Python 3.11+ `date.fromisoformat` accepts `20260331` and `2026-W13-2`, 3.9 does not: the same CSV gave different answers per Python version. One strict reader now, same on 3.9/3.12/3.13. | `test_compact_and_week_dates_are_not_accepted_on_any_python` |
| Hostile-input / performance | My own new date reader hung for minutes on a 1 MB cell of spaces (backtracking). Cells over 64 characters are now refused instantly; fast paths and a small cache keep loading cost low. Also found in Pass B: `1e308` in a transaction CSV crashed with `OverflowError` (introduced by my first cents-summing change); now a plain error. | `python3 -c` timing run (timed out at 200 s before the cap, 0.0000 s after); `test_pathological_cells_are_rejected_fast`, `test_huge_amounts_are_a_plain_error_not_a_traceback` |
| Hostile-input | 4,000 random garbage CSVs (control characters, bidi, NUL, full-width digits, quotes, NaN/inf, huge numbers) through `main()` with random option combinations: 0 crashes, all exit codes in {0, 2, 3}. 8 threads x 200 histories through `evaluate`: 0 mismatches (the engine is pure; `main()` keeps module-level state and is not for concurrent use). Spaces in paths and an ASCII locale are covered by the round-4 tests; `LC_ALL=tr_TR.UTF-8 gstwatch check ...` runs without error. | inline fuzz script, thread script |

## 2. Upgrade path from the registry version (0.1.0)

0.1.0 has no state or config files: the only things carried over are the user's CSVs, command lines and the JSON consumers read.

| Check | Result |
|---|---|
| Install the real 0.1.0 wheel (`pip download gstwatch==0.1.0 --no-deps`), run its CLI and engine on 3,000 seeded random histories and compare with this tree | 128 differ, all in `trigger`/`effective_date`/`register_by`; in every one the new date is **earlier** (the 0.2.0 "earliest test wins" fix: 0.1.0 reported only the single-quarter date even when a multi-quarter window had already tripped). 0 cases where the new date is later. |
| 0.1.0 `--json` keys | All 10 still present (`test_json_is_superset_of_0_1_0`); new keys are additive; `schema_version` 1 unchanged. |
| 0.1.0 CSV (`quarter_end,amount`) | Reads identically (`test_0_1_0_csv_still_reads`). |
| Not compatible by design (documented in CHANGELOG/checklist) | `date` column now means transactions; `12,50`, `1_000`, hex, non-ASCII digits refused; `fromisoformat`-only date forms refused; exit code 3 for "register" (0.1.0 also used 3). |

## 3. Quality methods added

Property tests (seeded, plus hypothesis where installed): more revenue never clears a registration and never delays it; input order is irrelevant; shifting a history by k years shifts dates by k years; register-by = effective + 29; earliest <= latest (including random `--as-of`); headroom is exactly the edge (+0.01 trips); transactions sum to quarter totals; parsers raise only `InputError` on arbitrary text. Mutation harness (`bench/mutation.py`). Golden files for every output format (`tests/golden/`, 11 cases: text and JSON for check/freq/records; regenerate with `GSTWATCH_REGEN=1 pytest tests/test_round5.py -k golden_output`). Differential: the existing 20,000-case oracle (0 mismatches, still) plus the 0.1.0 comparison above.

## 4. Competitors re-checked (read-only, 2026-11-08)

1. gst-hst-tracker (github.com/jasveerai88/gst-hst-tracker): `report`, `threshold`, `provinces`; "77 tests, standard library only"; rolling four-quarter window tested; no single-quarter test described; cites the 29-day rule but shows no effective date; MIT; v1.0.0; **it is on PyPI** (`pip index versions gst-hst-tracker` -> 1.0.0), which round 4 had left unconfirmed. It does province tax, ITCs and net tax, which gstwatch does not.
2. yourincomecalculator.com/ca/calculators/hst-registration: **found again** (round 4 could not): Q1-Q4 boxes, province dropdown, rolling total, tax estimate, "within 29 days" as text, no date, FAQ mentions the single-quarter rule but the displayed results are built on the four-quarter total.
README comparison table updated. Accounting-software columns stay unverified.

## 5. Scored ideas (value / differentiation / effort / risk: 1 low to 5 high)

| # | Idea | Value | Diff | Effort | Risk | Status |
|---|---|---|---|---|---|---|
| 1 | Exact decimal arithmetic at the threshold edge | 5 | 3 | 2 | 2 | DONE |
| 2 | Mid-quarter clamp of latest effective date to today | 4 | 4 | 2 | 2 | DONE |
| 3 | Stale-data / unfinished-quarter notes | 3 | 3 | 1 | 1 | DONE |
| 4 | `--date-column` / `--amount-column` for any export | 5 | 4 | 3 | 2 | DONE |
| 5 | `--skip-where` (voided / unpaid rows) | 4 | 3 | 2 | 2 | DONE |
| 6 | Datetimes with zones, month-name dates, `(500.00)` negatives | 4 | 3 | 2 | 2 | DONE |
| 7 | Ambiguous numeric dates refused unless certain; `--date-order` | 4 | 4 | 2 | 2 | DONE |
| 8 | `--table` quarter-by-quarter working (+ JSON `table`) | 4 | 4 | 2 | 1 | DONE |
| 9 | Filing-frequency basis corrected (Canada, preceding fiscal year) | 4 | 3 | 1 | 1 | DONE |
| 10 | "Enter sales before GST/HST, in CAD (unverified)" note | 3 | 2 | 1 | 1 | DONE |
| 11 | Refuse over-long cells (pattern-matcher DoS) | 3 | 1 | 1 | 1 | DONE |
| 12 | Same date reader on every Python version | 3 | 2 | 1 | 1 | DONE |
| 13 | Mutation harness | 3 | 3 | 3 | 1 | DONE |
| 14 | Golden files for every output format | 3 | 2 | 2 | 1 | DONE |
| 15 | Property + hypothesis tests | 3 | 2 | 2 | 1 | DONE |
| 16 | `__author__`, `maintainers`, `--help` line, pinned by tests | 2 | 1 | 1 | 1 | DONE |
| 17 | Pin CI actions to commit SHAs (round 4 #18) | 3 | 1 | 1 | 1 | NOT-DONE (needs online SHA lookup) |
| 18 | PyPI Trusted Publishing workflow (round 4 #19) | 4 | 2 | 2 | 3 | NOT-DONE (publishing path is Dan's call) |
| 19 | `--fail-within DAYS` exit code (round 4 #20) | 3 | 4 | 2 | 3 | NOT-DONE (changes exit-code contract) |
| 20 | French-language output (round 4 #21) | 4 | 5 | 4 | 2 | NOT-DONE |
| 21 | Province rates / net tax / ITCs (round 4 #22) | 4 | 3 | 5 | 5 | NOT-DONE (out of scope, error-prone) |
| 22 | Credit-note netting per CRA (round 4 #23) | 3 | 2 | 2 | 4 | NOT-DONE (rule not on the pages) |
| 23 | Voluntary-registration date / one-year minimum (round 4 #24) | 3 | 3 | 3 | 4 | NOT-DONE (needs primary source) |
| 24 | Quebec QST sibling check (round 4 #25) | 3 | 4 | 3 | 4 | NOT-DONE (needs Revenu Quebec source) |
| 25 | Auto-recognize QuickBooks/Wave/Square header names (round 4 #27) | 4 | 4 | 3 | 4 | NOT-DONE (no real exports to test; user names columns instead) |
| 26 | Skip title lines above the header (QuickBooks report exports) | 3 | 3 | 2 | 3 | NOT-DONE (no sample) |
| 27 | Foreign-currency conversion (Bank of Canada rates) | 3 | 3 | 4 | 4 | NOT-DONE (needs live rates; rule source not checked) |
| 28 | Read `.xlsx` directly | 3 | 2 | 4 | 3 | NOT-DONE (no dependency policy) |
| 29 | Say which date counts (invoice vs payment) | 3 | 3 | 2 | 4 | NOT-DONE (rule not found on the pages) |
| 30 | Shell completion (round 4 #26) | 1 | 1 | 2 | 1 | NOT-DONE |

## 6. Verification (Pass B)

- Tests: 111 before, 187 after with hypothesis installed (184 passed + 3 skipped without it). Python 3.13 (with and without hypothesis), 3.12 and 3.9 all green; 3.10 and 3.11 not run.
- Lint: `ruff check --isolated --select E9,F,B` clean except the known `zip(strict=)` note in an old test; `mypy src` clean.
- Built wheel and sdist from a copy of the tree, `twine check` PASSED for both, wheel installed non-editable into a fresh venv (`pip check` clean), every README command and `python -m gstwatch` run from there with the documented exit codes (0/3), stdin input, the library example, and `--table`.
- Pass B findings that came from re-attacking my own diff: the `1e308` crash (above); the test that passed by accident (`match="negative"`); a mutation pattern that silently stopped matching after an edit (script now reports "NOT APPLIED"); a doubled full stop in the new `--help` line.
- Benchmark: oracle 0 mismatches / 20,000 (unchanged). Timing on a very noisy machine: the exact-decimal engine is 1-3x slower per call (still a few milliseconds for 400 quarters); loading 100,000 rows between equal and about 1.5x slower than round 4 (side by side, four runs).

## 7. Could NOT test

- Windows and macOS (static review only; new code adds no paths, shell calls or signals). CI has never been executed.
- Python 3.10 and 3.11.
- Real QuickBooks, Wave, Square, Shopify or Stripe exports: the column handling was tested against exports I wrote from memory of their formats; their real headers and date formats are unverified.
- Whether the GitHub repository is public (the check was blocked) and PyPI's rendering of the README.
- Any CRA rule beyond the three canada.ca pages named above; the page text was read through a fetch tool that summarises, so quotes should be re-read on canada.ca before relying on them. Still unverified: tax-inclusive vs exclusive revenue, credit-note netting, calendar vs fiscal year for retention, voluntary registration.
- Competitor features beyond the pages fetched; accounting-software columns remain unverified.
