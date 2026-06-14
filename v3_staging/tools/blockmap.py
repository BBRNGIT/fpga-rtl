#!/usr/bin/env python3
"""
blockmap.py — Tool: join the three extractions into the full system block diagram.

Reads board_net.json (Z19 connections), ds_resources.json (DS891 inventory), and
device.json (UG-transcribed gate-level blocks), then renders blockmap.html: the
ZU19EG at center with its resource inventory, the board peripherals around it, and
every FPGA-resource -> peripheral edge (counts + direction) — the picture the
connections reveal. No hand-drawing.
"""
import json, os, sys, html, re
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

def subsystem(name):
    n = name.upper()
    if re.match(r'(LUT|FD|LD|CARRY|MUXF|SRL|RAM\d|CFGLUT|AND2)', n): return "CLB logic"
    if re.match(r'(RAMB|URAM|FIFO)', n): return "Memory"
    if n.startswith("DSP"): return "DSP"
    if re.match(r'(IBUFDS_GTE|OBUFDS_GTE|GT)', n): return "Transceiver"
    if re.match(r'(IBUF|OBUF|IOBUF|ISERDES|OSERDES|IDELAY|ODELAY|IDDR|ODDR|BITSLICE|HPIO|KEEPER|PULL|IDELAYCTRL|HARD_SYNC)', n): return "I/O"
    if re.match(r'(BUFG|BUFCE|MMCM|PLL|BUFH)', n): return "Clocking"
    return "Config / other"

def load(p, d):
    try: return json.load(open(p))
    except Exception: return d

def esc(s): return html.escape(str(s))

def main():
    net = load(os.path.join(HERE, "board_net.json"), [])
    inv = load(os.path.join(HERE, "ds_resources.json"), {}).get("ZU19EG", {})
    dev = load(os.path.join(ROOT, "device", "device.json"), {"blocks": {}})
    prims = load(os.path.join(HERE, "catalog.json"), {})       # complete parts list (142, ports+params+hard-IP notes)
    prims = {k: v for k, v in prims.items() if not k.startswith("xpm_")}
    transcribed = {k for k, b in dev["blocks"].items() if not b.get("abstract")}

    # peripheral (interface) -> {resource: count, dirs}
    per = defaultdict(lambda: Counter())
    pdir = defaultdict(Counter)
    for r in net:
        iface = r.get("iface", "?")
        if iface.startswith("Config") or iface.startswith("Master") or iface.startswith("ZYNQ"): continue
        per[iface][r["resource"]] += 1
        if r.get("dir"): pdir[iface][r["dir"]] += 1
    # order peripherals by total connections
    order = sorted(per, key=lambda k: -sum(per[k].values()))

    # which FPGA-resource a peripheral mainly uses -> chip side
    def main_res(iface): return per[iface].most_common(1)[0][0]
    SIDE = {"transceiver(GT/PS-GTR)": "gt", "GT_refclk": "gt",
            "PL_IO": "io", "PS_DDR": "ps", "PS_MIO": "ps", "PS": "ps", "other": "io"}
    cols = {"gt": [], "io": [], "ps": []}
    for iface in order:
        cols[SIDE.get(main_res(iface), "io")].append(iface)

    # transcription status by subsystem
    nblk = len(dev["blocks"]); ndec = sum(1 for b in dev["blocks"].values() if not b.get("abstract"))

    invrows = "".join(f"<tr><td>{esc(k)}</td><td class='v'>{esc(v)}</td></tr>"
                      for k, v in inv.items() if not k.startswith("FFV"))
    def perip(iface):
        rc = per[iface]; tot = sum(rc.values())
        res = rc.most_common(1)[0][0].split("(")[0]
        d = pdir[iface]; ds = (f" {d['out']}↑" if d.get('out') else "") + (f" {d['in']}↓" if d.get('in') else "")
        return (f"<div class='per'><div class='pn'>{esc(iface)}</div>"
                f"<div class='pm'>{tot} conns · {esc(res)}{ds}</div></div>")
    gt = "".join(perip(i) for i in cols["gt"])
    io = "".join(perip(i) for i in cols["io"])
    ps = "".join(perip(i) for i in cols["ps"])

    # PARTS LIST — UG974 primitives grouped by subsystem (green = decomposition already derived)
    bysub = defaultdict(list)
    for name in sorted(prims): bysub[subsystem(name)].append(name)
    SUBORD = ["CLB logic", "Memory", "DSP", "I/O", "Clocking", "Transceiver", "Config / other"]
    parts = ""
    for sub in SUBORD:
        names = bysub.get(sub, [])
        if not names: continue
        ndone = sum(1 for n in names if n in transcribed)
        def chip(n):
            p = prims[n]; stub = bool(p.get("note"))
            cls = "done" if n in transcribed else ("stub" if stub else "")
            meta = esc(p["note"]) if stub else f"{len(p['ports'])}p·{len(p['params'])}a"
            return f"<span class='chip {cls}' title='{esc(p.get('note',''))}'>{esc(n)}<i>{meta}</i></span>"
        chips = "".join(chip(n) for n in names)
        nstub = sum(1 for n in names if prims[n].get("note"))
        sd = f"<span class='pd'>{ndone} derived</span>" + (f"<span class='ps2'>{nstub} hard-IP→other doc</span>" if nstub else "")
        parts += (f"<div class='psub'><div class='ph'>{esc(sub)} <b>{len(names)}</b>{sd}</div>{chips}</div>")

    doc = TMPL.replace("__INV__", invrows).replace("__GT__", gt).replace("__IO__", io)\
        .replace("__PS__", ps).replace("__PARTS__", parts).replace("__NCONN__", str(len(net)))\
        .replace("__NBLK__", f"{ndec} derived / {nblk}").replace("__NPRIM__", str(len(prims)))\
        .replace("__NPER__", str(len(order)))
    os.makedirs(os.path.join(ROOT, "views"), exist_ok=True)
    open(os.path.join(ROOT, "views", "blockmap.html"), "w").write(doc)
    print(f"blockmap: wrote blockmap.html — {len(prims)} primitives (parts), {len(net)} connections (netlist), "
          f"{len(order)} peripherals, {ndec}/{nblk} blocks derived")
    return 0

TMPL = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ZU19EG system block diagram</title>
<style>:root{--bg:#0e1116;--panel:#161b22;--line:#2a323d;--txt:#e6edf3;--dim:#9aa7b4;--chip:#1f6feb;--gt:#ff7b72;--io:#3fb950;--ps:#a371f7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:13px/1.5 ui-monospace,Menlo,monospace;padding:20px}
h1{font-size:18px;margin:0 0 2px}.sub{color:var(--dim);font-size:12px;margin:0 0 16px}
.grid{display:grid;grid-template-columns:1fr 1.3fr 1fr;gap:14px;align-items:start}
.col h2{font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin:0 0 8px}
.gt h2{color:var(--gt)}.io h2{color:var(--io)}.ps h2{color:var(--ps)}
.per{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:7px}
.gt .per{border-left:3px solid var(--gt)}.io .per{border-left:3px solid var(--io)}.ps .per{border-left:3px solid var(--ps)}
.pn{font-weight:700}.pm{color:var(--dim);font-size:11px}
.chip{background:var(--panel);border:2px solid var(--chip);border-radius:12px;padding:14px}
.chip h2{font-size:14px;margin:0 0 8px;color:var(--chip)}
.chip table{width:100%;border-collapse:collapse}.chip td{padding:3px 6px;border-bottom:1px solid var(--line);font-size:12px}
.chip td.v{text-align:right;font-weight:600}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 13px}
.card b{font-size:16px}.card span{color:var(--dim);font-size:11px;display:block}
.sec{margin-top:22px}.sec h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);margin:0 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.psub{margin-bottom:12px}.ph{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);margin-bottom:5px}.ph b{color:var(--txt)}.pd{margin-left:8px;color:var(--io)}
.chip{display:inline-block;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:3px 7px;margin:0 5px 5px 0;font-size:11px}
.chip.done{border-color:var(--io);color:var(--io)}.chip.stub{border-style:dashed;border-color:var(--gt);color:var(--gt)}.chip i{color:var(--dim);font-style:normal;margin-left:5px;font-size:9.5px}
.pd{margin-left:8px;color:var(--io)}.ps2{margin-left:8px;color:var(--gt)}
.note{color:var(--dim);font-size:11.5px;margin-top:14px}</style></head>
<body><h1>ZU19EG — full system block diagram (from the connections)</h1>
<p class="sub">Generated by blockmap.py from board_net.json (Z19) + ds_resources.json (DS891) + device.json (UGs). The edges are the spec's actual source→destinations.</p>
<div class="cards">
<div class="card"><b>__NPRIM__</b><span>chip primitives (parts, UG974)</span></div>
<div class="card"><b>__NCONN__</b><span>board connections (netlist, Z19)</span></div>
<div class="card"><b>__NPER__</b><span>board peripherals</span></div>
<div class="card"><b>__NBLK__</b><span>blocks derived to gates</span></div>
</div>
<div class="grid">
<div class="col io"><h2>◀ PL I/O peripherals</h2>__IO__</div>
<div class="col"><div class="chip"><h2>XCZU19EG (chip inventory — DS891)</h2><table>__INV__</table>
<p style="color:var(--dim);font-size:11px;margin:8px 0 0">↑ transcribed: clocking subsystem (24 blocks). Logic/Memory/DSP/IO/Transceiver/PS pending their UGs.</p></div></div>
<div class="col gt ps"><h2 style="color:var(--gt)">▶ transceiver peripherals</h2>__GT__<h2 style="color:var(--ps);margin-top:14px">PS peripherals</h2>__PS__</div>
</div>
<div class="sec"><h2>Parts list — chip primitives (UG974, ports·params) · green = decomposition derived</h2>__PARTS__</div>
<p class="note">Each peripheral box: connection count + the FPGA resource it lands on + direction (↑out/↓down). Transceiver peripherals (SFP/PCIe/USB/SATA/DP) ride the GTH/GTY/PS-GTR; PL-IO peripherals (FMC/DDR4-PL/Ethernet) ride the I/O banks; PS peripherals ride PS-MIO/PS-DDR. This is the system source→destination map the three docs jointly reveal.</p>
</body></html>"""

if __name__ == "__main__":
    try: sys.exit(main())
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(2)
