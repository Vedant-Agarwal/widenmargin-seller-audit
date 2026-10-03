#!/usr/bin/env python3
"""Check the plugin against the documented requirements (as read on 2026-10-03):

- Agent Skills spec (https://agentskills.io/specification) and claude.com/docs/skills/how-to:
  SKILL.md frontmatter fields, name rules (lowercase/digits/hyphens, <=64, no leading/trailing or
  double hyphen, equals folder name), description 1-1024 chars, compatibility <=500, metadata
  string->string, no XML tags, no "anthropic"/"claude" in names, body under 500 lines,
  referenced files exist.
- Plugin manifest + directory pre-submission checklist (claude.com/docs/plugins/build,
  /plugins/pre-submission-checklist, code.claude.com/docs/en/plugins/manifest-reference):
  .claude-plugin/plugin.json name/version/description/author/license, README >= 40 words outside
  code blocks, LICENSE, every non-image file < 256 KiB, <= 512 files, no .DS_Store/Thumbs.db/
  desktop.ini/__MACOSX, Windows/macOS-safe names, no symlinks, no top-level bin/.
- Upload ZIP shape (if dist/ exists): skill ZIP = <skill>/SKILL.md at top; plugin ZIP = one top
  folder holding .claude-plugin/plugin.json.
- House rules: identical core copies, no network/process modules in scripts, no monetisation
  wording in shipped files.
Exit 0 when clean.
"""
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE_TOP = {".git", "_ref", "dist", "_parity_tmp", ".venv", ".pytest_cache"}
ALLOWED_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
WIN_DEVICES = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ttf", ".otf", ".woff", ".woff2"}
FORBIDDEN = re.compile(r"\b(paid|pricing|prices?|affiliate|subscriptions?|premium|upgrade|discounts?|coupons?|billing)\b", re.I)
NETWORK = re.compile(r"^\s*(import|from)\s+(urllib|requests|http|socket|subprocess|ftplib|smtplib|asyncio)\b", re.M)


def plugin_files():
    out = []
    for d, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(d, ROOT)
        top = rel.split(os.sep)[0]
        if top in EXCLUDE_TOP:
            dirs[:] = []
            continue
        dirs[:] = [x for x in dirs if x not in ("__pycache__",) and not (rel == "." and x in EXCLUDE_TOP)]
        for f in files:
            if f.endswith(".pyc"):
                continue
            out.append(os.path.join(d, f))
    return sorted(out)


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with '---' YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("frontmatter is not closed with '---'")
    fm, body = text[4:end], text[end + 5:]
    data, current = {}, None
    for line in fm.split("\n"):
        if not line.strip():
            continue
        if line.startswith("  ") and current == "metadata":
            k, _, v = line.strip().partition(":")
            data["metadata"][k.strip()] = v.strip()
            continue
        k, sep, v = line.partition(":")
        if not sep or line.startswith(" "):
            raise ValueError("unparseable frontmatter line: %r" % line)
        k, v = k.strip(), v.strip()
        current = k
        data[k] = {} if (k == "metadata" and v == "") else v
    return data, body


def unquote(v):
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'" else v


def check_skill(skill_dir, errors):
    name = os.path.basename(skill_dir)
    path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(path):
        errors.append("%s: no SKILL.md" % name)
        return
    text = open(path, encoding="utf-8").read()
    try:
        fm, body = parse_frontmatter(text)
    except ValueError as e:
        errors.append("%s/SKILL.md: %s" % (name, e))
        return
    extra = set(fm) - ALLOWED_FIELDS
    if extra:
        errors.append("%s: frontmatter fields not in the spec: %s" % (name, sorted(extra)))
    n = unquote(fm.get("name", ""))
    if not n or len(n) > 64 or not NAME_RE.match(n):
        errors.append("%s: invalid name %r" % (name, n))
    if n != name:
        errors.append("%s: name %r does not match folder" % (name, n))
    if "anthropic" in n or "claude" in n:
        errors.append("%s: name contains a reserved word" % name)
    d = unquote(fm.get("description", ""))
    if not d or len(d) > 1024:
        errors.append("%s: description must be 1-1024 chars (is %d)" % (name, len(d)))
    if re.search(r"<[^>]+>", d) or re.search(r"<[^>]+>", n):
        errors.append("%s: XML tags in name/description" % name)
    if "compatibility" in fm and not (1 <= len(unquote(fm["compatibility"])) <= 500):
        errors.append("%s: compatibility must be 1-500 chars" % name)
    if "metadata" in fm and not isinstance(fm["metadata"], dict):
        errors.append("%s: metadata must be a mapping" % name)
    if len(text.split("\n")) >= 500:
        errors.append("%s: SKILL.md should stay under 500 lines" % name)
    for ref in sorted(set(re.findall(r"`((?:references|scripts|assets)/[^`\s]+)`", body))):
        if not os.path.exists(os.path.join(skill_dir, ref)):
            errors.append("%s: SKILL.md references missing file %s" % (name, ref))
    for ref in sorted(set(re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([^\s\"'`]+)", body))):
        if not os.path.exists(os.path.join(skill_dir, ref)):
            errors.append("%s: ${CLAUDE_SKILL_DIR}/%s does not exist" % (name, ref))
    return {"name": n, "description_chars": len(d), "skill_md_lines": len(text.split("\n"))}


def readme_words(text):
    no_code = re.sub(r"```.*?```", " ", text, flags=re.S)
    return len(re.findall(r"[A-Za-z0-9][\w'’-]*", no_code))


def check_zip(path, errors):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    base = os.path.basename(path)
    tops = {n.split("/")[0] for n in names}
    if len(tops) != 1:
        errors.append("%s: must have exactly one top-level folder, has %s" % (base, sorted(tops)))
        return
    top = tops.pop()
    if any(n.startswith("__MACOSX") or n.endswith(".DS_Store") for n in names):
        errors.append("%s: contains macOS junk" % base)
    if "-plugin-" in base:
        if top + "/.claude-plugin/plugin.json" not in names:
            errors.append("%s: missing %s/.claude-plugin/plugin.json" % (base, top))
    else:
        if top + "/SKILL.md" not in names:
            errors.append("%s: missing %s/SKILL.md (zip the folder, not its contents)" % (base, top))


def main():
    errors, info = [], {}
    pj = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    n = pj.get("name", "")
    if not (n and len(n) <= 64 and NAME_RE.match(n)):
        errors.append("plugin.json: invalid name %r" % n)
    if re.match(r"^(claude|anthropic|anthropics|cc-plugin)-", n) or n in {"claude", "anthropic", "official", "plugin", "mcp", "test"}:
        errors.append("plugin.json: reserved name")
    for k in ("version", "description", "author", "license"):
        if not pj.get(k):
            errors.append("plugin.json: %s missing (directory warns)" % k)
    if not (pj.get("author") or {}).get("name"):
        errors.append("plugin.json: author.name is required")
    for k in ("homepage",):
        if k in pj and not re.match(r"^https://", pj[k]):
            errors.append("plugin.json: %s must be a URL" % k)
    mp_path = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
    if os.path.exists(mp_path):
        mp = json.load(open(mp_path))
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", mp.get("name", "")) or ".." in mp["name"]:
            errors.append("marketplace.json: invalid name")
        if not (mp.get("owner") or {}).get("name"):
            errors.append("marketplace.json: owner.name required")
        entry = (mp.get("plugins") or [{}])[0]
        if entry.get("name") != n or not str(entry.get("source", "")).startswith("./"):
            errors.append("marketplace.json: plugin entry must name %s with a ./ source" % n)
    skills = []
    for d in sorted(os.listdir(os.path.join(ROOT, "skills"))):
        sd = os.path.join(ROOT, "skills", d)
        if os.path.isdir(sd):
            skills.append(check_skill(sd, errors))
    info["skills"] = skills
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    info["readme_words_outside_code"] = readme_words(readme)
    if info["readme_words_outside_code"] < 40:
        errors.append("README.md: fewer than 40 words outside code blocks")
    if not os.path.isfile(os.path.join(ROOT, "LICENSE")) and not pj.get("license"):
        errors.append("LICENSE missing")
    if os.path.isdir(os.path.join(ROOT, "bin")):
        errors.append("top-level bin/ stops claude.ai and Cowork from installing the plugin")
    files = plugin_files()
    info["plugin_folder_files"] = len(files)
    info["largest_file"] = max((os.path.getsize(f), os.path.relpath(f, ROOT)) for f in files)
    if len(files) > 512:
        errors.append("more than 512 files in the plugin folder")
    seen = {}
    for f in files:
        rel = os.path.relpath(f, ROOT)
        base = os.path.basename(f)
        if os.path.islink(f):
            errors.append("%s: symlink" % rel)
        if base in {".DS_Store", "Thumbs.db", "desktop.ini"} or "__MACOSX" in rel:
            errors.append("%s: OS junk file" % rel)
        if os.path.splitext(f)[1].lower() not in IMAGE_EXT and os.path.getsize(f) >= 256 * 1024:
            errors.append("%s: >= 256 KiB" % rel)
        for part in rel.split(os.sep):
            if ":" in part or part.endswith((".", " ")) or part.split(".")[0].lower() in WIN_DEVICES:
                errors.append("%s: name not valid on Windows" % rel)
        for part in rel.split(os.sep)[:-1]:
            if not re.match(r"^[A-Za-z0-9._-]+$", part):
                errors.append("%s: folder name has characters outside letters/digits/._-" % rel)
        key = rel.lower()
        if key in seen and seen[key] != rel:
            errors.append("%s and %s differ only by case" % (rel, seen[key]))
        seen[key] = rel
        if rel.replace(os.sep, "/") != "tools/validate.py" and f.endswith((".md", ".json", ".py", ".txt")):
            m = FORBIDDEN.search(open(f, encoding="utf-8", errors="replace").read())
            if m:
                errors.append("%s: monetisation wording %r" % (rel, m.group(0)))
    core_src = open(os.path.join(ROOT, "src", "wm_audit_core.py"), "rb").read()
    for s in info["skills"]:
        if not s:
            continue
        sd = os.path.join(ROOT, "skills", s["name"], "scripts")
        cp = os.path.join(sd, "wm_audit_core.py")
        if not os.path.isfile(cp) or open(cp, "rb").read() != core_src:
            errors.append("skills/%s/scripts/wm_audit_core.py differs from src/ (run tools/sync_core.py)" % s["name"])
        for py in os.listdir(sd):
            if py.endswith(".py") and NETWORK.search(open(os.path.join(sd, py), encoding="utf-8").read()):
                errors.append("skills/%s/scripts/%s imports a network/process module" % (s["name"], py))
    if os.path.isdir(os.path.join(ROOT, "dist")):
        info["zips"] = []
        for z in sorted(os.listdir(os.path.join(ROOT, "dist"))):
            if z.endswith(".zip"):
                check_zip(os.path.join(ROOT, "dist", z), errors)
                info["zips"].append((z, os.path.getsize(os.path.join(ROOT, "dist", z))))
    print(json.dumps(info, indent=2, default=str))
    if errors:
        print("\nFAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print("\nOK: no problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
