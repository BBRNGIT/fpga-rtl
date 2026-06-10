# WAVE 1 Audit — Stub Implementation Issue

**Date:** 2026-06-09  
**Status:** BLOCKED — Device C files contain no flip-flop logic

---

## Summary

The three indicator modules (candle, footprint, TPO) were generated via the emitter-first methodology but **contain no actual RTL logic**. The generated `*_gen.h` files are register stubs only — they declare address slots and pre-read inputs, but have zero gate-level cell calls and zero computation.

**Example: candle_gen.h**
```c
/* COMPUTE phase — all logic via cells (no native C operators). */
/* No combinational logic in this netlist. */

/* WRITE phase — commit every dff (no read-after-write). */
r[CANDLE_CANDLE_STATE] = candle_state;
```

The COMPUTE phase is empty. No cells for OHLC tracking, volume accumulation, delta calculation, or imbalance detection exist.

---

## Root Cause

**Three-layer failure:**

### 1. Emitter (gen_*_net.py) — Incomplete Netlist Generation

The emitter generates only:
```json
{
  "config_nodes": [ /* inputs from other modules */ ],
  "dff_nodes": [ /* registered state */ ]
}
```

Missing:
```json
{
  "comb_nodes": [ /* NO gate definitions — the actual logic */ ],
  "wiring": { /* NO signal connections */ },
  "tables": { "fed_by": "cell_type" /* NO cell attribution */ }
}
```

**Why:** The emitter template (`emitter-template.jinja2`) only emits register declarations from the YAML spec. It has no knowledge of the *logic* that operates on those registers.

### 2. Specification (candle.yaml, footprint.yaml, tpo.yaml) — Registers Only

The YAML specs document:
- What registers exist (dff_nodes, tables, history_ring)
- Where inputs come from (cross_module_inputs)
- What outputs are published (seam_nodes)

Missing:
- **How registers transform.** No specification of:
  - Which cells compute OHLC open/high/low/close updates
  - Which cells track POC (running maximum)
  - Which cells implement diagonal imbalance (HVN/LVN detection)
  - Which cells accumulate CVD (cumulative delta)
  - How OHLC comparison gates work (cell_cmp_lt, cell_eqmask)

### 3. Gate.sh — No Validation of Logic Content

The project gate (`gate.sh`) validates:
- ✅ Netlist structure (validate.py)
- ✅ Build succeeds (make)
- ✅ No native C operators in tick (gate 2b — grep for +/-/\*)
- ✅ Device logic is generated, not hand-written (gate 2c)
- ✅ Clean-room rebuild matches (gate 3)

Missing:
- ❌ **Verification that device C contains actual flip-flop logic**
  - No check that cell calls exist
  - No check that comb_nodes are present in netlist
  - No check that COMPUTE phase is non-empty

Gate 2b (`grep "\\+\\|\\-\\|\\*"`) will pass an empty COMPUTE section because there are no operators to find. This is the architectural loophole.

---

## Comparison with Graduated Modules

**Graduated modules (built before meta-generators):**

| Module    | Lines | Cell Calls | Status          |
|-----------|-------|------------|-----------------|
| taiosc    | 71    | 6          | Real logic ✅   |
| tai       | ?     | ?          | Real logic ✅   |
| mac       | ?     | ?          | Real logic ✅   |
| internal  | 71    | 6          | Real logic ✅   |
| tai_cdc   | ?     | ?          | Real logic ✅   |
| nic       | ?     | ?          | Real logic ✅   |
| fifo_rx   | 12448 | 4115       | Real logic ✅   |
| dom       | 388   | 83         | Real logic ✅   |

**WAVE 1 indicators (meta-generated):**

| Module    | Lines | Cell Calls | Status           |
|-----------|-------|------------|-----------------|
| candle    | 46    | 0          | **Stub only** ❌ |
| footprint | 46    | 0          | **Stub only** ❌ |
| tpo       | 48    | 0          | **Stub only** ❌ |

---

## What's Missing: The Architecture Work

The emitter-first pipeline *assumes* that the YAML spec + PARTS_LIST.md contain a complete architectural description — including both data structure (registers) and control logic (gate-level primitives and their connections).

**For indicators to work, the YAML spec must specify:**

### Example: Candle OHLC Tracking

```yaml
# In candle.yaml, add to comb_nodes:
comb_nodes:
  - name: CANDLE_BID_OPEN_UPDATE
    inputs: [CANDLE_BID_OPEN, DOM_BID_PRICE, CANDLE_OPEN_SET]
    logic: "mux(CANDLE_OPEN_SET, DOM_BID_PRICE, CANDLE_BID_OPEN)"
    comment: "First bid price of bar (or hold)"
  
  - name: CANDLE_BID_HIGH_UPDATE
    inputs: [CANDLE_BID_HIGH, DOM_BID_PRICE]
    logic: "mux(cmp_lt(CANDLE_BID_HIGH, DOM_BID_PRICE), DOM_BID_PRICE, CANDLE_BID_HIGH)"
    comment: "Running maximum bid price"
  
  - name: CANDLE_BID_LOW_UPDATE
    inputs: [CANDLE_BID_LOW, DOM_BID_PRICE]
    logic: "mux(cmp_lt(DOM_BID_PRICE, CANDLE_BID_LOW), DOM_BID_PRICE, CANDLE_BID_LOW)"
    comment: "Running minimum bid price"

  - name: CANDLE_BID_DELTA
    inputs: [CANDLE_BID_OPEN, DOM_BID_PRICE]
    logic: "cell_addsub(DOM_BID_PRICE, CANDLE_BID_OPEN, 1)"  # subtract via 2's complement add
    comment: "Current - open price"
```

And the emitter must:
1. Parse these comb_node definitions from YAML
2. Generate netlist entries with cell type attribution
3. gennet must translate cell calls into C function calls (cell_mux, cell_addsub, etc.)

### Example: Footprint POC Tracking (Running Maximum)

```yaml
comb_nodes:
  - name: FP_POC_PRICE_UPDATE
    inputs: [FP_POC_PRICE, FP_POC_VOL, DOM_PROFILE[idx], DOM_ASK_QTY[idx], DOM_BID_QTY[idx]]
    logic: |
      current_vol = cell_addsub(DOM_ASK_QTY[idx], DOM_BID_QTY[idx], 0);
      is_new_max = cmp_lt(FP_POC_VOL, current_vol);
      mux(is_new_max, idx, FP_POC_PRICE)
    comment: "Track price level with maximum volume"
```

---

## What Must Happen

### Phase 1: Architecture Documentation (Human)
For each indicator (candle, footprint, TPO, fractal, CBR):
1. **Translate the indicator's high-level logic to flip-flop primitives**
   - OHLC → cell_mux (open), cmp_lt + mux (high/low), passthrough (close)
   - POC tracking → cell_addsub (accumulate volume), cmp_lt + mux (running max)
   - Imbalance detection → cell_eqmask (bid/ask compare), cell_addsub (delta)
   - CVD → cell_addsub (cumulative add)
2. **Document the combinational logic in the YAML spec**
   - Add `comb_nodes` section with gate-level cell definitions
   - Add `wiring` section specifying signal routing
   - Add `tables[].fed_by` attributes (which cell drives each table)

### Phase 2: Emitter Enhancement
Update emitter template to:
- Parse comb_nodes from YAML
- Emit them into the netlist JSON
- Include wiring specifications
- Preserve cell type attribution

### Phase 3: gennet Enhancement
Update gennet to:
- Read comb_nodes from netlist
- Translate cell definitions into C function calls
- Generate tick() logic that actually *computes* using cells

### Phase 4: Gate Update
**Critical:** Update gate.sh stage 2b to validate logic content:
```bash
# NEW CHECK: comb_nodes exist and cell calls appear in device C
cell_count=$(grep -o "cell_[a-z_]*(" ${GEN} | wc -l)
if [ "$cell_count" -eq 0 ]; then
    echo "[gate 2d] ERROR: no cell calls found in ${GEN}"
    echo "           Device C is a register stub, not flip-flop logic"
    exit 1
fi
```

---

## Immediate Actions Required

1. **Halt WAVE 1 graduation**  
   Candle, footprint, TPO should NOT be in vault yet; they're stubs masquerading as RTL.

2. **Document indicator logic architectures**  
   For each (candle, footprint, TPO, fractal, CBR), write out the flip-flop-level primitives and their connections in a design document before code generation.

3. **Update gate.sh**  
   Add a validation check that device C contains actual cell calls (cell_addsub, cell_mux, cell_eqmask, etc.). This is the missing safeguard.

4. **Extend YAML spec schema**  
   Add required sections:
   - `comb_nodes`: gate-level cell definitions
   - `wiring`: signal routing (which cells feed which registers)
   - `tables[].fed_by`: which cell type drives each table

5. **Regenerate indicators**  
   Once architecture is documented, regenerate netlists and device C with actual logic.

---

## Why This Matters

The emitter-first methodology is sound: specification → netlist → device C. But it **requires the specification to be complete** — registers + logic. We had registers only.

This was caught because:
- The stub files are *syntactically* valid C (gate passes 2a, 2b, 2c)
- The empty COMPUTE phase doesn't violate any rules ("no native operators" is satisfied by having none)
- No indicator has been tested yet (would have shown zero computation)

**The gate needs to fail on **missing logic content**, not just missing operators.**

---

## Files Affected

- `.hft_staging/candle/candle_gen.h` — stub, no cells
- `.hft_staging/footprint/footprint_gen.h` — stub, no cells
- `.hft_staging/tpo/tpo_gen.h` — stub, no cells
- `.hft/candle/`, `.hft/footprint/`, `.hft/tpo/` — graduated stubs (should be reverted)
- `.hft_staging/gate.sh` — missing validation check (needs update)

---

## Next Steps

**Do not proceed with fractal or CBR until:**
1. Indicator architecture is fully documented (design spec with gate-level primitives)
2. gate.sh is updated to validate logic content
3. WAVE 1 indicators are regenerated with actual RTL logic

This is a blocking issue on the entire indicator build pathway.
