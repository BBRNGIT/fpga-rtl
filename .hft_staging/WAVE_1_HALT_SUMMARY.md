# WAVE 1 — Build Halted and Documented

**Date:** 2026-06-09  
**Status:** Blocking — Do not proceed with WAVE 2 (fractal, CBR) until resolved

---

## What Happened

**WAVE 1 attempted to build three indicators (candle, footprint, TPO) using the emitter-first methodology:**

1. Created YAML specs (candle.yaml, footprint.yaml, tpo.yaml)
2. Generated PARTS_LIST.md files documenting registers
3. Generated emitter scripts (gen_*_net.py) via partslist-to-emitter.py
4. Generated gennet scripts (gennet.py) via partslist-to-gennet.py
5. Ran emitters to produce netlists (*.net.json)
6. Ran gennet to produce device C (*_gen.h)
7. Passed all gate validation (1-2c)
8. Graduated all three to immutable vault (.hft/)

**Result: Complete failure (silent).**

---

## The Problem: Stub Implementation

The generated device C files contain **register declarations only**. No actual RTL logic.

**Example: candle_gen.h**
```c
static inline void candle_tick(word_t *r) {
    /* READ phase */
    const word_t dom_bid_price = r[CANDLE_DOM_BID_PRICE];
    
    /* COMPUTE phase — all logic via cells (no native C operators). */
    /* No combinational logic in this netlist. */   ← STUB
    
    /* WRITE phase */
    r[CANDLE_CANDLE_STATE] = candle_state;
}
```

**All three modules are identical stubs:**
- candle_gen.h: 46 lines, 0 cell calls
- footprint_gen.h: 46 lines, 0 cell calls
- tpo_gen.h: 48 lines, 0 cell calls

**Comparison with real graduated modules:**
- fifo_rx_gen.h: 12448 lines, 4115 cell calls ✓ (real RTL)
- dom_gen.h: 388 lines, 83 cell calls ✓ (real RTL)
- taiosc_gen.h: 71 lines, 6 cell calls ✓ (real RTL)

---

## Why This Happened

### Root Cause 1: Incomplete Specifications

The YAML specs document *registers* (what state exists) but NOT *logic* (how state transforms).

**candle.yaml specifies:**
```yaml
dff_nodes:
  - name: CANDLE_BID_OPEN
    type: u64
    comment: First bid price in bar
```

**Missing:**
```yaml
comb_nodes:
  - name: CANDLE_BID_OPEN_UPDATE
    inputs: [CANDLE_BID_OPEN, DOM_BID_PRICE, CANDLE_OPEN_SET]
    logic: "cell_mux(CANDLE_OPEN_SET, DOM_BID_PRICE, CANDLE_BID_OPEN)"
    comment: "Latch first bid or hold"
```

**Implication:** Without comb_nodes, the emitter has no logic to emit.

### Root Cause 2: Incomplete Emitter Template

The emitter template (`emitter-template.jinja2`) generates only:
```json
{
  "config_nodes": [ ... ],
  "dff_nodes": [ ... ]
}
```

Missing:
```json
{
  "comb_nodes": [ ... ],        /* Gate-level primitives and wiring */
  "wiring": { ... },            /* Signal routing */
  "tables": { "fed_by": "..." } /* Which cell drives each table */
}
```

**Implication:** Netlist is a register declaration, not a circuit specification.

### Root Cause 3: Incomplete Gate Validation

The project gate validates:
- ✓ Netlist structure (validate.py)
- ✓ Build succeeds
- ✓ No native C operators in tick (grep for +/-/*)
- ✓ Device C is generated, not hand-written

Missing:
- ❌ **Device C contains actual flip-flop logic (cell calls)**

Empty COMPUTE phases pass gate 2b because `grep "\\+\\|\\-\\|\\*"` finds nothing (no operators to find). This is a false positive.

**Implication:** Stubs pass all gates and graduate successfully.

---

## Three Documents Created

### 1. WAVE_1_AUDIT.md
**What:** Detailed analysis of the stub issue.
**Purpose:** Proves the failure, identifies all three failure points, compares with real graduated modules.
**Length:** 254 lines

### 2. GATE_SH_UPDATE_REQUIRED.md
**What:** Specification for fixing gate.sh to catch this in the future.
**Purpose:** Adds gate stage 2d (logic content validation) — checks for cell calls, fails if COMPUTE is empty.
**Action:** Must be implemented before WAVE 2.
**Length:** 179 lines

### 3. INDICATOR_ARCHITECTURE_TEMPLATE.md
**What:** Complete template for specifying indicator logic at flip-flop level.
**Purpose:** Shows how to document candle (full example), footprint (POC tracking), and TPO (time accumulation) using only gate primitives.
**Action:** Must be followed to complete the build.
**Length:** 350 lines

---

## What Must Happen Before WAVE 2

### Phase 1: Gate Infrastructure Update (Critical)
**Responsible:** Architect  
**Task:** Implement gate stage 2d (logic content validation)  
**File:** `.hft_staging/gate.sh`  
**Change:** Add check for `cell_count > 0` in device C files  
**Validation:** Run gate against real modules (should pass) and WAVE 1 stubs (should fail)

### Phase 2: Indicator Architecture Documentation (Critical)
**Responsible:** Architect + founder  
**Task:** Document flip-flop-level logic for each indicator  
**Files:** Updated candle.yaml, footprint.yaml, tpo.yaml  
**Requirement:** Must include `comb_nodes` sections with explicit cell definitions per INDICATOR_ARCHITECTURE_TEMPLATE.md  
**Validation:** Architecture specs reviewed for correctness before proceeding to code generation

### Phase 3: Emitter Enhancement
**Responsible:** Infrastructure  
**Task:** Update emitter template to parse and emit comb_nodes  
**File:** `emitter-template.jinja2`  
**Change:** Add sections for comb_nodes, wiring, table fed_by attribution  
**Validation:** Regenerated netlists contain proper structure

### Phase 4: Regenerate WAVE 1
**Responsible:** Infrastructure  
**Task:** Rebuild candle, footprint, TPO with real logic  
**Steps:**
1. Run spec-to-partslist.py (should be unchanged)
2. Run partslist-to-emitter.py (updated template, should emit comb_nodes)
3. Run gen_*_net.py (should produce complete netlists)
4. Run gennet.py (should produce device C with cell calls)
5. Run .hft_staging/gate.sh (stage 2d should PASS with cell count > 0)
6. Graduate to vault

### Phase 5: WAVE 2 Proceed
**Responsible:** Infrastructure  
**Task:** Build fractal and CBR indicators  
**Prerequisites:** Candle WAVE 1 regeneration complete and gate-passing  
**Note:** Follow same template (INDICATOR_ARCHITECTURE_TEMPLATE.md) before code generation

---

## Immediate Actions (Today)

1. **✓ Halt all indicator builds** — Do not proceed with fractal or CBR
2. **✓ Document the failure** — Three audit documents created and committed
3. **⏳ Implement gate 2d** — Update gate.sh with logic content validation
4. **⏳ Review architecture specs** — Candle, footprint, TPO must include comb_nodes
5. **⏳ Regenerate WAVE 1** — With complete specs and updated tooling

---

## Files and Commits

**Audit and blocking documentation:**
- `.hft_staging/WAVE_1_AUDIT.md` (commit: d01076f)
- `.hft_staging/GATE_SH_UPDATE_REQUIRED.md` (commit: 833c78f)
- `.hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md` (commit: d01076f)
- `.hft_staging/WAVE_1_HALT_SUMMARY.md` (this file)

**Stubs in vault (should be reverted once WAVE 1 is regenerated with real logic):**
- `.hft/candle/` (stub: 0 cell calls)
- `.hft/footprint/` (stub: 0 cell calls)
- `.hft/tpo/` (stub: 0 cell calls)

**Specs needing architecture work:**
- `tools/generators/candle.yaml` (missing comb_nodes)
- `tools/generators/footprint.yaml` (missing comb_nodes)
- `tools/generators/tpo.yaml` (missing comb_nodes)

---

## Lessons Learned

1. **Gate validation must check logic content, not just syntax.**
   - No native operators ≠ has gate primitives
   - Empty COMPUTE sections pass syntactic validation but are incomplete architecturally

2. **Specifications must be complete before code generation.**
   - Registers alone are insufficient
   - Must specify combinational logic (comb_nodes) at gate-level primitives
   - Must specify wiring (signal flow) before emitter can generate netlists

3. **Emitter-first methodology is sound, but depends on complete specifications.**
   - Spec → Emitter → Netlist → gennet → Device C
   - Each stage amplifies incomplete input (garbage in, garbage out)
   - Validated specs are prerequisite for valid code generation

4. **Silent failures are the worst failures.**
   - Stubs pass all gates and graduate to vault
   - Only detected when tested (or audited late)
   - Gate 2d (logic content check) would catch this immediately

---

## Status Summary

| Component          | Status         | Action Required                                    |
|--------------------|----------------|-----------------------------------------------------|
| candle spec        | Incomplete     | Add comb_nodes per TEMPLATE                        |
| footprint spec     | Incomplete     | Add comb_nodes per TEMPLATE                        |
| tpo spec           | Incomplete     | Add comb_nodes per TEMPLATE                        |
| emitter template   | Incomplete     | Update to emit comb_nodes + wiring                 |
| gate.sh stage 2d   | Missing        | Implement logic content validation                 |
| WAVE 1 artifacts   | Stubs (vault)  | Regenerate with real logic; re-gate; re-graduate   |
| WAVE 2 (fractal)   | Blocked        | Wait for WAVE 1 completion + gate 2d implementation |

**Current Branch:** task/fifo_rx  
**Commits (this session):** 10 (specs + artifacts + audit docs)  
**Build Status:** HALTED (no further indicator builds until resolved)

---

## Next Session Instructions

1. Start by reading `.hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md`
2. Document the three indicators' flip-flop-level logic
3. Implement gate.sh stage 2d
4. Update emitter template to read comb_nodes
5. Regenerate WAVE 1 with real logic
6. Verify gate 2d passes with cell count > 0
7. Then proceed with WAVE 2 (fractal, CBR)

**Do not skip the architecture documentation step.** The problem started here, and it must be fixed here.
