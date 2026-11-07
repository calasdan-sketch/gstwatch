"""Round 4: what a stranger gets from the installed package (CLI via subprocess, metadata, stdin)."""
import io
import json
import os
import re
import subprocess
import sys

import pytest

import gstwatch
from gstwatch.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))


def run(*args, stdin=b"", cwd=None):
    return subprocess.run([sys.executable, "-m", "gstwatch", *args], input=stdin,
                          capture_output=True, env=ENV, cwd=cwd, timeout=60)


def test_python_dash_m_works():
    r = run("--version")
    assert r.returncode == 0 and r.stdout.decode().strip() == f"gstwatch {gstwatch.__version__}"


def test_stdin_dash(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"date,amount\r\n2026-01-02,40000\r\n")))
    assert main(["check", "-"]) == 3
    assert "Small supplier: NO" in capsys.readouterr().out


def test_stdin_utf16_excel_unicode_text():
    data = "date\tamount\n2026-01-01\t40000\n".encode("utf-16")  # BOM + tab-delimited
    r = run("check", "-", "--json", stdin=data)
    assert r.returncode == 3 and json.loads(r.stdout)["trigger"] == "single-quarter"


def test_non_utf8_message_is_actionable():
    r = run("check", "-", stdin=b"date,amount\n2026-01-01,5\xe9\n")
    assert r.returncode == 2 and b"CSV UTF-8" in r.stderr and b"Traceback" not in r.stderr


def test_exit_code_survives_closed_pipe():
    # a reader that closes immediately (like `| head -0`) must not turn "register" (3) into 0
    p = subprocess.Popen([sys.executable, "-m", "gstwatch", "check", "--quarter", "2026Q1=40000"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV)
    p.stdout.close()
    p.wait(timeout=60)
    assert p.returncode == 3
    assert b"Traceback" not in p.stderr.read()


def test_usage_errors_are_json_with_flag():
    r = run("--json", "bogus")
    assert r.returncode == 2
    out = json.loads(r.stdout)
    assert out["exit"] == 2 and out["schema_version"] == 1


def test_json_has_schema_and_version(capsys):
    assert main(["check", "--quarter", "2026Q1=1000", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["schema_version"] == 1 and d["gstwatch_version"] == gstwatch.__version__


def test_freq_uses_strict_money_parser(capsys):
    assert main(["freq", "1,400,000"]) == 0
    capsys.readouterr()
    assert main(["freq", "1_000"]) == 2
    assert main(["freq", "12,50"]) == 2


def test_crossing_ignored_note_when_still_small(capsys):
    assert main(["check", "--quarter", "2026Q1=100", "--crossing", "2026-02-01"]) == 0
    assert "--crossing ignored" in capsys.readouterr().out


def test_repeated_header_rejected(tmp_path, capsys):
    p = tmp_path / "x.csv"
    p.write_text("date,amount,date\n2026-01-01,5,2026-02-02\n")
    assert main(["check", str(p)]) == 2
    assert "repeated column" in capsys.readouterr().err


def test_huge_field_and_nul_are_plain_errors(tmp_path, capsys):
    p = tmp_path / "big.csv"
    p.write_text("date,amount\n2026-01-01," + "9" * 200000 + "\n")
    assert main(["check", str(p)]) == 2
    q = tmp_path / "nul.csv"
    q.write_bytes(b"date,amount\n2026-01-01,5\x00\n")
    assert main(["check", str(q)]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_output_error_is_not_a_traceback():
    if not os.path.exists("/dev/full"):
        pytest.skip("no /dev/full on this OS")
    with open("/dev/full", "wb") as full:
        r = subprocess.run([sys.executable, "-m", "gstwatch", "check", "--quarter", "2026Q1=1"],
                           stdout=full, stderr=subprocess.PIPE, env=ENV)
    assert r.returncode == 2 and b"Traceback" not in r.stderr


def test_runs_from_directory_with_spaces_and_ascii_locale(tmp_path):
    d = tmp_path / "my docs & files"
    d.mkdir()
    (d / "q q.csv").write_text("quarter_end,amount\n2026-03-31,31000\n")
    env = dict(ENV, LC_ALL="C", PYTHONIOENCODING="ascii")
    r = subprocess.run([sys.executable, "-m", "gstwatch", "check", "q q.csv"], cwd=d,
                       capture_output=True, env=env, timeout=60)
    assert r.returncode == 3 and b"Traceback" not in r.stderr
    r.stdout.decode("ascii")  # footer is plain ASCII now


def test_metadata_consistent():
    text = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
    assert re.search(rf'^version = "{re.escape(gstwatch.__version__)}"', text, re.M)
    assert "https://github.com/calasdan-sketch/gstwatch" in text
    assert 'name = "Calas Automations Inc."' in text
    assert "Copyright (c) 2026 Calas Automations Inc." in open(os.path.join(ROOT, "LICENSE")).read()
    assert f"## {gstwatch.__version__} " in open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    assert os.path.exists(os.path.join(ROOT, "src", "gstwatch", "py.typed"))
    classifiers = re.findall(r'"Programming Language :: Python :: (3\.\d+)"', text)
    assert "3.9" in classifiers and re.search(r'requires-python = ">=3\.9"', text)


def test_readme_library_example_runs():
    text = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    code = re.search(r"```python\n(.*?)```", text, re.S).group(1)
    ns = {}
    exec(compile(code, "README", "exec"), ns)  # must run as written
    assert ns["st"].small_supplier is False
