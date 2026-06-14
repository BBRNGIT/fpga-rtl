#!/usr/bin/env python3
"""
build.py — the v3 build ORCHESTRATOR / harness.

Drives the tool chain with no hand labor: runs each tool, checks its result,
retries on a transient (internal) error, and HALTS with a clear report on a
validation (spec) error. Add tools to STAGES as they are built; the harness
treats them uniformly. Exit 0 only if every stage passes.

Contract (per tool): exit 0 = ok, 1 = validation error (spec is wrong — fix the
format, do not retry), 2 = internal/transient error (retry), other = hard fail.
"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))   # v3_staging/tools -> repo root
PY = sys.executable
RETRIES = 2
PDF   = os.environ.get("SPEC_PDF", os.path.join(REPO, "ug572-ultrascale-clocking.pdf"))
Z19   = os.environ.get("BOARD_PDF", os.path.join(REPO, "Z19.pdf"))
DS891 = os.environ.get("DS_PDF", os.path.join(REPO, "ds891_zynq_ultrascale_plus_overview-1662253.pdf"))
UG974 = os.environ.get("LIB_PDF", os.path.join(REPO, "ug974.pdf"))

# tool chain — the program does it all across all docs:
#   UG (gate-level) -> ports + connections ; board manual -> netlist ; datasheet -> inventory ;
#   integrate -> validate/render ; join all -> the full system block diagram.
def _opt(stage, path):  # skip a doc-extractor cleanly if its PDF isn't present
    return stage if os.path.exists(path) else None
STAGES = [s for s in [
    ("specgen — UG tables -> ports",             [PY, os.path.join(HERE, "specgen.py"), PDF, "--pages", "16-80"]),
    ("figparse — UG figures -> connections",     [PY, os.path.join(HERE, "figparse.py"), PDF, "--pages", "16-30"]),
    _opt(("boardparse — Z19 board -> netlist",   [PY, os.path.join(HERE, "boardparse.py"), Z19, "--pages", "11-74"]), Z19),
    _opt(("dsparse — DS891 -> ZU19EG inventory", [PY, os.path.join(HERE, "dsparse.py"), DS891, "--pages", "1-20"]), DS891),
    _opt(("extract — UG974 -> page cache",       [PY, os.path.join(HERE, "extract.py"), UG974]), UG974),
    _opt(("vparse — UG974 Verilog templates -> primitive ports+params", [PY, os.path.join(HERE, "vparse.py")]), UG974),
    _opt(("catalog — parse FULL cache (all docs) -> complete parts list", [PY, os.path.join(HERE, "catalog.py")]), UG974),
    ("integrate — primitives + templates + blocks/*.json -> library.json", [PY, os.path.join(HERE, "integrate.py")]),
    ("netc — compile + validate + render",       [PY, os.path.join(HERE, "netc.py")]),
    ("figdiff — figure-vs-template connection checkpoint", [PY, os.path.join(HERE, "figdiff.py")]),
    ("progress — render transcription dashboard",  [PY, os.path.join(HERE, "progress.py")]),
    ("blockmap — join all docs -> system block diagram", [PY, os.path.join(HERE, "blockmap.py")]),
] if s]

def run_stage(name, cmd):
    for attempt in range(1, RETRIES + 1):
        print(f"\n[build] ▶ {name}  (attempt {attempt}/{RETRIES})")
        try:
            rc = subprocess.run(cmd).returncode
        except Exception as e:
            print(f"[build]   launch error: {e}")
            rc = 2
        if rc == 0:
            print(f"[build]   ✓ PASS")
            return 0
        if rc == 2 and attempt < RETRIES:
            print(f"[build]   transient error (exit 2) — retrying")
            continue
        if rc == 1:
            print(f"[build]   ✗ VALIDATION FAILED — the format is wrong; fix it, do not retry")
            return 1
        print(f"[build]   ✗ FAILED (exit {rc})")
        return rc
    return 2

def main():
    print(f"[build] v3 orchestrator — {len(STAGES)} stage(s)")
    for name, cmd in STAGES:
        rc = run_stage(name, cmd)
        if rc != 0:
            print(f"\n[build] HALT at '{name}' (exit {rc}). Chain stopped.")
            return rc
    print(f"\n[build] ✓ ALL STAGES PASSED — outputs: explorer.html, device.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())
