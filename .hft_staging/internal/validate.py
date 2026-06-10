#!/usr/bin/env python3
"""validate.py — netlist validator for a counter-clock (the project gate).

The reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply. Enforces the
structural laws on <clock>.net.json:

  single-writer : every dff node has exactly one writer (the counter / edge);
                  config nodes are inputs (zero internal writers).
  no-overlap    : no two nodes share an address (node names are the address keys).
  no-floating   : every referenced node (counter.reg/power/increment, edge.reg/
                  power, run_power, run_bound.count/limit) is a declared node.

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

    # no-overlap: duplicate node name == address overlap.
    seen = set()
    for nm in names:
        if nm in seen:
            errors.append(f"no-overlap: node '{nm}' declared more than once")
        seen.add(nm)
    declared = set(names)

    config = {n["name"] for n in net.get("config_nodes", [])}
    writers = {nm: [] for nm in names}

    counter = net["counter"]
    if counter["reg"] in writers:
        writers[counter["reg"]].append("counter")
    edge = net.get("edge")
    if edge and edge["reg"] in writers:
        writers[edge["reg"]].append("edge")

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

    # no-floating: every referenced node must be declared.
    def ref(who, nm):
        if nm is not None and nm not in declared:
            errors.append(f"no-floating: '{who}' references undeclared node '{nm}'")

    ref("counter.reg", counter["reg"])
    ref("counter.power", counter["power"])
    ref("counter.increment", counter.get("increment"))
    if edge:
        ref("edge.reg", edge["reg"])
        ref("edge.power", edge["power"])
    ref("run_power", net.get("run_power"))
    rb = net.get("run_bound")
    if rb:
        ref("run_bound.count", rb["count"])
        ref("run_bound.limit", rb["limit"])

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "taisoc.net.json"
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
