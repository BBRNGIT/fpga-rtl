---
name: Specification Completeness
description: A complete spec requires all 5 components before code generation — no stubs
type: validation
source: FOUNDER_VISION.md §1
---

# Specification Completeness

**Core Rule:** A specification is complete **ONLY** if it includes all five components. Without all five, the emitter produces stubs (register declarations with no logic), and the device fails silently at test/runtime.

## The Five Required Components

### 1. Register State

**What it is:** The flip-flop registers that hold state across clock edges.

**Examples:**
- State machine counters (`STATE_COUNTER`)
- Historical data (`PRICE_HISTORY_RING`)
- Event flags (`IS_READY`, `WAS_TRIGGERED`)
- Latched inputs (`LATCHED_BID`, `LATCHED_ASK`)

**In the netlist:**
```json
{
  "registers": [
    {"name": "STATE_COUNTER", "dff": true, "width": 8},
    {"name": "PRICE_HISTORY", "dff": true, "width": 64},
    {"name": "IS_READY", "dff": true, "width": 1}
  ]
}
```

**Completeness check:** Every piece of state that must persist across clock edges is explicitly listed.

### 2. Input Interface

**What it is:** Registers or cross-module inputs that the module reads (does NOT own).

**Examples:**
- Data from upstream modules (`WIRE_BID`, `WIRE_ASK`)
- Control signals (`TIMEFRAME_TICK`)
- External ingress (`NIC_DATA`)

**In the netlist:**
```json
{
  "cross_module_inputs": [
    {"name": "DOM_BID", "width": 64},
    {"name": "DOM_ASK", "width": 64},
    {"name": "TIMEFRAME_TICK", "width": 1}
  ]
}
```

**Completeness check:** Every input the module needs is declared.

### 3. Output Interface (Seam Nodes)

**What it is:** Registers that this module writes, which other modules will read.

**Examples:**
- Processed data (`ADAPTER_PRICE_CLEAN`)
- Status signals (`ADAPTER_READY`)
- Historical output (`CANDLE_CLOSE_PRICE`)

**In the netlist:**
```json
{
  "seam_nodes": [
    {"name": "ADAPTER_PRICE_CLEAN", "width": 64},
    {"name": "ADAPTER_READY", "width": 1}
  ]
}
```

**Completeness check:** Every output the module produces is declared.

### 4. Combinational Logic (comb_nodes) — **LOAD-BEARING**

**What it is:** The actual gate-level logic that transforms inputs to outputs. This is where the work happens.

**Examples:**
- Arithmetic operations (`cell_addsub`, `cell_mul`)
- Comparisons (`cell_cmp_lt`, `cell_eqmask`)
- Multiplexing (`cell_mux`)
- Bit operations (`cell_and`, `cell_or`, `cell_xor`)

**In the netlist:**
```json
{
  "comb_nodes": [
    {
      "name": "price_validator",
      "reads": ["DOM_BID", "DOM_ASK"],
      "writes": ["PRICE_VALID"],
      "logic": {"type": "cell_cmp_gt", "a": "DOM_BID", "b": 0}
    },
    {
      "name": "clean_price",
      "reads": ["DOM_BID"],
      "writes": ["ADAPTER_PRICE_CLEAN"],
      "logic": {"type": "cell_buf", "input": "DOM_BID"}
    }
  ]
}
```

**Completeness check:** Every transformation from input → output has an explicit cell definition. No omissions.

### 5. Wiring (Signal Flow) — **LOAD-BEARING**

**What it is:** How nodes connect to registers. Every comb_node output must feed somewhere; every register must be written by a node.

**In the netlist:**
```json
{
  "nodes": [
    {
      "name": "price_validator",
      "reads": ["DOM_BID"],
      "writes": ["PRICE_VALID"]  // Wired to PRICE_VALID register
    },
    {
      "name": "clean_price",
      "reads": ["DOM_BID"],
      "writes": ["ADAPTER_PRICE_CLEAN"]  // Wired to output
    }
  ]
}
```

**Completeness check:** All reads/writes point to actual registers or cross-module inputs.

## What Happens Without All Five

**Incomplete spec (missing comb_nodes):**
```json
{
  "registers": [{"name": "OUT", "dff": true}],
  "cross_module_inputs": [{"name": "IN"}],
  "seam_nodes": [{"name": "OUT"}],
  "comb_nodes": [],  // ❌ EMPTY — NO LOGIC
  "nodes": []        // ❌ NO WIRING
}
```

**Result:**
- gennet.py produces `*_gen.h` with no logic (stub)
- Device compiles and runs but does nothing
- gate.sh stage 2d catches this: `[FAIL] no structural cell calls found`
- Test shows register unchanged (device is silent failure)

## Completeness Audit Checklist

Before writing the emitter (`gen_<module>_net.py`):

### Component 1: Register State
- [ ] Every flip-flop that persists state is listed
- [ ] State machines have state registers
- [ ] Historical data (rings, tables) are defined
- [ ] All widths are specified (e.g., `width: 64`)

### Component 2: Input Interface
- [ ] Every upstream module's output is declared as cross_module_input
- [ ] Control signals (timeframe ticks, external events) are listed
- [ ] All read sources are named

### Component 3: Output Interface
- [ ] Every downstream consumer knows what registers to read
- [ ] Seam nodes match the module's responsibility
- [ ] Output widths match expected consumers

### Component 4: Combinational Logic (Critical)
- [ ] Every transformation from input to output has a cell defined
- [ ] No "obvious" omissions (e.g., "multiply these two values" with no cell)
- [ ] Logic is gate-level (no loops, conditionals, or abstractions)
- [ ] Every cell type (cell_addsub, cell_mux, etc.) is defined in netlist

### Component 5: Wiring (Critical)
- [ ] All comb_node outputs feed into registers
- [ ] All registers are written by exactly one node
- [ ] No floating nodes (orphans)
- [ ] validate.py passes

## Common Completeness Failures

| Missing | Symptom | Fix |
|---------|---------|-----|
| comb_nodes | Device does nothing; gate.sh fails at 2d | Add logic nodes to netlist |
| cell definitions in comb_nodes | gennet can't generate code | Define each cell's type, inputs, outputs |
| wiring edges | validate.py reports floating nodes | Wire all nodes to registers |
| input interface | Missing upstream data | Declare cross_module_inputs |
| output interface | Downstream modules can't read | Add seam_nodes |

## Example: Complete Adapter Spec

```json
{
  "registers": [
    {"name": "ADAPTER_PRICE_LIVE", "dff": true, "width": 64},
    {"name": "ADAPTER_READY", "dff": true, "width": 1}
  ],
  "cross_module_inputs": [
    {"name": "WIRE_BID", "width": 64},
    {"name": "WIRE_ASK", "width": 64},
    {"name": "EXTERNAL_SEQ", "width": 32}
  ],
  "seam_nodes": [
    {"name": "ADAPTER_PRICE_LIVE", "width": 64},
    {"name": "ADAPTER_READY", "width": 1}
  ],
  "comb_nodes": [
    {
      "name": "validate_bid",
      "reads": ["WIRE_BID"],
      "writes": ["BID_VALID"],
      "logic": {"type": "cell_cmp_gt", "a": "WIRE_BID", "b": 0}
    },
    {
      "name": "validate_ask",
      "reads": ["WIRE_ASK"],
      "writes": ["ASK_VALID"],
      "logic": {"type": "cell_cmp_gt", "a": "WIRE_ASK", "b": 0}
    },
    {
      "name": "latch_bid",
      "reads": ["WIRE_BID", "BID_VALID"],
      "writes": ["LATCHED_BID"],
      "logic": {"type": "cell_mux", "sel": "BID_VALID", "true": "WIRE_BID", "false": "LATCHED_BID_PREV"}
    }
  ],
  "nodes": [
    {"name": "validate_bid", "reads": ["WIRE_BID"], "writes": ["BID_VALID"]},
    {"name": "validate_ask", "reads": ["WIRE_ASK"], "writes": ["ASK_VALID"]},
    {"name": "latch_bid", "reads": ["WIRE_BID", "BID_VALID"], "writes": ["LATCHED_BID"]}
  ]
}
```

**All five components present → emitter can generate complete device logic.**

## How to Validate Completeness

1. **Read the component `.md`** — Design doc should explain all five
2. **Write the emitter** — gen_<module>_net.py produces the netlist
3. **Run validate.py** — Checks structure and wiring
4. **Run gennet.py** — Generates device C; will fail if logic is missing
5. **Run gate.sh stage 2d** — Checks for at least one cell call

## References

- FOUNDER_VISION.md §1 — Specification Completeness
- CLAUDE.md — Design Phase
- `.hft_staging/adapter/adapter.net.json` — Complete example
- `.hft_staging/adapter/gen_adapter_net.py` — Reference emitter
