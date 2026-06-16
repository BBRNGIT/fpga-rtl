#!/usr/bin/env python3
"""
gate_library.py — the LIBRARY-WIDE completeness gate. The C cell library is
"done" only when EVERY UNISIM .v has a passing .c twin (per gate_replica.py).

Conservation at the library level: count(.v) == count(passing .c twins).
Any .v with no twin, or a twin that fails its per-file gate, fails this gate.

Exit 0 = library complete + all twins pass. 1 = incomplete or a twin fails.

Usage:
  gate_library.py                # full report: total .v, twins, passing, missing
  gate_library.py --staged FILE… # gate only the named (staged) .c files (for the hook)
"""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
V4   = os.path.dirname(HERE)
ROOT = os.path.dirname(V4)
VSRC = os.path.join(ROOT, "unisim_src", "verilog", "src")
CLIB = os.path.join(V4, "clib")
GATE = os.path.join(HERE, "gate_replica.py")

def all_v_names():
    names = []
    for base, _d, files in os.walk(VSRC):
        for f in files:
            if f.endswith(".v"):
                names.append(f[:-2])
    return sorted(set(names))

def gate(name):
    r = subprocess.run([sys.executable, GATE, name], capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip()

def report():
    vnames = all_v_names()
    passing, missing, failing = [], [], []
    for n in vnames:
        # twin present?
        twin = None
        for base, _d, files in os.walk(CLIB):
            if f"{n}.c" in files: twin = os.path.join(base, f"{n}.c"); break
        if not twin:
            missing.append(n); continue
        ok, _ = gate(n)
        (passing if ok else failing).append(n)
    total = len(vnames)
    print(f"== C cell library completeness ==")
    print(f"  UNISIM .v primitives : {total}")
    print(f"  passing .c twins     : {len(passing)}")
    print(f"  failing twins        : {len(failing)}  {failing[:8]}")
    print(f"  missing twins        : {len(missing)}  {missing[:8]}")
    complete = (len(passing) == total)
    print(f"\n  LIBRARY {'COMPLETE — all twins pass' if complete else 'INCOMPLETE'}")
    return complete

def gate_staged(files):
    bad = []
    for f in files:
        if not f.endswith(".c") or f.endswith(".test.c"): continue
        name = os.path.basename(f)[:-2]
        ok, out = gate(name)
        print(out)
        if not ok: bad.append(name)
    if bad:
        print(f"\n[hook] BLOCKED — {len(bad)} twin(s) fail their replica gate: {bad}")
        return False
    return True

def main():
    ap = argparse.ArgumentParser(description="library-wide UNISIM C-twin completeness gate")
    ap.add_argument("--staged", nargs="*", help="gate only these staged .c files (hook mode)")
    a = ap.parse_args()
    if a.staged is not None:
        sys.exit(0 if gate_staged(a.staged) else 1)
    sys.exit(0 if report() else 1)

if __name__ == "__main__":
    main()
