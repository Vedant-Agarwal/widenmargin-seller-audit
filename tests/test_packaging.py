"""Packaging rules (see tools/validate.py for the documented requirements each check maps to)."""
import importlib.util
import os
import zipfile

from conftest import ROOT


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_validator_passes(capsys):
    assert _load("validate").main() == 0, capsys.readouterr().out


def test_zips_have_the_documented_shape(tmp_path, monkeypatch):
    bz = _load("build_zips")
    monkeypatch.setattr(bz, "DIST", str(tmp_path))
    bz.main()
    names = sorted(os.listdir(str(tmp_path)))
    assert names == ["ledger-audit.zip", "reimbursement-check.zip", "returns-not-received.zip",
                     "widenmargin-seller-audit-plugin-0.1.0.zip"]
    for skill in ("ledger-audit", "reimbursement-check", "returns-not-received"):
        with zipfile.ZipFile(str(tmp_path / (skill + ".zip"))) as z:
            entries = z.namelist()
        assert all(e.startswith(skill + "/") for e in entries)
        assert skill + "/SKILL.md" in entries and skill + "/scripts/wm_audit_core.py" in entries
        assert not any("__pycache__" in e or e.endswith(".pyc") for e in entries)
    with zipfile.ZipFile(str(tmp_path / "widenmargin-seller-audit-plugin-0.1.0.zip")) as z:
        entries = z.namelist()
    assert "widenmargin-seller-audit/.claude-plugin/plugin.json" in entries
    assert "widenmargin-seller-audit/.claude-plugin/marketplace.json" not in entries
    assert "widenmargin-seller-audit/LICENSE" in entries and "widenmargin-seller-audit/README.md" in entries
    assert not any(e.startswith("widenmargin-seller-audit/tests/") for e in entries)


def test_each_skill_runs_from_its_own_folder_only(tmp_path):
    """A skill uploaded on its own must work with nothing but its own folder."""
    import shutil
    import subprocess
    import sys
    for skill, args in [("ledger-audit", ["ledger_audit.py", "demo_ledger.csv", "--today", "2026-10-03"]),
                        ("returns-not-received", ["returns_not_received.py", "--settlement", "settlement_returns.tsv",
                                                  "--returns", "returns.tsv", "--today", "2026-09-24"]),
                        ("reimbursement-check", ["reimbursement_check.py", "demo_reimbursements.tsv"])]:
        dst = tmp_path / skill
        src = os.path.join(ROOT, "skills", skill)
        shutil.copytree(src, str(dst), ignore=shutil.ignore_patterns("__pycache__"))
        script = str(dst / "scripts" / args[0])
        fx = os.path.join(ROOT, "tests", "fixtures")
        cmd = [sys.executable, script] + [os.path.join(fx, a) if a.endswith((".csv", ".tsv")) else a for a in args[1:]]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(tmp_path), env={"PATH": os.environ.get("PATH", "")})
        assert r.returncode == 0, r.stderr
        assert "Read this before acting" in r.stdout
