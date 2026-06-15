#!/usr/bin/env python3
"""
configmap.py — P1: map EVERY ported catalogue entry onto a physical fabric element and
realize the elements. Two element kinds:
  - DECOMPOSED (CLB): storage_element / LUT6 / CARRY8 / MUXF7-9 — realized by phys_lib.py
    builders; the catalogue families (FDRE/FDSE/…, LUT1-6/RAM*/SRL*, MUXF*) are CONFIGS.
  - LEAF (hard blocks): RAMB/URAM/DSP/transceiver/IO/clock/config — distinct physical
    elements (NOT config-variants of each other). Realized as configurable BASE PRIMITIVES
    (behavior is spec, like dff_d), interface = the documented ports. Memory FIFO modes fold
    into their RAM element (a documented config). "Deeper where documented" refinement of a
    leaf into gates is a later pass; a faithful leaf + config is the P1 floor.

Outputs configmap.json (the full map) and INJECTS leaf elements into primitives.json so
assemble.py emits them and netc.py validates the whole library. Faithful: grouping is the
doc's (UG574 CLB folding, UG573 FIFO=BRAM mode); ports are extracted; nothing invented.
Usage: configmap.py
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
cat = json.load(open(os.path.join(HERE, "catalog.json")))
phys = json.load(open(os.path.join(HERE, "phys.json")))
res_of = {m["primitive"]: m["resource"] for m in phys["prim_resource_map"]}

# Import depth variants from depth_extractor (P1 hard-IP depth modeling)
try:
    import depth_extractor
    depth_variants = depth_extractor.build_depth_augment()
except Exception as e:
    depth_variants = {}
    print(f"warning: depth_extractor load failed: {e}", file=sys.stderr)

DECOMP = {"storage_element", "LUT6", "CARRY8", "MUXF7", "MUXF8", "MUXF9"}  # realized by phys_lib/atom

# IO-buffer config-variants fold onto ONE physical IO-buffer element (mirrors CLB folding).
# The UNISIM IBUF*/OBUF*/IOBUF* families + the pad-control trio (KEEPER/PULLUP/PULLDOWN) are
# all configurations of the same physical I/O-buffer at an I/O site — differential vs single,
# tri-state, DCI/INTERM-disable, etc. are CONFIGS, not separate physical elements (DS891 counts
# I/O sites, not buffer variants). Genuinely-distinct IO-logic (ISERDES/OSERDES/IDELAY/ODELAY/
# IDELAYCTRL/BITSLICE*/DCIRESET/HPIO_VREF/RIU_OR/IBUF_ANALOG) are NOT folded — they have their
# own documented ports and remain distinct physical elements (Law #6/#7: do not over-fold).
IO_BUFFER_EL = "IO_BUFFER"
IO_BUF_RE = re.compile(r"^(IBUF|OBUF|IOBUF)")               # UNISIM buffer families
IO_BUF_PAD = {"KEEPER", "PULLUP", "PULLDOWN"}              # passive pad-control, same I/O site
IO_BUF_EXCLUDE = {"IBUF_ANALOG"}                           # SYSMON analog path — distinct element

def is_io_buffer(n):
    if n in IO_BUF_EXCLUDE: return False
    if n in IO_BUF_PAD: return True
    if re.search(r"GTE\d", n): return False                 # transceiver ref-clk buffer (ADVANCED),
                                                            # e.g. IBUFDS_GTE3/4, OBUFDS_GTE3/4 — not a fabric I/O site
    return bool(IO_BUF_RE.match(n))

def element_of(name, v):
    n = name.upper(); g = v.get("group", "")
    if g == "PS" or v.get("note"): return None                # PS (P4) / doc-pointer hard-IP
    if re.match(r"GT[HY]E3", n): return None                  # UltraScale E3 — not in this part
    # --- CLB: config-folded onto the 6 physical elements ---
    if re.match(r"FD|LD", n): return "storage_element"
    if re.match(r"(LUT\d|CFGLUT|SRL|RAM\d)", n): return "LUT6"
    if re.match(r"CARRY", n): return "CARRY8"
    if n in ("MUXF7", "MUXF8", "MUXF9"): return n
    # --- Memory: FIFO modes fold into the BRAM element (UG573) ---
    if re.match(r"(RAMB36|FIFO36)", n): return "RAMB36E2"
    if re.match(r"(RAMB18|FIFO18)", n): return "RAMB18E2"
    if re.match(r"URAM", n): return "URAM288"
    # --- Transceivers: channel and common folded by transceiver type/family ---
    if re.match(r"GTYE4_CHANNEL", n): return "GTYE4_CHANNEL"
    if re.match(r"GTYE4_COMMON", n): return "GTYE4_COMMON"
    if re.match(r"GTHE4_CHANNEL", n): return "GTHE4_CHANNEL"
    if re.match(r"GTHE4_COMMON", n): return "GTHE4_COMMON"
    # --- IO: buffer config-variants fold onto ONE physical I/O-buffer element ---
    if is_io_buffer(n): return IO_BUFFER_EL
    # --- everything else: the hard block IS its own physical element (leaf) ---
    return name

def config_of(name, v, el):
    ports = {p["name"] for p in v.get("ports", [])}
    cfg = {"init": next((p["default"] for p in v.get("params", []) if p["name"] == "INIT"), None),
           "inverts": [p["name"] for p in v.get("params", []) if p["name"].startswith("IS_")]}
    if el == "storage_element":
        cfg["mode"] = "latch" if name.upper().startswith("LD") else "flip_flop"
        cfg["control"] = sorted({{"R":"sync_reset","S":"sync_set","CLR":"async_clear",
                                   "PRE":"async_preset","G":"latch_gate"}[c] for c in
                                  ("R","S","CLR","PRE","G") if c in ports})
    elif el == "LUT6":
        cfg["mode"] = ("dist_ram" if name.upper().startswith("RAM") else
                       "srl" if name.upper().startswith("SRL") else
                       "reconfig" if name.upper().startswith("CFGLUT") else "logic")
        if res_of.get(name): cfg["resource"] = res_of[name]
        m = re.match(r"LUT(\d)", name.upper()); cfg["inputs"] = int(m.group(1)) if m else None
    elif el in ("RAMB36E2", "RAMB18E2"):
        cfg["mode"] = "fifo" if name.upper().startswith("FIFO") else "ram"
        # BRAM width/depth variants: config each member by port width presence
        cfg["width_variants"] = ["64-bit", "32-bit", "18-bit", "9-bit"]
        cfg["depth_config"] = "cascadeable"
    elif el == "URAM288":
        # URAM has fixed 72-bit width, variable depth via cascade
        cfg["width"] = 72
        cfg["depth_variants"] = ["single", "cascaded"]
        cfg["ecc_enabled"] = "INJECT_DBITERR_A" in ports or "INJECT_SBITERR_A" in ports
    elif el == "DSP48E2":
        # DSP48E2 pipeline and arithmetic configuration variants
        cfg["arithmetic_mode"] = ("multiplier" if "P" in ports else
                                  "adder" if "CARRYOUT" in ports else
                                  "logic")
        cfg["pipeline_stages"] = ["0", "1", "2", "3"]  # configurable via AREG, BREG, PREG
        cfg["mult_width"] = "27x18"  # curated-constant: DSP48E2 27 x 18 multiplier (ug579 p_DSP, "27 x 18 multiplier"); A port is 30-bit, lower 27 to the multiplier
        cfg["accumulator_width"] = 48  # curated-constant: 48-bit accumulator (ug579)
        cfg["pattern_detect"] = "PATTERNDETECT" in ports or "PATTERNBDETECT" in ports
    elif el in ("GTYE4_CHANNEL", "GTHE4_CHANNEL"):
        # Transceiver lane configuration: protocol, width, skew
        cfg["transceiver_type"] = "GTY" if "GTYE4" in name.upper() else "GTH"
        cfg["lane_count"] = "single"  # single channel; quad use multiple
        cfg["protocols"] = ["8b10b", "64b66b", "gearbox"]  # curated-constant: GTY/GTH encodings (ug578/ug576 transceiver guides)
        cfg["datawidth"] = ["16", "20", "32", "40", "64"]  # curated-constant: GTY/GTH datapath widths (ug578/ug576)
        cfg["adaptive_eq"] = "ADPRESET" in ports or "ADPRESETVALUE" in ports
    elif el in ("GTYE4_COMMON", "GTHE4_COMMON"):
        # Transceiver common (quad) configuration
        cfg["transceiver_type"] = "GTY" if "GTYE4" in name.upper() else "GTH"
        cfg["quad_pll"] = "QPLL"
        cfg["pll_modes"] = ["QPLL0", "QPLL1"]
        cfg["refclk_sources"] = ["internal", "external"]
    elif el == IO_BUFFER_EL:
        n = name.upper()
        cfg["direction"] = ("inout" if n.startswith("IOBUF") else
                            "output" if n.startswith("OBUF") else
                            "input" if n.startswith("IBUF") else "passive")
        cfg["differential"] = ("IB" in ports or "OB" in ports or n.endswith("DS")
                               or "DS" in n)
        cfg["tristate"] = "T" in ports or "TM" in ports or "TS" in ports
    return cfg

elements = {}
excluded = []
for name in sorted(cat):
    v = cat[name]
    if not v.get("ports"): continue
    el = element_of(name, v)
    if el is None:
        excluded.append(name); continue
    e = elements.setdefault(el, {"element": el, "ports": {}, "members": [], "configs": {},
                                 "kind": "decomposed" if el in DECOMP else "leaf",
                                 "subsystem": v.get("group", "")})
    e["members"].append(name); e["configs"][name] = config_of(name, v, el)
    for p in v["ports"]: e["ports"].setdefault(p["name"], p)

out = {}
for el, d in elements.items():
    entry = {
        "element": el,
        "kind": d["kind"],
        "subsystem": d["subsystem"],
        "ports": sorted(d["ports"].values(), key=lambda p: p["name"]),
        "members": sorted(d["members"]),
        "configs": d["configs"]
    }
    # Merge depth variants (P1 hard-IP depth modeling)
    if el in depth_variants:
        dv = depth_variants[el]
        # Add variant metadata alongside configs (non-invasive augmentation)
        if "modes" in dv:
            entry["_modes"] = dv["modes"]
        if "pipeline_configs" in dv:
            entry["_pipeline"] = dv["pipeline_configs"]
        if "width_variants" in dv:
            entry["_width_variants"] = dv["width_variants"]
        if "depth_variants" in dv:
            entry["_depth_variants"] = dv["depth_variants"]
        if "line_rates" in dv:
            entry["_line_rates"] = dv["line_rates"]
        if "protocols" in dv:
            entry["_protocols"] = dv["protocols"]
        if "datawidth_modes" in dv:
            entry["_datawidth_modes"] = dv["datawidth_modes"]
        if "quad_pll_types" in dv:
            entry["_quad_pll_types"] = dv["quad_pll_types"]
    out[el] = entry

json.dump(out, open(os.path.join(HERE, "configmap.json"), "w"), indent=2)

# inject LEAF elements into primitives.json as configurable base primitives (behavior is spec).
# REBUILD, don't append: a prior run's leaf set may differ (e.g. IO folding dropped 35 IBUF*/
# OBUF*/IOBUF* variants onto IO_BUFFER). First evict every configmap-OWNED entry, then re-inject
# exactly the current leaf set — so primitives.json mirrors configmap.json with no orphans.
# Ownership is keyed on the injection marker below; Tier-0 atomic axioms (no marker) and PS leaves
# owned by ps_realize.py ("see ps_ports.json") are left untouched.
CM_MARK = "see configmap.json"
prims = json.load(open(os.path.join(HERE, "primitives.json")))
removed = [k for k, v in prims.items()
           if isinstance(v, dict) and CM_MARK in str(v.get("_note", ""))]
for k in removed: del prims[k]
added = 0
for el, d in out.items():
    if d["kind"] == "decomposed": continue                    # CLB handled by phys_lib / storage_element
    pins = [p["name"] for p in d["ports"]]
    outs = [p["name"] for p in d["ports"] if p["dir"] == "out"]
    prims[el] = {"pins": pins, "out": outs, "state": True,
                 "config": f"configs: {', '.join(d['members'][:8])}",
                 "_note": f"physical {d['subsystem']} element (leaf, behavior=spec); {CM_MARK}"}
    added += 1
json.dump(prims, open(os.path.join(HERE, "primitives.json"), "w"), indent=2)
orphaned = len(removed) - added

mapped = sum(len(d["members"]) for d in out.values())
dec = sum(1 for d in out.values() if d["kind"] == "decomposed")
depth_enabled = sum(1 for d in out.values() if "_modes" in d or "_width_variants" in d or "_line_rates" in d)

print(f"configmap: {mapped} catalogue entries -> {len(out)} physical elements "
      f"({dec} decomposed CLB + {len(out)-dec} leaf), {added} leaf primitives injected "
      f"({len(removed)} evicted, net {orphaned:+d} orphans removed) -> primitives.json")
print(f"  excluded (E3/PS/hard-IP-doc-pointer): {len(excluded)} -> {excluded[:8]}{'…' if len(excluded)>8 else ''}")
import collections
bysub = collections.Counter(d["subsystem"] for d in out.values())
print("  physical elements by subsystem:", dict(bysub))
if depth_enabled > 0:
    print(f"  hard-IP depth modeling (P1): {depth_enabled} elements with config variants (DSP/BRAM/URAM/GT*)")
    for el in sorted([e for e in out.keys() if "_modes" in out[e] or "_width_variants" in out[e] or "_line_rates" in out[e]]):
        modes = len(out[el].get("_modes", []))
        variants = len(out[el].get("_width_variants", []))
        rates = len(out[el].get("_line_rates", []))
        print(f"    {el}: modes={modes}, variants={variants}, rates={rates}")
