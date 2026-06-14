#!/usr/bin/env python3
"""
phys_lib.py — P1 realizer: decomposition builders for the CLB PHYSICAL fabric elements
(UG574-grounded). These emit ONE builder per physical element; the catalogue configs
(LUT1-6/RAM*/SRL*, MUXF7/8/9, FDRE/FDSE/…) are CONFIGURATIONS of these (see configmap.json),
never separate netlists. templates.py imports PHYS_BLOCKS; assemble.py emits them into
library.json; netc.py validates. Standalone (no templates import) to avoid a cycle.
"""
def P(n, d, **kw): return {"name": n, "dir": d, **kw}
def G(ref, typ, **conn): return {"ref": ref, "type": typ, "conn": conn}

# MUXF7/8/9 — a 2:1 select mux (UG574: dedicated wide-function muxes between LUT outputs)
def muxf(spec):
    return dict(group="CLB logic", spec=spec,
        ports=[P("I0", "in"), P("I1", "in"), P("S", "in"), P("O", "out")],
        cells=[G("m", "mux2", A="I0", B="I1", S="S", O="O")], nets=[])

# CARRY8 — ripple carry chain: per bit O=S^Cin, CO=MUXCY(S? Cin : DI). CI_TOP feeds bit-4
# carry in the split (two-CARRY4) mode, selected by a config cell (UG574).
def carry8():
    c = [G("split", "cfgcell", Q="SPLIT"),
         G("topmux", "mux2", A="co[3]", B="CI_TOP", S="SPLIT", O="ci4")]
    cin = lambda i: "CI" if i == 0 else "ci4" if i == 4 else f"co[{i-1}]"
    for i in range(8):
        c.append(G(f"x{i}", "xor", A=f"S[{i}]", B=cin(i), O=f"O[{i}]"))
        c.append(G(f"m{i}", "mux2", A=f"DI[{i}]", B=cin(i), S=f"S[{i}]", O=f"co[{i}]"))
        c.append(G(f"cob{i}", "buf", A=f"co[{i}]", O=f"CO[{i}]"))
    return dict(group="CLB logic", spec="UG574 CARRY8 (MUXCY+XOR ripple; CI_TOP split)",
        ports=[P("CI", "in"), P("CI_TOP", "in"), P("DI", "in", width=8), P("S", "in", width=8),
               P("O", "out", width=8), P("CO", "out", width=8)],
        cells=c, nets=["co", "ci4", "SPLIT"])

# LUT6 — a 64-bit SRAM (INIT config cells) read by a 6-level 2:1 mux tree on I0..I5.
# A LUT IS a configurable SRAM+mux; LUT1-5/RAM*/SRL* are this element in narrower/other modes.
def lut6():
    c = [G(f"i{k}", "cfgcell", Q=f"INIT[{k}]") for k in range(64)]
    level = [f"INIT[{k}]" for k in range(64)]
    for lv in range(6):
        nxt = []
        for j in range(0, len(level), 2):
            o = f"n{lv}_{j//2}"
            c.append(G(f"mx{lv}_{j//2}", "mux2", A=level[j], B=level[j+1], S=f"I{lv}", O=o))
            nxt.append(o)
        level = nxt
    c.append(G("outb", "buf", A=level[0], O="O"))
    nets = ["INIT"] + [f"n{lv}_{j}" for lv in range(6) for j in range(2 ** (5 - lv))]
    return dict(group="CLB logic", spec="UG574 LUT6 = 64-bit INIT SRAM + 6-level 2:1 mux tree",
        ports=[P(f"I{k}", "in") for k in range(6)] + [P("O", "out")], cells=c, nets=nets)

PHYS_BLOCKS = {
    "MUXF7": lambda: muxf("UG574 MUXF7 (2:1)"),
    "MUXF8": lambda: muxf("UG574 MUXF8 (2:1)"),
    "MUXF9": lambda: muxf("UG574 MUXF9 (2:1)"),
    "CARRY8": carry8,
    "LUT6": lut6,
}
