# gstwatch

**The C$30,000 GST/HST threshold has two tests, a 29-day registration clock, and a 6-year memory.** `gstwatch` applies Canada's published small-supplier rules to your quarterly revenue and tells you: are you still a small supplier, when registration takes effect, when you must register by, what filing frequency CRA will assign, and how long to keep records.

Rules verified against Canada.ca, October 2026. **Not tax advice** — it applies published rules to your numbers and shows its work.

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

## What's modeled — and what isn't

Modeled: the two threshold tests, 29-day registration clock, effective-date rules (single vs rolling), assigned filing bands, 6-year retention.

**Not** modeled: the detailed supply inclusions/exclusions (exempt supplies, financial services, capital property, goodwill, associates' rules), voluntary-registration date elections and the one-year minimum, deregistration decisions, and filing obligations themselves. The threshold test includes worldwide taxable supplies (including zero-rated) per CRA's description — bring your accountant for the exclusions.

Sources: [when to register and start charging](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/when-register-charge.html) · [assigned reporting periods](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/gst-hst-account/change-account.html) · [records to keep](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/calculate-prepare-report/gst-hst-records-keep.html)

## License

MIT-style: use it, ship it, no warranty.
