#!/usr/bin/env python3
"""validate.py — netlist validator for a passive BARRIER bus (the project gate).

Enforces the passive-bus laws on <bus>.net.json:
  passive       : NO clock, NO comb_nodes, NO dff_nodes (a bus owns no logic).
  has-lanes     : at least one bus_node (a bus must carry lanes).
  no-overlap    : bus lanes are uniquely named (assigned sequential addresses).
  addressed     : every lane is a named register (no floating lane).

Exit 0 = PASS; non-zero = FAIL with the offending detail.
"""
import json
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "dom_bus.net.json"
    net = json.load(open(path))
    errs = []

    if net.get("kind") != "passive_bus":
        errs.append(f"kind must be 'passive_bus' (got {net.get('kind')!r})")
    for forbidden in ("clock", "comb_nodes", "dff_nodes"):
        if net.get(forbidden):
            errs.append(f"passive bus must have NO {forbidden} (it owns no logic)")
    lanes = net.get("bus_nodes", [])
    if not lanes:
        errs.append("a bus must declare at least one lane (bus_nodes)")
    names = [n.get("name") for n in lanes]
    if any(not n for n in names):
        errs.append("every lane must be a named register")
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        errs.append(f"duplicate lane names (no-overlap): {dupes}")

    if errs:
        for e in errs:
            sys.stderr.write(f"[validate] FAIL: {e}\n")
        sys.exit(3)
    print(f"[validate] OK — passive bus, {len(lanes)} lanes, single barrier medium")


if __name__ == "__main__":
    main()
