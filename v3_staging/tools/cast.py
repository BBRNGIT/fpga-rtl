#!/usr/bin/env python3
"""
cast.py — P2 Container Casting. Cast THE one blank container: every physical element
(configmap.json) arrayed at its AUTHENTIC DS891 count on a synthesized grid. Grid coordinate
(X,Y) IS identity — no registry, no allocation. Code is O(tile TYPES); the 8.1M lives in the
count fields / static-array dimensions (scale architecture). A blank assigns nothing.

Output container.json: {elements:[{name,kind,count,per_slice,ports}], grid:{...}, totals:{...}}.
The downstream realizer arrays each tile TYPE to its count; this manifest is the cast blank.
Usage: cast.py
"""
import json, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
cm = json.load(open(os.path.join(HERE, "configmap.json")))
ds = json.load(open(os.path.join(HERE, "ds_resources.json")))
inv = next(iter(ds.values()), {})
def num(k):
    try: return int(str(inv.get(k, "")).replace(",", "").split(".")[0])
    except Exception: return None

FF = num("CLB Flip-Flops"); LUT = num("CLB LUTs"); BRAM = num("Block RAM Blocks")
URAM = num("UltraRAM Blocks"); DSP = num("DSP Slices"); CMT = num("CMTs")
GTH = num("GTH Transceiver 16.3Gb/s(3)"); GTY = num("GTY Transceivers 32.75Gb/s")
HPIO = num("Max. HP I/O(1)"); HDIO = num("Max. HD I/O(2)"); IOB = (HPIO or 0) + (HDIO or 0)
SLICES = LUT // 8 if LUT else None                              # 8 LUT6 / slice (UG574)

# I/O elements split by GRANULARITY: per-SITE logic is one-per-I/O (count = IOB, the DS891
# HP+HD I/O scalar) — IO_BUFFER, ISERDES/OSERDES, IDELAY/ODELAY, the RX/TX bitslices. The
# per-BANK/per-nibble control elements are NOT a DS891 site scalar (their count is bank/nibble
# count, which DS891 does not give and UG571 would) — so they stay UNCOUNTED rather than be
# over-counted at 668 or invented (Law #7). They join the count-by-bank bucket pending UG571.
PER_BANK_IO = {"BITSLICE_CONTROL", "IDELAYCTRL", "HPIO_VREF", "RIU_OR", "DCIRESET"}

# element -> authentic count (DS891-derived; per-slice ratios from UG574)
def count_of(name, d):
    sub = d.get("subsystem", "")
    if name in PER_BANK_IO: return None                         # per-bank/nibble — needs UG571, not 668
    return {
        "storage_element": FF, "LUT6": LUT, "CARRY8": SLICES,
        "MUXF7": (LUT // 2 if LUT else None), "MUXF8": (LUT // 4 if LUT else None),
        "MUXF9": (LUT // 8 if LUT else None),
        "RAMB36E2": BRAM, "RAMB18E2": (BRAM * 2 if BRAM else None), "URAM288": URAM,
        "DSP48E2": DSP,
    }.get(name) or {                                            # else by subsystem family
        "BLOCKRAM": BRAM, "ARITHMETIC": DSP, "CLOCK": CMT,
        "ADVANCED": (GTH if "GTH" in name.upper() else GTY if "GTY" in name.upper() else None),
        "I": IOB,                                               # per-SITE I/O logic = one per I/O
    }.get(sub)

elements = []
for el, d in cm.items():
    if el in ("MUXF7", "MUXF8", "MUXF9") and not d.get("ports"): continue
    elements.append({"name": el, "kind": d["kind"], "subsystem": d.get("subsystem", ""),
                     "count": count_of(el, d), "ports": len(d.get("ports", [])),
                     "configs": len(d.get("configs", {}))})
elements.sort(key=lambda e: -(e["count"] or 0))

# synthesized floorplan grid (the docs don't give exact PIP-level placement -> we synthesize,
# faithful to the column/clock-region structure: CLB/BRAM/DSP columns over a slice grid).
clk_regions = CMT * 12 if CMT else None                        # ~clock-region order of magnitude
rows = int(math.sqrt(SLICES)) if SLICES else None
cols = (SLICES // rows + 1) if rows else None
grid = {"slices": SLICES, "rows": rows, "cols": cols, "clock_regions_est": clk_regions,
        "note": "synthesized column/region floorplan; (X,Y) is identity, no allocation"}

# M1 — SIZING. total_placed_instances is the SUM of per-element DS891 scalars (FF + LUT +
# MUXF7/8/9 + CARRY8 + BRAM + DSP + per-IO-site leaves). It is NOT the same number as either:
#   - system_logic_cells_DS891 ("System Logic Cells", ~1.14M — Xilinx's marketing cell-equiv), or
#   - the founder's ~8.1M "full authentic" sizing target (see V3_REALIZATION_ROADMAP.md §P2
#     "Open decision" + Decisions #2: full authentic counts are the target; current blank is the
#     proven floor). The three figures measure different things; do not conflate them. The blank
#     is correct at whatever DS891-derived scalar each element carries — closing to 8.1M is a
#     roadmap sizing decision (array-dimension scaling), NOT a bug in this caster.
placed = sum(e["count"] for e in elements if e["count"])
totals = {"physical_element_types": len(elements),
          "total_placed_instances": placed,                 # sum of per-element DS891 scalars (M1)
          "system_logic_cells_DS891": num("System Logic Cells"),  # ~1.14M marketing cell-equiv (≠ above)
          "authentic_sizing_target_note": "founder target ~8.1M full-authentic; see roadmap §P2 (M1)",
          "uncounted_element_types": sum(1 for e in elements if not e["count"])}
json.dump({"part": list(ds.keys())[0] if ds else "?", "elements": elements,
           "grid": grid, "totals": totals}, open(os.path.join(os.path.dirname(HERE), "device", "container.json"), "w"), indent=2)

print(f"cast: blank container — {len(elements)} physical element types, "
      f"{placed:,} instances placed on synthesized grid -> container.json")
print(f"  grid: {SLICES:,} slices ≈ {rows}×{cols}, ~{clk_regions} clock regions")
for e in elements[:12]:
    c = f"{e['count']:,}" if e["count"] else "—(bank/region)"
    print(f"   {e['name']:18s} [{e['subsystem']:>9s}] ×{c:>11s}  {e['ports']}p · {e['configs']} configs")
nc = [e["name"] for e in elements if not e["count"]]
if nc: print(f"  count-by-bank/region (not a DS891 scalar): {len(nc)} types e.g. {nc[:6]}")
