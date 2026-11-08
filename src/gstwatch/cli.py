"""gstwatch CLI: threshold check, filing frequency, record retention dates."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import stat
import sys
import unicodedata
from typing import Dict, List, Sequence, Tuple

from . import __author__, __version__
from .evaluate import (
    AmbiguousDate,
    InputError,
    Quarter,
    aggregate_transactions,
    date_from_parts,
    dsum,
    evaluate,
    filing_frequency,
    parse_amount,
    parse_date_cell,
    parse_quarter_label,
    quarter_table,
    resolve_ambiguous,
    retention_deadline,
)

MAX_CSV_BYTES = 5_000_000
SCHEMA_VERSION = 1  # bump only if a --json field is removed or changes meaning


def _date(text: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {text!r}") from None


def _amount(text: str) -> float:
    return parse_amount(text)


class _Parser(argparse.ArgumentParser):
    """argparse that honours --json for usage errors too (still exit 2, plain English)."""
    argv_seen: "list[str]" = []

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {_clean(message)}", file=sys.stderr)
        if "--json" in self.argv_seen:
            print(json.dumps({"error": _clean(message), "exit": 2, "not_tax_advice": True,
                              "schema_version": SCHEMA_VERSION}))
        sys.exit(2)


def _decode(raw: bytes, label: str) -> str:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):  # Excel "Unicode Text" export (UTF-16 with BOM)
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            raise ValueError(f"cannot read {label}: damaged UTF-16 text") from None
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"cannot read {label}: not UTF-8 text (in Excel use Save As > "
                         "CSV UTF-8)") from None


def _read_text(path: str) -> str:
    """Read a regular file (or stdin for ``-``), bounded.

    Refuses devices/pipes/directories (they can block or be endless).
    """
    if path == "-":
        try:
            raw = sys.stdin.buffer.read(MAX_CSV_BYTES + 1)
        except (OSError, ValueError, AttributeError):
            raise ValueError("cannot read standard input") from None
        label = "standard input"
    else:
        label = repr(path)
        try:
            st = os.stat(path)
            if not stat.S_ISREG(st.st_mode):
                raise ValueError(f"{path!r} is not a regular file")
            with open(path, "rb") as fh:
                raw = fh.read(MAX_CSV_BYTES + 1)
        except FileNotFoundError:
            raise ValueError(f"not found: {path!r}") from None
        except OSError as e:
            raise ValueError(f"cannot read {path!r}: {type(e).__name__}") from None
    if len(raw) > MAX_CSV_BYTES:
        raise ValueError(f"CSV larger than {MAX_CSV_BYTES} bytes")
    return _decode(raw, label)


def _sniff(text: str) -> str:
    head = text.split("\n", 1)[0]
    return max([",", ";", "\t"], key=lambda c: head.count(c))


def _opt_amount(norm: Dict[str, str], key: str) -> float:
    v = norm.get(key, "")
    return parse_amount(v) if v else 0.0


def _pick_column(names: List[str], wanted: str, flag: str) -> str:
    w = wanted.strip().lower()
    hits = [n for n in names if n == w]
    if not hits:
        raise ValueError(f"{flag} {_clean(repr(wanted))} is not a column in the file (columns: "
                         + ", ".join(_clean(n) for n in names if n) + ")")
    return w


def load_quarters(path: str, date_column: "str | None" = None, amount_column: "str | None" = None,
                  date_order: "str | None" = None, skip_where: "Sequence[str] | None" = None,
                  stats: "Dict[str, int] | None" = None) -> List[Quarter]:
    """CSV -> calendar-quarter totals.

    Either ``quarter_end,amount`` (one row per quarter, duplicates rejected) or
    ``date,amount`` (any transactions; summed into calendar quarters). Optional
    ``associates`` and ``excluded`` columns adjust each row: amount + associates - excluded.
    Comma, semicolon or tab delimited. ``date_column`` / ``amount_column`` name the columns of
    an accounting-software export (case-insensitive); naming a date column means transactions.
    Numeric dates like 03/04/2026 need an unambiguous file or ``date_order`` ('dmy'/'mdy').
    ``skip_where`` items look like ``"Financial Status=voided"``: rows whose column equals the
    value (case-insensitive) are left out; ``stats["skipped"]`` receives how many.
    """
    text = _read_text(path)
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=_sniff(text))
        names = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
        fields = set(names)
        dup = sorted({n for n in names if n and names.count(n) > 1})
        if dup:
            raise ValueError("CSV has repeated column name(s): " + ", ".join(_clean(d) for d in dup))
        has_assoc, has_excl = "associates" in fields, "excluded" in fields
        dcol = _pick_column(names, date_column, "--date-column") if date_column else "date"
        acol = _pick_column(names, amount_column, "--amount-column") if amount_column else "amount"
        by_date = dcol in fields
        by_quarter = "quarter_end" in fields and not date_column
        if acol not in fields or by_date == by_quarter:
            shown = ", ".join(_clean(n) for n in names if n)
            raise ValueError("CSV needs an amount column and exactly one of quarter_end or date "
                             f"(columns found: {shown}); for an accounting-software export name "
                             "them with --date-column and --amount-column")
        skips: List[Tuple[str, str]] = []
        for item in skip_where or []:
            col, eq, val = item.partition("=")
            if not eq or not col.strip():
                raise ValueError(f"bad --skip-where {_clean(repr(item))}, expected COLUMN=VALUE")
            skips.append((_pick_column(names, col, "--skip-where"), val.strip().casefold()))
        skipped = 0
        rows: List[Tuple[dt.date, float]] = []
        pending: List[Tuple[int, AmbiguousDate, float]] = []
        for n, row in enumerate(reader, start=2):
            if row.get(None):
                raise ValueError(f"row {n}: more columns than the header (quote amounts that "
                                 "contain commas, e.g. \"1,250\")")
            norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            if not any(norm.values()):
                continue
            if skips and any(norm.get(c, "").casefold() == v for c, v in skips):
                skipped += 1
                continue
            try:
                if not norm.get(acol):
                    raise InputError("amount is empty")
                amount = parse_amount(norm[acol])
                if has_assoc:
                    amount = dsum(amount, _opt_amount(norm, "associates"))
                if has_excl:
                    amount = dsum(amount, -_opt_amount(norm, "excluded"))
                if by_date:
                    got = parse_date_cell(norm.get(dcol, ""))
                    if isinstance(got, tuple):
                        pending.append((n, got, amount))
                        continue
                    d = got
                else:
                    d = parse_quarter_label(norm["quarter_end"])
            except InputError as e:
                raise ValueError(f"row {n}: {e}") from None
            rows.append((d, amount))
            if len(rows) + len(pending) > 200_000:
                raise ValueError("too many rows")
        if pending:
            try:
                order = resolve_ambiguous([p for _, p, _ in pending], date_order)
            except InputError as e:
                raise ValueError(str(e)) from None
            for n, parts, amount in pending:
                try:
                    rows.append((date_from_parts(parts, order), amount))
                except InputError as e:
                    raise ValueError(f"row {n}: {e}") from None
    except csv.Error as e:
        raise ValueError(f"cannot read {path!r}: CSV format problem ({e})") from None
    if stats is not None:
        stats["skipped"] = skipped
    if not rows:
        raise ValueError(f"no rows in {path!r}" + (f" (all {skipped} were skipped by --skip-where)" if skipped else ""))
    return aggregate_transactions(rows) if by_date else rows


def _clean(text: str) -> str:
    """Strip terminal control, bidi and zero-width characters from echoed input."""
    return "".join(ch for ch in text if ch.isprintable()
                   and unicodedata.category(ch) not in ("Cf",))


def _parse_inline(items, what: str) -> Dict[dt.date, float]:
    out: Dict[dt.date, float] = {}
    for inline in items or []:
        try:
            d, amt = inline.split("=", 1)
            q = parse_quarter_label(d)
            out[q] = dsum(out.get(q, 0.0), _amount(amt))
        except (ValueError, AttributeError):
            raise ValueError(f"bad {what} {_clean(repr(inline))}, expected YYYY-MM-DD=AMOUNT "
                             "or 2026Q1=AMOUNT") from None
    return out


def _fail(args, msg: str) -> int:
    msg = _clean(msg)
    print(f"gstwatch: {msg}", file=sys.stderr)
    if getattr(args, "json", False):
        print(json.dumps({"error": msg, "exit": 2, "not_tax_advice": True,
                          "schema_version": SCHEMA_VERSION}))
    return 2


_EXIT: "dict[str, int]" = {}


def main(argv: "list[str] | None" = None) -> int:
    try:
        return _main(argv)
    except BrokenPipeError:  # e.g. `gstwatch check ... | head`
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        return _EXIT.get("code", 0)  # keep the real answer (3 = register) for scripts
    except OSError as e:  # e.g. disk full / closed stdout while printing
        try:
            print(f"gstwatch: cannot write output ({type(e).__name__})", file=sys.stderr)
        except OSError:
            pass
        return 2


def _main(argv) -> int:
    _EXIT.clear()
    _Parser.argv_seen = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):  # never crash on a legacy console code page
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass
    ap = _Parser(
        prog="gstwatch",
        description="GST/HST small-supplier threshold tests and dates (CRA rules, re-verified 2026-11-08). "
                    "Not tax advice.",
        epilog=f"gstwatch {__version__}, maintained by {__author__}; MIT license.",
    )
    ap.add_argument("--version", action="version", version=f"gstwatch {__version__}")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="run the small-supplier tests over your quarters")
    c.add_argument("csvfile", nargs="?", help="CSV file, or - for standard input: quarter_end,amount "
                   "or date,amount (transactions; optional associates, excluded columns)")
    c.add_argument("--quarter", action="append", metavar="YYYY-MM-DD=AMOUNT",
                   help="inline quarter (repeatable; combined with csvfile if given)")
    c.add_argument("--associates", action="append", metavar="2026Q1=AMOUNT",
                   help="add an associates' taxable supplies for that quarter (repeatable). "
                        "CRA counts associates only if associated at the START of that quarter")
    c.add_argument("--excluded", action="append", metavar="2026Q1=AMOUNT",
                   help="subtract financial-services / capital-property / goodwill sales "
                        "that CRA excludes from the test (repeatable)")
    c.add_argument("--date-column", metavar="NAME",
                   help="accounting-software export: name of the column holding each sale's date "
                        "(ISO, '2026-03-31 23:30:00 -0400', '31 Mar 2026'); rows are summed into quarters")
    c.add_argument("--amount-column", metavar="NAME",
                   help="name of the column to add up. Pick the one BEFORE tax (e.g. a subtotal), "
                        "not a total that includes GST/HST")
    c.add_argument("--date-order", choices=["dmy", "mdy"],
                   help="how to read dates like 03/04/2026 (day first or month first); needed only "
                        "when the file does not make it obvious")
    c.add_argument("--skip-where", action="append", metavar="COLUMN=VALUE",
                   help="leave out rows whose column equals the value, e.g. \"Financial Status=voided\" "
                        "(repeatable; case-insensitive). Unpaid, voided or draft orders are your call")
    c.add_argument("--table", action="store_true",
                   help="also print the quarter-by-quarter working (trailing 2/3/4-quarter totals)")
    c.add_argument("--crossing", type=_date, help="exact date of the supply that crossed the threshold")
    c.add_argument("--first-supply", type=_date, metavar="YYYY-MM-DD",
                   help="multi-quarter test: date of your first supply after small-supplier "
                        "status ended (CRA's effective date is no later than this)")
    c.add_argument("--entity", choices=["supplier", "psb", "charity"], default="supplier",
                   help="supplier = C$30,000 (default); psb = public service body, C$50,000; "
                        "charity = unsupported (different tests)")
    c.add_argument("--taxi", action="store_true",
                   help="taxi/ride-share operator: must register even if a small supplier")
    c.add_argument("--as-of", type=_date, help="today's date, to show days left / overdue "
                   "(never read from the clock, so output is reproducible)")
    c.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="machine-readable output (also accepted before the subcommand)")

    f = sub.add_parser("freq", help="assigned filing frequency from annualized supplies")
    f.add_argument("annualized", type=str, help="worldwide taxable supplies, annualized")
    f.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    r = sub.add_parser("records", help="6-year record retention deadline for a transaction")
    r.add_argument("transaction", type=_date)
    r.add_argument("--period-end", type=_date, metavar="YYYY-MM-DD",
                   help="end of your fiscal year, if not the calendar year (the later date wins)")
    r.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    args = ap.parse_args(argv)

    if args.cmd == "freq":
        try:
            args.annualized = parse_amount(args.annualized)
            band = filing_frequency(args.annualized)
        except InputError as e:
            return _fail(args, str(e))
        if args.json:
            print(json.dumps({"annualized": args.annualized, "filing_frequency": band,
                              "schema_version": SCHEMA_VERSION, "gstwatch_version": __version__}))
        else:
            print(f"C${args.annualized:,.0f} annualized -> {band} filing "
                  "(CRA assigned periods: annual <= 1.5M, quarterly <= 6M, monthly above)")
        return 0

    if args.cmd == "records":
        try:
            deadline = retention_deadline(args.transaction, args.period_end)
        except InputError as e:
            return _fail(args, str(e))
        if args.json:
            print(json.dumps({"transaction": args.transaction.isoformat(),
                              "retain_until": deadline.isoformat(),
                              "schema_version": SCHEMA_VERSION,
                              "gstwatch_version": __version__}))
        else:
            print(f"Transaction {args.transaction.isoformat()}: keep records until "
                  f"{deadline.isoformat()} (6 years from the end of the year it relates to)")
        return 0

    if args.entity == "charity":
        return _fail(args, "charities and public institutions use different tests (C$250,000 gross "
                           "revenue and C$50,000 taxable supplies); not supported. Ask your accountant.")
    quarters: List[Quarter] = []
    stats: Dict[str, int] = {}
    if not args.csvfile and (args.date_column or args.amount_column or args.date_order or args.skip_where):
        return _fail(args, "--date-column, --amount-column, --date-order and --skip-where apply to a CSV file; "
                           "give the file name (or - for standard input)")
    try:
        if args.csvfile:
            quarters.extend(load_quarters(args.csvfile, args.date_column, args.amount_column,
                                          args.date_order, args.skip_where, stats))
        for item in args.quarter or []:
            try:
                d, amt = item.split("=", 1)
                quarters.append((parse_quarter_label(d), _amount(amt)))
            except ValueError as e:
                raise ValueError(f"bad --quarter {_clean(repr(item))} ({e}); expected "
                                 "YYYY-MM-DD=AMOUNT or 2026Q1=AMOUNT") from None
        assoc = _parse_inline(args.associates, "--associates")
        excl = _parse_inline(args.excluded, "--excluded")
    except ValueError as e:
        return _fail(args, str(e))
    if not quarters:
        return _fail(args, "give a CSV file or at least one --quarter")

    adj_notes: List[str] = []
    if args.csvfile and stats.get("skipped"):
        adj_notes.append(f"{stats['skipped']} row(s) left out by --skip-where "
                         + "; ".join(_clean(x) for x in args.skip_where))
    if assoc or excl:
        # duplicates among quarters are still rejected by evaluate(); adjust the first only
        adjusted: List[Quarter] = []
        seen = set()
        for d, a in quarters:
            if d in seen:
                adjusted.append((d, a))
                continue
            seen.add(d)
            adjusted.append((d, dsum(a, assoc.get(d, 0.0), -excl.get(d, 0.0))))
        for label, m in (("associates", assoc), ("excluded", excl)):
            missing = [q for q in m if q not in seen]
            if missing:
                return _fail(args, f"--{label} given for a quarter with no --quarter amount: "
                             + ", ".join(q.isoformat() for q in missing))
        quarters = adjusted
        if assoc:
            adj_notes.append("associates' supplies added: " + ", ".join(
                f"{q.isoformat()} +C${v:,.2f}" for q, v in sorted(assoc.items()))
                + " (valid only if associated at the beginning of that quarter)")
        if excl:
            adj_notes.append("excluded supplies subtracted: " + ", ".join(
                f"{q.isoformat()} -C${v:,.2f}" for q, v in sorted(excl.items())))
    try:
        status = evaluate(quarters, crossing_date=args.crossing, entity=args.entity,
                          taxi=args.taxi, as_of=args.as_of, first_supply=args.first_supply)
    except InputError as e:
        return _fail(args, str(e))
    status.notes[0:0] = adj_notes
    must = (not status.small_supplier) or status.taxi_must_register
    _EXIT["code"] = 3 if must else 0
    if args.json:
        out = status.as_dict()
        out["schema_version"] = SCHEMA_VERSION
        out["gstwatch_version"] = __version__
        if args.table:
            out["table"] = quarter_table(quarters, status.threshold)
        print(json.dumps(out, indent=2))
        return _EXIT["code"]

    print(f"Total across {len(quarters)} quarter(s): C${status.total:,.2f}")
    print(f"Threshold used: C${status.threshold:,.0f} ({status.entity})")
    print(f"Filing frequency (assigned): {status.filing_frequency} [{status.filing_basis}]")
    label = "YES" if status.small_supplier else "NO"
    if status.small_supplier and status.taxi_must_register:
        label += " (under the threshold, BUT taxi/ride-share operators must register anyway)"
    print(f"Small supplier: {label} (trigger: {status.trigger})")
    if status.effective_date and status.register_by:
        print(f"Effective registration date: {status.effective_date.isoformat()}"
              f"  [{status.effective_basis}]")
        print(f"Register by:                {status.register_by.isoformat()} "
              "(29 days from the effective date)")
        if status.register_by_earliest and status.register_by_earliest != status.register_by:
            print(f"Earliest possible register-by: {status.register_by_earliest.isoformat()} "
                  "(plan to this date if you are unsure)")
    if status.days_to_register is not None:
        print(f"Days to register: {status.days_to_register}" +
              ("  ** OVERDUE **" if status.overdue else
               "  ** POSSIBLY OVERDUE if the crossing supply was early in the quarter **"
               if status.possibly_overdue else ""))
    for note in status.notes:
        print(f"  - {_clean(note)}")
    if args.table:
        print("\nQuarter-by-quarter working (trailing totals; '*' = over the threshold):")
        print(f"  {'Quarter end':<12} {'Amount':>14} {'Last 2':>14} {'Last 3':>14} {'Last 4':>14}  Trips")
        for row in quarter_table(quarters, status.threshold):
            cells = [row["amount"], row["last_2_quarters"], row["last_3_quarters"], row["last_4_quarters"]]
            marks = [f"{c:>13,.2f}" + ("*" if c > status.threshold else " ") for c in cells]
            tail = (row["over_threshold"][0] if row["over_threshold"] else "") + (
                "  (assumed C$0)" if row["assumed_zero"] else "")
            print(f"  {row['quarter_end']:<12} " + " ".join(marks) + "  " + tail)
    print("\nPublished CRA rules applied to your numbers - not tax advice.")
    # 3 = registration required / exceeded, useful for scripts that treat it distinctly
    return 3 if must else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
