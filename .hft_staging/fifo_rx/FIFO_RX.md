# fifo_rx — MAC→internal async CDC FIFO (Cummings)

The clock-domain-crossing FIFO between the NIC (MAC domain, 125 MHz) and the
pipeline (internal domain, 250 MHz). The RX mirror of the OB TX FIFO Cummings
pattern. Packet-wide: one slot = one structured re-stamped nic-seam packet.

## Block diagram

```
        MAC (write) domain                          internal (read) domain
  ┌───────────────────────────┐              ┌───────────────────────────────┐
  │ nic SEAM_STROBE ─┐        │              │      ┌──> RD_EN (consumer)     │
  │  (sampled)       v        │              │      v                         │
  │  wr_fire = strobe & ~FULL │              │ rd_fire = RD_EN & ~EMPTY       │
  │        │                  │              │       │                        │
  │        v                  │              │       v                        │
  │  WR_BIN (+wr_fire) ──> WR_GRAY ──┐   ┌── RD_GRAY <── (+rd_fire) RD_BIN    │
  │        │                         │   │                     │             │
  │   slot[WR_BIN & mask] <= seam    │   │            consumer samples       │
  │        │                  ┌──────┘   └──────┐      slot[RD_BIN & mask]    │
  │        │            (write gray)     (read gray)                         │
  │        │                  v                 v                            │
  │   FULL = eqmask(   RQ1_WGRAY          WQ1_RGRAY    EMPTY = eqmask(        │
  │     WR_GRAY,            │                 │          RD_GRAY, RQ2_WGRAY)  │
  │     inv_top2(WQ2)) <─ RQ2_WGRAY      WQ2_RGRAY ─> (2-FF stable)          │
  │            (2-FF stable into read)  (2-FF stable into write)             │
  └───────────────────────────┘              └───────────────────────────────┘
```

Each pointer is sampled into the OPPOSITE domain through a 2-FF synchronizer; the
cross-domain comparison (FULL/EMPTY) only ever reads the 2-FF-stable form, never
the raw counter (no torn multi-bit read).

## Registers (window base 0x2000000)

| Register        | Domain   | Kind | Role |
|-----------------|----------|------|------|
| FIFO_POWER      | —        | cfg  | power/enable (self-run from bit0) |
| FIFO_RUN_UNTIL  | —        | cfg  | self-run tick budget |
| FIFO_RD_EN      | internal | cfg  | consumer read-enable (pop one packet) |
| FIFO_TICKS      | —        | dff  | self-run tick counter |
| FIFO_WR_BIN     | MAC      | dff  | write pointer, binary, (n+1)-bit |
| FIFO_RD_BIN     | internal | dff  | read pointer, binary, (n+1)-bit |
| FIFO_WR_GRAY    | MAC      | dff  | write pointer, gray (cross-domain form) |
| FIFO_RD_GRAY    | internal | dff  | read pointer, gray (cross-domain form) |
| FIFO_WQ1_RGRAY  | MAC      | dff  | sync stage 1: read gray into write domain |
| FIFO_WQ2_RGRAY  | MAC      | dff  | sync stage 2: stable read gray (FULL src) |
| FIFO_RQ1_WGRAY  | internal | dff  | sync stage 1: write gray into read domain |
| FIFO_RQ2_WGRAY  | internal | dff  | sync stage 2: stable write gray (EMPTY src) |
| FIFO_FULL       | MAC      | comb | wr_gray == inv_top2(WQ2_RGRAY) |
| FIFO_EMPTY      | internal | comb | rd_gray == RQ2_WGRAY |
| FIFO_WR_FIRE    | MAC      | comb | a write was honoured this edge (diag) |
| FIFO_RD_FIRE    | internal | comb | a read was honoured this edge (diag) |
| FIFO_SLOT_i_*   | RAM      | dff  | 512 slots × 8 packet lanes (packet-wide) |

Depth 512 (addr_bits 9), pointer width 10 (= addr_bits + 1). 4112 nodes total.

## Packet lanes per slot (from the nic seam)

`BID_PX, ASK_PX, TIME (TAI), SRC_TIME, SYMBOL, PIP, COMMISSION, SEQ` — the
structured re-stamped packet the NIC deposits. The nic→fifo seam carries a
structured packet, NOT raw bytes.

## Single-writer / module-barrier contract

- fifo_rx writes ONLY its own `FIFO_*` registers (pointers, syncs, flags, slots).
- fifo_rx READS the nic seam (`SEAM_*` lanes from `nic_gen.h`) as a consumer of the
  nic's published window — no private copy, no second writer.
- Each slot has exactly one writer (the write side, en = eqmask(wr_idx,i) & wr_fire);
  the read side never writes the RAM.

## Clock-domain crossing (the law)

- A multi-bit pointer crosses ONLY as gray code through a 2-FF synchronizer — never
  a raw cross-domain counter read (which would tear). Gray guarantees ≤1 bit changes
  per increment, so a metastable sample resolves to either the old or new value, both
  valid pointer states.
- FULL (write domain) and EMPTY (read domain) each compare the local pointer to the
  2-FF-stable form of the opposite pointer. FULL uses the Cummings test: the top two
  pointer bits of the synced read pointer inverted (the (n+1)-bit wrap distinguishes
  full from empty when the lower bits match).

## Build sequence (corrected law)

`gen_fifo_rx_net.py → fifo_rx.net.json → gennet.py → fifo_rx_gen.h (COMMITTED)`.
The netlist is the validation spec: the committed `fifo_rx_gen.h` byte-matches
`gennet.py fifo_rx.net.json`. Sibling `nic_gen.h`/`wire_gen.h`/`tai_cdc_gen.h` are
regenerated at build time and gitignored. Hand-written files (`fifo_rx.c/.h`,
`display.c/.h`, `test_synth.c`) contain no `cell_*()` and no `*_tick` body.

## Open decision flagged for the founder

**Address window.** The dispatch named `0x1B00000`; BUILD_PLAN.md named `0x1700000`.
Both are already owned siblings (`taiosc` = 0x1B00000, `adapter` = 0x1700000). This
build uses `0x2000000` — the next free window above the graduated clock set
(0x1700000..0x1F00000 are all taken). One-line change in the emitter if a different
address is wanted; flagged for confirmation before graduation.
