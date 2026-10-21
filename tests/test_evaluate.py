"""Threshold evaluation tests — dates hand-computed from the verified rules."""
import datetime as dt

import pytest

from gstwatch.evaluate import (
    evaluate,
    filing_frequency,
    next_month_end,
    quarter_end,
    retention_deadline,
)

D = dt.date


def test_quarter_ends():
    assert quarter_end(2026, 1) == D(2026, 3, 31)
    assert quarter_end(2026, 4) == D(2026, 12, 31)
    assert quarter_end(2028, 1) == D(2028, 3, 31)  # leap Feb


def test_next_month_end():
    assert next_month_end(D(2026, 9, 30)) == D(2026, 10, 31)
    assert next_month_end(D(2026, 12, 31)) == D(2027, 1, 31)
    assert next_month_end(D(2026, 2, 28)) == D(2026, 3, 31)


def test_below_threshold_is_small_supplier():
    qs = [(D(2025, 12, 31), 7000), (D(2026, 3, 31), 7000),
          (D(2026, 6, 30), 7000), (D(2026, 9, 30), 7000)]
    s = evaluate(qs)
    assert s.small_supplier and s.trigger == "none"
    assert s.effective_date is None and s.filing_frequency == "annual"


def test_single_quarter_trigger_and_dates():
    s = evaluate([(D(2026, 3, 31), 31000)])
    assert not s.small_supplier and s.trigger == "single-quarter"
    assert s.effective_date == D(2026, 3, 31)
    assert s.register_by == D(2026, 4, 29)          # +29 days
    assert any("supply that takes you over" in n for n in s.notes)


def test_crossing_date_override():
    s = evaluate([(D(2026, 3, 31), 31000)], crossing_date=D(2026, 2, 15))
    assert s.effective_date == D(2026, 2, 15)
    assert s.register_by == D(2026, 3, 16)          # Feb 15 + 29


def test_exact_threshold_not_exceeded():
    # "exceed" means strictly more than C$30,000
    assert evaluate([(D(2026, 3, 31), 30000)]).small_supplier
    qs = [(D(2025, 12, 31), 10000), (D(2026, 3, 31), 10000),
          (D(2026, 6, 30), 10000), (D(2026, 9, 30), 0)]
    assert evaluate(qs).small_supplier                # four quarters = 30,000 exactly


def test_rolling_four_quarter_trigger():
    qs = [(D(2025, 12, 31), 8000), (D(2026, 3, 31), 8000),
          (D(2026, 6, 30), 8000), (D(2026, 9, 30), 8000)]
    s = evaluate(qs)
    assert not s.small_supplier and s.trigger == "rolling"
    assert s.crossing_quarter == D(2026, 9, 30)
    assert s.window_total == 32000
    assert s.effective_date == D(2026, 10, 31)       # end of month FOLLOWING the quarter
    assert s.register_by == D(2026, 11, 29)          # +29 days
    assert any("end of the month following" in n for n in s.notes)


def test_rolling_window_of_two():
    qs = [(D(2026, 3, 31), 16000), (D(2026, 6, 30), 16000)]
    s = evaluate(qs)
    assert s.trigger == "rolling" and len(s.window) == 2
    assert s.effective_date == D(2026, 7, 31)


def test_filing_frequency_bands():
    assert filing_frequency(0) == "annual"
    assert filing_frequency(1_500_000) == "annual"       # <= 1.5M
    assert filing_frequency(1_500_001) == "quarterly"
    assert filing_frequency(6_000_000) == "quarterly"    # <= 6M
    assert filing_frequency(6_000_001) == "monthly"


def test_retention_deadline():
    assert retention_deadline(D(2026, 5, 10)) == D(2032, 12, 31)  # 6 years from end of year
    assert retention_deadline(D(2026, 12, 31)) == D(2032, 12, 31)


def test_empty_input_rejected():
    with pytest.raises(ValueError):
        evaluate([])


def test_as_dict_shape():
    d = evaluate([(D(2026, 3, 31), 31000)]).as_dict()
    assert d["trigger"] == "single-quarter" and d["register_by"] == "2026-04-29"
    assert isinstance(d["notes"], list)
