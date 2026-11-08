"""Round 5: author pins, upgrade compatibility, mid-quarter/stale-data notes, accounting exports,
quarter table, seeded property tests, and golden output files for every format."""
import datetime as dt
import json
import os
import random
import re

import pytest

import gstwatch
from gstwatch import evaluate
from gstwatch.cli import load_quarters, main
from gstwatch.evaluate import (
    aggregate_transactions,
    dsum,
    _add_years,
    InputError,
    parse_amount,
    parse_date_cell,
    quarter_end,
    quarter_table,
    resolve_ambiguous,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "golden")
AUTHOR = "Calas Automations Inc."
D = dt.date


def qs(*amounts, start=(2025, 1)):
    y, q = start
    out = []
    for a in amounts:
        out.append((quarter_end(y, q), float(a)))
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return out


# ---------------------------------------------------------------- author / version pins
def test_author_everywhere():
    assert gstwatch.__author__ == AUTHOR
    py = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
    assert py.count(f'name = "{AUTHOR}"') == 2  # authors and maintainers
    assert re.search(r"^authors = \[\{ name = \"Calas Automations Inc\.\" \}\]$", py, re.M)
    assert re.search(r"^maintainers = \[\{ name = \"Calas Automations Inc\.\" \}\]$", py, re.M)
    assert "email" not in py  # never invent one
    assert open(os.path.join(ROOT, "LICENSE")).read().startswith(f"MIT License\n\nCopyright (c) 2026 {AUTHOR}\n")


def test_old_handle_only_appears_inside_github_urls():
    bad = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".mypy_cache", ".pytest_cache", "dist",
                                                 "build", "golden")]
        for f in files:
            if f.endswith((".py", ".md", ".toml", ".yml", ".json", ".txt", ".in")) or f == "LICENSE":
                path = os.path.join(base, f)
                for n, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
                    stripped = line.replace("github.com/calasdan-sketch", "")
                    if "calasdan" + "-sketch" in stripped:
                        bad.append(f"{path}:{n}")
    assert not bad, bad


def test_help_names_maintainer(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert AUTHOR in capsys.readouterr().out


def test_version_pinned_everywhere():
    v = gstwatch.__version__
    read = lambda n: open(os.path.join(ROOT, n), encoding="utf-8").read()
    assert f'version = "{v}"' in read("pyproject.toml")
    assert f"## {v} " in read("CHANGELOG.md")
    assert f"Version to release: {v}" in read("PUBLISH-CHECKLIST.md").replace("**", "")
    assert f"gstwatch {v}" in read("PUBLISH-CHECKLIST.md")


# ---------------------------------------------------------------- upgrade compatibility with 0.1.0
OLD_JSON_KEYS = {"total", "small_supplier", "trigger", "crossing_quarter", "window", "window_total",
                 "effective_date", "register_by", "filing_frequency", "notes"}  # 0.1.0 `check --json`


def test_json_is_superset_of_0_1_0(capsys):
    main(["check", "--quarter", "2026Q1=8000", "--quarter", "2026Q2=15000", "--quarter", "2026Q3=9000", "--json"])
    assert OLD_JSON_KEYS <= set(json.loads(capsys.readouterr().out))


def test_0_1_0_csv_still_reads(tmp_path):
    p = tmp_path / "q.csv"  # exactly the format 0.1.0 documented
    p.write_text("quarter_end,amount\n2025-12-31,8000\n2026-03-31,8000\n2026-06-30,15000\n")
    assert load_quarters(str(p)) == [(D(2025, 12, 31), 8000.0), (D(2026, 3, 31), 8000.0),
                                     (D(2026, 6, 30), 15000.0)]


# ---------------------------------------------------------------- mid-quarter / stale data
def test_mid_quarter_clamps_latest_effective_date_to_today():
    st = evaluate([(D(2026, 6, 30), 35000.0)], as_of=D(2026, 5, 10))
    assert st.effective_date == D(2026, 5, 10) and st.register_by == D(2026, 6, 8)
    assert st.register_by_earliest == D(2026, 4, 30)
    assert "still running" in st.effective_basis
    assert any("has not finished" in n for n in st.notes)


def test_finished_quarter_keeps_quarter_end():
    st = evaluate([(D(2026, 3, 31), 35000.0)], as_of=D(2026, 5, 10))
    assert st.effective_date == D(2026, 3, 31)


def test_crossing_date_beats_clamp():
    st = evaluate([(D(2026, 6, 30), 35000.0)], as_of=D(2026, 5, 10), crossing_date=D(2026, 4, 20))
    assert st.effective_date == D(2026, 4, 20)


def test_stale_data_is_flagged_not_zero_filled():
    st = evaluate(qs(5000, 5000), as_of=D(2026, 12, 1))
    assert any("data stops at" in n and "NOT counted as C$0" in n for n in st.notes)
    st2 = evaluate(qs(5000, 5000), as_of=D(2025, 8, 1))  # current quarter running: not stale
    assert not any("data stops" in n for n in st2.notes)


def test_filing_frequency_note_says_canada_not_worldwide():
    st = evaluate(qs(5000))
    assert any("preceding fiscal year" in n and "not the worldwide" in n for n in st.notes)


# ---------------------------------------------------------------- accounting exports
SHOPIFY = (
    "Name,Created at,Subtotal,Taxes,Total\n"
    "#1,2026-01-15 10:00:00 -0500,\"10,000.00\",1300,\"11,300.00\"\n"
    "#2,2026-03-31 23:30:00 -0400,9000.00,1170,10170\n"
    "#3,2026-04-02T08:00:00Z,(500.00),0,0\n")


def test_named_columns_read_a_shopify_style_export(tmp_path):
    p = tmp_path / "orders.csv"
    p.write_text(SHOPIFY)
    got = load_quarters(str(p), date_column="Created At", amount_column="SUBTOTAL")
    assert got == [(D(2026, 3, 31), 19000.0), (D(2026, 6, 30), -500.0)]  # date as written, not UTC-shifted


def test_without_flags_the_export_is_refused_and_columns_listed(tmp_path):
    p = tmp_path / "orders.csv"
    p.write_text(SHOPIFY)
    with pytest.raises(ValueError, match="columns found: name, created at, subtotal"):
        load_quarters(str(p))


def test_unknown_named_column_lists_choices(tmp_path):
    p = tmp_path / "o.csv"
    p.write_text(SHOPIFY)
    with pytest.raises(ValueError, match="--amount-column 'nope' is not a column"):
        load_quarters(str(p), date_column="created at", amount_column="nope")


def test_flags_without_file_are_a_usage_error(capsys):
    assert main(["check", "--quarter", "2026Q1=1", "--date-column", "x"]) == 2
    assert "apply to a CSV file" in capsys.readouterr().err


@pytest.mark.parametrize("text,expected", [
    ("2026-03-31", D(2026, 3, 31)),
    ("2026/03/31", D(2026, 3, 31)),
    ("2026-03-31 23:59", D(2026, 3, 31)),
    ("2026-03-31T23:59:59.123+05:30", D(2026, 3, 31)),
    ("2026-03-31 11:30 PM EST", D(2026, 3, 31)),
    ("31 Mar 2026", D(2026, 3, 31)),
    ("31-March-2026", D(2026, 3, 31)),
    ("Mar 31, 2026", D(2026, 3, 31)),
    ("sept. 5, 2026", D(2026, 9, 5)),
    ("03/31/2026", (3, 31, 2026)),
    ("31.03.2026", (31, 3, 2026)),
])
def test_parse_date_cell(text, expected):
    assert parse_date_cell(text) == expected


@pytest.mark.parametrize("text", ["", "2026-02-30", "26-03-31", "31 Mär 2026", "1 Foo 2026", "2026-3-1",
                                  "２０２６-03-31", "2026-03-31 99", "yesterday", "03/31/26", "0x7E9-03-31"])
def test_parse_date_cell_rejects(text):
    with pytest.raises(InputError):
        parse_date_cell(text)


def test_ambiguous_numeric_dates_fail_closed_unless_certain(tmp_path):
    assert resolve_ambiguous([(25, 3, 2026), (5, 4, 2026)], None) == "dmy"
    assert resolve_ambiguous([(3, 25, 2026), (5, 4, 2026)], None) == "mdy"
    assert resolve_ambiguous([(3, 4, 2026)], "dmy") == "dmy"
    with pytest.raises(InputError, match="March 4 or April 3"):
        resolve_ambiguous([(3, 4, 2026)], None)
    with pytest.raises(InputError, match="mix"):
        resolve_ambiguous([(25, 3, 2026), (3, 25, 2026)], None)
    p = tmp_path / "a.csv"
    p.write_text("date,amount\n03/04/2026,100\n")
    with pytest.raises(ValueError, match="could be March 4 or April 3"):
        load_quarters(str(p))
    assert load_quarters(str(p), date_order="mdy") == [(D(2026, 3, 31), 100.0)]
    assert load_quarters(str(p), date_order="dmy") == [(D(2026, 6, 30), 100.0)]
    p.write_text("date,amount\n13/13/2026,100\n")
    with pytest.raises(ValueError, match="row 2"):
        load_quarters(str(p), date_order="dmy")


def test_accounting_negative_parentheses():
    assert parse_amount("(1,234.56)") == -1234.56
    assert parse_amount("($500)") == -500.0
    for bad in ("(1,234.56", "()", "(-5)", "((5))"):
        with pytest.raises(InputError):
            parse_amount(bad)


# ---------------------------------------------------------------- quarter table
def test_quarter_table_shows_working_and_gaps():
    rows = quarter_table([(D(2025, 3, 31), 20000.0), (D(2025, 12, 31), 15000.0)])
    assert [r["quarter_end"] for r in rows] == ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
    assert [r["assumed_zero"] for r in rows] == [False, True, True, False]
    assert rows[3]["last_4_quarters"] == 35000.0 and rows[3]["over_threshold"] == ["4-quarter"]
    assert rows[1]["last_2_quarters"] == 20000.0 and rows[0]["over_threshold"] == []


def test_table_flag_text_and_json(capsys):
    assert main(["check", "--quarter", "2026Q1=20000", "--quarter", "2026Q2=15000", "--table"]) == 3
    out = capsys.readouterr().out
    assert "Quarter-by-quarter working" in out and "35,000.00*" in out
    assert main(["check", "--quarter", "2026Q1=20000", "--quarter", "2026Q2=15000", "--table", "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["table"][1]["last_2_quarters"] == 35000.0
    main(["check", "--quarter", "2026Q1=20000", "--json"])
    assert "table" not in json.loads(capsys.readouterr().out)  # only when asked


# ---------------------------------------------------------------- seeded property tests
def _rand_history(rnd):
    n = rnd.randint(1, 8)
    start = rnd.randint(0, 3)
    amts = [round(rnd.choice([0, 0, 2000, 9000, 14000, 29999.99, 30000, 30000.01, 45000]) * rnd.random() * 1.3, 2)
            for _ in range(n)]
    return [(quarter_end(2024 + (i + start) // 4, (i + start) % 4 + 1), a) for i, a in enumerate(amts)]


def test_property_more_revenue_never_clears_a_registration():
    rnd = random.Random(501)
    for _ in range(1500):
        h = _rand_history(rnd)
        base = evaluate(h)
        i = rnd.randrange(len(h))
        bumped = [(d, a + (rnd.choice([1, 500, 20000]) if j == i else 0)) for j, (d, a) in enumerate(h)]
        more = evaluate(bumped)
        if not base.small_supplier:
            assert not more.small_supplier
            assert more.effective_earliest <= base.effective_earliest  # never later
        if more.small_supplier:
            assert base.small_supplier


def test_property_input_order_does_not_matter():
    rnd = random.Random(502)
    for _ in range(500):
        h = _rand_history(rnd)
        shuffled = h[:]
        rnd.shuffle(shuffled)
        assert evaluate(h).as_dict() == evaluate(shuffled).as_dict()


def test_property_shifting_whole_history_by_years_shifts_dates_by_years():
    rnd = random.Random(503)
    for _ in range(500):
        h = _rand_history(rnd)
        k = rnd.randint(1, 20)
        moved = [(d.replace(year=d.year + k), a) for d, a in h]
        a, b = evaluate(h), evaluate(moved)
        assert (a.small_supplier, a.trigger, a.window_total) == (b.small_supplier, b.trigger, b.window_total)
        if a.effective_date:
            assert b.effective_date == _add_years(a.effective_date, k)
            assert b.register_by - b.effective_date == a.register_by - a.effective_date


def test_property_register_by_is_effective_plus_29_and_earliest_not_after_latest():
    rnd = random.Random(504)
    for _ in range(1500):
        st = evaluate(_rand_history(rnd))
        if st.small_supplier:
            assert st.register_by is None and st.next_quarter_headroom is not None
            continue
        assert st.register_by - st.effective_date == dt.timedelta(days=29)
        assert st.effective_earliest <= st.effective_date


def test_property_headroom_is_exactly_the_edge():
    rnd = random.Random(505)
    checked = 0
    for _ in range(1500):
        h = _rand_history(rnd)
        st = evaluate(h)
        if not st.small_supplier:
            continue
        room = st.next_quarter_headroom
        nxt = st.next_quarter
        at_edge = evaluate(h + [(nxt, room)])
        over = evaluate(h + [(nxt, room + 0.01)])
        assert at_edge.small_supplier and not over.small_supplier
        checked += 1
    assert checked > 200


def test_property_transactions_equal_quarter_totals(tmp_path):
    rnd = random.Random(506)
    for _ in range(40):
        h = _rand_history(rnd)
        lines = ["date,amount"]
        for d, a in h:
            cuts = sorted(rnd.randint(0, int(a * 100)) for _ in range(2))
            parts = [cuts[0], cuts[1] - cuts[0], int(a * 100) - cuts[1]]
            qstart_month = d.month - 2
            for k, c in enumerate(parts):
                lines.append(f"{d.year}-{qstart_month + k:02d}-{rnd.randint(1, 28):02d},{c / 100:.2f}")
        p = tmp_path / "t.csv"
        p.write_text("\n".join(lines) + "\n")
        got = load_quarters(str(p))
        assert [d for d, _ in got] == [d for d, _ in h]
        assert len(got) == len(h)
        for (_, x), (_, y) in zip(got, h):  # noqa: B905 (strict= needs 3.10)
            assert abs(x - y) < 0.011


# ---------------------------------------------------------------- golden files (every output format)
CASES = {
    "check_small.txt": ["check", "--quarter", "2026Q1=8000", "--quarter", "2026Q2=7000"],
    "check_single.txt": ["check", "--quarter", "2026Q1=31000", "--as-of", "2026-04-15", "--table"],
    "check_rolling.txt": ["check", "--quarter", "2025Q4=8000", "--quarter", "2026Q1=8000",
                          "--quarter", "2026Q2=15000", "--first-supply", "2026-08-12"],
    "check_midquarter.txt": ["check", "--quarter", "2026Q2=35000", "--as-of", "2026-05-10"],
    "check_taxi.txt": ["check", "--quarter", "2026Q1=1000", "--taxi"],
    "check_psb.json": ["check", "--quarter", "2026Q1=45000", "--entity", "psb", "--json"],
    "check_rolling.json": ["check", "--quarter", "2025Q4=8000", "--quarter", "2026Q1=8000",
                           "--quarter", "2026Q2=15000", "--json", "--table"],
    "freq.txt": ["freq", "1400000"],
    "freq.json": ["freq", "7000000", "--json"],
    "records.txt": ["records", "2026-05-10"],
    "records.json": ["records", "2026-05-10", "--period-end", "2027-03-31", "--json"],
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden_output(name, capsys):
    main(CASES[name])
    out = capsys.readouterr().out
    path = os.path.join(GOLDEN, name)
    if os.environ.get("GSTWATCH_REGEN") == "1":
        os.makedirs(GOLDEN, exist_ok=True)
        open(path, "w", encoding="utf-8", newline="\n").write(out)
    expected = open(path, encoding="utf-8", newline="").read()
    assert out == expected
    if name.endswith(".json"):
        json.loads(out)


def test_golden_error_outputs(capsys):
    assert main(["check", "--quarter", "2026-02-30=5", "--json"]) == 2
    cap = capsys.readouterr()
    assert json.loads(cap.out)["exit"] == 2 and cap.err.startswith("gstwatch: ")
    assert main(["freq", "-5", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]


# ---------------------------------------------------------------- float boundary (found by the headroom property)
def test_exactly_the_threshold_is_not_over_even_when_floats_disagree():
    for a, b in [(10000.10, 19999.90), (0.3, 29999.7), (12345.67, 17654.33), (29999.99, 0.01)]:
        st = evaluate(qs(a, b))
        assert st.small_supplier, (a, b)
    assert not evaluate(qs(29999.99, 0.02)).small_supplier


def test_transaction_sums_are_exact_decimals(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("date,amount\n" + "".join(f"2026-01-{d:02d},0.10\n" for d in range(1, 21))
                 + "2026-02-01,29997.99\n")
    (q, total), = load_quarters(str(p))
    assert total == 29999.99  # 20 x 0.10 + 29997.99; naive float sums drift
    assert evaluate([(q, total)]).small_supplier


def test_inline_associates_and_excluded_are_exact():
    assert main(["check", "--quarter", "2026Q1=20000.10", "--associates", "2026Q1=9999.90"]) == 0


# ---------------------------------------------------------------- gaps found by mutation testing (bench/mutation.py)
def test_short_history_filing_estimate_is_scaled_to_a_year():
    st = evaluate(qs(400000, 400000))           # 2 quarters -> 1.6M a year -> quarterly
    assert st.filing_frequency == "quarterly" and st.filing_basis.startswith("ESTIMATE: 2 quarter(s)")
    st1 = evaluate(qs(400000))                  # 1 quarter -> 1.6M a year
    assert st1.filing_frequency == "quarterly"
    st3 = evaluate(qs(0, 0, 400000))            # 3 quarters -> 400k*4/3
    assert st3.filing_frequency == "annual"


def test_exactly_four_quarters_use_trailing_basis_not_estimate():
    st = evaluate(qs(100, 100, 100, 100))
    assert st.filing_basis == "trailing 4 calendar quarters"
    assert evaluate(qs(100, 100, 100)).filing_basis.startswith("ESTIMATE")


def test_negative_quarter_amount_is_rejected_everywhere(capsys):
    with pytest.raises(InputError, match="amount for 2026-03-31 is negative"):
        evaluate([(D(2026, 3, 31), -0.01)])
    assert main(["check", "--quarter", "2026Q1=-1"]) == 2
    assert "amount for 2026-03-31 is negative" in capsys.readouterr().err
    assert evaluate([(D(2026, 3, 31), 0.0)]).small_supplier


def test_tie_between_single_and_rolling_is_reported_as_single_quarter():
    # window ending 2025Q4 -> effective 2026-01-31; the single-quarter crossing is also 2026-01-31
    st = evaluate([(D(2025, 9, 30), 16000.0), (D(2025, 12, 31), 16000.0), (D(2026, 3, 31), 31000.0)],
                  crossing_date=D(2026, 1, 31))
    assert st.trigger == "single-quarter" and st.effective_date == D(2026, 1, 31)


def test_pathological_cells_are_rejected_fast():
    import time
    t0 = time.perf_counter()
    for bad in ("2026-03-31" + " " * 1_000_000 + "x", "T" * 1_000_000, "1/" * 500_000, "1 " + "a" * 100_000 + " 2026"):
        with pytest.raises(InputError):
            parse_date_cell(bad)
    for bad in ("9" * 1_000_000, "(" * 500_000, "1 " * 400_000):
        with pytest.raises(InputError):
            parse_amount(bad)
    assert time.perf_counter() - t0 < 2.0


def test_compact_and_week_dates_are_not_accepted_on_any_python():
    for odd in ("20260331", "2026-W13-2", "2026-090"):  # date.fromisoformat takes these on 3.11+, not on 3.9
        with pytest.raises(InputError):
            parse_date_cell(odd)


def test_sub_cent_amounts_are_still_summed_exactly():
    rows = [(D(2026, 1, 5), 0.001)] * 3 + [(D(2026, 2, 5), 29999.99), (D(2026, 2, 6), -0.5)]
    (q, total), = aggregate_transactions(rows)
    assert total == 29999.493


# ---------------------------------------------------------------- hypothesis (runs only where it is installed)
def test_hypothesis_parsers_never_raise_anything_but_input_error():
    hyp = pytest.importorskip("hypothesis")
    st_ = pytest.importorskip("hypothesis.strategies")

    @hyp.settings(max_examples=400, deadline=None, derandomize=True)
    @hyp.given(st_.text(max_size=80))
    def inner(text):
        for fn in (parse_amount, parse_date_cell):
            try:
                fn(text)
            except InputError:
                pass

    inner()


def test_hypothesis_date_formats_agree_with_calendar():
    hyp = pytest.importorskip("hypothesis")
    st_ = pytest.importorskip("hypothesis.strategies")

    @hyp.settings(max_examples=300, deadline=None, derandomize=True)
    @hyp.given(st_.dates(min_value=D(1900, 1, 1), max_value=D(2100, 12, 31)), st_.integers(0, 23),
               st_.integers(0, 59))
    def inner(d, h, m):
        names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for text in (d.isoformat(), f"{d.isoformat()} {h:02d}:{m:02d}:00 -0500",
                     f"{d.year}/{d.month:02d}/{d.day:02d}", f"{d.day} {names[d.month - 1]} {d.year}",
                     f"{names[d.month - 1]} {d.day}, {d.year}"):
            assert parse_date_cell(text) == d

    inner()


def test_hypothesis_more_revenue_never_clears_registration():
    hyp = pytest.importorskip("hypothesis")
    st_ = pytest.importorskip("hypothesis.strategies")
    money = st_.integers(0, 6_000_000).map(lambda c: c / 100)

    @hyp.settings(max_examples=300, deadline=None, derandomize=True)
    @hyp.given(st_.lists(money, min_size=1, max_size=9), st_.integers(0, 8), money)
    def inner(amounts, i, bump):
        h = qs(*amounts)
        i %= len(h)
        more = [(d, dsum(a, bump) if j == i else a) for j, (d, a) in enumerate(h)]
        if not evaluate(h).small_supplier:
            assert not evaluate(more).small_supplier

    inner()


# ---------------------------------------------------------------- --skip-where
STATUS_CSV = ("Created at,Subtotal,Financial Status\n2026-01-10,20000,paid\n2026-01-11,15000,VOIDED\n"
              "2026-02-01,9000,paid\n")


def test_skip_where_leaves_out_voided_rows(tmp_path, capsys):
    p = tmp_path / "o.csv"
    p.write_text(STATUS_CSV)
    stats = {}
    got = load_quarters(str(p), "created at", "subtotal", skip_where=["financial status=voided"], stats=stats)
    assert got == [(D(2026, 3, 31), 29000.0)] and stats == {"skipped": 1}
    argv = ["check", str(p), "--date-column", "Created at", "--amount-column", "Subtotal"]
    assert main(argv) == 3                                 # 44,000 counted
    capsys.readouterr()
    assert main(argv + ["--skip-where", "Financial Status=voided"]) == 0
    out = capsys.readouterr().out
    assert "1 row(s) left out by --skip-where" in out and "29,000.00" in out


def test_skip_where_errors_are_plain(tmp_path):
    p = tmp_path / "o.csv"
    p.write_text(STATUS_CSV)
    with pytest.raises(ValueError, match="expected COLUMN=VALUE"):
        load_quarters(str(p), "created at", "subtotal", skip_where=["nonsense"])
    with pytest.raises(ValueError, match="--skip-where 'nope' is not a column"):
        load_quarters(str(p), "created at", "subtotal", skip_where=["nope=x"])
    p.write_text("Created at,Subtotal,S\n2026-01-10,5,x\n")
    with pytest.raises(ValueError, match="all 1 were skipped"):
        load_quarters(str(p), "created at", "subtotal", skip_where=["s=X"])


def test_huge_amounts_are_a_plain_error_not_a_traceback(tmp_path, capsys):
    p = tmp_path / "big.csv"
    for body in ("2026-01-01,1e308\n", "2026-01-01,1e308\n2026-01-02,1e308\n", "2026-01-01,-1e308\n",
                 "2026-01-01,1e15\n2026-01-02,1e15\n"):
        p.write_text("date,amount\n" + body)
        assert main(["check", str(p)]) == 2
        err = capsys.readouterr().err
        assert err.startswith("gstwatch: ") and "Traceback" not in err


def test_property_clamped_dates_stay_ordered():
    rnd = random.Random(507)
    for _ in range(1500):
        h = _rand_history(rnd)
        as_of = D(2024, 1, 1) + dt.timedelta(days=rnd.randint(0, 1100))
        st = evaluate(h, as_of=as_of)
        if st.small_supplier:
            continue
        assert st.effective_earliest <= st.effective_date
        assert st.register_by_earliest <= st.register_by
        assert st.days_to_register == (st.register_by - as_of).days
