# Publish checklist for gstwatch (plain words)

Nothing here has been run for you. Nothing was published, tagged or pushed. The upload step at the bottom is yours.

**Version to release: 0.2.0.** PyPI has 0.1.0 (checked 2026-11-08). Everything in this folder already says 0.2.0 (pyproject, `__version__`, CHANGELOG), and a test makes sure they stay equal. Do not change the number unless you decide to; 0.2.0 has never been uploaded, so there is nothing to bump.

Be ready to say in the release notes: it is a "minor" step, not a drop-in patch. A CSV with a `date` column now means transactions; amounts like `12,50` or `1_000` are refused instead of guessed; numeric dates like `03/04/2026` are refused unless the file makes the order obvious. Anything that worked in 0.1.0 (`quarter_end,amount` files, `--quarter`, `--crossing`, `--json` keys) still works, and 128 of 3,000 random histories now get an EARLIER (more correct) registration date than 0.1.0 gave.

## Decide first (2 minutes)
1. **Is the GitHub page public?** The package lists `https://github.com/calasdan-sketch/gstwatch` as its home. I could not check from here (the check was blocked). Open that link in a private window. If it shows "404", the repository is private: delete the whole `[project.urls]` block in `pyproject.toml` and the "install from the repository" sentence in `README.md` before you upload, or the PyPI page will link to nowhere.
2. **Company name.** `LICENSE` and the package author both say "Calas Automations Inc." (no email address; none was invented). That is what PyPI will show instead of the old handle.
3. **Windows has never been run** on this code (`docs/ROUND5.md`, last section). The CI file will test it the first time you push; look at that result before you announce anything.

## Commands (run in the repo folder, in order)
```bash
git switch expert-2 && git status          # should say "nothing to commit"
python -m venv /tmp/gw && /tmp/gw/bin/pip install build twine pytest
/tmp/gw/bin/pip install -e . && /tmp/gw/bin/pytest -q     # expect 187 passed (hypothesis tests skip if it is not installed)
rm -rf dist && /tmp/gw/bin/python -m build
/tmp/gw/bin/twine check dist/*             # expect PASSED twice
unzip -p dist/*.whl '*/METADATA' | head -8 # expect: Author: Calas Automations Inc.
git tag v0.2.0                              # only after merging to main
# upload (needs you logged in to PyPI as owner; this is the step that goes public):
/tmp/gw/bin/twine upload dist/*
```
After uploading: in a fresh folder run `pip install "gstwatch>=0.2" && gstwatch --version` (should print `gstwatch 0.2.0`), then edit the README install note ("PyPI currently holds the older 0.1.0...") to remove it.

## Cost
PyPI is free. Nothing else here costs money. The tests and the benchmark never touch the network.
