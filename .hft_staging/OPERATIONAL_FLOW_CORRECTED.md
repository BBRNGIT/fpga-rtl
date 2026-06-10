# Operational Flow (Corrected) — Independent Clocks, Per-Module Subscription

## System Clock Model: 5 Independent Oscillators

```
┌──────────────────┐
│ TAIOSC           │  Authoritative oscillator (GNSS equivalent)
│ (independent ref)│  • Free-running, no discipline
│ ~1–100 GHz       │  • Only reference for TAI counter
└────────┬─────────┘
         │ increments continuously
         ▼
┌──────────────────┐
│ TAI              │  Plain counter off TAIOSC
│ (independent)    │  • Increments every TAIOSC cycle
│ (timestamp)      │  • No PLL, no discipline, no fast-forward
└────────┬─────────┘
         │ Gray-code CDC (2-FF)
         │ because TAI and MAC are independent
         │
    ┌────┴──────────────┐
    │                   │
    ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│ TAI_MAC          │  │ MAC              │
│ (in MAC domain)  │  │ (independent ref)│
│ (stable, stage2) │  │ 125 MHz          │
│ (frozen snapshot)│  │ NIC sample clock │
└──────────────────┘  └────────┬─────────┘
                               │
                        Increments @ 125 MHz

┌──────────────────┐
│ INTERNAL         │  Independent reference, 250 MHz
│ (independent ref)│  Pipeline clock domain
│ 250 MHz          │  Increments independently
└──────────────────┘

┌──────────────────┐
│ CPU              │  Independent clock (host board)
│ (independent ref)│  Frequency TBD
└──────────────────┘

[Optional: GPU clock, independent reference]
```

**Key:** All 5 clocks are **truly independent oscillators**. They do NOT synchronize to each other. CDC (2-FF gray-code) exists **because they drift independently**. In real hardware, ppm differences cause metastability — CDC protects that.

---

## MAC-Domain Tick (125 MHz, Independent Reference)

**Each MAC rising edge (on its own oscillator):**

### Phase 1: READ (sample current state from prior cycle's frozen outputs)

```
Adapter reads:
  └─ Its own prior-cycle output (what's in ADAPTER_OUTPUT_*)
     (Not reading external data again; already buffered)

WIRE reads:
  └─ (Passive relay; no compute)

NIC reads:
  ├─ WIRE_BID_PRICE        (from adapter's output)
  ├─ WIRE_ASK_PRICE        (from adapter's output)
  ├─ WIRE_SYMBOL           (from adapter's output)
  ├─ WIRE_SEQ              (from adapter's output)
  ├─ TAI_MAC               (from tai_cdc, 2-FF synced)
  └─ FIFO_RX wr_gray       (CDC synchronized write pointer)
```

### Phase 2: COMPUTE (combinational logic)

```
Adapter compute:
  ├─ Read external data source (CSV, broker stream)
  └─ Format into internal representation (bid, ask, symbol, seq)
     (Does NOT write immediately; holds in registers)

WIRE compute:
  └─ (Passive relay; no logic)

NIC compute:
  ├─ Dedup: is seq == prior_seq? (skip if duplicate)
  ├─ Form packet: {ts=TAI_MAC, bid, ask, symbol, pip, seq}
  └─ Increment wr_gray for FIFO_RX push
```

### Phase 3: WRITE (latch outputs)

```
Adapter writes:
  ├─ ADAPTER_OUTPUT_BID
  ├─ ADAPTER_OUTPUT_ASK
  ├─ ADAPTER_OUTPUT_SYMBOL
  └─ ADAPTER_OUTPUT_SEQ
  (These are now frozen for NIC to read on next MAC tick)

WIRE writes:
  ├─ WIRE_BID_PRICE        ← ADAPTER_OUTPUT_BID
  ├─ WIRE_ASK_PRICE        ← ADAPTER_OUTPUT_ASK
  ├─ WIRE_SYMBOL           ← ADAPTER_OUTPUT_SYMBOL
  └─ WIRE_SEQ              ← ADAPTER_OUTPUT_SEQ

NIC writes:
  ├─ FIFO_RX[wr_slot] ← packet {ts, bid, ask, symbol, pip, seq}
  ├─ FIFO_RX_WR_GRAY   ← new write pointer (gray-coded)
  └─ [NIC also publishes to display]
      ├─ NIC_DISPLAY_TS
      ├─ NIC_DISPLAY_BID
      ├─ NIC_DISPLAY_ASK
      ├─ NIC_DISPLAY_SEQ
      └─ NIC_DISPLAY_FIFO_DEPTH

Timing infrastructure writes:
  ├─ MAC ← MAC + 1           (increment on its own clock)
  ├─ TAI ← TAI + 1           (increment on its own clock)
  ├─ TAIOSC ← TAIOSC + 1     (increment on its own clock)
  ├─ TAI_CDC Gray-sync chain (2-FF pipeline stage)
  └─ [All publish to display]
      ├─ MAC_DISPLAY_COUNT
      ├─ TAI_DISPLAY_COUNT
      ├─ TAIOSC_DISPLAY_COUNT
      └─ TAI_MAC_DISPLAY_COUNT
```

**Result:** FIFO_RX has new packet (waiting for internal-domain reader on a different clock).

---

## SLR Seam Crossing (Two Independent Clock Domains)

**NIC (MAC domain) ↔ Pipeline (INTERNAL domain)**

Clocks are independent → CDC required. FIFO_RX handles the crossing asynchronously.

```
MAC Domain (125 MHz, free-running):
  ├─ NIC pushes packet into FIFO_RX
  ├─ Updates wr_gray pointer (gray-coded)
  └─ wr_gray enters 2-FF sync chain (one stage per sync clock)

2-FF Gray-Code Synchronizer (2 stages of internal clock):
  Cycle N (internal):     wr_gray_sync[0] ← wr_gray (from MAC, metastable)
  Cycle N+1 (internal):   wr_gray_sync[1] ← wr_gray_sync[0] (stable)
  Cycle N+2 (internal):   Pipeline reads stable wr_gray_sync[1]

Internal Domain (250 MHz, free-running):
  ├─ Reads stable wr_gray (no tearing)
  ├─ Calculates FIFO occupancy (wr_gray vs rd_gray)
  └─ Pops packet when valid

2-FF CDC (reverse direction, internal → MAC):
  Cycle M (MAC):          rd_gray_sync[0] ← rd_gray (from internal, metastable)
  Cycle M+1 (MAC):        rd_gray_sync[1] ← rd_gray_sync[0] (stable)
  Cycle M+2 (MAC):        NIC reads stable rd_gray_sync[1]
```

---

## Internal-Domain Tick (250 MHz, Independent Reference)

**All modules in internal domain read from prior-cycle frozen outputs. Order of execution is irrelevant (all inputs are registered 1 cycle old).**

### Phase 0: All Modules READ (in any order)

```
DOM reads:
  ├─ FIFO_RX pop (new packet: ts, bid, ask, symbol, pip, seq)
  ├─ TIMEFRAME_BASE_TICK (is a new base tick?)
  └─ [prior cycle's outputs from pip_resolver, other modules]

CANDLE reads:
  ├─ TIMEFRAME_BASE_TICK (for its own multiplier logic)
  ├─ [frozen candle state from prior cycle]
  ├─ DOM_DISPLAY_BID (or direct bid stream)
  ├─ DOM_DISPLAY_ASK
  └─ CANDLE_MULTIPLIER (user-configured, e.g., 2)

FOOTPRINT reads:
  ├─ TIMEFRAME_BASE_TICK
  ├─ DOM depth tables (bid/ask qty per level)
  ├─ FOOTPRINT_MULTIPLIER (user-configured, default 1)
  └─ [frozen footprint state from prior cycle]

TPO reads:
  ├─ TIMEFRAME_BASE_TICK
  ├─ DOM trade side (implicit from bid/ask qty changes)
  ├─ TPO_MULTIPLIER (user-configured, default 1)
  └─ [frozen TPO state from prior cycle]

TIMEFRAME reads:
  ├─ TAI (current timestamp)
  ├─ INTERNAL_TICK_COUNT (internal clock counter)
  └─ TF_BASE_PERIOD_TICKS (e.g., 250 for 1-second bars @ 250 MHz)

FRACTAL reads:
  ├─ CANDLE_HIST (last 5 bars)
  └─ FRACTAL_MULTIPLIER (if user configured different timeframe)

CBR reads:
  ├─ CANDLE_HIST (just-closed bar vs prior bar)
  ├─ FOOTPRINT_HIST (cumulative delta from both bars)
  └─ CBR_MULTIPLIER

STRATEGY reads:
  ├─ CANDLE_HIST (multi-bar history)
  ├─ FOOTPRINT_HIST
  ├─ FRACTAL_RESULT
  ├─ CBR_DELTAS
  └─ [all frozen from prior cycle]

RISK reads:
  ├─ STRATEGY_SIGNAL (long/short/flat/confidence)
  ├─ Current position size
  ├─ Margin available
  └─ [all frozen from prior cycle]

OMS reads:
  ├─ RISK_ARMED_LANE (approval)
  ├─ STRATEGY_SIGNAL
  └─ [frozen from prior cycle]

SOR reads:
  ├─ OMS_ORDER
  ├─ Venue list
  └─ [frozen from prior cycle]

OUTBOUND reads:
  ├─ SOR_ROUTED_ORDERS
  ├─ TX_FIFO_RD_GRAY (CDC synchronized read pointer)
  └─ [frozen from prior cycle]
```

### Phase 1: All Modules COMPUTE (in any order)

```
DOM compute:
  ├─ Index packet by symbol, price (price / pip_size)
  ├─ Update qty tables (bid/ask at each price level)
  ├─ Track best bid/ask prices
  ├─ Calculate depth ladder (10 best prices each side)
  └─ [all combinational, no reads after this]

CANDLE compute:
  ├─ Check: (INTERNAL_TICK_COUNT % (TF_BASE_PERIOD × CANDLE_MULTIPLIER)) == 0?
  ├─ If YES: close bar (CANDLE_BAR_SEQ ← CANDLE_BAR_SEQ + 1)
  ├─ Update bid-OHLC: open/high/low/close
  ├─ Update ask-OHLC: open/high/low/close
  ├─ Update bid/ask volume per bar
  └─ Add to CANDLE_HIST ring

FOOTPRINT compute:
  ├─ Check: (INTERNAL_TICK_COUNT % (TF_BASE_PERIOD × FOOTPRINT_MULTIPLIER)) == 0?
  ├─ If YES: close bar, calculate:
  │   ├─ POC (point of control, max qty level)
  │   ├─ VAH/VAL (volume at high/low)
  │   ├─ Cumulative delta (sum of all ask_qty - bid_qty)
  │   ├─ Imbalance ratio (diagonal qty threshold check)
  │   └─ Add to FOOTPRINT_HIST ring
  └─ Update live footprint

TPO compute:
  ├─ Check: (INTERNAL_TICK_COUNT % (TF_BASE_PERIOD × TPO_MULTIPLIER)) == 0?
  ├─ If YES: close bar, commit TPO count per price level
  └─ Update live TPO tick counters

TIMEFRAME compute:
  ├─ Increment INTERNAL_TICK_COUNT
  ├─ Check: (INTERNAL_TICK_COUNT % TF_BASE_PERIOD) == 0?
  ├─ If YES: 
  │   ├─ TIMEFRAME_BASE_TICK ← 1 (pulse, one cycle wide)
  │   ├─ Shift CANDLE_HIST ring (bar_seq moves back)
  │   └─ Reset counters for next base period
  └─ Else: TIMEFRAME_BASE_TICK ← 0

FRACTAL compute:
  ├─ (happens every cycle if user wants real-time, or only on candle bar close)
  ├─ Detect 5-bar pivot patterns:
  │   ├─ Fractal UP = (bars[-3] is local high, bars[-4] < bars[-3], bars[-2] < bars[-3])
  │   └─ Fractal DN = (bars[-3] is local low, bars[-4] > bars[-3], bars[-2] > bars[-3])
  └─ Output: FRACTAL_UP, FRACTAL_DN, confidence

CBR compute:
  ├─ (Only on bar close, same cycle as CANDLE/FOOTPRINT)
  ├─ Compare just-closed bar[seq] vs bar[seq-1]:
  │   ├─ delta_volume = vol[seq] - vol[seq-1]
  │   ├─ delta_true_range = TR[seq] - TR[seq-1]
  │   └─ delta_cumulative_delta = cum_delta[seq] - cum_delta[seq-1]
  └─ Store in CBR_HIST ring

STRATEGY compute:
  ├─ Read multi-bar history (CANDLE_HIST, FOOTPRINT_HIST, FRACTAL, CBR)
  ├─ Apply decision logic (EMA, RSI, pattern match, consensus)
  ├─ Output: STRATEGY_SIGNAL {LONG, SHORT, FLAT}
  └─ Output: confidence (0–100%)

RISK compute:
  ├─ Check ARMED_LANE approval:
  │   ├─ If signal=LONG && position < MAX && margin > REQUIREMENT: ARMED ← 1
  │   └─ Else: ARMED ← 0
  └─ Write approval to RISK_ARMED_LANE

OMS compute:
  ├─ If ARMED:
  │   ├─ Calculate ORDER_QTY (size based on signal + position sizing)
  │   ├─ Set ORDER_SIDE = signal (LONG→BUY, SHORT→SELL)
  │   └─ Assign ORDER_ID (sequential counter)
  └─ Else: ORDER_QTY ← 0 (no order)

SOR compute:
  ├─ If ORDER_QTY > 0:
  │   ├─ Allocate order across venues (venue list, best-execution rules)
  │   ├─ For each venue: VENUE_ROUTED_QTY[i], VENUE_ROUTED_SIDE[i]
  │   └─ Venue assignment (e.g., 30% CME, 40% CBOE, 30% NASDAQ)
  └─ Else: all VENUE_ROUTED_QTY ← 0

OUTBOUND compute:
  ├─ For each routed order:
  │   ├─ Format FIX frame
  │   ├─ Push to TX_FIFO
  │   └─ Update TX_WR_GRAY (gray-coded write pointer)
  └─ (TX_WR_GRAY enters 2-FF sync chain to MAC domain)
```

### Phase 2: All Modules WRITE (latch outputs)

```
All modules write their results to registers (the act of latching on rising edge).
All outputs are now frozen for next cycle's reads.

Every module ALSO writes to display lanes:

DOM writes:
  ├─ DOM_BEST_BID, DOM_BEST_ASK
  ├─ DOM_DEPTH_BID[0..9], DOM_DEPTH_ASK[0..9]
  ├─ (Live tables for each bar)
  └─ DOM_DISPLAY_* (same data, raw, for TUI)

CANDLE writes:
  ├─ CANDLE_BID_OPEN/HIGH/LOW/CLOSE
  ├─ CANDLE_ASK_OPEN/HIGH/LOW/CLOSE
  ├─ CANDLE_VOLUME_BID, CANDLE_VOLUME_ASK
  ├─ CANDLE_HIST_RING[seq] (commit to history)
  └─ CANDLE_DISPLAY_* (all fields, raw)

FOOTPRINT writes:
  ├─ FOOTPRINT_POC_PRICE, FOOTPRINT_VAH, FOOTPRINT_VAL
  ├─ FOOTPRINT_CUMULATIVE_DELTA
  ├─ FOOTPRINT_IMBALANCE_RATIO
  ├─ FOOTPRINT_QTY_BID[], FOOTPRINT_QTY_ASK[] (per level)
  ├─ FOOTPRINT_HIST_RING[seq]
  └─ FOOTPRINT_DISPLAY_* (all fields, raw)

TPO writes:
  ├─ TPO_TICK_COUNT[] (per price level, bid/ask split)
  ├─ TPO_HIST_RING[seq]
  └─ TPO_DISPLAY_* (all fields, raw)

TIMEFRAME writes:
  ├─ TIMEFRAME_BASE_TICK (pulse)
  ├─ TIMEFRAME_BASE_SEQ (incremented on bar close)
  └─ TIMEFRAME_DISPLAY_* (current tick count, seq)

FRACTAL writes:
  ├─ FRACTAL_UP, FRACTAL_DN
  ├─ FRACTAL_CONFIDENCE
  └─ FRACTAL_DISPLAY_* (all fields, raw)

CBR writes:
  ├─ CBR_DELTA_VOLUME, CBR_DELTA_TR, CBR_DELTA_CUMULATIVE_DELTA
  ├─ CBR_HIST_RING[seq]
  └─ CBR_DISPLAY_* (all fields, raw)

STRATEGY writes:
  ├─ STRATEGY_SIGNAL {LONG, SHORT, FLAT}
  ├─ STRATEGY_CONFIDENCE
  └─ STRATEGY_DISPLAY_* (signal, confidence, reasoning flags)

RISK writes:
  ├─ RISK_ARMED_LANE
  ├─ RISK_REASON (why armed or not)
  └─ RISK_DISPLAY_* (armed flag, position size, margin, heat)

OMS writes:
  ├─ ORDER_QTY, ORDER_SIDE, ORDER_ID
  ├─ ORDER_ACTIVE_COUNT (running trades)
  └─ OMS_DISPLAY_* (order details, active count, trade table snapshot)

SOR writes:
  ├─ VENUE_ROUTED_QTY[], VENUE_ROUTED_SIDE[]
  ├─ VENUE_ROUTED_ORDER_ID[]
  └─ SOR_DISPLAY_* (per-venue routed quantities, order IDs)

OUTBOUND writes:
  ├─ TX_FIFO[wr_slot] (FIX frame data)
  ├─ TX_WR_GRAY (gray-coded write pointer, enters CDC sync chain)
  └─ OUTBOUND_DISPLAY_* (queued orders, TX FIFO depth, last sent frame)
```

---

## Key Timing Properties

### Independent Clocks → No Synchronous Reads Across Domains

```
MAC tick (cycle M, 125 MHz):
  └─ Can read TAI_MAC (synced via 2-FF CDC, stable from prior cycle)
  └─ Can read FIFO_RX (gray-coded pointers, CDC synchronized)
  └─ CANNOT directly read INTERNAL_TICK_COUNT (would tear)

INTERNAL tick (cycle N, 250 MHz):
  └─ Can read FIFO_RX (gray-coded pointers, CDC synchronized)
  └─ Can read TAI_MAC (synced via 2-FF CDC, stable from prior cycle)
  └─ CANNOT directly read MAC counter (would tear)

CDC ensures metastability-safe crossing at domain boundaries.
```

### Per-Module Bar Subscription

```
Base period: 250 ticks @ 250 MHz = 1 second

User configuration:
  CANDLE_MULTIPLIER = 2     (candle bar = 2 seconds)
  FOOTPRINT_MULTIPLIER = 1  (footprint bar = 1 second)
  TPO_MULTIPLIER = 4        (TPO bar = 4 seconds)

Each tick, each module independently checks:
  if (INTERNAL_TICK_COUNT % (TF_BASE_PERIOD × MULTIPLIER)) == 0:
    close_bar()

Result: Bars close at different times (1s, 2s, 1s, 4s...),
        NO global broadcast pulse, NO tight coupling.
```

### Adapter as Data Repository

```
Cycle N (MAC):
  ├─ External source delivers new data (bid, ask, symbol, seq)
  ├─ Adapter receives and buffers: ADAPTER_INTERNAL_BID, ADAPTER_INTERNAL_ASK, ...
  └─ Adapter outputs frozen (not yet visible on WIRE)

Cycle N (MAC) Phase 3 (WRITE):
  ├─ Adapter writes to WIRE relay lanes
  └─ Wire now reflects latest adapter buffer

Cycle N+1 (MAC):
  ├─ NIC reads WIRE (sees adapter's output from cycle N)
  ├─ Adapter reads next external data source (pipelined)
  └─ Adapter will update WIRE on next WRITE phase

Result: Adapter is a 1-cycle buffer, not a passthrough.
```

---

## Summary: Order-Free, Per-Module, Independent Clocks

| Property | Model |
|---|---|
| **Clock domains** | 5 truly independent oscillators (TAIOSC, TAI, MAC, INTERNAL, CPU) |
| **Cross-domain reads** | CDC 2-FF gray-code synchronizers only; never raw reads |
| **Module execution order** | Any order (all inputs frozen from prior cycle) |
| **Bar closes** | Per-module subscription with user-configurable multiplier (default 1×) |
| **Display** | Every module outputs raw register lanes (non-blocking, async) |
| **Adapter** | Data repository/buffer (not passthrough pipe) |
| **Per-cycle latency** | 1 register hop per module (input → compute → output) |

**Contrast with old model:**
- ✗ Not: "one deterministic time base"
- ✗ Not: "explicit seq 0–11 dispatch"
- ✗ Not: "global bar-close broadcast pulse"
- ✗ Not: "adapter as passthrough"

**New model:**
- ✓ Five independent clocks (CDC at boundaries)
- ✓ Order-free parallel execution (registered 1-cycle latency)
- ✓ Per-module bar subscription (user-configurable multiples)
- ✓ Adapter as buffer (holds external state)
- ✓ Every module has display output
