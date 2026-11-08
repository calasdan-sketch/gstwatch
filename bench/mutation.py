"""Mutation-style sanity check: break one rule at a time in a COPY of the tree and confirm
the test suite notices. Never touches the real source.

Run:  python3 bench/mutation.py            (prints a table; ~5 minutes)
      python3 bench/mutation.py --write    (also saves bench/mutation_results.json)
      python3 bench/mutation.py 4-quarter  (only mutants whose name contains the text)

A "survivor" means no test failed after the rule was broken: either a missing test or an
equivalent change (listed with a note when it is known to be equivalent).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV, CLI = "src/gstwatch/evaluate.py", "src/gstwatch/cli.py"

# (name, file, old text, new text)
MUTANTS = [
    ("single quarter: > becomes >=", EV, "        if amt[i] > thr:", "        if amt[i] >= thr:"),
    ("rolling window: > becomes >=", EV, "            if s > thr:\n                rolling", "            if s >= thr:\n                rolling"),
    ("register window 29 -> 30 days", EV, "REGISTER_DAYS = 29", "REGISTER_DAYS = 30"),
    ("threshold 30000 -> 30001", EV, "THRESHOLD = 30000", "THRESHOLD = 30001"),
    ("PSB threshold 50000 -> 40000", EV, "PSB_THRESHOLD = 50000", "PSB_THRESHOLD = 40000"),
    ("rolling test ignores 4-quarter windows", EV, "        for size in (2, 3, 4):\n            s = sum((get(k)",
     "        for size in (2, 3):\n            s = sum((get(k)"),
    ("month-end after December broken", EV, "(d.year + 1, 1) if d.month == 12", "(d.year + 1, 1) if d.month == 11"),
    ("annual filing limit 1.5M -> 1.4M", EV, "FILING_ANNUAL_MAX = 1_500_000", "FILING_ANNUAL_MAX = 1_400_000"),
    ("quarterly filing limit 6M -> 5M", EV, "FILING_QUARTERLY_MAX = 6_000_000", "FILING_QUARTERLY_MAX = 5_000_000"),
    ("records: 6 years -> 5", EV, "transaction_date.year + 6, 12, 31", "transaction_date.year + 5, 12, 31"),
    ("records: fiscal year ignored", EV, "    return max(base, _add_years(period_end, 6))", "    return base"),
    ("mid-quarter clamp removed", EV, "                latest = as_of  # quarter still running", "                latest = end  # quarter still running"),
    ("headroom can go negative", EV, "next_quarter_headroom=float(max(Decimal(0), room)),", "next_quarter_headroom=float(room),"),
    ("earliest possible date = quarter end", EV, "earliest = _qdate(i - 1) + dt.timedelta(days=1)", "earliest = _qdate(i - 1)"),
    ("short-history filing estimate not scaled", EV, "trailing * 4 / (hi - lo + 1)", "trailing * 3 / (hi - lo + 1)"),
    ("trailing-four test off by one", EV, "if hi - lo + 1 >= 4:", "if hi - lo + 1 > 4:"),
    ("negative quarter accepted", EV, "        if a < 0:\n            raise InputError(f\"amount for", "        if a < -1e18:\n            raise InputError(f\"amount for"),
    ("thousands separator group size", EV, "{1,3}(?:,[0-9]{3})+(?:\\.[0-9]+)?\")", "{1,3}(?:,[0-9]{2})+(?:\\.[0-9]+)?\")"),
    ("exact-decimal sums replaced by float", EV, "    return Decimal(repr(float(x)))", "    return Decimal(float(x))"),
    ("excluded sales added instead of subtracted", CLI, "dsum(amount, -_opt_amount(norm, \"excluded\"))", "dsum(amount, _opt_amount(norm, \"excluded\"))"),
    ("exit code 3 -> 1", CLI, "_EXIT[\"code\"] = 3 if must else 0", "_EXIT[\"code\"] = 1 if must else 0"),
    ("ambiguous dates accepted as day-first", EV, "    raise InputError(\"dates like 03/04/2026 could be March 4 or April 3; add --date-order mdy \"\n                     \"(month first) or --date-order dmy (day first)\")",
     "    return \"dmy\""),
    ("single wins ties against rolling", EV, "single[2] <= next_month_end(_qdate(rolling[0]))", "single[2] < next_month_end(_qdate(rolling[0]))"),
]
# Known-equivalent mutants (cannot change any observable output); reported but not counted as gaps.
EQUIVALENT = {"headroom can go negative":
              "a small supplier has every 1-4 quarter window at or under the threshold, so the room is never negative"}


def run_suite(tree):
    env = dict(os.environ, PYTHONPATH=os.path.join(tree, "src"), PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider"], cwd=tree,
                       capture_output=True, text=True, env=env, timeout=600)
    return r.returncode


def main():
    results = []
    scratch = tempfile.mkdtemp(prefix="gstwatch-mut-")
    try:
        only = [a for a in sys.argv[1:] if not a.startswith("--")]
        for name, rel, old, new in MUTANTS:
            if only and not any(o in name for o in only):
                continue
            tree = os.path.join(scratch, "tree")
            shutil.rmtree(tree, ignore_errors=True)
            shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns(".git", "__pycache__", ".mypy_cache",
                                                                       ".pytest_cache", "dist", "build"))
            path = os.path.join(tree, rel)
            text = open(path, encoding="utf-8").read()
            if text.count(old) != 1:
                results.append({"mutant": name, "result": "NOT APPLIED (pattern changed)"})
                continue
            open(path, "w", encoding="utf-8").write(text.replace(old, new))
            code = run_suite(tree)
            results.append({"mutant": name, "result": "killed" if code != 0 else "SURVIVED",
                            **({"note": EQUIVALENT[name]} if name in EQUIVALENT and code == 0 else {})})
            print(f"{results[-1]['result']:>10}  {name}", flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    killed = sum(r["result"] == "killed" for r in results)
    summary = {"mutants": len(results), "killed": killed,
               "survivors": [r for r in results if r["result"] != "killed"], "all": results}
    print(f"\n{killed}/{len(results)} mutants killed")
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, "bench", "mutation_results.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
            fh.write("\n")
    return 0 if all(r["result"] == "killed" or r.get("note") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
