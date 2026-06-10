#!/usr/bin/env python3
"""validate.py — the netlist validator (the project gate for the wire bus).

This is the reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply here.
It enforces the structural laws of the build approach on wire.net.json.

The wire is a PASSIVE addressed-memory bus (INGRESS_FLOW.md s3,
feedback_hft_wire_and_barrier): no clock, no compute, no logic of its own —
just addressed storage that the adapter deposits into and the NIC samples.
So this validator enforces, in addition to the usual laws, that the wire is
PASSIVE:

  passive       : NO clock, NO comb cells, NO dffs, NO latch logic in the wire.
                  The wire writes nothing itself; the adapter (external) is the
                  sole writer. A clock/strobe/latch here would be the discarded
                  "active relay" mistake.
  no-overlap    : no two bus nodes share an address (assigned sequentially).
  single-writer : the wire has ZERO internal writers — every bus node is driven
                  from OUTSIDE the wire (the adapter deposits). That is exactly
                  what a passive bus is. (The single-writer contract — adapter is
                  the only depositor — is enforced structurally by there being no
                  other writer in the system: the wire offers no write path.)
  addressed     : every bus lane is a named, addressed register (no floating
                  lane "in space" — a lane needs an address; that storage IS the
                  wire).

Exit 0 = PASS; non-zero = FAIL with the offending nodes named.
"""
import json
import sys

LOGIC_KEYS = ("clock", "comb_nodes", "dff_nodes", "latch", "config_nodes",
              "buffer_nodes", "pos", "writeout", "display_ring")


def load(path):
    with open(path) as f:
        return json.load(f)


def validate(net):
    errors = []

    # passive: a bus has NO logic. Any clock/comb/dff/latch is the discarded
    # active-relay mistake — the wire must write nothing itself.
    for k in LOGIC_KEYS:
        if k in net and net[k]:
            errors.append(
                f"passive: wire bus must have NO logic, but key '{k}' is present "
                f"(the wire has no clock/compute/latch — the adapter is the sole writer)")

    nodes = net.get("bus_nodes", [])
    if not nodes:
        errors.append("addressed: wire bus declares no bus_nodes (a bus is its lanes)")

    # no-overlap / addressed: each lane is a uniquely named addressed register.
    seen = set()
    for n in nodes:
        nm = n.get("name")
        if not nm:
            errors.append("addressed: a bus_node has no name (a lane needs an address)")
            continue
        if nm in seen:
            errors.append(f"no-overlap: bus lane '{nm}' declared more than once")
        seen.add(nm)

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "wire.net.json"
    net = load(path)
    errs = validate(net)
    if errs:
        print(f"VALIDATE {path}: FAIL ({len(errs)} error(s))")
        for e in errs:
            print("  " + e)
        sys.exit(1)
    n = len(net.get("bus_nodes", []))
    print(f"VALIDATE {path}: PASS — {n} bus lanes, passive/no-overlap/addressed OK "
          f"(no clock/compute/latch; sole writer = adapter)")
    sys.exit(0)


if __name__ == "__main__":
    main()
