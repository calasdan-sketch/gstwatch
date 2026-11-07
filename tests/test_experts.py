"""Findings from the expert pass: data quality, rule gaps, headroom."""
import datetime as dt
import json

import pytest

from gstwatch.cli import main
from gstwatch.evaluate import InputError, evaluate, parse_quarter_label

D = dt.date


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 1e18])
def test_rejects_bad_amounts(bad):
    # NaN used to compare False and silently report "small supplier" (fail-open)
    with pytest.raises(InputError):
        evaluate([(D(2026, 3, 31), bad)])


def test_rejects_duplicates_and_non_quarter_ends():
    with pytest.raises(InputError):
        evaluate([(D(2026, 3, 31), 1), (D(2026, 3, 31), 2)])
    with pytest.raises(InputError):
        evaluate([(D(2026, 3, 30), 1)])


def test_gap_quarters_are_not_adjacent():
    # Q1 and Q4 are 3 quarters apart; old code summed them as "consecutive" windows
    s = evaluate([(D(2025, 3, 31), 16000), (D(2026, 3, 31), 16000)])
    assert s.small_supplier and len(s.gaps) == 3
    assert any("assumed to be C$0" in n for n in s.notes)


def test_earliest_trigger_wins():
    qs = [(D(2026, 3, 31), 20000), (D(2026, 6, 30), 20000), (D(2026, 9, 30), 35000)]
    s = evaluate(qs)
    assert s.trigger == "rolling" and s.effective_date == D(2026, 7, 31)


def test_filing_uses_trailing_four_quarters():
    qs = [(D(2024, 3, 31), 1_000_000), (D(2024, 6, 30), 1_000_000),
          (D(2024, 9, 30), 1_000_000), (D(2024, 12, 31), 1_000_000),
          (D(2025, 3, 31), 100), (D(2025, 6, 30), 100), (D(2025, 9, 30), 100),
          (D(2025, 12, 31), 100)]
    s = evaluate(qs)
    assert s.filing_frequency == "annual" and "trailing" in s.filing_basis


def test_short_history_flagged_as_estimate():
    assert "ESTIMATE" in evaluate([(D(2026, 3, 31), 100)]).filing_basis


def test_psb_threshold_and_taxi():
    assert evaluate([(D(2026, 3, 31), 40000)], entity="psb").small_supplier
    assert not evaluate([(D(2026, 3, 31), 51000)], entity="psb").small_supplier
    s = evaluate([(D(2026, 3, 31), 100)], taxi=True)
    assert s.taxi_must_register and any("taxi" in n for n in s.notes)


def test_headroom():
    qs = [(D(2025, 12, 31), 5000), (D(2026, 3, 31), 5000), (D(2026, 6, 30), 5000)]
    s = evaluate(qs)
    assert s.next_quarter == D(2026, 9, 30) and s.next_quarter_headroom == 15000
    full = evaluate([(D(2026, 3, 31), 30000)])
    assert full.next_quarter_headroom == 0


def test_crossing_must_be_in_quarter():
    with pytest.raises(InputError):
        evaluate([(D(2026, 3, 31), 31000)], crossing_date=D(2025, 1, 1))
    assert evaluate([(D(2026, 3, 31), 31000)], crossing_date=D(2026, 1, 1)).effective_date == D(2026, 1, 1)


def test_as_of_overdue():
    s = evaluate([(D(2026, 3, 31), 31000)], as_of=D(2026, 5, 10))
    assert s.overdue and s.days_to_register == -11


def test_quarter_labels():
    assert parse_quarter_label("2026Q2") == D(2026, 6, 30)
    assert parse_quarter_label("2026-q4") == D(2026, 12, 31)
    with pytest.raises(InputError):
        parse_quarter_label("2026Q5")


def test_cli_nan_and_escape(capsys):
    assert main(["check", "--quarter", "2026Q1=nan"]) == 2
    assert main(["check", "--quarter", "2026-03-31=1", "--quarter", "2026Q1=2"]) == 2
    assert main(["check", "--quarter", "2026-03-31=1\x1b[31m‮"]) == 2
    err = capsys.readouterr().err
    assert "\x1b" not in err and "‮" not in err


def test_cli_json_and_flags(capsys):
    assert main(["check", "--quarter", "2026Q1=100", "--taxi", "--json"]) == 3
    d = json.loads(capsys.readouterr().out)
    assert d["taxi_must_register"] and d["not_tax_advice"]
    assert main(["check", "--quarter", "2026Q1=100", "--entity", "charity"]) == 2
    assert main(["freq", "nan"]) == 2
    assert main(["freq", "-5"]) == 2


def test_cli_unreadable_csv(tmp_path, capsys):
    assert main(["check", str(tmp_path)]) == 2          # directory
    b = tmp_path / "b.csv"
    b.write_bytes(b"\xff\xfe\x00bad")
    assert main(["check", str(b)]) == 2
    assert main(["check", str(tmp_path / "missing.csv")]) == 2


def test_matches_independent_oracle():
    """5,000 random histories vs a naive re-implementation of the two tests."""
    import random
    rnd = random.Random(7)
    ends = [(2024 + i // 4, i % 4 + 1) for i in range(8)]
    for _ in range(5000):
        vals = [rnd.choice([0, 3000, 8000, 12000, 20000, 31000]) for _ in ends]
        qs = [(D(y, q * 3, 30 if q in (2, 3) else 31), v) for (y, q), v in zip(ends, vals)]
        trip = any(sum(vals[max(0, i - n + 1):i + 1]) > 30000 for i in range(8) for n in (1, 2, 3, 4))
        assert (not evaluate(qs).small_supplier) == trip
