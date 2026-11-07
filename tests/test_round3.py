"""Round 3: strict money parsing, transaction CSVs, safe file reads, effective-date honesty."""
import datetime as dt
import json
import os
import sys

import pytest

from gstwatch.cli import main
from gstwatch.evaluate import (
    InputError,
    aggregate_transactions,
    evaluate,
    parse_amount,
    retention_deadline,
)

D = dt.date


@pytest.mark.parametrize("text,val", [
    ("1234.56", 1234.56), ("1,234.56", 1234.56), ("$5,000", 5000.0), ("C$5,000", 5000.0),
    ("CAD 5000", 5000.0), ("5000 CAD", 5000.0), ("12 500,50", 12500.5),
    ("12 500,50", 12500.5), ("1 234", 1234.0), ("-20.5", -20.5), ("1e3", 1000.0), ("0", 0.0),
])
def test_parse_amount_ok(text, val):
    assert parse_amount(text) == pytest.approx(val)


@pytest.mark.parametrize("bad", [
    "12,50", "1,25", "1C0", "1_000", "0x10", "٣٠٠٠٠", "nan", "inf",
    "", "abc", "1,2,3", "12,5000", "1..2", "--5", "1e999999", "$$5", "5 5",
])
def test_parse_amount_rejects(bad):
    with pytest.raises(InputError):
        parse_amount(bad)


def test_ambiguous_comma_hint():
    with pytest.raises(InputError, match="ambiguous"):
        parse_amount("12,50")


def test_aggregate_transactions_and_refunds():
    qs = aggregate_transactions([(D(2026, 1, 5), 100.0), (D(2026, 3, 31), 50.0),
                                 (D(2026, 4, 1), 10.0), (D(2026, 4, 2), -4.0)])
    assert qs == [(D(2026, 3, 31), 150.0), (D(2026, 6, 30), 6.0)]


def test_transaction_csv_sums_into_quarters(tmp_path, capsys):
    p = tmp_path / "t.csv"
    rows = ["date,amount"] + [f"2026-0{m}-15,11000" for m in (1, 2, 3)]
    p.write_text("\n".join(rows) + "\n")
    assert main(["--json", "check", str(p)]) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["trigger"] == "single-quarter" and out["total"] == 33000


def test_quarter_csv_still_rejects_duplicates(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("quarter_end,amount\n2026Q1,1\n2026Q1,2\n")
    assert main(["check", str(p)]) == 2


def test_csv_needs_exactly_one_date_column(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("date,quarter_end,amount\n2026-01-01,2026Q1,1\n")
    assert main(["check", str(p)]) == 2


def test_semicolon_french_csv(tmp_path, capsys):
    p = tmp_path / "fr.csv"
    p.write_text("quarter_end;amount\n2026Q1;12 500,50\n", encoding="utf-8")
    assert main(["--json", "check", str(p)]) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 12500.5


def test_csv_row_error_names_row(tmp_path, capsys):
    p = tmp_path / "r.csv"
    p.write_text("quarter_end,amount\n2026Q1,10\n2026Q2,12,50\n")
    assert main(["check", str(p)]) == 2
    assert "row 3" in capsys.readouterr().err


def test_csv_associates_and_excluded_columns(tmp_path, capsys):
    p = tmp_path / "a.csv"
    p.write_text("quarter_end,amount,associates,excluded\n2026Q1,20000,15000,1000\n")
    assert main(["--json", "check", str(p)]) == 3
    assert json.loads(capsys.readouterr().out)["total"] == 34000


def test_cli_associates_excluded(capsys):
    assert main(["--json", "check", "--quarter", "2026Q1=20000", "--associates", "2026Q1=15000",
                 "--excluded", "2026Q1=6000"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total"] == 29000 and any("associates" in n for n in out["notes"])
    assert main(["check", "--quarter", "2026Q1=1", "--associates", "2026Q2=5"]) == 2
    assert main(["check", "--quarter", "2026Q1=5", "--excluded", "2026Q1=9"]) == 2  # negative


def test_non_regular_file_refused(tmp_path, capsys):
    assert main(["check", str(tmp_path)]) == 2
    if os.path.exists("/dev/zero") and sys.platform != "win32":
        assert main(["check", "/dev/zero"]) == 2


def test_oversize_csv_refused(tmp_path):
    p = tmp_path / "big.csv"
    p.write_bytes(b"quarter_end,amount\n" + b"2026Q1,1\n" * 700_000)
    assert main(["check", str(p)]) == 2


def test_non_utf8_csv(tmp_path):
    p = tmp_path / "l.csv"
    p.write_bytes(b"quarter_end,amount\n2026Q1,\xff\n")
    assert main(["check", str(p)]) == 2


def test_json_errors_are_json(capsys):
    assert main(["--json", "check", "--quarter", "bad"]) == 2
    cap = capsys.readouterr()
    assert json.loads(cap.out)["exit"] == 2 and "gstwatch:" in cap.err


def test_taxi_label_not_plain_yes(capsys):
    assert main(["check", "--taxi", "--quarter", "2026Q1=100"]) == 3
    assert "BUT taxi" in capsys.readouterr().out


def test_single_quarter_without_crossing_gives_earliest():
    st = evaluate([(D(2026, 6, 30), 31000)])
    assert st.effective_date == D(2026, 6, 30)
    assert st.effective_earliest == D(2026, 4, 1)
    assert st.register_by_earliest == D(2026, 4, 30)
    assert st.register_by == D(2026, 7, 29)


def test_crossing_given_collapses_range():
    st = evaluate([(D(2026, 6, 30), 31000)], crossing_date=D(2026, 5, 10))
    assert st.register_by == st.register_by_earliest == D(2026, 6, 8)


def test_first_supply_moves_rolling_deadline():
    qs = [(D(2026, 3, 31), 20000), (D(2026, 6, 30), 15000)]
    base = evaluate(qs)
    assert base.effective_date == D(2026, 7, 31)
    st = evaluate(qs, first_supply=D(2026, 9, 10))
    assert st.effective_date == D(2026, 9, 10)
    assert st.register_by == D(2026, 10, 9)
    assert st.register_by_earliest == D(2026, 8, 29)
    with pytest.raises(InputError):
        evaluate(qs, first_supply=D(2026, 7, 31))  # not after status end


def test_first_supply_cli(capsys):
    assert main(["--json", "check", "--quarter", "2026Q1=20000", "--quarter", "2026Q2=15000",
                 "--first-supply", "2026-09-10"]) == 3
    assert json.loads(capsys.readouterr().out)["register_by"] == "2026-10-09"


def test_year_bounds():
    with pytest.raises(InputError):
        evaluate([(D(1, 3, 31), 5)])
    with pytest.raises(InputError):
        evaluate([(D(9999, 12, 31), 5)])
    with pytest.raises(InputError):
        retention_deadline(D(9999, 1, 1))
    assert main(["records", "9999-01-01"]) == 2


def test_retention_fiscal_period_end():
    assert retention_deadline(D(2026, 5, 10)) == D(2032, 12, 31)
    assert retention_deadline(D(2026, 5, 10), D(2027, 3, 31)) == D(2033, 3, 31)
    assert retention_deadline(D(2026, 5, 10), D(2026, 12, 31)) == D(2032, 12, 31)
    assert retention_deadline(D(2024, 2, 29), D(2024, 2, 29)) == D(2030, 12, 31)
    with pytest.raises(InputError):
        retention_deadline(D(2026, 5, 10), D(2026, 1, 1))
    with pytest.raises(InputError):
        retention_deadline(D(2026, 5, 10), D(2029, 1, 1))


def test_broken_pipe_is_quiet(monkeypatch):
    import gstwatch.cli as cli

    def boom(*a, **k):
        raise BrokenPipeError
    calls = []
    monkeypatch.setattr(cli, "_main", boom)
    monkeypatch.setattr(cli.os, "dup2", lambda *a: calls.append(a))
    assert cli.main(["freq", "1"]) == 0
    assert calls


def test_control_chars_not_echoed(capsys):
    assert main(["check", "--quarter", "2026Q1=\x1b[31mX‮"]) == 2
    err = capsys.readouterr().err
    assert "\x1b" not in err and "‮" not in err


def test_empty_amount_rejected(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("quarter_end,amount\n2026Q1,\n")
    assert main(["check", str(p)]) == 2


def test_fuzz_never_crashes(tmp_path, capsys):
    """Random hostile CSVs and args: only exit codes 0/2/3, never a traceback."""
    import random
    rnd = random.Random(1234)
    alphabet = list("0123456789,.;\t \n\"'-+eE$CAD:QqT/\\") + ["2026", "Q1", "-", "‮", "\x1b", "\x00", "é"]
    p = tmp_path / "f.csv"
    for _ in range(600):
        head = rnd.choice(["quarter_end,amount", "date,amount", "date;amount", "amount", "", "a,b"])
        body = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 120)))
        p.write_text(head + "\n" + body, encoding="utf-8", errors="replace")
        try:
            rc = main(["check", str(p)])
        except SystemExit as e:  # argparse usage errors
            rc = e.code
        assert rc in (0, 2, 3)
    capsys.readouterr()
    for _ in range(300):
        arg = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 30)))
        for argv in (["check", "--quarter", arg], ["records", arg], ["freq", arg],
                     ["check", "--quarter", "2026Q1=1", "--crossing", arg]):
            try:
                rc = main(argv)
            except SystemExit as e:
                rc = e.code
            assert rc in (0, 2, 3)


def test_parse_amount_rejects_overflow():
    with pytest.raises(InputError):
        parse_amount("1e999")


def test_possibly_overdue_uses_earliest():
    qs = [(D(2026, 6, 30), 31000)]
    st = evaluate(qs, as_of=D(2026, 6, 10))
    assert st.overdue is False and st.possibly_overdue is True
    assert evaluate(qs, as_of=D(2026, 4, 10)).possibly_overdue is False
    assert evaluate(qs, as_of=D(2026, 9, 1)).overdue is True


def test_rolling_pick_reports_earlier_single_possibility():
    # Q1+Q2 = 35k trips rolling (eff 2026-07-31); Q3 alone 31k could have crossed from 2026-07-01
    qs = [(D(2026, 3, 31), 20000), (D(2026, 6, 30), 15000), (D(2026, 9, 30), 31000)]
    st = evaluate(qs)
    assert st.trigger == "rolling" and st.effective_date == D(2026, 7, 31)
    assert st.effective_earliest == D(2026, 7, 1)
    assert st.register_by_earliest == D(2026, 7, 30)


def test_ascii_console_does_not_crash(monkeypatch, capsys):
    import io

    import gstwatch.cli as cli
    buf = io.TextIOWrapper(io.BytesIO(), encoding="ascii", errors="strict")
    monkeypatch.setattr(cli.sys, "stdout", buf)
    assert cli.main(["check", "--quarter", "2026Q1=1"]) == 0
