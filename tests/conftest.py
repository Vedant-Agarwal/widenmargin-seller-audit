import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(ROOT, "tests", "fixtures")
sys.path.insert(0, os.path.join(ROOT, "src"))


def fixture_text(name):
    import wm_audit_core as core
    return core.read_text(os.path.join(FX, name))


def load_script(skill, module):
    """Import a skill's CLI module from its own scripts/ folder (with that folder's core copy)."""
    path = os.path.join(ROOT, "skills", skill, "scripts", module + ".py")
    spec = importlib.util.spec_from_file_location("%s_%s" % (skill.replace("-", "_"), module), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
