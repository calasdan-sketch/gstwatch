# gstwatch

**The C$30,000 GST/HST threshold has two tests, a 29-day registration clock, and a 6-year memory.** `gstwatch` applies Canada's published small-supplier rules to your quarterly revenue and tells you: are you still a small supplier, when registration takes effect, when you must register by, what filing frequency CRA will assign, and how long to keep records.

Rules verified against Canada.ca, October 2026. **Not tax advice and not a substitute for a CPA or CRA** — it applies published rules to your numbers and shows its work.

## Install

```bash
pip install gstwatch
```

## Check the threshold

```bash
gstwatch check --quarter 2025-12-31=8000 --quarter 2026-03-31=8000 \
               --quarter 2026-06-30=8000 --quarter 2026-09-30=8000

# or from a CSV: quarter_end,amount
gstwatch check quarters.csv
```

Both CRA tests are run:

1. **Single quarter** — one calendar quarter alone over C$30,000: you must charge GST/HST on the supply that takes you over; effective registration is no later than that supply; **register within 29 days**. Pass `--crossing YYYY-MM-DD` if you know the exact supply date (otherwise the quarter end is used and the output says so).
2. **Four-or-fewer consecutive quarters** — total over C$30,000: small-supplier status ends at the **end of the month following** the quarter in which you crossed; collect from the first supply after that; register within 29 days of that effective date.

Exit codes: `0` still a small supplier, `3` registration required (distinct on purpose, so scripts can branch), `2` usage error. `--json` for automation.

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
```

Six years from the **end of the year** the record relates to.

`check` assigns filing frequency from the trailing four calendar quarters; with under four quarters it is labelled an ESTIMATE (CRA bases it on actual annual taxable revenue, and the periods do not auto-adjust if revenue falls).

## How it compares

| | gstwatch | Accounting software (Wave, QuickBooks Canada, FreshBooks) | Spreadsheet |
|---|---|---|---|
| Both CRA tests + effective/register-by dates | yes | unverified, not found in docs searched | DIY |
| Free, offline, scriptable (exit codes, JSON) | yes | no | partly |
| Cites canada.ca rules | yes | unverified | no |
| Books, invoicing, filing | **no** | yes | no |

Verified against canada.ca on 2026-11-07: the C$30,000 single-quarter and four-quarter tests, 29-day registration, associates' revenue included, financial services and capital property excluded, C$50,000 public service body threshold, taxi/ride-share rule, filing bands (<= C$1.5M annual, <= C$6M quarterly), 6-year records. Not found on the pages fetched, so treated as unverified: any CRA online calculator, and competitor features.

## What's modeled — and what isn't

Modeled: the two threshold tests, 29-day registration clock, effective-date rules (single vs rolling), assigned filing bands, 6-year retention.

**Not** modeled: the detailed supply inclusions/exclusions (exempt supplies, financial services, capital property, goodwill, associates' rules), voluntary-registration date elections and the one-year minimum, deregistration decisions, and filing obligations themselves. The threshold test includes worldwide taxable supplies (including zero-rated) per CRA's description — bring your accountant for the exclusions.

Sources: [when to register and start charging](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/when-register-charge.html) · [assigned reporting periods](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/gst-hst-account/change-account.html) · [records to keep](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/calculate-prepare-report/gst-hst-records-keep.html)

## License

MIT-style: use it, ship it, no warranty.
