# FOOTPRINT Architectural Parts List

**Purpose:** Hardware specification for building the Footprint (Indicator) component flip-flop-level from the netlist-generator (emitter-first workflow).

**Input to:** `gen_footprint_net.py` (emitter script) → `footprint.net.json` (netlist) → `gennet.py` → `footprint_gen.h` (generated device code)

**Date:** 2026-06-09
**Status:** Parts list complete; ready for emitter implementation

---

## 1. INPUT INTERFACE


Consumed from upstream modules via published lanes:


- `DOM_ASK_QTY` — Ask quantity per price level (indexed by PRICE_IDX)
  - Source: `dom` module
  - Type: `u64`

- `DOM_BID_QTY` — Bid quantity per price level (indexed by PRICE_IDX)
  - Source: `dom` module
  - Type: `u64`

- `DOM_COUNT` — Event count per price level
  - Source: `dom` module
  - Type: `u64`

- `DOM_TIME` — Latest TAI timestamp per price level
  - Source: `dom` module
  - Type: `u64`

- `TF_BAR_SEQ_REG` — Timeframe bar sequence (for bar-boundary detection)
  - Source: `timeframe` module
  - Type: `u64`



---

## 2. REGISTERS (State Flip-Flops)


Sequential state (updated at end of each tick):


```
FP_POC_PRICE            — 64-bit flip-flop
                            Comment: Point of Control price (highest volume level)
                            Type: u64
```

```
FP_POC_VOL            — 64-bit flip-flop
                            Comment: POC total volume (bid + ask)
                            Type: u64
```

```
FP_POC_ASK_VOL            — 64-bit flip-flop
                            Comment: POC ask-side volume
                            Type: u64
```

```
FP_POC_BID_VOL            — 64-bit flip-flop
                            Comment: POC bid-side volume
                            Type: u64
```

```
FP_DELTA            — 64-bit flip-flop
                            Comment: POC-level delta (ask_vol - bid_vol at POC)
                            Type: u64
```

```
FP_VAH_PRICE            — 64-bit flip-flop
                            Comment: Value Area High (highest price where ask > bid)
                            Type: u64
```

```
FP_VAL_PRICE            — 64-bit flip-flop
                            Comment: Value Area Low (lowest price where bid > ask)
                            Type: u64
```

```
FP_ASK_IMB_PRICE            — 64-bit flip-flop
                            Comment: Ask-imbalanced price (HVN — highest value node)
                            Type: u64
```

```
FP_BID_IMB_PRICE            — 64-bit flip-flop
                            Comment: Bid-imbalanced price (LVN — lowest value node)
                            Type: u64
```

```
FP_BAR_CUM_DELTA            — 64-bit flip-flop
                            Comment: Cumulative delta (CVD — total ask_qty - total bid_qty)
                            Type: u64
```

```
FP_BAR_TOTAL_VOL            — 64-bit flip-flop
                            Comment: Total bar volume (all levels)
                            Type: u64
```

```
FP_MIN_PRICE            — 64-bit flip-flop
                            Comment: Bar minimum price touched
                            Type: u64
```

```
FP_MAX_PRICE            — 64-bit flip-flop
                            Comment: Bar maximum price touched
                            Type: u64
```

```
FP_BAR_PARITY            — 64-bit flip-flop
                            Comment: Virtual-reset parity tag (bit 63 of per-level entries)
                            Type: u64
```

```
FP_LAST_TF_SEQ            — 64-bit flip-flop
                            Comment: Last timeframe sequence seen (for bar-boundary sync)
                            Type: u64
```

```
FP_BAR_SEQ            — 64-bit flip-flop
                            Comment: Bar sequence number
                            Type: u64
```

```
FP_STACKED_IMB_BUY            — 64-bit flip-flop
                            Comment: Consecutive ask-imbalanced ticks above POC
                            Type: u64
```

```
FP_STACKED_IMB_SELL            — 64-bit flip-flop
                            Comment: Consecutive bid-imbalanced ticks below POC
                            Type: u64
```

```
FP_DIV_STAGE            — 64-bit flip-flop
                            Comment: Division pipeline stage counter (0-3)
                            Type: u64
```

```
FP_DIV_VALID            — 64-bit flip-flop
                            Comment: Division result valid flag
                            Type: u64
```

```
FP_DIV_VA_NUMER            — 64-bit flip-flop
                            Comment: Value-area numerator
                            Type: u64
```

```
FP_DIV_VA_DENOM            — 64-bit flip-flop
                            Comment: Value-area denominator
                            Type: u64
```

```
FP_DIV_ASK_NUMER            — 64-bit flip-flop
                            Comment: Ask-imbalance numerator
                            Type: u64
```

```
FP_DIV_ASK_DENOM            — 64-bit flip-flop
                            Comment: Ask-imbalance denominator
                            Type: u64
```

```
FP_DIV_ASK_RESULT            — 64-bit flip-flop
                            Comment: Ask-imbalance result (fixed-point)
                            Type: u64
```

```
FP_DIV_BID_NUMER            — 64-bit flip-flop
                            Comment: Bid-imbalance numerator
                            Type: u64
```

```
FP_DIV_BID_DENOM            — 64-bit flip-flop
                            Comment: Bid-imbalance denominator
                            Type: u64
```

```
FP_DIV_BID_RESULT            — 64-bit flip-flop
                            Comment: Bid-imbalance result (fixed-point)
                            Type: u64
```

```
FP_DIV_VA_RESULT            — 64-bit flip-flop
                            Comment: Value-area result (fixed-point)
                            Type: u64
```



---

## 3. MEMORY TABLES (Primary Accumulators)


Array registers indexed by address / level:


```
FP_ASK_VOL[16384]    — 64-bit flip-flop array
                                        Depth: 16384 entries
                                        Index: PRICE_IDX
                                        Comment: Ask volume accumulator per price level (parity-tagged)
                                        Type: u64
```

```
FP_BID_VOL[16384]    — 64-bit flip-flop array
                                        Depth: 16384 entries
                                        Index: PRICE_IDX
                                        Comment: Bid volume accumulator per price level (parity-tagged)
                                        Type: u64
```

```
FP_PROFILE[16384]    — 64-bit flip-flop array
                                        Depth: 16384 entries
                                        Index: PRICE_IDX
                                        Comment: Total volume profile per price level
                                        Type: u64
```


**Indexing model:**
- All tables indexed by `PRICE_IDX` (price-level index)
- Index range: 0 to 16383
- All tables indexed **in parallel** (no serialization)

**Per-level hardware:**
- Each table entry is a 64-bit accumulator (can be incremented, latched, or cleared)
- Update logic is structural: `cell_addsub` (ripple-carry), `cell_mux` (multiplexer), or direct latch
- No branches: all deltas computed in COMPUTE phase, written in WRITE phase



---

## 4. PUBLISHED RELAY OUTPUTS


Lanes deposited for downstream consumers (non-blocking, visible immediately):


```
FP_POC_OUT            — 64-bit relay output
                            Source: FP_POC_PRICE
                            Comment: POC price relay output
                            Type: u64
```

```
FP_POC_VOL_OUT            — 64-bit relay output
                            Source: FP_POC_VOL
                            Comment: POC volume relay output
                            Type: u64
```

```
FP_VAH_OUT            — 64-bit relay output
                            Source: FP_VAH_PRICE
                            Comment: Value area high relay output
                            Type: u64
```

```
FP_VAL_OUT            — 64-bit relay output
                            Source: FP_VAL_PRICE
                            Comment: Value area low relay output
                            Type: u64
```

```
FP_DELTA_OUT            — 64-bit relay output
                            Source: FP_BAR_CUM_DELTA
                            Comment: Cumulative delta (CVD) relay output
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
FOOTPRINT Base Address: TBD (reserved window; assigned at init)

Register Offsets (exact layout TBD per backplane allocation):

  Scalar Registers (each 8 bytes):


  0x0000 — FP_POC_PRICE

  0x0008 — FP_POC_VOL

  0x0010 — FP_POC_ASK_VOL

  0x0018 — FP_POC_BID_VOL

  0x0020 — FP_DELTA

  0x0028 — FP_VAH_PRICE

  0x0030 — FP_VAL_PRICE

  0x0038 — FP_ASK_IMB_PRICE

  0x0040 — FP_BID_IMB_PRICE

  0x0048 — FP_BAR_CUM_DELTA

  0x0050 — FP_BAR_TOTAL_VOL

  0x0058 — FP_MIN_PRICE

  0x0060 — FP_MAX_PRICE

  0x0068 — FP_BAR_PARITY

  0x0070 — FP_LAST_TF_SEQ

  0x0078 — FP_BAR_SEQ

  0x0080 — FP_STACKED_IMB_BUY

  0x0088 — FP_STACKED_IMB_SELL

  0x0090 — FP_DIV_STAGE

  0x0098 — FP_DIV_VALID

  0x00A0 — FP_DIV_VA_NUMER

  0x00A8 — FP_DIV_VA_DENOM

  0x00B0 — FP_DIV_ASK_NUMER

  0x00B8 — FP_DIV_ASK_DENOM

  0x00C0 — FP_DIV_ASK_RESULT

  0x00C8 — FP_DIV_BID_NUMER

  0x00D0 — FP_DIV_BID_DENOM

  0x00D8 — FP_DIV_BID_RESULT

  0x00E0 — FP_DIV_VA_RESULT




  Relay Outputs (each 8 bytes):

  0x0100 — FP_POC_OUT

  0x0108 — FP_POC_VOL_OUT

  0x0110 — FP_VAH_OUT

  0x0118 — FP_VAL_OUT

  0x0120 — FP_DELTA_OUT




  Tables (sparse or dense; indexed by level):

  0x004000 onwards — FP_ASK_VOL[16384]

  0x014000 onwards — FP_BID_VOL[16384]

  0x024000 onwards — FP_PROFILE[16384]


```

**Notes:**
- Scalar registers occupy first 64 KB (0x0000–0x10000)
- Tables may be sparse or dense (TBD based on netlist)
- All addresses are backplane-relative (module window offset + register offset)

---

## 7. DATAFLOW SUMMARY

```

Upstream (dom module):

  DOM_ASK_QTY → (input lane)

  DOM_BID_QTY → (input lane)

  DOM_COUNT → (input lane)

  DOM_TIME → (input lane)

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


  FP_POC_OUT → (relay lane)

  FP_POC_VOL_OUT → (relay lane)

  FP_VAH_OUT → (relay lane)

  FP_VAL_OUT → (relay lane)

  FP_DELTA_OUT → (relay lane)


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

- FOOTPRINT reads only from **published lanes** (cross_module_inputs), NOT module internals
- FOOTPRINT writes only to **its own window** (scalars, tables, relay outputs)
- Downstream modules read from **relay outputs only** (seam_nodes), NOT internal state

### Branchless Data Path (CLAUDE.md §4)

- No `if`/`else` in COMPUTE phase → all logic is ternary `cell_mux`
- No loops over bits → use `__builtin_popcount` if applicable
- No nested conditionals → flatten with bitwise boolean algebra
- No function calls in tick → all inline as cell chains

### Clock Domain (CLAUDE.md §5)

- FOOTPRINT runs in **internal clock domain** (250 MHz pipeline FPGA)
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

1. **`gen_footprint_net.py`** — Python emitter script
   - Input: this parts list (or hardcoded logic matching it)
   - Output: `footprint.net.json` (declarative netlist)
   - Declares all registers, tables, accumulators, comparators, muxes

2. **`footprint.net.json`** — Declarative netlist (committed to git)
   - Validates: single-writer (no conflict), no overlap, no floating inputs
   - Checksums circuit; used to verify `footprint_gen.h` integrity

3. **`gennet.py`** — Netlist → C generator (shared; may already exist)
   - Input: `footprint.net.json`
   - Output: `footprint_gen.h` (generated device code)
   - **Never hand-write device logic; gennet produces it entirely.**

4. **`footprint.c` / `footprint.h`** — Host init, register setup, display helpers
   - `_init()` function to set base window, constants
   - Display code (read raw lanes, print state)
   - **No device logic here; host-side infrastructure only.**

5. **`test_synth.c`** — Thin test (≤45 lines)
   - Power-on + display
   - No clock stepping, data injection, or orchestration
   - Enforced by pre-commit hook `check_thin_tests.sh`

**Build sequence (exact commands):**
```bash
cd .hft_staging/footprint
python3 gen_footprint_net.py > footprint.net.json    # emitter produces netlist
python3 validate.py footprint.net.json              # validate
python3 gennet.py footprint.net.json > footprint_gen.h  # generator produces C
```

**Build-Sequence Law (enforced by gate stage 2c):**
- `footprint.net.json` is PRODUCED by the emitter; NEVER hand-written.
- `footprint_gen.h` is PRODUCED by gennet from the netlist; NEVER hand-written.
- Both are COMMITTED to git (proof that the circuit was generated, not hand-coded).
- Clean-room rebuild: running the three commands above must byte-match the committed files.

**Test expectations:**
- Coverage ≥ 95% (enforced by pre-commit hook)
- Tests are thin (power-on + display only)
- All gate stages pass (validate + build + 2b + 2c + clean-room)
