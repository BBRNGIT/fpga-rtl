#!/usr/bin/env python3
"""Generate plle4_adv.json and mmcme4_adv.json block definitions.

PLLE4_ADV = PLLE4_BASE + DRP (UG572 Table 3-10).
MMCME4_ADV = the 35-port advanced MMCM (clock_switch + MMCME4_BASE + drp + phase_shift + cddc).

DRP buses (DADDR[7], DI[16], DO[16]) are connected per-bit when instantiating
the `drp` block, since its ports are buses.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def drp_conn():
    """Per-bit + scalar DRP connection map: each drp pin -> same-named parent net."""
    conn = {"DCLK": "DCLK", "DEN": "DEN", "DWE": "DWE", "DRDY": "DRDY"}
    for b in range(7):
        conn[f"DADDR[{b}]"] = f"DADDR[{b}]"
    for b in range(16):
        conn[f"DI[{b}]"] = f"DI[{b}]"
    for b in range(16):
        conn[f"DO[{b}]"] = f"DO[{b}]"
    return conn


def plle4_adv():
    plle4_base_pins = {
        "CLKIN": "CLKIN", "CLKFBIN": "CLKFBIN", "RST": "RST",
        "PWRDWN": "PWRDWN", "CLKOUTPHYEN": "CLKOUTPHYEN",
        "CLKOUT0": "CLKOUT0", "CLKOUT0B": "CLKOUT0B",
        "CLKOUT1": "CLKOUT1", "CLKOUT1B": "CLKOUT1B",
        "CLKFBOUT": "CLKFBOUT", "CLKOUTPHY": "CLKOUTPHY", "LOCKED": "LOCKED",
    }
    ports = [
        {"name": "CLKIN", "dir": "in", "kind": "clock"},
        {"name": "CLKFBIN", "dir": "in", "kind": "clock"},
        {"name": "RST", "dir": "in"},
        {"name": "PWRDWN", "dir": "in"},
        {"name": "CLKOUTPHYEN", "dir": "in"},
        {"name": "DCLK", "dir": "in", "kind": "clock"},
        {"name": "DEN", "dir": "in"},
        {"name": "DWE", "dir": "in"},
        {"name": "DADDR", "dir": "in", "width": 7},
        {"name": "DI", "dir": "in", "width": 16},
        {"name": "CLKOUT0", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT0B", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT1", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT1B", "dir": "out", "kind": "clock"},
        {"name": "CLKFBOUT", "dir": "out", "kind": "clock"},
        {"name": "CLKOUTPHY", "dir": "out", "kind": "clock"},
        {"name": "LOCKED", "dir": "out"},
        {"name": "DO", "dir": "out", "width": 16},
        {"name": "DRDY", "dir": "out"},
    ]
    cells = [
        {"ref": "pll", "type": "PLLE4_BASE", "conn": plle4_base_pins},
        {"ref": "drp", "type": "drp", "conn": drp_conn()},
    ]
    return {
        "name": "plle4_adv",
        "group": "clocking",
        "spec": "UG572 Table 3-10: PLLE4_ADV = PLLE4_BASE + DRP only.",
        "ports": ports,
        "cells": cells,
        "nets": [],
    }


def mmcme4_adv():
    base_conn = {
        "CLKIN1": "clkin_sel", "CLKFBIN": "CLKFBIN",
        "RST": "RST", "PWRDWN": "PWRDWN",
    }
    for n in ["CLKOUT0", "CLKOUT1", "CLKOUT2", "CLKOUT3", "CLKOUT4",
              "CLKOUT5", "CLKOUT6", "CLKOUT0B", "CLKOUT1B", "CLKOUT2B",
              "CLKOUT3B", "CLKFBOUT", "CLKFBOUTB", "LOCKED"]:
        base_conn[n] = n

    cs_conn = {
        "CLKIN1": "CLKIN1", "CLKIN2": "CLKIN2",
        "CLKINSEL": "CLKINSEL", "CLKFBIN": "CLKFBIN",
        "CLKIN": "clkin_sel",
        "CLKINSTOPPED": "CLKINSTOPPED", "CLKFBSTOPPED": "CLKFBSTOPPED",
    }

    ps_conn = {
        "PSCLK": "PSCLK", "PSEN": "PSEN", "PSINCDEC": "PSINCDEC",
        "PSDONE": "PSDONE",
    }

    cddc_conn = {"D": "CDDCREQ", "CLK": "DCLK", "Q": "CDDCDONE"}

    ports = [
        {"name": "CLKIN1", "dir": "in", "kind": "clock"},
        {"name": "CLKIN2", "dir": "in", "kind": "clock"},
        {"name": "CLKFBIN", "dir": "in", "kind": "clock"},
        {"name": "DCLK", "dir": "in", "kind": "clock"},
        {"name": "PSCLK", "dir": "in", "kind": "clock"},
        {"name": "RST", "dir": "in"},
        {"name": "PWRDWN", "dir": "in"},
        {"name": "CLKINSEL", "dir": "in"},
        {"name": "DWE", "dir": "in"},
        {"name": "DEN", "dir": "in"},
        {"name": "PSINCDEC", "dir": "in"},
        {"name": "PSEN", "dir": "in"},
        {"name": "CDDCREQ", "dir": "in"},
        {"name": "DADDR", "dir": "in", "width": 7},
        {"name": "DI", "dir": "in", "width": 16},
        {"name": "CLKOUT0", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT1", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT2", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT3", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT4", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT5", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT6", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT0B", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT1B", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT2B", "dir": "out", "kind": "clock"},
        {"name": "CLKOUT3B", "dir": "out", "kind": "clock"},
        {"name": "CLKFBOUT", "dir": "out", "kind": "clock"},
        {"name": "CLKFBOUTB", "dir": "out", "kind": "clock"},
        {"name": "LOCKED", "dir": "out"},
        {"name": "DO", "dir": "out", "width": 16},
        {"name": "DRDY", "dir": "out"},
        {"name": "PSDONE", "dir": "out"},
        {"name": "CLKINSTOPPED", "dir": "out"},
        {"name": "CLKFBSTOPPED", "dir": "out"},
        {"name": "CDDCDONE", "dir": "out"},
    ]
    cells = [
        {"ref": "cswitch", "type": "clock_switch", "conn": cs_conn},
        {"ref": "mmcm", "type": "MMCME4_BASE", "conn": base_conn},
        {"ref": "drp", "type": "drp", "conn": drp_conn()},
        {"ref": "pshift", "type": "phase_shift", "conn": ps_conn},
        {"ref": "cddc", "type": "dff_d", "conn": cddc_conn},
    ]
    return {
        "name": "mmcme4_adv",
        "group": "clocking",
        "spec": "MMCME4_ADV (35-port): clock_switch + MMCME4_BASE + DRP + phase_shift + CDDC handshake.",
        "ports": ports,
        "cells": cells,
        "nets": ["clkin_sel"],
    }


def main():
    for blk in (plle4_adv(), mmcme4_adv()):
        path = os.path.join(HERE, blk["name"] + ".json")
        with open(path, "w") as f:
            json.dump(blk, f, indent=2)
            f.write("\n")
        print("wrote", path)


if __name__ == "__main__":
    main()
