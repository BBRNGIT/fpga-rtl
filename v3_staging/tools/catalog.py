#!/usr/bin/env python3
"""
catalog.py — parse the COMPLETE cache (all docs, all pages) into one parts catalogue.

Drives entirely off cache/*.jsonl (produced by extract.py). For every primitive section
(a page whose heading is followed by "Primitive:" / "PRIMITIVE_GROUP" / "Macro:") it
collects, from that section's pages:
  - ports  : from the cached structured 'Port Descriptions' table (uniform — works for
             CLB, memory, DSP, I/O, transceivers; no newline/regex hacks)
  - params : from the Verilog template's #(...) block
  - template: the raw Verilog instantiation template (the base for our C instruction lang)
  - note   : stub primitives that point elsewhere (e.g. GTYE4 -> UG578) are flagged, not faked.

Output catalog.json — the complete parts list across every provided doc.
Usage: catalog.py [--cachedir cache] [--out catalog.json]
"""
import sys, os, re, json, glob, argparse
HERE = os.path.dirname(os.path.abspath(__file__))

SECT = re.compile(r'^([A-Z][A-Z0-9_]{2,30})\s*\n\s*(?:Primitive:|PRIMITIVE_GROUP|Macro:|Xilinx Parameterized)')
PAIR = re.compile(r'\.(\w+)\s*\(\s*([^()]*?)\s*\)')

def is_portdesc(rows):
    if not rows: return None
    hdr = [(c or "").strip().lower() for c in rows[0]]
    if "port" in hdr and any("direction" in h for h in hdr):
        return (hdr.index("port") if "port" in hdr else 0,
                next(i for i, h in enumerate(hdr) if "direction" in h),
                next((i for i, h in enumerate(hdr) if h == "width"), None))
    return None

def parse_ports(rows, cols):
    pc, dc, wc = cols; out = []
    for r in rows[1:]:
        if len(r) <= max(pc, dc): continue
        nm = re.sub(r'[<\[].*?[>\]]', '', re.sub(r'\s+', '_', (r[pc] or '').strip())).strip('_')
        if not nm or not re.match(r'^[A-Za-z]', nm): continue
        d = (r[dc] or '').strip().lower()
        e = {"name": nm, "dir": "out" if d.startswith("out") else ("inout" if "inout" in d else "in")}
        if wc is not None and wc < len(r):
            wm = re.match(r'^\s*(\d+)', r[wc] or '')
            if wm and int(wm.group(1)) > 1: e["width"] = int(wm.group(1))
        out.append(e)
    return out

VPORT = re.compile(r'\.(\w+)\s*\(([^)]*)\)\s*,?\s*(//[^\n]*)?')   # .PORT(net),  // <dir> comment
def verilog_ports(vtext):
    """Port names + directions from the instantiation template's port-map. Direction is
    read from the doc's own inline comment ('// 1-bit output: ...'). The port-map is the
    block after the `<PRIM>_inst (` token — anchored there so a page-footer or stray VHDL
    mention can't truncate it. Factual extraction, not inference."""
    a = re.search(r'\w+_inst\s*\(', vtext)
    rest = vtext[a.end():] if a else vtext
    out, seen = [], set()
    for nm, net, cmt in VPORT.findall(rest):
        if nm in seen or nm != net.strip(): continue          # .PORT(PORT) — a real port wire, not a param assign
        seen.add(nm)
        c = (cmt or "").lower()
        dr = "out" if "output" in c else ("inout" if "inout" in c else "in")
        e = {"name": nm, "dir": dr}
        wm = re.search(r'\[(\d+):0\]', net)
        if wm: e["width"] = int(wm.group(1)) + 1
        out.append(e)
    return out

def verilog_params(vtext):
    i = vtext.find("#(")
    if i < 0: return []
    depth = 0
    for k in range(i + 1, len(vtext)):
        if vtext[k] == '(': depth += 1
        elif vtext[k] == ')':
            depth -= 1
            if depth == 0: return PAIR.findall(vtext[i + 2:k])
    return PAIR.findall(vtext[i + 2:])

def run(cachedir, out):
    cat = {}
    for cf in sorted(glob.glob(os.path.join(cachedir, "*.jsonl"))):
        doc = os.path.basename(cf).split(".")[0]
        cur = None
        recs = [json.loads(line) for line in open(cf)]
        for ri, rec in enumerate(recs):
            m = SECT.match(rec["text"])
            if m:                                            # new primitive section starts
                cur = m.group(1)
                cat.setdefault(cur, {"name": cur, "ports": [], "params": [], "template": "",
                                     "source": f"{doc} p{rec['page']}", "group": None})
                cat[cur]["_pg"] = rec["page"]
                g = re.search(r'PRIMITIVE_GROUP:\s*(\w+)', rec["text"])
                if g: cat[cur]["group"] = g.group(1)
            if cur is None: continue
            for tb in rec.get("tables", []):
                cols = is_portdesc(tb["rows"])
                if cols:
                    ports = parse_ports(tb["rows"], cols)
                    have = {p["name"] for p in cat[cur]["ports"]}
                    cat[cur]["ports"] += [p for p in ports if p["name"] not in have]
            if "Verilog Instantiation Template" in rec["text"] and not cat[cur]["template"]:
                # join across pages — long/short templates can straddle a page break
                acc = rec["text"]
                for k in range(ri + 1, min(len(recs), ri + 4)):
                    if SECT.match(recs[k]["text"]): break      # stop at the next primitive
                    acc += "\n" + recs[k]["text"]
                vt = acc[acc.find("Verilog Instantiation Template") + 30:].strip()
                cat[cur]["template"] = vt[:4000]
                cat[cur]["params"] = [{"name": n, "default": v} for n, v in verilog_params(vt)]
                if not cat[cur]["ports"]:                      # fallback: small CLB prims (LUT/RAM/KEEPER)
                    cat[cur]["ports"] = verilog_ports(vt)      # have no Port-Descriptions table
                    if cat[cur]["ports"]: cat[cur]["port_src"] = "verilog template"
        # for primitives with no ports here, record the dedicated guide they point to
        for nm, v in cat.items():
            if v["ports"] or v.get("note") or not v["source"].startswith(doc): continue
            pg = v.get("_pg")
            if pg is None: continue
            txt = "".join(recs[p]["text"] for p in range(pg - 1, min(len(recs), pg + 1)))
            refs = [r for r in re.findall(r'(?:UG|PG)\d{3}', txt) if r != "UG974"]
            # the port spec lives in the architecture UG (e.g. UG576/UG578); a PG is the
            # configuration wizard. Prefer a UG pointer when the page cites one.
            refs.sort(key=lambda r: (0 if r.startswith("UG") else 1))
            if refs: v["note"] = f"hard-IP block — ports specified in {refs[0]} (not in UG974)"
    for v in cat.values(): v.pop("_pg", None)
    # merge transceiver ports harvested from UG576/UG578 (txports.py) into their stubs
    txf = os.path.join(os.path.dirname(out), "tx_ports.json")
    merged = 0
    if os.path.exists(txf):
        tx = json.load(open(txf))
        guide = {"GTH": "UG576", "GTY": "UG578"}
        for nm, ports in tx.items():
            if nm in cat and not cat[nm]["ports"] and ports:
                cat[nm]["ports"] = ports
                cat[nm]["port_src"] = guide.get(nm[:3], "transceiver UG") + " port-description chapter"
                cat[nm].pop("note", None)
                merged += 1
        json.dump(cat, open(out, "w"), indent=2)
    else:
        json.dump(cat, open(out, "w"), indent=2)
    if merged: print(f"  merged transceiver ports into {merged} primitives from tx_ports.json")
    full = {k: v for k, v in cat.items() if v["ports"]}
    stubs = {k: v for k, v in cat.items() if not v["ports"]}
    print(f"catalog: {len(cat)} primitives across all docs -> {out}")
    print(f"  with ports (catalogued): {len(full)}   |  stub/elsewhere: {len(stubs)}")
    miss = [k for k, v in stubs.items() if v.get("note")]
    print(f"  point to another doc: {[(k, stubs[k]['note']) for k in miss][:10]}")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cachedir", default=os.path.join(HERE, "cache"))
    ap.add_argument("--out", default=os.path.join(HERE, "catalog.json"))
    a = ap.parse_args()
    sys.exit(run(a.cachedir, a.out))
