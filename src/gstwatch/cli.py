"""gstwatch CLI: threshold check, filing frequency, record retention dates."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from typing import List

from . import __version__
from .evaluate import Quarter, evaluate, filing_frequency, retention_deadline


def _date(text: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {text!r}")


def load_quarters(path: str) -> List[Quarter]:
    """CSV with columns quarter_end,amount (extra columns ignored)."""
    out: List[Quarter] = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            fields = {(f or "").strip().lower() for f in (reader.fieldnames or [])}
            if "quarter_end" not in fields or "amount" not in fields:
                raise ValueError("CSV needs quarter_end and amount columns")
            for row in reader:
                norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                out.append((dt.date.fromisoformat(norm["quarter_end"]),
                            float(norm["amount"].replace(",", "").replace("$", ""))))
    except FileNotFoundError:
        raise SystemExit(f"gstwatch: not found: {path}")
    if not out:
        raise SystemExit(f"gstwatch: no quarters in {path}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="gstwatch",
        description="GST/HST small-supplier threshold tests and dates (CRA rules, Oct 2026). "
                    "Not tax advice.",
    )
    ap.add_argument("--version", action="version", version=f"gstwatch {__version__}")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="run the small-supplier tests over your quarters")
    c.add_argument("csvfile", nargs="?", help="CSV: quarter_end,amount")
    c.add_argument("--quarter", action="append", metavar="YYYY-MM-DD=AMOUNT",
                   help="inline quarter (repeatable; combined with csvfile if given)")
    c.add_argument("--crossing", type=_date, help="exact date of the supply that crossed the threshold")
    c.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="machine-readable output (also accepted before the subcommand)")

    f = sub.add_parser("freq", help="assigned filing frequency from annualized supplies")
    f.add_argument("annualized", type=float, help="worldwide taxable supplies, annualized")
    f.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    r = sub.add_parser("records", help="6-year record retention deadline for a transaction")
    r.add_argument("transaction", type=_date)
    r.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    args = ap.parse_args(argv)

    if args.cmd == "freq":
        band = filing_frequency(args.annualized)
        if args.json:
            print(json.dumps({"annualized": args.annualized, "filing_frequency": band}))
        else:
            print(f"C${args.annualized:,.0f} annualized -> {band} filing "
                  "(CRA assigned periods: annual <= 1.5M, quarterly <= 6M, monthly above)")
        return 0

    if args.cmd == "records":
        deadline = retention_deadline(args.transaction)
        if args.json:
            print(json.dumps({"transaction": args.transaction.isoformat(),
                              "retain_until": deadline.isoformat()}))
        else:
            print(f"Transaction {args.transaction.isoformat()}: keep records until "
                  f"{deadline.isoformat()} (6 years from the end of the year it relates to)")
        return 0

    quarters: List[Quarter] = []
    if args.csvfile:
        try:
            quarters.extend(load_quarters(args.csvfile))
        except ValueError as e:
            print(f"gstwatch: {e}", file=sys.stderr)
            return 2
    for inline in args.quarter or []:
        try:
            d, amt = inline.split("=", 1)
            quarters.append((dt.date.fromisoformat(d), float(amt.replace(",", ""))))
        except (ValueError, AttributeError):
            print(f"gstwatch: bad --quarter {inline!r}, expected YYYY-MM-DD=AMOUNT", file=sys.stderr)
            return 2
    if not quarters:
        print("gstwatch: give a CSV file or at least one --quarter", file=sys.stderr)
        return 2

    status = evaluate(quarters, crossing_date=args.crossing)
    if args.json:
        print(json.dumps(status.as_dict(), indent=2))
        return 0 if status.small_supplier else 3

    print(f"Total across {len(quarters)} quarter(s): C${status.total:,.2f}")
    print(f"Filing frequency (assigned): {status.filing_frequency}")
    print(f"Small supplier: {'YES' if status.small_supplier else 'NO'} (trigger: {status.trigger})")
    if status.effective_date:
        print(f"Effective registration date: {status.effective_date.isoformat()}")
        print(f"Register by:                {status.register_by.isoformat()} "
              "(29 days from the effective date)")
    for note in status.notes:
        print(f"  - {note}")
    print("\nPublished CRA rules applied to your numbers — not tax advice.")
    # 3 = exceeded, useful for scripts that treat "needs registration" distinctly
    return 0 if status.small_supplier else 3


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
