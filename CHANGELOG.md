# Changelog

## 0.2.0 (unreleased)
- Fix: NaN amounts silently produced "small supplier" (now rejected); also inf, negative, duplicate, non-quarter-end dates.
- Fix: non-adjacent quarters were treated as consecutive; windows now use calendar quarters, gaps assumed C$0 and reported.
- Fix: when both tests trip, the earliest effective date wins (was always single-quarter).
- Fix: filing frequency uses trailing four quarters (was all quarters); short history labelled ESTIMATE.
- Add: next-quarter headroom, `--as-of` days-left/overdue, `--entity psb|charity`, `--taxi`, `2026Q1` labels.
- Harden: terminal-control/bidi stripped from echoed input, CSV size cap, unreadable-file errors exit 2.
- Tests: 21 -> 39 including a 5,000-case oracle comparison.
