#!/usr/bin/env python3
"""
tabledump.py — Tool: inspect the TABLE structures in any PDF so specialized
extractors (dsparse for DS891 resource counts, boardparse for Z19 pinouts) can be
built to match reality. For each detected table it prints the nearest heading, the
column count, the header row, and the first data rows. No hand-probing — a tool reports.

Usage: tabledump.py <pdf> [--pages a-b] [--max N]
"""
import sys, os, argparse
try:
    import fitz
except Exception as e:
    print(f"tabledump: PyMuPDF required: {e}"); sys.exit(2)

def heading_above(page, tbl):
    y0 = tbl.bbox[1]; best, bd = "", 1e9
    for b in page.get_text("blocks"):
        if b[3] <= y0 + 2 and 0 <= y0 - b[3] < bd and b[4].strip():
            bd = y0 - b[3]; best = b[4].strip().replace("\n", " ")
    return best[:70]

def run(pdf, pages, mx):
    doc = fitz.open(pdf)
    rng = range(doc.page_count)
    if pages:
        a, b = pages.split("-"); rng = range(int(a) - 1, int(b))
    shown = 0
    for i in rng:
        if i < 0 or i >= doc.page_count: continue
        try: tabs = doc[i].find_tables()
        except Exception: continue
        for t in tabs.tables:
            rows = t.extract()
            if not rows: continue
            ncol = max(len(r) for r in rows)
            print(f"\n── p{i+1}  [{len(rows)}x{ncol}]  «{heading_above(doc[i], t)}»")
            for r in rows[:4]:
                cells = [(c or "").replace("\n", " ").strip()[:22] for c in r]
                print("   | " + " | ".join(cells))
            shown += 1
            if shown >= mx:
                print(f"\n(reached --max {mx})"); return 0
    print(f"\ntabledump: {shown} table(s) shown")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--pages", default=None); ap.add_argument("--max", type=int, default=40)
    a = ap.parse_args()
    sys.exit(run(a.pdf, a.pages, a.max))
