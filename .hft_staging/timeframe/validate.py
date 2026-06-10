#!/usr/bin/env python3
"""validate.py — netlist validator for the timeframe rollover detector.

The reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply. Enforces the
structural laws on timeframe.net.json:

  single-writer : every dff node has exactly one writer (bar_seq / bar_closed /
                  bar_start / the run counter); config nodes are inputs (zero
                  internal writers).
  no-overlap    : no two nodes share an address (node names are the address keys).
  no-floating   : every referenced node (power / tai / period / bar_seq /
                  bar_closed / bar_start / run) is a declared node.

Exit 0 = PASS; non-zero = FAIL with the offending nodes named.
"""
import json
import sys


def all_nodes(net):
    names = []
    for grp in ("config_nodes", "dff_nodes"):
        for n in net.get(grp, []):
            names.append(n["name"])
    return names


def validate(net):
    errors = []
    names = all_nodes(net)

    seen = set()
    for nm in names:
        if nm in seen:
            errors.append(f"no-overlap: node '{nm}' declared more than once")
        seen.add(nm)
    declared = set(names)

    config = {n["name"] for n in net.get("config_nodes", [])}
    writers = {nm: [] for nm in names}

    seq = net["bar_seq"]
    closed = net["bar_closed"]
    start = net["bar_start"]
    ticks = net["run"]["count"]
    for nm, who in ((seq, "bar_seq"), (closed, "bar_closed"),
                    (start, "bar_start"), (ticks, "run")):
        if nm in writers:
            writers[nm].append(who)

    for nm in names:
        w = writers[nm]
        if nm in config:
            if w:
                errors.append(f"single-writer: input node '{nm}' has internal writer(s) {w}")
            continue
        if len(w) == 0:
            errors.append(f"single-writer: node '{nm}' has no writer (floating output)")
        elif len(w) > 1:
            errors.append(f"single-writer: node '{nm}' has {len(w)} writers {w}")

    def ref(who, nm):
        if nm is not None and nm not in declared:
            errors.append(f"no-floating: '{who}' references undeclared node '{nm}'")

    ref("power", net["power"])
    ref("tai", net["tai"])
    ref("period", net["period"])
    ref("bar_seq", net["bar_seq"])
    ref("bar_closed", net["bar_closed"])
    ref("bar_start", net["bar_start"])
    ref("run.power", net["run"]["power"])
    ref("run.count", net["run"]["count"])
    ref("run.limit", net["run"]["limit"])

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "timeframe.net.json"
    with open(path) as f:
        net = json.load(f)
    errs = validate(net)
    if errs:
        print(f"VALIDATE {path}: FAIL ({len(errs)} error(s))")
        for e in errs:
            print("  " + e)
        sys.exit(1)
    print(f"VALIDATE {path}: PASS — {len(all_nodes(net))} nodes, "
          "single-writer/no-overlap/no-floating OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
