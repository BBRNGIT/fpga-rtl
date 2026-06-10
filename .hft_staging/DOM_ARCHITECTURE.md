# DOM Architecture — Flip-Flop vs. Memory Separation

## Fundamental Principle: Independent Depth Stacks

**Bid-side and ask-side are completely independent price stacks.**

- Adding a bid at price P does **NOT** deplete or affect any ask level
- Adding an ask at price P does **NOT** deplete or affect any bid level
- Each price level (bid-side and ask-side) is a **separate, independent memory cell**
- Depth evolves by:
  1. **Accumulating quantity** at existing price levels (increment qty at same idx)
  2. **Creating new price levels** when input introduces a price not yet seen (touch new idx)
  3. **Naturally tapering** (sparse far from spread) as an **emergent pattern** from market data, not mechanical depletion

**Critical clarification:** "Depth depletion" is a misleading term. The correct term is **depth taper** — an observed empirical pattern (traders cluster near best bid/ask) that emerges from independent order placement, not a structural rule.

---

## Clear Categorization

### 1. FLIP-FLOP REGISTERS (Counters, Logic, State Machines)

These are **stateful logic** implemented as flip-flops (dff cells) with combinational updates per tick.

#### Best-of-Book Tracking (4 flip-flops)
```
┌─ BEST BID TRACKING ─────────────────────┐
│ DOM_BEST_BID_PRICE_REG    [64-bit dff]  │
│ DOM_BEST_BID_QTY_REG      [64-bit dff]  │
│                                          │
│ Logic: dff_price = (mod_bid_set | add_buy_higher) ? price : price_prev
│        dff_qty = (new_price == price) ? new_qty : qty_prev
└──────────────────────────────────────────┘

┌─ BEST ASK TRACKING ─────────────────────┐
│ DOM_BEST_ASK_PRICE_REG    [64-bit dff]  │
│ DOM_BEST_ASK_QTY_REG      [64-bit dff]  │
│                                          │
│ Logic: dff_price = (mod_ask_set | add_sell_lower) ? price : price_prev
│        dff_qty = (new_price == price) ? new_qty : qty_prev
└──────────────────────────────────────────┘
```

**Purpose:** Track the highest bid price (qty > 0) and lowest ask price (qty > 0)

**Update Rule:**
- BID: set on MODIFY with qty > 0, OR set on ADD if price > current best
- ASK: set on MODIFY with qty > 0, OR set on ADD if price < current best
- **Staleness accepted:** CANCEL at best price → dff retains old value until next ADD updates it (≤1 packet latency)

---

#### Trade Tracking (3 flip-flops)
```
┌─ LAST TRADE ────────────────────────────┐
│ DOM_LAST_TRADE_PRICE_REG  [64-bit dff]  │
│ DOM_LAST_TRADE_QTY_REG    [64-bit dff]  │
│ DOM_LAST_TRADE_SIDE_REG   [64-bit dff]  │
│                                          │
│ Logic: latch price, qty, side when is_trade = 1
└──────────────────────────────────────────┘
```

**Purpose:** Capture most recent trade execution

---

#### Global Quantity Accumulators (2 flip-flops)
```
┌─ TOTAL QUANTITIES ──────────────────────┐
│ DOM_TOTAL_BID_QTY_REG     [64-bit dff]  │
│ DOM_TOTAL_ASK_QTY_REG     [64-bit dff]  │
│                                          │
│ Logic: new_total = total + (inc*qty) - (dec*qty) + (set*qty) - (set*cur)
│        (ADD increments, CANCEL/TRADE decrements, MODIFY sets)
└──────────────────────────────────────────┘
```

**Purpose:** Running sum of all bid and ask quantities across entire book

---

#### Aggressive Side Counters (2 flip-flops)
```
┌─ AGGRESSIVE COUNTS (OFI input) ─────────┐
│ DOM_AGG_BUY_CNT_REG       [64-bit dff]  │  ← count of aggressive buys
│ DOM_AGG_SELL_CNT_REG      [64-bit dff]  │  ← count of aggressive sells
│                                          │
│ Logic: increment by 1 when is_trade fires
└──────────────────────────────────────────┘
```

**Purpose:** OFI (Order Flow Imbalance) input — aggressive buy means TRADE on buy side (hitting ask)

---

#### Cumulative Volume Delta (CVD) — Single Flip-Flop
```
┌─ CVD STATE ─────────────────────────────┐
│ DOM_TRADE_DELTA_REG       [64-bit dff]  │  ← signed accumulator
│                                          │
│ Logic: delta = prev_delta + (buy_vol) - (sell_vol)
│        Two's complement (readers apply sign extension)
└──────────────────────────────────────────┘
```

**Purpose:** Signed volume delta across all trades (buy_vol - sell_vol)

**Note:** This is **NOT** per-price. It's a single global counter.

---

#### CVD Side Accumulators (2 flip-flops) — Optional Detail
```
┌─ CVD VOLUMES (breakout detail) ─────────┐
│ DOM_CVD_BUY_VOL_REG       [64-bit dff]  │
│ DOM_CVD_SELL_VOL_REG      [64-bit dff]  │
│                                          │
│ Logic: increment on TRADE (separate accumulation of buy vs. sell volume)
│        DOM_TRADE_DELTA = buy_vol - sell_vol
└──────────────────────────────────────────┘
```

---

#### Derived Metrics (2 flip-flops)
```
┌─ DERIVED ───────────────────────────────┐
│ DOM_SPREAD_REG            [64-bit dff]  │  ← best_ask - best_bid
│ DOM_MID_PRICE_REG         [64-bit dff]  │  ← (best_bid + best_ask) >> 1
│                                          │
│ Logic: spread = valid_ask ? (ask - bid) : 0
│        mid = valid_ask ? (bid + ask) >> 1 : bid
└──────────────────────────────────────────┘
```

---

#### Event Counters (4 flip-flops)
```
┌─ STATISTICS ────────────────────────────┐
│ DOM_PKT_COUNT_REG         [64-bit dff]  │  ← all packets (is_valid)
│ DOM_ADD_COUNT_REG         [64-bit dff]  │  ← ADD events
│ DOM_CANCEL_COUNT_REG      [64-bit dff]  │  ← CANCEL events
│ DOM_TRADE_COUNT_REG       [64-bit dff]  │  ← TRADE events
│                                          │
│ Logic: increment by 1 when event fires
└──────────────────────────────────────────┘
```

---

#### Feed Timestamp Latch (1 flip-flop)
```
┌─ TIMING ────────────────────────────────┐
│ DOM_LAST_FEED_TIME_REG    [64-bit dff]  │  ← TAI timestamp of input packet
│                                          │
│ Logic: latch on valid, hold otherwise
└──────────────────────────────────────────┘
```

---

**FLIP-FLOP TOTAL: 20 × 64-bit = 20 registers**

All logic operations (comparison, MUX, ADD/SUB, gate logic) happen combinationally in the COMPUTE phase.
State updates (latching new values) happen on the rising edge (WRITE phase).

---

### 2. MEMORY (Table Storage)

These are **addressable arrays** with **no computation**. Each entry is read/written as a unit.

#### Price-Indexed Depth Tables (6 arrays)

```
┌─────────────────────────────────────────────────────────────────────┐
│  TABLE DEPTH (price-indexed, 16384 entries × 6 quantities)          │
│                                                                      │
│  idx = (price - SESSION_BASE_PRICE) / PRICE_IDX_RESOLUTION         │
│  BID SIDE and ASK SIDE are INDEPENDENT (no cross-side interaction)  │
│                                                                      │
│  For each idx:                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ DOM_BID_QTY(idx)    [64-bit memory cell]  ← qty at this bid    │ │
│  │                     (independent: unaffected by ask prices)     │ │
│  │                                                                  │ │
│  │ DOM_ASK_QTY(idx)    [64-bit memory cell]  ← qty at this ask    │ │
│  │                     (independent: unaffected by bid prices)     │ │
│  │                                                                  │ │
│  │ DOM_BUY_VOL(idx)    [64-bit memory cell]  ← footprint buy vol  │ │
│  │                     (per-price, not per-side total)             │ │
│  │                                                                  │ │
│  │ DOM_SELL_VOL(idx)   [64-bit memory cell]  ← footprint sell vol │ │
│  │                     (per-price, not per-side total)             │ │
│  │                                                                  │ │
│  │ DOM_COUNT(idx)      [64-bit memory cell]  ← event count        │ │
│  │ DOM_TIME(idx)       [64-bit memory cell]  ← time accumulated   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  TOTAL: 16384 × 6 × 64-bit = 786 KB of memory                       │
│                                                                      │
│  EVOLUTION MECHANICS:                                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Each tick, fifo_rx provides: BID_PX, ASK_PX (two sides)        │ │
│  │                                                                  │ │
│  │ BID SIDE (independent):                                         │ │
│  │  idx_bid = (BID_PX - SESSION_BASE) / TICK_SIZE                 │ │
│  │  new_bid_qty = DOM_BID_QTY[idx_bid] + incoming_qty             │ │
│  │  → DOM_BID_QTY[idx_bid] ← new_bid_qty (accumulation)           │ │
│  │  → best_bid = max(idx) with qty > 0 (independent tracking)     │ │
│  │  → Higher-priced bids UNAFFECTED by this operation             │ │
│  │  → New bid levels CREATED if new price introduced              │ │
│  │                                                                  │ │
│  │ ASK SIDE (independent):                                         │ │
│  │  idx_ask = (ASK_PX - SESSION_BASE) / TICK_SIZE                 │ │
│  │  new_ask_qty = DOM_ASK_QTY[idx_ask] + incoming_qty             │ │
│  │  → DOM_ASK_QTY[idx_ask] ← new_ask_qty (accumulation)           │ │
│  │  → best_ask = min(idx) with qty > 0 (independent tracking)     │ │
│  │  → Lower-priced asks UNAFFECTED by this operation              │ │
│  │  → New ask levels CREATED if new price introduced              │ │
│  │                                                                  │ │
│  │ Spread = best_ask - best_bid (emerges from side tracking)      │ │
│  │ Depth Taper = sparse far from spread (empirical, not mechanical)
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Operations per tick:                                                │
│  ├─ READ:   cur_bid = MEM[idx].bid_qty, cur_ask = MEM[idx].ask_qty │
│  ├─         cur_bvol = MEM[idx].buy_vol, cur_svol = MEM[idx].sell  │
│  ├─         cur_cnt = MEM[idx].count, cur_time = MEM[idx].time     │
│  │                                                                   │
│  ├─ COMPUTE: new_bid = cur_bid + qty (if BID_PX at this idx)       │
│  ├─          new_ask = cur_ask + qty (if ASK_PX at this idx)       │
│  ├─          new_bvol = cur_bvol + qty (if this is a buy trade)    │
│  ├─          new_svol = cur_svol + qty (if this is a sell trade)   │
│  ├─          new_cnt = cur_cnt + 1 (event counter)                 │
│  ├─          new_time = cur_time + 1 (ticks at level)              │
│  │                                                                   │
│  └─ WRITE:   MEM[idx] ← {new_bid, new_ask, new_bvol, new_svol,    │
│                         new_cnt, new_time}                          │
└─────────────────────────────────────────────────────────────────────┘
```

**Key distinctions:**
- **BID and ASK sides are independent** — no quantity crosses between them
- **Depth evolution = accumulation + new levels** — qty at a level increments; new prices touch new memory cells
- **Taper is emergent** — sparse deep levels because input market data clusters near spread, not because of mechanical depletion
- **Computation** (new_qty = cur_qty + incoming) happens in COMPUTE phase; **storage** (MEM[idx] ← new value) happens in WRITE phase
- **Footprint** (BUY_VOL / SELL_VOL) **is per-price, not global** — accumulates at each price level independently

---

### 3. RELAY OUTPUTS (Computed from Best Bid/Ask + Adjacent Levels)

```
┌─────────────────────────────────────────────────────────────────────┐
│  RELAY LANES (top 10 levels: 0=best, 1..9=adjacent)                 │
│                                                                      │
│  ┌─ BID SIDE ──────────────────────────────────────────────────────┐ │
│  │ DOM_REL_BID_PRICE(0..9)  ← [best, best-pip, best-2pip, ...]    │ │
│  │ DOM_REL_BID_QTY(0..9)    ← [best_qty, qty@p-1, qty@p-2, ...]   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─ ASK SIDE ──────────────────────────────────────────────────────┐ │
│  │ DOM_REL_ASK_PRICE(0..9)  ← [best, best+pip, best+2pip, ...]    │ │
│  │ DOM_REL_ASK_QTY(0..9)    ← [best_qty, qty@p+1, qty@p+2, ...]   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Each level is a register (flip-flop), updated every tick:          │
│                                                                      │
│  Logic (per tick, in COMPUTE phase):                                 │
│  ├─ rel_bid_price[0] = new_bbid_p                                   │
│  ├─ rel_bid_price[i] = new_bbid_p - (i * pip_size) for i=1..9      │
│  ├─ rel_bid_qty[i] = MEM[idx_for_price[i]].bid_qty (pre-read)      │
│  ├─ (same for ask side, opposite direction)                        │
│  │                                                                   │
│  WRITE phase: latch all 20 registers (10 bid + 10 ask)             │
│  Indicators read: dom_relay_* lanes passively (no mux delay)       │
│  └─────────────────────────────────────────────────────────────────┘
│                                                                      │
│  RELAY TOTAL: 20 × 64-bit = 20 registers (flip-flops)              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Confusion Points Clarified

### "Depletion" vs. "Taper" — Critical Semantic Fix

**OLD (misleading):** "Depth naturally depletes as you move away from the spread."

**CORRECT:** "Depth naturally tapers (sparse) as you move away from the spread."

**Why it matters:**
- **Depletion** implies a process: higher-priced bids consuming lower-priced bids as you traverse outward (FALSE)
- **Taper** describes the observed pattern: traders place fewer orders at wider prices (TRUE, emergent)
- Each price level is **independent** — no level consumes another

**The reality:** Market data shows sparse depth far from spread because:
1. Traders prefer tighter prices (less slippage)
2. Market makers place more liquidity where demand is
3. **Not** because the order book structure mechanically depletes as you go deeper

---

### "Footprint" — Was Conflated, Now Clear

**OLD confusion:** Footprint treated as global counter.  
**TRUTH:** Footprint is **per-price-level memory**.

- `DOM_BUY_VOL(idx)` — aggregate buy volume at **this specific price level** (independent of other levels)
- `DOM_SELL_VOL(idx)` — aggregate sell volume at **this specific price level** (independent of other levels)
- Updated on every incoming packet: `new_bvol = cur_bvol + qty` (increment at this level only)
- **Not** a global counter; **not** dependent on other prices

**Use case:** Footprint module reads DOM_BUY_VOL(0..15) + DOM_SELL_VOL(0..15) to draw price profile (volume at each level), then indicators (TPO, footprint chart) consume this.

---

### "CVD" vs "Trade Delta" — Global, Not Per-Price

**CVD (Cumulative Volume Delta):** Single flip-flop
- `DOM_TRADE_DELTA_REG` ← accumulated (buy_vol - sell_vol) across **all trades in entire session**
- **Global counter**, not price-indexed
- Computed as: `new_delta = old_delta + (buy_qty - sell_qty)` per tick

**CVD breakout (optional detail):**
- `DOM_CVD_BUY_VOL_REG`, `DOM_CVD_SELL_VOL_REG` — separate accumulation of total buy vs. total sell volumes (also global, not per-price)
- Allows readers to derive delta themselves: `delta = buy_total - sell_total`

**Key distinction:**
- **Footprint (DOM_BUY_VOL, DOM_SELL_VOL):** Per-price-level (one value per price)
- **CVD (DOM_TRADE_DELTA_REG):** Global (one value for entire session)

---

### "Bid/Ask Independence" — Critical for Depth Evolution

**OLD (implied in presentation):** Bid and ask side interact or influence each other.  
**CORRECT:** Bid and ask sides are **completely independent**.

**Per-tick evolution:**
- **Bid side:** Receives BID_PX, updates `DOM_BID_QTY[idx_bid] ← cur + qty`, updates `best_bid`
  - Ask prices: UNAFFECTED
  - Higher-priced bids: UNAFFECTED
  - New bid levels: CREATED if idx_bid not previously touched

- **Ask side:** Receives ASK_PX, updates `DOM_ASK_QTY[idx_ask] ← cur + qty`, updates `best_ask`
  - Bid prices: UNAFFECTED
  - Lower-priced asks: UNAFFECTED
  - New ask levels: CREATED if idx_ask not previously touched

**Spread emerges:** `spread = best_ask - best_bid` (derived from independent tracking)

---

### "Relay" — Live Output Window (Snapshot, Not Cumulative)

**NOT** memory. **NOT** computed from memory on-read.**
**IS** 20 flip-flop registers updated every tick.

Each tick:
1. **READ phase:** Pre-read 9 levels from memory for each side (async memory, no clock)
2. **COMPUTE phase:** Calculate 10 relay price/qty pairs from (best_bid/ask + 9 adjacent levels)
3. **WRITE phase:** Strobe all 20 relay registers on rising edge

Result: Indicators sample relay lanes combinationally (no mux delay) every tick.

**Critical:** Relay shows **current 10-level snapshot**, not cumulative. It updates every tick with fresh depth, including new levels created and old levels updated.

---

## Register/Memory Inventory

| Category | Count | Type | Size | Purpose |
|----------|-------|------|------|---------|
| **Flip-flop Registers** | 20 | Control logic | 1,280 bits | Best bid/ask, counters, trade state |
| **Relay Flip-flops** | 20 | Output lanes | 1,280 bits | Top 10 levels bid/ask for indicators |
| **Memory (Depth Tables)** | 6 arrays | Storage | 786 KB | Price-indexed bid/ask/volume/count/time |
| **Total Flip-flops** | 40 | | 2,560 bits | |
| **Total Memory** | 16384×6 | | 786 KB | |

---

## Proposed Rebuild (Flip-Flop Level) — Corrected for Independent Depth Evolution

### Inputs
- fifo_rx head slot: `BID_PX, ASK_PX, DEDUP_MARK, TAI_MAC, SEQ, SRC_TIME`

### Logic (20 flip-flops, independent side tracking)
1. **Best bid tracking** (2 dff): price + qty, updated independently
2. **Best ask tracking** (2 dff): price + qty, updated independently  
3. **Total qty accumulators** (2 dff): total_bid, total_ask (global, not per-price)
4. **Aggressive counters** (2 dff): agg_buy, agg_sell (global, OFI input)
5. **Trade tracking** (3 dff): last_trade_price, qty, side
6. **CVD / trade delta** (1 dff): global cumulative volume delta
7. **Event counters** (4 dff): pkt_count, add_count, cancel_count, trade_count
8. **Derived metrics** (2 dff): spread, mid_price (from best bid/ask)
9. **Feed timestamp** (1 dff): TAI latch

### Memory (6 arrays, 16384 entries each — independent per-level storage)
1. `DOM_BID_QTY[idx]` — quantity at this bid price (independent of ask)
2. `DOM_ASK_QTY[idx]` — quantity at this ask price (independent of bid)
3. `DOM_BUY_VOL[idx]` — per-price footprint (trade buy volume at this level)
4. `DOM_SELL_VOL[idx]` — per-price footprint (trade sell volume at this level)
5. `DOM_COUNT[idx]` — event count at this price
6. `DOM_TIME[idx]` — time accumulated at this price

### Relay Output (20 flip-flops — updated snapshot each tick)
- `DOM_REL_BID_PRICE(0..9)` / `DOM_REL_BID_QTY(0..9)` — best bid + 9 levels below
- `DOM_REL_ASK_PRICE(0..9)` / `DOM_REL_ASK_QTY(0..9)` — best ask + 9 levels above

### Processing per tick (independent sides, no cross-depletion)

```
BID SIDE (independent):
  idx_bid = (BID_PX - SESSION_BASE) / TICK_SIZE
  new_bid_qty = DOM_BID_QTY[idx_bid] + qty
  → Write DOM_BID_QTY[idx_bid] ← new_bid_qty (accumulation)
  → Update best_bid (if BID_PX updated best)
  → Ask prices UNAFFECTED; higher-priced bids UNAFFECTED

ASK SIDE (independent):
  idx_ask = (ASK_PX - SESSION_BASE) / TICK_SIZE
  new_ask_qty = DOM_ASK_QTY[idx_ask] + qty
  → Write DOM_ASK_QTY[idx_ask] ← new_ask_qty (accumulation)
  → Update best_ask (if ASK_PX updated best)
  → Bid prices UNAFFECTED; lower-priced asks UNAFFECTED

FOOTPRINT (per-price, not global):
  new_buy_vol = DOM_BUY_VOL[idx_bid] + qty
  new_sell_vol = DOM_SELL_VOL[idx_ask] + qty
  → Write DOM_BUY_VOL[idx_bid] ← new_buy_vol
  → Write DOM_SELL_VOL[idx_ask] ← new_sell_vol

CVD (global, not per-price):
  new_cvd = old_cvd + (buy_qty - sell_qty)
  → Write DOM_TRADE_DELTA_REG ← new_cvd

RELAY (snapshot of current 10 levels, updated every tick):
  best_bid_qty = DOM_BID_QTY[best_bid_idx]
  best_ask_qty = DOM_ASK_QTY[best_ask_idx]
  → Pre-read 9 levels below best_bid, 9 above best_ask
  → Write DOM_REL_BID_PRICE(0..9), DOM_REL_BID_QTY(0..9)
  → Write DOM_REL_ASK_PRICE(0..9), DOM_REL_ASK_QTY(0..9)

DEPTH EVOLUTION (natural, not mechanical):
  ├─ New bid at price P → DOM_BID_QTY[idx_P] incremented (new level if idx_P untouched)
  ├─ New ask at price P → DOM_ASK_QTY[idx_P] incremented (new level if idx_P untouched)
  ├─ Spread = best_ask - best_bid (emerges from independent tracking)
  └─ Depth Taper = sparse far from spread (empirical, market data clusters near spread)
```

### Address Window
- 0x2100000 (next free after fifo_rx @ 0x2000000)

### Build Method
- **Emitter script:** `gen_dom_net.py` (Python loops for 16384 price levels, 40 flip-flops, 6 memory arrays)
- **Netlist:** `dom.net.json` (validation spec, checksums circuit integrity)
- **Generated device:** `dom_gen.h` (committed, graduated, immutable)
- **Thin host glue:** `dom.c/.h` (init, display)
- **Thin test:** ≤45 lines, power-on + synthetic market data + display output

---

## Summary: Corrected Design

✅ **BID and ASK sides are independent** — no cross-depletion  
✅ **Depth evolution = accumulation + new levels** — not mechanical depletion  
✅ **Footprint is per-price** (DOM_BUY_VOL, DOM_SELL_VOL at each level)  
✅ **CVD is global** (DOM_TRADE_DELTA_REG, not per-price)  
✅ **Taper is emergent** (sparse deep levels from input market data clustering)  
✅ **Relay is snapshot** (20 flip-flops, updated every tick, shows current top 10 levels)  

---

**Ready to spawn AGT to build DOM with emitter-first workflow using this corrected architecture?**

