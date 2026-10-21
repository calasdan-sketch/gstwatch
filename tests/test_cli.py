"""CLI tests."""
import json

from gstwatch.cli import main


def write_csv(tmp, rows):
    p = tmp / "quarters.csv"
    p.write_text("quarter_end,amount\n" + "\n".join(f"{d},{a}" for d, a in rows) + "\n",
                 encoding="utf-8")
    return str(p)


def test_check_below_threshold(capsys):
    assert main(["check", "--quarter", "2026-03-31=7000", "--quarter", "2026-06-30=7000"]) == 0
    out = capsys.readouterr().out
    assert "Small supplier: YES" in out and "not tax advice" in out


def test_check_exceeded_returns_3(tmp_path, capsys):
    csv = write_csv(tmp_path, [("2026-03-31", "31000")])
    assert main(["check", csv]) == 3
    out = capsys.readouterr().out
    assert "Register by:                2026-04-29" in out


def test_check_json(tmp_path, capsys):
    csv = write_csv(tmp_path, [("2026-03-31", "8000"), ("2026-06-30", "8000"),
                          ("2026-09-30", "8000"), ("2026-12-31", "8000")])
    assert main(["check", csv, "--json"]) == 3
    data = json.loads(capsys.readouterr().out)
    assert data["trigger"] == "rolling" and data["effective_date"] == "2027-01-31"


def test_crossing_flag(tmp_path, capsys):
    csv = write_csv(tmp_path, [("2026-03-31", "31000")])
    assert main(["check", csv, "--crossing", "2026-02-15"]) == 3
    assert "2026-02-15" in capsys.readouterr().out


def test_freq(capsys):
    assert main(["freq", "1400000"]) == 0
    assert "annual" in capsys.readouterr().out
    assert main(["freq", "7000000"]) == 0
    assert "monthly" in capsys.readouterr().out


def test_records(capsys):
    assert main(["records", "2026-05-10"]) == 0
    assert "2032-12-31" in capsys.readouterr().out
    assert main(["records", "2026-05-10", ]) == 0


def test_records_json(capsys):
    assert main(["records", "2026-05-10"]) == 0
    capsys.readouterr()
    assert main(["--json", "records", "2026-05-10"]) == 0
    assert json.loads(capsys.readouterr().out)["retain_until"] == "2032-12-31"


def test_no_input_is_usage_error(capsys):
    assert main(["check"]) == 2
    assert main(["check", "--quarter", "bogus"]) == 2


def test_bad_csv_columns(tmp_path, capsys):
    p = tmp_path / "bad.csv"
    p.write_text("date,amount\n2026-03-31,100\n", encoding="utf-8")
    assert main(["check", str(p)]) == 2
