#!/usr/bin/env python3
"""gennet.py — GENERIC netlist -> device C generator.

Consumes a ``<module>.net.json`` (produced by gen_module_net.py) and emits the
device C header ``<module>_gen.h`` with a strict READ -> COMPUTE -> WRITE tick.

This is a TOOL (hand-written Python). Its OUTPUT (the *_gen.h) is the hardware
artifact and is NEVER hand-edited — it is produced by running this generator.
The device tick is therefore generated, not hand-coded (Build-Sequence Law).

Every operation in the generated tick is a canonical structural cell call
(cell_buf/not/and/or/xor/mux/eqmask/addsub/dff + the cmp_lt gate-netlist
helper). No native +/-/* on data; selection is mask algebra; gated writes use
cell_dff(en). Running max/min are a cmp_lt + mux chain in the netlist, so the
device tracks real OHLC (the WAVE-1 stub computed only the compare flag).

Netlist nodes:
  config_nodes  — published upstream lanes (read-only)
  const_nodes   — reset-latched constants (incl. clock power bit)
  dff_nodes     — registered state; each has fed_by (+ optional enable)
  comb_nodes    — combinational cell chain (the logic); cell + inputs (+ invert,
                  sub, shift_right modifiers)
  history_ring  — ring snapshot appended on write_enable, wrapping at depth
  seam_nodes    — relay outputs (registered copy of a source each tick)

Usage:
    python3 gennet.py <module>.net.json > <module>_gen.h
"""
import json
import sys


CMP_LT_HELPER = """
/* cmp_lt: gate-netlist comparator. Returns 1 (bit0) iff a < b (unsigned).
 * a - b = a + (~b) + 1 via 64 full-adder cells; the carry-out of the top bit is
 * (a >= b). So (a < b) = carry ^ 1. Pure gate algebra, no native C compare. */
static inline word_t cmp_lt(word_t a, word_t b) {
    word_t carry = 1ULL;                 /* +1 for two's-complement of b */
    word_t i = 0ULL;
    for (i = 0ULL; i < 64ULL; i = i + 1ULL) {
        const word_t aa = (a >> i) & 1ULL;
        const word_t nb = (cell_not(b) >> i) & 1ULL;     /* ~b bit */
        const word_t fa = cell_fa(aa, nb, carry);
        carry           = (fa >> 1) & 1ULL;              /* carry-out to next */
    }
    return (carry & 1ULL) ^ 1ULL;        /* carry==0 (borrow) == (a < b) */
}
"""


def lc(name):
    return name.lower()


def emit_comb_expr(node):
    """One comb_node -> a single structural cell-call expression string.

    Inputs are referenced by their lower-cased name, which is bound either to a
    READ-phase register local or to an earlier COMPUTE-phase comb local. The
    only non-cell native tokens permitted are the optional invert (^ 1ULL) and
    shift_right (>> n) — boolean/shift, not add/sub/mul (gate 2b allows these).
    """
    cell = node["cell"]
    args = [lc(i) for i in node["inputs"]]
    if cell == "buf":
        expr = f"cell_buf({args[0]})"
    elif cell == "not":
        expr = f"cell_not({args[0]})"
    elif cell == "and":
        expr = f"cell_and({args[0]}, {args[1]})"
    elif cell == "or":
        expr = f"cell_or({args[0]}, {args[1]})"
    elif cell == "xor":
        expr = f"cell_xor({args[0]}, {args[1]})"
    elif cell == "eqmask":
        expr = f"cell_eqmask({args[0]}, {args[1]})"
    elif cell == "mux":
        expr = f"cell_mux({args[0]}, {args[1]}, {args[2]})"
    elif cell == "addsub":
        sub = str(int(node.get("sub", 0))) + "ULL"
        expr = f"cell_addsub({args[0]}, {args[1]}, {sub})"
    elif cell == "cmp_lt":
        expr = f"cmp_lt({args[0]}, {args[1]})"
    else:
        sys.stderr.write(f"gennet: unknown cell '{cell}' for {node['name']}\n")
        sys.exit(2)
    if node.get("invert"):
        expr = f"({expr} ^ 1ULL)"
    sr = node.get("shift_right")
    if sr:
        # Law 2: shifts are structural (cell_sar), not native >>.
        expr = f"cell_sar({expr}, {int(sr)}u)"
    return expr


def main():
    net_path = sys.argv[1] if len(sys.argv) > 1 else "candle.net.json"
    with open(net_path) as f:
        net = json.load(f)

    dev = net["device"]
    DEV = dev.upper()
    pfx = DEV

    config = net.get("config_nodes", [])
    consts = net.get("const_nodes", [])
    dffs = net.get("dff_nodes", [])
    combs = net.get("comb_nodes", [])
    seams = net.get("seam_nodes", [])
    hist = net.get("history_ring")
    clock = net.get("clock")

    dff_names = {d["name"] for d in dffs}
    comb_names = {c["name"] for c in combs}

    # ---- address allocation: one register slot per node, declaration order. --
    # A comb_node that shares a dff's name does NOT get its own slot (it flows
    # through the dff register) — prevents the WAVE-1 address-collision where the
    # same name was defined twice.
    order = []
    for n in config:
        order.append(n["name"])
    for n in consts:
        order.append(n["name"])
    for n in dffs:
        order.append(n["name"])
    for n in combs:
        if n["name"] not in dff_names:
            order.append(n["name"])     # diagnostic register for the comb value
    for s in seams:
        order.append(s["name"])

    # history ring: index counter + depth*fields snapshot lanes.
    ring_fields = []
    if hist:
        depth = hist["depth"]
        if depth <= 0 or (depth & (depth - 1)) != 0:
            sys.stderr.write(f"gennet: history_ring.depth ({depth}) not power of two\n")
            sys.exit(2)
        # No index register: history is a record STORE, not an index construct
        # (Law #10). Records shift in; identity is the time each record carries.
        for s in range(depth):
            for fld in hist["fields"]:
                nm = f"{hist['name']}_{s}_{fld['name']}"
                ring_fields.append((s, fld, nm))
                order.append(nm)

    if len(order) != len(set(order)):
        dupes = sorted({x for x in order if order.count(x) > 1})
        sys.stderr.write(f"gennet: duplicate register names (single-writer/"
                         f"no-overlap violation): {dupes}\n")
        sys.exit(3)

    addr = {nm: i for i, nm in enumerate(order)}
    count = len(order)

    has_cmp_lt = any(c.get("cell") == "cmp_lt" for c in combs)

    # ---- which READ-phase locals are actually consumed (avoid -Wunused) ------
    # A register local is read when it feeds a comb input, a dff.fed_by, a
    # dff.enable, a seam source, or a ring field source. comb_nodes are bound in
    # COMPUTE (not READ), so their names are NOT read-phase locals.
    consumed = set()
    for c in combs:
        consumed.update(c["inputs"])
    for d in dffs:
        consumed.add(d["fed_by"])
        if d.get("enable") is not None:
            consumed.add(d["enable"])
        consumed.add(d["name"])          # current value, for cell_dff(q, d, en)
    for s in seams:
        consumed.add(s["source"])
    if hist:
        for fld in hist["fields"]:
            consumed.add(fld["source"])
        if hist.get("write_enable") is not None:
            consumed.add(hist["write_enable"])

    out = []
    out.append(f"/* GENERATED by gennet.py from {net_path} — DO NOT EDIT BY HAND.")
    out.append(f" * The {dev} device: register lanes + cell-based logic (READ->COMPUTE->WRITE).")
    out.append(" * Netlist-generated; every data operation is a structural cell call. */")
    out.append(f"#ifndef {DEV}_GEN_H")
    out.append(f"#define {DEV}_GEN_H")
    out.append('#include "cells.h"')
    out.append("")
    out.append(f"#define {pfx}_REG_COUNT {count}u")
    # No WINDOW_BASE: build artifacts carry no addresses (registers are module-local
    # indices). Absolute placement is assigned later by the registry toolbox.
    out.append("")
    for nm in order:
        out.append(f"#define {pfx}_{nm} {addr[nm]}u")
    if hist:
        out.append(f"#define {pfx}_HIST_STRIDE {len(hist['fields'])}u")
        out.append(f"#define {pfx}_HIST_DEPTH {hist['depth']}u")
    out.append("")

    if has_cmp_lt:
        out.append(CMP_LT_HELPER)
        out.append("")

    # ---- init: synchronous reset; const lanes latch their value -------------
    out.append(f"static inline void {dev}_init(word_t *r) {{")
    out.append("    word_t i = 0ULL;")
    out.append(f"    for (i = 0ULL; i < {pfx}_REG_COUNT; i = i + 1ULL) {{ r[i] = 0ULL; }}")
    for n in consts:
        out.append(f"    r[{pfx}_{n['name']}] = {int(n.get('value', 0))}ULL;")
    out.append("}")
    out.append("")

    # ---- one clock edge ------------------------------------------------------
    out.append(f"/* {dev}_tick: one clock edge. READ inputs as const locals,")
    out.append(" * COMPUTE via cells (no native add/sub/mul on data), WRITE every register. */")
    out.append(f"static inline void {dev}_tick(word_t *r) {{")
    out.append("    /* READ phase — pre-read every consumed register value. */")
    for grp in (config, consts, dffs):
        for n in grp:
            nm = n["name"]
            if nm in consumed:
                out.append(f"    const word_t {lc(nm)} = r[{pfx}_{nm}];")
    out.append("")

    out.append("    /* COMPUTE phase — combinational cell chain (declaration order). */")
    for c in combs:
        out.append(f"    const word_t {lc(c['name'])} = {emit_comb_expr(c)};")
    out.append("")

    out.append("    /* WRITE phase — gated dff commit: r[X] = cell_dff(q, fed_by, enable). */")
    for d in dffs:
        nm = d["name"]
        src = lc(d["fed_by"])
        en = d.get("enable")
        en_tok = lc(en) if en is not None else "1ULL"
        out.append(f"    r[{pfx}_{nm}] = cell_dff({lc(nm)}, {src}, {en_tok});")
    # diagnostic comb registers (comb values not already backing a dff).
    for c in combs:
        if c["name"] not in dff_names:
            out.append(f"    r[{pfx}_{c['name']}] = {lc(c['name'])};")
    # seam outputs: registered relay copy of the source.
    for s in seams:
        out.append(f"    r[{pfx}_{s['name']}] = {lc(s['source'])};")
    out.append("")

    # ---- history record store (shift-in; NO index construct, Law #10) -------
    # History is a bank of stored records, not an index. On write_enable the
    # records shift down one slot and the newly-committed record enters slot 0;
    # otherwise every slot holds. There is NO write-pointer, NO address decoder,
    # NO managed slot — a record's identity is the time it carries as a stored
    # field. Browsing is a separate module that scans these records in parallel.
    # Shift is computed high->low so each r[s] reads slot s-1's OLD value.
    if hist:
        we = hist.get("write_enable")
        we_tok = lc(we) if we is not None else "1ULL"
        depth = hist["depth"]
        flds = hist["fields"]
        out.append("    /* history record store: shift-in on write_enable (newest at slot 0).")
        out.append("     * Each field is a gated dff; high->low order keeps the shift correct. */")
        for s in range(depth - 1, 0, -1):
            for fld in flds:
                dst = f"{hist['name']}_{s}_{fld['name']}"
                src = f"{hist['name']}_{s-1}_{fld['name']}"
                out.append(f"    r[{pfx}_{dst}] = cell_dff(r[{pfx}_{dst}], r[{pfx}_{src}], {we_tok});")
        for fld in flds:
            dst = f"{hist['name']}_0_{fld['name']}"
            out.append(f"    r[{pfx}_{dst}] = cell_dff(r[{pfx}_{dst}], {lc(fld['source'])}, {we_tok});")
        out.append("")
    out.append("}")
    out.append("")

    # ---- free-running power-gated loop --------------------------------------
    power = clock.get("power") if clock else None
    out.append(f"/* {dev}_run: canonical free-running clock. Power on once; the clock")
    out.append(" * self-oscillates while the power bit is set. Nothing external steps it. */")
    out.append(f"static inline void {dev}_run(word_t *r) {{")
    if power:
        out.append(f"    while (r[{pfx}_{power}] & 1ULL) {{ {dev}_tick(r); }}")
    else:
        out.append(f"    {dev}_tick(r);")
    out.append("}")
    out.append("")
    out.append(f"#endif /* {DEV}_GEN_H */")

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
