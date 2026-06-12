#!/usr/bin/env python3
"""materialize.py — build the PARAMETRIC device model from authentic inputs.

Materialization rule (founder-adopted, EDA-standard): the blank is a
Device -> Tile(_X#Y#) -> Site(_X#Y#) -> BEL grid, full BEL fidelity, grid-addressed,
with per-tile power-gating (unused hardware can be turned off). FF=cell_dff,
LUT=library lut6, etc. (memory/materialization-rule-tile-site-bel).

This tool consumes ONLY authentic inputs and DESIGNS NOTHING:
  * the verbatim parts manifest (assess_spec.py output) — resource TOTALS,
  * authentic tile composition specs (composition/*.tile.yaml, transcribed from
    the UltraScale architecture user guides).
It derives each tile-type's instance COUNT from the totals and emits a PARAMETRIC
device model (tile type defs + grid counts + per-tile power + coordinate addressing).
It is PARAMETRIC by necessity — full BEL fidelity at VU9P scale (millions of BELs)
is a type+grid description, never a flat per-BEL enumeration; live state is allocated
per used BEL at placement.

Built-in AUTHENTICITY CHECK: the composition cross-checks must agree with the manifest
(e.g. CLBs*16 == manifest flip-flops AND CLBs*8 == manifest LUTs); a mismatch is a
hard error (poison/inconsistency), never silently reconciled.

Honest gaps (flagged, not invented):
  * grid LAYOUT here is a REGULAR MODEL layout (functional), NOT the physical VU9P
    floorplan — physical coordinates require the device DB (RapidWright/prjxray).
  * only tile types with a committed composition spec are BEL-composed; others are
    emitted as typed sites at their manifest count, composition pending their UG.

Usage: python3 materialize.py <parts.json> > device_model.json
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP_DIR = os.path.join(HERE, "composition")


def die(m):
    sys.stderr.write("materialize: " + m + "\n"); sys.exit(2)


def num(v):
    """'2,364' -> 2364 ; '36.1' -> None (not an integer count)."""
    s = str(v).replace(",", "")
    return int(s) if re.fullmatch(r"\d+", s) else None


def manifest_count(parts, key_substr):
    for p in parts:
        if key_substr.lower() in p["resource"].lower():
            return num(p["value"]), p["value"], p["source_line"]
    return None, None, None


def main():
    if len(sys.argv) != 2:
        die("usage: materialize.py <parts.json> > device_model.json")
    man = json.load(open(sys.argv[1]))
    parts = man["parts"]

    # 'K' columns in the selection guide are thousands — the manifest stores the
    # printed value (e.g. '2,364' meaning 2,364 K). Detect the (K) unit per row.
    def total(key_substr):
        for p in parts:
            if key_substr.lower() in p["resource"].lower():
                n = num(p["value"])
                if n is None:
                    return None
                return n * 1000 if "(K)" in p["resource"] else n
        return None

    ff_total = total("CLB Flip-Flops")
    lut_total = total("CLB LUTs")
    if ff_total is None or lut_total is None:
        die("manifest missing CLB Flip-Flops / CLB LUTs totals")

    tile_types = {}
    grid = {}
    warnings = []

    # CLB tile (authentic composition present) ---------------------------------
    clb_path = os.path.join(COMP_DIR, "clb.tile.yaml")
    if os.path.exists(clb_path):
        import yaml
        clb = yaml.safe_load(open(clb_path))
        slice_bels = clb["sites"][0]["bels"]
        ff_per = next(b["count"] for b in slice_bels if b["bel"] == "FF")
        lut_per = next(b["count"] for b in slice_bels if b["bel"] == "LUT6")
        clb_count = ff_total // ff_per
        # authenticity cross-check: composition must agree with the manifest
        if clb_count * ff_per != ff_total:
            die(f"composition mismatch: {clb_count}*{ff_per} != flip-flops {ff_total}")
        if clb_count * lut_per != lut_total:
            die(f"composition mismatch: CLBs*{lut_per}={clb_count*lut_per} != LUTs {lut_total}")
        tile_types["CLB"] = {
            "source": clb["source"],
            "sites": clb["sites"],
            "bels_per_tile": ff_per + lut_per,
        }
        grid["CLB"] = {"count": clb_count, "layout": "regular_model",
                       "addressing": "_X#Y# per Xilinx scheme",
                       "power": "per-tile enable (unused tiles off)"}

    # other resource part types (composition pending their UG) ------------------
    for key, label in (("36K Block RAM", "BRAM36"), ("DSP Slices", "DSP48E2"),
                       ("GTY", "GTY"), ("UltraRAM", "URAM")):
        n, raw, _ = manifest_count(parts, key)
        if n:
            tile_types[label] = {"composition": "pending UG (UG573/UG579/UG578)",
                                 "status": "typed_site_count_only"}
            grid[label] = {"count": n, "layout": "regular_model",
                           "power": "per-tile enable"}
            warnings.append(f"{label}: count {n} only — BEL composition pending its architecture UG")

    out = {
        "device_model": man.get("device", "device"),
        "from_spec": man.get("spec"),
        "materialization": "tile/site/BEL grid (EDA standard); PARAMETRIC (type+grid, not flat); per-tile power-gating",
        "authenticity": {
            "clb_count_derived": grid.get("CLB", {}).get("count"),
            "cross_check": "CLBs*16==flip-flops AND CLBs*8==LUTs (passed)" if "CLB" in tile_types else "n/a",
        },
        "tile_types": tile_types,
        "grid": grid,
        "flags": [
            "grid layout is a REGULAR MODEL layout (functional), NOT the physical VU9P floorplan — physical coords need the device DB",
            "LUT6 BEL needs a library component (lut6) before CLB elaborates to atoms",
            *warnings,
        ],
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
