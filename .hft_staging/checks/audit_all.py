#!/usr/bin/env python3
"""audit_all.py — repo-wide conformance auditor (C2).

ONE deterministic answer to "is the codebase conformant." Runs the full gate on
every buildable component, the EDA validator on every description, and the global
checks (blank-identity, factory-contracts). Prints a PASS/FAIL ledger; exits
non-zero if ANYTHING fails. Used by the gate-forcing hook, by CI/cron, and by the
orchestrator before claiming any milestone done — correctness stops depending on
anyone remembering to run individual checks.

Usage:
    python3 checks/audit_all.py            # full audit (all components + globals)
    python3 checks/audit_all.py <names...> # audit only the named components/descriptions
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STAGING = os.path.normpath(os.path.join(HERE, ".."))
GATE = os.path.join(STAGING, "gate.sh")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def is_component(d):
    return os.path.isfile(os.path.join(d, "Makefile")) and glob.glob(os.path.join(d, "*.net.json"))


def main():
    only = set(sys.argv[1:])
    results = []   # (label, ok, detail)

    # 1) every buildable component -> full gate
    for d in sorted(glob.glob(os.path.join(STAGING, "*"))):
        name = os.path.basename(d)
        if not is_component(d):
            continue
        if only and name not in only:
            continue
        rc, out = run([GATE, d])
        ok = (rc == 0)
        tail = next((l for l in reversed(out.splitlines()) if "PASS" in l or "FAIL" in l or "[FAIL]" in l), "")
        results.append((f"component {name}", ok, tail.strip()))

    # 2) every description -> EDA validator (check_elaborated)
    chk_elab = os.path.join(HERE, "check_elaborated.py")
    if os.path.isfile(chk_elab):
        for desc in sorted(glob.glob(os.path.join(STAGING, "descriptions", "*.desc.yaml"))):
            name = os.path.basename(desc)
            if only and name not in only and name.replace(".desc.yaml", "") not in only:
                continue
            rc, out = run([sys.executable, chk_elab, desc])
            results.append((f"description {name}", rc == 0, out.strip().splitlines()[-1] if out.strip() else ""))

    # 3) global checks (run once, when doing a full audit)
    if not only:
        for g in ("check_blank_identity.py", "check_factory_contracts.py"):
            p = os.path.join(HERE, g)
            if os.path.isfile(p):
                rc, out = run([sys.executable, p])
                results.append((f"global {g}", rc == 0, out.strip().splitlines()[-1] if out.strip() else ""))

    # ---- ledger ----
    fails = [r for r in results if not r[1]]
    print("=== CONFORMANCE AUDIT ===")
    for label, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {label:<28} {detail}")
    print(f"=== {len(results) - len(fails)}/{len(results)} pass"
          + (f" | FAILED: {', '.join(l for l, o, _ in fails if not o)}" if fails else " | ALL CONFORMANT") + " ===")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
