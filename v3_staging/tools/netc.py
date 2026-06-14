#!/usr/bin/env python3
"""
netc.py — Tool #1 of the v3 toolchain: the netlist compiler / renderer / validator.

Input : library.json  — THE format ({primitives, blocks} in {ports, cells, nets} form).
Output: explorer.html — auto-rendered schematic + generated netlist text per block.
        device.json   — the canonical flattened netlist every downstream tool consumes.

You author the FORMAT. This tool draws + validates. No schematic is hand-coded.
Exit codes: 0 = ok, 1 = validation error (spec wrong), 2 = internal tool error.
"""
import json, os, sys, html, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIB  = os.path.join(ROOT, "device", "library.json")
OUT_HTML = os.path.join(ROOT, "views", "explorer.html")
OUT_JSON = os.path.join(ROOT, "device", "device.json")

# ---------- format expansion ----------
def port_bits(p):
    w = p.get("width", 1)
    return [p["name"]] if w == 1 else [f'{p["name"]}[{b}]' for b in range(w)]

def resolve(v, i):
    if isinstance(v, str) and v.startswith("="):
        return str(eval(v[1:], {"__builtins__": {}}, {"i": i}))
    if i is not None and isinstance(v, str):
        try: return v.format(i=i)
        except Exception: return v
    return v

def expand(blk):
    """ -> (ports[(net,dir,kind)], insts[(ref,type,{pin:net})]) with gen + width expanded."""
    ports = []
    for p in blk.get("ports", []):
        for bn in port_bits(p):
            ports.append((bn, p["dir"], p.get("kind")))
    insts = []
    for c in blk.get("cells", []):
        idxs = [None]
        if "gen" in c:
            lo, hi = c["gen"]["range"]; idxs = list(range(lo, hi + 1))
        for i in idxs:
            ref = c["ref"].format(i=i) if i is not None else c["ref"]
            conn = {pin: resolve(v, i) for pin, v in c["conn"].items()}
            insts.append((ref, c["type"], conn))
    return ports, insts

def get_pins(t, prims, blocks):
    if t in prims:
        outs = set(prims[t].get("out", [])); ins = set(prims[t]["pins"]) - outs
        return ins, outs
    if t in blocks:
        ins, outs = set(), set()
        for p in blocks[t].get("ports", []):
            for bn in port_bits(p):
                (outs if p["dir"] == "out" else ins).add(bn)
        return ins, outs
    return None, None

def base_net(tok):
    """strip negation / detect constant."""
    if tok in ("0", "1", "GND", "VCC"): return None
    return tok[1:] if tok.startswith("~") else tok

# ---------- validation ----------
def validate(lib):
    prims, blocks = lib["primitives"], lib["blocks"]
    errs, warns = [], []
    # type-hierarchy acyclicity
    def cyc(t, stack):
        if t in prims: return
        if t in stack: errs.append(f"type cycle: {' -> '.join(stack+[t])}"); return
        for c in blocks.get(t, {}).get("cells", []):
            cyc(c["type"], stack + [t])
    for bn in blocks: cyc(bn, [])

    for name, blk in blocks.items():
        if blk.get("abstract") or not blk.get("cells"):
            warns.append(f"[{name}] stub — ports declared from spec, decomposition pending")
            continue
        ports, insts = expand(blk)
        in_ports  = {n for n, d, k in ports if d == "in"}
        out_ports = {n for n, d, k in ports if d == "out"}
        drivers, reads = {}, {}
        for n in in_ports: drivers.setdefault(n, []).append("PORT")
        for n in out_ports: reads.setdefault(n, []).append("OUT")
        for ref, typ, conn in insts:
            ins, outs = get_pins(typ, prims, blocks)
            if ins is None:
                errs.append(f"[{name}] {ref}: unknown type '{typ}'"); continue
            need = ins | outs
            for pin in conn:
                if pin not in need:
                    errs.append(f"[{name}] {ref}({typ}): pin '{pin}' not on this type")
            for pin in need:
                if pin not in conn:
                    errs.append(f"[{name}] {ref}({typ}): pin '{pin}' unconnected")
            for pin in outs & set(conn):
                drivers.setdefault(conn[pin], []).append(f"{ref}.{pin}")
            for pin in ins & set(conn):
                b = base_net(conn[pin])
                if b is not None: reads.setdefault(b, []).append(f"{ref}.{pin}")
        # single-writer
        for net, drv in drivers.items():
            if len(drv) > 1:
                errs.append(f"[{name}] multi-driver net '{net}': {', '.join(drv)}")
        # floating (read, no driver) / undriven outputs
        for net, rd in reads.items():
            if net not in drivers:
                errs.append(f"[{name}] floating net '{net}' (read by {', '.join(rd)}, no driver)")
        for op in out_ports:
            real = [d for d in drivers.get(op, []) if d != "PORT"]
            if not real:
                errs.append(f"[{name}] output port '{op}' is undriven")
        # dangling (driven, never read, not an output) -> warning
        for net, drv in drivers.items():
            if net not in reads and net not in out_ports and drv != ["PORT"]:
                warns.append(f"[{name}] dangling net '{net}' (driven by {drv[0]}, never read)")
    return errs, warns

# ---------- layout + render ----------
def layout(blk, prims, blocks):
    ports, insts = expand(blk)
    in_ports  = [n for n, d, k in ports if d == "in"]
    out_ports = [n for n, d, k in ports if d == "out"]
    drv_of = {}                                  # net -> inst ref that drives it
    reads_of = {}                                # ref -> [nets it reads]
    for ref, typ, conn in insts:
        ins, outs = get_pins(typ, prims, blocks)
        for pin in (outs or set()) & set(conn): drv_of[conn[pin]] = ref
        reads_of[ref] = [base_net(conn[p]) for p in (ins or set()) & set(conn)
                         if base_net(conn[p]) is not None]
    depth, seen = {}, set()
    def dep(ref):
        if ref in depth: return depth[ref]
        if ref in seen: return 0
        seen.add(ref)
        ins = [drv_of.get(n) for n in reads_of.get(ref, [])]
        d = 1 + max([dep(p) for p in ins if p] + [0])
        depth[ref] = d; return d
    for ref, _, _ in insts: dep(ref)
    maxd = max([depth.get(r, 1) for r, _, _ in insts] + [1])
    cols = {0: list(in_ports)}
    for ref, typ, _ in insts: cols.setdefault(depth[ref], []).append(ref)
    cols[maxd + 1] = list(out_ports)
    return ports, insts, drv_of, depth, cols, maxd, in_ports, out_ports

def esc(s): return html.escape(str(s))

def render_svg(name, blk, prims, blocks):
    ports, insts, drv_of, depth, cols, maxd, in_ports, out_ports = layout(blk, prims, blocks)
    CW, RH, BW, BH, MX, MY = 168, 60, 120, 38, 60, 40
    pos = {}                                     # ref/port -> (x,y center-left)
    ncols = maxd + 2
    rowcount = max((len(v) for v in cols.values()), default=1)
    W = MX * 2 + (ncols - 1) * CW + BW
    H = MY * 2 + max(rowcount, 1) * RH
    parts = []
    typ_of = {ref: t for ref, t, _ in insts}
    # place
    for col, members in cols.items():
        x = MX + col * CW
        for r, m in enumerate(members):
            y = MY + r * RH
            pos[m] = (x, y)
    # wires first (under boxes)
    for ref, typ, conn in insts:
        ins, outs = get_pins(typ, prims, blocks)
        tx, ty = pos[ref]
        for pin in (ins or set()) & set(conn):
            b = base_net(conn[pin]);
            if b is None: continue
            src = drv_of.get(b, b if b in pos else None)
            if src is None or src not in pos: continue
            sx, sy = pos[src]
            x1 = sx + (BW if src in typ_of or src in in_ports else 8); y1 = sy + BH/2
            x2 = tx; y2 = ty + BH/2
            mx = (x1 + x2) / 2
            inv = conn[pin].startswith("~")
            parts.append(f'<path class="w" d="M{x1:.0f},{y1:.0f} H{mx:.0f} V{y2:.0f} H{x2:.0f}"/>')
            parts.append(f'<text class="wl" x="{mx+2:.0f}" y="{y1-3:.0f}">{esc(("~" if inv else "")+b)}</text>')
    # input ports
    for p in in_ports:
        x, y = pos[p]
        parts.append(f'<circle cx="{x+8}" cy="{y+BH/2:.0f}" r="4" fill="#9aa7b4"/>')
        parts.append(f'<text class="port" x="{x+16}" y="{y+BH/2+3:.0f}">{esc(p)}</text>')
    # output ports
    for p in out_ports:
        x, y = pos[p]
        parts.append(f'<circle cx="{x+8}" cy="{y+BH/2:.0f}" r="4" fill="#7ee787"/>')
        parts.append(f'<text class="port" x="{x+16}" y="{y+BH/2+3:.0f}">{esc(p)}</text>')
    # cell boxes
    for ref, typ, _ in insts:
        x, y = pos[ref]
        fill = "#a5d6ff"
        if typ in blocks: fill = "#86b8e0"
        if typ in ("dff_d", "latch_d"): fill = "#7fb6e6"
        if typ == "cfgcell": fill = "#ffa657"
        parts.append(f'<rect class="bx" x="{x}" y="{y}" width="{BW}" height="{BH}" fill="{fill}"/>')
        parts.append(f'<text class="pt" x="{x+7}" y="{y+15}">{esc(ref)}</text>')
        parts.append(f'<text class="ps" x="{x+7}" y="{y+29}">{esc(typ)}</text>')
    return W, H, "\n".join(parts)

def gen_netlist_text(name, blk, prims, blocks):
    ports, insts = expand(blk)
    lines = [f'# {name}  —  {blk.get("spec","")}']
    pl = ", ".join(f'{n}{"" if d=="in" else "→"}' for n, d, k in ports)
    ins  = [n for n, d, k in ports if d == "in"]
    outs = [n for n, d, k in ports if d == "out"]
    lines.append(f'PORTS in: {", ".join(ins)}')
    lines.append(f'PORTS out: {", ".join(outs)}')
    for ref, typ, conn in insts:
        cs = " ".join(f'{p}={conn[p]}' for p in conn)
        lines.append(f'INST {ref:8s}: {typ:9s} {cs}')
    nets = blk.get("nets", [])
    if nets: lines.append(f'NET  {" ".join(nets)}')
    if blk.get("array"): lines.append(f'# array: {blk["array"]}')
    if not insts: lines.append('# STUB — decomposition pending (ports declared from spec)')
    return "\n".join(lines)

# ---------- emit ----------
def emit(lib):
    prims, blocks = lib["primitives"], lib["blocks"]
    # device.json (canonical netlist: expanded insts per block)
    dev = {"primitives": prims, "blocks": {}}
    for name, blk in blocks.items():
        ports, insts = expand(blk)
        dev["blocks"][name] = {
            "spec": blk.get("spec", ""), "group": blk.get("group", ""),
            "array": blk.get("array", ""),
            "abstract": bool(blk.get("abstract") or not blk.get("cells")),
            "ports": [{"name": n, "dir": d, "kind": k} for n, d, k in ports],
            "insts": [{"ref": r, "type": t, "conn": c} for r, t, c in insts],
            "nets": blk.get("nets", []),
        }
    with open(OUT_JSON, "w") as f: json.dump(dev, f, indent=2)

    # explorer.html (sidebar + auto-rendered schematic + generated netlist text)
    groups = {}
    for name, blk in blocks.items():
        groups.setdefault(blk.get("group", "blocks"), []).append(name)
    nav, views = [], []
    first = next(iter(blocks))
    for g, names in groups.items():
        nav.append(f'<h3>{esc(g)}</h3>')
        for nm in names:
            stub = bool(blocks[nm].get("abstract") or not blocks[nm].get("cells"))
            nav.append(f'<div class="item" data-id="{nm}" onclick="sel(\'{nm}\')">'
                       f'<span class="dot{" stub" if stub else ""}"></span>{esc(nm)}</div>')
    for name, blk in blocks.items():
        W, H, svg = render_svg(name, blk, prims, blocks)
        nl = esc(gen_netlist_text(name, blk, prims, blocks))
        on = " on" if name == first else ""
        views.append(f'''<div class="view{on}" id="v_{name}">
          <h2>{esc(name)}</h2><p class="desc">{esc(blk.get("desc",""))}
          &nbsp;<span class="spec">{esc(blk.get("spec",""))}</span></p>
          <div class="canvas"><svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">{svg}</svg></div>
          <div class="nl"><h4>generated netlist</h4><pre>{nl}</pre></div></div>''')
    doc = HTML_TMPL.replace("__NAV__", "\n".join(nav)).replace("__VIEWS__", "\n".join(views))\
                   .replace("__FIRST__", first).replace("__NB__", str(len(blocks)))
    with open(OUT_HTML, "w") as f: f.write(doc)

HTML_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>v3 device — generated</title>
<style>:root{--bg:#0e1116;--panel:#161b22;--panel2:#1c232c;--line:#2a323d;--txt:#e6edf3;--dim:#9aa7b4;--net:#7ee787;--accent:#4493f8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:13px/1.45 ui-monospace,Menlo,monospace}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
h1{font-size:16px;margin:0}.sub{color:var(--dim);font-size:12px}a.dl{background:#1f6feb;color:#fff;padding:7px 12px;border-radius:6px;text-decoration:none;font-size:12px}
.app{display:grid;grid-template-columns:230px 1fr;min-height:88vh}
nav{border-right:1px solid var(--line);padding:12px;overflow:auto}nav h3{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--dim);margin:14px 0 5px}
.item{padding:5px 9px;border-radius:6px;cursor:pointer;display:flex;gap:7px;align-items:center;font-size:12.5px}.item:hover{background:var(--panel2)}.item.on{background:#1f6feb33;border:1px solid var(--accent)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--net);flex:none}.dot.stub{background:var(--dim)}
main{padding:18px 22px;overflow:auto}.view{display:none}.view.on{display:block}.view h2{margin:0 0 2px;font-size:16px}
.desc{color:var(--dim);font-size:12.5px;margin:0 0 12px}.spec{color:var(--accent)}
.canvas{background:#0b0e13;border:1px solid var(--line);border-radius:9px;padding:8px;overflow:auto}
.nl{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:12px 14px;margin-top:12px}
.nl h4{margin:0 0 8px;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim)}
.nl pre{margin:0;white-space:pre;overflow-x:auto;color:#cbd5e1;font-size:12px;line-height:1.5}
.bx{rx:5;stroke:#0b0e13;stroke-opacity:.3}.pt{font:700 10px ui-monospace,monospace;fill:#0b0e13}
.ps{font:600 8.5px ui-monospace,monospace;fill:#0b0e13;opacity:.8}.w{stroke:var(--net);stroke-width:1.3;fill:none}
.wl{font:600 8px ui-monospace,monospace;fill:var(--net)}.port{font:700 9.5px ui-monospace,monospace;fill:#e6edf3}</style></head>
<body><header><div><h1>v3 device — generated from library.json</h1>
<div class="sub">__NB__ blocks · schematic + netlist auto-rendered by netc.py · nothing hand-drawn</div></div>
<a class="dl" href="device.json" download>Download device.json</a></header>
<div class="app"><nav>__NAV__</nav><main>__VIEWS__</main></div>
<script>function sel(id){document.querySelectorAll('.item').forEach(i=>i.classList.toggle('on',i.dataset.id===id));
document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on',v.id==='v_'+id))}
var q=new URLSearchParams(location.search).get('b');sel(q&&document.getElementById('v_'+q)?q:'__FIRST__');</script></body></html>"""

def main():
    try:
        with open(LIB) as f: lib = json.load(f)
    except Exception as e:
        print(f"netc: cannot read library.json: {e}"); return 2
    try:
        errs, warns = validate(lib)
    except Exception:
        traceback.print_exc(); return 2
    for w in warns: print(f"netc: WARN  {w}")
    if errs:
        print(f"netc: {len(errs)} VALIDATION ERROR(S):")
        for e in errs: print(f"  ✗ {e}")
        return 1
    try:
        emit(lib)
    except Exception:
        traceback.print_exc(); return 2
    nb = len(lib["blocks"])
    print(f"netc: OK — {nb} blocks validated + rendered -> explorer.html, device.json"
          + (f"  ({len(warns)} warning)" if warns else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
