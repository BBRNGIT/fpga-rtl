#!/usr/bin/env python3
"""validate.py — the netlist validator (the project gate for the adapter device).

This is the reviewer for C-as-RTL work — semgrep/CVE/npm do NOT apply here.
It enforces the structural laws of the build approach on adapter.net.json:

  single-writer : every node has exactly one writer (one driver).
  no-overlap    : no two nodes share an address (assigned here, sequentially).
  no-floating   : every input referenced by a cell/lane/clock/pos exists as a
                  declared node (no operand is a ghost — every value is backed
                  by a register).

Exit 0 = PASS; non-zero = FAIL with the offending nodes named.
"""
import json
import sys


def load(path):
    with open(path) as f:
        return json.load(f)


def ring_node_names(net):
    dr = net.get("display_ring")
    names = []
    if dr:
        names.append(dr["count"])
        for s in range(dr["depth"]):
            for fld in dr["fields"]:
                names.append(f"DISP_{s}_{fld}")
    return names


def all_nodes(net):
    names = []
    for grp in ("config_nodes", "buffer_nodes", "dff_nodes", "comb_nodes"):
        for n in net.get(grp, []):
            names.append(n["name"])
    names.extend(ring_node_names(net))
    return names


def validate(net):
    errors = []
    names = all_nodes(net)

    # no-overlap: node names are the address keys; duplicates = address overlap.
    seen = set()
    for nm in names:
        if nm in seen:
            errors.append(f"no-overlap: node '{nm}' declared more than once")
        seen.add(nm)
    declared = set(names)

    # single-writer: collect every (writer -> node) edge and count writers/node.
    writers = {nm: [] for nm in names}

    # comb nodes: each is driven by its own cell.
    for n in net.get("comb_nodes", []):
        writers[n["name"]].append("comb:" + n.get("cell", "?"))

    # dff nodes driven by the clock / pos / writeout sections.
    clk = net["clock"]
    writers[clk["counter"]].append("clock")
    pos = net["pos"]
    writers[pos["counter"]].append("pos")
    wo = net["writeout"]
    for lane in wo["lanes"]:
        writers[lane["out"]].append("writeout")
    writers[wo["valid"]].append("writeout")

    # display ring: each ring node (and the emit counter) driven by display_ring.
    for nm in ring_node_names(net):
        writers[nm].append("display_ring")

    # config + buffer nodes are device inputs (driven from outside the netlist:
    # power bit set by starter; buffer presented by the buffer primitive). They
    # legitimately have zero internal writers — they are source lanes.
    input_nodes = set()
    for grp in ("config_nodes", "buffer_nodes"):
        for n in net.get(grp, []):
            input_nodes.add(n["name"])

    for nm in names:
        w = writers[nm]
        if nm in input_nodes:
            if w:
                errors.append(f"single-writer: input node '{nm}' has internal writer(s) {w}")
            continue
        if len(w) == 0:
            errors.append(f"single-writer: node '{nm}' has no writer (floating output)")
        elif len(w) > 1:
            errors.append(f"single-writer: node '{nm}' has {len(w)} writers {w}")

    # no-floating: every referenced input must be a declared node.
    def ref(node_name, ref_name):
        if ref_name not in declared:
            errors.append(f"no-floating: '{node_name}' references undeclared node '{ref_name}'")

    for n in net.get("comb_nodes", []):
        for inp in n.get("inputs", []):
            ref(n["name"], inp)
    ref("clock", clk["power"])
    if "step" in clk:
        ref("clock", clk["step"])
    ref("pos", pos["increment"])
    ref("writeout", wo["enable"])
    for lane in wo["lanes"]:
        ref("writeout", lane["from"])

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "adapter.net.json"
    net = load(path)
    errs = validate(net)
    if errs:
        print(f"VALIDATE {path}: FAIL ({len(errs)} error(s))")
        for e in errs:
            print("  " + e)
        sys.exit(1)
    n = len(all_nodes(net))
    print(f"VALIDATE {path}: PASS — {n} nodes, single-writer/no-overlap/no-floating OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
