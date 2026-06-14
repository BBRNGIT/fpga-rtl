#!/usr/bin/env python3
"""
figdiff.py — Tool: DIFF figure-extracted connections (figparse) vs the template
decomposition, per config figure. Turns "is it as accurate as spec?" into a
measured score: for each tie the template asserts (e.g. BUFGCE_1: I0=I, S0=VDD),
check the figure shows it. Reports confirmed / total + the specific gaps.

This is the connection-level observational checkpoint. Exit 0 always (report),
2 internal error.
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import templates as T

FIG = os.path.join(HERE, "figparse_out.json")
# config block  ->  figure id in figparse_out.json
FIG_MAP = {"BUFGCE_1": "p20:Fig2-7", "BUFGMUX": "p21:Fig2-9", "BUFGMUX_CTRL": "p24:Fig2-12"}

def template_ties(block):
    """from a config block's cells -> {bufgctrl_pin: expected}, where expected is
    '1'/'0' (VDD/GND), a port name, or ('~', net) for an inverted tie."""
    cells = block.get("cells", [])
    inv_src = {c["conn"]["O"]: c["conn"]["A"] for c in cells if c["type"] == "not"}
    bc = next((c for c in cells if c["type"] == "BUFGCTRL"), None)
    if not bc: return {}
    ties = {}
    for pin, v in bc["conn"].items():
        if pin == "O": continue
        if v in inv_src:        ties[pin] = ("~", inv_src[v])
        else:                   ties[pin] = v
    return ties

def figure_facts(fig):
    """-> (same: list of label-sets, tie: {label:const}, inv: list of (outset,inset))"""
    same, tie, inv = [], {}, []
    for g in fig.get("nets", []):
        s = set(g["net"]); same.append(s)
        if g.get("tie"):
            for lb in s:
                if lb in ("VDD", "GND", "VCC", "VSS"): continue
                tie[lb] = g["tie"][0]
    for iv in fig.get("inverters", []):
        inv.append((set(iv["out"]), set(iv["in"])))
    return same, tie, inv

def same_net(a, b, same):
    return any(a in s and b in s for s in same)

def check(block, fig):
    ties = template_ties(block)
    same, tie, inv = figure_facts(fig)
    ok, miss = [], []
    for pin, exp in ties.items():
        if isinstance(exp, tuple):                       # inverted tie: pin = ~src
            src = exp[1]
            hit = any(pin in o and src in i for o, i in inv) or \
                  any(pin in o and src in i for o, i in inv)
            (ok if hit else miss).append(f"{pin}=~{src}")
        elif exp in ("0", "1"):                           # VDD/GND tie
            hit = tie.get(pin) == exp
            (ok if hit else miss).append(f"{pin}={'VDD' if exp=='1' else 'GND'}")
        else:                                             # pin = external port
            hit = same_net(pin, exp, same) or pin == exp
            (ok if hit else miss).append(f"{pin}={exp}")
    return ok, miss

def run():
    if not os.path.exists(FIG):
        print("figdiff: no figparse_out.json (run figparse first)"); return 0
    figs = json.load(open(FIG))
    tot_ok = tot = 0
    results = {}
    print("figdiff: figure connections vs template decomposition")
    for blk_name, fid in FIG_MAP.items():
        if fid not in figs:
            print(f"  {blk_name:14s} (figure {fid} not extracted)"); continue
        block = T.BLOCKS[blk_name]()
        ok, miss = check(block, figs[fid])
        tot_ok += len(ok); tot += len(ok) + len(miss)
        results[blk_name] = {"fig": fid, "confirmed": ok, "gaps": miss}
        status = "✓ MATCH" if not miss else f"{len(ok)}/{len(ok)+len(miss)}"
        print(f"  {blk_name:14s} {fid:12s} {status:8s} confirmed: {', '.join(ok) or '-'}")
        if miss: print(f"  {'':14s} {'':12s} {'':8s} gaps:      {', '.join(miss)}")
    print(f"figdiff: {tot_ok}/{tot} template ties confirmed by the figures")
    json.dump({"total_ok": tot_ok, "total": tot, "blocks": results},
              open(os.path.join(HERE, "figdiff_out.json"), "w"), indent=2)
    return 0

if __name__ == "__main__":
    try: sys.exit(run())
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(2)
