---
name: Module Independence
description: Modules read only published interfaces — no cross-module coupling beyond register fabric
type: architecture
source: FOUNDER_VISION.md §4 & §9, CLAUDE.md
---

# Module Independence

**Core Rule:** Modules are self-contained. Each module reads ONLY published output registers (seam_nodes) from other modules; it never reads internal state or depends on another module's implementation.

## The Principle: Register Fabric IS The Wiring

On an FPGA, once modules are placed, you don't hand-wire them. The fabric routes signals. Here, the equivalent is:

**A module reads published registers at known addresses.**
**Any module reading those addresses is automatically wired.**
**Placement = register assignment = connectivity.**

```
Module A (adapter)
  ├─ [INTERNAL_STATE] (not published)
  └─ [ADAPTER_PRICE] ← Published (seam_node)
  
Module B (candle)
  └─ reads [ADAPTER_PRICE] (published interface)

Module C (dom)
  └─ reads [ADAPTER_PRICE] (same interface, no duplication)
```

**Key:** Module B and C both read the same published register; no wiring step needed.

## What Modules Can Read

✅ **Published seam_nodes** from other modules
- These are outputs declared in the netlist
- Example: candle reads `ADAPTER_PRICE` (from adapter's seam_nodes)

✅ **Own registers** (internal state)
- Module reads its own previous-cycle state
- Example: candle reads its own `CANDLE_STATE` to accumulate bars

❌ **Internal registers** of other modules
- Never read another module's `_STATE` or `_TEMP` registers
- These are implementation details; they can change

❌ **Cross-module private data**
- No "private copies" of another module's data
- No assuming another module will update a register (timing dependency)

## Module Boundaries

```
Module A
  ├─ [A_INTERNAL_1]
  ├─ [A_INTERNAL_2]
  └─ [A_OUTPUT]          ← Published (other modules read this)

Module B
  ├─ [B_INTERNAL_1]
  ├─ [B_INTERNAL_2]
  └─ [B_OUTPUT]          ← Published

Module C (read-only consumer)
  ├─ [C_STATE] (own state)
  └─ reads [A_OUTPUT] and [B_OUTPUT] only
     (never reads A_INTERNAL_1, A_INTERNAL_2, etc.)
```

## In the Netlist

### Module A's Published Interface

```json
{
  "seam_nodes": [
    {"name": "ADAPTER_PRICE", "width": 64},
    {"name": "ADAPTER_READY", "width": 1}
  ],
  "registers": [
    {"name": "INTERNAL_BUFFER", "dff": true},
    {"name": "INTERNAL_COUNTER", "dff": true}
  ]
}
```

### Module C Reads Only Published

```json
{
  "cross_module_inputs": [
    {"name": "ADAPTER_PRICE", "width": 64},
    {"name": "ADAPTER_READY", "width": 1}
  ],
  "registers": [
    {"name": "CANDLE_STATE", "dff": true}
  ]
}
```

**Note:** Module C declares `ADAPTER_PRICE` and `ADAPTER_READY` as `cross_module_inputs`, not `INTERNAL_BUFFER` or `INTERNAL_COUNTER`.

## Enforcing Independence

### Pre-graduation Audit

Before `gate.sh`, verify module boundaries:

1. **List published interfaces**
   ```sh
   jq '.seam_nodes[].name' .hft_staging/<module>/<module>.net.json
   ```

2. **List cross-module inputs**
   ```sh
   jq '.cross_module_inputs[].name' .hft_staging/<module>/<module>.net.json
   ```

3. **Verify inputs match published outputs**
   - Check that each cross_module_input is a seam_node from another module
   - If reading `ADAPTER_BUFFER` (internal), that's a violation

### What to Check

```json
{
  "registers": [
    {"name": "MY_OUTPUT"}  // ✅ Own register, can read
  ],
  "cross_module_inputs": [
    {"name": "OTHER_OUTPUT"}  // ✅ Published from other module
  ]
}
```

❌ **Bad:**
```json
{
  "cross_module_inputs": [
    {"name": "ADAPTER_INTERNAL_STATE"}  // ❌ Internal register (not published)
  ]
}
```

## Register Naming Convention

Use names that signal ownership:

```
ADAPTER_PRICE           ← Owned by adapter module
ADAPTER_READY
ADAPTER_SEQ

CANDLE_CLOSE           ← Owned by candle module
CANDLE_HIGH
CANDLE_LOW

DOM_BID                ← Owned by DOM module
DOM_ASK
```

**Others can read these; only the owning module writes them.**

## Tight Coupling (Anti-pattern)

❌ **WRONG:**
```c
// In candle's tick:
// Candle assumes adapter will update ADAPTER_PRICE by a specific amount
// If adapter changes its logic, candle breaks

uint64_t delta = r[ADAPTER_PRICE] - previous_price;  // ❌ Tight coupling

// Or worse:
// Candle reads adapter's internal counter
uint64_t adapter_tick_count = r[ADAPTER_INTERNAL_TICK];  // ❌ Reading private state
```

✅ **RIGHT:**
```c
// In candle's tick:
// Candle reads published ADAPTER_PRICE and uses it as-is
// Doesn't care how adapter calculated it

uint64_t current_price = r[ADAPTER_PRICE];
// Use current_price in candle logic; adapter can change internally
```

## Order Independence

Because modules read only the previous-cycle snapshot via registers, **execution order doesn't matter**:

```c
// All three orders produce identical results:
// 1. dom_tick(); candle_tick(); footprint_tick();
// 2. candle_tick(); dom_tick(); footprint_tick();
// 3. footprint_tick(); candle_tick(); dom_tick();

// Why? Each reads the same register values (from previous cycle)
// and writes to different registers.
```

## Dependency Graph

Document module dependencies as a simple list:

```
adapter         (no dependencies)
  ↓
wire            (reads adapter output)
  ↓
nic             (reads wire)
  ↓
fifo_rx         (reads nic)
  ↓
dom             (reads fifo_rx prices)
  ↓
candle          (reads dom prices)
footprint       (reads dom prices)
cbr             (reads dom prices)
timeframe       (no dependencies; free-running)
```

**Each module depends only on published outputs of upstream modules.**

## Pre-graduation Checklist

Before `gate.sh`:

- [ ] Every cross_module_input matches a seam_node from another module
- [ ] No cross_module_inputs point to internal registers (names without module prefix)
- [ ] Module uses published inputs, not assumed internal state
- [ ] Single-writer law holds (other modules can't write your registers)
- [ ] No timing dependencies (e.g., "adapter must run first")

## Common Independence Violations

| Violation | Fix |
|-----------|-----|
| Reading ADAPTER_BUFFER (internal) | Request ADAPTER_PRICE as published output instead |
| Assuming adapter runs before candle | Make candle read published outputs; order-independent |
| Directly wiring modules in glue code | Use register fabric; read/write through r[] addresses |
| Tight coupling to internal counters | Use published ready/valid signals instead |

## References

- FOUNDER_VISION.md §4 — Modules = Tiny Self-Contained Programs
- FOUNDER_VISION.md §9 — Module Barrier
- CLAUDE.md — Single-Writer Law
