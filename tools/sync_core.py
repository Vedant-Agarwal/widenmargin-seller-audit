#!/usr/bin/env python3
"""Copy src/wm_audit_core.py into every skill's scripts/ folder.

Each skill must be self-contained (claude.ai copies one skill folder into its sandbox, and a skill
can be uploaded on its own), so the shared core is duplicated. tests/test_packaging.py fails if a
copy drifts from src/.
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "wm_audit_core.py")

for name in sorted(os.listdir(os.path.join(ROOT, "skills"))):
    dst = os.path.join(ROOT, "skills", name, "scripts", "wm_audit_core.py")
    if os.path.isdir(os.path.dirname(dst)):
        shutil.copyfile(SRC, dst)
        print("synced", os.path.relpath(dst, ROOT))
