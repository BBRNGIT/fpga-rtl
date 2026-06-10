# CANDLE Architectural Parts List

**Purpose:** Hardware specification for building the Candle (Indicator) component flip-flop-level from the netlist-generator (emitter-first workflow).

**Input to:** `gen_candle_net.py` (emitter script) → `candle.net.json` (netlist) → `gennet.py` → `candle_gen.h` (generated device code)

**Date:** 2026-06-09
**Status:** Parts list complete; ready for emitter implementation

---

## 1. INPUT INTERFACE


Consumed from upstream modules via published lanes:


- `DOM_BID_PRICE` — Best bid price (highest bid level)
  - Source: `dom` module
  - Type: `u64`

- `DOM_ASK_PRICE` — Best ask price (lowest ask level)
  - Source: `dom` module
  - Type: `u64`

- `DOM_BID_QTY` — Bid quantity per price level (indexed by PRICE_IDX)
  - Source: `dom` module
  - Type: `u64`

- `DOM_ASK_QTY` — Ask quantity per price level (indexed by PRICE_IDX)
  - Source: `dom` module
  - Type: `u64`

- `TF_BAR_SEQ_REG` — Timeframe bar sequence (for bar-boundary detection)
  - Source: `timeframe` module
  - Type: `u64`



---

## 2. REGISTERS (State Flip-Flops)


Sequential state (updated at end of each tick):


```
CANDLE_BID_OPEN            — 64-bit flip-flop
                            Comment: First bid price in bar
                            Type: u64
```

```
CANDLE_BID_HIGH            — 64-bit flip-flop
                            Comment: Highest bid price in bar
                            Type: u64
```

```
CANDLE_BID_LOW            — 64-bit flip-flop
                            Comment: Lowest bid price in bar
                            Type: u64
```

```
CANDLE_BID_CLOSE            — 64-bit flip-flop
                            Comment: Most recent bid price
                            Type: u64
```

```
CANDLE_ASK_OPEN            — 64-bit flip-flop
                            Comment: First ask price in bar
                            Type: u64
```

```
CANDLE_ASK_HIGH            — 64-bit flip-flop
                            Comment: Highest ask price in bar
                            Type: u64
```

```
CANDLE_ASK_LOW            — 64-bit flip-flop
                            Comment: Lowest ask price in bar
                            Type: u64
```

```
CANDLE_ASK_CLOSE            — 64-bit flip-flop
                            Comment: Most recent ask price
                            Type: u64
```

```
CANDLE_VOLUME_BID            — 64-bit flip-flop
                            Comment: Cumulative bid ticks in bar
                            Type: u64
```

```
CANDLE_VOLUME_ASK            — 64-bit flip-flop
                            Comment: Cumulative ask ticks in bar
                            Type: u64
```

```
CANDLE_TRUE_RANGE_BID            — 64-bit flip-flop
                            Comment: Bid high - bid low (bid-side range only)
                            Type: u64
```

```
CANDLE_TRUE_RANGE_ASK            — 64-bit flip-flop
                            Comment: Ask high - ask low (ask-side range only)
                            Type: u64
```

```
CANDLE_INTRABAR_QTY_DELTA            — 64-bit flip-flop
                            Comment: Cumulative ask_qty - bid_qty over bar
                            Type: u64
```

```
CANDLE_OPEN_SET            — 64-bit flip-flop
                            Comment: Flag—first tick of bar processed
                            Type: u64
```

```
CANDLE_LAST_TF_SEQ            — 64-bit flip-flop
                            Comment: Last timeframe sequence seen (for bar-boundary sync)
                            Type: u64
```

```
CANDLE_BAR_SEQ            — 64-bit flip-flop
                            Comment: Bar sequence number
                            Type: u64
```

```
CANDLE_BAR_PARITY            — 64-bit flip-flop
                            Comment: Virtual-reset parity tag (bit 63)
                            Type: u64
```

```
CANDLE_PREV_TRADE_CNT            — 64-bit flip-flop
                            Comment: Last trade count (for delta calculation)
                            Type: u64
```

```
CANDLE_MID            — 64-bit flip-flop
                            Comment: Mid price ((bid_high + ask_low) / 2, non-blocking convenience)
                            Type: u64
```

```
CANDLE_COMP_BID_OPEN            — 64-bit flip-flop
                            Comment: Completed bar bid open
                            Type: u64
```

```
CANDLE_COMP_BID_HIGH            — 64-bit flip-flop
                            Comment: Completed bar bid high
                            Type: u64
```

```
CANDLE_COMP_BID_LOW            — 64-bit flip-flop
                            Comment: Completed bar bid low
                            Type: u64
```

```
CANDLE_COMP_BID_CLOSE            — 64-bit flip-flop
                            Comment: Completed bar bid close
                            Type: u64
```

```
CANDLE_COMP_ASK_OPEN            — 64-bit flip-flop
                            Comment: Completed bar ask open
                            Type: u64
```

```
CANDLE_COMP_ASK_HIGH            — 64-bit flip-flop
                            Comment: Completed bar ask high
                            Type: u64
```

```
CANDLE_COMP_ASK_LOW            — 64-bit flip-flop
                            Comment: Completed bar ask low
                            Type: u64
```

```
CANDLE_COMP_ASK_CLOSE            — 64-bit flip-flop
                            Comment: Completed bar ask close
                            Type: u64
```

```
CANDLE_COMP_VOLUME_BID            — 64-bit flip-flop
                            Comment: Completed bar bid volume
                            Type: u64
```

```
CANDLE_COMP_VOLUME_ASK            — 64-bit flip-flop
                            Comment: Completed bar ask volume
                            Type: u64
```

```
CANDLE_COMP_TRUE_RANGE_BID            — 64-bit flip-flop
                            Comment: Completed bar bid true range
                            Type: u64
```

```
CANDLE_COMP_TRUE_RANGE_ASK            — 64-bit flip-flop
                            Comment: Completed bar ask true range
                            Type: u64
```

```
CANDLE_COMP_INTRABAR_QTY_DELTA            — 64-bit flip-flop
                            Comment: Completed bar intrabar qty delta
                            Type: u64
```

```
CANDLE_COMP_TAI            — 64-bit flip-flop
                            Comment: Completed bar TAI timestamp
                            Type: u64
```

```
CANDLE_COMP_BAR_SEQ            — 64-bit flip-flop
                            Comment: Completed bar sequence
                            Type: u64
```



---

## 3. MEMORY TABLES (Primary Accumulators)


No tables — scalar state only.


---

## 4. PUBLISHED RELAY OUTPUTS


Lanes deposited for downstream consumers (non-blocking, visible immediately):


```
CANDLE_BID_OHLC_OUT            — 64-bit relay output
                            Source: CANDLE_BID_CLOSE
                            Comment: Bid OHLC relay (read CANDLE_BID_OPEN/HIGH/LOW/CLOSE)
                            Type: u64
```

```
CANDLE_ASK_OHLC_OUT            — 64-bit relay output
                            Source: CANDLE_ASK_CLOSE
                            Comment: Ask OHLC relay (read CANDLE_ASK_OPEN/HIGH/LOW/CLOSE)
                            Type: u64
```

```
CANDLE_VOLUME_OUT            — 64-bit relay output
                            Source: CANDLE_VOLUME_BID
                            Comment: Volume relay (read both VOLUME_BID and VOLUME_ASK)
                            Type: u64
```

```
CANDLE_TRUE_RANGE_OUT            — 64-bit relay output
                            Source: CANDLE_TRUE_RANGE_BID
                            Comment: True range relay (read both TR_BID and TR_ASK)
                            Type: u64
```

```
CANDLE_DELTA_OUT            — 64-bit relay output
                            Source: CANDLE_INTRABAR_QTY_DELTA
                            Comment: Intrabar delta relay output
                            Type: u64
```


**Relay window:**
- 5 output lanes
- Updated passively (whenever source updates)
- Read by downstream indicators and strategy modules



---

## 5. CONTROL SIGNALS & GATES

- **Clock strobe:** Self-run from power bit (or gated by upstream)
- **Read gate:** All inputs sampled when valid
- **Write gate:** All outputs latched on clock edge

---

## 6. ADDRESS WINDOW LAYOUT

```
CANDLE Base Address: TBD (reserved window; assigned at init)

Register Offsets (exact layout TBD per backplane allocation):

  Scalar Registers (each 8 bytes):


  0x0000 — CANDLE_BID_OPEN

  0x0008 — CANDLE_BID_HIGH

  0x0010 — CANDLE_BID_LOW

  0x0018 — CANDLE_BID_CLOSE

  0x0020 — CANDLE_ASK_OPEN

  0x0028 — CANDLE_ASK_HIGH

  0x0030 — CANDLE_ASK_LOW

  0x0038 — CANDLE_ASK_CLOSE

  0x0040 — CANDLE_VOLUME_BID

  0x0048 — CANDLE_VOLUME_ASK

  0x0050 — CANDLE_TRUE_RANGE_BID

  0x0058 — CANDLE_TRUE_RANGE_ASK

  0x0060 — CANDLE_INTRABAR_QTY_DELTA

  0x0068 — CANDLE_OPEN_SET

  0x0070 — CANDLE_LAST_TF_SEQ

  0x0078 — CANDLE_BAR_SEQ

  0x0080 — CANDLE_BAR_PARITY

  0x0088 — CANDLE_PREV_TRADE_CNT

  0x0090 — CANDLE_MID

  0x0098 — CANDLE_COMP_BID_OPEN

  0x00A0 — CANDLE_COMP_BID_HIGH

  0x00A8 — CANDLE_COMP_BID_LOW

  0x00B0 — CANDLE_COMP_BID_CLOSE

  0x00B8 — CANDLE_COMP_ASK_OPEN

  0x00C0 — CANDLE_COMP_ASK_HIGH

  0x00C8 — CANDLE_COMP_ASK_LOW

  0x00D0 — CANDLE_COMP_ASK_CLOSE

  0x00D8 — CANDLE_COMP_VOLUME_BID

  0x00E0 — CANDLE_COMP_VOLUME_ASK

  0x00E8 — CANDLE_COMP_TRUE_RANGE_BID

  0x00F0 — CANDLE_COMP_TRUE_RANGE_ASK

  0x00F8 — CANDLE_COMP_INTRABAR_QTY_DELTA

  0x0100 — CANDLE_COMP_TAI

  0x0108 — CANDLE_COMP_BAR_SEQ




  Relay Outputs (each 8 bytes):

  0x0100 — CANDLE_BID_OHLC_OUT

  0x0108 — CANDLE_ASK_OHLC_OUT

  0x0110 — CANDLE_VOLUME_OUT

  0x0118 — CANDLE_TRUE_RANGE_OUT

  0x0120 — CANDLE_DELTA_OUT




```

**Notes:**
- Scalar registers occupy first 64 KB (0x0000–0x10000)
- Tables may be sparse or dense (TBD based on netlist)
- All addresses are backplane-relative (module window offset + register offset)

---

## 7. DATAFLOW SUMMARY

```

Upstream (dom module):

  DOM_BID_PRICE → (input lane)

  DOM_ASK_PRICE → (input lane)

  DOM_BID_QTY → (input lane)

  DOM_ASK_QTY → (input lane)

  TF_BAR_SEQ_REG → (input lane)



READ PHASE:
  — Pre-read all cross-module inputs and current table values
  — Compute table indices, deltas, and comparisons (combinational)

COMPUTE PHASE:
  — All logic is branchless: muxes and gates only
  — Update decisions are combinational (driven by input gates)

WRITE PHASE:
  — Write updated registers (all DFF nodes, all table entries)
  — Write relay outputs (seam lanes)
  — No REG_R calls in WRITE phase

Downstream (indicator/strategy):


  CANDLE_BID_OHLC_OUT → (relay lane)

  CANDLE_ASK_OHLC_OUT → (relay lane)

  CANDLE_VOLUME_OUT → (relay lane)

  CANDLE_TRUE_RANGE_OUT → (relay lane)

  CANDLE_DELTA_OUT → (relay lane)


```

---

## 8. ARCHITECTURAL CONSTRAINTS

### Gate-Level Arithmetic (CLAUDE.md §2)

All datapath operations must be structural cells, **NO native C operators** in generated tick:

- **Increment/Decrement:** `cell_addsub(qty, delta_mux)` — ripple-carry adder chain
  - No native `++` or `+=`

- **Comparison:** `cell_eqmask(a != b)` — equality comparator
  - No native `==` or `!=`

- **Selection:** `cell_mux(sel, a, b)` — 2-to-1 or N-to-1 mux
  - No native `?:` ternary operator

### Module Barrier Law (CLAUDE.md §3)

- CANDLE reads only from **published lanes** (cross_module_inputs), NOT module internals
- CANDLE writes only to **its own window** (scalars, tables, relay outputs)
- Downstream modules read from **relay outputs only** (seam_nodes), NOT internal state

### Branchless Data Path (CLAUDE.md §4)

- No `if`/`else` in COMPUTE phase → all logic is ternary `cell_mux`
- No loops over bits → use `__builtin_popcount` if applicable
- No nested conditionals → flatten with bitwise boolean algebra
- No function calls in tick → all inline as cell chains

### Clock Domain (CLAUDE.md §5)

- CANDLE runs in **internal clock domain** (250 MHz pipeline FPGA)
- Receives inputs from **published upstream lanes** (already clock-domain crossed if needed)
- No CDC needed if all inputs are in-domain

### Read→Compute→Write Phases (CLAUDE.md §6)

```c
CLOCK_PHASE_READ
  // Pre-read all upstream inputs (cross_module_inputs)
  // Pre-read current state (dff_nodes, tables)
  // Compute combinational deltas and indices

CLOCK_PHASE_COMPUTE
  // All delta detection, comparisons, table index computation, gate logic
  // No REG_R calls here; use pre-read values

CLOCK_PHASE_WRITE
  // Write all updated registers (dff_nodes, tables)
  // Write all relay outputs (seam_nodes)
  // No REG_R calls in WRITE phase
```

---

## 9. COMMIT EXPECTATIONS

**Deliverables (emitter-first workflow):**

1. **`gen_candle_net.py`** — Python emitter script
   - Input: this parts list (or hardcoded logic matching it)
   - Output: `candle.net.json` (declarative netlist)
   - Declares all registers, tables, accumulators, comparators, muxes

2. **`candle.net.json`** — Declarative netlist (committed to git)
   - Validates: single-writer (no conflict), no overlap, no floating inputs
   - Checksums circuit; used to verify `candle_gen.h` integrity

3. **`gennet.py`** — Netlist → C generator (shared; may already exist)
   - Input: `candle.net.json`
   - Output: `candle_gen.h` (generated device code)
   - **Never hand-write device logic; gennet produces it entirely.**

4. **`candle.c` / `candle.h`** — Host init, register setup, display helpers
   - `_init()` function to set base window, constants
   - Display code (read raw lanes, print state)
   - **No device logic here; host-side infrastructure only.**

5. **`test_synth.c`** — Thin test (≤45 lines)
   - Power-on + display
   - No clock stepping, data injection, or orchestration
   - Enforced by pre-commit hook `check_thin_tests.sh`

**Build sequence (exact commands):**
```bash
cd .hft_staging/candle
python3 gen_candle_net.py > candle.net.json    # emitter produces netlist
python3 validate.py candle.net.json              # validate
python3 gennet.py candle.net.json > candle_gen.h  # generator produces C
```

**Build-Sequence Law (enforced by gate stage 2c):**
- `candle.net.json` is PRODUCED by the emitter; NEVER hand-written.
- `candle_gen.h` is PRODUCED by gennet from the netlist; NEVER hand-written.
- Both are COMMITTED to git (proof that the circuit was generated, not hand-coded).
- Clean-room rebuild: running the three commands above must byte-match the committed files.

**Test expectations:**
- Coverage ≥ 95% (enforced by pre-commit hook)
- Tests are thin (power-on + display only)
- All gate stages pass (validate + build + 2b + 2c + clean-room)
