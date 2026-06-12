#!/usr/bin/env python3
"""gen_nic_net.py — EMITTER: writes nic.net.json.

Emits the netlist for the NIC device — the wire->fifo gateway. On the MAC edge it
samples the wire bus (gated by WIRE_VALID), dedups by WIRE_SEQ via a history ring,
re-stamps the survivor with the MAC-domain TAI value (TAI_MAC from tai_cdc), and
deposits the structured packet into the nic->fifo seam on a 1-cycle write strobe.

The device tick is GENERATED from this netlist by gennet.py — never hand-written.
The dedup ring index is a power-of-two mask (NIC_RING_MASK); add/sub is the
cell_addsub fa-chain; comparison/equality are cell_eqmask/cmp_lt gate netlists —
NO native +/-/* in the generated tick (gate-level arithmetic law).

Module-barrier: the NIC reads the wire's WIRE_* lanes (wire_gen.h) and tai_cdc's
TAI_MAC lane (tai_cdc_gen.h) as a CONSUMER of their published windows; it writes
only its own NIC_*/SEAM_* registers. No private copies of the sibling maps.
"""
import json

# Dedup ring depth — MUST be a power of two (index is a branchless mask:
# WIRE_SEQ & (depth-1)). gennet asserts this at generate time.
RING_DEPTH = 16

NET = {
    "device": "nic",
    "kind": "gateway",
    "clock": "mac",
    "comment": (
        "NIC — the wire->fifo gateway. On the MAC edge: sample the wire bus "
        "(gated by WIRE_VALID), dedup by WIRE_SEQ via a history ring (full-seq "
        "key + valid tag), re-stamp the survivor with TAI_MAC (the MAC-domain "
        "TAI value from tai_cdc; never a raw cross-domain tai read), and deposit "
        "the structured re-stamped packet into the nic->fifo seam on a 1-cycle "
        "write strobe. Same-domain hop (MAC); the FIFO CDC is downstream (fifo_rx)."
    ),

    # --- config / input lanes (set once by the starter). ----------------------
    "config_nodes": [
        {"name": "NIC_POWER", "type": "bit",
         "comment": "power/enable: the NIC self-runs on the mac edge while bit0 = 1 (set once)"},
        {"name": "NIC_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run tick budget (set once by starter)"}
    ],

    # --- the wire bus lanes the NIC SAMPLES (read from wire_gen.h — the wire's
    # canonical window; not redeclared as NIC nodes). Listed here for the
    # generator's READ phase + validator no-floating cross-check. ---------------
    "wire_inputs": [
        "WIRE_BID_PX", "WIRE_ASK_PX", "WIRE_TIME", "WIRE_SYMBOL",
        "WIRE_PIP", "WIRE_COMMISSION", "WIRE_SEQ", "WIRE_VALID"
    ],
    # the tai_cdc output lane the NIC reads (from tai_cdc_gen.h).
    "tai_input": "TAI_MAC",

    # --- registered state (dffs). --------------------------------------------
    "dff_nodes": [
        {"name": "NIC_TICKS", "type": "u64",
         "comment": "self-run tick counter (run-loop bookkeeping; bounds the self-run)"}
    ],

    # --- dedup history ring: depth slots, each a (seq dff + valid dff). --------
    "ring": {
        "depth": RING_DEPTH,
        "seq_prefix": "NIC_RING_SEQ",      # NIC_RING_SEQ_<i>: last seq seen at index i
        "valid_prefix": "NIC_RING_VALID",  # NIC_RING_VALID_<i>: slot i has stored a seq
        "index_from": "WIRE_SEQ",
        "comment": ("dedup ring: index = WIRE_SEQ & (depth-1) (power-of-two mask). Each "
                    "slot stores the FULL last seq seen there + a valid tag. A packet is a "
                    "DUP iff slot valid AND slot_seq == WIRE_SEQ (cell_eqmask). Storing the "
                    "full seq (not a parity bit) makes a wrapped old seq never false-match.")
    },

    # --- the dedup / stamp / strobe compute (branchless; for READ/COMPUTE gen).
    "compute": {
        "valid": "WIRE_VALID",
        "seq": "WIRE_SEQ",
        "stamp": "TAI_MAC",            # authoritative seam time
        "src_time": "WIRE_TIME",       # kept for latency/sync
        "comment": ("dup = valid & slot_valid & eqmask(slot_seq, WIRE_SEQ); "
                    "pass = valid & ~dup; strobe = pass (1-cycle). Seam flops latch "
                    "on en=pass; ring slot at idx latches seq + valid=1 on en=pass.")
    },

    # --- the nic->fifo seam: the NIC's OWN output lanes (en = pass gated dffs).
    # The NIC is the seam's sole writer; fifo_rx (next component) samples these. -
    "seam_nodes": [
        {"name": "SEAM_BID_PX",     "from": "WIRE_BID_PX",     "type": "u64",
         "comment": "re-stamped packet: bid price (passthrough)"},
        {"name": "SEAM_ASK_PX",     "from": "WIRE_ASK_PX",     "type": "u64",
         "comment": "re-stamped packet: ask price (passthrough)"},
        {"name": "SEAM_TIME",       "from": "TAI_MAC",         "type": "u64",
         "comment": "TAI stamp = TAI_MAC (authoritative downstream)"},
        {"name": "SEAM_SRC_TIME",   "from": "WIRE_TIME",       "type": "u64",
         "comment": "source time (WIRE_TIME) kept for sync/latency"},
        {"name": "SEAM_SYMBOL",     "from": "WIRE_SYMBOL",     "type": "u64",
         "comment": "symbol id (passthrough)"},
        {"name": "SEAM_PIP",        "from": "WIRE_PIP",        "type": "u64",
         "comment": "pip value (passthrough)"},
        {"name": "SEAM_COMMISSION", "from": "WIRE_COMMISSION", "type": "u64",
         "comment": "commission (passthrough)"},
        {"name": "SEAM_SEQ",        "from": "WIRE_SEQ",        "type": "u64",
         "comment": "source sequence number (passthrough; dedup key)"}
    ],

    # --- single-bit seam status flops. ---------------------------------------
    # SEAM_VALID/SEAM_STROBE <= pass (en=power); SEAM_DEDUP_MARK <= dup (en=power).
    "seam_status": [
        {"name": "SEAM_VALID",      "from": "pass", "type": "bit",
         "comment": "a re-stamped packet is present on the seam this cycle"},
        {"name": "SEAM_STROBE",     "from": "pass", "type": "bit",
         "comment": "1-cycle write strobe: high iff a fresh deduped packet was emitted"},
        {"name": "SEAM_DEDUP_MARK", "from": "dup",  "type": "bit",
         "comment": "1 iff the sampled packet was a DUP (dropped) — diagnostic/display"}
    ],

    "power": "NIC_POWER",
    "run": {"power": "NIC_POWER", "count": "NIC_TICKS", "limit": "NIC_RUN_UNTIL"}
}


def main():
    depth = NET["ring"]["depth"]
    if depth <= 0 or (depth & (depth - 1)) != 0:
        raise SystemExit(
            f"gen_nic_net: ring depth ({depth}) must be a power of two "
            f"(index is a branchless mask: WIRE_SEQ & (depth-1)).")
    with open("nic.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print(f"emitted nic.net.json (ring depth {depth})")


if __name__ == "__main__":
    main()
