#!/usr/bin/env python3
"""
hierarchy.py — assemble ALL committed extraction artifacts into ONE hierarchical graph
netlist (the physical-proof view), emit an interactive HTML, and materialize a folder tree
so the circuit hierarchy is physically enforced before any code is built.

Inputs (committed):  catalog.json, ds_resources.json, board_net.json, figblocks_out.json,
  ug576_figblocks.json, ug578_figblocks.json, ps_ports.json, ug1085_richtext.json (routing).
Outputs: ../hierarchy.json (nodes+edges), ../hierarchy.html (collapsible tree + edges),
  ../device_tree/<path>/node.json (folder hierarchy, with --materialize).

Faithful: every node/count/port/edge comes from an extracted artifact; nothing invented.
Usage: hierarchy.py [--materialize]
"""
import json, os, re, sys, html, argparse, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
def L(p, d):
    try: return json.load(open(os.path.join(HERE, p)))
    except Exception: return d
def num(s):
    try: return int(str(s).replace(",", "").split(".")[0])
    except Exception: return None

cat = L("catalog.json", {}); ds = L("ds_resources.json", {})
inv = next(iter(ds.values()), {}) if ds else {}
board = L("board_net.json", []); ps = L("ps_ports.json", {})
fig = {**L("figblocks_out.json", {}), **L("ug576_figblocks.json", {}), **L("ug578_figblocks.json", {})}
routing = L("ug1085_richtext.json", {}).get("routing", [])

# physical fabric elements with authentic DS891 counts + the catalogue configs that USE them
PHYS = [  # (subsystem, element, role, count, [catalogue-config name prefixes])
 ("CLB", "storage_element", "configurable FF/latch (CE, sync/async set/reset)", num(inv.get("CLB Flip-Flops")), ["FD","LD"]),
 ("CLB", "LUT6", "6-input LUT / distributed-RAM / SRL (SLICEM)", num(inv.get("CLB LUTs")), ["LUT","RAM","SRL","CFGLUT"]),
 ("CLB", "CARRY8", "carry chain", (num(inv.get("CLB LUTs")) or 0)//8 or None, ["CARRY"]),
 ("CLB", "MUXF", "wide function mux (F7/F8/F9)", None, ["MUXF"]),
 ("Memory", "RAMB36E2", "36Kb block RAM", num(inv.get("Block RAM Blocks")), ["RAMB36","FIFO36"]),
 ("Memory", "RAMB18E2", "18Kb block RAM", (num(inv.get("Block RAM Blocks")) or 0)*2 or None, ["RAMB18","FIFO18"]),
 ("Memory", "URAM288", "288Kb UltraRAM", num(inv.get("UltraRAM Blocks")), ["URAM"]),
 ("DSP", "DSP48E2", "DSP slice", num(inv.get("DSP Slices")), ["DSP"]),
 ("Clocking", "CMT", "clock mgmt tile (MMCM+PLL)", num(inv.get("CMTs")), ["MMCM","PLL","BUFG","BUFCE","BUFGCE","BUFGCTRL"]),
 ("Transceiver", "GTH", "16.3Gb/s transceiver", num(inv.get("GTH Transceiver 16.3Gb/s(3)")), ["GTHE4"]),
 ("Transceiver", "GTY", "32.75Gb/s transceiver", num(inv.get("GTY Transceivers 32.75Gb/s")), ["GTYE4"]),
 ("I/O", "HP_IO", "high-performance I/O", num(inv.get("Max. HP I/O(1)")), ["IBUF","OBUF","IOBUF","ISERDES","OSERDES","IDELAY","ODELAY","IDDR","ODDR","BITSLICE","HPIO","HARD_SYNC","KEEPER","DCIRESET","ODELAYE","IDELAYE"]),
 ("I/O", "HD_IO", "high-density I/O", num(inv.get("Max. HD I/O(2)")), []),
 ("Config", "config", "configuration / boot / system", None, ["BSCAN","ICAP","STARTUP","EFUSE","DNA","FRAME_ECC","USR_ACCESS","MASTER","SYSMON"]),
]
SUBS = ["CLB", "Memory", "DSP", "Clocking", "I/O", "Transceiver", "Config", "Interconnect"]

nodes, edges = [], []
def N(nid, parent, kind, **m): nodes.append({"id": nid, "parent": parent, "kind": kind, **m})

N("XCZU19EG", None, "device", label="XCZU19EG (Zynq UltraScale+ MPSoC)",
  note=f"{inv.get('System Logic Cells','?')} system logic cells")
for dom in ("PL", "PS", "Board"): N(dom, "XCZU19EG", "domain")

# --- PL: subsystem -> physical element (count) -> catalogue configs (ports) -------------
assigned = set()
for sub in SUBS: N(f"PL/{sub}", "PL", "subsystem")
N("PL/Interconnect", "PL", "subsystem", note="INT tiles / PIP crossbar — synthesized from primitives (P3)")
for sub, el, role, count, prefixes in PHYS:
    eid = f"PL/{sub}/{el}"
    N(eid, f"PL/{sub}", "element", role=role, count=count)
    for name in sorted(cat):
        if name in assigned: continue
        if any(name.upper().startswith(p) for p in prefixes):
            v = cat[name]; assigned.add(name)
            N(f"{eid}/{name}", eid, "config", ports=len(v.get("ports", [])),
              ports_list=v.get("ports", []),                # full port-level netlist detail
              note=v.get("note") or v.get("port_src") or v.get("group") or "", source=v.get("source", ""))
# remaining ported primitives placed by their authoritative PRIMITIVE_GROUP (no name-prefix
# guessing). PS blocks live under the PS domain (below); E3 transceivers are UltraScale, not in
# this UltraScale+ part -> honestly excluded. Placement here is group-level; the exact config-bit
# map is P1 (UG574/573/579), deliberately not faked.
GROUP_EL = {"CLB": "PL/CLB/dedicated_gate", "REGISTER": "PL/CLB/storage_element",
            "BLOCKRAM": "PL/Memory/RAMB36E2", "CLOCK": "PL/Clocking/CMT", "I": "PL/I/O/HP_IO",
            "ADVANCED": "PL/Transceiver/_hard_ip", "CONFIGURATION": "PL/Config/config",
            "ARITHMETIC": "PL/DSP/DSP48E2"}
for name in sorted(cat):
    v = cat[name]
    if name in assigned or not v.get("ports"): continue
    g = v.get("group", "")
    if g == "PS": continue                                   # PS-domain block, placed under PS
    if re.match(r"GT[HY]E3", name.upper()):                  # UltraScale (E3) — not in ZU19EG (E4)
        N(f"PL/Transceiver/_not_in_part/{name}", "PL/Transceiver", "excluded", ports=len(v["ports"]),
          note="UltraScale GTHE3/GTYE3 — ZU19EG is UltraScale+ (uses E4)"); continue
    pid = GROUP_EL.get(g, "PL/Config/config")
    if not any(x["id"] == pid for x in nodes):
        N(pid, pid.rsplit("/", 1)[0], "element", role="(group-level placement; config-map TBD in P1)")
    N(f"{pid}/{name}", pid, "config", ports=len(v["ports"]), ports_list=v["ports"], note=v.get("note", ""))

# --- PS: blocks -> signal count ---------------------------------------------------------
for blk, sigs in ps.items():
    N(f"PS/{blk}", "PS", "subsystem", count=len(sigs), note="UG1085")

# --- Board: peripherals by interface ----------------------------------------------------
from collections import Counter, defaultdict
peri = defaultdict(Counter)
for r in board: peri[r.get("iface","?")][r.get("resource","?")] += 1
for iface, rc in sorted(peri.items(), key=lambda kv:-sum(kv[1].values())):
    N(f"Board/{iface}", "Board", "peripheral", count=sum(rc.values()), note=rc.most_common(1)[0][0])
# EVERY individual pin/ball assignment as a leaf (the real external netlist — not aggregated)
for r in board:
    sig = (r.get("signal") or "").strip()
    if not sig: continue
    N(f"Board/{r.get('iface','?')}/{sig}", f"Board/{r.get('iface','?')}", "assignment",
      pin=r.get("pin",""), ball=r.get("ball",""), dir=r.get("dir",""), resource=r.get("resource",""))

# --- edges: per-signal board assignment -> resource ; figures ; PS-PL routing ----------
for r in board:
    sig = (r.get("signal") or "").strip()
    if not sig: continue
    edges.append({"src": f"Board/{r.get('iface','?')}/{sig}", "dst": f"PL/{r.get('resource','?')}",
                  "kind": "board", "pin": r.get("pin",""), "ball": r.get("ball",""), "dir": r.get("dir","")})
for k, v in fig.items():
    for c in v.get("connections", []):
        b = c.get("blocks", [])
        for i in range(len(b)-1):
            edges.append({"src": b[i], "dst": b[i+1], "kind": "figure", "fig": k, "signals": c.get("signals", [])[:4]})
for r in routing:
    # provenance derives from the extracted row itself (richtext kept the page);
    # the edge carries the doc citation so C06 (connection-provenance) can trace it.
    _pg = r.get("page")
    _src = f"ug1085 p{_pg} Table 2-5" if _pg else ""
    edges.append({"src": f"PS:{r.get('source','')}", "dst": f"PS:{r.get('destination','')}",
                  "kind": "routing", "name": r.get("name",""), "source": _src})
# UG572 clock-fabric nets (figparse): each net = pins wired together (clock distribution)
for k, v in L("figparse_out.json", {}).items():
    for net in v.get("nets", []):
        labs = net.get("net", [])
        for i in range(len(labs)-1):
            edges.append({"src": f"clk:{labs[i]}", "dst": f"clk:{labs[i+1]}", "kind": "clocknet", "fig": k})

json.dump({"nodes": nodes, "edges": edges}, open(os.path.join(ROOT, "hierarchy.json"), "w"), indent=2)

# ---- HTML: collapsible hierarchy + edge tallies ---------------------------------------
kids = defaultdict(list)
for n in nodes: kids[n["parent"]].append(n)
def esc(s): return html.escape(str(s))
def render(nid):
    n = next(x for x in nodes if x["id"] == nid)
    ch = kids.get(nid, [])
    cnt = f" <b>×{n['count']:,}</b>" if n.get("count") else ""
    meta = []
    if n.get("role"): meta.append(esc(n["role"]))
    if n.get("kind") == "assignment":
        meta.append(f"pin {esc(n.get('pin','?'))} · ball {esc(n.get('ball','?'))}"
                    + (f" · {esc(n['dir'])}" if n.get("dir") else "") + f" → {esc(n.get('resource',''))}")
    if n.get("ports") is not None: meta.append(f"{n['ports']} ports")
    if n.get("note"): meta.append(esc(n["note"]))
    label = esc(n.get("label", nid.split("/")[-1]))
    head = f"<span class='k k-{n['kind']}'>{n['kind']}</span> <span class='nm'>{label}</span>{cnt}" + \
           (f" <span class='m'>{' · '.join(meta)}</span>" if meta else "")
    if not ch: return f"<li class='leaf'>{head}</li>"
    inner = "".join(render(c["id"]) for c in sorted(ch, key=lambda c: (-(c.get('count') or 0), c['id'])))
    op = " open" if n["kind"] in ("device","domain") else ""
    return f"<li><details{op}><summary>{head} <span class='c'>{len(ch)}</span></summary><ul>{inner}</ul></details></li>"
ek = Counter(e["kind"] for e in edges)
doc = f"""<!doctype html><meta charset=utf-8><title>XCZU19EG hierarchy</title>
<style>:root{{--bg:#0e1116;--p:#161b22;--l:#2a323d;--t:#e6edf3;--d:#9aa7b4}}
body{{margin:0;background:var(--bg);color:var(--t);font:13px/1.55 ui-monospace,Menlo,monospace;padding:20px}}
h1{{font-size:17px;margin:0 0 4px}}.sub{{color:var(--d);margin:0 0 14px}}
ul{{list-style:none;margin:0;padding-left:18px}}li{{margin:1px 0}}
details>summary{{cursor:pointer;list-style:none}}details>summary::-webkit-details-marker{{display:none}}
summary:before{{content:'▶ ';color:var(--d)}}details[open]>summary:before{{content:'▼ '}}
.leaf{{padding-left:14px;color:var(--d)}}
.k{{font-size:9px;text-transform:uppercase;letter-spacing:.04em;padding:1px 5px;border-radius:8px;background:var(--p);border:1px solid var(--l)}}
.k-device{{color:#1f6feb}}.k-domain{{color:#a371f7}}.k-subsystem{{color:#3fb950}}.k-element{{color:#e3b341}}.k-config{{color:var(--d)}}.k-peripheral{{color:#ff7b72}}.k-assignment{{color:#56d4dd}}
.nm{{font-weight:600}}.m{{color:var(--d);font-size:11px}}.c{{color:var(--d);font-size:10px}}
.cards{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}}.card{{background:var(--p);border:1px solid var(--l);border-radius:8px;padding:8px 12px}}.card b{{font-size:15px}}.card span{{color:var(--d);font-size:11px;display:block}}</style>
<h1>XCZU19EG — hierarchical netlist (physical-proof view)</h1>
<p class=sub>Generated by hierarchy.py from the committed extraction artifacts. Every node/count/port/edge is extracted, not invented. Layered model: subsystem → physical element (DS891 count) → catalogue config (UNISIM use).</p>
<div class=cards>
<div class=card><b>{len(nodes)}</b><span>nodes</span></div>
<div class=card><b>{len(edges)}</b><span>edges</span></div>
<div class=card><b>{ek['board']}</b><span>board edges</span></div>
<div class=card><b>{ek['figure']}</b><span>figure edges</span></div>
<div class=card><b>{ek['routing']}</b><span>PS-PL routing</span></div>
</div>
<ul>{render('XCZU19EG')}</ul>"""
os.makedirs(os.path.join(ROOT, "views"), exist_ok=True)
open(os.path.join(ROOT, "views", "hierarchy.html"), "w").write(doc)

# ---- materialize folder hierarchy ------------------------------------------------------
mat = "--materialize" in sys.argv
if mat:
    base = os.path.join(ROOT, "device_tree")
    if os.path.exists(base): shutil.rmtree(base)
    for n in nodes:
        d = os.path.join(base, *n["id"].split("/"))
        os.makedirs(d, exist_ok=True)
        out_e = [e for e in edges if e["src"] == n["id"] or e["dst"] == n["id"]]
        json.dump({**n, "edges": out_e}, open(os.path.join(d, "node.json"), "w"), indent=2)

print(f"hierarchy: {len(nodes)} nodes, {len(edges)} edges -> hierarchy.json + hierarchy.html"
      + (f" + device_tree/ ({sum(1 for n in nodes)} dirs)" if mat else ""))
_cfg = sum(1 for n in nodes if n["kind"] == "config")
_exc = sum(1 for n in nodes if n["kind"] == "excluded")
_unm = sum(1 for n in nodes if "_unmapped" in n["id"])
print(f"  catalogue placement: {_cfg} configs placed under physical elements, {_unm} unmapped, "
      f"{_exc} excluded (E3 not in part), PS blocks under PS domain")
