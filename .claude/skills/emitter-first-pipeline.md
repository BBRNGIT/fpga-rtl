---
name: Emitter-First Pipeline
description: Three-stage build process — emitter → netlist → generator, never hand-coded logic
type: workflow
source: FOUNDER_VISION.md §1
---

# Emitter-First Pipeline

**Core Rule:** Every module follows an identical three-stage build sequence. Device logic is GENERATED, never hand-written.

## The Three Stages

### Stage 1: Emitter (gen_<module>_net.py)
- **Input:** Hardware specification (registers, cells, connectivity)
- **Output:** `<module>.net.json` (the netlist)
- **Command:** `python3 gen_<module>_net.py > <module>.net.json`
- **Deliverable:** You write this hand.
- **Example:** `gen_adapter_net.py` produces `adapter.net.json`

### Stage 2: Netlist (<module>.net.json)
- **Input:** Output from Stage 1 emitter
- **Output:** JSON specification (COMMITTED to git)
- **Validate:** `python3 validate.py <module>.net.json`
- **What it is:** Register definitions, gate definitions, explicit wiring
- **Key constraint:** Must include all 5 components:
  1. Register state (dff_nodes, tables, history_ring)
  2. Input interface (cross_module_inputs)
  3. Output interface (seam_nodes)
  4. Combinational logic (comb_nodes with explicit cell definitions) — **LOAD-BEARING**
  5. Wiring (signal flow between blocks) — **LOAD-BEARING**

### Stage 3: Generator (gennet.py)
- **Input:** `<module>.net.json`
- **Output:** `<module>_gen.h` (device C code)
- **Command:** `python3 gennet.py <module>.net.json > <module>_gen.h`
- **Deliverable:** You write this hand.
- **What it produces:** Device tick function with explicit READ→COMPUTE→WRITE phases, all cell calls inlined.

## What NOT to Do

❌ Hand-write `*_tick()` functions
❌ Hand-compose `cell_*()` calls in `.c` or `.h` files
❌ Hand-edit `*_gen.h` files
❌ Skip the netlist stage (go directly from spec to code)
❌ Produce stubs (empty COMPUTE phases with no logic)

## What the Build Proves

- **Specification is complete:** All 5 netlist components are present
- **Circuit is generated:** The netlist exists, is committed, and matches the generated C byte-for-byte
- **No hand-written logic:** Device logic comes only from gennet output
- **Deterministic rebuilds:** Running the three commands on committed HEAD reproduces `*_gen.h` exactly

## Common Pitfalls

1. **Writing comb_nodes without gate-level definitions** — Netlist lacks the "LOAD-BEARING" logic; emitter produces stubs
2. **Forgetting to commit the netlist** — The `.net.json` must be committed; it's proof of specification
3. **Hand-tweaking `*_gen.h` after generation** — This breaks clean-room builds; regenerate instead
4. **Not wiring all nodes** — Validate catches "floating" nodes; use validate.py early

## How to Check This

1. Run `make gen` and observe the output
2. Run `make validate` on the netlist — should pass with no errors
3. Verify `*_gen.h` contains `READ` phase, `COMPUTE` phase with cell calls, `WRITE` phase
4. Run `gate.sh` — stage 2c checks for hand-written logic; stage 2d checks for structural cells
5. Commit the netlist and `*_gen.h` together

## Examples

**Correct flow:**
```sh
cd .hft_staging/adapter
python3 gen_adapter_net.py > adapter.net.json
python3 validate.py adapter.net.json          # Must pass
python3 gennet.py adapter.net.json > adapter_gen.h
make test
.hft_staging/gate.sh .hft_staging/adapter
.hft_staging/graduate.sh adapter
```

**Incorrect (hand-written):**
```c
// BAD — in adapter.c
static inline void adapter_tick(word_t *r) {
  r[ADAPTER_OUT] = r[ADAPTER_IN] + 100;  // ❌ Native arithmetic, hand-written
}
```

**Correct (generated):**
```c
// GOOD — in adapter_gen.h (from gennet.py)
static inline void adapter_tick(word_t *r) {
  // READ phase
  uint64_t in_val = r[ADAPTER_IN];
  
  // COMPUTE phase (generated from netlist)
  uint64_t out = 0;
  cell_addsub(in_val, 100, 0, &out);  // Structural cell from netlist
  
  // WRITE phase
  r[ADAPTER_OUT] = out;
}
```

## References

- FOUNDER_VISION.md §1 — Build Model
- CLAUDE.md — Common Commands, Build & Validate
- `.hft_staging/adapter/` — Reference implementation
