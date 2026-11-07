# Publish checklist for gstwatch (plain words)

Nothing here has been run for you. Nothing was published, tagged or pushed.

**Version to release: 0.2.0.** PyPI has 0.1.0 (checked 2026-11-07). The code in this repo is already 0.2.0 everywhere (pyproject, `__version__`, CHANGELOG). It is a "minor" bump, not a drop-in patch: a CSV with a `date` column now means transactions, and amounts like `12,50` or `1_000` are now rejected instead of guessed. Say so in the release notes.

## Check first
1. Open `LICENSE`. It now says "Copyright (c) 2026 Calas Automations Inc." Confirm you want the company, not yourself personally, as the holder. If not, change it back (and the author in `pyproject.toml`).
2. Open `README.md` and `docs/ROUND4.md`. Read the "could not test" list. Windows was never run.
3. Confirm the PyPI project `gstwatch` is yours (you will need to be logged in as its owner).

## Commands (run in the repo folder, in order)
```bash
git switch expert-2 && git status          # should say "nothing to commit"
python -m venv /tmp/gw && /tmp/gw/bin/pip install build twine pytest
/tmp/gw/bin/pip install -e . && /tmp/gw/bin/pytest -q     # expect 111 passed
rm -rf dist && /tmp/gw/bin/python -m build
/tmp/gw/bin/twine check dist/*             # expect PASSED twice
git tag v0.2.0                              # only after merging to main
# upload (needs your PyPI token or Trusted Publishing; this step is the one that goes public):
/tmp/gw/bin/twine upload dist/*
```
After uploading: in a fresh folder run `pip install "gstwatch>=0.2" && gstwatch --version` (should print `gstwatch 0.2.0`), then edit the README install note ("PyPI currently holds the older 0.1.0...") to remove it.

## Cost
PyPI is free. Nothing else here costs money.
