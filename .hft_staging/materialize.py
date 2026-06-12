#!/usr/bin/env python3
"""materialize.py — build the PARAMETRIC device model from authentic inputs.

GENERIC: this tool hardcodes NOTHING about any device or part. It discovers the
composition specs (composition/*.tile.yaml) and, for each, applies the spec's OWN
declared count-rule + cross-checks against the parts manifest. Add a part to the
model by adding an authentic composition spec — never by editing this tool.

Materialization rule (founder-adopted, EDA-standard): the blank is a
Device -> Tile(_X#Y#) -> Site -> BEL grid, full BEL fidelity, grid-addressed, with
per-tile power-gating. PARAMETRIC by necessity (type+grid+counts, not flat per-BEL;
live state allocates per used BEL at placement).

Each composition spec declares:
  tile_type, source, sites:[{site_type, per_tile, bels:[{bel,count,library,...}]}]
  count_rule:   {from: <manifest resource substr>, scale: <int=1>, per_bel: <bel name>}
  cross_checks: [{from: <manifest resource substr>, scale: <int=1>, per_bel: <bel name>}]
The tool resolves <from> against the manifest, computes count = scaled/ (#per_bel),
and asserts each cross_check (scaled == count * #per_bel). A mismatch is a HARD
error (authenticity/poison) — never silently reconciled.

Flags (honest, not invented): grid layout is a REGULAR MODEL layout (functional),
NOT the physical floorplan (that needs the device DB).

Usage: python3 materialize.py <parts.json> > device_model.json
"""
import glob
import json
import os
import re
import sys

try:
    import yaml
except Exception:
    sys.stderr.write("materialize: PyYAML required\n"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
COMP_DIR = os.path.join(HERE, "composition")


def die(m):
    sys.stderr.write("materialize: " + m + "\n"); sys.exit(2)


def as_int(v):
    s = str(v).replace(",", "")
    return int(s) if re.fullmatch(r"\d+", s) else None


def resolve(parts, substr, scale):
    """Return the scaled integer value of the manifest resource matching substr."""
    hits = [p for p in parts if substr.lower() in p["resource"].lower()]
    if not hits:
        die(f"manifest has no resource matching '{substr}'")
    n = as_int(hits[0]["value"])
    if n is None:
        die(f"manifest resource '{substr}' value '{hits[0]['value']}' is not an integer count")
    return n * int(scale)


def bel_count(spec, bel_name):
    for s in spec.get("sites", []):
        per = int(s.get("per_tile", 1))
        for b in s.get("bels", []):
            if b.get("bel") == bel_name:
                return per * int(b["count"])
    die(f"composition '{spec.get('tile_type')}' declares no bel named '{bel_name}'")


def main():
    if len(sys.argv) != 2:
        die("usage: materialize.py <parts.json> > device_model.json")
    man = json.load(open(sys.argv[1]))
    parts = man["parts"]

    tile_types, grid = {}, {}
    specs = sorted(glob.glob(os.path.join(COMP_DIR, "*.tile.yaml")))
    if not specs:
        die("no composition specs in composition/ — add authentic *.tile.yaml first")

    for path in specs:
        spec = yaml.safe_load(open(path))
        tt = spec["tile_type"]
        cr = spec.get("count_rule")
        if not cr:
            die(f"{os.path.basename(path)}: missing count_rule (the spec must declare "
                f"how its count derives from the manifest — the tool hardcodes nothing)")
        scaled = resolve(parts, cr["from"], cr.get("scale", 1))
        per = bel_count(spec, cr["per_bel"])
        if per <= 0 or scaled % per != 0:
            die(f"{tt}: count_rule {scaled}/{per} is not a whole number — composition/manifest mismatch")
        count = scaled // per
        for cc in spec.get("cross_checks", []):
            cval = resolve(parts, cc["from"], cc.get("scale", 1))
            expect = count * bel_count(spec, cc["per_bel"])
            if cval != expect:
                die(f"{tt}: cross-check FAILED — manifest '{cc['from']}'={cval} != "
                    f"count*{cc['per_bel']}={expect} (authenticity mismatch)")
        bels_per = sum(int(s.get("per_tile", 1)) * sum(int(b["count"]) for b in s.get("bels", []))
                       for s in spec.get("sites", []))
        tile_types[tt] = {"source": spec.get("source", ""), "sites": spec["sites"],
                          "bels_per_tile": bels_per}
        grid[tt] = {"count": count, "layout": "regular_model",
                    "addressing": "_X#Y# per Xilinx scheme",
                    "power": "per-tile enable (unused tiles off)"}

    out = {
        "device_model": man.get("device", "device"),
        "from_spec": man.get("spec"),
        "materialization": "tile/site/BEL grid (EDA standard); PARAMETRIC; per-tile power-gating; GENERIC tool (no device hardcoded)",
        "tile_types": tile_types,
        "grid": grid,
        "flags": [
            "grid layout is a REGULAR MODEL layout (functional), NOT the physical floorplan — physical coords need the device DB",
            "only part types with an authentic composition spec are modeled; add more via composition/*.tile.yaml (never by editing this tool)",
        ],
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
