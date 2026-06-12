#!/usr/bin/env python3
"""check_elaborated.py — THE validator for the EDA pipeline (description + library).

Enforces the two laws the pipeline rests on:

  COMPOSITION-ONLY (nothing lives in code/AI memory):
    * every instance in the description AND in every library composite resolves to
      a REAL library component (atom or composite). A component named but not in
      the library exists only in the description's words — forbidden.
    * descriptions/composites carry only structural fields (ports/instances/
      connections/params) — no field in which to write raw logic or values.

  FLIP-FLOPPED + ADDRESSABLE (or it isn't in the system):
    * the elaborated design flattens to ATOMS ONLY (flip-flops + gates in C) —
      no composite/black-box survives. Everything is flip-flopped to the atom.
    * every node gets a unique address; every reference (a comb input, a dff
      fed_by/enable, a seam source) RESOLVES to an addressed node. An unaddressed
      reference would exist only in code/AI memory — fail.
    * single-writer (unique node names) / no-floating (all refs resolve).

It reuses THE elaborator (elaborate.py) to flatten — no duplicate flatten logic.

Usage: check_elaborated.py <design>.desc.yaml
Exit 0 = PASS; 1 = FAIL with the offending detail.
"""
import json
import os
import subprocess
import sys

try:
    import yaml
except Exception:
    sys.stderr.write("check_elaborated: PyYAML required\n")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
STAGING = os.path.normpath(os.path.join(HERE, ".."))
LIB = os.path.join(STAGING, "library")
ELABORATE = os.path.join(STAGING, "elaborate.py")

DESC_KEYS = {"design", "kind", "ports", "instances", "connections", "comment"}
COMP_KEYS = {"component", "params", "ports", "body", "comment"}
BODY_KEYS = {"instances", "connections"}


def load_library():
    import glob
    a = yaml.safe_load(open(os.path.join(LIB, "atoms.yaml"))) or {}
    atoms = {**(a.get("gates") or {}), **(a.get("flip_flops") or {})}
    cpath = os.path.join(LIB, "conductors.yaml")
    conductors = ((yaml.safe_load(open(cpath)) or {}).get("conductors", {})
                  if os.path.exists(cpath) else {})
    comps = {}
    for f in glob.glob(os.path.join(LIB, "components", "*.comp.yaml")):
        c = yaml.safe_load(open(f))
        comps[c["component"]] = c
    return atoms, conductors, comps


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: check_elaborated.py <design>.desc.yaml\n"); sys.exit(2)
    desc_path = sys.argv[1]
    atoms, conductors, comps = load_library()
    known = set(atoms) | set(conductors) | set(comps)
    errs = []

    # ---- (1) composition-only: every component resolves; only structural fields
    design = yaml.safe_load(open(desc_path))
    extra = set(design) - DESC_KEYS
    if extra:
        errs.append(f"description has non-structural fields {sorted(extra)} "
                    f"(composition only — no place to author logic/values)")
    for inst in design.get("instances", []) or []:
        if inst.get("component") not in known:
            errs.append(f"description instance '{inst.get('name')}' uses '{inst.get('component')}' "
                        f"— NOT in the library (exists only in the description = code/AI memory)")
    # every library composite must itself resolve + be structural
    for cname, c in comps.items():
        ex = set(c) - COMP_KEYS
        if ex:
            errs.append(f"library composite '{cname}' has non-structural fields {sorted(ex)}")
        body = c.get("body", {})
        bex = set(body) - BODY_KEYS
        if bex:
            errs.append(f"library composite '{cname}'.body has non-structural fields {sorted(bex)}")
        for inst in body.get("instances", []) or []:
            if inst.get("component") not in known:
                errs.append(f"library composite '{cname}' instance '{inst.get('name')}' uses "
                            f"'{inst.get('component')}' — NOT in the library")

    # ---- (2) elaborate (reuse THE elaborator) and validate the flat netlist
    r = subprocess.run([sys.executable, ELABORATE, desc_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        # elaborate already rejects floating/multi-writer/unknown-component
        errs.append("elaboration FAILED: " + (r.stderr.strip() or "(no detail)"))
    elif not errs:
        net = json.loads(r.stdout)
        if net.get("kind") != "elaborated":
            errs.append(f"elaborated netlist kind must be 'elaborated' (got {net.get('kind')!r})")
        # atoms-only: every comb cell + dff must be a library atom
        for c in net.get("comb_nodes", []):
            if c.get("cell") not in atoms:
                errs.append(f"comb node '{c.get('name')}' cell '{c.get('cell')}' is not an "
                            f"atom — design did not flatten to flip-flops/gates")
        # addressability: unique names (single-writer) + every reference resolves
        names = []
        for grp in ("config_nodes", "const_nodes", "dff_nodes", "comb_nodes", "seam_nodes"):
            for n in net.get(grp, []):
                names.append(n["name"])
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            errs.append(f"single-writer violation — duplicate addressable names: {dupes}")
        addr = set(names)
        def ref(x, where):
            if x is not None and x not in addr:
                errs.append(f"unaddressed reference '{x}' ({where}) — resolves to nothing; "
                            f"it would exist only in code/AI memory")
        for c in net.get("comb_nodes", []):
            for i in c.get("inputs", []):
                ref(i, f"comb {c['name']} input")
        for d in net.get("dff_nodes", []):
            ref(d.get("fed_by"), f"dff {d['name']} fed_by")
            ref(d.get("enable"), f"dff {d['name']} enable")
        for s in net.get("seam_nodes", []):
            ref(s.get("source"), f"seam {s['name']} source")
        n_addr = len(set(names))

    if errs:
        print(f"check_elaborated: FAIL {os.path.basename(desc_path)}:")
        for e in errs:
            print(f"  ERROR: {e}")
        sys.exit(1)
    print(f"check_elaborated: PASS {design.get('design')} — composition-only, flattened to "
          f"atoms (flip-flops/gates), {n_addr} addressable nodes, single-writer, no-floating")
    sys.exit(0)


if __name__ == "__main__":
    main()
