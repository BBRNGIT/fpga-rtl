#!/usr/bin/env python3
"""
dsparse.py — Tool: extract a device's RESOURCE COUNTS from a datasheet (DS891).

DS891 feature tables are FEATURE-rows x DEVICE-columns. This finds every table whose
header names the target device (default ZU19EG), reads that column, and emits the
device's resource/feature list -> ds_resources.json. This is the device INVENTORY
(the "what's in the chip + how many") that bounds the build scope.

Usage: dsparse.py <pdf> [--device ZU19EG] [--pages a-b] [--out ds_resources.json]
"""
import sys, os, re, json, argparse
try:
    import fitz
except Exception as e:
    print(f"dsparse: PyMuPDF required: {e}"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))

def clean(s): return re.sub(r'\s+', ' ', (s or '').strip())

def run(pdf, device, pages, out):
    doc = fitz.open(pdf); rng = range(doc.page_count)
    if pages:
        a, b = pages.split("-"); rng = range(int(a) - 1, int(b))
    facts = {}
    for i in rng:
        if i < 0 or i >= doc.page_count: continue
        try: tabs = doc[i].find_tables()
        except Exception: continue
        for t in tabs.tables:
            rows = t.extract()
            if not rows: continue
            # find the header row + the device's column
            col = None; hdr_i = 0
            for ri, r in enumerate(rows[:3]):
                for ci, c in enumerate(r):
                    if c and device.upper() in clean(c).upper():
                        col, hdr_i = ci, ri; break
                if col is not None: break
            if col is None: continue
            for r in rows[hdr_i + 1:]:
                if len(r) <= col: continue
                label = clean(r[0]) or next((clean(c) for c in r if c and c.strip()), '')
                val = clean(r[col])
                if label and val and val != label and len(val) < 60:
                    facts.setdefault(label, val)
    json.dump({device: facts}, open(out, "w"), indent=2)
    print(f"dsparse: {len(facts)} {device} facts -> {out}")
    for k, v in list(facts.items())[:40]:
        print(f"  {k[:40]:40s} = {v}")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--device", default="ZU19EG")
    ap.add_argument("--pages", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "ds_resources.json"))
    a = ap.parse_args()
    sys.exit(run(a.pdf, a.device, a.pages, a.out))
