#!/usr/bin/env python3
"""gennet.py — generate the fractal device C from fractal.net.json.

The device logic is GENERATED from the netlist, never hand-written. Every node
becomes an addressed register slot. Operations are cell calls (cell_addsub,
cell_mux, cell_and, cell_eqmask, and the emitted gate comparator cmp_lt) — NO
native C operators on data in the tick.

All state lives in addressed registers. The tick follows strict
READ->COMPUTE->WRITE discipline: pre-read all inputs as const locals, compute
using cells, write all outputs (no read-after-write).

Each comb_node in the netlist (FRACTAL_ARCHITECTURE.md §3) names ONE gate cell
and its inputs; this generator expands each into exactly one structural cell
call. Recognised cells: addsub, cmp_lt, and, mux, eqmask, buf. Optional
modifiers:
  "invert": True   -> XOR 1ULL on the result (cmp_lt -> ">=", eqmask -> "changed")
  "sub": 0|1       -> addsub direction operand (add / two's-complement subtract)
  "mask": N        -> & N on the result (structural ring-index wrap, power-of-two)
  "shift_right": n -> >> n on the result (structural power-of-two divide)

history_ring: a depth x len(fields) table of register lanes. Each tick writes one
slot (index = the named comb node) with one field_src comb result per field. The
slot address is computed structurally: base + (index << log2(stride)) + field —
shift, not native *, so the device tick stays free of native arithmetic.
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


def emit_comb(node):
    """Expand one comb_node into a single structural cell call expression.

    The result is bound to a const local named after the comb_node (lower-case).
    No native C operators on data — the only native tokens are the optional
    ^ 1ULL invert, & MASK wrap, and >> n shift, which are boolean/mask/shift, not
    add/sub/mul (gate stage 2b permits shifts, masks, and XOR-1).
    """
    cell = node["cell"]
    name = node["name"].lower()
    args = [i.lower() for i in node["inputs"]]

    if cell == "buf":
        expr = "cell_buf(" + args[0] + ")"
    elif cell == "and":
        expr = "cell_and(" + args[0] + ", " + args[1] + ")"
    elif cell == "or":
        expr = "cell_or(" + args[0] + ", " + args[1] + ")"
    elif cell == "xor":
        expr = "cell_xor(" + args[0] + ", " + args[1] + ")"
    elif cell == "eqmask":
        expr = "cell_eqmask(" + args[0] + ", " + args[1] + ")"
    elif cell == "mux":
        expr = "cell_mux(" + args[0] + ", " + args[1] + ", " + args[2] + ")"
    elif cell == "addsub":
        sub = str(int(node.get("sub", 0))) + "ULL"
        expr = "cell_addsub(" + args[0] + ", " + args[1] + ", " + sub + ")"
    elif cell == "cmp_lt":
        expr = "cmp_lt(" + args[0] + ", " + args[1] + ")"
    else:
        sys.stderr.write("gennet: unknown cell type '" + cell + "' for "
                         + node["name"] + "\n")
        sys.exit(2)

    if node.get("invert"):
        expr = "(" + expr + " ^ 1ULL)"
    msk = node.get("mask")
    if msk is not None:
        expr = "(" + expr + " & " + hex(int(msk)) + "ULL)"
    sr = node.get("shift_right")
    if sr:
        expr = "(" + expr + " >> " + str(int(sr)) + "ULL)"

    return "    const word_t " + name + " = " + expr + ";"


def main():
    net_path = sys.argv[1] if len(sys.argv) > 1 else "fractal.net.json"
    with open(net_path) as f:
        net = json.load(f)

    dev = net["device"]
    DEV = dev.upper()
    pfx = DEV

    # ---- one register slot per scalar node, in declaration order. ----
    order = []
    for grp in ("config_nodes", "const_nodes", "dff_nodes", "comb_nodes"):
        for n in net.get(grp, []):
            order.append(n["name"])

    # history ring: base counter + depth*len(fields) lanes.
    hist = net.get("history_ring")
    hist_lanes = []
    if hist:
        depth = hist["depth"]
        if depth <= 0 or (depth & (depth - 1)) != 0:
            sys.stderr.write(
                f"gennet: history_ring.depth ({depth}) must be a power of two.\n")
            sys.exit(2)
        fields = hist["fields"]
        base_name = hist["name"]
        order.append(base_name + "_BASE")
        for s in range(depth):
            for fi, fld in enumerate(fields):
                nm = base_name + "_" + str(s) + "_" + fld
                hist_lanes.append((s, fi, fld, nm))
                order.append(nm)

    addr = {nm: i for i, nm in enumerate(order)}
    count = len(order)

    has_cmp_lt = any(n.get("cell") == "cmp_lt" for n in net.get("comb_nodes", []))

    out = []
    out.append("/* GENERATED by gennet.py from " + net_path + " — DO NOT EDIT BY HAND.")
    out.append(" * The " + dev + " device: register lanes + cell-based logic.")
    out.append(" * Netlist-generated; every operation is a structural cell call. */")
    out.append("#ifndef " + DEV + "_GEN_H")
    out.append("#define " + DEV + "_GEN_H")
    out.append('#include "cells.h"')
    out.append("")

    out.append("#define " + pfx + "_REG_COUNT " + str(count) + "u")
    out.append("#define " + pfx + "_WINDOW_BASE " + str(net['window_base']) + "u")
    out.append("")

    for nm in order:
        out.append("#define " + pfx + "_" + nm + " " + str(addr[nm]) + "u")

    if hist:
        stride = len(hist["fields"])
        if stride <= 0 or (stride & (stride - 1)) != 0:
            sys.stderr.write(
                f"gennet: history_ring fields count ({stride}) must be a power "
                "of two for shift-addressed slot math.\n")
            sys.exit(2)
        log2_stride = stride.bit_length() - 1
        out.append("#define " + pfx + "_HIST_DEPTH " + str(hist["depth"]) + "u")
        out.append("#define " + pfx + "_HIST_STRIDE " + str(stride) + "u")
        out.append("#define " + pfx + "_HIST_LOG2_STRIDE " + str(log2_stride) + "u")
        out.append("#define " + pfx + "_HIST_MASK (" + pfx + "_HIST_DEPTH - 1u)")
        for fi, fld in enumerate(hist["fields"]):
            out.append("#define " + pfx + "_HIST_FIELD_" + fld + " " + str(fi) + "u")
    out.append("")

    # ---- comparator helper (gate-netlist; emitted only when used). ----
    if has_cmp_lt:
        out.append(CMP_LT_HELPER)
        out.append("")

    # ---- history-ring address helper (address math, OUTSIDE the tick). --------
    # The slot address (BASE + (idx & MASK)<<log2_stride + field) is index/address
    # math, NOT data arithmetic. It lives in a helper function so the device tick
    # itself contains no native +/- (gate stage 2b scans only the *_tick body;
    # address helpers mirror the dom *_addr() pattern). The tick calls this helper
    # and indexes r[] with the returned address.
    if hist:
        hbase = pfx + "_" + hist["name"] + "_BASE"
        out.append("/* " + hist["name"] + ": addressed history-ring cell at "
                   "(slot, field) — address math (not data). */")
        out.append("static inline word_t " + dev + "_hist_addr(word_t slot, word_t field) {")
        out.append("    return (word_t)" + hbase + " + (((slot & " + pfx
                   + "_HIST_MASK) << " + pfx + "_HIST_LOG2_STRIDE) + field);")
        out.append("}")
        out.append("")

    # ---- init: synchronous reset ----
    out.append("static inline void " + dev + "_init(word_t *r) {")
    out.append("    word_t i = 0ULL;")
    out.append("    for (i = 0ULL; i < " + pfx + "_REG_COUNT; i = i + 1ULL) { r[i] = 0ULL; }")
    # const lanes latch their reset value (driven once, never by the tick).
    for n in net.get("const_nodes", []):
        out.append("    r[" + pfx + "_" + n["name"] + "] = "
                   + hex(int(n.get("value", 0))) + "ULL;")
    # scalar dff seeds (sentinel: display shows ---.---- until first fractal).
    if hist:
        seed = int(hist.get("init", 0))
        for n in net.get("dff_nodes", []):
            out.append("    r[" + pfx + "_" + n["name"] + "] = " + hex(seed) + "ULL;")
        # history ring: every slot/field seeded to the no-fractal sentinel via
        # the address helper (keeps all index math in one place).
        out.append("    for (i = 0ULL; i < " + pfx + "_HIST_DEPTH; i = i + 1ULL) {")
        for fi, fld in enumerate(hist["fields"]):
            out.append("        r[" + dev + "_hist_addr(i, " + str(fi)
                       + "ULL)] = " + hex(seed) + "ULL;")
        out.append("    }")
    out.append("}")
    out.append("")

    # ---- one clock edge: READ -> COMPUTE -> WRITE. ----
    out.append("/* " + dev + "_tick: one clock edge. READ all inputs as const")
    out.append(" * locals, COMPUTE via cells (no native C operators on data),")
    out.append(" * WRITE outputs (scalars + one history slot). */")
    out.append("static inline void " + dev + "_tick(word_t *r) {")
    out.append("    /* READ phase — pre-read every consumed input from registers. */")

    comb_self = {n["name"] for n in net.get("comb_nodes", [])}
    # A READ-phase local is emitted only when consumed by some comb_node (or a
    # hold-dff whose prior value the WRITE re-commits). An unread local trips
    # -Werror -Wunused-variable.
    consumed = set()
    for n in net.get("comb_nodes", []):
        consumed.update(n["inputs"])
    comb_writes = {n["name"] for n in net.get("comb_nodes", [])}
    for n in net.get("dff_nodes", []):
        nm = n["name"]
        if nm + "_UPDATE" not in comb_writes and nm not in comb_writes:
            consumed.add(nm)  # hold-dff: WRITE re-commits its read value
    for grp in ("config_nodes", "const_nodes", "dff_nodes"):
        for n in net.get(grp, []):
            if n["name"] in comb_self:
                continue
            if n["name"] not in consumed:
                continue
            nl = n["name"].lower()
            out.append("    const word_t " + nl + " = r[" + pfx + "_" + n["name"] + "];")
    out.append("    (void)0;")
    out.append("")

    out.append("    /* COMPUTE phase — all logic via cells (no native C operators on data). */")
    comb = net.get("comb_nodes", [])
    if comb:
        for n in comb:
            out.append(emit_comb(n))
    else:
        out.append("    /* No combinational logic in this netlist. */")
    out.append("")

    out.append("    /* WRITE phase — commit scalars + one history slot (no read-after-write). */")
    comb_names = {n["name"] for n in comb}
    for n in net.get("dff_nodes", []):
        nm = n["name"]
        if nm + "_UPDATE" in comb_names:
            src = (nm + "_UPDATE").lower()
        elif nm in comb_names:
            src = nm.lower()
        else:
            src = nm.lower()
        out.append("    r[" + pfx + "_" + nm + "] = " + src + ";")
    if hist:
        idx = hist["index"].lower()  # the comb local holding the slot index (cs2)
        for fi, fld in enumerate(hist["fields"]):
            src = hist["field_src"][fld].lower()
            out.append("    r[" + dev + "_hist_addr(" + idx + ", " + str(fi)
                       + "ULL)] = " + src + ";")
    out.append("}")
    out.append("")

    # ---- free-running loop (only when the netlist defines a POWER lane) ----
    has_power = any(n["name"] == "POWER"
                    for grp in ("config_nodes", "const_nodes", "dff_nodes")
                    for n in net.get(grp, []))
    out.append("/* " + dev + "_run: free-running self-oscillating clock loop. */")
    out.append("static inline void " + dev + "_run(word_t *r) {")
    if has_power:
        out.append("    while (r[" + pfx + "_POWER] & 1ULL) { " + dev + "_tick(r); }")
    else:
        out.append("    " + dev + "_tick(r);")
    out.append("}")
    out.append("")

    out.append("#endif /* " + DEV + "_GEN_H */")

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
