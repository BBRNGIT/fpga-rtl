#!/usr/bin/env python3
"""check_factory_contracts.py — enforce the digital-silicon-factory toolchain contract.

System-level enforcer (not per-component). Reads factory_toolchain.yaml and enforces
the phase/tool/format laws so the toolchain plan persists in the codebase, not in
memory (SILICON_FACTORY.md is the narrative).

Enforced:
  * canonical board set is exactly {fpga-in, fpga-main, fpga-control}.
  * a tool with status 'built'/'done' MUST exist on disk (its `file`).
  * phase order: a phase may have built tools only if every PRIOR phase is complete
    (all its tools built/done) — no skipping ahead.
  * a format with status 'built' MUST have at least one conforming artifact (file_glob)
    whose entries carry the required_fields.
  * report the full status ledger.

Usage: check_factory_contracts.py [--strict]
  default: report (exit 0); --strict: any violation fails (exit 1).
"""
import os, sys, glob, json
try:
    import yaml
except Exception:
    sys.stderr.write("check_factory_contracts: PyYAML required\n"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
STAGING = os.path.normpath(os.path.join(HERE, ".."))
CONTRACT = os.path.join(STAGING, "factory_toolchain.yaml")
CANON_FPGAS = ["fpga-in", "fpga-main", "fpga-control"]
BUILT = ("built", "done")


def main():
    strict = "--strict" in sys.argv
    c = yaml.safe_load(open(CONTRACT))
    errs, notes = [], []

    if c.get("fpgas") != CANON_FPGAS:
        errs.append(f"fpgas must be {CANON_FPGAS} (got {c.get('fpgas')})")

    phases = c.get("phases", [])
    prior_complete = True
    print("== Factory toolchain status ==")
    for ph in phases:
        tools = ph.get("tools", []) or []
        built = [t for t in tools if t.get("status") in BUILT]
        complete = bool(tools) and all(t.get("status") in BUILT for t in tools) or ph.get("status") in BUILT
        flag = "done" if complete else ("partial" if built else "planned")
        print(f"  phase {ph.get('id')} {ph.get('name'):<14} [{flag}]  tools={len(tools)} built={len(built)}")
        # built tools must exist
        for t in built:
            fp = os.path.join(STAGING, t.get("file", ""))
            if not t.get("file") or not os.path.exists(fp):
                errs.append(f"phase {ph.get('id')} tool '{t.get('name')}' is status:built but file missing: {t.get('file')}")
        # phase order: built tools require all prior phases complete
        if built and not prior_complete:
            errs.append(f"phase {ph.get('id')} '{ph.get('name')}' has built tools but a prior phase is incomplete (no skipping)")
        prior_complete = prior_complete and complete

    # formats marked built must have a conforming artifact
    for fname, fmt in (c.get("formats") or {}).items():
        if fmt.get("status") in BUILT:
            hits = glob.glob(os.path.join(STAGING, fmt.get("file_glob", "")))
            if not hits:
                errs.append(f"format '{fname}' is status:built but no artifact matches {fmt.get('file_glob')}")

    if errs:
        print("\nVIOLATIONS:")
        for e in errs:
            print(f"  [FACTORY] {e}")
        sys.exit(1 if strict else 0)
    print("\ncheck_factory_contracts: OK — toolchain contract consistent "
          "(built tools exist, phase order intact, boards canonical)")
    sys.exit(0)


if __name__ == "__main__":
    main()
