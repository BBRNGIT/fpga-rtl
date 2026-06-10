# gate.sh — Core Update Required

**Issue:** The project gate validates that device C contains no native operators (gate 2b) but does NOT verify that device C contains *any actual flip-flop logic at all*.

**Current gates pass:** Stub C files with empty COMPUTE phases pass all validation.

**Required fix:** Add gate stage 2d — Logic Content Validation.

---

## Current Gate Stages (gate.sh)

1. **validate** — Netlist structure (single-writer, power-of-2, no-floating)
2. **build** — Compile + thin test
3. **2b** — Gate-level arithmetic (no native +/-/*)
4. **2c** — Build-sequence (device logic is generated, not hand-written)
5. **3** — Clean-room rebuild (byte-identical from HEAD)

---

## Problem: Stage 2b is Insufficient

**Gate 2b checks:**
```bash
grep "\\+\\|\\-\\|\\*" ${GEN}
```

This passes if:
- File has no operators (correct: structural logic only) ✓
- File has operators but they're in comments (wrong: would fail) ✓
- **File has zero COMPUTE logic at all (wrong: would PASS)** ❌

**Example: empty COMPUTE section**
```c
static inline void candle_tick(word_t *r) {
    /* READ phase */
    const word_t dom_bid_price = r[CANDLE_DOM_BID_PRICE];
    
    /* COMPUTE phase — all logic via cells (no native C operators). */
    /* No combinational logic in this netlist. */   // <- COMMENT (not checked)
    
    /* WRITE phase */
    r[CANDLE_CANDLE_STATE] = candle_state;
}
```

This passes gate 2b because `grep "\\+\\|\\-\\|\\*"` finds nothing — not because there's good structural logic, but because there's *no logic at all*.

---

## Solution: Add Gate Stage 2d — Logic Content Validation

Insert between current stages 2c and 3:

```bash
echo "==> [gate] 2d/3 flip-flop logic content (actual cell calls required)"
( cd "$DIR" && {
    cell_count=$(grep -o "cell_[a-z_]*(" ${GEN} 2>/dev/null | wc -l)
    if [ "$cell_count" -eq 0 ]; then
        echo "    FAIL: no cell calls found in ${GEN}"
        echo "    Device C is a register stub, not flip-flop-level RTL"
        echo "    Verify: spec includes comb_nodes, emitter generated wiring, gennet produced cells"
        exit 1
    fi
    echo "    ${GEN}: ${cell_count} cell calls — OK"
} )
```

**Rationale:**
- Every flip-flop-level device *must* contain at least one structural cell call
- cell_addsub, cell_mux, cell_eqmask, cell_gate, cmp_lt, cell_rol, cell_popcount, etc.
- An empty device is incomplete by definition
- This catches the architecture gap early (at gate time, not at runtime/test)

---

## Updated Gate Output

Current (insufficient):
```
==> [gate] 1/3 validate netlist
==> [gate] 2/3 build + thin test (working tree)
==> [gate] 2b/3 gate-level arithmetic (no native +/-/* in generated tick)
    candle_gen.h tick: no native +/-/* — OK
==> [gate] 2c/3 build-sequence (device logic generated, not hand-written)
    no hand-written device logic — OK
==> [gate] 3/3 clean-room build from committed HEAD
==> [gate] PASS: .hft_staging/candle    ← WRONG: stub should fail here
```

Updated (catches stubs):
```
==> [gate] 1/3 validate netlist
==> [gate] 2/3 build + thin test (working tree)
==> [gate] 2b/3 gate-level arithmetic (no native +/-/* in generated tick)
    candle_gen.h tick: no native +/-/* — OK
==> [gate] 2c/3 build-sequence (device logic generated, not hand-written)
    no hand-written device logic — OK
==> [gate] 2d/3 flip-flop logic content (actual cell calls required)
    FAIL: no cell calls found in candle_gen.h
    Device C is a register stub, not flip-flop-level RTL
    Verify: spec includes comb_nodes, emitter generated wiring, gennet produced cells
==> [gate] FAIL: .hft_staging/candle    ← CORRECT: blocks stub
```

---

## Implementation

**File to update:** `.hft_staging/gate.sh`

**Location:** After the 2c check, before the 3/3 clean-room section

**Insertion point:** Around line 80 (after the "build-sequence" stage)

**Code to add:**
```bash
echo "==> [gate] 2d/3 flip-flop logic content (cell calls in device C)"
( cd "$DIR" && {
    cell_count=$(grep -o "cell_[a-z_]*(" ${GEN} 2>/dev/null | wc -l)
    if [ "$cell_count" -eq 0 ]; then
        echo "    FAIL: no structural cell calls found in ${GEN}"
        echo "    Device C appears to be a register stub (empty COMPUTE phase)"
        echo ""
        echo "    Possible causes:"
        echo "    1. Netlist has no comb_nodes (emitter did not generate logic)"
        echo "    2. YAML spec omitted gate-level primitive definitions"
        echo "    3. gennet did not translate comb_nodes to cell calls"
        echo ""
        echo "    Verify that:"
        echo "    - Spec includes comb_nodes with gate-level definitions"
        echo "    - Emitter generated complete netlist with wiring"
        echo "    - gennet translated cells to function calls (cell_addsub, cell_mux, etc.)"
        exit 1
    fi
    echo "    ${GEN}: ${cell_count} cell calls — OK"
} )
```

---

## Why This is Critical

1. **Prevents silent failures.** Without this check, stub devices graduate successfully, are tested (produce zeros), and only fail at runtime when they don't compute.

2. **Enforces the architecture.** Flip-flop-level = gate primitives. No gates = not flip-flop-level.

3. **Catches specification gaps early.** If a spec has no comb_nodes, the gate fails before graduation, signaling incomplete architecture documentation.

4. **Reverses the WAVE 1 issue.** candle, footprint, TPO would have been caught at gate time instead of passing through to vault as stubs.

---

## Related Actions

Once gate.sh is updated with 2d:

1. **WAVE 1 stubs fail gate immediately** (good, prevents further graduation)
2. **Architecture work becomes mandatory** (spec must include comb_nodes before gate can pass)
3. **Emitter enhancements become testable** (regenerate indicators, watch gate 2d pass with real logic)
4. **Future indicators start with correct gate discipline** (prevents repeat of WAVE 1)

---

## Testing the Gate Update

After adding gate 2d, run against known modules:

```bash
# Should PASS (has real cell calls)
.hft_staging/gate.sh .hft_staging/dom
.hft_staging/gate.sh .hft_staging/nic
.hft_staging/gate.sh .hft_staging/fifo_rx

# Should FAIL at gate 2d (no cell calls)
.hft_staging/gate.sh .hft_staging/candle     # Expected: FAIL (currently PASS)
.hft_staging/gate.sh .hft_staging/footprint  # Expected: FAIL (currently PASS)
.hft_staging/gate.sh .hft_staging/tpo        # Expected: FAIL (currently PASS)
```
