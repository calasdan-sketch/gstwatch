# Changelog

## 0.2.0 (unreleased)
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
