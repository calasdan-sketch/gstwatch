# Changelog

## 0.2.0 (unreleased)
Round 5 (CPA, bookkeeper, CRA-rules and accounting-software review)
- Fix (silent wrong answer at the edge): sums used binary floats, so a history that adds up to exactly C$30,000.00 could come out as 30000.000000000004 and be called "over". Quarter and transaction sums are now exact decimals; headroom is exactly the edge (found by a property test).
- Fix: a cell of 1e308 in a transaction CSV crashed with a traceback; now "amount ... is implausibly large", exit 2.
- Fix: very long or pathological date/amount cells could take minutes in the pattern matcher; cells over 64 characters are refused instantly.
- Fix: `freq` and the filing-frequency line were described as using worldwide supplies; canada.ca's reporting-period page uses taxable supplies made in Canada for the preceding fiscal year. Text and an explicit note corrected (the figure in `check` stays an approximation).
- Fix: run with `--as-of` inside the quarter that exceeded C$30,000, the "latest possible" effective date was the quarter end, a date in the future; it is now today, because the supply has already happened. Data that stops quarters before `--as-of` is flagged as possibly out of date instead of silently treated as C$0.
- Add: `--date-column`, `--amount-column`, `--skip-where COLUMN=VALUE` to read any accounting-software or shop export (QuickBooks, Wave, Square, Shopify...); datetimes with zones (`2026-03-31 23:30:00 -0400`), `31 Mar 2026`, `Mar 31, 2026`; `(500.00)` as a negative; numeric `03/04/2026` refused unless unambiguous or `--date-order dmy|mdy` is given. Column names are never guessed.
- Add: `--table` (and `table` in `--json`): quarter-by-quarter working with trailing 2/3/4-quarter totals.
- Add: a note on every result to enter sales before GST/HST in Canadian dollars (canada.ca does not say outright: marked unverified).
- Add: `__author__`, `maintainers` in the package metadata, maintainer line in `--help`; tests pin "Calas Automations Inc." everywhere.
- Behaviour change: with a CSV the date is now read by one strict reader on every Python version (3.11+'s `fromisoformat` used to accept `20260331` and `2026-W13-2`; 3.9 did not; both are now refused).
- Tests: 111 -> 187 (property tests, golden files for every output format, hypothesis tests where installed); `bench/mutation.py` breaks 23 rules one at a time and the suite catches 22 (the 23rd cannot change any output). See `docs/ROUND5.md`.
- Speed: exact sums and a stricter date reader cost something (four side-by-side runs on a noisy machine: engine call 1-3x slower, still a few milliseconds; loading 100,000 rows between equal and about 1.5x slower).
Round 4 (what a stranger gets from `pip install`)
- Fix: `python -m gstwatch` did not work (no `__main__`).
- Fix: `check ... | head` turned exit code 3 ("register") into 0; the real code is kept.
- Fix: a full disk / closed stdout printed a traceback; now a one-line error, exit 2.
- Fix: a CSV with a repeated column name (e.g. two `date` columns) silently used the last one; now rejected.
- Fix: `freq` accepted `1_000` and rejected `1,400,000`; it now uses the same strict money parser as everything else.
- Fix: `--crossing` was silently ignored when no quarter exceeded the threshold; now says so.
- Fix: non-ASCII dash in the footer garbled on legacy Windows consoles; output is ASCII-safe.
- Fix: packaging metadata. `setuptools>=77` is required for the SPDX `license` string (was `>=68`); added project URLs, author "Calas Automations Inc.", Python 3.9-3.13 classifiers, `py.typed`, CHANGELOG/bench/docs in the sdist; LICENSE holder matches the author.
- Add: `check -` reads standard input; Excel UTF-16 "Unicode Text" files read; non-UTF-8 files get a "Save As CSV UTF-8" hint.
- Add: usage errors are JSON under `--json`; every `--json` output carries `schema_version` (1) and `gstwatch_version`.
- Add: README library example (tested), CI/script usage, Windows notes; CI now also runs on Windows and installs the built wheel into a clean venv.
- Speed: reading transaction CSVs is about 1.5x faster (plain-number fast path, no per-row work for absent columns).
- Tests: 96 -> 111. See `docs/ROUND4.md`.
Round 3
- Fix (silent wrong answer): amounts like `12,50` were read as 1250, `1C0` as 10, `1_000`/non-ASCII digits accepted. Money parsing is now strict; ambiguous forms are rejected.
- Fix: `check /dev/zero` (or a FIFO) hung forever; only regular files are read, bounded.
- Fix: `records 9999-01-01` and year-0001 quarters crashed or gave nonsense; years limited to 1900-2100.
- Fix: broken pipe (`| head`) traceback; Windows legacy-console encoding crash on the em dash.
- Fix: taxi/ride-share under the threshold printed a plain "Small supplier: YES" while exiting 3.
- Fix: single-quarter register-by was only the latest possible date; now shows earliest and latest and a "possibly overdue" flag.
- Add: transaction CSVs (`date,amount`) summed to calendar quarters; `;`/tab delimiters; row numbers in CSV errors.
- Add: `--associates`, `--excluded` (and CSV columns); `--first-supply` for the multi-quarter effective date; `records --period-end` for fiscal years.
- Add: `--json` errors are JSON; `bench/` oracle + timing benchmark.
- Behaviour change: a CSV with a `date` column was an error, now means transactions. Amount `1e3` still works; underscores/hex/`12,50` no longer do.
- Tests: 39 -> 96 (fuzzing included).

Round 2
- Fix: NaN amounts silently produced "small supplier" (now rejected); also inf, negative, duplicate, non-quarter-end dates.
- Fix: non-adjacent quarters were treated as consecutive; windows now use calendar quarters, gaps assumed C$0 and reported.
- Fix: when both tests trip, the earliest effective date wins (was always single-quarter).
- Fix: filing frequency uses trailing four quarters (was all quarters); short history labelled ESTIMATE.
- Add: next-quarter headroom, `--as-of` days-left/overdue, `--entity psb|charity`, `--taxi`, `2026Q1` labels.
- Harden: terminal-control/bidi stripped from echoed input, CSV size cap, unreadable-file errors exit 2.
- Tests: 21 -> 39 including a 5,000-case oracle comparison.
