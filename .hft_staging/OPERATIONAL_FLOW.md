# Operational Flow: Clock Sequence & Execution Order

## System Clock Model

Three independent clock domains, two synchronized:

```
┌─────────────────┐
│ TAIOSC          │  Free-running oscillator (GNSS-equivalent truth)
│ (authoritative) │  • No discipline, no PPS
└────────┬────────┘
         │ increments continuously
         ▼
┌─────────────────┐
│ TAI             │  Plain counter off TAIOSC
│ (timestamp)     │  • Increments every taiosc cycle
└────────┬────────┘
         │
         ├──────────────────────────────────┐
         │ Gray-code 2-FF CDC crossing      │
         │ (TAI → MAC domain)               │
         │                                  │
         ▼                                  ▼
┌──────────────────────┐        ┌──────────────────────┐
│ TAI_MAC (in MAC dom) │        │ MAC (125 MHz clock)  │
│ (stable, stage-2)    │        │ (NIC sample/copy)    │
│ Used by: NIC         │        │ Increment counter    │
└──────────────────────┘        └──────────────────────┘
         │                             │
         └─────────────┬───────────────┘
                       │
              Two synchronized sources
                (independent oscillators;
                 TAI = truth, MAC = rate)
```

**Key:** TAI and MAC are **independent oscillators**, not derived from each other. TAI is the authoritative timestamp; MAC is the sampling rate. The NIC reads the current TAI value (via CDC) and pairs it with MAC's rate for packet timing.

---

## MAC-Domain Tick (125 MHz NIC)

**Each MAC rising edge:**

1. **CLOCK_PHASE_READ** (pre-compute sample time)
   - Adapter reads external CSV (if available)
   - Adapter reads its own output (pacing)
   - NIC reads WIRE (latest bid/ask/symbol)
   - NIC reads TAI_MAC (current timestamp via tai_cdc)
   - NIC reads FIFO_RX write-gray pointer (CDC synchronized)

2. **CLOCK_PHASE_COMPUTE** (combinational logic)
   - Adapter: pace output by CSV timestamp
   - WIRE: (no compute, passive relay)
   - NIC: dedup by sequence, form output packet
   - TAI_CDC: gray-code synchronizer (ongoing)
   - FIFO_RX writer: push packet, update gray pointer

3. **CLOCK_PHASE_WRITE** (latch outputs)
   - Adapter writes to WIRE relay lanes
   - NIC writes to FIFO_RX push slots + wr_gray
   - TAI_CDC writes to MAC-domain stable register

**Latency:** ~3 ns (one 125 MHz cycle = 8 ns)
**Output:** FIFO_RX has new packet (waiting for internal-domain reader)

---

## SLR Seam Timing (NIC FPGA → Pipeline FPGA)

**Boundary crossing:** Registered delay across SLR boundary (2 internal cycles).

| Event | Cycle | Action |
|---|---|---|
| FIFO_RX MAC-write | Cycle 0 (MAC) | NIC pushes packet into FIFO |
| CDC gray-sync (wr_ptr) | Cycle 0–1 (MAC) | Write pointer enters 2-FF sync chain |
| FIFO read-enable (internal) | Cycle N | Internal domain sees stable wr_gray @ cycle N+2 |
| SLR0→SLR1 pipeline regs | Seq 3 (internal) | Packet data mirrored to seam latches (2-cycle registered) |

**Visible latency:** 2 internal cycles (~8 ns @ 250 MHz) after write is stable in MAC domain.

---

## Internal-Domain Tick (250 MHz Pipeline)

Execution is **sequence-ordered** (CLK_DEP_TABLE) — NOT all at once:

```
┌──────────────────────────────────────────────────────────────┐
│ SINGLE 250 MHz CLOCK EDGE (4 ns)                            │
├──────────────────────────────────────────────────────────────┤
│ Seq 0: CLOCK_PHASE_READ (all modules read their inputs)     │
├──────────────────────────────────────────────────────────────┤
│ Seq 1: INTERNAL clock increment, TIMEFRAME bar detection    │
├──────────────────────────────────────────────────────────────┤
│ Seq 2: TAIOSC + TAI increment                               │
├──────────────────────────────────────────────────────────────┤
│ Seq 3: SLR seam regs write (NIC→Pipeline CDC delivers)      │
│        PIP_RESOLVER lookup outputs (lookup comb logic)      │
├──────────────────────────────────────────────────────────────┤
│ Seq 4: DOM ingress (reads seam regs, updates tables)        │
├──────────────────────────────────────────────────────────────┤
│ Seq 5: CANDLE, FOOTPRINT, TPO reads DOM outputs             │
│        FRACTAL reads CANDLE history (last bar)              │
│        CBR reads CANDLE + FOOTPRINT history                 │
├──────────────────────────────────────────────────────────────┤
│ Seq 6: TIMEFRAME signals bar-closed (TF_BAR_CLOSED pulse)   │
├──────────────────────────────────────────────────────────────┤
│ Seq 7: STRATEGY reads indicators (all latched)              │
│        Generates SIGNAL (long/short/flat)                   │
├──────────────────────────────────────────────────────────────┤
│ Seq 8: RISK reads signal, evaluates position limits         │
│        Writes ARMED_LANE approval                           │
├──────────────────────────────────────────────────────────────┤
│ Seq 9: OMS reads ARMED_LANE                                 │
│        Generates ORDER + VENUE assignment                   │
├──────────────────────────────────────────────────────────────┤
│ Seq 10: SOR reads OMS outputs                               │
│         Routes to venue-specific TX buffers                 │
├──────────────────────────────────────────────────────────────┤
│ Seq 11: OUTBOUND reads SOR routed orders                    │
│         Writes to TX FIFO (egress to NIC)                   │
├──────────────────────────────────────────────────────────────┤
│ CLOCK_PHASE_COMPUTE (entire tick; no interleaving)         │
├──────────────────────────────────────────────────────────────┤
│ Seq 0–11: All gate algebra (combinational logic)            │
├──────────────────────────────────────────────────────────────┤
│ CLOCK_PHASE_WRITE (all modules latch their outputs)        │
│ (Happens AFTER all CLOCK_PHASE_READ/COMPUTE complete)      │
└──────────────────────────────────────────────────────────────┘
```

**Critical:** `CLK_DEP_TABLE` defines the **READ offset** for each module's clock_edge_* call.
- Seq 0: reads @ START of tick (dependencies available from PRIOR tick's WRITE phase)
- Seq 3: SLR seam regs become readable (NIC output delivered via CDC)
- Seq 4+: each module reads outputs from earlier seqs

---

## Data Flow Timing Example (One Tick)

**Scenario:** NIC sends a new bid price update packet.

```
Cycle N (125 MHz / MAC domain):
  ├─ Adapter reads CSV: {bid=105.50, ask=105.75, seq=12345}
  ├─ WIRE relays: bid/ask/seq lanes updated
  ├─ NIC reads WIRE, reads TAI_MAC, dedup checks seq
  ├─ NIC: seq 12345 is new (not 12344)
  ├─ NIC: form packet {ts=TAI_MAC, bid, ask, symbol, pip, seq}
  ├─ FIFO_RX writer: push to slots, wr_gray←12341 (gray)
  └─ Gray sync begins: wr_gray[0] → FF[0] → FF[1] (2-FF chain)

Cycle N+1 (125 MHz / MAC domain):
  └─ wr_gray[1] (2-FF stable in MAC) → CDC input to internal

Cycle N+2 (internal @ 250 MHz / pipeline):
  [Previous tick's WRITE phase completes]
  ├─ TAI_MAC shows the TAI value that was stamped at cycle N
  ├─ rd_gray[0] synced (FF[0] now shows wr_gray[1] stable)
  ├─ rd_gray[1] synced (FF[1] now shows wr_gray[2])

Cycle M (250 MHz / internal @ seq 3):
  ├─ SLR seam registers latch packet data from FIFO_RX
  │  {ts, bid, ask, symbol, pip, comm, seq} now in Pipeline domain
  ├─ PIP_RESOLVER: lookup(symbol) → pip_size (comb output)
  ├─ These seam outputs become readable @ seq 4+

Cycle M+1 (250 MHz / internal @ seq 4):
  ├─ DOM: reads seam regs (packet: bid, ask, qty, symbol, pip)
  ├─ DOM: indexing logic
  │  ├─ bid_idx ← bid / pip_size (div by pip_size from pip_resolver)
  │  ├─ ask_idx ← ask / pip_size
  │  ├─ qty_bid_old ← TABLE[bid_idx]
  │  └─ qty_bid_new ← qty_bid_old + DOM_BID_QTY_DELTA
  ├─ DOM: best-bid tracking
  │  ├─ is_new_best ← (bid > DOM_BEST_BID_PRICE) && valid_packet
  │  └─ If yes: DOM_BEST_BID_PRICE ← bid, DOM_BEST_BID_QTY ← qty_new
  ├─ DOM: relay ladder (10 prices above/below best)
  │  ├─ DOM_DEPTH_BID[0] ← best price
  │  ├─ DOM_DEPTH_BID[1] ← best - 1*pip
  │  ├─ DOM_DEPTH_BID[2] ← best - 2*pip
  │  └─ ... (quantities from table)
  └─ DOM outputs latched in REG_W

Cycle M+2 (250 MHz / internal @ seq 5):
  ├─ CANDLE: reads DOM_BEST_BID_PRICE, DOM_BEST_ASK_PRICE
  │  ├─ CANDLE_BID_OPEN already latched from prior bar
  │  ├─ CANDLE_BID_HIGH ← max(CANDLE_BID_HIGH, bid)
  │  ├─ CANDLE_BID_LOW ← min(CANDLE_BID_LOW, bid)
  │  └─ CANDLE_BID_CLOSE ← bid (updated every tick)
  ├─ FOOTPRINT: reads DOM qty (bid/ask per level)
  │  ├─ POC tracking (which price has max qty)
  │  ├─ VAH/VAL calculation (volume at high/low)
  │  └─ Delta imbalance (buy-initiated vs sell-initiated)
  ├─ TPO: reads trade side (implicit from DOM flow)
  │  └─ Increments time counter for current price
  └─ All outputs latched

Cycle M+3 (250 MHz / internal @ seq 6):
  ├─ TIMEFRAME: reads TAI_MAC (current time)
  ├─ Checks: has bar closed? (TAI second boundary crossed?)
  ├─ If yes:
  │  ├─ TF_BAR_CLOSED ← 1 (pulse, one-cycle wide)
  │  ├─ TF_BAR_SEQ ← TF_BAR_SEQ + 1 (bar counter increment)
  │  └─ Shift CANDLE_HIST ring: [bar_seq-1] copy to [bar_seq-2], etc.
  ├─ If no:
  │  └─ TF_BAR_CLOSED ← 0
  └─ Outputs latched

Cycle M+4 (250 MHz / internal @ seq 7):
  ├─ FRACTAL: reads CANDLE_HIST[last_5_bars]
  │  ├─ Detects 5-bar pivot patterns (higher high, lower low)
  │  ├─ FRACTAL_UP ← (bars[-3] is pivot high)
  │  └─ FRACTAL_DN ← (bars[-3] is pivot low)
  ├─ STRATEGY: reads CANDLE_HIST, FOOTPRINT_HIST, FRACTAL, CBR
  │  ├─ Decision logic (EMA / RSI / pattern match)
  │  ├─ Outputs: SIGNAL ← {LONG, SHORT, FLAT}
  │  └─ Confidence level (0–100%)
  └─ Outputs latched

Cycle M+5 (250 MHz / internal @ seq 8):
  ├─ RISK: reads STRATEGY_SIGNAL
  │  ├─ Checks: max position size, margin available, heat
  │  ├─ If signal=LONG && position < MAX && margin > REQUIREMENT:
  │  │  └─ ARMED_LANE ← 1 (approve order generation)
  │  └─ Else: ARMED_LANE ← 0 (veto)
  └─ Output latched

Cycle M+6 (250 MHz / internal @ seq 9):
  ├─ OMS: reads ARMED_LANE, SIGNAL
  │  ├─ If ARMED:
  │  │  ├─ ORDER_QTY ← calculate_size(signal)
  │  │  └─ ORDER_SIDE ← signal (LONG→BUY, SHORT→SELL)
  │  ├─ Else: ORDER_QTY ← 0 (no order)
  │  └─ Assign venue (e.g., {CME, CBOE, NASDAQ})
  └─ Outputs latched

Cycle M+7 (250 MHz / internal @ seq 10):
  ├─ SOR: reads OMS order + venues
  │  ├─ Allocates order across venues (best execution)
  │  ├─ Venue#0: 30% of qty
  │  ├─ Venue#1: 40% of qty
  │  └─ Venue#2: 30% of qty
  └─ Outputs latched (venue-routed fragments)

Cycle M+8 (250 MHz / internal @ seq 11):
  ├─ OUTBOUND: reads SOR routed orders
  │  ├─ Formats FIX frames (for each venue)
  │  ├─ Writes to TX FIFO (egress to NIC)
  │  └─ Updates TX wr_gray pointer
  └─ Output latched

Next MAC-domain tick (125 MHz / NIC @ cycle M+9):
  └─ TX FIFO reader (NIC egress) reads TX gray pointer
     Gray sync runs 2-FF chain to deliver to NIC
     Next cycle: NIC TX sends frames to broker
```

---

## Clock Dependency Table (CLK_DEP_TABLE)

The canonical execution order. Each module's `clock_edge_*()` call happens at its assigned SEQ offset:

| Seq | Module | Operation | Inputs Available | Outputs Latched |
|---|---|---|---|---|
| **0** | **All (READ)** | Read prior-tick outputs | All modules' WRITE phase (prior tick) | — |
| **1** | INTERNAL | Increment counter | Previous INTERNAL count | new INTERNAL count |
| **2** | TAIOSC + TAI | Increment counters | Previous TAI, TAIOSC values | new TAI, TAIOSC |
| **3** | TAI_CDC + SLR seam | Gray sync + mirror | NIC FIFO_RX output, TAI_MAC | SLR0_TO_SLR1_* regs |
| **4** | DOM | Index + aggregate | Seam regs (prices, qty, symbol) | DOM_BEST_*, DOM_DEPTH_* |
| **5** | CANDLE, FOOTPRINT, TPO | OHLC, imbalance, time | DOM outputs, CANDLE_HIST | CANDLE, FOOTPRINT, TPO outputs |
| **5** | FRACTAL, CBR | History reads | CANDLE_HIST, FOOTPRINT_HIST | FRACTAL, CBR outputs |
| **6** | TIMEFRAME | Bar boundary detect | TAI, current bar seq | TF_BAR_CLOSED, TF_BAR_SEQ |
| **7** | STRATEGY | Signal generation | CANDLE_HIST, indicators | STRATEGY_SIGNAL, confidence |
| **8** | RISK | Approval gate | STRATEGY_SIGNAL, positions | ARMED_LANE |
| **9** | OMS | Order assembly | ARMED_LANE, signal | ORDER_*, ORDER_SIDE |
| **10** | SOR | Venue routing | OMS order, venue list | VENUE_ROUTED_* (per venue) |
| **11** | OUTBOUND | FIX format + TX push | SOR routed orders | TX FIFO, wr_gray |
| **—** | **All (WRITE)** | Latch outputs | (all compute complete) | All registers updated |

---

## Display Lanes (Non-Blocking Reads)

Every module publishes a **display window** (relay lanes) for external TUI/LCD consumption:

```
┌──────────────────────────────────────────────────────────────┐
│ DISPLAY ARCHITECTURE                                         │
├──────────────────────────────────────────────────────────────┤
│ Each module writes to a DISPLAY_REG window (non-blocking,   │
│ same address space, no clock dependency).                    │
│                                                              │
│ Example: DOM_DISPLAY_* (raw price + qty + bar_seq)          │
│  ├─ DOM_DISPLAY_BEST_BID        (u64: price in bps)         │
│ │ DOM_DISPLAY_BEST_ASK        (u64: price in bps)         │
│  ├─ DOM_DISPLAY_BID_QTY        (u64: qty lots)             │
│  ├─ DOM_DISPLAY_ASK_QTY        (u64: qty lots)             │
│  └─ DOM_DISPLAY_BAR_SEQ        (u64: sequence counter)     │
│                                                              │
│ TUI reads these lanes directly (no reformat, no compute).   │
│ Updates are **pipelined**: TUI reads whatever is live, no  │
│ need to wait for a specific synchronization point.          │
│                                                              │
│ Display updates lag by at most 1–2 internal ticks (4–8 ns).│
└──────────────────────────────────────────────────────────────┘
```

**Key:** Display is **asynchronous and non-blocking**. The TUI reads what's there; the pipeline never waits for the TUI to catch up.

---

## Summary: Three-Layer Timing Model

```
┌────────────────────────────────────────┐
│ TAI (timestamp, GNSS-equivalent)       │  Authoritative time
│ Taiosc (free-running oscillator)       │  Feeds TAI, no discipline
│ TAI_MAC (TAI in MAC domain, via CDC)   │  NIC sees timestamp values
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ MAC domain (125 MHz, NIC FPGA)         │  Ingress & wire sampling
│ Increments @ 125 MHz                   │  Rate = 8 ns / cycle
│ Functions: adapter, wire, nic,         │
│             tai_cdc, fifo_rx           │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ Internal domain (250 MHz, Pipeline)    │  Processing pipeline
│ Increments @ 250 MHz                   │  Rate = 4 ns / cycle
│ Functions: dom, candle, footprint,     │  Sequenced (CLK_DEP_TABLE)
│             tpo, strategy, risk, OMS   │  12 seqs per tick
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ CDC crossings (SLR0 → SLR1 boundary)   │  2-FF gray-code sync
│ FIFO_RX (512 slots, async FIFO)        │  2 internal cycles latency
│ Results visible @ seq 3, readable @ 4+ │
└────────────────────────────────────────┘
```

**All three operate in parallel; synchronization happens at CDC boundaries only.**
