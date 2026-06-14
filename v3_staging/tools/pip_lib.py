#!/usr/bin/env python3
"""
pip_lib.py — P3 interconnect realizer. The general routing fabric has no doc to extract
(Vivado-internal) — it is SYNTHESIZED from primitives, faithfully: a PIP is a
config-controlled connection (a mux selected by a config cell); a switch box / INT tile is a
crossbar of PIPs. Built from mux2 + cfgcell only. templates.py imports PIP_BLOCKS; assemble +
netc validate. Standalone (no templates import).
"""
def P(n, d, **kw): return {"name": n, "dir": d, **kw}
def G(ref, typ, **conn): return {"ref": ref, "type": typ, "conn": conn}

def int_tile(M=16, N=16):
    """INT tile = N outputs, each an M:1 PIP mux over the M tile inputs, config-selected.
    The config cells ARE the routing bits (the synthesized PIP database)."""
    c, nets = [], []
    sbits = (M - 1).bit_length()
    for o in range(N):
        sel = [f"s{o}_{b}" for b in range(sbits)]
        for b in range(sbits):
            c.append(G(f"cfg{o}_{b}", "cfgcell", Q=sel[b])); nets.append(sel[b])
        level = [f"IN[{i}]" for i in range(M)]
        for lv in range(sbits):
            nxt = []
            for j in range(0, len(level), 2):
                nm = f"t{o}_{lv}_{j//2}"
                b = level[j + 1] if j + 1 < len(level) else level[j]   # pad odd
                c.append(G(f"mx{o}_{lv}_{j//2}", "mux2", A=level[j], B=b, S=sel[lv], O=nm))
                nxt.append(nm); nets.append(nm)
            level = nxt
        c.append(G(f"ob{o}", "buf", A=level[0], O=f"OUT[{o}]"))
    return dict(group="Interconnect", spec="synthesized PIP switch box (config-mux crossbar)",
        ports=[P("IN", "in", width=M), P("OUT", "out", width=N)], cells=c, nets=nets)

def clk_root():
    """clock distribution root: a config-selected source onto a clock spine (UG572 routing
    vs distribution tracks). A PIP onto the global clock net."""
    return dict(group="Interconnect", spec="UG572 clock root (routing->distribution PIP)",
        ports=[P("CLKIN", "in", width=24), P("CLKOUT", "out")],
        cells=[G(f"cfg{b}", "cfgcell", Q=f"s{b}") for b in range(5)] +
              [G("ob", "buf", A="IN_sel", O="CLKOUT")],
        nets=[f"s{b}" for b in range(5)] + ["IN_sel"])

PIP_BLOCKS = {"INT_TILE": int_tile}
