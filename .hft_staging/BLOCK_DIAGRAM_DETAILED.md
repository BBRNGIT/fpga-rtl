# Block Diagram: HFT Pipeline Data & Control Flow

## System Layout (Three-Chip Architecture)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL WORLD (Real-Time)                          │
│  CSV File / Broker Feed ────────────┐                                       │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                    ┌─────────────────▼─────────────────┐
                    │   ADAPTER (ext clock, 208 cells)  │
                    │  • Read market data (prices)      │
                    │  • Pace output by timestamps      │
                    │  • Deposit to WIRE bus            │
                    └─────────────────┬─────────────────┘
                                      │
        ┌─────────────────────────────▼────────────────────────────────────┐
        │                    NIC FPGA (125 MHz MAC clock)                  │
        │ ┌──────────────────────────────────────────────────────────────┐ │
        │ │  WIRE (0 cells, passive bus @ 0x1700000)                    │ │
        │ │  • Relay: price-only packets from adapter                  │ │
        │ │  • No clock, no logic — just register window               │ │
        │ │  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐  │ │
        │ │  │ BID_PRICE  │  │ ASK_PRICE  │  │ SYMBOL,PIP,SEQ,...  │  │ │
        │ │  └─────┬──────┘  └──────┬─────┘  └────────┬────────────┘  │ │
        │ │        │                │                 │                │ │
        │ │        └────────────────┴─────────────────┘                │ │
        │ │                 │                                          │ │
        │ │                 ▼                                          │ │
        │ │  ┌────────────────────────────────────────────────────┐   │ │
        │ │  │  NIC (180 cells @ 0x1A00000)                      │   │ │
        │ │  │  • Sample WIRE (read prices, symbol, seq)         │   │ │
        │ │  │  • Dedup by seq (drop repeats)                    │   │ │
        │ │  │  • Read TAI_MAC (timestamp from tai_cdc)          │   │ │
        │ │  │  • Write to FIFO_RX (MAC-domain output)           │   │ │
        │ │  │  Outputs: [ts, bid, ask, symbol, pip, comm, seq]│   │ │
        │ │  └────┬────────────────────────────────────────────┘   │ │
        │ │       │ (MAC domain, paced by 125 MHz)                  │ │
        │ │       │                                                 │ │
        │ │  ┌────▼───────────────────────────────────────────────┐ │ │
        │ │  │  Timing Infrastructure (MAC domain)               │ │ │
        │ │  │  ┌─────────────────┐  ┌────────────────────────┐ │ │ │
        │ │  │  │ TAIOSC (5 cells)│  │ MAC (5 cells)          │ │ │ │
        │ │  │  │ • TAI oscillator│  │ • 125 MHz ref counter  │ │ │ │
        │ │  │  │ • Free-running  │  │ • Sample/copy rate     │ │ │ │
        │ │  │  │   (GNSS-equiv)  │  │   (NIC clock)          │ │ │ │
        │ │  │  └────────┬────────┘  └─────────┬──────────────┘ │ │ │
        │ │  │           │                     │                 │ │ │
        │ │  │    ┌──────▼──────────┐          │                 │ │ │
        │ │  │    │ TAI (4 cells)   │          │                 │ │ │
        │ │  │    │ • TAI counter   │          │                 │ │ │
        │ │  │    │ • Off taiosc    │          │                 │ │ │
        │ │  │    │ • No discipline │          │                 │ │ │
        │ │  │    └────────┬────────┘          │                 │ │ │
        │ │  │             │                   │                 │ │ │
        │ │  │    ┌────────▼──────────────────▼────────┐         │ │ │
        │ │  │    │ TAI_CDC (12 cells)                 │         │ │ │
        │ │  │    │ • Gray-code 2-FF sync             │         │ │ │
        │ │  │    │ • TAI value → MAC domain          │         │ │ │
        │ │  │    │ Output: TAI_MAC (stable, stage-2) │         │ │ │
        │ │  │    └────────────────────────────────────┘         │ │ │
        │ │  └──────────────────────────────────────────────────┘ │ │
        │ │                       │                               │ │
        │ │                       ▼                               │ │
        │ │  ┌────────────────────────────────────────────────┐   │ │
        │ │  │ FIFO_RX (8211 cells @ 0x2000000)            │   │ │
        │ │  │ • Async CDC FIFO (MAC ↔ internal)           │   │ │
        │ │  │ • 512 slots, gray-code sync (2-FF each way) │   │ │
        │ │  │ • Writer (MAC): NIC output                  │   │ │
        │ │  │ • Reader (internal): DOM pulls packets      │   │ │
        │ │  │ Latency: 2 cycle @ 250 MHz (8 ns)           │   │ │
        │ │  └────┬────────────────────────────────────────┘   │ │
        │ └──────┼────────────────────────────────────────────┘ │
        │        │  SLR SEAM (NIC FPGA → Pipeline FPGA)        │
        │ ┌──────▼────────────────────────────────────────────┐ │
        │ │                                                   │ │
        └─┤────────────────────────────────────────────────────┤─┘
          │                                                     │
          │  ┌──────────────────────────────────────────────┐  │
          │  │     SLR0→SLR1 CDC REGISTERS (seq 3)         │  │
          │  │  • SLR0_TO_SLR1_PIPE_R2_REG (valid flag)   │  │
          │  │  • SLR0_TO_SLR1_W0_R2_REG (ts, bid)        │  │
          │  │  • SLR0_TO_SLR1_W1_R2_REG (ask)            │  │
          │  │  • SLR0_TO_SLR1_W2_R2_REG (symbol, pip)    │  │
          │  │  • SLR0_TO_SLR1_TAI_R2_REG (TAI stable)    │  │
          │  │  Latency: 2 internal cycles (8 ns @ 250MHz)│  │
          │  └──────────────────────────────────────────────┘  │
          │                                                     │
          │         PIPELINE FPGA (250 MHz internal clock)      │
          │                                                     │
        ┌─▼──────────────────────────────────────────────────┐  │
        │ ┌─────────────────────────────────────────────────┐│  │
        │ │  DOM (84 cells @ 0x2100000)                    ││  │
        │ │  • Input: seam registers (via CDC)             ││  │
        │ │  • Reads: price, qty, seq, symbol from fifo    ││  │
        │ │  • Logic:                                       ││  │
        │ │    - Price-indexed tables (16384 entries)      ││  │
        │ │    - Best bid/ask tracking                     ││  │
        │ │    - Depth ladder (10-level relay)            ││  │
        │ │  • Outputs:                                     ││  │
        │ │    - DOM_BEST_BID_PRICE, DOM_BEST_ASK_PRICE   ││  │
        │ │    - DOM_DEPTH_BID[], DOM_DEPTH_ASK[]         ││  │
        │ │    - per-level tables (indexed by symbol/px)  ││  │
        │ └──┬──────────────────────────────────────────────┤│  │
        │    │                                              ││  │
        │    └──────────────────┬─────────────────────────┐ ││  │
        │                       │                         │ ││  │
        │  ┌────────────────────▼────────────────────┐   │ ││  │
        │  │ INDICATORS (248 cells total)            │   │ ││  │
        │  │                                         │   │ ││  │
        │  │ ┌──────────────────────────────────┐   │   │ ││  │
        │  │ │ CANDLE (16 cells @ 0x2200000)   │   │   │ ││  │
        │  │ │ • Input: DOM bid/ask prices     │   │   │ ││  │
        │  │ │ • Logic: OHLC (dual bid/ask)   │   │   │ ││  │
        │  │ │ • Outputs: CANDLE_HIST ring    │   │   │ ││  │
        │  │ │           (256-bar history)     │   │   │ ││  │
        │  │ └──────────────────────────────────┘   │   │ ││  │
        │  │                                         │   │ ││  │
        │  │ ┌──────────────────────────────────┐   │   │ ││  │
        │  │ │ FOOTPRINT (36 cells @ 0x2300000)│   │   │ ││  │
        │  │ │ • Input: DOM qty (bid/ask)      │   │   │ ││  │
        │  │ │ • Logic: POC, VAH/VAL, delta   │   │   │ ││  │
        │  │ │ • Outputs: FOOTPRINT_HIST ring │   │   │ ││  │
        │  │ │           (256-bar history)     │   │   │ ││  │
        │  │ └──────────────────────────────────┘   │   │ ││  │
        │  │                                         │   │ ││  │
        │  │ ┌──────────────────────────────────┐   │   │ ││  │
        │  │ │ TPO (7 cells @ 0x2400000)       │   │   │ ││  │
        │  │ │ • Input: DOM trade price/side   │   │   │ ││  │
        │  │ │ • Logic: time-per-price (bid/ask) │ │   │ ││  │
        │  │ │ • Outputs: TPO_HIST ring        │   │   │ ││  │
        │  │ │           (256-bar history)     │   │   │ ││  │
        │  │ └──────────────────────────────────┘   │   │ ││  │
        │  │                                         │   │ ││  │
        │  │ ┌──────────────────────────────────┐   │   │ ││  │
        │  │ │ FRACTAL (15 cells @ 0x2450000)  │   │   │ ││  │
        │  │ │ • Input: CANDLE_HIST (5-bar)   │   │   │ ││  │
        │  │ │ • Logic: 5-bar pivot patterns  │   │   │ ││  │
        │  │ │ • Outputs: fractal up/dn reg   │   │   │ ││  │
        │  │ └──────────────────────────────────┘   │   │ ││  │
        │  │                                         │   │ ││  │
        │  │ ┌──────────────────────────────────┐   │   │ ││  │
        │  │ │ CBR (18 cells @ 0x2460000)      │   │   │ ││  │
        │  │ │ • Inputs: CANDLE_HIST + FP delta│   │   │ ││  │
        │  │ │ • Logic: cross-bar deltas + HW │   │   │ ││  │
        │  │ │ • Outputs: delta registers      │   │   │ ││  │
        │  │ └──────────────────────────────────┘   │   │ ││  │
        │  │                                         │   │ ││  │
        │  │ ┌──────────────────────────────────┐   │   │ ││  │
        │  │ │ TIMEFRAME (8 cells @ 0x1E80000) │   │   │ ││  │
        │  │ │ • Input: TAI (current time)     │   │   │ ││  │
        │  │ │ • Logic: bar-boundary detect   │   │   │ ││  │
        │  │ │ • Outputs: TF_BAR_SEQ (sync)   │   │   │ ││  │
        │  │ │           TF_BAR_CLOSED (pulse)│   │   │ ││  │
        │  │ └──────────────────────────────────┘   │   │ ││  │
        │  │                                         │   │ ││  │
        │  │ ┌──────────────────────────────────┐   │   │ ││  │
        │  │ │ PIP_RESOLVER (55 cells)         │   │   │ ││  │
        │  │ │ • Lookup: symbol → pip size    │   │   │ ││  │
        │  │ │ • Serves: DOM, indicators      │   │   │ ││  │
        │  │ └──────────────────────────────────┘   │   │ ││  │
        │  └─────────────────────────────────────────┘   │ ││  │
        │                  │                             │ ││  │
        │  ┌───────────────▼──────────────────────────┐  │ ││  │
        │  │ STRATEGY (TBD)                          │  │ ││  │
        │  │ • Reads: CANDLE_HIST, FOOTPRINT_HIST   │  │ ││  │
        │  │ • Logic: decision (long/short/flat)    │  │ ││  │
        │  │ • Output: CONSENSUS_SIGNAL             │  │ ││  │
        │  └───────────────┬──────────────────────────┘  │ ││  │
        │                  │                             │ ││  │
        │  ┌───────────────▼──────────────────────────┐  │ ││  │
        │  │ RISK (TBD)                              │  │ ││  │
        │  │ • Input: signal, positions              │  │ ││  │
        │  │ • Output: ARMED_LANE approval           │  │ ││  │
        │  └───────────────┬──────────────────────────┘  │ ││  │
        │                  │                             │ ││  │
        │  ┌───────────────▼──────────────────────────┐  │ ││  │
        │  │ OMS (TBD)                               │  │ ││  │
        │  │ • Input: armed signal                   │  │ ││  │
        │  │ • Logic: order management               │  │ ││  │
        │  │ • Output: orders to SOR                 │  │ ││  │
        │  └───────────────┬──────────────────────────┘  │ ││  │
        │                  │                             │ ││  │
        │  ┌───────────────▼──────────────────────────┐  │ ││  │
        │  │ SOR (TBD)                               │  │ ││  │
        │  │ • Input: orders, venue list             │  │ ││  │
        │  │ • Logic: smart order routing            │  │ ││  │
        │  │ • Output: routed to outbound            │  │ ││  │
        │  └───────────────┬──────────────────────────┘  │ ││  │
        │                  │                             │ ││  │
        │  ┌───────────────▼──────────────────────────┐  │ ││  │
        │  │ OUTBOUND (TBD)                          │  │ ││  │
        │  │ • Input: routed orders                  │  │ ││  │
        │  │ • Logic: FIX frame, TX CDC FIFO        │  │ ││  │
        │  │ • Output: TX stream to broker           │  │ ││  │
        │  └───────────────┬──────────────────────────┘  │ ││  │
        │                  │                             │ ││  │
        └──────────────────┼─────────────────────────────┘ ││  │
                           │                               ││  │
                    (egress back to broker)                ││  │
                                                           ││  │
                   ┌─────────────────────────────────────┐ ││  │
                   │ DISPLAY LANES (non-blocking reads)  │ ││  │
                   │ ┌─────────────────────────────────┐ │ ││  │
                   │ │ Each module publishes:          │ │ ││  │
                   │ │ • Display window (relay lanes)  │ │ ││  │
                   │ │ • Raw register read (no compute)│ │ ││  │
                   │ │ • For TUI/LCD output            │ │ ││  │
                   │ └─────────────────────────────────┘ │ ││  │
                   └─────────────────────────────────────┘ ││  │
                                                            ││  │
                   ┌──────────────────────────────────────┐││  │
                   │ INTERNAL CLOCK (250 MHz)             │││  │
                   │ • Reference oscillator               │││  │
                   │ • Drives pipeline fabric             │││  │
                   │ • (5 cells: reference only)          │││  │
                   └──────────────────────────────────────┘││  │
                                                            ││  │
        └────────────────────────────────────────────────────┘│  │
```

## Signal Flow Summary

```
Ingress Path (125 MHz → 250 MHz):
  adapter[CSV] → wire[relay] → nic[dedup+stamp] 
    → fifo_rx[CDC] → [seam latches] → dom[indexing]
    ↓
  dom[best prices] → candle, footprint, tpo [indicators]
    ↓
  candle_hist, footprint_hist → fractal, cbr, strategy
    ↓
  strategy[signal] → risk[approval] → OMS[orders] 
    → SOR[routing] → outbound[FIX]

Egress Path (250 MHz → broker):
  outbound → TX FIFO → NIC egress → broker

Display Buses (non-blocking, all domains):
  Every module → display_lane[raw_read] → TUI/LCD
  (No computation, just register window reads)

Timing Sync:
  TAI (authoritative) → tai_cdc[CDC] → all modules (via seam)
  TIMEFRAME[bar_boundary] → all indicators + strategy

Clock Domains:
  MAC (125 MHz): adapter, wire, nic, tai_cdc, fifo_rx[writer]
  INTERNAL (250 MHz): dom, indicators, strategy, risk, OMS, SOR, outbound, fifo_rx[reader]
  TAI: taiosc, tai (free-running, no discipline)
```
