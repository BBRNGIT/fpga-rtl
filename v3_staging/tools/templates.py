"""
templates.py — decomposition generators for the v3 clocking library.

Each builder returns a full block dict {ports, cells, nets, spec, group} with the
gate-level decomposition encoded ONCE in Python (cleaner than JSON `gen`). assemble.py
calls these and cross-checks the ports against specgen's PDF extraction. To add a
primitive: write a builder + register it in BLOCKS. No hand-edited JSON.
"""

def G(ref, typ, **conn): return {"ref": ref, "type": typ, "conn": conn}
def P(name, d, **kw):     return {"name": name, "dir": d, **kw}
CLK = "clock"

# ---- base gate composition ----
def mux2():
    return dict(group="Tier-0 compositions", spec="O=(A&~S)|(B&S)",
        ports=[P("A","in"),P("B","in"),P("S","in"),P("O","out")],
        cells=[G("not_s","not",A="S",O="Sn"),G("and_a","and",A="A",B="Sn",O="na"),
               G("and_b","and",A="B",B="S",O="nb"),G("or_o","or",A="na",B="nb",O="O")],
        nets=["Sn","na","nb"])

# ---- BUFGCTRL: glitchless 2:1 clock select (UG572 Fig 2-5) ----
def bufgctrl():
    return dict(group="Clock management", spec="UG572 Fig 2-5",
        array="24 BUFGCE + 8 BUFGCTRL + 4 BUFGCE_DIV / clock region",
        ports=[P("I0","in",kind=CLK),P("I1","in",kind=CLK),P("S0","in"),P("S1","in"),
               P("CE0","in"),P("CE1","in"),P("IGNORE0","in"),P("IGNORE1","in"),P("O","out",kind=CLK)],
        # the latch gate is driven by the INVERSE of the clock input: emit an explicit
        # `not` cell (ni0/ni1) rather than the "~I0" shorthand, so every net has a real
        # driver (C02 single-driver / no-floating; the inverter is a real silicon gate).
        cells=[G("ni0","not",A="I0",O="ni0"),
               G("and0","and",A="S0",B="CE0",O="g0"),G("lat0","latch_d",D="g0",G="ni0",Q="l0"),
               G("ig0","mux2",A="l0",B="g0",S="IGNORE0",O="sel0"),G("a0","and",A="I0",B="sel0",O="a0n"),
               G("ni1","not",A="I1",O="ni1"),
               G("and1","and",A="S1",B="CE1",O="g1"),G("lat1","latch_d",D="g1",G="ni1",Q="l1"),
               G("ig1","mux2",A="l1",B="g1",S="IGNORE1",O="sel1"),G("a1","and",A="I1",B="sel1",O="a1n"),
               G("oro","or",A="a0n",B="a1n",O="O")],
        nets=["ni0","g0","l0","sel0","a0n","ni1","g1","l1","sel1","a1n"])

# ---- glitchless gated buffer: BUFGCE / BUFCE_LEAF (UG572 Fig 2-18, Table 2-5/2-7) ----
def gated_buffer(spec):
    return dict(group="Clock management", spec=spec,
        ports=[P("I","in",kind=CLK),P("CE","in"),P("O","out",kind=CLK)],
        cells=[G("n_i","not",A="I",O="ni"),G("lat","latch_d",D="CE",G="ni",Q="ceg"),
               G("ao","and",A="I",B="ceg",O="O")], nets=["ni","ceg"])

# ---- pass buffers: BUFG (=BUFGCE,CE=1) / BUFG_PS (=buf) ----
def buf_via_bufgce(spec):
    return dict(group="Clock management", spec=spec,
        ports=[P("I","in",kind=CLK),P("O","out",kind=CLK)],
        cells=[G("bg","BUFGCE",I="I",CE="1",O="O")], nets=[])
def buf_pass(spec):
    return dict(group="Clock management", spec=spec,
        ports=[P("I","in",kind=CLK),P("O","out",kind=CLK)],
        cells=[G("b","buf",A="I",O="O")], nets=[])

# ---- BUFGCTRL configurations: BUFGCE_1 / BUFGMUX / BUFGMUX_1 / BUFGMUX_CTRL ----
def bufgce_1(spec):
    return dict(group="Clock management", spec=spec,
        ports=[P("I","in",kind=CLK),P("CE","in"),P("O","out",kind=CLK)],
        cells=[G("bc","BUFGCTRL",I0="I",I1="1",S0="1",S1="0",CE0="CE",CE1="0",
                 IGNORE0="0",IGNORE1="1",O="O")], nets=[])  # IGNORE1=VDD per UG572 Fig 2-7 (figdiff-confirmed)
def bufgmux(spec, use_s):
    # use_s True -> S pins (BUFGMUX_CTRL); False -> CE pins (BUFGMUX/_1)
    ce = ("1","1") if use_s else ("nsv","S")
    s  = ("nsv","S") if use_s else ("1","1")
    ce0, ce1 = (s if use_s else ce)  # noqa (clarity)
    return dict(group="Clock management", spec=spec,
        ports=[P("I0","in",kind=CLK),P("I1","in",kind=CLK),P("S","in"),P("O","out",kind=CLK)],
        cells=[G("ns","not",A="S",O="nsv"),
               G("bc","BUFGCTRL",I0="I0",I1="I1",S0=s[0],S1=s[1],CE0=ce[0],CE1=ce[1],
                 IGNORE0="0",IGNORE1="0",O="O")], nets=["nsv"])

# ---- BUFG_GT_SYNC: 2-stage CE/CLR synchronizer (UG572 Fig 2-21) ----
def bufg_gt_sync():
    return dict(group="Clock management", spec="UG572 Fig 2-21",
        ports=[P("CLK","in",kind=CLK),P("CE","in"),P("CLR","in"),P("CESYNC","out"),P("CLRSYNC","out")],
        cells=[G("ce0","dff_d",D="CE",CLK="CLK",Q="ce_s0"),G("ce1","dff_d",D="ce_s0",CLK="CLK",Q="CESYNC"),
               G("clr0","dff_d",D="CLR",CLK="CLK",Q="clr_s0"),G("clr1","dff_d",D="clr_s0",CLK="CLK",Q="CLRSYNC")],
        nets=["ce_s0","clr_s0"])

# ---- div_prog: programmable integer divider ÷1..128 (UG572 Eq 3-1/3-2) ----
def divider():
    c = []
    for i in range(7): c.append(G(f"cfg_{i}","cfgcell",Q=f"DIVCFG[{i}]"))
    for i in range(7): c.append(G(f"eq_{i}","xnor",A=f"Q[{i}]",B=f"DIVCFG[{i}]",O=f"eq[{i}]"))
    for i in range(1,7):
        c.append(G(f"tc_{i}","and",A=("eq[0]" if i==1 else f"tc[{i-1}]"),B=f"eq[{i}]",O=f"tc[{i}]"))
    c += [G("rsto","or",A="RST",B="tc[6]",O="rst_eff"), G("nrst","not",A="rst_eff",O="nrst")]
    for i in range(1,7):
        c.append(G(f"cin_{i}","and",A=("1" if i==1 else f"cin[{i-1}]"),B=f"Q[{i-1}]",O=f"cin[{i}]"))
    for i in range(7):
        c.append(G(f"xr_{i}","xor",A=f"Q[{i}]",B=("1" if i==0 else f"cin[{i}]"),O=f"nxt[{i}]"))
    for i in range(7): c.append(G(f"da_{i}","and",A=f"nxt[{i}]",B="nrst",O=f"d[{i}]"))
    for i in range(7): c.append(G(f"ff_{i}","dff_d",D=f"d[{i}]",CLK="CLK",Q=f"Q[{i}]"))
    c += [G("otog","xor",A="O",B="tc[6]",O="otog"), G("off","dff_d",D="otog",CLK="CLK",Q="O")]
    return dict(group="Clock management", spec="UG572 Eq 3-1/3-2 (M/D/O counters)",
        ports=[P("CLK","in",kind=CLK),P("RST","in"),P("O","out",kind=CLK)], cells=c,
        nets=["Q","eq","tc","cin","nxt","d","rst_eff","nrst","otog"])

def bufgce_div():
    return dict(group="Clock management", spec="UG572 Table 2-8",
        array="4 BUFGCE_DIV / clock region",
        ports=[P("I","in",kind=CLK),P("CE","in"),P("CLR","in"),P("O","out",kind=CLK)],
        cells=[G("gate","BUFGCE",I="I",CE="CE",O="gi"),G("dv","div_prog",CLK="gi",RST="CLR",O="O")],
        nets=["gi"])

def bufg_gt():
    return dict(group="Clock management", spec="UG572 Fig 2-21",
        array="24 BUFG_GT + 14 BUFG_GT_SYNC / GT Quad (UltraScale+)",
        ports=[P("I","in",kind=CLK),P("CE","in"),P("CEMASK","in"),P("CLR","in"),
               P("CLRMASK","in"),P("DIV","in",width=3),P("O","out",kind=CLK)],
        cells=[G("cem","or",A="CE",B="CEMASK",O="ce_eff"),G("ncm","not",A="CLRMASK",O="nclrm"),
               G("clm","and",A="CLR",B="nclrm",O="clr_eff"),
               G("sync","BUFG_GT_SYNC",CLK="I",CE="ce_eff",CLR="clr_eff",CESYNC="cesync",CLRSYNC="clrsync"),
               G("gate","BUFGCE",I="I",CE="cesync",O="gi"),G("dv","div_prog",CLK="gi",RST="clrsync",O="O")],
        nets=["ce_eff","nclrm","clr_eff","cesync","clrsync","gi"])

# ---- CMT: MMCM/PLL loop + dividers, built from the output port list ----
import re
def cmt(name, ports, spec, array, clkin):
    out = [p["name"] for p in ports if p["dir"]=="out"]
    c = [G("dd","div_prog",CLK=clkin,RST="RST",O="clkin_d"),
         G("pf","pfd",CLKREF="clkin_d",CLKFB="CLKFBIN",UP="up",DN="dn"),
         G("cp","charge_pump",UP="up",DN="dn",VCTRL="vctrl"),
         G("vc","vco",VCTRL="vctrl",CLK="vcoclk")]
    nets=["clkin_d","up","dn","vctrl","vcoclk"]
    if "LOCKED" in out: c.append(G("ld","lock_det",UP="up",DN="dn",LOCKED="LOCKED"))
    for o in out:
        if o=="CLKFBOUT": c.append(G("mm","div_prog",CLK="vcoclk",RST="RST",O=o))
        elif re.match(r"CLKOUT\d+$",o): c.append(G(f"o{o[6:]}","div_prog",CLK="vcoclk",RST="RST",O=o))
    for o in out:
        m=re.match(r"(CLKOUT\d+|CLKFBOUT)B$",o)
        if m: c.append(G("b_"+o,"not",A=m.group(1),O=o))
    if "CLKOUTPHY" in out:
        c.append(G("op","div_prog",CLK="vcoclk",RST="RST",O="phyraw")); nets.append("phyraw")
        c.append(G("pg","and",A="phyraw",B="CLKOUTPHYEN",O="CLKOUTPHY"))
    return dict(group="Clock management", spec=spec, array=array, ports=ports, cells=c, nets=nets)

# canonical ports for the CMT blocks (verified vs UG974; specgen cross-checks vs PDF)
def _cmt_ports(clkin, outs, extra_in=()):
    ins=[P(clkin,"in",kind=CLK),P("CLKFBIN","in",kind=CLK),P("RST","in"),P("PWRDWN","in")]+\
        [P(x,"in") for x in extra_in]
    return ins+[P(o,"out",kind=CLK) if o!="LOCKED" else P("LOCKED","out") for o in outs]

def mmcme4_base():
    outs=["CLKOUT0","CLKOUT1","CLKOUT2","CLKOUT3","CLKOUT4","CLKOUT5","CLKOUT6",
          "CLKOUT0B","CLKOUT1B","CLKOUT2B","CLKOUT3B","CLKFBOUT","CLKFBOUTB","LOCKED"]
    return cmt("MMCME4_BASE", _cmt_ports("CLKIN1",outs), "UG572 Fig 3-2/Table 3-1 (UG974 MMCME4_BASE)",
               "1 MMCM / CMT", "CLKIN1")

def plle4_base():
    outs=["CLKOUT0","CLKOUT0B","CLKOUT1","CLKOUT1B","CLKFBOUT","CLKOUTPHY","LOCKED"]
    return cmt("PLLE4_BASE", _cmt_ports("CLKIN",outs,extra_in=("CLKOUTPHYEN",)),
               "UG974 PLLE4_BASE", "2 PLL / CMT", "CLKIN")

# stub: ports-only (decomposition needs a source we don't have, e.g. DRP map = XAPP888)
def stub(name, ports, spec, note):
    return dict(group="Clock management", spec=spec, abstract=True, ports=ports, note=note)

def mmcme4_adv():
    ins=["CLKIN1","CLKIN2","CLKFBIN","DCLK","PSCLK"]
    cin=["RST","PWRDWN","CLKINSEL","DWE","DEN","PSINCDEC","PSEN","CDDCREQ"]
    ports=[P(x,"in",kind=CLK) for x in ins]+[P(x,"in") for x in cin]+\
          [P("DADDR","in",width=7),P("DI","in",width=16),
           P("CLKOUT0","out",kind=CLK),P("CLKOUT1","out",kind=CLK),P("CLKOUT2","out",kind=CLK),
           P("CLKOUT3","out",kind=CLK),P("CLKOUT4","out",kind=CLK),P("CLKOUT5","out",kind=CLK),
           P("CLKOUT6","out",kind=CLK),P("CLKOUT0B","out",kind=CLK),P("CLKOUT1B","out",kind=CLK),
           P("CLKOUT2B","out",kind=CLK),P("CLKOUT3B","out",kind=CLK),P("CLKFBOUT","out",kind=CLK),
           P("CLKFBOUTB","out",kind=CLK),P("LOCKED","out"),P("DO","out",width=16),P("DRDY","out"),
           P("PSDONE","out"),P("CLKINSTOPPED","out"),P("CLKFBSTOPPED","out"),P("CDDCDONE","out")]
    return stub("MMCME4_ADV", ports, "UG572 Table 3-2/3-3",
                "DRP register-map = XAPP888 (not in UG572); phase-shift interpolator pending")

# registry: canonical name -> builder. assemble.py emits exactly these blocks.
BLOCKS = {
    "mux2": mux2,
    "BUFGCTRL": bufgctrl,
    "BUFGCE": lambda: gated_buffer("UG572 Fig 2-18/Table 2-5"),
    "BUFCE_LEAF": lambda: gated_buffer("UG572 Table 2-7"),
    "BUFG": lambda: buf_via_bufgce("UG572 Fig 2-20"),
    "BUFG_PS": lambda: buf_pass("UG572 p34"),
    "BUFGCE_1": lambda: bufgce_1("UG572 Table 2-1/Fig 2-7"),
    "BUFGMUX": lambda: bufgmux("UG572 Fig 2-9", use_s=False),
    "BUFGMUX_1": lambda: bufgmux("UG572 Fig 2-11", use_s=False),
    "BUFGMUX_CTRL": lambda: bufgmux("UG572 Fig 2-12", use_s=True),
    "BUFG_GT_SYNC": bufg_gt_sync,
    "div_prog": divider,
    "BUFGCE_DIV": bufgce_div,
    "BUFG_GT": bufg_gt,
    "MMCME4_BASE": mmcme4_base,
    "PLLE4_BASE": plle4_base,
    # MMCME4_ADV / PLLE4_ADV now come from blocks/*.json (composed: BASE + clock_switch + drp + phase_shift)
}

# P1 physical-element realizers (UG574-grounded CLB elements) — see phys_lib.py / configmap.json
try:
    from phys_lib import PHYS_BLOCKS
    BLOCKS.update(PHYS_BLOCKS)
except Exception as _e:
    pass

# P3 interconnect: synthesized PIP switch box (no doc — built from primitives) — see pip_lib.py
try:
    from pip_lib import PIP_BLOCKS
    BLOCKS.update(PIP_BLOCKS)
except Exception:
    pass
