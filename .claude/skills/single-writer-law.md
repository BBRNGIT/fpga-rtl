---
name: Single-Writer Law
description: Each register is written by exactly one node — no concurrent writes
type: enforcement
source: FOUNDER_VISION.md §3 & §9, CLAUDE.md
---

# Single-Writer Law

**Core Rule:** Each register is owned by exactly one module. Only that module can write it. Other modules may read it, but all writes come from one source.

## Why This Matters

In a distributed system of independent modules clocked on their own edge, concurrent writes to the same register create **undefined behavior**: which module wins? The result depends on timing, which is non-deterministic.

The single-writer law guarantees:
- **Determinism:** Register ownership is clear
- **No races:** No two modules fight over a register
- **Clear data flow:** Register = pipeline stage output = exactly one producer

## The Rule in Practice

### ❌ NOT Allowed

```json
{
  "registers": [
    {"name": "DOM_MID_PRICE", "dff": true}
  ],
  "nodes": [
    {"name": "adapter_mid", "writes": ["DOM_MID_PRICE"]},
    {"name": "calculator_mid", "writes": ["DOM_MID_PRICE"]}  // ❌ Two writers
  ]
}
```

**Problem:** Which module's value is in DOM_MID_PRICE after a clock edge? Undefined.

### ✅ ALLOWED

```json
{
  "registers": [
    {"name": "ADAPTER_MID", "dff": true},
    {"name": "CALC_MID", "dff": true}
  ],
  "nodes": [
    {"name": "adapter_mid", "writes": ["ADAPTER_MID"]},       // Single writer
    {"name": "calculator_mid", "writes": ["CALC_MID"]}        // Different register
  ]
}
```

**Solution:** Each module writes its own register. Consumers read from both if they need both.

## Data Flow Pattern

```
Module A  →  [REGISTER_A] ──┐
                             ├─→ Mux Node ─→ [RESULT]
Module B  →  [REGISTER_B] ──┘

Rule: REGISTER_A written ONLY by Module A
      REGISTER_B written ONLY by Module B
      RESULT written ONLY by Mux Node
```

**Every register has one source; reads can be many.**

## validate.py Enforces This

The netlist validator checks:

```python
for register in netlist.registers:
    writers = [node for node in netlist.nodes if register in node.writes]
    if len(writers) != 1:
        FAIL(f"Register {register} written by {len(writers)} nodes: {[n.name for n in writers]}")
```

**Failure output:**
```
[validate] FAIL: register DOM_BID written by 2 nodes
  1. ingress_deserialize
  2. fallback_data_source
```

## Common Single-Writer Violations

| Scenario | Problem | Fix |
|----------|---------|-----|
| Two sources for same data | Conflict | Give each a separate register |
| Fallback/backup data | "Use X if A unavailable, else B" | Create [DATA], [FALLBACK]; use mux to select |
| State machine with multiple inputs | "Set STATE on condition A or B" | Create [STATE_NEXT]; mux conditions into it; one write |
| Multiple indicators from same source | Each indicator calculates mid-price | Each has own [MID_PRICE_X]; wire same input to all |

## Correct Architecture for Multi-Source Data

**Scenario:** DOM needs bid/ask data from two sources.

**WRONG (concurrent writes):**
```json
{
  "registers": [{"name": "BID", "dff": true}],
  "nodes": [
    {"name": "source_a", "writes": ["BID"]},
    {"name": "source_b", "writes": ["BID"]}  // ❌ Conflict
  ]
}
```

**RIGHT (separate registers + selection):**
```json
{
  "registers": [
    {"name": "BID_FROM_A", "dff": true},
    {"name": "BID_FROM_B", "dff": true},
    {"name": "BID_SELECTED", "dff": true}
  ],
  "comb_nodes": [
    {
      "name": "bid_selector",
      "reads": ["BID_FROM_A", "BID_FROM_B", "SOURCE_SELECT"],
      "writes": ["BID_SELECTED"],
      "logic": {"type": "cell_mux", "sel": "SOURCE_SELECT", 
                "true": "BID_FROM_A", "false": "BID_FROM_B"}
    }
  ]
}
```

**Result:**
- Source A writes [BID_FROM_A] alone
- Source B writes [BID_FROM_B] alone
- Selector mux chooses between them
- No conflicts; deterministic

## State Machine Example

**Scenario:** State machine responds to multiple external events.

**WRONG (multiple writers to STATE):**
```c
// BAD — two transitions to STATE
void tick() {
  if (external_event_a) state_node_a_writes(STATE);  // ❌
  if (external_event_b) state_node_b_writes(STATE);  // ❌
}
```

**RIGHT (one state node, multiple conditions):**
```json
{
  "registers": [
    {"name": "STATE", "dff": true, "width": 8},
    {"name": "NEXT_STATE", "dff": true, "width": 8}
  ],
  "comb_nodes": [
    {
      "name": "state_transition",
      "reads": ["STATE", "EVENT_A", "EVENT_B"],
      "writes": ["NEXT_STATE"],
      "logic": {
        "type": "cell_mux",
        "sel": {"type": "cell_or", "a": "EVENT_A", "b": "EVENT_B"},
        "true": "STATE_NEXT_VALUE",
        "false": "STATE"
      }
    }
  ]
}
```

**Result:** One node (state_transition) writes NEXT_STATE.

## Cross-Module Boundaries

**Rule:** A module reads only published output registers (seam_nodes); it does NOT read internal state of other modules.

```
Module A
  ├─ [INTERNAL_STATE] ──┐ (not published)
  └─ [OUTPUT] ──────────┤ (published seam_node)
                         │
                    Module B reads [OUTPUT] only
                    (not [INTERNAL_STATE])
```

**Why:** INTERNAL_STATE may change; OUTPUT is the contract.

## Pre-graduation Checklist

Before running `gate.sh`:

- [ ] Run `validate.py` — checks single-writer automatically
  ```sh
  python3 validate.py <module>.net.json
  ```

- [ ] Every register in netlist has exactly one `writes` source
  ```sh
  jq '.nodes[].writes[]' <module>.net.json | sort | uniq -d
  # Should return nothing (no duplicates)
  ```

- [ ] No cross-module ownership conflicts
  - Adapter owns [ADAPTER_PRICE]
  - Wire owns [WIRE_BID], [WIRE_ASK]
  - Each module owns only its outputs

## Debugging Single-Writer Violations

If validate.py reports a conflict:

```
[validate] FAIL: register OUT_PRICE written by 2 nodes
  1. price_calc
  2. price_backup
```

**Steps:**

1. **Open the netlist**
   ```sh
   grep -A2 '"writes":' adapter.net.json | grep "OUT_PRICE"
   ```

2. **Identify the nodes**
   - Find price_calc node; check its writes
   - Find price_backup node; check its writes

3. **Fix (choose one):**
   - Option A: Delete one writer (if redundant)
   - Option B: Rename one register (price_calc → OUT_PRICE_A, price_backup → OUT_PRICE_B)
   - Option C: Add a mux node to select between them; have it be the sole writer

4. **Regenerate and validate**
   ```sh
   python3 gennet.py adapter.net.json > adapter_gen.h
   python3 validate.py adapter.net.json
   ```

## References

- FOUNDER_VISION.md §3 — Single-Writer Law
- FOUNDER_VISION.md §9 — Module Barrier
- CLAUDE.md — Single-Writer Law
- `.hft_staging/adapter/validate.py` — Validation implementation
