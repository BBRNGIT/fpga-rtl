#!/usr/bin/env python3
"""
txports.py — harvest transceiver primitive ports from the GTH/GTY architecture UGs.

UG576 (GTH) / UG578 (GTY) do NOT lay ports out per-primitive the way UG974 does — the
ports are grouped by FUNCTION (CPLL/QPLL/TX/RX/reset/clocking) across the chapter, each
group under a section heading that names its owner ("GTYE3/4_CHANNEL Clocking Ports",
"GTYE3/4_COMMON Clocking Ports") or implies it by the documented PLL convention
(CPLL = Channel PLL -> CHANNEL ; QPLL = Quad/common PLL -> COMMON). This tool reads the
cached [Port, Dir, Clock Domain, Description] tables, attributes each to CHANNEL or
COMMON by the doc's own section headers, and emits tx_ports.json. catalog.py merges it
into the stub transceiver entries. Faithful extraction — owner comes from the doc, not us.

Each guide covers both the UltraScale (E3) and UltraScale+ (E4) family, so both variants
receive the same port set (the guide title is "GTYE3/4" / "GTHE3/4").

Usage: txports.py   (reads cache/ug576-*.jsonl + cache/ug578-*.jsonl)
"""
import sys, os, re, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(HERE, "cache")

# section-header markers -> owner. The doc states ownership; CPLL/QPLL is documented fact.
COMMON = re.compile(r'(GT[YH]E3/4_COMMON[^\n]*Ports)|(QPLL[0-9/]*\s+Ports)|(Common\s+Clocking\s+Ports)', re.I)
CHANNEL = re.compile(r'(GT[YH]E3/4_CHANNEL[^\n]*Ports)|(CPLL[^\n]*Ports?)|(Channel\s+Clocking\s+Ports)', re.I)

def is_portdesc(rows):
    if not rows: return None
    h = [(c or "").strip().lower() for c in rows[0]]
    if "port" not in h: return None
    di = next((i for i, x in enumerate(h) if x in ("dir", "direction")), None)
    if di is None: return None
    return h.index("port"), di

def parse(rows, cols):
    pc, dc = cols; out = []
    for r in rows[1:]:
        if len(r) <= max(pc, dc): continue
        cell = (r[pc] or "").strip()
        d = (r[dc] or "").strip().lower()
        dr = "out" if d.startswith("out") else ("inout" if ("inout" in d or "in/out" in d) else "in")
        # one cell can stack several related ports — separated by newline, comma, or slash
        for raw in re.split(r'[\n,/]', cell):
            raw = raw.strip().rstrip("_").strip()
            mb = re.match(r'^([A-Z][A-Z0-9_]{2,})\s*(?:\[(\d+):0\])?$', raw)  # >=3 chars (kills I/O/CEB stragglers)
            if not mb: continue
            e = {"name": mb.group(1), "dir": dr}
            if mb.group(2): e["width"] = int(mb.group(2)) + 1
            out.append(e)
    return out

def harvest(cache, fam):
    recs = [json.loads(l) for l in open(cache)]
    owner = "CHANNEL"                                        # most ports are per-channel
    started = False                                          # gate: skip Ch.1/2 buffer prims (IBUFDS_GTE..)
    buckets = {"CHANNEL": {}, "COMMON": {}}                  # name -> port (dedup, keep widest)
    for rec in recs:
        t = rec["text"]
        c, m = CHANNEL.search(t), COMMON.search(t)
        if c and m: owner = "COMMON" if m.start() > c.start() else "CHANNEL"  # last heading wins
        elif m: owner = "COMMON"
        elif c: owner = "CHANNEL"
        if c or m: started = True                            # the per-primitive port chapter has begun
        if not started: continue
        for tb in rec.get("tables", []):
            cols = is_portdesc(tb["rows"])
            if not cols: continue
            for p in parse(tb["rows"], cols):
                # documented PLL convention overrides page attribution per-port:
                # CPLL = Channel PLL -> CHANNEL ; QPLL = Quad/common PLL -> COMMON
                who = "COMMON" if p["name"].startswith("QPLL") else \
                      "CHANNEL" if p["name"].startswith("CPLL") else owner
                b = buckets[who]
                if p["name"] not in b or p.get("width", 1) > b[p["name"]].get("width", 1):
                    b[p["name"]] = p
    return {f"{fam}_{k}": sorted(v.values(), key=lambda p: p["name"]) for k, v in buckets.items()}

def run():
    out = {}
    for fam, pat in [("GTH", "ug576-*.jsonl"), ("GTY", "ug578-*.jsonl")]:
        g = glob.glob(os.path.join(CACHE, pat))
        if not g:
            print(f"txports: no cache for {fam} ({pat}) — run extract.py on its UG first"); continue
        h = harvest(g[0], fam)
        for k, ports in h.items():
            for e3e4 in ("3", "4"):                          # the guide covers both families
                out[k.replace("E", f"E{e3e4}", 1) if False else k.replace(fam, f"{fam}E{e3e4}")] = ports
        print(f"txports: {fam} -> CHANNEL {len(h[fam+'_CHANNEL'])} ports, COMMON {len(h[fam+'_COMMON'])} ports")
    json.dump(out, open(os.path.join(HERE, "tx_ports.json"), "w"), indent=2)
    print(f"txports: wrote tx_ports.json — {sorted(out)}")
    return 0

if __name__ == "__main__":
    sys.exit(run())
