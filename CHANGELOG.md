# Changelog

## 0.2.0 (unreleased)
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
