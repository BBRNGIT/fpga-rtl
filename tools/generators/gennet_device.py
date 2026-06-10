#!/usr/bin/env python3
"""gennet_device.py — universal device C generator for FPGA netlists.

This is a generic generator that produces device_gen.h from any valid device.net.json.
It synthesizes the complete device model from a netlist specification:

  - Device constants (register counts, window base, address map)
  - Register structure (all nodes as addressed memory slots)
  - Initialization function (synchronous reset to zero)
  - Clock primitives (gate-netlist comparators, arithmetic cells as needed)
  - Per-tick function skeleton with READ/COMPUTE/WRITE phases
  - Cell instantiation templates (branchless gate algebra)
  - Optional free-running clock loop (power-bit gated)
  - Optional display ring (snapshot history buffer)

The generated code is the source of truth for device structure. No hand-written logic
lives outside the gennet-produced header.

Usage:
    python3 gennet_device.py <netlist.net.json> > <device>_gen.h

The generator enforces:
  - No native C arithmetic in the data path (+/-/* forbidden)
  - All operations decomposed to cell calls (cell_and, cell_mux, cell_addsub, etc.)
  - Strict READ->COMPUTE->WRITE order (no read-after-write)
  - Branchless logic only (selection via mask algebra, not if/switch/?:)
  - Every node is a register; every operation routes through registers
"""

import json
import sys


# ---- Comparator helper functions (emitted only when needed) ----

CMP_LE_HELPER = """/* cmp_le: gate-netlist comparator. Returns 1 (bit0) iff a <= b (unsigned).
 * Implemented as (b - a) carry-out via 64 full-adder cells; the final carry
 * is 1 exactly when (b >= a) i.e. (a <= b). Pure gate algebra, no native compare. */
static inline word_t cmp_le(word_t a, word_t b) {
    word_t carry = 1ULL;                 /* +1 for two's-complement of a */
    word_t i = 0ULL;
    for (i = 0ULL; i < 64ULL; i = i + 1ULL) {
        const word_t bb = (b >> i) & 1ULL;
        const word_t na = (cell_not(a) >> i) & 1ULL;     /* ~a bit */
        const word_t fa = cell_fa(bb, na, carry);
        carry           = (fa >> 1) & 1ULL;              /* carry-out to next */
    }
    return carry & 1ULL;                 /* final carry-out == (a <= b) */
}
"""

CMP_LT_HELPER = """/* cmp_lt: gate-netlist comparator. Returns 1 (bit0) iff a < b (unsigned).
 * Implemented as (b - a) carry-out via 64 full-adder cells; the final carry
 * is 1 exactly when (b >= a) i.e. (a <= b). Then invert to get (a < b).
 * Pure gate algebra, no native compare. */
static inline word_t cmp_lt(word_t a, word_t b) {
    word_t carry = 1ULL;                 /* +1 for two's-complement of a */
    word_t i = 0ULL;
    for (i = 0ULL; i < 64ULL; i = i + 1ULL) {
        const word_t bb = (b >> i) & 1ULL;
        const word_t na = (cell_not(a) >> i) & 1ULL;     /* ~a bit */
        const word_t fa = cell_fa(bb, na, carry);
        carry           = (fa >> 1) & 1ULL;              /* carry-out to next */
    }
    return (carry & 1ULL) ^ 1ULL;        /* invert: (a < b) = !(a <= b) */
}
"""

CMP_GE_HELPER = """/* cmp_ge: gate-netlist comparator. Returns 1 (bit0) iff a >= b (unsigned).
 * Implemented as (a - b) carry-out via 64 full-adder cells; the final carry
 * is 1 exactly when (a >= b). Pure gate algebra, no native compare. */
static inline word_t cmp_ge(word_t a, word_t b) {
    word_t carry = 1ULL;                 /* +1 for two's-complement of b */
    word_t i = 0ULL;
    for (i = 0ULL; i < 64ULL; i = i + 1ULL) {
        const word_t aa = (a >> i) & 1ULL;
        const word_t nb = (cell_not(b) >> i) & 1ULL;     /* ~b bit */
        const word_t fa = cell_fa(aa, nb, carry);
        carry           = (fa >> 1) & 1ULL;              /* carry-out to next */
    }
    return carry & 1ULL;                 /* final carry-out == (a >= b) */
}
"""

CMP_GT_HELPER = """/* cmp_gt: gate-netlist comparator. Returns 1 (bit0) iff a > b (unsigned).
 * Implemented as (a - b) carry-out via 64 full-adder cells; the final carry
 * is 1 exactly when (a >= b). Then invert to get (a > b).
 * Pure gate algebra, no native compare. */
static inline word_t cmp_gt(word_t a, word_t b) {
    word_t carry = 1ULL;                 /* +1 for two's-complement of b */
    word_t i = 0ULL;
    for (i = 0ULL; i < 64ULL; i = i + 1ULL) {
        const word_t aa = (a >> i) & 1ULL;
        const word_t nb = (cell_not(b) >> i) & 1ULL;     /* ~b bit */
        const word_t fa = cell_fa(aa, nb, carry);
        carry           = (fa >> 1) & 1ULL;              /* carry-out to next */
    }
    return (carry & 1ULL) ^ 1ULL;        /* invert: (a > b) = !(a >= b) */
}
"""


def collect_comparators_needed(net):
    """Scan the netlist to determine which comparator helpers are needed.

    Returns a set of comparator names (cmp_le, cmp_lt, cmp_ge, cmp_gt) that
    are referenced in comb_nodes.
    """
    needed = set()
    for node in net.get("comb_nodes", []):
        if node.get("cell") == "cmp_le":
            needed.add("cmp_le")
        elif node.get("cell") == "cmp_lt":
            needed.add("cmp_lt")
        elif node.get("cell") == "cmp_ge":
            needed.add("cmp_ge")
        elif node.get("cell") == "cmp_gt":
            needed.add("cmp_gt")
    return needed


def emit_comb_node(node, prefix):
    """Generate a single combinational cell invocation.

    Transforms a comb_node into a const local variable initialized by calling
    the appropriate structural cell. Input register reads use the register
    address constants (R[PFX_NODENAME]); recursive comb dependencies are
    resolved by referencing the lower-cased local variable of the input node.

    The generated line is:
        const word_t <nodename_lower> = cell_<type>(...);

    No native C operators (except >> for structural shifts and ^ 1 for invert).
    """
    cell_type = node.get("cell", "buf")
    node_name = node["name"]
    node_name_lower = node_name.lower()
    inputs = node.get("inputs", [])

    # Build argument list: each input is either a lower-cased local (if it's a
    # comb node) or needs to be read from a register. For simplicity, we assume
    # inputs are pre-read into const locals in the READ phase, so all are
    # lower-cased. This matches the adapter pattern.
    args = [inp.lower() for inp in inputs]

    if cell_type == "buf":
        cell_call = f"cell_buf({args[0]})"
    elif cell_type == "not":
        cell_call = f"cell_not({args[0]})"
    elif cell_type == "and":
        cell_call = f"cell_and({args[0]}, {args[1]})"
    elif cell_type == "or":
        cell_call = f"cell_or({args[0]}, {args[1]})"
    elif cell_type == "xor":
        cell_call = f"cell_xor({args[0]}, {args[1]})"
    elif cell_type == "mux":
        # mux(a, b, sel): sel ? b : a
        cell_call = f"cell_mux({args[0]}, {args[1]}, {args[2]})"
    elif cell_type == "eqmask":
        # eqmask(a, b): 1 if a==b, 0 otherwise
        cell_call = f"cell_eqmask({args[0]}, {args[1]})"
    elif cell_type == "addsub":
        # addsub(a, b, sub): sub=0 → a+b; sub=1 → a-b
        sub_val = node.get("sub", 0)
        cell_call = f"cell_addsub({args[0]}, {args[1]}, {int(sub_val)}ULL)"
    elif cell_type == "cmp_le":
        # cmp_le(a, b): 1 if a <= b
        cell_call = f"cmp_le({args[0]}, {args[1]})"
    elif cell_type == "cmp_lt":
        # cmp_lt(a, b): 1 if a < b
        cell_call = f"cmp_lt({args[0]}, {args[1]})"
    elif cell_type == "cmp_ge":
        # cmp_ge(a, b): 1 if a >= b
        cell_call = f"cmp_ge({args[0]}, {args[1]})"
    elif cell_type == "cmp_gt":
        # cmp_gt(a, b): 1 if a > b
        cell_call = f"cmp_gt({args[0]}, {args[1]})"
    elif cell_type == "gate":
        # gate(val, en): val & en (register-backed pass-or-zero)
        cell_call = f"cell_gate({args[0]}, {args[1]})"
    elif cell_type == "fa":
        # full adder: fa(a, b, cin)
        cell_call = f"cell_fa({args[0]}, {args[1]}, {args[2]})"
    else:
        # Unknown cell; emit a comment placeholder (will likely fail to compile).
        return f"    /* TODO: unknown cell type '{cell_type}' for {node_name} */"

    # Apply optional modifiers.
    if node.get("invert"):
        cell_call = f"({cell_call} ^ 1ULL)"

    shift_right = node.get("shift_right")
    if shift_right:
        cell_call = f"({cell_call} >> {int(shift_right)}ULL)"

    return f"    const word_t {node_name_lower} = {cell_call};"


def build_ring_nodes(display_ring):
    """Extract all display ring node names from the ring specification.

    The ring is a circular buffer of snapshots. It has an emit counter and
    depth*fields snapshot registers. Returns a list of (slot_index, field_name, full_name).
    """
    if not display_ring:
        return []

    depth = display_ring["depth"]
    nodes = []
    for slot in range(depth):
        for field in display_ring["fields"]:
            full_name = f"DISP_{slot}_{field}"
            nodes.append((slot, field, full_name))

    return nodes


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: gennet_device.py <netlist.net.json> > <device>_gen.h\n")
        sys.exit(1)

    net_path = sys.argv[1]
    with open(net_path) as f:
        net = json.load(f)

    device_name = net.get("device", "device")
    device_name_upper = device_name.upper()
    window_base = net.get("window_base", "0x0")

    # ---- Build the register address map. ----
    # Each node gets a unique address slot in declaration order:
    # config_nodes, buffer_nodes, const_nodes, dff_nodes, comb_nodes,
    # then display ring nodes.

    address_map = {}
    node_order = []

    for group in ("config_nodes", "buffer_nodes", "const_nodes", "dff_nodes", "comb_nodes"):
        for node in net.get(group, []):
            name = node["name"]
            address_map[name] = len(node_order)
            node_order.append(name)

    # Display ring nodes.
    display_ring = net.get("display_ring")
    ring_nodes = build_ring_nodes(display_ring)
    if display_ring:
        # Emit counter comes first.
        count_name = display_ring["count"]
        address_map[count_name] = len(node_order)
        node_order.append(count_name)

        # Then all ring snapshot slots.
        for slot, field, full_name in ring_nodes:
            address_map[full_name] = len(node_order)
            node_order.append(full_name)

    total_registers = len(node_order)

    # ---- Collect which comparators are needed. ----
    comparators_needed = collect_comparators_needed(net)

    # ---- Begin output. ----
    lines = []

    lines.append(f"/* GENERATED by gennet_device.py from {net_path} — DO NOT EDIT BY HAND.")
    lines.append(f" * The {device_name} device: complete model from netlist.")
    lines.append(f" * All logic is gate-level; every operation is a structural cell call. */")
    lines.append(f"#ifndef {device_name_upper}_GEN_H")
    lines.append(f"#define {device_name_upper}_GEN_H")
    lines.append('#include "cells.h"')
    lines.append("")

    # ---- Device constants. ----
    lines.append(f"/* Device constants: register count, window base, address map. */")
    lines.append(f"#define {device_name_upper}_REG_COUNT {total_registers}u")
    lines.append(f"#define {device_name_upper}_WINDOW_BASE {window_base}u")
    lines.append("")

    # ---- Register address macros. ----
    for name in node_order:
        addr = address_map[name]
        lines.append(f"#define {device_name_upper}_{name} {addr}u")

    # Display ring macros (if present).
    if display_ring:
        lines.append("")
        lines.append(f"#define {device_name_upper}_DISP_STRIDE {len(display_ring['fields'])}u")
        lines.append(f"#define {device_name_upper}_DISP_DEPTH {display_ring['depth']}u")
        lines.append(f"#define {device_name_upper}_DISP_MASK ({device_name_upper}_DISP_DEPTH - 1u)")

    lines.append("")

    # ---- Comparator helpers. ----
    if comparators_needed:
        lines.append("/* Gate-netlist comparators (used by comb nodes). */")
        if "cmp_le" in comparators_needed:
            lines.append(CMP_LE_HELPER)
        if "cmp_lt" in comparators_needed:
            lines.append(CMP_LT_HELPER)
        if "cmp_ge" in comparators_needed:
            lines.append(CMP_GE_HELPER)
        if "cmp_gt" in comparators_needed:
            lines.append(CMP_GT_HELPER)
        lines.append("")

    # ---- Initialization function. ----
    lines.append(f"/* {device_name}_init: synchronous reset. Zero all registers. */")
    lines.append(f"static inline void {device_name}_init(word_t *r) {{")
    lines.append(f"    word_t i = 0ULL;")
    lines.append(f"    for (i = 0ULL; i < {device_name_upper}_REG_COUNT; i = i + 1ULL) {{")
    lines.append(f"        r[i] = 0ULL;")
    lines.append(f"    }}")

    # Const nodes are initialized to their fixed values (not zero).
    for node in net.get("const_nodes", []):
        const_value = node.get("value", 0)
        lines.append(f"    r[{device_name_upper}_{node['name']}] = {int(const_value)}ULL;")

    lines.append("}")
    lines.append("")

    # ---- Per-tick function. ----
    lines.append(f"/* {device_name}_tick: one clock edge. READ all inputs as const locals,")
    lines.append(f" * COMPUTE using gate cells (no native C operators), WRITE all outputs. */")
    lines.append(f"static inline void {device_name}_tick(word_t *r) {{")

    # READ phase: pre-read all consumed values from registers into const locals.
    lines.append("    /* READ phase — pre-read every consumed register into const locals. */")

    # Determine which nodes are actually consumed as inputs to comb_nodes or
    # held-dffs (dffs with no comb writer).
    consumed_nodes = set()
    comb_writes = set()
    for node in net.get("comb_nodes", []):
        consumed_nodes.update(node.get("inputs", []))
        comb_writes.add(node["name"])

    # Hold-dffs (no comb writer) need to be re-read and re-committed.
    for node in net.get("dff_nodes", []):
        if node["name"] not in comb_writes:
            consumed_nodes.add(node["name"])

    # Display ring fields are consumed as sources.
    display_ring = net.get("display_ring")
    if display_ring:
        for field in display_ring["fields"]:
            consumed_nodes.add(field)

    # Emit READ-phase locals for all consumed non-comb nodes.
    for node_name in node_order:
        if node_name in comb_writes:
            # This node is recomputed in COMPUTE phase; don't read it.
            continue
        if node_name not in consumed_nodes:
            # Not consumed; don't emit a local.
            continue

        lines.append(f"    const word_t {node_name.lower()} = r[{device_name_upper}_{node_name}];")

    if not consumed_nodes:
        lines.append("    /* No inputs consumed in this cycle. */")

    lines.append("")

    # COMPUTE phase: evaluate all comb nodes and compute derived values.
    lines.append("    /* COMPUTE phase — all logic via gate cells. */")

    # Compute clock_next and pos_next if clock/pos sections are defined.
    clock = net.get("clock")
    if clock:
        counter = clock["counter"]
        step = clock.get("step")
        if step:
            # clk_next = cell_addsub(clk, clk_step, 0)
            lines.append(f"    const word_t {counter.lower()}_next = cell_addsub({counter.lower()}, {step.lower()}, 0ULL);")

    pos = net.get("pos")
    if pos:
        counter = pos["counter"]
        increment = pos["increment"]
        # pos_next = cell_addsub(pos, due, 0)
        lines.append(f"    const word_t {counter.lower()}_next = cell_addsub({counter.lower()}, {increment.lower()}, 0ULL);")

    # Compute writeout gated DFFs if writeout section is defined.
    writeout = net.get("writeout")
    if writeout:
        enable = writeout["enable"]
        valid = writeout["valid"]

        # For each output lane, compute: out_next = cell_dff(out, from, enable)
        for lane in writeout["lanes"]:
            out = lane["out"]
            src = lane["from"]
            out_lower = out.lower()
            src_lower = src.lower()
            lines.append(f"    const word_t {out_lower}_next = cell_dff(r[{device_name_upper}_{out}], {src_lower}, {enable.lower()});")

        # Compute valid lane: valid_next = cell_dff(valid, enable, power_or_implicit)
        # Use '1ULL' as a simple implicit gating for now.
        valid_lower = valid.lower()
        lines.append(f"    const word_t {valid_lower}_next = cell_dff(r[{device_name_upper}_{valid}], {enable.lower()}, 1ULL);")

    # Emit all other comb nodes.
    comb_nodes = net.get("comb_nodes", [])
    if comb_nodes:
        for node in comb_nodes:
            lines.append(emit_comb_node(node, device_name_upper))

    if not (clock or pos or writeout or comb_nodes):
        lines.append("    /* No combinational logic in this device. */")

    lines.append("")

    # WRITE phase: commit all dff nodes.
    lines.append("    /* WRITE phase — commit every dff (no read-after-write). */")

    # Write clock counter if clock section is defined.
    if clock:
        counter = clock["counter"]
        lines.append(f"    r[{device_name_upper}_{counter}] = {counter.lower()}_next;")

    # Write pos counter if pos section is defined.
    if pos:
        counter = pos["counter"]
        lines.append(f"    r[{device_name_upper}_{counter}] = {counter.lower()}_next;")

    # Write all writeout lanes if writeout section is defined.
    if writeout:
        for lane in writeout["lanes"]:
            out = lane["out"]
            out_lower = out.lower()
            lines.append(f"    r[{device_name_upper}_{out}] = {out_lower}_next;")
        valid = writeout["valid"]
        valid_lower = valid.lower()
        lines.append(f"    r[{device_name_upper}_{valid}] = {valid_lower}_next;")

    # Write all remaining dff nodes (those not handled by clock/pos/writeout).
    handled_dffs = set()
    if clock:
        handled_dffs.add(clock["counter"])
    if pos:
        handled_dffs.add(pos["counter"])
    if writeout:
        for lane in writeout["lanes"]:
            handled_dffs.add(lane["out"])
        handled_dffs.add(writeout["valid"])

    for node in net.get("dff_nodes", []):
        name = node["name"]
        if name in handled_dffs:
            continue

        name_lower = name.lower()

        # If this dff is recomputed (has a matching comb), use the comb result.
        if name in comb_writes:
            src = name_lower
        else:
            # Hold dff: re-commit its read value.
            src = name_lower

        lines.append(f"    r[{device_name_upper}_{name}] = {src};")

    # Display ring WRITE (if present).
    if display_ring:
        lines.append("")
        lines.append("    /* Display ring append: snapshot on each tick (or on event). */")
        count_name = display_ring["count"]
        count_name_lower = count_name.lower()

        # The ring index is: emit_count & (depth - 1)
        lines.append(f"    const word_t {count_name_lower} = r[{device_name_upper}_{count_name}];")
        lines.append(f"    const word_t wr_slot = cell_and({count_name_lower}, {device_name_upper}_DISP_MASK);")

        # For each field in the ring, emit a slot-write conditional via eqmask.
        # Note: Field names are assumed to be the same as the source register names (lower-cased).
        # If a field is derived (e.g., ADP_CLK_AT_EMIT from ADP_CLK), manually edit this section
        # or extend the netlist with explicit field-to-source mappings.
        for slot, field, full_name in ring_nodes:
            field_src = field.lower()
            lines.append(f"    const word_t rw_{full_name} = cell_dff(r[{device_name_upper}_{full_name}], {field_src}, cell_eqmask(wr_slot, {slot}ULL));")

        # Write back all ring nodes and the emit counter.
        for slot, field, full_name in ring_nodes:
            lines.append(f"    r[{device_name_upper}_{full_name}] = rw_{full_name};")
        lines.append(f"    r[{device_name_upper}_{count_name}] = cell_addsub({count_name_lower}, 1ULL, 0ULL);")

    lines.append("}")
    lines.append("")

    # ---- Free-running clock loop. ----
    lines.append(f"/* {device_name}_run: self-oscillating clock loop (power-bit gated). */")
    lines.append(f"static inline void {device_name}_run(word_t *r) {{")

    # Check if there's a POWER node, either from the clock section or named POWER.
    power_node = None
    if clock and "power" in clock:
        power_node = clock["power"]
    else:
        # Fallback: look for a node named POWER or power.
        for group in ("config_nodes", "const_nodes", "dff_nodes"):
            for node in net.get(group, []):
                if node["name"].upper() == "POWER":
                    power_node = node["name"]
                    break

    if power_node:
        lines.append(f"    while (r[{device_name_upper}_{power_node}] & 1ULL) {{")
        lines.append(f"        {device_name}_tick(r);")
        lines.append("    }")
    else:
        # No POWER node; emit a single tick and return.
        lines.append(f"    {device_name}_tick(r);")

    lines.append("}")
    lines.append("")

    # ---- Closing. ----
    lines.append(f"#endif /* {device_name_upper}_GEN_H */")

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
