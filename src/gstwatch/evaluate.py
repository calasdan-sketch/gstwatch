"""Small-supplier tests and the dates CRA's rules produce.

Verified October 2026, re-verified 2026-11-08 (canada.ca):
* C$30,000 threshold: exceeded in ONE calendar quarter, or across FOUR OR
  FEWER consecutive calendar quarters (worldwide taxable supplies incl.
  zero-rated supplies and associates', minus the listed exclusions).
* Single-quarter exceedance: charge GST/HST on the supply that takes you over;
  effective registration no later than that supply; register within 29 days.
* Rolling exceedance: small-supplier status ends the END OF THE MONTH
  FOLLOWING the quarter in which the threshold was exceeded; collect from the
  first supply after that; register within 29 days of the effective date.
* Assigned filing periods: annual at <= C$1.5M; quarterly > C$1.5M to C$6M;
  monthly > C$6M.
* Records: keep 6 years from the end of the year to which they relate.
* Public service bodies (not charities/public institutions): threshold C$50,000.
* Taxi / ride-share operators must register even if small suppliers.
* Revenue of associates counts; financial services and capital property sales
  are excluded (NOT modeled: you supply the already-adjusted quarterly figure).
"""
from __future__ import annotations

import calendar
import datetime as dt
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

THRESHOLD = 30000
PSB_THRESHOLD = 50000
REGISTER_DAYS = 29
FILING_ANNUAL_MAX = 1_500_000
FILING_QUARTERLY_MAX = 6_000_000
MAX_QUARTERS = 400
MAX_AMOUNT = 1e15
MAX_TRANSACTIONS = 200_000
MIN_YEAR, MAX_YEAR = 1900, 2100
MAX_DATE_CHARS, MAX_AMOUNT_CHARS = 64, 64


def _shorten(text: str, n: int = 40) -> str:
    return text if len(text) <= n else text[:n] + "..."

QUARTER_END_MD = {(3, 31): 1, (6, 30): 2, (9, 30): 3, (12, 31): 4}

Quarter = Tuple[dt.date, float]  # (quarter end, taxable supplies)


def dec(x: float) -> Decimal:
    """Exact decimal for the number as written (repr round-trips), so sums and the
    strictly-greater-than tests are exact: 10000.10 + 19999.90 is 30000, not 30000.000000000004."""
    return Decimal(repr(float(x)))


def dsum(*xs: float) -> float:
    """Add money amounts exactly (in decimal) and return the nearest float."""
    return float(sum((dec(x) for x in xs), Decimal(0)))


class InputError(ValueError):
    """Bad user data. Always raised instead of guessing (fail closed)."""


def quarter_end(year: int, quarter: int) -> dt.date:
    if quarter not in (1, 2, 3, 4):
        raise InputError("quarter must be 1-4")
    month = quarter * 3
    return dt.date(year, month, calendar.monthrange(year, month)[1])


def parse_quarter_label(text: str) -> dt.date:
    """Accept 2026-03-31, 2026Q1, 2026-Q1 (case-insensitive)."""
    t = text.strip()
    m = re.fullmatch(r"(\d{4})-?[Qq]([1-4])", t)
    if m:
        return quarter_end(int(m.group(1)), int(m.group(2)))
    try:
        return dt.date.fromisoformat(t)
    except ValueError:
        raise InputError(f"expected YYYY-MM-DD or YYYYQn, got {text!r}") from None


def next_month_end(d: dt.date) -> dt.date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return dt.date(year, month, calendar.monthrange(year, month)[1])


def _qidx(d: dt.date) -> int:
    return d.year * 4 + QUARTER_END_MD[(d.month, d.day)] - 1


def _qdate(idx: int) -> dt.date:
    return quarter_end(idx // 4, idx % 4 + 1)


_PLAIN = re.compile(r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]{1,3})?")
_EN_THOUSANDS = re.compile(r"[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?")
_FR_THOUSANDS = re.compile(r"[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})*(?:,[0-9]{1,2})?")
_CURRENCY_PREFIX = re.compile(r"^(?:CAD|CA\$|C\$|\$)\s*", re.IGNORECASE)
_CURRENCY_SUFFIX = re.compile(r"\s*(?:CAD|\$)$", re.IGNORECASE)


def parse_amount(text: str) -> float:
    """Parse a money string strictly; ambiguous or odd forms are REJECTED, never guessed.

    Accepted: 1234.56, 1,234.56, 12 500,50 (fr-CA: space groups + decimal comma),
    optional leading minus or accounting parentheses ``(1,234.56)``, optional C$ / $ / CAD
    marker. Rejected: 12,50 (could be
    12.50 or 1250), 1_000, 0x10, non-ASCII digits, stray letters, NaN/inf.
    """
    t = text.strip()
    if len(t) > MAX_AMOUNT_CHARS:
        raise InputError(f"bad amount {_shorten(text)!r}")
    if _PLAIN.fullmatch(t):  # fast path: the overwhelmingly common plain "1234.56"
        v = float(t)
        if math.isfinite(v):
            return v
    neg = False
    if len(t) > 2 and t[0] == "(" and t[-1] == ")":  # accounting negative: (1,234.56)
        neg, t = True, t[1:-1].strip()
    elif t.startswith("-") or t.startswith("\u2212"):
        neg, t = True, t[1:].strip()
    t = _CURRENCY_PREFIX.sub("", t)
    t = _CURRENCY_SUFFIX.sub("", t).strip()
    if _PLAIN.fullmatch(t):
        v = float(t)
    elif _EN_THOUSANDS.fullmatch(t):
        v = float(t.replace(",", ""))
    elif _FR_THOUSANDS.fullmatch(t) and re.search(r"[ \u00a0\u202f]", t):
        v = float(re.sub(r"[ \u00a0\u202f]", "", t).replace(",", "."))
    else:
        hint = " (ambiguous comma: write 12.50 or 1,250)" if re.fullmatch(r"[0-9]+,[0-9]{1,2}", t) else ""
        raise InputError(f"bad amount {text!r}{hint}")
    if not math.isfinite(v):
        raise InputError(f"bad amount {text!r}")
    return -v if neg else v


_TIME_TAIL = (r"(?:[T\s]+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?\s*(?:[AaPp][Mm])?"
              r"\s*(?:Z|[A-Za-z]{3,4}|[+-][0-9]{2}:?[0-9]{2})?)?")
_DATE_SPLIT = re.compile(r"(?P<d>.+?)" + _TIME_TAIL)
_ISO = re.compile(r"([0-9]{4})[-/]([0-9]{2})[-/]([0-9]{2})")
_SLASH = re.compile(r"([0-9]{1,2})[/.-]([0-9]{1,2})[/.-]([0-9]{4})")
_DMON = re.compile(r"([0-9]{1,2})[ -]([A-Za-z]{3,9})\.?,?[ -]([0-9]{4})")
_MOND = re.compile(r"([A-Za-z]{3,9})\.? ([0-9]{1,2}),? ([0-9]{4})")
_MONTHS = {m: i for i, names in enumerate(
    ["jan january", "feb february", "mar march", "apr april", "may", "jun june", "jul july",
     "aug august", "sep sept september", "oct october", "nov november", "dec december"], 1)
    for m in names.split()}
AmbiguousDate = Tuple[int, int, int]  # (first, second, year) of a numeric d/m/y or m/d/y date


@lru_cache(maxsize=8192)  # exports repeat the same dates thousands of times
def parse_date_cell(text: str) -> "dt.date | AmbiguousDate":
    """Read one date from an export, strictly (English month names only).

    Returns a ``date`` when the text is unambiguous: ``2026-03-31``, ``2026/03/31``,
    ISO or Shopify-style stamps with a time and zone (``2026-03-31 23:30:00 -0400`` is
    taken as written, the date in the file), ``31 Mar 2026``, ``Mar 31, 2026``. A numeric
    ``03/04/2026`` could be March 4 or April 3, so it returns ``(3, 4, 2026)`` for
    ``resolve_ambiguous`` to settle across the whole file. Anything else raises InputError.
    """
    t = text.strip()
    if len(t) == 10 and t[4] == "-" and t[7] == "-" and t[:4].isascii() and t[:4].isdigit() \
            and t[5:7].isdigit() and t[8:].isdigit() and t[5:7].isascii() and t[8:].isascii():
        try:  # fast path: plain YYYY-MM-DD, the overwhelmingly common case
            return dt.date(int(t[:4]), int(t[5:7]), int(t[8:]))
        except ValueError:
            raise InputError(f"not a real calendar date: {text!r}") from None
    if len(t) > MAX_DATE_CHARS:  # also keeps the patterns below from ever being slow
        raise InputError(f"unrecognised date {_shorten(text)!r}")
    m = _DATE_SPLIT.fullmatch(t)
    core = m.group("d") if m else t
    try:
        iso = _ISO.fullmatch(core)
        if iso:
            return dt.date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        sl = _SLASH.fullmatch(core)
        if sl:
            return (int(sl.group(1)), int(sl.group(2)), int(sl.group(3)))
        dm = _DMON.fullmatch(core)
        if dm and dm.group(2).lower() in _MONTHS:
            return dt.date(int(dm.group(3)), _MONTHS[dm.group(2).lower()], int(dm.group(1)))
        md = _MOND.fullmatch(core)
        if md and md.group(1).lower() in _MONTHS:
            return dt.date(int(md.group(3)), _MONTHS[md.group(1).lower()], int(md.group(2)))
    except ValueError:  # e.g. 2026-02-30
        raise InputError(f"not a real calendar date: {text!r}") from None
    raise InputError(f"unrecognised date {text!r}; use YYYY-MM-DD (or 31 Mar 2026, or "
                     "03/31/2026 together with --date-order)")


def resolve_ambiguous(parts: Sequence[AmbiguousDate], order: Optional[str]) -> str:
    """Pick 'dmy' or 'mdy' for a whole file; fail closed unless it is certain.

    ``order`` is the user's explicit choice (or None). Without it, the order is accepted
    only when at least one date can be read just one way (a part above 12) and none
    contradicts it.
    """
    if order in ("dmy", "mdy"):
        return order
    only_d = any(a > 12 >= b for a, b, _ in parts)   # 25/03/2026 can only be day-first
    only_m = any(b > 12 >= a for a, b, _ in parts)   # 03/25/2026 can only be month-first
    if only_d and only_m:
        raise InputError("dates mix day-first and month-first (e.g. 25/03/2026 and 03/25/2026); "
                         "fix the file or pass --date-order")
    if only_d:
        return "dmy"
    if only_m:
        return "mdy"
    raise InputError("dates like 03/04/2026 could be March 4 or April 3; add --date-order mdy "
                     "(month first) or --date-order dmy (day first)")


def date_from_parts(parts: AmbiguousDate, order: str) -> dt.date:
    a, b, y = parts
    day, month = (a, b) if order == "dmy" else (b, a)
    try:
        return dt.date(y, month, day)
    except ValueError:
        raise InputError(f"{a}/{b}/{y} is not a real date read as {order}") from None


def to_quarter_end(d: dt.date) -> dt.date:
    """Calendar quarter end containing date d."""
    return quarter_end(d.year, (d.month - 1) // 3 + 1)


def aggregate_transactions(rows: Sequence[Tuple[dt.date, float]]) -> List[Quarter]:
    """Sum dated transactions (refund rows may be negative) into calendar quarters."""
    if len(rows) > MAX_TRANSACTIONS:
        raise InputError(f"too many transaction rows (max {MAX_TRANSACTIONS})")
    cents: Dict[Tuple[int, int], int] = {}     # exact whole cents (the normal case)
    extra: Dict[Tuple[int, int], Decimal] = {}  # anything with sub-cent digits, kept exact too
    for d, a in rows:
        if not math.isfinite(a):
            raise InputError(f"amount on {d.isoformat()} is not a finite number")
        if abs(a) > MAX_AMOUNT:
            raise InputError(f"amount on {d.isoformat()} is implausibly large")
        k = (d.year, (d.month - 1) // 3 + 1)  # cheap key; dates built once per quarter below
        c = round(a * 100)
        if c / 100 == a:   # a is the float nearest to a whole number of cents: add as an exact integer
            cents[k] = cents.get(k, 0) + c
        else:
            extra[k] = extra.get(k, Decimal(0)) + dec(a)
            cents.setdefault(k, 0)
    return sorted((quarter_end(y, q), float(Decimal(c) / 100 + extra.get((y, q), Decimal(0))))
                  for (y, q), c in cents.items())


def validate_quarters(quarters: Sequence[Quarter]) -> List[Quarter]:
    """Reject NaN/inf/negative/duplicate/non-calendar-quarter data."""
    if not quarters:
        raise InputError("no quarters supplied")
    if len(quarters) > MAX_QUARTERS:
        raise InputError(f"too many quarters (max {MAX_QUARTERS})")
    seen = set()
    for d, a in quarters:
        if not (MIN_YEAR <= d.year <= MAX_YEAR):
            raise InputError(f"{d.isoformat()}: year must be {MIN_YEAR}-{MAX_YEAR}")
        if (d.month, d.day) not in QUARTER_END_MD:
            raise InputError(
                f"{d.isoformat()} is not a calendar quarter end (Mar 31, Jun 30, Sep 30, Dec 31); "
                "CRA's test uses calendar quarters")
        if not math.isfinite(a):
            raise InputError(f"amount for {d.isoformat()} is not a finite number")
        if a < 0:
            raise InputError(f"amount for {d.isoformat()} is negative; net refunds/credits "
                             "into the quarter before entering it")
        if a > MAX_AMOUNT:
            raise InputError(f"amount for {d.isoformat()} is implausibly large")
        if d in seen:
            raise InputError(f"duplicate quarter {d.isoformat()}; give one total per quarter")
        seen.add(d)
    return sorted(quarters, key=lambda q: q[0])


@dataclass
class Status:
    total: float
    small_supplier: bool
    trigger: str                       # none | single-quarter | rolling
    crossing_quarter: Optional[dt.date] = None
    window: List[dt.date] = field(default_factory=list)
    window_total: float = 0.0
    effective_date: Optional[dt.date] = None
    register_by: Optional[dt.date] = None
    effective_earliest: Optional[dt.date] = None
    register_by_earliest: Optional[dt.date] = None
    effective_basis: str = ""
    filing_frequency: str = ""
    filing_basis: str = ""
    threshold: float = THRESHOLD
    entity: str = "supplier"
    taxi_must_register: bool = False
    gaps: List[dt.date] = field(default_factory=list)
    next_quarter: Optional[dt.date] = None
    next_quarter_headroom: Optional[float] = None
    days_to_register: Optional[int] = None
    overdue: Optional[bool] = None
    possibly_overdue: Optional[bool] = None
    notes: List[str] = field(default_factory=list)

    def as_dict(self):
        iso = lambda d: d.isoformat() if d else None
        return {
            "total": self.total,
            "small_supplier": self.small_supplier,
            "trigger": self.trigger,
            "threshold": self.threshold,
            "entity": self.entity,
            "taxi_must_register": self.taxi_must_register,
            "crossing_quarter": iso(self.crossing_quarter),
            "window": [d.isoformat() for d in self.window],
            "window_total": self.window_total,
            "effective_date": iso(self.effective_date),
            "register_by": iso(self.register_by),
            "effective_date_earliest": iso(self.effective_earliest),
            "register_by_earliest": iso(self.register_by_earliest),
            "effective_date_basis": self.effective_basis,
            "days_to_register": self.days_to_register,
            "overdue": self.overdue,
            "possibly_overdue": self.possibly_overdue,
            "filing_frequency": self.filing_frequency,
            "filing_basis": self.filing_basis,
            "assumed_zero_quarters": [d.isoformat() for d in self.gaps],
            "next_quarter": iso(self.next_quarter),
            "next_quarter_headroom": self.next_quarter_headroom,
            "notes": self.notes,
            "not_tax_advice": True,
        }


def evaluate(quarters: Sequence[Quarter],
             threshold: float = THRESHOLD,
             crossing_date: Optional[dt.date] = None,
             entity: str = "supplier",
             taxi: bool = False,
             as_of: Optional[dt.date] = None,
             first_supply: Optional[dt.date] = None) -> Status:
    """Apply both small-supplier tests to (calendar quarter end, amount) pairs.

    Quarters missing between the first and last given are assumed 0 and listed
    in ``gaps``. If both tests trip, the one with the EARLIEST effective date wins.
    """
    qs = validate_quarters(quarters)
    if entity == "psb" and threshold == THRESHOLD:
        threshold = PSB_THRESHOLD
    thr = dec(threshold)
    total = float(sum((dec(a) for _, a in qs), Decimal(0)))
    amt = {_qidx(d): dec(a) for d, a in qs}
    lo, hi = min(amt), max(amt)
    gaps = [_qdate(i) for i in range(lo, hi + 1) if i not in amt]
    get = lambda i: amt.get(i, Decimal(0))

    # trailing four calendar quarters ending at the latest quarter given
    trailing = sum((get(i) for i in range(hi - 3, hi + 1)), Decimal(0))
    if hi - lo + 1 >= 4:
        freq, basis = filing_frequency(float(trailing)), "trailing 4 calendar quarters"
    else:
        freq, basis = filing_frequency(float(trailing * 4 / (hi - lo + 1))), \
            f"ESTIMATE: {hi - lo + 1} quarter(s) scaled to a year (CRA uses actual annual revenue)"

    common: Dict[str, Any] = dict(total=total, filing_frequency=freq, filing_basis=basis, threshold=threshold,
                  entity=entity, taxi_must_register=taxi, gaps=gaps)
    notes: List[str] = []
    if taxi:
        notes.append("taxi/ride-share operators must register for GST/HST even if a small "
                     "supplier (canada.ca, when-register-charge)")
    if gaps:
        notes.append("quarters not provided were assumed to be C$0: "
                     + ", ".join(g.isoformat() for g in gaps))

    # candidate 1: single quarter over the threshold (earliest)
    single: Optional[Tuple[int, dt.date, dt.date]] = None
    for i in sorted(amt):
        if amt[i] > thr:
            end = _qdate(i)
            if crossing_date is not None:
                if not (_qdate(i - 1) < crossing_date <= end):
                    raise InputError(f"--crossing {crossing_date.isoformat()} is not inside the "
                                     f"quarter ending {end.isoformat()} that exceeded the threshold")
            latest = crossing_date or end
            if crossing_date is None and as_of is not None and _qdate(i - 1) < as_of < end:
                latest = as_of  # quarter still running: the crossing supply has already happened
            single = (i, end, latest)
            break

    # candidate 2: 2-4 consecutive calendar quarters, earliest window end
    rolling: Optional[Tuple[int, int, Decimal]] = None
    for j in range(lo, hi + 1):
        for size in (2, 3, 4):
            s = sum((get(k) for k in range(j - size + 1, j + 1)), Decimal(0))
            if s > thr:
                rolling = (j, size, s)
                break
        if rolling:
            break

    pick = None
    if single and rolling:
        pick = "single" if single[2] <= next_month_end(_qdate(rolling[0])) else "rolling"
    elif single:
        pick = "single"
    elif rolling:
        pick = "rolling"

    if pick == "single":
        assert single is not None
        i, end, effective = single
        n = notes + [
            f"one quarter alone is C${amt[i]:,.2f} > C${threshold:,.0f}",
            "charge GST/HST on the supply that takes you over the threshold; "
            "effective registration is no later than that supply"
            + (f" (you supplied {crossing_date.isoformat()})" if crossing_date else
               " — pass --crossing YYYY-MM-DD if you know the exact supply date; "
               + ("using today (--as-of) as the latest possible date, because the quarter is still running"
                  if effective < end else "using the quarter end as the latest possible date")),
            f"register within {REGISTER_DAYS} days of the effective date",
        ]
        if crossing_date is not None and rolling:
            n.append("note: the multi-quarter test would also have tripped, later; earliest wins")
        earliest = _qdate(i - 1) + dt.timedelta(days=1)
        if crossing_date is None:
            n.append(f"if the crossing supply was early in the quarter, the effective date could be "
                     f"as early as {earliest.isoformat()} (register by "
                     f"{(earliest + dt.timedelta(days=REGISTER_DAYS)).isoformat()}); "
                     "register-by shown is the LATEST possible")
        if first_supply is not None:
            n.append("--first-supply ignored: it only applies to the multi-quarter test")
        known = crossing_date is not None
        st = Status(small_supplier=False, trigger="single-quarter", crossing_quarter=end,
                    window=[end], window_total=float(amt[i]), effective_date=effective,
                    register_by=effective + dt.timedelta(days=REGISTER_DAYS),
                    effective_earliest=effective if known else earliest,
                    register_by_earliest=(effective if known else earliest) + dt.timedelta(days=REGISTER_DAYS),
                    effective_basis="supply date given" if known else (
                        "latest possible = today (--as-of); the quarter is still running"
                        if effective < end else "latest possible = quarter end"),
                    notes=n, **common)
    elif pick == "rolling":
        assert rolling is not None
        j, size, s = rolling
        end = _qdate(j)
        effective = next_month_end(end)
        n = notes + [
            f"{size} consecutive quarter(s) total C${s:,.2f} > C${threshold:,.0f}",
            "small-supplier status ends at the end of the month following the quarter "
            "in which the threshold was exceeded",
            "start charging on the first supply after that date; "
            f"register within {REGISTER_DAYS} days of the effective date",
        ]
        if crossing_date is not None:
            n.append("--crossing ignored: it only applies to the single-quarter test")
        basis = "earliest possible = end of the month following the quarter"
        status_end = effective
        if first_supply is not None:
            if first_supply <= status_end:
                raise InputError(f"--first-supply {first_supply.isoformat()} must be after "
                                 f"{status_end.isoformat()} (when small-supplier status ended)")
            effective, basis = first_supply, "first supply after status ended, as given"
            n.append(f"effective date set to your first supply after status ended: {first_supply.isoformat()}")
        else:
            n.append("effective date is no later than your first supply after "
                     f"{status_end.isoformat()}; shown is the earliest possible, so the true "
                     "register-by may be later (pass --first-supply YYYY-MM-DD)")
        st = Status(small_supplier=False, trigger="rolling", crossing_quarter=end,
                    window=[_qdate(k) for k in range(j - size + 1, j + 1)], window_total=float(s),
                    effective_date=effective,
                    register_by=effective + dt.timedelta(days=REGISTER_DAYS),
                    effective_earliest=status_end,
                    register_by_earliest=status_end + dt.timedelta(days=REGISTER_DAYS),
                    effective_basis=basis, notes=n, **common)
        if single and crossing_date is None:
            early = _qdate(single[0] - 1) + dt.timedelta(days=1)
            if st.effective_earliest is not None and early < st.effective_earliest:
                st.effective_earliest = early
                st.register_by_earliest = early + dt.timedelta(days=REGISTER_DAYS)
                st.notes.append(f"a single quarter also exceeded the threshold ({single[1].isoformat()}); "
                                f"if that supply came early in the quarter it would be earlier "
                                f"(as early as {early.isoformat()}): pass --crossing to settle it")
    else:
        # headroom: most the NEXT quarter can add without tripping any 1-4 quarter window
        nxt = hi + 1
        room = min(thr - sum((get(k) for k in range(nxt - size + 1, nxt)), Decimal(0))
                   for size in (1, 2, 3, 4))
        st = Status(small_supplier=True, trigger="none", next_quarter=_qdate(nxt),
                    next_quarter_headroom=float(max(Decimal(0), room)),
                    notes=notes + [
                        f"total C${total:,.2f} stays within C${threshold:,.0f} for both tests "
                        "(any single quarter, and 4-or-fewer consecutive quarters)",
                        f"room left: up to C${max(Decimal(0), room):,.2f} of taxable supplies in the "
                        f"quarter ending {_qdate(nxt).isoformat()} keeps you at or under "
                        f"C${threshold:,.0f} (exceeding means strictly more)"], **common)

    if st.trigger == "none":
        if first_supply is not None:
            st.notes.append("--first-supply ignored: you are still a small supplier")
        if crossing_date is not None:
            st.notes.append("--crossing ignored: no quarter exceeded the threshold")
    if as_of is not None and st.register_by:
        st.days_to_register = (st.register_by - as_of).days
        st.overdue = st.days_to_register < 0
        st.possibly_overdue = bool(st.register_by_earliest and as_of > st.register_by_earliest)
    if as_of is not None:
        last_end = _qdate(hi)
        if as_of < last_end:
            st.notes.append(f"the quarter ending {last_end.isoformat()} has not finished as of "
                            f"{as_of.isoformat()}: its figure is treated as the amount so far")
        elif _qdate(hi + 1) < as_of:
            st.notes.append(f"your data stops at the quarter ending {last_end.isoformat()}; later "
                            "quarters are missing (NOT counted as C$0), so this answer may be out of date")
    st.notes.append("filing frequency is an approximation: CRA assigns it from taxable supplies made in "
                    "Canada in your preceding fiscal year, not the worldwide figure used for the threshold "
                    "(canada.ca, change-account)")
    st.notes.append("Enter sales before GST/HST (canada.ca does not spell this out: unverified), in "
                    "Canadian dollars. Not modeled: which supplies are associates' or excluded, voluntary "
                    "registration, charities; enter already-adjusted figures.")
    return st


def quarter_table(quarters: Sequence[Quarter], threshold: float = THRESHOLD) -> List[Dict[str, Any]]:
    """Quarter-by-quarter working: amount, trailing 2/3/4-quarter totals, which test trips.

    Skipped quarters between the first and last are shown as assumed C$0.
    """
    qs = validate_quarters(quarters)
    amt = {_qidx(d): dec(a) for d, a in qs}
    thr = dec(threshold)
    lo, hi = min(amt), max(amt)
    rows: List[Dict[str, Any]] = []
    for i in range(lo, hi + 1):
        row: Dict[str, Any] = {"quarter_end": _qdate(i).isoformat(), "amount": float(amt.get(i, Decimal(0))),
                               "assumed_zero": i not in amt}
        flags = []
        if amt.get(i, Decimal(0)) > thr:
            flags.append("single-quarter")
        for size in (2, 3, 4):
            tot = sum((amt.get(k, Decimal(0)) for k in range(i - size + 1, i + 1)), Decimal(0))
            row[f"last_{size}_quarters"] = float(tot)
            if tot > thr:
                flags.append(f"{size}-quarter")
        row["over_threshold"] = flags
        rows.append(row)
    return rows


def filing_frequency(annualized: float) -> str:
    """CRA assigned reporting periods by worldwide taxable supplies."""
    if not math.isfinite(annualized) or annualized < 0:
        raise InputError("annual taxable supplies must be a finite, non-negative number")
    if annualized <= FILING_ANNUAL_MAX:
        return "annual"
    if annualized <= FILING_QUARTERLY_MAX:
        return "quarterly"
    return "monthly"


def _add_years(d: dt.date, n: int) -> dt.date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # Feb 29 -> Feb 28
        return d.replace(year=d.year + n, day=28)


def retention_deadline(transaction_date: dt.date,
                       period_end: Optional[dt.date] = None) -> dt.date:
    """Keep records 6 years from the END of the year they relate to.

    Default treats "year" as the calendar year. For a non-calendar fiscal year pass
    ``period_end`` (the end of that fiscal year); the LATER of the two dates is
    returned so the answer is never too early. (Whether CRA's "year" means calendar
    or fiscal year for GST/HST is not stated on the page: unverified.)
    """
    if not (MIN_YEAR <= transaction_date.year <= MAX_YEAR):
        raise InputError(f"transaction year must be {MIN_YEAR}-{MAX_YEAR}")
    base = dt.date(transaction_date.year + 6, 12, 31)
    if period_end is None:
        return base
    if period_end < transaction_date:
        raise InputError("--period-end is before the transaction date")
    if (period_end - transaction_date).days > 400:
        raise InputError("--period-end is more than a year after the transaction")
    if period_end.year > MAX_YEAR:
        raise InputError(f"period end year must be at most {MAX_YEAR}")
    return max(base, _add_years(period_end, 6))
