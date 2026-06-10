---
name: Read-Compute-Write Pattern
description: Device tick follows strict READ→COMPUTE→WRITE structure — atomic, deterministic
type: pattern
source: FOUNDER_VISION.md §4, CLAUDE.md
---

# Read-Compute-Write Pattern

**Core Rule:** Every device tick function follows the exact same structure:
1. **READ phase** — Sample input registers into local variables
2. **COMPUTE phase** — Gate-level logic transforms inputs to outputs
3. **WRITE phase** — Store results back to output registers

This pattern ensures determinism: all reads see the same snapshot of inputs; all writes happen atomically on the clock edge.

## Why This Structure

On real hardware, a clock edge is **atomic**:
1. All flip-flops capture their inputs simultaneously
2. Combinational logic processes in parallel
3. All flip-flops update simultaneously

The READ→COMPUTE→WRITE pattern in C mirrors this atomic behavior:
- **READ** = snapshot inputs before they change
- **COMPUTE** = all logic processes on the snapshot
- **WRITE** = all outputs update at once

## The Pattern

```c
static inline void adapter_tick(word_t *r) {
  // ===== READ PHASE =====
  // Capture all inputs at the start of the clock edge
  uint64_t in_bid = r[WIRE_BID];
  uint64_t in_ask = r[WIRE_ASK];
  uint64_t in_seq = r[WIRE_SEQ];
  
  // ===== COMPUTE PHASE =====
  // All logic operates on captured inputs
  uint64_t valid = 0;
  cell_cmp_gt(in_bid, 0, &valid);  // Is bid > 0?
  
  uint64_t mid = 0;
  cell_addsub(in_bid, in_ask, 0, &mid);
  uint64_t mid_half = 0;
  cell_sar(mid, 1, &mid_half);  // mid / 2
  
  uint64_t clean_price = 0;
  cell_mux(valid, mid_half, 0, &clean_price);  // if valid, use mid; else 0
  
  // ===== WRITE PHASE =====
  // Update output registers (write happens on clock edge)
  r[ADAPTER_VALID] = valid;
  r[ADAPTER_MID] = clean_price;
  r[ADAPTER_SEQ] = in_seq;  // Pass through
}
```

## The Three Phases Explained

### Phase 1: READ

**Goal:** Capture the current state of all input registers before computing anything.

**What happens:**
- Create local variables for each input signal
- Copy values from `r[REGISTER]` into locals
- From now on, only read from locals (never re-read `r[]`)

```c
// ✅ GOOD — read once, compute on local copy
uint64_t in_bid = r[WIRE_BID];
uint64_t in_ask = r[WIRE_ASK];

// ❌ BAD — reading from r[] inside compute
uint64_t sum = 0;
cell_addsub(r[WIRE_BID], r[WIRE_ASK], 0, &sum);  // Re-reads
```

**Why separate:** If WIRE_BID changed mid-tick (it doesn't in this model, but the pattern protects against it), you'd have undefined behavior. By reading once, you get an atomic snapshot.

### Phase 2: COMPUTE

**Goal:** Transform inputs to outputs using only gate-level logic.

**What happens:**
- All `cell_*()` calls happen here
- No register reads or writes during this phase
- All operations are on local variables
- Pure combinational logic (no state changes)

```c
// ✅ GOOD — pure gates on locals
uint64_t result = 0;
cell_addsub(in_a, in_b, 0, &result);
uint64_t shifted = 0;
cell_sar(result, 2, &shifted);

// ❌ BAD — writing to registers during compute
r[TEMP] = in_a + in_b;  // Register write in compute phase
```

**Cell calls in order:**
- Inputs flow through gates
- Each gate is one hardware block
- Outputs feed into next gates (like a circuit)

### Phase 3: WRITE

**Goal:** Store all computed results back to output registers atomically.

**What happens:**
- Only `r[OUTPUT] = local_variable` assignments
- One write per output register
- All writes happen together (on clock edge)
- No logic, no computation

```c
// ✅ GOOD — clean writes at the end
r[ADAPTER_VALID] = valid;
r[ADAPTER_MID] = clean_price;
r[ADAPTER_OUT] = output_signal;

// ❌ BAD — logic mixed into write phase
r[RESULT] = in_a + in_b;  // Computation in write phase
```

## Generated Code Example

When gennet.py generates from a netlist, it automatically produces this structure:

```c
static inline void adapter_tick(word_t *r) {
  // ===== READ PHASE =====
  // (gennet inserts: uint64_t <input> = r[<INPUT_REGISTER>];)
  uint64_t wire_bid = r[WIRE_BID];
  uint64_t wire_ask = r[WIRE_ASK];
  uint64_t wire_seq = r[WIRE_SEQ];
  
  // ===== COMPUTE PHASE =====
  // (gennet inserts: uint64_t <node_output> = 0; cell_*(..., &<node_output>);)
  uint64_t valid_check = 0;
  cell_cmp_gt(wire_bid, 0, &valid_check);
  
  uint64_t mid_calc = 0;
  cell_addsub(wire_bid, wire_ask, 0, &mid_calc);
  
  uint64_t mux_result = 0;
  cell_mux(valid_check, mid_calc, 0, &mux_result);
  
  // ===== WRITE PHASE =====
  // (gennet inserts: r[<OUTPUT_REGISTER>] = <node_output>;)
  r[ADAPTER_VALID] = valid_check;
  r[ADAPTER_CLEAN_PRICE] = mux_result;
  r[ADAPTER_SEQ] = wire_seq;
}
```

## How gennet.py Creates This Structure

```python
# In gennet.py

def generate_tick(spec):
    print("static inline void tick(word_t *r) {")
    
    # === READ PHASE ===
    print("  // ===== READ PHASE =====")
    for inp in spec['cross_module_inputs']:
        print(f"  uint64_t {inp['name'].lower()} = r[{inp['name']}];")
    
    # === COMPUTE PHASE ===
    print("  // ===== COMPUTE PHASE =====")
    for node in spec['comb_nodes']:
        print(f"  uint64_t {node['name']} = 0;")
        print(f"  cell_{node['logic']['type']}({...}, &{node['name']});")
    
    # === WRITE PHASE ===
    print("  // ===== WRITE PHASE =====")
    for reg in spec['registers']:
        writer = find_writer(spec, reg['name'])
        print(f"  r[{reg['name']}] = {writer};")
    
    print("}")
```

## Pattern Validation in gate.sh

The gate verifies the pattern exists by checking:

1. **Tick function exists**
   ```sh
   grep -E "void [a-z_]+_tick" adapter_gen.h
   ```

2. **Phases are distinct** (implicit in structure)
   - READ: assignments from `r[X] = r[INPUT]`
   - COMPUTE: `cell_*()` calls
   - WRITE: assignments to `r[OUTPUT] = local`

3. **No logic outside the tick**
   - Helper functions (cmp, cell primitives) are infrastructure
   - Main loop just calls tick repeatedly

## Verifying the Pattern Manually

Check that `*_gen.h` follows the pattern:

```sh
# Extract the tick function
sed -n '/^.*_tick(word_t \*r)/,/^}/p' adapter_gen.h

# Should show:
# 1. Local variable declarations (READ)
# 2. cell_*() calls (COMPUTE)
# 3. r[...] = ... assignments (WRITE)
```

## Common Pattern Violations

| Violation | Example | Fix |
|-----------|---------|-----|
| Compute before read | `cell_add(r[A], r[B])` — reads during compute | Move read to READ phase; use local |
| Write during compute | `r[OUT] = cell_add(...)` result write | Do `cell_add(..., &temp)` in COMPUTE; write in WRITE |
| Logic in write | `r[OUT] = in_a + in_b;` | Do addition in COMPUTE; `r[OUT] = sum;` in WRITE |
| Re-reading in compute | `sum1 = r[X]; sum2 = r[X];` | Read once: `uint64_t in_x = r[X];` use in_x twice |
| Conditional in tick | `if (cond) { r[OUT] = ... }` | Use cell_mux to select output |

## Why This Matters

1. **Determinism:** All reads happen at the same time; you never see partially-updated state
2. **Hardware accuracy:** Mirrors real clock-domain behavior
3. **Testability:** Clear flow from input → logic → output
4. **Debugging:** You can trace data through each phase

## Pre-graduation Checklist

Before running `gate.sh`:

- [ ] Every generated tick has READ, COMPUTE, WRITE phases
- [ ] No logic or conditionals in READ or WRITE phases
- [ ] All reads from `r[]` happen in READ phase
- [ ] All writes to `r[]` happen in WRITE phase
- [ ] COMPUTE phase uses only cell_*() calls and local variables

## References

- FOUNDER_VISION.md §4 — Modules = Tiny Self-Contained Programs
- CLAUDE.md — Development Workflow, Read→Compute→Write
- `.hft_staging/adapter/adapter_gen.h` — Example generated tick
- `.hft_staging/adapter/gennet.py` — Generator that creates this pattern
