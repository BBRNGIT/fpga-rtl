# TPO Architectural Parts List

**Purpose:** Hardware specification for building the Tpo (Indicator) component flip-flop-level from the netlist-generator (emitter-first workflow).

**Input to:** `gen_tpo_net.py` (emitter script) → `tpo.net.json` (netlist) → `gennet.py` → `tpo_gen.h` (generated device code)

**Date:** 2026-06-09
**Status:** Parts list complete; ready for emitter implementation

---

## 1. INPUT INTERFACE


Consumed from upstream modules via published lanes:


- `DOM_TIME` — Timestamp when price level was last active
  - Source: `dom` module
  - Type: `u64`



---

## 2. REGISTERS (State Flip-Flops)


Sequential state (updated at end of each tick):


```
TPO_MAX_TIME_PRICE            — 64-bit flip-flop
                            Comment: Price level with longest time exposure
                            Type: u64
```

```
TPO_MAX_TIME_VALUE            — 64-bit flip-flop
                            Comment: Maximum time value (in ticks)
                            Type: u64
```



---

## 3. MEMORY TABLES (Primary Accumulators)


Array registers indexed by address / level:


```
TPO_TIME_PROFILE[16384]    — 64-bit flip-flop array
                                        Depth: 16384 entries
                                        Index: PRICE_IDX
                                        Comment: Cumulative time spent at each price level
                                        Type: u64
```

```
TPO_TICK_COUNT[16384]    — 64-bit flip-flop array
                                        Depth: 16384 entries
                                        Index: PRICE_IDX
                                        Comment: Number of ticks at each price level
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
TPO_PROFILE_OUT            — 64-bit relay output
                            Source: TPO_TIME_PROFILE
                            Comment: TPO profile relay (sparse read-window)
                            Type: u64
```

```
TPO_MAX_PRICE_OUT            — 64-bit relay output
                            Source: TPO_MAX_TIME_PRICE
                            Comment: Maximum time price relay output
                            Type: u64
```

```
TPO_MAX_TIME_OUT            — 64-bit relay output
                            Source: TPO_MAX_TIME_VALUE
                            Comment: Maximum time value relay output
                            Type: u64
```


**Relay window:**
- 3 output lanes
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
TPO Base Address: TBD (reserved window; assigned at init)

Register Offsets (exact layout TBD per backplane allocation):

  Scalar Registers (each 8 bytes):


  0x0000 — TPO_MAX_TIME_PRICE

  0x0008 — TPO_MAX_TIME_VALUE




  Relay Outputs (each 8 bytes):

  0x0100 — TPO_PROFILE_OUT

  0x0108 — TPO_MAX_PRICE_OUT

  0x0110 — TPO_MAX_TIME_OUT




  Tables (sparse or dense; indexed by level):

  0x004000 onwards — TPO_TIME_PROFILE[16384]

  0x014000 onwards — TPO_TICK_COUNT[16384]


```

**Notes:**
- Scalar registers occupy first 64 KB (0x0000–0x10000)
- Tables may be sparse or dense (TBD based on netlist)
- All addresses are backplane-relative (module window offset + register offset)

---

## 7. DATAFLOW SUMMARY

```

Upstream (dom module):

  DOM_TIME → (input lane)



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


  TPO_PROFILE_OUT → (relay lane)

  TPO_MAX_PRICE_OUT → (relay lane)

  TPO_MAX_TIME_OUT → (relay lane)


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

- TPO reads only from **published lanes** (cross_module_inputs), NOT module internals
- TPO writes only to **its own window** (scalars, tables, relay outputs)
- Downstream modules read from **relay outputs only** (seam_nodes), NOT internal state

### Branchless Data Path (CLAUDE.md §4)

- No `if`/`else` in COMPUTE phase → all logic is ternary `cell_mux`
- No loops over bits → use `__builtin_popcount` if applicable
- No nested conditionals → flatten with bitwise boolean algebra
- No function calls in tick → all inline as cell chains

### Clock Domain (CLAUDE.md §5)

- TPO runs in **internal clock domain** (250 MHz pipeline FPGA)
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

1. **`gen_tpo_net.py`** — Python emitter script
   - Input: this parts list (or hardcoded logic matching it)
   - Output: `tpo.net.json` (declarative netlist)
   - Declares all registers, tables, accumulators, comparators, muxes

2. **`tpo.net.json`** — Declarative netlist (committed to git)
   - Validates: single-writer (no conflict), no overlap, no floating inputs
   - Checksums circuit; used to verify `tpo_gen.h` integrity

3. **`gennet.py`** — Netlist → C generator (shared; may already exist)
   - Input: `tpo.net.json`
   - Output: `tpo_gen.h` (generated device code)
   - **Never hand-write device logic; gennet produces it entirely.**

4. **`tpo.c` / `tpo.h`** — Host init, register setup, display helpers
   - `_init()` function to set base window, constants
   - Display code (read raw lanes, print state)
   - **No device logic here; host-side infrastructure only.**

5. **`test_synth.c`** — Thin test (≤45 lines)
   - Power-on + display
   - No clock stepping, data injection, or orchestration
   - Enforced by pre-commit hook `check_thin_tests.sh`

**Build sequence (exact commands):**
```bash
cd .hft_staging/tpo
python3 gen_tpo_net.py > tpo.net.json    # emitter produces netlist
python3 validate.py tpo.net.json              # validate
python3 gennet.py tpo.net.json > tpo_gen.h  # generator produces C
```

**Build-Sequence Law (enforced by gate stage 2c):**
- `tpo.net.json` is PRODUCED by the emitter; NEVER hand-written.
- `tpo_gen.h` is PRODUCED by gennet from the netlist; NEVER hand-written.
- Both are COMMITTED to git (proof that the circuit was generated, not hand-coded).
- Clean-room rebuild: running the three commands above must byte-match the committed files.

**Test expectations:**
- Coverage ≥ 95% (enforced by pre-commit hook)
- Tests are thin (power-on + display only)
- All gate stages pass (validate + build + 2b + 2c + clean-room)
