#!/usr/bin/env python3
"""
jobgen.py — generate jobs.json (the ~100-job manifest) from the live tool/artifact/phase
lists + the invariant registry. Adding a job = a line here or a function in checks_lib.py.
runner.py executes the manifest each minute. Re-runnable.
"""
import os, json, glob, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def J(id, kind, group, check, gate=False, nudge=""):
    return {"id": id, "kind": kind, "group": group, "check": check, "gate": gate, "nudge": nudge}

jobs = []
# INTEGRITY · per-tool (syntax/compile, side-effect-free)
SKIP = {"jobgen", "runner", "checks_lib"}
for p in sorted(glob.glob(os.path.join(HERE, "*.py"))):
    m = os.path.splitext(os.path.basename(p))[0]
    if m in SKIP: continue
    jobs.append(J(f"tool:{m}", "integrity", "tools", f"python3 -m py_compile {p}", gate=True))

# INTEGRITY · per-artifact (parses as JSON)
_root = os.path.dirname(HERE)
for p in sorted(glob.glob(os.path.join(HERE, "*.json")) + glob.glob(os.path.join(_root, "device", "*.json"))):
    n = os.path.basename(p)
    jobs.append(J(f"artifact:{n}", "integrity", "artifacts",
                  f"python3 -c \"import json;json.load(open(r'{p}'))\"", gate=True))

# INTEGRITY · invariants (checks_lib functions)
spec = importlib.util.spec_from_file_location("checks_lib", os.path.join(HERE, "checks_lib.py"))
cl = importlib.util.module_from_spec(spec); spec.loader.exec_module(cl)
for name in sorted(cl.CHECKS):
    jobs.append(J(f"inv:{name}", "integrity", "invariants", f"python3 checks_lib.py {name}", gate=True))

# PROGRESS · per-phase (uses realize.measure; green when phase complete)
for ph in ("P1", "P2", "P3", "P4", "P5", "P6"):
    chk = ("python3 -c \"import realize,sys;d,t,_=realize.measure('%s');"
           "sys.exit(0 if d>=t and t>0 else 1)\"") % ph
    jobs.append(J(f"phase:{ph}", "progress", "phases", chk,
                  nudge=f"advance {ph}: run `realize.py worklist {ph}` and execute the next item"))

# PROGRESS · per remaining tool (exists yet?)
for t in ("route", "clkfab", "ps_realize", "map", "unify"):
    jobs.append(J(f"todo:{t}", "progress", "remaining_tools",
                  f"test -f {os.path.join(HERE, t + '.py')}",
                  nudge=f"build {t}.py (next phase tool)"))

out = {"generated_from": "jobgen.py", "count": len(jobs), "jobs": jobs}
json.dump(out, open(os.path.join(HERE, "jobs.json"), "w"), indent=2)
ig = sum(1 for j in jobs if j["kind"] == "integrity")
print(f"jobgen: {len(jobs)} jobs -> jobs.json  ({ig} integrity, {len(jobs)-ig} progress)")
