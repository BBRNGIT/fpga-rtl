#!/usr/bin/env python3
"""
psports.py — harvest the Processing System (PS) interface from UG1085 (Zynq US+ TRM).

The PS is a hardened subsystem documented in a register-reference TRM, NOT a libraries
guide — its instantiable surface is the set of INTERFACE signals (the PS-PL seam: AXI
HP/HPC/ACP/ACE + M_AXI, EMIO, PS clocks/resets, PS-to-PL / PL-to-PS interrupts) plus the
per-controller signal/pin tables (DDR, GEM, USB, SATA, DisplayPort, PS-GTR, MIO). Those
appear as [Signal Name | I/O | Description] / [Pin Name | Direction | Description] tables,
grouped by the doc's own CHAPTERS. This tool reads the cached tables, attributes each to
its chapter (the doc's grouping — not ours), and emits ps_ports.json.

Faithful transcription: the grouping is the TRM's chapter, the direction is the doc's I/O
column. We invent nothing; behavioral controllers (ARM cores, GPU, VCU) that the TRM does
not give a signal table are simply not emitted (they are not a PL-facing interface).

Usage: psports.py   (reads cache/ug1085-*.jsonl)
"""
import sys, os, re, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(HERE, "cache")

CHAP = re.compile(r'Chapter\s+\d+:\s*([A-Z][^\n]{3,48})')
NAMECOL = ("signal name", "port", "pin name", "port name", "signal")
DIRCOL = ("i/o", "direction", "dir", "type")

def block_name(chapter):
    c = re.sub(r'[^A-Za-z0-9]+', '_', chapter.strip()).strip('_').upper()
    return "PS_" + c[:32]

def cols(rows):
    if not rows: return None
    h = [(c or "").strip().lower() for c in rows[0]]
    ni = next((i for i, x in enumerate(h) if x in NAMECOL), None)
    di = next((i for i, x in enumerate(h) if x in DIRCOL), None)
    if ni is None or di is None: return None
    return ni, di

def parse(rows, c):
    ni, di = c; out = []
    for r in rows[1:]:
        if len(r) <= max(ni, di): continue
        d = (r[di] or "").strip().lower()
        dr = "inout" if ("inout" in d or "input/output" in d or "i/o" in d or "bidir" in d) else \
             ("out" if d.startswith("out") else "in" if d.startswith("in") else None)
        if dr is None: continue                              # not a real signal row (e.g. a note)
        # UG1085 PDF renders underscores in names as spaces with stray '_' continuation
        # lines: PS_REF_CLK -> "PS REF CLK\n_ _". Reconstruct: drop underscore-only lines,
        # turn spaces back into underscores. Letter-bearing lines = distinct stacked signals.
        for raw in (r[ni] or "").split("\n"):
            raw = raw.strip()
            if not raw or re.match(r'^[_\s]+$', raw): continue
            mb = re.match(r'^([A-Za-z][\w ]*?)\s*(?:\[(\d+):(\d+)\])?\s*$', raw)
            if not mb: continue
            nm = re.sub(r'\s+', '_', mb.group(1).strip())
            if len(nm) < 3: continue
            e = {"name": nm, "dir": dr}
            if mb.group(2) is not None:
                e["width"] = abs(int(mb.group(2)) - int(mb.group(3))) + 1
            out.append(e)
    return out

def run():
    g = glob.glob(os.path.join(CACHE, "ug1085-*.jsonl"))
    if not g:
        print("psports: no UG1085 cache — run extract.py on ug1085 first"); return 2
    recs = [json.loads(l) for l in open(g[0])]
    chapter = "Unknown"; blocks = {}
    for r in recs:
        m = CHAP.search(r["text"])
        if m: chapter = m.group(1).strip()
        for tb in r.get("tables", []):
            c = cols(tb["rows"])
            if not c: continue
            ports = parse(tb["rows"], c)
            if not ports: continue
            bn = block_name(chapter)
            b = blocks.setdefault(bn, {})
            for p in ports:
                if p["name"] not in b or p.get("width", 1) > b[p["name"]].get("width", 1):
                    b[p["name"]] = p
    # PS-PL AXI seam: documented as named interface ports (each a full AMBA AXI4 bus).
    # We name them faithfully from the TRM; the per-interface AXI4 signal expansion is the
    # AMBA standard, detailed at wiring time (not invented here).
    axi = {}
    AXI = re.compile(r'\b([SM]_AXI_(?:HP[C]?\d|HP|LPD|ACE_FPD|ACP_FPD|HPM\d)(?:_[FL]PD)?)\b')
    for r in recs:
        for nm in AXI.findall(r["text"]):
            if nm in ("S_AXI_HP", "S_AXI_HPC"): continue       # truncated mentions
            axi[nm] = {"name": nm, "dir": "slave" if nm.startswith("S_") else "master",
                       "kind": "axi4_interface"}
    if axi: blocks["PS_PL_AXI_INTERFACES"] = axi

    out = {k: sorted(v.values(), key=lambda p: p["name"]) for k, v in blocks.items() if len(v) >= 2}
    json.dump(out, open(os.path.join(HERE, "ps_ports.json"), "w"), indent=2)
    tot = sum(len(v) for v in out.values())
    print(f"psports: {len(out)} PS blocks, {tot} interface signals -> ps_ports.json")
    for k in sorted(out, key=lambda k: -len(out[k])):
        print(f"   {k:34s} {len(out[k])} signals")
    return 0

if __name__ == "__main__":
    sys.exit(run())
