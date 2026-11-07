"""Committed benchmark: correctness against an independent brute-force oracle + speed.

Run:  PYTHONPATH=src python3 bench/bench.py            (prints JSON)
      PYTHONPATH=src python3 bench/bench.py --write    (also updates bench/results.json)

Correctness numbers are deterministic (seeded). Timings depend on the machine and are indicative only.
"""
import calendar
import datetime as dt
import json
import os
import random
import sys
import tempfile
import time

from gstwatch.cli import load_quarters
from gstwatch.evaluate import THRESHOLD, evaluate, parse_amount, quarter_end

SEED, CASES = 20261107, 20000


def oracle(amounts, threshold=THRESHOLD):
    """Independent restatement of CRA's two tests over consecutive calendar quarters.

    amounts: list of quarterly totals starting at quarter index 0. Returns
    (small, trigger_index, kind) where the effective ordering is by END of quarter index
    (single) or end of the following month (rolling); we compare only the verdict and kind.
    """
    n = len(amounts)
    single = next((i for i, a in enumerate(amounts) if a > threshold), None)
    rolling = None
    for j in range(n):
        if any(sum(amounts[j - s + 1:j + 1]) > threshold for s in (2, 3, 4) if j - s + 1 >= 0):
            rolling = j
            break
    return single, rolling


def correctness():
    rnd = random.Random(SEED)
    bad = 0
    for _ in range(CASES):
        n = rnd.randint(1, 9)
        amts = [round(rnd.choice([0, 1000, 5000, 9000, 12000, 15000, 29999.99, 30000, 30000.01, 45000])
                      * rnd.random() * 1.4, 2) for _ in range(n)]
        qs = [(quarter_end(2024 + (i // 4), i % 4 + 1), a) for i, a in enumerate(amts)]
        st = evaluate(qs)
        single, rolling = oracle(amts)
        small = single is None and rolling is None
        if st.small_supplier != small:
            bad += 1
            continue
        if not small:
            # earliest effective date wins; rolling effective = end of month after quarter
            eff = []
            if single is not None:
                eff.append(("single-quarter", quarter_end(2024 + single // 4, single % 4 + 1)))
            if rolling is not None:
                q = quarter_end(2024 + rolling // 4, rolling % 4 + 1)
                m = q.month + 1
                y = q.year + (m > 12)
                m = 1 if m > 12 else m
                eff.append(("rolling", dt.date(y, m, calendar.monthrange(y, m)[1])))
            want = min(eff, key=lambda e: e[1])
            ties = [e for e in eff if e[1] == want[1]]
            if st.effective_date != want[1] or st.trigger not in [t for t, _ in ties]:
                bad += 1
    return {"cases": CASES, "mismatches_vs_oracle": bad, "seed": SEED}


def timing():
    out = {}
    qs = [(quarter_end(1950 + i // 4, i % 4 + 1), 100.0) for i in range(400)]
    t = time.perf_counter()
    for _ in range(200):
        evaluate(qs)
    out["evaluate_400_quarters_ms_each"] = round((time.perf_counter() - t) / 200 * 1000, 3)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.csv")
        rows = ["date,amount"] + [f"{2000 + (i % 100)}-{(i % 12) + 1:02d}-15,{i % 97 + 1}.50"
                                  for i in range(100_000)]
        with open(p, "w") as fh:
            fh.write("\n".join(rows) + "\n")
        t = time.perf_counter()
        q = load_quarters(p)
        out["load_100000_transaction_rows_s"] = round(time.perf_counter() - t, 3)
        out["quarters_from_100000_rows"] = len(q)
    t = time.perf_counter()
    for _ in range(100000):
        parse_amount("12 500,50")
    out["parse_amount_us_each"] = round((time.perf_counter() - t) / 100000 * 1e6, 2)
    return out


def main_():
    res = {"correctness": correctness(), "timing_indicative": timing()}
    txt = json.dumps(res, indent=2, sort_keys=True)
    print(txt)
    if "--write" in sys.argv:
        with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as fh:
            fh.write(txt + "\n")
    return 0 if res["correctness"]["mismatches_vs_oracle"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main_())
