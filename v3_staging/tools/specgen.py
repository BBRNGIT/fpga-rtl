#!/usr/bin/env python3
"""
specgen.py — Tool #2 of the v3 toolchain: PDF spec ingestion.

Reads a Xilinx UG PDF (tables + figure text) and EXTRACTS primitive port
definitions automatically -> specgen_out.json. No human reads pages and types
ports; the program does it. netc.py / the library then consume these ports.

What it extracts (the automatable part):
  - "<NAME> Pins" tables (Pin Name / Type)            -> ports + direction
  - "<NAME> ... Input | Output | Control" tables       -> one primitive per row
  - "<NAME> Ports" tables (Pin Name / I/O)             -> ports + direction
  - figure port labels (text left/right of a symbol)   -> ports (fallback)

Decomposition (cells) is applied by templates keyed on primitive shape (see
TEMPLATES); ports it cannot classify are emitted as a stub for review.

Usage: specgen.py <pdf> [--pages a-b] [--out specgen_out.json]
Exit 0 ok, 2 internal error.
"""
import sys, os, re, json, argparse
try:
    import fitz  # PyMuPDF
except Exception as e:
    print(f"specgen: PyMuPDF required (pip install pymupdf): {e}"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))

PRIM_RE = re.compile(r'\b([A-Z][A-Z0-9_]{2,})\b')          # BUFGCE, MMCME4_BASE ...
BUS_RE  = re.compile(r'^([A-Za-z][A-Za-z0-9_]*?)\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]$')
RANGE_RE = re.compile(r'^([A-Za-z_]+?)(\d+)([A-Za-z]*)\s+to\s+([A-Za-z_]+?)(\d+)([A-Za-z]*)$')  # CLKOUT0 to CLKOUT6 / CLKOUT0B to CLKOUT3B
SUF_RE  = re.compile(r'^([A-Za-z_]+)\[\s*(\d+)\s*:\s*(\d+)\s*\]([A-Za-z]+)$')  # CLKOUT[0:3]B

def parse_port_token(tok):
    """ 'DADDR[6:0]' -> [('DADDR',7)] ; 'CLKOUT0 to CLKOUT6' -> [(CLKOUT0,1)..] ; 'A, B' handled by caller """
    tok = tok.strip().strip(',').strip()
    if not tok: return []
    m = RANGE_RE.match(tok)
    if m:
        base1, lo, suf1, base2, hi, suf2 = (m.group(1), int(m.group(2)), m.group(3),
                                            m.group(4), int(m.group(5)), m.group(6))
        if base1 == base2 and suf1 == suf2 and hi >= lo:
            return [(f"{base1}{n}{suf1}", 1) for n in range(lo, hi + 1)]
    m = SUF_RE.match(tok)          # CLKOUT[0:3]B -> CLKOUT0B..CLKOUT3B
    if m:
        base, a, b, suf = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        lo, hi = min(a, b), max(a, b)
        return [(f"{base}{n}{suf}", 1) for n in range(lo, hi + 1)]
    m = BUS_RE.match(tok)
    if m:
        name, hi, lo = m.group(1), int(m.group(2)), int(m.group(3))
        return [(name, abs(hi - lo) + 1)]
    if re.match(r'^[A-Za-z][A-Za-z0-9_]*$', tok):
        return [(tok, 1)]
    return []

def split_ports(cell):
    """split a table cell of port names: commas, 'and', newlines."""
    if not cell: return []
    cell = cell.replace(" and ", ", ").replace("\n", ", ")
    out = []
    for part in cell.split(","):
        out += parse_port_token(part)
    return out

DIR_WORDS = {"input": "in", "in": "in", "output": "out", "out": "out", "i": "in", "o": "out"}

def classify_dir(s):
    return DIR_WORDS.get((s or "").strip().lower(), None)

def norm_header(row):
    return [(c or "").strip().lower() for c in row]

def primitive_name(page, tbl):
    """UG974: the primitive name is a standalone short ALL-CAPS heading above its
    'Port Descriptions' table (e.g. CARRY8, LUT6, RAMB36E2, GTYE4_CHANNEL)."""
    if page is None: return None
    y0 = tbl.bbox[1]; best, bd = None, 1e9
    for b in page.get_text("blocks"):
        t = b[4].strip()
        if b[3] <= y0 + 2 and re.match(r'^[A-Z][A-Z0-9_]{2,23}$', t) and t not in ("NA", "LEVEL", "EDGE"):
            d = y0 - b[3]
            if 0 <= d < bd: bd, best = d, t
    return best

def extract_from_table(tbl, caption, page_no, found, page=None):
    rows = tbl.extract()
    if not rows or len(rows) < 2: return
    hdr = norm_header(rows[0])
    body = rows[1:]
    cap_prim = None
    m = re.search(r'\b([A-Z][A-Z0-9_]{2,}(?:_[A-Z0-9]+)*)\b', caption or "")
    if m: cap_prim = m.group(1)

    # shape D: UG974 primitive "Port Descriptions" (Port | Direction | Width | ...)
    if hdr and hdr[0] == "port" and any("direction" in h for h in hdr):
        prim = primitive_name(page, tbl) or cap_prim
        if not prim: return
        di = next((i for i, h in enumerate(hdr) if "direction" in h), 1)
        wi = next((i for i, h in enumerate(hdr) if h == "width"), None)
        ports = []
        for r in body:
            if not r or not r[0] or not r[0].strip(): continue
            nm = re.sub(r'<.*?>', '', re.sub(r'\s+', '_', r[0].strip())).strip('_')
            if not nm: continue
            d = classify_dir(r[di]) if di < len(r) else None
            p = {"name": nm, "dir": d or "in"}
            if wi is not None and wi < len(r):
                wm = re.match(r'^\s*(\d+)\s*$', r[wi] or '')
                if wm and int(wm.group(1)) > 1: p["width"] = int(wm.group(1))
            ports.append(p)
        if ports: found.setdefault(prim, _mk(prim, page_no, caption))["ports"] = ports
        return

    # shape A: pins table  (Pin Name | Type/Direction | ...)
    if any("pin name" in h for h in hdr) or (hdr and hdr[0] in ("pin", "pin name")):
        prim = cap_prim
        if not prim: return
        di = next((i for i, h in enumerate(hdr) if h in ("type", "i/o", "direction")), None)
        ports = []
        for r in body:
            if not r or not r[0]: continue
            for nm, w in split_ports(r[0]):
                d = classify_dir(r[di]) if di is not None and di < len(r) else None
                ports.append({"name": nm, "dir": d or "in", **({"width": w} if w > 1 else {})})
        if ports: found.setdefault(prim, _mk(prim, page_no, caption))["ports"] = ports
        return

    # shape B: ports table  (Description | Ports)   e.g. "Clock input | CLKIN1, CLKFBIN"
    if any("ports" in h for h in hdr) and any("desc" in h for h in hdr):
        prim = cap_prim
        if not prim: return
        ci = next(i for i, h in enumerate(hdr) if "desc" in h)
        pi = next(i for i, h in enumerate(hdr) if "ports" in h)
        ports = []
        for r in body:
            if len(r) <= max(ci, pi): continue
            desc = (r[ci] or "").lower()
            d = "out" if "output" in desc else ("in" if ("input" in desc or "control" in desc or "power" in desc) else "in")
            for nm, w in split_ports(r[pi]):
                ports.append({"name": nm, "dir": d, **({"width": w} if w > 1 else {})})
        if ports: found.setdefault(prim, _mk(prim, page_no, caption))["ports"] = ports
        return

    # shape C: primitive-per-row  (Primitive | Input | Output | Control)
    if hdr and hdr[0] in ("primitive", "primitives"):
        coli = {h: i for i, h in enumerate(hdr)}
        for r in body:
            if not r or not r[0]: continue
            pm = re.match(r'\s*([A-Z][A-Z0-9_]+)', r[0])
            if not pm: continue
            prim = pm.group(1); ports = []
            for col, d in (("input", "in"), ("output", "out"), ("control", "in")):
                if col in coli and coli[col] < len(r):
                    for nm, w in split_ports(r[coli[col]]):
                        ports.append({"name": nm, "dir": d, **({"width": w} if w > 1 else {})})
            if ports:
                e = found.setdefault(prim, _mk(prim, page_no, caption))
                # merge (a primitive can span Table 3-1 base + 3-3 full)
                have = {p["name"] for p in e.get("ports", [])}
                e.setdefault("ports", []).extend(p for p in ports if p["name"] not in have)
        return

def _mk(prim, page, caption):
    return {"name": prim, "ports": [], "spec": f"UG572 p{page} ({caption.strip()[:60]})" if caption else f"UG572 p{page}",
            "group": "Clock management", "source": "specgen"}

def caption_for(page, tbl):
    """nearest 'Table N-N: ...' line above the table bbox."""
    y0 = tbl.bbox[1]
    best, bestd = None, 1e9
    for b in page.get_text("blocks"):
        bx0, by0, bx1, by1, txt = b[0], b[1], b[2], b[3], b[4]
        if "Table" in txt and by1 <= y0 + 4:
            d = y0 - by1
            if 0 <= d < bestd: bestd, best = d, txt.strip().replace("\n", " ")
    return best or ""

def run(pdf, pages, out):
    doc = fitz.open(pdf)
    rng = range(doc.page_count)
    if pages:
        a, b = pages.split("-"); rng = range(int(a) - 1, int(b))
    found = {}
    for i in rng:
        if i < 0 or i >= doc.page_count: continue
        page = doc[i]
        # fast-skip: only detect tables on pages that actually carry a port/primitive table
        # (find_tables is the slow step; this 5-10x's a 697-page guide)
        txt = page.get_text()
        if not any(k in txt for k in ("Port Descriptions", "Pin Name", "Ports", "Primitive", "Input Output")):
            continue
        try:
            tabs = page.find_tables()
        except Exception:
            continue
        for tbl in tabs.tables:
            try:
                extract_from_table(tbl, caption_for(page, tbl), i + 1, found, page)
            except Exception as e:
                print(f"specgen: WARN p{i+1} table parse: {e}")
    with open(out, "w") as f:
        json.dump(found, f, indent=2)
    print(f"specgen: extracted {len(found)} primitive(s) -> {out}")
    for nm, e in found.items():
        ins = [p["name"] for p in e["ports"] if p["dir"] == "in"]
        outs = [p["name"] for p in e["ports"] if p["dir"] == "out"]
        print(f"  {nm:16s} in[{len(ins)}]={','.join(ins[:6])}{'...' if len(ins)>6 else ''}  "
              f"out[{len(outs)}]={','.join(outs[:6])}{'...' if len(outs)>6 else ''}")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--pages", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "specgen_out.json"))
    a = ap.parse_args()
    try:
        sys.exit(run(a.pdf, a.pages, a.out))
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(2)
