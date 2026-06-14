#!/usr/bin/env python3
"""
extract.py — Phase-1 RAW extractor. Reads a PDF ONCE, page by page, and caches each
page's raw data so parsers never re-pay the slow PDF read. Separates extraction from
parsing (the smart split): extract once -> cache -> parse many times, re-runnable.

Per page it caches: text, the Verilog Instantiation Template region (exact ports +
params), short ALL-CAPS headings (with y, for the primitive name), and the vector
wires/bubbles (for figparse). Cache: cache/<pdf-stem>.jsonl (one JSON object per page).

Usage: extract.py <pdf> [--pages a-b]
"""
import sys, os, re, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
try:
    import fitz
except Exception as e:
    print(f"extract: PyMuPDF required: {e}"); sys.exit(2)
import eda_shapes as eda

CACHE = os.path.join(HERE, "cache")

def verilog_region(text):
    i = text.find("Verilog Instantiation Template")
    if i < 0: return ""
    seg = text[i + 30:]
    j = seg.find("VHDL Instantiation")                      # cut at the VHDL template if present
    if j > 0: seg = seg[:j]
    return seg.strip()[:6000]                               # big primitives (RAMB/DSP/GTY) have long templates

def page_record(page, i):
    text = page.get_text()
    heads = []
    for b in page.get_text("blocks"):
        t = b[4].strip()
        if re.match(r'^[A-Z][A-Z0-9_]{2,30}$', t): heads.append([t, round(b[1], 1)])
    wires, diags, rects, bubbles = eda.collect(page.get_drawings())
    tables = []                                             # structured tables (ports/pinouts/counts)
    try:
        for t in page.find_tables().tables:
            rows = t.extract()
            if rows: tables.append({"bbox": [round(x, 1) for x in t.bbox], "rows": rows})
    except Exception:
        pass
    return {"page": i + 1, "text": text, "verilog": verilog_region(text),
            "heads": heads, "tables": tables, "wires": wires, "bubbles": bubbles}

def run(pdf, pages, force=False):
    os.makedirs(CACHE, exist_ok=True)
    stem = os.path.splitext(os.path.basename(pdf))[0]
    out = os.path.join(CACHE, stem + ".jsonl")
    # idempotent: the cache is the committed artifact; extraction is one-time. Skip if a
    # fresh cache exists (or the PDF is absent). --force re-extracts.
    if not force and not pages and os.path.exists(out) and (not os.path.exists(pdf)
            or os.path.getmtime(out) >= os.path.getmtime(pdf)):
        n = sum(1 for _ in open(out))
        print(f"extract: cache/{stem}.jsonl present ({n} pages) — skip (use --force to re-extract)")
        return 0
    if not os.path.exists(pdf):
        print(f"extract: {pdf} missing and no cache — run fetch_docs.sh"); return 2
    doc = fitz.open(pdf)
    rng = range(doc.page_count)
    if pages:
        a, b = pages.split("-"); rng = range(int(a) - 1, int(b))
    n = nv = 0
    with open(out, "w") as f:
        for i in rng:
            if i < 0 or i >= doc.page_count: continue
            rec = page_record(doc[i], i)
            if rec["verilog"]: nv += 1
            f.write(json.dumps(rec) + "\n"); n += 1
    print(f"extract: cached {n} pages ({nv} with Verilog templates) -> cache/{stem}.jsonl")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--pages", default=None)
    ap.add_argument("--force", action="store_true", help="re-extract even if cache exists")
    a = ap.parse_args()
    sys.exit(run(a.pdf, a.pages, a.force))
