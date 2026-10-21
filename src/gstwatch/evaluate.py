"""Small-supplier tests and the dates CRA's rules produce.

Verified October 2026 (canada.ca):
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
"""
from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

THRESHOLD = 30000
REGISTER_DAYS = 29
FILING_ANNUAL_MAX = 1_500_000
FILING_QUARTERLY_MAX = 6_000_000

Quarter = Tuple[dt.date, float]  # (quarter end, taxable supplies)


def quarter_end(year: int, quarter: int) -> dt.date:
    month = quarter * 3
    return dt.date(year, month, calendar.monthrange(year, month)[1])


def next_month_end(d: dt.date) -> dt.date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return dt.date(year, month, calendar.monthrange(year, month)[1])


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
    filing_frequency: str = ""
    notes: List[str] = field(default_factory=list)

    def as_dict(self):
        return {
            "total": self.total,
            "small_supplier": self.small_supplier,
            "trigger": self.trigger,
            "crossing_quarter": self.crossing_quarter.isoformat() if self.crossing_quarter else None,
            "window": [d.isoformat() for d in self.window],
            "window_total": self.window_total,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "register_by": self.register_by.isoformat() if self.register_by else None,
            "filing_frequency": self.filing_frequency,
            "notes": self.notes,
        }


def evaluate(quarters: Sequence[Quarter],
             threshold: float = THRESHOLD,
             crossing_date: Optional[dt.date] = None) -> Status:
    """Apply both small-supplier tests to ordered (quarter_end, amount) pairs."""
    qs = sorted(quarters, key=lambda q: q[0])
    if not qs:
        raise ValueError("no quarters supplied")
    total = sum(amount for _, amount in qs)
    annualized = total * 4 if len(qs) < 4 else total
    freq = filing_frequency(annualized)

    # Test 1: a single quarter over the threshold
    for end, amount in qs:
        if amount > threshold:
            effective = crossing_date or end
            return Status(
                total=total, small_supplier=False, trigger="single-quarter",
                crossing_quarter=end, window=[end], window_total=amount,
                effective_date=effective,
                register_by=effective + dt.timedelta(days=REGISTER_DAYS),
                filing_frequency=freq,
                notes=[
                    f"one quarter alone is C${amount:,.2f} > C${threshold:,.0f}",
                    "charge GST/HST on the supply that takes you over the threshold; "
                    f"effective registration is no later than that supply"
                    + (f" (you supplied {crossing_date.isoformat()})" if crossing_date else
                       " — pass --crossing YYYY-MM-DD if you know the exact supply date; "
                       "using the quarter end as the best known date"),
                    f"register within {REGISTER_DAYS} days of the effective date",
                ],
            )

    # Test 2: four-or-fewer consecutive quarters together over the threshold
    best: Optional[Tuple[List[Quarter], float]] = None
    for size in range(2, 5):  # 2, 3, 4 consecutive quarters
        for i in range(len(qs) - size + 1):
            window = qs[i:i + size]
            s = sum(a for _, a in window)
            if s > threshold and (best is None or window[-1][0] < best[0][-1][0]):
                best = (window, s)
    if best:
        window, s = best
        crossing_end = window[-1][0]
        effective = next_month_end(crossing_end)
        return Status(
            total=total, small_supplier=False, trigger="rolling",
            crossing_quarter=crossing_end, window=[w[0] for w in window], window_total=s,
            effective_date=effective,
            register_by=effective + dt.timedelta(days=REGISTER_DAYS),
            filing_frequency=freq,
            notes=[
                f"{len(window)} consecutive quarter(s) total C${s:,.2f} > C${threshold:,.0f}",
                "small-supplier status ends at the end of the month following the quarter "
                "in which the threshold was exceeded",
                "start charging on the first supply after that date; "
                f"register within {REGISTER_DAYS} days of the effective date",
            ],
        )

    return Status(total=total, small_supplier=True, trigger="none", filing_frequency=freq,
                  notes=[f"total C${total:,.2f} stays within C${threshold:,.0f} "
                         "for both tests (any single quarter, and 4-or-fewer consecutive quarters)"])


def filing_frequency(annualized: float) -> str:
    """CRA assigned reporting periods by worldwide taxable supplies."""
    if annualized <= FILING_ANNUAL_MAX:
        return "annual"
    if annualized <= FILING_QUARTERLY_MAX:
        return "quarterly"
    return "monthly"


def retention_deadline(transaction_date: dt.date) -> dt.date:
    """Keep records 6 years from the END of the year they relate to."""
    return dt.date(transaction_date.year + 6, 12, 31)
