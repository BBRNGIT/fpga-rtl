#!/usr/bin/env python3
"""Generate the DRP (MMCM Dynamic Reconfiguration Port) block definition.

A byte-addressed 16-bit register file. Per UG572 Fig 3-23.
Emits blocks/drp.json. Uses 2-input gates only.
"""
import json
import os

ADDRS = [0x00, 0x04, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D,
         0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x18,
         0x19, 0x1A, 0x27, 0x4E, 0x4F]


def main():
    cells = []
    nets = set()

    def add_net(n):
        nets.add(n)

    # Build a chain of 2-input gates reducing `inputs` to a single net.
    # The chain's final output is forced to `final_net`; intermediates use
    # `prefix_<k>`. Returns nothing (drives final_net).
    def reduce_to(inputs, gate, prefix, final_net):
        acc = inputs[0]
        n = len(inputs)
        for k in range(1, n):
            nxt = inputs[k]
            out = final_net if k == n - 1 else f"{prefix}_{k}"
            cells.append({"ref": f"{prefix}_g{k}", "type": gate,
                          "conn": {"A": acc, "B": nxt, "O": out}})
            add_net(out)
            acc = out

    # input ports drive nets
    for b in range(7):
        add_net(f"DADDR[{b}]")
    for i in range(16):
        add_net(f"DI[{i}]")
    add_net("DEN")
    add_net("DWE")
    add_net("DCLK")

    for a in ADDRS:
        al = f"{a:02x}"
        # 1) address-constant: 7 cfgcell
        for b in range(7):
            net = f"acfg_{al}_{b}"
            cells.append({"ref": f"acfg_{al}_{b}", "type": "cfgcell",
                          "conn": {"Q": net}})
            add_net(net)
        # 2) compare: 7 xnor
        ab_nets = []
        for b in range(7):
            out = f"ab_{al}_{b}"
            cells.append({"ref": f"cmp_{al}_{b}", "type": "xnor",
                          "conn": {"A": f"DADDR[{b}]", "B": f"acfg_{al}_{b}",
                                   "O": out}})
            add_net(out)
            ab_nets.append(out)
        # 3) and-reduce 7 ab bits -> match_<a>
        reduce_to(ab_nets, "and", f"matchr_{al}", f"match_{al}")
        add_net(f"match_{al}")
        # 4) write-enable: and(match, DEN -> wm); and(wm, DWE -> wen)
        cells.append({"ref": f"wm_{al}", "type": "and",
                      "conn": {"A": f"match_{al}", "B": "DEN",
                               "O": f"wm_{al}"}})
        add_net(f"wm_{al}")
        cells.append({"ref": f"wen_{al}", "type": "and",
                      "conn": {"A": f"wm_{al}", "B": "DWE",
                               "O": f"wen_{al}"}})
        add_net(f"wen_{al}")
        # 5) register: 16 bits, mux2 feedback + dff_d
        for i in range(16):
            cells.append({"ref": f"mux_{al}_{i}", "type": "mux2",
                          "conn": {"A": f"q_{al}_{i}", "B": f"DI[{i}]",
                                   "S": f"wen_{al}", "O": f"d_{al}_{i}"}})
            add_net(f"d_{al}_{i}")
            cells.append({"ref": f"reg_{al}_{i}", "type": "dff_d",
                          "conn": {"D": f"d_{al}_{i}", "CLK": "DCLK",
                                   "Q": f"q_{al}_{i}"}})
            add_net(f"q_{al}_{i}")

    # DO read mux: for each bit i, AND each address's match with its q,
    # then OR-tree the 25 results -> DO[i]
    for i in range(16):
        rmk_nets = []
        for a in ADDRS:
            al = f"{a:02x}"
            out = f"rmk_{al}_{i}"
            cells.append({"ref": f"rmk_{al}_{i}", "type": "and",
                          "conn": {"A": f"match_{al}", "B": f"q_{al}_{i}",
                                   "O": out}})
            add_net(out)
            rmk_nets.append(out)
        reduce_to(rmk_nets, "or", f"dotree_{i}", f"DO[{i}]")
        add_net(f"DO[{i}]")

    # DRDY: dff_d(D=DEN, CLK=DCLK, Q=DRDY)
    cells.append({"ref": "drdy_reg", "type": "dff_d",
                  "conn": {"D": "DEN", "CLK": "DCLK", "Q": "DRDY"}})
    add_net("DRDY")

    ports = [
        {"name": "DCLK", "dir": "in", "kind": "clock"},
        {"name": "DEN", "dir": "in"},
        {"name": "DWE", "dir": "in"},
        {"name": "DADDR", "dir": "in", "width": 7},
        {"name": "DI", "dir": "in", "width": 16},
        {"name": "DO", "dir": "out", "width": 16},
        {"name": "DRDY", "dir": "out"},
    ]

    block = {
        "name": "drp",
        "group": "Clock management",
        "spec": "UG572 Fig 3-23",
        "ports": ports,
        "cells": cells,
        "nets": sorted(nets),
    }

    here = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(here, "drp.json")
    with open(out_path, "w") as f:
        json.dump(block, f, indent=1)
    print(f"wrote {out_path}: {len(cells)} cells, {len(nets)} nets")


if __name__ == "__main__":
    main()
