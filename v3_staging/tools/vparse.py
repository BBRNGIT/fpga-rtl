#!/usr/bin/env python3
"""
vparse.py — Phase-2 parser: read the cached pages and extract each primitive's exact
PORTS + PARAMETERS from its Verilog Instantiation Template (the machine-readable spec
UG974 prints). Port directions/widths come from the 'Port Descriptions' lines in the
same cached page text. No PDF re-read, no find_tables. Re-runnable in milliseconds.

Output ug974_prims.json: {NAME: {ports:[{name,dir,width}], params:[{name,default}], spec}}.
The params map is exactly the Verilog `#(...)` block — the model for our C format's
attribute layer.

Usage: vparse.py [--cache cache/ug974.jsonl] [--out ug974_prims.json]
"""
import sys, os, re, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))

PAIR = re.compile(r'\.(\w+)\s*\(\s*([^()]*?)\s*\)')          # .NAME(VAL)
# Port Descriptions cells are newline-separated: NAME[<bus>] \n Direction \n Width
DESC = re.compile(r'\n([A-Za-z]\w*)(?:[<\[][\d:]+[>\]])?\s*\n(Input|Output|Inout)\s*\n(\d+)')

def _match(s, i):
    """i indexes a '(' -> index of its matching ')'. Robust for any template size."""
    depth = 0
    for k in range(i, len(s)):
        if s[k] == '(': depth += 1
        elif s[k] == ')':
            depth -= 1
            if depth == 0: return k
    return len(s)

def parse_template(vtext):
    """-> (module_name, params[(name,default)], port_names[]). Paren-matched split of
    the params block `#( ... )` from the port-map `( ... )` — works for 600-port GTYE4."""
    name = None
    for ln in vtext.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("//"): continue
        m = re.match(r'([A-Za-z_]\w*)', ln); name = m.group(1) if m else None; break
    if not name: return None, [], []
    i = vtext.find("#(")
    if i >= 0:
        j = _match(vtext, i + 1); params_txt = vtext[i + 2:j]; rest = vtext[j + 1:]
    else:
        params_txt, rest = "", vtext
    k = rest.find("(")
    ports_txt = rest[k + 1:_match(rest, k)] if k >= 0 else ""
    params = PAIR.findall(params_txt)
    seen = set(); ports = [n for n, _ in PAIR.findall(ports_txt) if not (n in seen or seen.add(n))]
    return name, params, ports

def run(cache, out):
    recs = [json.loads(l) for l in open(cache)]
    prims = {}
    for pi, rec in enumerate(recs):
        if "Verilog Instantiation Template" not in rec["text"]: continue
        # ONE primitive's template, bounded Verilog...->VHDL... (spans pages if long, but
        # the VHDL terminator stops it before the next primitive leaks in).
        acc = ""                                            # full template, even 600-port GTYE4
        for k in range(pi, min(len(recs), pi + 16)):
            acc += "\n" + recs[k]["text"]
            if "VHDL Instantiation" in acc: break
        vi = acc.find("Verilog Instantiation Template")
        vj = acc.find("VHDL Instantiation", vi)
        vseg = acc[vi + 30: vj if vj > 0 else len(acc)]
        name, params, ports = parse_template(vseg)
        if not name: continue
        pnames = {n for n, _ in params}
        ports = [p for p in ports if p not in pnames]      # params (INIT_*/IS_*) never leak as ports
        if not ports or name in prims: continue
        # directions/widths from this primitive's section pages (the table can be far from the template)
        desc_text = "\n".join(recs[k]["text"] for k in range(max(0, pi - 16), pi + 2))
        desc = DESC.findall(desc_text)
        dirs = {n: d.lower()[:3] for n, d, w in desc}
        wid  = {n: int(w) for n, d, w in desc}
        pl = []
        for p in ports:
            e = {"name": p, "dir": "out" if dirs.get(p, "") == "out" else "in"}
            if wid.get(p, 1) > 1: e["width"] = wid[p]
            pl.append(e)
        prims[name] = {"ports": pl,
                       "params": [{"name": n, "default": v} for n, v in params],
                       "spec": f"UG974 p{rec['page']}", "page": rec["page"]}
    json.dump(prims, open(out, "w"), indent=2)
    unisim = {k: v for k, v in prims.items() if not k.startswith("xpm_")}
    print(f"vparse: {len(prims)} templates -> {out}  ({len(unisim)} UNISIM, {len(prims)-len(unisim)} xpm macros)")
    for k in sorted(unisim):
        v = unisim[k]; ni = sum(1 for p in v["ports"] if p["dir"] == "in")
        print(f"  {k:18s} ports[{len(v['ports'])}] in/out={ni}/{len(v['ports'])-ni}  params[{len(v['params'])}]")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.path.join(HERE, "cache", "ug974.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "ug974_prims.json"))
    a = ap.parse_args()
    sys.exit(run(a.cache, a.out))
