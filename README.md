# gstwatch

**The C$30,000 GST/HST threshold has two tests, a 29-day registration clock, and a 6-year memory.** `gstwatch` applies Canada's published small-supplier rules to your quarterly revenue and tells you: are you still a small supplier, when registration takes effect, when you must register by, what filing frequency CRA will assign, and how long to keep records.

Rules verified against Canada.ca on 2026-11-08. **Not tax advice and not a substitute for a CPA or CRA** — it applies published rules to your numbers and shows its work.

## Install

```bash
pip install "gstwatch>=0.2"      # Python 3.9+, no other dependencies
```

The command is `gstwatch`; `python -m gstwatch` does the same. PyPI currently holds the older 0.1.0, which lacks most of what is described below: if `pip` says it cannot find `>=0.2`, 0.2.0 is not published yet, so install from the repository instead: `pip install git+https://github.com/calasdan-sketch/gstwatch`.

## Check the threshold

```bash
gstwatch check --quarter 2025-12-31=8000 --quarter 2026-03-31=8000 \
               --quarter 2026-06-30=8000 --quarter 2026-09-30=8000

# or from a CSV of quarter totals: quarter_end,amount
gstwatch check quarters.csv

# or straight from an export of dated transactions: date,amount (summed into calendar quarters)
gstwatch check sales.csv
```

### Straight from your accounting software or shop export

Export your sales (QuickBooks, Wave, Square, Shopify, a spreadsheet: any CSV), then tell `gstwatch` which columns hold the date and the amount:

```bash
gstwatch check orders.csv --date-column "Created at" --amount-column Subtotal --table
```

Pick an amount **before** GST/HST (a subtotal or net-sales column, not a "Total" that includes tax). The canada.ca page does not say outright whether the figure is with or without tax, so that advice is unverified; ask your accountant. Dates may be `2026-03-31`, `2026-03-31 23:30:00 -0400` (taken as written, no time-zone shifting), `31 Mar 2026` or `Mar 31, 2026`. A numeric `03/04/2026` could be March 4 or April 3, so it is **refused** unless some date in the file can only be read one way (`25/03/2026`), or you say `--date-order dmy` / `mdy`. Accounting-style negatives such as `(500.00)` are read as refunds. Without these options the file must have the plain `date,amount` or `quarter_end,amount` headers; otherwise the error lists the columns it found. I did not have real QuickBooks/Wave/Square exports to test, so column names are never guessed: you choose them. Sums are exact (cents are added as whole numbers), so a total of exactly C$30,000.00 is never mistaken for being over.

`--table` prints the working, quarter by quarter: the amount, the trailing 2/3/4-quarter totals, and which test trips (`--json` gets a `table` list). If you run it mid-quarter with `--as-of` (put the amount so far under that quarter's end date), the latest possible registration date is clamped to today, because the supply that crossed the line has already happened; if your data stops quarters before `--as-of`, you are told it may be out of date rather than having the gap treated as C$0.

CSV files may be comma-, semicolon- or tab-separated (French-locale Excel exports work), UTF-8 or Excel's UTF-16 "Unicode Text"; use `-` as the file name to read standard input (`cat sales.csv | gstwatch check -`). A file saved by Excel in the old Windows code page is refused with a message telling you to Save As "CSV UTF-8". Money is parsed strictly: `1,234.56`, `12 500,50` and `C$5,000` are fine; an ambiguous `12,50` (12.50 or 1,250?) is **rejected**, never guessed. Optional `associates` and `excluded` columns (or `--associates 2026Q1=AMT` / `--excluded 2026Q1=AMT`) add associates' supplies and subtract the supplies CRA excludes (financial services, capital property, goodwill); you remain responsible for which items qualify. Refund rows may be negative in a transaction CSV and are netted within their quarter; whether CRA nets credit notes this way is unverified.

Both CRA tests are run:

1. **Single quarter** — one calendar quarter alone over C$30,000: you must charge GST/HST on the supply that takes you over; effective registration is no later than that supply; **register within 29 days**. Pass `--crossing YYYY-MM-DD` if you know the exact supply date; otherwise the output gives the range: the latest possible register-by (quarter end + 29 days) **and** the earliest possible (quarter start + 29 days), and flags "possibly overdue" against the earliest.
2. **Four-or-fewer consecutive quarters** — total over C$30,000: small-supplier status ends at the **end of the month following** the quarter in which you crossed; collect from the first supply after that; register within 29 days of that effective date. CRA's effective date is "no later than" your first supply after status ended, so the end-of-month date shown is the earliest possible: pass `--first-supply YYYY-MM-DD` to compute from the real date.

Exit codes: `0` still a small supplier, `3` registration required (also taxi/ride-share operators) (distinct on purpose, so scripts can branch), `2` usage error. `--json` for automation.

Useful options: quarters can be written `2026Q1=8000`; `--as-of 2026-11-07` adds days-left / overdue; `--entity psb` uses the C$50,000 public-service-body threshold; `--taxi` flags taxi/ride-share operators (CRA: must register even if small). While you are still under, the output tells you **how much more you can supply next quarter** before either test trips. If both tests trip, the earliest effective date is reported.

Input is validated and rejected, never guessed: NaN/infinite/negative amounts, duplicate quarters, dates that are not calendar quarter ends, and `--crossing` dates outside the offending quarter all exit `2`. Quarters you skip are assumed C$0 and listed. Charities/public institutions (different tests) are refused.

### In a script or CI job

`--json` output carries `"schema_version": 1` (changes only if a field is removed or changes meaning) and `"gstwatch_version"`. Errors are JSON too, on stdout, with a plain message on stderr. Exit code 3 survives `| head`.

```bash
gstwatch check sales.csv --json > result.json || [ $? -eq 3 ] || exit 1   # 3 = "register", not a failure of the tool
```

From Python (the same engine the CLI uses; amounts are floats, quarter ends are `datetime.date`):

```python
import datetime as dt
from gstwatch import evaluate

st = evaluate([(dt.date(2026, 3, 31), 31000.0)])
print(st.small_supplier, st.register_by)   # False 2026-04-29
```

## Filing frequency

```bash
gstwatch freq 1400000     # -> annual   (assigned: annual <= C$1.5M)
gstwatch freq 7000000     # -> monthly  (quarterly up to C$6M, monthly above)
```

Give it your annual **taxable supplies made in Canada** (including zero-rated sales and your associates'; excluding sales outside Canada, zero-rated exports, exempt supplies, capital real property and goodwill). That is what canada.ca's reporting-period page says CRA uses, for the preceding fiscal year. It is *not* the same measure as the worldwide figure in the threshold test, so the filing frequency printed by `check` is an approximation and says so.

## Record retention

```bash
gstwatch records 2026-05-10   # -> keep records until 2032-12-31
gstwatch records 2026-05-10 --period-end 2027-03-31   # fiscal year ending Mar 31 -> 2033-03-31
```

Six years from the **end of the year** the record relates to (calendar year by default; with `--period-end` the later of the calendar and fiscal answers is shown. canada.ca does not say which "year" it means for GST/HST, so this is unverified).

`check` approximates filing frequency from the trailing four calendar quarters you gave it; with under four quarters it is labelled an ESTIMATE (CRA bases it on actual annual taxable revenue, and the periods do not auto-adjust if revenue falls).

## How it compares

| | gstwatch | gst-hst-tracker (OSS CLI, PyPI 1.0.0) | yourincomecalculator.com HST page | Accounting software (Wave, QuickBooks Canada, FreshBooks) |
|---|---|---|---|---|
| Single-quarter test | yes | not described in its README | FAQ mentions it; the outputs shown are built on the 4-quarter total | unverified |
| Four-quarter test | yes | yes | yes | unverified |
| Effective date + 29-day register-by | yes (with earliest/latest range) | no | text "within 29 days", no date | unverified |
| Reads dated transactions | yes (`date,amount`; any export via `--date-column`) | yes (needs province, kind, description) | no, 4 quarter boxes | yes (it is the books) |
| Province tax estimate / net tax / ITCs | **no** | yes | tax estimate | yes |
| Free, offline, scriptable (exit codes, JSON) | yes | yes | no | no |
| Filing, books | **no** | no | no | yes |

Re-checked 2026-11-08: the gst-hst-tracker README (github.com/jasveerai88/gst-hst-tracker: `report`, `threshold`, `provinces` commands, rolling four-quarter window tested, no effective date shown, MIT, v1.0.0; `pip index versions gst-hst-tracker` lists 1.0.0, so it is on PyPI) and yourincomecalculator.com/ca/calculators/hst-registration (found again this time: Q1-Q4 boxes, a province dropdown, a rolling total and a tax estimate, free to use as far as the page says). Accounting-software columns are not verified: I did not find these features in docs searched, which is not proof they are absent. If you need province-specific tax, ITCs or net tax, those tools do that; `gstwatch` does not.

Verified against canada.ca on 2026-11-08 (when-register-charge, change-account and records pages): the C$30,000 single-quarter and four-quarter tests, 29-day registration, associates' revenue included (if associated at the start of the quarter), financial services and capital property/goodwill excluded, C$50,000 public service body threshold, taxi/ride-share rule, filing bands (<= C$1.5M annual, <= C$6M quarterly, periods do not auto-adjust), 6-year records. Not found on the pages fetched, so unverified: whether the C$30,000 is measured with or without GST/HST, any CRA online calculator, whether credit notes net against a quarter, voluntary-registration dates and the one-year minimum, and competitor features. Also note: the reporting-period page counts taxable supplies *made in Canada* for the preceding fiscal year, while the small-supplier page says *worldwide* taxable supplies including zero-rated; they are different measures.

## Windows

Written to be portable (no shell calls, no signals, no file replacement; CSV read as bytes so CRLF and BOMs are fine; output never crashes on a legacy console code page: unprintable characters become `?`). CI runs the tests on `windows-latest` as well. **It has not been run on Windows by the author**; if something breaks there, please open an issue.

## Benchmark

`PYTHONPATH=src python3 bench/bench.py` compares the engine with an independent brute-force restatement of the two tests on 20,000 seeded random histories (0 mismatches, committed in `bench/results.json`) and times it (indicative, machine-dependent, noisy): 400 quarters in about 2-4 ms and 100,000 transaction rows loaded in about 0.3-0.7 s on a busy machine. Round 5's exact decimal sums cost something: in four back-to-back side-by-side runs against the round-4 code the engine call was about 1-3x slower (1.7-4.2 ms against 0.7-2.5 ms) and loading 100,000 rows was between equal and about 1.5x slower. The committed `bench/results.json` is one such noisy run. The oracle was written by the same author from the same reading of the rules, so it checks the code, not CRA's interpretation.

`python3 bench/mutation.py` is the other check: it breaks 23 rules one at a time in a scratch copy (threshold, 29 days, filing bands, exit code, exact sums...) and confirms the tests fail each time. Results are in `bench/mutation_results.json`; one mutant is listed as unable to change any output.

## What's modeled — and what isn't

Modeled: the two threshold tests, 29-day registration clock, effective-date rules (single vs rolling, with earliest/latest when the exact supply date is unknown), assigned filing bands, 6-year retention. Years outside 1900-2100 are rejected.

**Not** modeled: converting foreign currency (enter Canadian dollars), deciding which supplies are inclusions/exclusions or whether parties are associates (you supply the amounts; the tool only adds/subtracts them), voluntary-registration date elections and the one-year minimum, deregistration decisions, and filing obligations themselves. The threshold test includes worldwide taxable supplies (including zero-rated) per CRA's description — bring your accountant for the exclusions.

Sources: [when to register and start charging](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/when-register-charge.html) · [assigned reporting periods](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/gst-hst-account/change-account.html) · [records to keep](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/calculate-prepare-report/gst-hst-records-keep.html)

## License

MIT-style: use it, ship it, no warranty.
