---
name: Netlist Validation
description: Validate netlists for single-writer, no-overlap, no-floating constraints
type: workflow
source: FOUNDER_VISION.md §1, CLAUDE.md
---

# Netlist Validation

**Core Rule:** Every netlist must pass three structural checks before code generation: single-writer, no-overlap, no-floating. These are enforced by `validate.py`.

## The Three Constraints

### 1. Single-Writer Law

**Requirement:** Each register is written by exactly one node.

**Why:** Determinism requires clear ownership. If two nodes try to write the same register, the result is undefined.

**Check:**
```python
# In validate.py
for register in netlist.registers:
    writers = [node for node in netlist.nodes if register in node.writes]
    assert len(writers) == 1, f"Register {register} written by {len(writers)} nodes"
```

**Failure example:**
```json
{
  "registers": [
    {"name": "PRICE_OUT", "dff": true}
  ],
  "nodes": [
    {"name": "adapter_out", "writes": ["PRICE_OUT"]},
    {"name": "candle_out",  "writes": ["PRICE_OUT"]}  // ❌ Two writers
  ]
}
```

**Fix:**
- Give each module its own output register
- Have a mux node select between them
- Or re-architect so only one module writes

### 2. No-Overlap Constraint

**Requirement:** A register cannot be both read and written in the same combinational path (no feedback loops without registers).

**Why:** Combinational feedback creates races and indeterminism in hardware. Register-to-register paths are deterministic (one clock per hop).

**Check:**
```python
# In validate.py
for node in netlist.nodes:
    for reg in node.reads:
        assert reg not in node.writes, f"Node {node} reads and writes {reg}"
```

**Failure example:**
```json
{
  "nodes": [
    {
      "name": "feedback_mux",
      "reads": ["PRICE"],     // Reads output
      "writes": ["PRICE"],    // Writes output ❌ Combinational feedback
      "logic": "mux(PRICE, ...) -> PRICE"
    }
  ]
}
```

**Fix:**
- Introduce an intermediate register (e.g., `PRICE_NEXT`)
- Write to `PRICE_NEXT` in current cycle; read from `PRICE` (previous value)
- Update `PRICE` from `PRICE_NEXT` on clock edge

### 3. No-Floating Nodes

**Requirement:** Every node in the netlist must have outputs that feed into registers (registers, outputs, or other combinational nodes that eventually feed registers).

**Why:** Orphan nodes consume logic but produce no result. They're usually mistakes (typos, incomplete specs).

**Check:**
```python
# In validate.py
reachable = set()
for reg in netlist.registers:
    reachable.update(netlist.producers_of(reg))  # Recursively add producers
for node in netlist.nodes:
    assert node in reachable, f"Node {node.name} is floating (not connected to any register)"
```

**Failure example:**
```json
{
  "registers": [
    {"name": "PRICE_OUT"}
  ],
  "nodes": [
    {"name": "price_calc", "writes": ["PRICE_OUT"]},
    {"name": "unused_mux", "writes": []}  // ❌ No outputs; not wired to anything
  ]
}
```

**Fix:**
- Wire the node to a register or another node
- Or delete it if it's unused

## How to Run validate.py

```sh
cd .hft_staging/<module>
python3 validate.py <module>.net.json
```

### Success

```
$ python3 validate.py adapter.net.json
[validate] checking adapter.net.json
[validate] single-writer check OK
[validate] no-overlap check OK
[validate] no-floating check OK
[validate] PASS
```

### Failure

```
$ python3 validate.py adapter.net.json
[validate] checking adapter.net.json
[validate] FAIL: register IN_PRICE written by 2 nodes
  1. ingress_deserialize (node 0)
  2. fallback_ingress (node 5)

[validate] Fix: assign one unique writer per register
```

## Pre-gate Validation Workflow

Run validate.py **immediately** after updating the netlist:

```sh
# 1. Generate the netlist
python3 gen_adapter_net.py > adapter.net.json

# 2. Validate it
python3 validate.py adapter.net.json

# 3. If PASS, then generate device C
python3 gennet.py adapter.net.json > adapter_gen.h

# 4. If FAIL, fix the spec and go back to step 1
```

## Common Validation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Register written by N nodes (N > 1) | Multiple modules try to write the same register | Architect single ownership; use mux if needed |
| Register written by 0 nodes | Output register has no producer | Wire a node to it; add comb_nodes or dff_nodes |
| Node reads and writes same register | Combinational feedback loop | Introduce intermediate register; use dff for state |
| Node X is floating | Orphan node with no outputs | Delete it or wire it to a register |
| Unknown register reference | Typo in register name | Check spelling; match case exactly |
| Unknown node reference | Typo in node name | Check spelling; verify node is defined |

## Netlist Structure (Expected)

A valid netlist has this structure:

```json
{
  "registers": [
    {"name": "REG_NAME", "dff": true/false, "width": 64}
  ],
  "dff_nodes": [
    {
      "name": "state_machine",
      "reads": ["IN_DATA"],
      "writes": ["STATE"],
      "logic": {"type": "dff", ...}
    }
  ],
  "comb_nodes": [
    {
      "name": "price_add",
      "reads": ["IN_A", "IN_B"],
      "writes": ["SUM"],
      "logic": {"type": "cell_addsub", ...}
    }
  ],
  "cross_module_inputs": [
    {"name": "DOM_BID", "width": 64}
  ],
  "seam_nodes": [
    {"name": "OUT_PRICE", "width": 64}
  ]
}
```

## What validate.py Doesn't Check

❌ Doesn't verify register widths match
❌ Doesn't verify cell types are valid
❌ Doesn't check timing constraints
❌ Doesn't validate against hardware limits

These are caught later by `gennet.py` or `gate.sh`.

## Running validate.py in gate.sh

When you run `gate.sh`, it calls validate.py automatically:

```sh
.hft_staging/gate.sh .hft_staging/adapter
# ==> [gate] 1/3 validate netlist
# python3 validate.py adapter.net.json
# Single-writer check OK
# No-overlap check OK
# No-floating check OK
```

If validation fails at gate stage 1, graduation is blocked.

## References

- FOUNDER_VISION.md §1 — Build Model, specification completeness
- CLAUDE.md — Architecture Enforcement Tools
- `.hft_staging/adapter/validate.py` — Reference implementation
- `.hft_staging/adapter/adapter.net.json` — Example netlist
