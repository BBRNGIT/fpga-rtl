#!/usr/bin/env python3
"""gen_fifo_rx_net.py — EMITTER: writes fifo_rx.net.json.

Emits the netlist for fifo_rx — the MAC->internal (pipeline) clock-domain-crossing
async FIFO (Cummings). The NIC writes a re-stamped packet into a slot on its
SEAM_STROBE (MAC domain); the pipeline reads a slot on a read-enable (internal
domain). The two pointers cross domains as GRAY code through dual 2-FF
synchronizers; FULL/EMPTY are derived from the synced opposite-domain pointer.

The device tick is GENERATED from this netlist by gennet.py — never hand-written.
Pointers are (n+1)-bit gray counters (the extra MSB distinguishes full from empty
on a power-of-two depth); slots are PACKET-WIDE (one slot = the 8 nic-seam packet
lanes, NOT raw bytes). Gray encode/decode are XOR/shift only; the 2-FF sync stages
are gated dffs; pointer step is cell_addsub; EMPTY/FULL are cell_eqmask — NO native
+/-/* in the generated tick (gate-level arithmetic law).

Module-barrier: fifo_rx SAMPLES the nic seam (SEAM_* lanes from nic_gen.h) as a
CONSUMER of the nic's published window; it writes only its own FIFO_* registers.
No private copy of the nic map.

Address window: 0x2000000. NOTE — the dispatch named 0x1B00000 and BUILD_PLAN.md
named 0x1700000; BOTH are already owned siblings (taiosc=0x1B00000, adapter=
0x1700000). 0x2000000 is the next free window above the graduated clock set
(0x1700000..0x1F00000 are all taken). Flagged for the founder to confirm; the
window base is a one-line change here if a different address is wanted.
"""
import json

# FIFO depth — MUST be a power of two (slot index is a branchless mask:
# ptr_bin & (depth-1)). gennet asserts this at generate time.
DEPTH = 512
# pointer width: log2(DEPTH) address bits + 1 wrap bit (Cummings: the extra MSB
# lets FULL be distinguished from EMPTY when the two pointers are otherwise equal).
ADDR_BITS = DEPTH.bit_length() - 1          # 9  (512 = 2**9)
PTR_BITS = ADDR_BITS + 1                     # 10 pointer bits (binary), gray same width

# the 8 packet lanes carried per slot — the nic seam's structured re-stamped packet
# (SEAM_* lanes). One slot stores all eight; the FIFO is packet-wide, not byte-wide.
PACKET_LANES = [
    "BID_PX", "ASK_PX", "TIME", "SRC_TIME",
    "SYMBOL", "PIP", "COMMISSION", "SEQ",
]
# the nic seam source lane for each carried packet lane (module-barrier read).
SEAM_SRC = {ln: f"SEAM_{ln}" for ln in PACKET_LANES}

NET = {
    "device": "fifo_rx",
    "window_base": "0x2000000",
    "kind": "cdc_fifo",
    "depth": DEPTH,
    "addr_bits": ADDR_BITS,
    "ptr_bits": PTR_BITS,
    "comment": (
        "fifo_rx — MAC->internal async CDC FIFO (Cummings). Write side (MAC): on "
        "the nic SEAM_STROBE, store the re-stamped packet into the slot at the "
        "write pointer and advance the write pointer. Read side (internal): on a "
        "read-enable while ~EMPTY, advance the read pointer (the consumer samples "
        "the slot at the read pointer). Pointers cross domains as gray code through "
        "dual 2-FF synchronizers; FULL is derived in the write domain from the "
        "synced read pointer, EMPTY in the read domain from the synced write "
        "pointer. Packet-wide slots: one slot = one structured re-stamped packet."
    ),

    # --- the nic seam lanes fifo_rx SAMPLES (read from nic_gen.h — the nic's
    # canonical window; not redeclared as fifo_rx nodes). Listed here for the
    # generator's READ phase + the validator's module-barrier cross-check. --------
    "seam_inputs": [SEAM_SRC[ln] for ln in PACKET_LANES] + ["SEAM_STROBE"],

    # --- config / input lanes (set once by the starter). ----------------------
    # Power runs the FIFO on its clock edge. The read-enable is a per-edge input
    # the pipeline asserts to pop a packet (config lane the consumer drives).
    "config_nodes": [
        {"name": "FIFO_POWER", "type": "bit",
         "comment": "power/enable: the FIFO self-runs on its clock edge while bit0 = 1 (set once)"},
        {"name": "FIFO_RUN_UNTIL", "type": "u64",
         "comment": "configured self-run tick budget (set once by starter)"},
        {"name": "FIFO_RD_EN", "type": "bit",
         "comment": "read-enable: the pipeline consumer asserts this to pop one packet "
                    "(advance the read pointer). Input lane the consumer drives; "
                    "honoured only while ~EMPTY (no underflow)."}
    ],

    # --- registered state (dffs), all fifo_rx-owned. --------------------------
    # Two binary pointers (the canonical count), their gray forms, the dual 2-FF
    # synchronizer stages, and the self-run tick counter.
    "dff_nodes": [
        {"name": "FIFO_TICKS", "type": "u64",
         "comment": "self-run tick counter (run-loop bookkeeping; bounds the self-run)"},
        {"name": "FIFO_WR_BIN", "type": "u64",
         "comment": "write pointer, BINARY (MAC domain). (n+1)-bit; advances on a "
                    "honoured write (nic SEAM_STROBE & ~FULL)."},
        {"name": "FIFO_RD_BIN", "type": "u64",
         "comment": "read pointer, BINARY (internal domain). (n+1)-bit; advances on "
                    "a honoured read (FIFO_RD_EN & ~EMPTY)."},
        {"name": "FIFO_WR_GRAY", "type": "u64",
         "comment": "write pointer, GRAY (the cross-domain form synced into the read "
                    "domain). Only 1 bit changes per increment — metastability-safe."},
        {"name": "FIFO_RD_GRAY", "type": "u64",
         "comment": "read pointer, GRAY (the cross-domain form synced into the write "
                    "domain). Only 1 bit changes per increment."},
        {"name": "FIFO_WQ1_RGRAY", "type": "u64",
         "comment": "sync stage 1: read gray pointer captured in the WRITE domain "
                    "(catches the metastability window). 2-FF: this is FF #1."},
        {"name": "FIFO_WQ2_RGRAY", "type": "u64",
         "comment": "sync stage 2: stable read gray pointer in the WRITE domain. "
                    "FULL is derived from this (the only safe read-side pointer here)."},
        {"name": "FIFO_RQ1_WGRAY", "type": "u64",
         "comment": "sync stage 1: write gray pointer captured in the READ domain. 2-FF FF #1."},
        {"name": "FIFO_RQ2_WGRAY", "type": "u64",
         "comment": "sync stage 2: stable write gray pointer in the READ domain. "
                    "EMPTY is derived from this (the only safe write-side pointer here)."}
    ],

    # --- combinational outputs (the device's derived writes). ------------------
    "comb_nodes": [
        {"name": "FIFO_FULL", "type": "bit",
         "comment": "FULL (write domain): wr_gray == rq-of-rd_gray with the top TWO "
                    "bits inverted (Cummings). High => no honoured write this edge."},
        {"name": "FIFO_EMPTY", "type": "bit",
         "comment": "EMPTY (read domain): rd_gray == synced write gray (cell_eqmask). "
                    "High => no honoured read this edge."},
        {"name": "FIFO_WR_FIRE", "type": "bit",
         "comment": "1 iff a write was honoured this edge (SEAM_STROBE & ~FULL) — "
                    "diagnostic/display."},
        {"name": "FIFO_RD_FIRE", "type": "bit",
         "comment": "1 iff a read was honoured this edge (FIFO_RD_EN & ~EMPTY) — "
                    "diagnostic/display. The popped slot index is rd_bin & (depth-1)."}
    ],

    # --- packet-wide slot RAM: depth slots, each carrying the 8 nic-seam lanes.
    # Single-writer: only the write side latches a slot (en = wr_fire & at-this-idx).
    "ram": {
        "depth": DEPTH,
        "addr_bits": ADDR_BITS,
        "slot_prefix": "FIFO_SLOT",          # FIFO_SLOT_<i>_<LANE>
        "lanes": PACKET_LANES,
        "wr_index_from": "FIFO_WR_BIN",      # write slot = wr_bin & (depth-1)
        "rd_index_from": "FIFO_RD_BIN",      # read slot  = rd_bin & (depth-1)
        "comment": ("packet-wide dual-port RAM: one slot = the 8 nic-seam packet "
                    "lanes. Write port (MAC): slot[wr_bin & mask] <= seam lanes on "
                    "wr_fire. Read port (internal): the consumer samples "
                    "slot[rd_bin & mask]. Single-writer per slot (write side only); "
                    "the read side never writes the RAM.")
    },

    # --- the gray/sync/full/empty/advance wiring the gennet consumes. ----------
    "write_side": {
        "bin": "FIFO_WR_BIN", "gray": "FIFO_WR_GRAY",
        "fire_from": "SEAM_STROBE",          # nic seam write strobe (gated by ~FULL)
        "full": "FIFO_FULL",
        "sync1": "FIFO_WQ1_RGRAY", "sync2": "FIFO_WQ2_RGRAY",
        "sync_from": "FIFO_RD_GRAY"          # synchronize the READ gray into write domain
    },
    "read_side": {
        "bin": "FIFO_RD_BIN", "gray": "FIFO_RD_GRAY",
        "fire_from": "FIFO_RD_EN",           # consumer read-enable (gated by ~EMPTY)
        "empty": "FIFO_EMPTY",
        "sync1": "FIFO_RQ1_WGRAY", "sync2": "FIFO_RQ2_WGRAY",
        "sync_from": "FIFO_WR_GRAY"          # synchronize the WRITE gray into read domain
    },
    "fire": {"write": "FIFO_WR_FIRE", "read": "FIFO_RD_FIRE"},

    "power": "FIFO_POWER",
    "run": {"power": "FIFO_POWER", "count": "FIFO_TICKS", "limit": "FIFO_RUN_UNTIL"}
}


def main():
    if DEPTH <= 0 or (DEPTH & (DEPTH - 1)) != 0:
        raise SystemExit(
            f"gen_fifo_rx_net: depth ({DEPTH}) must be a power of two "
            f"(slot index is a branchless mask: ptr_bin & (depth-1)).")
    with open("fifo_rx.net.json", "w") as f:
        json.dump(NET, f, indent=2)
        f.write("\n")
    print(f"emitted fifo_rx.net.json (depth {DEPTH}, {PTR_BITS}-bit gray pointers, "
          f"{len(PACKET_LANES)} lanes/slot)")


if __name__ == "__main__":
    main()
