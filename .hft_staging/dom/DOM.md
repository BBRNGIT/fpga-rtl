# DOM — Depth-of-Market (design doc, step 1)

Built flip-flop-level from the netlist generator (emitter-first). Device logic is
GENERATED into `dom_gen.h` by `gennet.py` from `dom.net.json` — never hand-written.
Source spec: `.hft_staging/DOM_PARTS_LIST.md` (the named authoritative parts list).

## Role

DOM is the first pipeline-domain (internal-clock) consumer past the CDC FIFO. Each
device edge it samples the `fifo_rx` head slot (the next packet the pipeline would
pop), gated by `fifo_rx`'s read-fire, and maintains the order book: price-indexed
qty/count/time tables, best-bid/ask tracking, running totals, derived spread/mid,
diagnostic event counters, and the 10-level relay ladders that the indicators read.

## Module-barrier contract (single-writer / consumer of published window)

- DOM SAMPLES the `fifo_rx` published window (the head slot at the read pointer +
  the read-fire / empty flags). It reads those lanes from `fifo_rx_gen.h` — it does
  NOT declare a private copy of the FIFO map (that would be a second writer).
  This mirrors: nic samples WIRE_* (wire window); fifo_rx samples SEAM_* (nic
  window). DOM samples the FIFO head slot (fifo_rx window).
- DOM writes ONLY its own window (DOM_* registers + the four tables).
- Indicators read DOM's RELAY/BEST/derived lanes — NOT DOM's internal tables or
  PREV state (barrier on the downstream side).

## FLAGGED open decisions (surfaced, not silently chosen)

1. **No fixed `FIFO_RX_HEAD_*` lanes exist on the producer.** PARTS_LIST §1 names
   `FIFO_RX_HEAD_BID_PX` etc. as DOM's inputs, but `fifo_rx` does NOT publish
   fixed-named head lanes — its head slot is reached at runtime via the generated
   `fifo_rx_head_addr(r, lane_ofs)` helper (the slot RAM at RD_BIN & mask). DECISION
   (faithful to the published interface): DOM's generated tick takes the fifo_rx
   register window as a second pointer (`const word_t *fifo`, exactly as fifo_rx
   takes `const word_t *nic`) and reads each head lane through the producer's own
   generated address helper, gated by `FIFO_FIFO_RD_FIRE`. No private FIFO copy.
   The packet "consumed" by DOM is the head slot on the cycle the FIFO fires a read.

2. **Address window: 0x2100000, NOT 0x0C00000.** PARTS_LIST §12 names 0x0C00000
   but marks it "exact value TBD per backplane allocation." 0x2100000 is the actual
   next-free window above the graduated `fifo_rx` @ 0x2000000 (every window below is
   an owned sibling). DOM_ARCHITECTURE.md §"Address Window" independently names
   0x2100000. Using 0x2100000; flag if the founder wants the PARTS_LIST literal.

3. **PARTS_LIST supersedes DOM_ARCHITECTURE on the trade/CVD model.** PARTS_LIST is
   the named spec and the newer file; it explicitly states "no trade inference",
   marks `DOM_TRADE_COUNT_REG` "KEPT FOR API COMPAT, NOT USED", and models qty as
   presence (0=clear, 1=increment) driven by branchless delta detection — NOT the
   `qty += incoming_qty` accumulation / CVD / aggressive-side model in
   DOM_ARCHITECTURE.md. BUILDING THE PARTS_LIST MODEL. The 6-table /
   CVD / footprint additions in DOM_ARCHITECTURE are NOT built (no `incoming_qty`
   lane exists on the price-only wire; no trade/side ghost values — data law).

4. **Table size is a generate-time constant (default 16384), accessed by ADDRESS,
   not per-cell unrolled.** A faithful price-indexed table is single-writer addressed
   RAM (one index touched per tick). Fully unrolling 16384 levels × 4 tables into
   per-cell muxes is neither 4ns-realizable (a 16384:1 mux) nor buildable (a ~60MB
   header). DECISION: the four tables are flat addressed regions; the tick computes
   the price index by mask (address math, like `fifo_rx_head_addr`'s `idx*lanes`)
   and reads/writes the addressed cell with gate-level `cell_addsub`/`cell_mux`. The
   per-cell single-writer guarantee holds (one index written per side per tick); the
   index is the only native index/address math (outside the data-path operator ban,
   same dispensation cells.h already takes for its loop counter).

## Inputs (sampled from the fifo_rx published window, §1)

Read via `fifo_rx_head_addr(fifo, OFS)` (lane order = fifo_rx PACKET_LANES):
BID_PX(0), ASK_PX(1), TIME(2)→TAI, SRC_TIME(3), SYMBOL(4), PIP(5), COMMISSION(6),
SEQ(7); plus `FIFO_FIFO_RD_FIRE` (consume gate) and `FIFO_FIFO_EMPTY` (validity).

## Outputs (DOM-owned window; §3–§9 of the parts list)

Scalars: BEST_BID_PRICE/QTY, BEST_ASK_PRICE/QTY, TOTAL_BID_QTY, TOTAL_ASK_QTY,
SPREAD, MID_PRICE, PKT_COUNT, ADD_COUNT, CANCEL_COUNT, TRADE_COUNT(=0),
LAST_FEED_TIME, PREV_BID_PRICE, PREV_ASK_PRICE (internal state).
Relay: REL_BID_PRICE[0..9], REL_BID_QTY[0..9], REL_ASK_PRICE[0..9],
REL_ASK_QTY[0..9].
Tables (addressed, depth N): DOM_BID_QTY[N], DOM_ASK_QTY[N], DOM_COUNT[N],
DOM_TIME[N].

## READ → COMPUTE → WRITE (all branchless / gate-level)

- READ: head lanes (gated by RD_FIRE), prev bid/ask, the addressed table cells at
  the bid/ask price indices, the relay candidate cells.
- COMPUTE (mask algebra only): `consume = RD_FIRE & ~EMPTY`;
  `bid_changed = ~eqmask(head_bid, prev_bid) & consume`;
  `ask_changed = ~eqmask(head_ask, prev_ask) & consume`; price→index by mask;
  table updates via `cell_addsub` (presence model: set 1 / clear 0 per spec §2);
  best-price `cell_mux` on changed; totals via `cell_addsub`; spread/mid via
  `cell_addsub`+shift guarded by ask-valid; relay ladder candidates best±(i+1)*pip.
- WRITE (write-only): tables at the two indices, best regs, totals, derived, relay
  20, counters, last-feed-time, prev state.

## Clock / domain

Internal (pipeline) domain. No CDC inside DOM (the MAC→internal crossing already
happened in fifo_rx). DOM self-runs from a power bit, bounded by a config tick
budget (`dom_run`), like every component.

## Files (mirror fifo_rx)

`gen_dom_net.py` (emitter) → `dom.net.json` (committed netlist) → `gennet.py` →
`dom_gen.h` (COMMITTED + graduated). Hand-written glue only: `dom.c/.h` (starter),
`display.c/.h` (raw lane print), `test_synth.c` (≤45 lines, power-on + display),
`Makefile`, `validate.py`, `.gitignore` (does NOT ignore `dom_gen.h`).
</content>
</invoke>
