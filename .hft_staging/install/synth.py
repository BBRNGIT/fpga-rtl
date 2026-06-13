#!/usr/bin/env python3
"""synth.py — the CELL-LEVEL SILICON SYNTHESIZER (all-CLB bit-blast).

Takes a module netlist of 64-bit word cells and synthesizes it onto the real
fabric exactly as an FPGA tool would: bit-blast every word to 64 bits, decompose
every cell into bit-level gates (booleans -> 1 LUT; addsub -> ripple-carry FA
LUTs; shifts -> rewiring), technology-map each bit-gate to a LUT6 (truth table),
map every word register to 64 FF BELs, place into CLB tiles, and emit a loader
that evaluates the placed LUT/FF netlist in the fabric. Nothing hand-coded; the
blank is never edited (runtime register writes only).

Semantics matched to cells/cells.h exactly:
  addsub(a,b,sub): bm=b^(-sub); cin0=sub; ripple cell_fa; out=sum bits.
  sar(a,n): out_i = a_{i+n} (i+n<64) else sign(a_63).   shl(a,n): out_i=a_{i-n} else 0.
  mux(a,b,sel): out_i = sel_0 ? b_i : a_i.   eqmask(a,b): out_0=AND_i(a_i==b_i), else 0.
  and/or/xor/not/buf/gate: per bit.

Usage: python3 synth.py <module.net.json> <start_tile> > <module>.cell.config.json
       (then synth emits gen/<module>_synth_load.h + gen/<module>_synth_verify.c)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
FAB = os.path.join(ROOT, "fpga")
GEN = os.path.join(HERE, "gen")
W = 64


def die(m): sys.stderr.write("synth: " + m + "\n"); sys.exit(2)


def defines(path):
    import re
    d = {}
    for ln in open(path):
        m = re.search(r"#define\s+(\w+)\s+(\d+)u", ln)
        if m:
            d[m.group(1)] = int(m.group(2))
    return d


# ---- bit-level boolean functions (for truth-table computation) --------------
def f_and(x): return x[0] & x[1]
def f_or(x):  return x[0] | x[1]
def f_xor(x): return x[0] ^ x[1]
def f_xnor(x): return 1 - (x[0] ^ x[1])
def f_not(x): return x[0] ^ 1
def f_mux(x): return x[1] if x[2] else x[0]          # (a,b,sel) -> sel?b:a
def f_fa_sum(x): return x[0] ^ x[1] ^ x[2]
def f_fa_carry(x): return (x[0] & x[1]) | (x[2] & (x[0] ^ x[1]))


def truth_table(fn, n):
    tt = 0
    for idx in range(64):
        bits = [(idx >> k) & 1 for k in range(n)]
        if fn(bits):
            tt |= (1 << idx)
    return tt


def main():
    if len(sys.argv) != 3:
        die("usage: synth.py <module.net.json> <start_tile> > config.json")
    net = json.load(open(sys.argv[1]))
    start_tile = int(sys.argv[2])
    mod = net.get("device", "mod")
    sdef = defines(os.path.join(FAB, "clb_slice_gen.h"))

    inputs = [n["name"] for n in net.get("config_nodes", [])]
    dffs = net.get("dff_nodes", [])
    combs = net.get("comb_nodes", [])
    consts = net.get("const_nodes", [])     # fixed-value words referenced by cells/dffs
    dff_names = {d["name"] for d in dffs}

    CONST0, CONST1 = "$const0", "$const1"
    gates = []          # {out, ins:[bitsig...], tt}  (each bit-gate -> a LUT6)
    alias = {}          # bitsig -> source bitsig (pure routing, no LUT)

    def bit(node, i):
        return f"{node}#{i}"

    # bit i of an input WORD-node, following the cell graph (config/dff = leaves;
    # comb outputs are produced below in topo order before they're consumed).
    def src(node, i):
        return bit(node, i)

    def add_gate(out, ins, fn):
        gates.append({"out": out, "ins": ins, "tt": truth_table(fn, len(ins))})

    # leaves: config inputs and dff outputs are primary bitsigs (set by loader)
    # comb_nodes come topo-sorted from the elaborator; bit-blast each in order.
    for c in combs:
        cell, name, ci = c["cell"], c["name"], c["inputs"]
        if cell in ("buf",):
            for i in range(W): alias[bit(name, i)] = src(ci[0], i)
        elif cell == "not":
            for i in range(W): add_gate(bit(name, i), [src(ci[0], i)], f_not)
        elif cell in ("and", "or", "xor"):
            fn = {"and": f_and, "or": f_or, "xor": f_xor}[cell]
            for i in range(W): add_gate(bit(name, i), [src(ci[0], i), src(ci[1], i)], fn)
        elif cell == "eqmask":
            eqs = []
            for i in range(W):
                e = f"{name}#eq{i}"
                add_gate(e, [src(ci[0], i), src(ci[1], i)], f_xnor); eqs.append(e)
            # AND-reduce all 64 equalities -> bit 0; higher bits are 0
            lvl = eqs; r = 0
            while len(lvl) > 1:
                nxt = []
                for k in range(0, len(lvl), 2):
                    if k + 1 < len(lvl):
                        o = f"{name}#and{r}_{k}"
                        add_gate(o, [lvl[k], lvl[k + 1]], f_and); nxt.append(o)
                    else:
                        nxt.append(lvl[k])
                lvl = nxt; r += 1
            if int(c.get("invert", 0)):              # cell_eqmask(...) ^ 1
                add_gate(bit(name, 0), [lvl[0]], f_not)
            else:
                alias[bit(name, 0)] = lvl[0]
            for i in range(1, W): alias[bit(name, i)] = CONST0
        elif cell == "gate":
            # out_i = en0 ? val_i : 0  == and(val_i, en0)
            for i in range(W): add_gate(bit(name, i), [src(ci[0], i), src(ci[1], 0)], f_and)
        elif cell == "mux":
            for i in range(W): add_gate(bit(name, i), [src(ci[0], i), src(ci[1], i), src(ci[2], 0)], f_mux)
        elif cell == "addsub":
            sub = int(c.get("sub", 0)) & 1
            shr = int(c.get("shift_right", 0))            # gennet: cell_sar(cell_addsub(...), shr)
            carry = CONST1 if sub else CONST0
            sumbit = (lambda i: bit(name, i)) if shr == 0 else (lambda i: f"{name}#s{i}")
            for i in range(W):
                ai = src(ci[0], i)
                bi = src(ci[1], i)
                if sub:                                   # bm = ~b
                    bn = f"{name}#bn{i}"; add_gate(bn, [bi], f_not); bi = bn
                add_gate(sumbit(i), [ai, bi, carry], f_fa_sum)
                if i < W - 1:
                    co = f"{name}#c{i+1}"
                    add_gate(co, [ai, bi, carry], f_fa_carry); carry = co
            if shr:                                        # arithmetic shift right (sign-fill from sum bit 63)
                for i in range(W):
                    alias[bit(name, i)] = sumbit(i + shr) if i + shr < W else sumbit(W - 1)
        elif cell == "cmp_lt":
            # a<b (unsigned) via a + ~b + 1 carry chain; result = NOT(final carry).
            carry = CONST1
            for i in range(W):
                ai = src(ci[0], i)
                bn = f"{name}#nb{i}"; add_gate(bn, [src(ci[1], i)], f_not)
                co = f"{name}#c{i+1}"
                add_gate(co, [ai, bn, carry], f_fa_carry); carry = co
            add_gate(bit(name, 0), [carry], f_not)        # 1 iff no carry-out == a<b
            for i in range(1, W): alias[bit(name, i)] = CONST0
        elif cell in ("sar", "shl"):
            n = int(c.get("shift_right", c.get("shift", 0)))
            for i in range(W):
                if cell == "shl":
                    alias[bit(name, i)] = src(ci[0], i - n) if i - n >= 0 else CONST0
                else:  # sar: sign-fill from bit 63
                    alias[bit(name, i)] = src(ci[0], i + n) if i + n < W else src(ci[0], W - 1)
        else:
            die(f"cell '{cell}' not handled by the synthesizer")

    # resolve aliases (transitively) on every gate input + final references
    def resolve(b):
        seen = 0
        while b in alias:
            b = alias[b]; seen += 1
            if seen > 1000: die(f"alias cycle at {b}")
        return b
    for g in gates:
        g["ins"] = [resolve(b) for b in g["ins"]]

    # mem-flagged dffs are addressed RAM storage -> BRAM cells (NOT CLB FF BELs);
    # only their write decode/feed stays in LUT fabric. ff_dffs are normal CLB FFs.
    ff_dffs = [d for d in dffs if not d.get("mem")]
    mem_dffs = [d for d in dffs if d.get("mem")]

    # ---- placement: pack bit-gates (8 LUT/tile) + bit-FFs (16 FF/tile) -------
    n_lut_tiles = (len(gates) + 7) // 8
    n_ff = len(ff_dffs) * W
    n_ff_tiles = (n_ff + 15) // 16
    tiles = list(range(start_tile, start_tile + n_lut_tiles + n_ff_tiles))
    lut_at = {}     # gate index -> (tile, slot)
    for gi in range(len(gates)):
        lut_at[gi] = (tiles[gi // 8], gi % 8)
    out_of = {gates[gi]["out"]: gi for gi in range(len(gates))}
    ff_at = {}      # (dff_name,bit) -> (tile, slot)
    fbase = n_lut_tiles
    fi = 0
    for d in ff_dffs:
        for i in range(W):
            ff_at[(d["name"], i)] = (tiles[fbase + fi // 16], fi % 16); fi += 1

    # ---- memory -> BRAM cells -----------------------------------------------
    # (a) shift-in history record store (Law #10): each (slot,field) word = 1 cell.
    # (b) mem-flagged dffs (addressed RAM word) = 1 cell each. Both are stored in
    # fpga_bram; their write enables/feeds are ordinary fabric cells.
    bdef = defines(os.path.join(FAB, "bram_block_gen.h"))
    BRAM_CELLS = 576
    hist = net.get("history_ring")
    hist_words = []     # ordered: {reg, slot, field, source}
    hplace = {}         # (slot, field) -> (bram_tile, cell_slot)
    mem_at = {}         # mem dff name -> (bram_tile, cell_slot)
    cell_seq = 0
    if hist:
        depth = hist["depth"]; flds = hist["fields"]
        for s in range(depth):
            for fld in flds:
                hist_words.append({"reg": f"{hist['name']}_{s}_{fld['name']}",
                                   "slot": s, "field": fld["name"], "source": fld["source"]})
    for hw in hist_words:
        hplace[(hw["slot"], hw["field"])] = (cell_seq // BRAM_CELLS, cell_seq % BRAM_CELLS); cell_seq += 1
    for d in mem_dffs:
        mem_at[d["name"]] = (cell_seq // BRAM_CELLS, cell_seq % BRAM_CELLS); cell_seq += 1
    n_bram = (cell_seq + BRAM_CELLS - 1) // BRAM_CELLS
    # addressed RAM -> one BRAM tile per lane (slot = cell offset; depth <= 576).
    # No fabric decode: the runtime index drives the BRAM cell offset (address port).
    ram = net.get("ram")
    ram_lane_tile = {}     # lane name -> bram tile
    if ram:
        if ram["depth"] > BRAM_CELLS:
            die(f"ram depth {ram['depth']} exceeds BRAM tile capacity {BRAM_CELLS}")
        for li, ln in enumerate(ram["lanes"]):
            ram_lane_tile[ln["name"]] = n_bram + li
        n_bram += len(ram["lanes"])
    bram_tiles = list(range(n_bram))

    cfg = {"mode": "cell_synth", "module": mod, "partition": f"P@{start_tile}",
           "start_tile": start_tile,
           "tiles": tiles, "n_gates": len(gates), "n_ff": n_ff,
           "bram_tiles": bram_tiles, "n_bram_cells": cell_seq,
           "inputs": inputs, "dffs": [d["name"] for d in ff_dffs],
           "mem_dffs": [d["name"] for d in mem_dffs],
           "provenance": "emitted by synth.py (do not hand-edit)"}
    p = os.path.join(HERE, "configs", f"{mod}.cell_synth.config.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(cfg, open(p, "w"), indent=2); open(p, "a").write("\n")

    ram_regs = []
    if ram:
        for s in range(ram["depth"]):
            for ln in ram["lanes"]:
                ram_regs.append(f"{ram['name']}_{s}_{ln['name']}")
    emit_loader(mod, gates, lut_at, ff_at, ff_dffs, inputs, out_of, sdef,
                CONST0, CONST1, resolve, consts, hist, hplace, bdef, bram_tiles,
                mem_dffs, mem_at, ram, ram_lane_tile)
    emit_verify(mod, inputs, [d["name"] for d in ff_dffs] + [hw["reg"] for hw in hist_words]
                + [d["name"] for d in mem_dffs] + ram_regs,
                os.path.dirname(os.path.abspath(sys.argv[1])))
    sys.stdout.write(json.dumps(cfg, indent=2) + "\n")
    sys.stderr.write(f"synth: {mod} -> {len(gates)} LUTs + {n_ff} FF BELs over "
                     f"{len(tiles)} CLB tiles (start {start_tile})\n")


def emit_loader(mod, gates, lut_at, ff_at, dffs, inputs, out_of, sdef,
                CONST0, CONST1, resolve, consts=(), hist=None, hplace=None,
                bdef=None, bram_tiles=(), mem_dffs=(), mem_at=None,
                ram=None, ram_lane_tile=None):
    MOD = mod.upper()
    mem_at = mem_at or {}
    ram_lane_tile = ram_lane_tile or {}
    dff_names = {d["name"] for d in dffs}
    ids = {}
    def vid(b):
        if b not in ids:
            ids[b] = len(ids)
        return ids[b]
    vid(CONST0); vid(CONST1)
    # const_nodes: fixed-value words referenced by cells/dffs (CANDLE_ONE, _POWER, ...)
    const_bits = {}     # bitsig -> 0/1
    for c in consts:
        v = int(c.get("value", 0))
        for i in range(W):
            b = f"{c['name']}#{i}"; vid(b); const_bits[b] = (v >> i) & 1
    for w in inputs:
        for i in range(W): vid(f"{w}#{i}")
    for d in dffs:
        for i in range(W): vid(f"{d['name']}#{i}")
    # resolve each dff's data/enable feed bitsigs
    feeds = []
    for d in dffs:
        fb = [resolve(f"{d['fed_by']}#{i}") for i in range(W)]
        en = resolve(f"{d['enable']}#0") if d.get("enable") else CONST1
        feeds.append((d["name"], fb, en))
        for b in fb: vid(b)
        vid(en)
    mem_feeds = []      # mem dff -> (name, fb bits, en bit) latched into BRAM
    for d in mem_dffs:
        fb = [resolve(f"{d['fed_by']}#{i}") for i in range(W)]
        en = resolve(f"{d['enable']}#0") if d.get("enable") else CONST1
        mem_feeds.append((d["name"], fb, en))
        for b in fb: vid(b)
        vid(en)
    for g in gates:
        for b in g["ins"]: vid(b)
        vid(g["out"])

    def topff(node, i):
        t, s = ff_at[(node, i)]
        return f"fpga_clb[{t}u][{sdef[f'CLB_SLICE_top_ff{s}']}u]"

    L = ["/* GENERATED by synth.py — cell-level synthesized loader. Evaluates the placed",
         " * LUT/FF netlist IN the fabric (LUT truth tables in tiles; this loader is the",
         " * configured routing). Never edits the blank header. */",
         f"#ifndef SYNTH_{MOD}_H", f"#define SYNTH_{MOD}_H",
         '#include "fpga_device_gen.h"',
         f"static word_t synv[{len(ids)}u];",
         f"static word_t synth_{mod}_in[{max(1,len(inputs))}u][64];"]
    luttiles = sorted({lut_at[gi][0] for gi in range(len(gates))})
    # load: program LUT truth tables, latch them
    L.append(f"static inline void synth_{mod}_load(void){{")
    for gi, g in enumerate(gates):
        t, s = lut_at[gi]
        L.append(f"  fpga_clb[{t}u][{sdef[f'CLB_SLICE_l{s}_cfg_d']}u]={g['tt']}ull;"
                 f" fpga_clb[{t}u][{sdef[f'CLB_SLICE_l{s}_cfg_en']}u]=1u;")
    for t in luttiles:
        L.append(f"  clb_slice_tick(fpga_clb[{t}u]);")
    L.append(f"  synv[{ids[CONST0]}u]=0u; synv[{ids[CONST1]}u]=1u;")
    for b, v in const_bits.items():
        L.append(f"  synv[{ids[b]}u]={v}u;")   # fixed const_node bit
    L.append("}")
    # tick: consts, inputs, FF reads, combinational eval (topo per-gate), FF latch
    L.append(f"static inline void synth_{mod}_tick(void){{")
    L.append(f"  synv[{ids[CONST0]}u]=0u; synv[{ids[CONST1]}u]=1u;")
    for wi, w in enumerate(inputs):
        for i in range(W):
            L.append(f"  synv[{ids[f'{w}#{i}']}u]=synth_{mod}_in[{wi}u][{i}u]&1u;")
    for d in dffs:
        dn = d["name"]
        for i in range(W):
            L.append(f"  synv[{ids[f'{dn}#{i}']}u]={topff(dn, i)}&1u;")
    # combinational eval: each LUT in topo order — set its inputs, tick its tile, read its output
    for gi, g in enumerate(gates):
        t, s = lut_at[gi]
        for n, b in enumerate(g["ins"]):
            L.append(f"  fpga_clb[{t}u][{sdef[f'CLB_SLICE_l{s}_i{n}']}u]=synv[{ids[b]}u];")
        L.append(f"  clb_slice_tick(fpga_clb[{t}u]); synv[{ids[g['out']]}u]=fpga_clb[{t}u][{sdef[f'CLB_SLICE_OUT_l{s}_y']}u]&1u;")
    # latch FFs: set every FF's d/en from synv, then one tick per FF tile
    fftiles = sorted({ff_at[(d['name'], i)][0] for d in dffs for i in range(W)})
    for nm, fb, en in feeds:
        for i in range(W):
            t, s = ff_at[(nm, i)]
            L.append(f"  fpga_clb[{t}u][{sdef[f'CLB_SLICE_d_{s}']}u]=synv[{ids[fb[i]]}u];"
                     f" fpga_clb[{t}u][{sdef[f'CLB_SLICE_en_{s}']}u]=synv[{ids[en]}u];")
    for t in fftiles:
        L.append(f"  clb_slice_tick(fpga_clb[{t}u]);")

    # ---- history record store -> BRAM (shift-in; newest at slot 0, Law #10) --
    # Runs AFTER the FF latch (gennet emits history after the dff writes), so the
    # slot-0 field source reads the NEW dff value. The shift reads OLD BRAM cells.
    def cell_ref(t, c, kind):
        return f"fpga_bram[{t}u][{bdef[f'BRAM_BLOCK_{kind}_{c}']}u]"

    def src_word_bit(node, i):
        # gennet captures field sources at tick START (old dff value / comb of old),
        # so read the synv value latched at tick start, NOT the post-latch FF.
        b = resolve(f"{node}#{i}")
        return f"(synv[{ids[b]}u]&1u)"
    if hist:
        we = hist.get("write_enable")
        we_expr = f"synv[{ids[resolve(we + '#0')]}u]&1u" if we else "1u"
        L.append(f"  word_t hwe=(word_t)({we_expr});")
        depth = hist["depth"]; flds = hist["fields"]
        # shift slots high->low: DIN[s] <- OLD CELL[s-1] (read all before any tick)
        for s in range(depth - 1, 0, -1):
            for fld in flds:
                t, c = hplace[(s, fld["name"])]
                pt, pc = hplace[(s - 1, fld["name"])]
                L.append(f"  {cell_ref(t,c,'DIN')}={cell_ref(pt,pc,'CELL')};"
                         f" {cell_ref(t,c,'WE')}=hwe;")
        for fld in flds:                                   # slot 0 <- field source word
            t, c = hplace[(0, fld["name"])]
            srcw = "|".join(f"({src_word_bit(fld['source'], i)}<<{i}u)" for i in range(W))
            L.append(f"  {cell_ref(t,c,'DIN')}=(word_t)({srcw}); {cell_ref(t,c,'WE')}=hwe;")
    # ---- addressed RAM words (mem dffs) -> BRAM cells: DIN=feed word, WE=enable --
    # Storage lives in BRAM; the feed/enable (the write decode) is ordinary fabric.
    for nm, fb, en in mem_feeds:
        t, c = mem_at[nm]
        memw = "|".join(f"((synv[{ids[fb[i]]}u]&1u)<<{i}u)" for i in range(W))
        L.append(f"  {cell_ref(t,c,'DIN')}=(word_t)({memw}); {cell_ref(t,c,'WE')}=synv[{ids[en]}u]&1u;")
    # ---- addressed RAM write port -> BRAM offset (no fabric decode) ----------
    # The runtime write index drives the BRAM cell offset (DIN_0+wa / WE_0+wa);
    # this is the address arithmetic a real BRAM port does. WE is cleared after
    # the latch so untouched cells hold next tick.
    din0 = bdef["BRAM_BLOCK_DIN_0"]; we0 = bdef["BRAM_BLOCK_WE_0"]
    cel0 = bdef["BRAM_BLOCK_CELL_0"]
    if ram:
        def word_from(node):
            return "|".join(f"({src_word_bit(node, i)}<<{i}u)" for i in range(W))
        L.append(f"  word_t _ram_wa=(word_t)({word_from(ram['wr_index'])}) & {ram['depth']-1}u;")
        L.append(f"  word_t _ram_we=(word_t)({src_word_bit(ram['wr_fire'], 0)});")
        for ln in ram["lanes"]:
            t = ram_lane_tile[ln["name"]]
            L.append(f"  fpga_bram[{t}u][{din0}u+_ram_wa]=(word_t)({word_from(ln['source'])});"
                     f" fpga_bram[{t}u][{we0}u+_ram_wa]=_ram_we;")
    for bt in bram_tiles:                                   # one latch over all BRAM tiles
        L.append(f"  bram_block_tick(fpga_bram[{bt}u]);")
    if ram:                                                 # clear WE so cells hold next tick
        for ln in ram["lanes"]:
            t = ram_lane_tile[ln["name"]]
            L.append(f"  fpga_bram[{t}u][{we0}u+_ram_wa]=0u;")
    L.append("}")
    # output accessors: reconstruct each register word from its 64 FF bits
    for d in dffs:
        L.append(f"static inline word_t synth_{mod}_{d['name']}(void){{ word_t v=0u;")
        for i in range(W):
            L.append(f"  v|=({topff(d['name'], i)}&1u)<<{i}u;")
        L.append("  return v; }")
    # history accessors: each (slot,field) word reads its BRAM storage cell
    if hist:
        for (slot, field), (t, c) in hplace.items():
            reg = f"{hist['name']}_{slot}_{field}"
            L.append(f"static inline word_t synth_{mod}_{reg}(void){{ return {cell_ref(t,c,'CELL')}; }}")
    # mem (RAM word) accessors: read the BRAM storage cell
    for nm, (t, c) in mem_at.items():
        L.append(f"static inline word_t synth_{mod}_{nm}(void){{ return {cell_ref(t,c,'CELL')}; }}")
    # addressed-RAM accessors: cell offset = slot in the lane's BRAM tile
    if ram:
        for s in range(ram["depth"]):
            for ln in ram["lanes"]:
                t = ram_lane_tile[ln["name"]]
                L.append(f"static inline word_t synth_{mod}_{ram['name']}_{s}_{ln['name']}(void)"
                         f"{{ return fpga_bram[{t}u][{cel0}u+{s}u]; }}")
    L.append("#endif")
    os.makedirs(GEN, exist_ok=True)
    open(os.path.join(GEN, f"{mod}_synth_load.h"), "w").write("\n".join(L) + "\n")


def emit_verify(mod, inputs, dff_names, mod_dir):
    """Emit a native-vs-synth harness: drive random inputs, tick both, compare every
    register word. Proves the synthesized (in-fabric LUT/FF) module == native module."""
    import re as _re
    MOD = mod.upper()
    guard = None
    cpath = os.path.join(mod_dir, "cells.h")
    if os.path.exists(cpath):
        for ln in open(cpath):
            m = _re.match(r"#ifndef\s+(\w+_H)", ln.strip())
            if m:
                guard = m.group(1); break
    nin, ndf = len(inputs), len(dff_names)
    L = [f'#include "{mod}_synth_load.h"']
    if guard:
        L.append(f"#define {guard}  /* suppress native module's duplicate cells.h */")
    L += [f'#include "{mod}_gen.h"', "#include <stdio.h>", "int main(void){",
          f"  fpga_device_init(); synth_{mod}_load();",
          f"  word_t reg[{MOD}_REG_COUNT]; {mod}_init(reg);"]
    if nin:
        L.append("  unsigned inr[]={" + ",".join(f"{MOD}_{x}" for x in inputs) + "};")
    L.append("  unsigned st[]={" + ",".join(f"{MOD}_{d}" for d in dff_names) + "};")
    L.append("  word_t (*sy[])(void)={" + ",".join(f"synth_{mod}_{d}" for d in dff_names) + "};")
    L += ["  unsigned seed=2463534242u; int pass=0,fail=0;", "  for(int c=0;c<8;c++){"]
    if nin:
        L += [f"    word_t in[{nin}];",
              f"    for(int k=0;k<{nin};k++){{seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;in[k]=(word_t)seed;}}",
              f"    for(int k=0;k<{nin};k++) reg[inr[k]]=in[k];"]
    L.append(f"    {mod}_tick(reg);")
    if nin:
        L.append(f"    for(int k=0;k<{nin};k++) for(int i=0;i<64;i++) synth_{mod}_in[k][i]=(in[k]>>i)&1u;")
    L += [f"    synth_{mod}_tick();",
          f"    for(int k=0;k<{ndf};k++){{ word_t n=reg[st[k]], s=sy[k](); if(n==s) pass++; else fail++; }}",
          "  }",
          f'  printf("VERIFY {mod}: %d/%d register-words bit-exact\\n",pass,pass+fail);',
          "  return fail?1:0;", "}"]
    open(os.path.join(GEN, f"{mod}_synth_verify.c"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
