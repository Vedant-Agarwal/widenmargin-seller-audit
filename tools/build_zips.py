#!/usr/bin/env python3
"""Build the upload ZIPs into dist/ (deterministic: sorted entries, fixed timestamps).

  dist/widenmargin-seller-audit-plugin-<version>.zip
      widenmargin-seller-audit/.claude-plugin/plugin.json, skills/**, README.md, LICENSE, CHANGELOG.md
      -> claude.ai / desktop: Customize > Plugins > Add > Upload plugin
  dist/<skill>.zip  (one per skill: <skill>/SKILL.md, scripts/, references/)
      -> claude.ai / desktop: Customize > Skills > + > Create skill > Upload a skill

Per the docs, a plugin ZIP may hold the plugin folder as its single top-level entry, and a skill
ZIP must hold the skill folder itself (not its contents) at the top level.
"""
import json
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
STAMP = (2026, 10, 3, 0, 0, 0)
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def walk(base):
    out = []
    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("__MACOSX"))
        for f in sorted(files):
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            out.append(os.path.join(d, f))
    return out


def add(z, src, arc):
    info = zipfile.ZipInfo(arc, STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o755 if arc.endswith(".py") and "/scripts/" in arc and not arc.endswith("wm_audit_core.py") else 0o644
    info.external_attr = (0o100000 | mode) << 16
    with open(src, "rb") as f:
        z.writestr(info, f.read())


def add_dirs(z, arcs):
    dirs = set()
    for a in arcs:
        parts = a.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]) + "/")
    for d in sorted(dirs):
        info = zipfile.ZipInfo(d, STAMP)
        info.external_attr = (0o040000 | 0o755) << 16
        z.writestr(info, b"")


def build_plugin(version):
    top = "widenmargin-seller-audit"
    files = [(os.path.join(ROOT, ".claude-plugin", "plugin.json"), top + "/.claude-plugin/plugin.json")]
    for p in walk(os.path.join(ROOT, "skills")):
        files.append((p, top + "/" + os.path.relpath(p, ROOT).replace(os.sep, "/")))
    for n in ("README.md", "LICENSE", "CHANGELOG.md"):
        files.append((os.path.join(ROOT, n), top + "/" + n))
    path = os.path.join(DIST, "%s-plugin-%s.zip" % (top, version))
    with zipfile.ZipFile(path, "w") as z:
        add_dirs(z, [a for _, a in files])
        for src, arc in sorted(files, key=lambda x: x[1]):
            add(z, src, arc)
    return path


def build_skill(name):
    base = os.path.join(ROOT, "skills", name)
    files = [(p, name + "/" + os.path.relpath(p, base).replace(os.sep, "/")) for p in walk(base)]
    path = os.path.join(DIST, name + ".zip")
    with zipfile.ZipFile(path, "w") as z:
        add_dirs(z, [a for _, a in files])
        for src, arc in sorted(files, key=lambda x: x[1]):
            add(z, src, arc)
    return path


def main():
    os.makedirs(DIST, exist_ok=True)
    version = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))["version"]
    built = [build_plugin(version)]
    for name in sorted(os.listdir(os.path.join(ROOT, "skills"))):
        if os.path.isfile(os.path.join(ROOT, "skills", name, "SKILL.md")):
            built.append(build_skill(name))
    for p in built:
        with zipfile.ZipFile(p) as z:
            n = len([i for i in z.infolist() if not i.is_dir()])
        print("%-60s %7d bytes  %3d files" % (os.path.relpath(p, ROOT), os.path.getsize(p), n))


if __name__ == "__main__":
    main()
