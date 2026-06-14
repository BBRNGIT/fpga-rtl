#!/usr/bin/env python3
"""
progress.py — Tool: generate progress.html, the transcription-progress dashboard.

Reads ONLY tool-generated artifacts (device.json, specgen_out.json, figdiff_out.json)
and renders exactly how far spec->library transcription has gotten: per-block ports /
decomposition / connection status, overall totals, and the UG roadmap (honest scope).
Viewable at /progress.html on the served link. Exit 0 / 2.
"""
import json, os, sys, html
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default

# doc-caption quirks -> canonical (mirror of assemble.ALIAS, for the ports-verified mark)
ALIAS = {"MMCME": "MMCME4_ADV", "MMCM": "MMCME4_ADV", "PLLE": "PLLE4_BASE", "PLL": "PLLE4_BASE"}

# honest device scope: which UGs (areas) of the full ZU19EG are transcribed
ROADMAP = [
    ("UG572  Clocking — MMCM / PLL / BUFG*",        "active"),
    ("UG574  CLB — LUT6 / FF / CARRY8 / MUXF",      "pending"),
    ("UG573  Memory — BRAM / URAM / FIFO",          "pending"),
    ("UG579  DSP48E2",                              "pending"),
    ("UG571  SelectIO — IOB / SERDES / delay",      "pending"),
    ("UG576  Transceivers — GTH / GTY",             "pending"),
    ("UG1085 PS8 — A53 / R5F / GIC / CCI / DDR",    "pending"),
]

def esc(s): return html.escape(str(s))

def main():
    dev = load(os.path.join(ROOT, "device", "device.json"), {"primitives": {}, "blocks": {}})
    spec = load(os.path.join(HERE, "specgen_out.json"), {})
    fdiff = load(os.path.join(HERE, "figdiff_out.json"), {"blocks": {}, "total_ok": 0, "total": 0})

    prims = dev.get("primitives", {})
    blocks = dev.get("blocks", {})
    verified = set()
    for ename, e in spec.items():
        verified.add(ALIAS.get(ename, ename))

    rows, n_dec, n_stub, cells = [], 0, 0, 0
    for name, b in blocks.items():
        stub = b.get("abstract")
        ninst = len(b.get("insts", []))
        nport = len(b.get("ports", []))
        if stub: n_stub += 1
        else: n_dec += 1; cells += ninst
        pv = name in verified
        cd = fdiff["blocks"].get(name)
        conn = ""
        if cd:
            ok, tot = len(cd["confirmed"]), len(cd["confirmed"]) + len(cd["gaps"])
            conn = f"{ok}/{tot}"
        rows.append((name, b.get("group", ""), nport, pv, stub, ninst, conn,
                     cd["gaps"] if cd else []))

    nb = len(blocks)
    ug_done = sum(1 for _, s in ROADMAP if s == "active")
    cards = [
        ("primitive leaves", len(prims)),
        ("blocks", f"{n_dec} decomposed / {n_stub} stub"),
        ("gate-cells transcribed", f"{cells:,}"),
        ("ports verified vs PDF", f"{len(verified & set(blocks))}/{nb}"),
        ("connections confirmed", f"{fdiff['total_ok']}/{fdiff['total']}"),
        ("device areas (UGs)", f"{ug_done}/{len(ROADMAP)} (1 partial)"),
    ]

    def row_html(r):
        name, grp, nport, pv, stub, ninst, conn, gaps = r
        dec = '<span class="stub">STUB</span>' if stub else f'{ninst} cells'
        pvb = '<span class="ok">✓ PDF</span>' if pv else '<span class="dim">—</span>'
        cb = (f'<span class="{"ok" if conn.split("/")[0]==conn.split("/")[1] else "warn"}">{conn}</span>'
              if conn else '<span class="dim">—</span>')
        gt = f'<div class="gaps">gaps: {esc(", ".join(gaps))}</div>' if gaps else ''
        return (f'<tr><td class="nm">{esc(name)}</td><td class="dim">{esc(grp)}</td>'
                f'<td>{nport}</td><td>{pvb}</td><td>{dec}</td><td>{cb}{gt}</td></tr>')

    rm = "".join(f'<li class="{s}"><span class="rdot"></span>{esc(t)}'
                 f'<span class="rs">{s}</span></li>' for t, s in ROADMAP)
    cardhtml = "".join(f'<div class="card"><div class="cv">{esc(v)}</div>'
                       f'<div class="cl">{esc(l)}</div></div>' for l, v in cards)
    tbl = "".join(row_html(r) for r in rows)
    doc = TMPL.replace("__CARDS__", cardhtml).replace("__ROADMAP__", rm).replace("__ROWS__", tbl)
    open(os.path.join(ROOT, "progress.html"), "w").write(doc)
    print(f"progress: wrote progress.html — {n_dec} decomposed + {n_stub} stub blocks, "
          f"{cells:,} cells, ports {len(verified & set(blocks))}/{nb}, "
          f"connections {fdiff['total_ok']}/{fdiff['total']}")
    return 0

TMPL = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>v3 transcription progress</title>
<style>:root{--bg:#0e1116;--panel:#161b22;--line:#2a323d;--txt:#e6edf3;--dim:#9aa7b4;--ok:#3fb950;--warn:#d29922;--stub:#6e7681;--accent:#4493f8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:13px/1.5 ui-monospace,Menlo,monospace;padding:22px}
h1{font-size:18px;margin:0 0 2px}.sub{color:var(--dim);font-size:12px;margin:0 0 18px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.cv{font-size:19px;font-weight:700}.cl{color:var(--dim);font-size:11px;margin-top:4px;text-transform:uppercase;letter-spacing:.04em}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);margin:18px 0 8px}
ul.rm{list-style:none;padding:0;margin:0;display:grid;gap:6px}
ul.rm li{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:9px 12px;display:flex;align-items:center;gap:9px;font-size:12.5px}
.rdot{width:8px;height:8px;border-radius:50%;flex:none}
li.active .rdot{background:var(--ok)}li.pending .rdot{background:var(--stub)}
.rs{margin-left:auto;font-size:10px;text-transform:uppercase;color:var(--dim)}
li.active .rs{color:var(--ok)}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-top:8px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);font-size:12.5px}
th{color:var(--dim);font-weight:600;text-transform:uppercase;font-size:10.5px;letter-spacing:.05em}
.nm{font-weight:600}.dim{color:var(--dim)}.ok{color:var(--ok)}.warn{color:var(--warn)}.stub{color:var(--stub)}
.gaps{color:var(--warn);font-size:10.5px;margin-top:2px}</style></head>
<body><h1>v3 — spec → library transcription progress</h1>
<p class="sub">Generated by progress.py from the tool outputs (device.json + specgen + figdiff). Source: UG572 (clocking). The full ZU19EG spans ~7 UGs — this is early.</p>
<div class="cards">__CARDS__</div>
<h2>Device scope (UG roadmap)</h2><ul class="rm">__ROADMAP__</ul>
<h2>Blocks transcribed so far</h2>
<table><tr><th>block</th><th>group</th><th>ports</th><th>vs PDF</th><th>decomposition</th><th>connections (fig vs spec)</th></tr>__ROWS__</table>
</body></html>"""

if __name__ == "__main__":
    try: sys.exit(main())
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(2)
