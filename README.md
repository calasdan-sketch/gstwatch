# gstwatch

**The C$30,000 GST/HST threshold has two tests, a 29-day registration clock, and a 6-year memory.** `gstwatch` applies Canada's published small-supplier rules to your quarterly revenue and tells you: are you still a small supplier, when registration takes effect, when you must register by, what filing frequency CRA will assign, and how long to keep records.

Rules verified against Canada.ca on 2026-11-07. **Not tax advice and not a substitute for a CPA or CRA** — it applies published rules to your numbers and shows its work.

## Install

```bash
pip install gstwatch
```

## Check the threshold

```bash
gstwatch check --quarter 2025-12-31=8000 --quarter 2026-03-31=8000 \
               --quarter 2026-06-30=8000 --quarter 2026-09-30=8000

# or from a CSV of quarter totals: quarter_end,amount
gstwatch check quarters.csv

# or straight from an export of dated transactions: date,amount (summed into calendar quarters)
gstwatch check sales.csv
```

CSV files may be comma-, semicolon- or tab-separated (French-locale Excel exports work). Money is parsed strictly: `1,234.56`, `12 500,50` and `C$5,000` are fine; an ambiguous `12,50` (12.50 or 1,250?) is **rejected**, never guessed. Optional `associates` and `excluded` columns (or `--associates 2026Q1=AMT` / `--excluded 2026Q1=AMT`) add associates' supplies and subtract the supplies CRA excludes (financial services, capital property, goodwill); you remain responsible for which items qualify. Refund rows may be negative in a transaction CSV and are netted within their quarter; whether CRA nets credit notes this way is unverified.

Both CRA tests are run:

1. **Single quarter** — one calendar quarter alone over C$30,000: you must charge GST/HST on the supply that takes you over; effective registration is no later than that supply; **register within 29 days**. Pass `--crossing YYYY-MM-DD` if you know the exact supply date; otherwise the output gives the range: the latest possible register-by (quarter end + 29 days) **and** the earliest possible (quarter start + 29 days), and flags "possibly overdue" against the earliest.
2. **Four-or-fewer consecutive quarters** — total over C$30,000: small-supplier status ends at the **end of the month following** the quarter in which you crossed; collect from the first supply after that; register within 29 days of that effective date. CRA's effective date is "no later than" your first supply after status ended, so the end-of-month date shown is the earliest possible: pass `--first-supply YYYY-MM-DD` to compute from the real date.

Exit codes: `0` still a small supplier, `3` registration required (also taxi/ride-share operators) (distinct on purpose, so scripts can branch), `2` usage error. `--json` for automation.

Useful options: quarters can be written `2026Q1=8000`; `--as-of 2026-11-07` adds days-left / overdue; `--entity psb` uses the C$50,000 public-service-body threshold; `--taxi` flags taxi/ride-share operators (CRA: must register even if small). While you are still under, the output tells you **how much more you can supply next quarter** before either test trips. If both tests trip, the earliest effective date is reported.

Input is validated and rejected, never guessed: NaN/infinite/negative amounts, duplicate quarters, dates that are not calendar quarter ends, and `--crossing` dates outside the offending quarter all exit `2`. Quarters you skip are assumed C$0 and listed. Charities/public institutions (different tests) are refused.

## Filing frequency

```bash
gstwatch freq 1400000     # -> annual   (assigned: annual <= C$1.5M)
gstwatch freq 7000000     # -> monthly  (quarterly up to C$6M, monthly above)
```

## Record retention

```bash
gstwatch records 2026-05-10   # -> keep records until 2032-12-31
gstwatch records 2026-05-10 --period-end 2027-03-31   # fiscal year ending Mar 31 -> 2033-03-31
```

Six years from the **end of the year** the record relates to (calendar year by default; with `--period-end` the later of the calendar and fiscal answers is shown. canada.ca does not say which "year" it means for GST/HST, so this is unverified).

`check` assigns filing frequency from the trailing four calendar quarters; with under four quarters it is labelled an ESTIMATE (CRA bases it on actual annual taxable revenue, and the periods do not auto-adjust if revenue falls).

## How it compares

| | gstwatch | gst-hst-tracker (OSS CLI) | Online threshold calculators (e.g. yourincomecalculator.com) | Accounting software (Wave, QuickBooks Canada, FreshBooks) |
|---|---|---|---|---|
| Single-quarter test | yes | no (its README says it does not implement it) | not clearly shown | unverified |
| Four-quarter test | yes | yes | yes | unverified |
| Effective date + 29-day register-by | yes (with earliest/latest range) | no | fixed text only | unverified |
| Reads dated transactions | yes (`date,amount` CSV) | yes (needs province, kind, description) | no, 4 quarter boxes | yes (it is the books) |
| Free, offline, scriptable (exit codes, JSON) | yes | yes | no | no |
| Books, ITCs, net tax, filing | **no** | partly (net tax, ITCs) | no | yes |

Checked 2026-11-07: gst-hst-tracker README (github.com/jasveerai88/gst-hst-tracker) and the yourincomecalculator.com registration page, as fetched. Accounting-software columns are not verified: I did not find these features in docs searched, which is not proof they are absent.

Verified against canada.ca on 2026-11-07: the C$30,000 single-quarter and four-quarter tests, 29-day registration, associates' revenue included (if associated at the start of the quarter), financial services and capital property/goodwill excluded, C$50,000 public service body threshold, taxi/ride-share rule, filing bands (<= C$1.5M annual, <= C$6M quarterly, periods do not auto-adjust), 6-year records. Not found on the pages fetched, so unverified: any CRA online calculator, whether credit notes net against a quarter, and competitor features.

## Benchmark

`PYTHONPATH=src python3 bench/bench.py` compares the engine with an independent brute-force restatement of the two tests on 20,000 seeded random histories (0 mismatches, committed in `bench/results.json`) and times it (indicative, machine-dependent): 400 quarters in about 3 ms; 100,000 transaction rows load in about 1.5 s. The oracle was written by the same author from the same reading of the rules, so it checks the code, not CRA's interpretation.

## What's modeled — and what isn't

Modeled: the two threshold tests, 29-day registration clock, effective-date rules (single vs rolling, with earliest/latest when the exact supply date is unknown), assigned filing bands, 6-year retention. Years outside 1900-2100 are rejected.

**Not** modeled: deciding which supplies are inclusions/exclusions or whether parties are associates (you supply the amounts; the tool only adds/subtracts them), voluntary-registration date elections and the one-year minimum, deregistration decisions, and filing obligations themselves. The threshold test includes worldwide taxable supplies (including zero-rated) per CRA's description — bring your accountant for the exclusions.

Sources: [when to register and start charging](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/when-register-charge.html) · [assigned reporting periods](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/gst-hst-account/change-account.html) · [records to keep](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/calculate-prepare-report/gst-hst-records-keep.html)

## License

MIT-style: use it, ship it, no warranty.
