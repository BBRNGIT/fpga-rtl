# DOM Architectural Parts List

**Purpose:** Hardware specification for building the DOM (Depth-of-Market) component flip-flop-level from the netlist-generator (emitter-first workflow).

**Input to:** `gen_dom_net.py` (emitter script) → `dom.net.json` (netlist) → `gennet.py` → `dom_gen.h` (generated device code)

**Date:** 2026-06-08  
**Status:** Parts list complete; ready for emitter implementation

---

## 1. INPUT INTERFACE (from FIFO_RX)

Consumed from FIFO_RX head slot when `RD_FIRE` strobes:

- `FIFO_RX_HEAD_BID_PX` — 64-bit fixed-point bid price
- `FIFO_RX_HEAD_ASK_PX` — 64-bit fixed-point ask price
- `FIFO_RX_HEAD_SEQ` — packet sequence number
- `FIFO_RX_HEAD_TAI` — timestamp value
- `FIFO_RX_HEAD_SYMBOL` — symbol ID
- `FIFO_RX_HEAD_PIP` — pip resolution
- `FIFO_RX_HEAD_COMMISSION` — commission value
- `FIFO_RX_EMPTY` — FIFO empty flag (read gate)

---

## 2. PRICE-INDEXED MEMORY TABLES (Primary Accumulators)

Each indexed by `PRICE_IDX = (price - SESSION_BASE_PRICE) / PRICE_IDX_RESOLUTION`.

### Per-Level Quantity & Count Storage

```
DOM_BID_QTY[16384]     — 64-bit flip-flop counters
                         Fed by: cell_addsub (accumulator)
                         Input: bid_qty_update (0=clear, 1=increment)
                         Logic: if update==1 then += 1, else = 0

DOM_ASK_QTY[16384]     — 64-bit flip-flop counters
                         Fed by: cell_addsub
                         Input: ask_qty_update (0=clear, 1=increment)
                         Logic: if update==1 then += 1, else = 0

DOM_COUNT[16384]       — 64-bit event-counter flip-flops
                         Fed by: cell_addsub (increment)
                         Input: event_valid (strobe on any price-level event)
                         Logic: if valid then += 1

DOM_TIME[16384]        — 64-bit timestamp/tick flip-flops
                         Fed by: cell_mux (latch latest)
                         Input: current_tai
                         Logic: on any level event, latch TAI; persist
```

**Hardware per level (×16384 parallel):**
- **BID_QTY[i]:**
  - Input gate: `bid_modified_at_i = (PRICE_IDX(old_bid)==i) | (PRICE_IDX(new_bid)==i)`
  - Update value: `if PRICE_IDX(new_bid)==i then 1 else 0` (ternary MUX)
  - Accumulator: current_qty + update_value (with saturation guard)

- **ASK_QTY[i]:** similar for ask

- **COUNT[i]:**
  - Incremented if level i touched (bid or ask moved into/out of it)

- **TIME[i]:**
  - Latched with TAI value when level i touched

---

## 3. BEST-PRICE REGISTERS (Eager Tracking)

### Bid Side
```
DOM_BEST_BID_PRICE_REG  — 64-bit flip-flop
                          Updated on: bid price changed
                          Logic: cell_mux(bid_changed, FIFO_RX_HEAD_BID_PX, current)
                          New value = current BID from FIFO_RX

DOM_BEST_BID_QTY_REG    — 64-bit flip-flop
                          Latches: DOM_BID_QTY[PRICE_IDX(DOM_BEST_BID_PRICE_REG)]
                          Updated on: best_bid_price changed
```

### Ask Side
```
DOM_BEST_ASK_PRICE_REG  — 64-bit flip-flop (init = DOM_NO_ASK sentinel)
                          Updated on: ask price changed
                          Logic: cell_mux(ask_changed, FIFO_RX_HEAD_ASK_PX, current)
                          New value = current ASK from FIFO_RX

DOM_BEST_ASK_QTY_REG    — 64-bit flip-flop
                          Latches: DOM_ASK_QTY[PRICE_IDX(DOM_BEST_ASK_PRICE_REG)]
                          Updated on: best_ask_price changed
```

---

## 4. RUNNING TOTALS (Sum Accumulators)

```
DOM_TOTAL_BID_QTY_REG   — 64-bit accumulator
                          Computed: sum(DOM_BID_QTY[i] for all i)
                          Updated: every tick (parallel tree of cell_addsub)
                          Stages: log2(16384) ≈ 14 stages (may pipeline across ticks)

DOM_TOTAL_ASK_QTY_REG   — 64-bit accumulator
                          Computed: sum(DOM_ASK_QTY[i] for all i)
```

---

## 5. DERIVED REGISTERS (Non-Blocking, Combinational)

```
DOM_SPREAD_REG          — 64-bit
                          Logic: cell_addsub(DOM_BEST_ASK_PRICE_REG - DOM_BEST_BID_PRICE_REG)
                          Guard: only valid if DOM_BEST_ASK_PRICE_REG != DOM_NO_ASK

DOM_MID_PRICE_REG       — 64-bit
                          Logic: (DOM_BEST_BID_PRICE_REG + DOM_BEST_ASK_PRICE_REG) >> 1
                          Via: cell_addsub + shift (or dedicated cell_mux for rounding)
                          Guard: only computed if DOM_BEST_ASK_PRICE_REG != DOM_NO_ASK
```

---

## 6. EVENT COUNTERS (Diagnostic)

```
DOM_PKT_COUNT_REG       — 64-bit accumulator
                          Increments: on every valid packet from FIFO_RX
                          Logic: cell_addsub(pkt_valid)

DOM_ADD_COUNT_REG       — 64-bit accumulator
                          Increments: when any level's qty increased (update==1)
                          Logic: tracks count of ADD-like events (bid/ask new prices set)

DOM_CANCEL_COUNT_REG    — 64-bit accumulator
                          Increments: when any level's qty decreased/cleared (update==0 and prior qty > 0)
                          Logic: tracks count of CANCEL-like events (bid/ask old prices cleared)

DOM_TRADE_COUNT_REG     — 64-bit accumulator (KEPT FOR API COMPAT, NOT USED)
                          Always 0 in new model (no trade inference)
```

---

## 7. METADATA

```
DOM_LAST_FEED_TIME_REG  — 64-bit flip-flop
                          Latches: FIFO_RX_HEAD_TAI
                          Updated: on every valid packet
```

---

## 8. RELAY OUTPUTS (Downstream Feed for Indicators)

### Relative Bid Ladder (10 levels, 0=best)
```
DOM_REL_BID_PRICE[0..9]   — 10 price registers (64-bit each)
                             REL_BID_PRICE[i] = BEST_BID_PRICE - (i+1) * PIP_RESOLUTION
                             (guard: underflow → zero)

DOM_REL_BID_QTY[0..9]      — 10 qty registers (64-bit each)
                             REL_BID_QTY[i] = DOM_BID_QTY[PRICE_IDX(REL_BID_PRICE[i])]
```

### Relative Ask Ladder (10 levels, 0=best)
```
DOM_REL_ASK_PRICE[0..9]   — 10 price registers (64-bit each)
                             REL_ASK_PRICE[i] = BEST_ASK_PRICE + (i+1) * PIP_RESOLUTION
                             (guard: overflow → max uint64)

DOM_REL_ASK_QTY[0..9]      — 10 qty registers (64-bit each)
                             REL_ASK_QTY[i] = DOM_ASK_QTY[PRICE_IDX(REL_ASK_PRICE[i])]
```

**Pre-read logic (READ phase):**
- Compute 10 candidate price levels (best ± 1..9 pips)
- Check bounds (not below SESSION_BASE or above sentinel)
- Read all 10 QTY values from tables (in parallel)

**Write logic (WRITE phase):**
- Write all 20 registers (10 price + 10 qty)

---

## 9. INTERNAL STATE (Previous Price Tracking)

```
DOM_PREV_BID_PRICE      — 64-bit flip-flop (internal, not relay)
                          Stores: BID price from previous tick
                          Used for: delta detection (bid_changed = curr != prev)
                          Updated: at end of tick

DOM_PREV_ASK_PRICE      — 64-bit flip-flop (internal)
                          Stores: ASK price from previous tick
                          Used for: delta detection (ask_changed = curr != prev)
                          Updated: at end of tick
```

---

## 10. INFERRED EVENT SIGNALS (Branchless Delta Detection)

These are computed in COMPUTE phase and drive the accumulator updates:

```
bid_changed             — bitfield (1 if curr_bid != prev_bid, 0 otherwise)
                          Logic: cell_eqmask(FIFO_RX_HEAD_BID_PX != DOM_PREV_BID_PRICE)

ask_changed             — bitfield (1 if curr_ask != prev_ask, 0 otherwise)
                          Logic: cell_eqmask(FIFO_RX_HEAD_ASK_PX != DOM_PREV_ASK_PRICE)

bid_modified_at_old     — 1-hot or multi-hot mux (which level had old bid price)
                          Logic: if bid_changed then idx = PRICE_IDX(DOM_PREV_BID_PRICE)

bid_modified_at_new     — 1-hot or multi-hot mux (which level has new bid price)
                          Logic: if bid_changed then idx = PRICE_IDX(FIFO_RX_HEAD_BID_PX)

ask_modified_at_old     — similar
ask_modified_at_new     — similar
```

---

## 11. CONTROL SIGNALS

```
RD_FIRE (input)         — Strobe from FIFO_RX; gates all DOM updates
                          When RD_FIRE==1: consume packet, update all tables
                          When RD_FIRE==0: hold state, pass through to relay

FIFO_RX_EMPTY (input)   — FIFO empty flag; gates validity
                          When EMPTY==1: no packet available
```

---

## 12. ADDRESS WINDOW LAYOUT

```
DOM Base Address: 0x0C00000 (reserved window; exact value TBD per backplane allocation)

Register Offsets (first 64 KB for scalar outputs; rest for tables):

  Scalar Registers (each 8 bytes):
  0x0000 — DOM_BEST_BID_PRICE_REG
  0x0008 — DOM_BEST_BID_QTY_REG
  0x0010 — DOM_BEST_ASK_PRICE_REG
  0x0018 — DOM_BEST_ASK_QTY_REG
  0x0020 — DOM_TOTAL_BID_QTY_REG
  0x0028 — DOM_TOTAL_ASK_QTY_REG
  0x0030 — DOM_SPREAD_REG
  0x0038 — DOM_MID_PRICE_REG
  0x0040–0x0088 — DOM_REL_BID_PRICE[0..9] (8 bytes each)
  0x0090–0x00D8 — DOM_REL_BID_QTY[0..9]
  0x00E0–0x0128 — DOM_REL_ASK_PRICE[0..9]
  0x0130–0x0178 — DOM_REL_ASK_QTY[0..9]
  0x0180–0x01F8 — DOM_PKT_COUNT_REG / ADD_COUNT_REG / CANCEL_COUNT_REG / TRADE_COUNT_REG
  0x0200 — DOM_LAST_FEED_TIME_REG

  Internal State (not relay):
  0x0208 — DOM_PREV_BID_PRICE
  0x0210 — DOM_PREV_ASK_PRICE

  Price-Indexed Tables (sparse, indexed by PRICE_IDX):
  0x10000 onwards — DOM_BID_QTY[16384] (sparse or dense; TBD)
  0x200000 onwards — DOM_ASK_QTY[16384]
  0x400000 onwards — DOM_COUNT[16384]
  0x600000 onwards — DOM_TIME[16384]
```

---

## 13. DATAFLOW SUMMARY

```
FIFO_RX head slot (BID, ASK, SEQ, TAI, SYMBOL, PIP, COMMISSION)
  ↓ [RD_FIRE gates consumption]
  ↓
[Delta Detection]
  bid_changed = (FIFO_RX_HEAD_BID_PX != DOM_PREV_BID_PRICE)
  ask_changed = (FIFO_RX_HEAD_ASK_PX != DOM_PREV_ASK_PRICE)
  ↓
[MODIFY Events Inferred by tick_adapter]
  If bid_changed:
    MODIFY(PRICE_IDX(DOM_PREV_BID_PRICE), qty=0) → decrement DOM_BID_QTY[idx]
    MODIFY(PRICE_IDX(FIFO_RX_HEAD_BID_PX), qty=1) → increment DOM_BID_QTY[idx]
  If ask_changed:
    MODIFY(PRICE_IDX(DOM_PREV_ASK_PRICE), qty=0) → decrement DOM_ASK_QTY[idx]
    MODIFY(PRICE_IDX(FIFO_RX_HEAD_ASK_PX), qty=1) → increment DOM_ASK_QTY[idx]
  ↓
[Per-Level Updates]
  For each MODIFY:
    DOM_BID_QTY[idx] += or -= 1 (via cell_addsub, mux on qty direction)
    DOM_COUNT[idx]++ (via cell_addsub)
    DOM_TIME[idx] = FIFO_RX_HEAD_TAI (via cell_mux)
  ↓
[Best-Price Tracking]
  DOM_BEST_BID_PRICE ← FIFO_RX_HEAD_BID_PX (if bid_changed)
  DOM_BEST_ASK_PRICE ← FIFO_RX_HEAD_ASK_PX (if ask_changed)
  DOM_BEST_BID_QTY ← DOM_BID_QTY[PRICE_IDX(DOM_BEST_BID_PRICE)]
  DOM_BEST_ASK_QTY ← DOM_ASK_QTY[PRICE_IDX(DOM_BEST_ASK_PRICE)]
  ↓
[Running Totals]
  DOM_TOTAL_BID_QTY = sum(DOM_BID_QTY[all]) (parallel tree)
  DOM_TOTAL_ASK_QTY = sum(DOM_ASK_QTY[all])
  ↓
[Derived Outputs]
  DOM_SPREAD = DOM_BEST_ASK_PRICE - DOM_BEST_BID_PRICE
  DOM_MID_PRICE = (DOM_BEST_BID_PRICE + DOM_BEST_ASK_PRICE) >> 1
  ↓
[Relay Ladder (10 levels per side)]
  For i=0..9:
    DOM_REL_BID_PRICE[i] = DOM_BEST_BID_PRICE - (i+1)*PIP_RES
    DOM_REL_BID_QTY[i] = DOM_BID_QTY[PRICE_IDX(DOM_REL_BID_PRICE[i])]
    (similar for ask)
  ↓
[Downstream Consumers]
  → footprint (reads DOM_BID_QTY, DOM_ASK_QTY, DOM_COUNT, DOM_TIME tables)
  → tpo (reads DOM_TIME table)
  → fractal (reads DOM_REL_BID/ASK lanes)
  → cbr (reads DOM_REL_BID/ASK lanes, DOM_BEST_BID/ASK)
  → strategy (reads DOM_BEST_BID/ASK, DOM_SPREAD, DOM_MID_PRICE)
```

---

## 14. ARCHITECTURAL CONSTRAINTS

### Gate-Level Arithmetic (CLAUDE.md §2)

All datapath operations must be structural cells, **NO native C operators** in generated tick:

- **Increment/Decrement:** `cell_addsub(qty, delta_mux)` — ripple-carry adder chain
  - No native `++` or `+=`
  
- **Comparison:** `cell_eqmask(a != b)` — equality comparator
  - No native `==` or `!=`

- **Selection:** `cell_mux(sel, a, b)` — 2-to-1 or N-to-1 mux
  - No native `?:` ternary operator

- **Summation tree:** `cell_addsub` parallel stages for totals
  - No native `+` in a loop

### Module Barrier Law (CLAUDE.md §3)

- DOM reads from **FIFO_RX's published lanes** (head slot), NOT FIFO_RX internals
- DOM writes only to **its own window** (0x0C00000+)
- Indicators read from **DOM's relay lanes** (REL_*, BEST_*, derived), NOT DOM internals (COUNT, TIME, full tables)

### Branchless Data Path (CLAUDE.md §4)

- No `if`/`else` in COMPUTE phase → all logic is ternary `cell_mux`
- No loops over bits → use `__builtin_popcount` (not applicable here, but rule applies)
- No nested conditionals → flatten with bitwise boolean algebra
- No function calls in tick → all inline as cell chains

### Clock Domain (CLAUDE.md §5)

- DOM runs in **internal clock domain** (250 MHz pipeline FPGA)
- Receives packets from **FIFO_RX read side** (already crossed from MAC → internal)
- No CDC needed within DOM (single clock domain)

### Read→Compute→Write Phases (CLAUDE.md §6)

```c
CLOCK_PHASE_READ
  // Pre-read FIFO_RX_HEAD_* and all DOM_*_QTY values needed for ladder
  // Compute deltas, indices, ladder positions
  
CLOCK_PHASE_COMPUTE
  // All delta detection, table index computation, mux logic for updates
  // No REG_R calls here; use pre-read values
  
CLOCK_PHASE_WRITE
  // Write all updated registers (tables, best-price, ladder, counters, state)
  // No REG_R calls in WRITE phase
```

---

## 15. COMMIT EXPECTATIONS

**Deliverables (emitter-first workflow):**

1. **`gen_dom_net.py`** — Python emitter script
   - Input: this parts list (or hardcoded logic matching it)
   - Output: `dom.net.json` (declarative netlist)
   - Loops over 16384 price levels, declares accumulators, comparators, muxes

2. **`dom.net.json`** — Declarative netlist (committed to git)
   - Validates: single-writer (one accumulator per level), no overlap, no floating
   - Checksums circuit; used to verify `dom_gen.h` integrity

3. **`dom_gen.h`** — Generated device code (COMMITTED to git, not gitignored)
   - Output of `gennet.py dom.net.json`
   - Contains `dom_tick()` function (branchless, structural cells only)
   - Pre-commit hook confirms no hand-written `cell_*()` in source files

4. **`dom.c` / `dom.h`** — Non-device glue
   - `dom_init()` — initialize tables, reset registers
   - Display helper (thin, power-on + register dump)
   - Test harness (thin: ≤45 lines, power-on only, no orchestration)

5. **`Makefile`** — Build DOM component
   - Runs `gen_dom_net.py` → netlist
   - Runs `gennet.py` → device code
   - Compiles and validates

---

**Status:** ✅ **Parts list complete; ready for emitter implementation.**

Next step: Dispatch `netlist-builder` subagent with this specification to generate `gen_dom_net.py` → `dom.net.json` → `dom_gen.h` (graduated).

