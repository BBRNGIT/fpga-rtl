#!/usr/bin/env python3
"""gen_pip_resolver_net.py — EMITTER: writes pip_resolver.net.json.

Emits the netlist for the PIP_RESOLVER device — the per-symbol pip-resolution
lookup. On the MAC edge it samples the NIC seam's SEAM_SYMBOL (gated by
SEAM_VALID), uses the symbol as a STATIC-table address (addr = symbol * 8 bytes =
the symbol-th 64-bit slot), reads the resolved pip value out of a static,
init-only pip-config table, and publishes it on PIP_RESOLUTION_REG.

The device tick is GENERATED from this netlist by gennet.py — never hand-written.
The table index is a power-of-two mask (PIP_TABLE_MASK); the slot select is the
branchless eqmask-gate-OR reduction; the bounded self-run uses cmp_lt and the
tick counter steps via cell_addsub — NO native +/-/* in the generated tick
(gate-level arithmetic law). The pip-config table is CONFIG ONLY (written once by
the starter); the device only READS it (per SPEC_REGISTERS.md s4: "Writes nothing
during operation (config only)").

Module-barrier: the PIP_RESOLVER reads the NIC seam's SEAM_SYMBOL/SEAM_VALID lanes
(nic_gen.h) as a CONSUMER of the NIC's published output window; it writes only its
own PIP_* registers. No private copy of the NIC map.
"""
import json

# Static pip-config table depth — MUST be a power of two (index is a branchless
# mask: SEAM_SYMBOL & (depth-1)). gennet asserts this at generate time.
TABLE_DEPTH = 16

NET = {
    "device": "pip_resolver",
    "kind": "lookup",
    "clock": "mac",
    "comment": (
        "PIP_RESOLVER — per-symbol pip-resolution lookup. On the MAC edge: sample "
        "the NIC seam's SEAM_SYMBOL (gated by SEAM_VALID), index a STATIC pip-config "
        "table by addr = symbol*8 bytes (= the symbol-th 64-bit slot; word index = "
        "symbol, reduced by a power-of-two mask — no %, no bounds if), read the "
        "resolved pip value (branchless eqmask-gate-OR slot select), and publish it "
        "on PIP_RESOLUTION_REG. Pure combinational address arithmetic + table "
        "select; the table is config-only (written once at init, never per-tick). "
        "Same-domain hop (MAC) with the NIC seam; no CDC."
    ),

    # --- config / input lanes (set once by the starter). ----------------------
    "config_nodes": [
        {"name": "PIP_POWER", "type": "bit",
         "comment": "power/enable: the device self-runs on the mac edge while bit0 = 1 (set once)"},
        {"name": "PIP_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run tick budget (set once by starter)"}
    ],

    # --- the static pip-config table: DEPTH slots, each an init-only u64 config
    # register. The symbol id is the table address (addr = symbol*8 bytes = slot).
    # Written ONCE by the starter; the device only READS it (SPEC s4 config-only). -
    "table": {
        "depth": TABLE_DEPTH,
        "prefix": "PIP_CFG_TABLE",        # PIP_CFG_TABLE_<i>: pip resolution for symbol i
        "index_from": "SEAM_SYMBOL",
        "comment": ("static pip-config table: index = SEAM_SYMBOL & (depth-1) "
                    "(power-of-two mask). Slot i holds the pip resolution for "
                    "symbol i (addr = symbol*8 bytes = the symbol-th 64-bit slot). "
                    "Config-only: written once at init, never mutated in the tick.")
    },

    # --- the NIC seam lanes the PIP_RESOLVER SAMPLES (read from nic_gen.h — the
    # NIC's canonical output window; not redeclared as PIP nodes). Listed here for
    # the generator's READ phase + validator no-floating cross-check. ------------
    "nic_inputs": ["SEAM_SYMBOL", "SEAM_VALID"],

    # --- registered state (dffs). --------------------------------------------
    "dff_nodes": [
        {"name": "PIP_TICKS", "type": "u64",
         "comment": "self-run tick counter (run-loop bookkeeping; bounds the self-run)"}
    ],

    # --- the lookup compute (branchless; for READ/COMPUTE gen). ---------------
    "compute": {
        "symbol": "SEAM_SYMBOL",   # the table address operand
        "valid": "SEAM_VALID",     # latch enable for the resolved output
        "comment": ("idx = symbol & (depth-1); res = OR-reduce over i of "
                    "(eqmask(idx,i) ? table[i] : 0). en = SEAM_VALID. The resolved "
                    "register latches on en=valid; PIP_VALID latches SEAM_VALID.")
    },

    # --- the output lanes: the device's OWN window (the sole writer). ----------
    # PIP_RESOLUTION_REG/PIP_SYMBOL latch on en=valid; PIP_VALID <= SEAM_VALID.
    "out_nodes": [
        {"name": "PIP_RESOLUTION_REG", "from": "res",    "type": "u64", "en": "valid",
         "comment": "resolved pip resolution for the sampled symbol (the unified Y-axis authority)"},
        {"name": "PIP_SYMBOL",         "from": "symbol", "type": "u64", "en": "valid",
         "comment": "the symbol id that was resolved (latched for display/trace)"}
    ],
    "out_status": [
        {"name": "PIP_VALID", "from": "valid", "type": "bit",
         "comment": "1 iff a symbol was sampled (= SEAM_VALID) this cycle"}
    ],

    "power": "PIP_POWER",
    "run": {"power": "PIP_POWER", "count": "PIP_TICKS", "limit": "PIP_RUN_UNTIL"}
}


def main():
    depth = NET["table"]["depth"]
    if depth <= 0 or (depth & (depth - 1)) != 0:
        raise SystemExit(
            f"gen_pip_resolver_net: table depth ({depth}) must be a power of two "
            f"(index is a branchless mask: SEAM_SYMBOL & (depth-1)).")
    with open("pip_resolver.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print(f"emitted pip_resolver.net.json (table depth {depth})")


if __name__ == "__main__":
    main()
