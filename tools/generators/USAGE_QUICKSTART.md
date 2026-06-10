# spec-to-partslist.py Quick Start

## 30-Second Overview

Generate hardware specification documents from simple YAML specs.

```bash
python3 spec-to-partslist.py <module>.yaml > <MODULE>_PARTS_LIST.md
```

## Step 1: Create Your YAML Spec

Create `<module>.yaml`:

```yaml
device: mymodule
kind: indicator                    # or: accumulator, clock, gateway, memory, oscillator
comment: Brief description here

# Input lanes from other modules (optional)
cross_module_inputs:
  - name: INPUT_NAME
    source: other_module
    type: u64
    comment: What this input is

# Sequential state registers (optional)
dff_nodes:
  - name: MY_PRICE
    type: u64
    comment: Current price value

# Array registers indexed by price level (optional)
tables:
  - name: MY_TABLE
    type: u64
    depth: 16384
    index_from: PRICE_IDX
    comment: Per-level data

# Published relay outputs (optional)
seam_nodes:
  - name: MY_OUTPUT
    from: MY_PRICE
    type: u64
    comment: Public output lane
```

See `spec-schema.yaml` for complete reference.

## Step 2: Run the Generator

```bash
python3 spec-to-partslist.py mymodule.yaml > MYMODULE_PARTS_LIST.md
```

## Step 3: Review the Output

Open `MYMODULE_PARTS_LIST.md` and verify:
- All 9 sections present
- Cross-module inputs documented (section 1)
- Registers listed (section 2)
- Tables with correct depths (section 3)
- Relay outputs documented (section 4)
- Address layout looks right (section 6)
- Dataflow diagram makes sense (section 7)
- Commit expectations clear (section 9)

## Step 4: Use as Grounding for Emitter

Pass the generated `MYMODULE_PARTS_LIST.md` to the netlist-builder agent:

```
Dispatch: netlist-builder subagent
Prompt: "Build <module> component from this parts list:
         [paste content of MYMODULE_PARTS_LIST.md]"
```

This will generate:
- `gen_<module>_net.py` (emitter script)
- `<module>.net.json` (netlist)
- `<module>_gen.h` (generated device C code)

## Examples

### Simple Indicator (1 input, 1 register, 2 tables, 1 relay output)

```yaml
device: myindicator
kind: indicator
comment: Simple indicator tracking price imbalance

cross_module_inputs:
  - name: PRICE_IDX
    source: dom
    type: u64
    comment: Current price level index

dff_nodes:
  - name: IMBALANCE
    type: u64
    comment: Current imbalance value

tables:
  - name: BID_COUNT
    type: u64
    depth: 16384
    index_from: PRICE_IDX
    comment: Bid count per level
  - name: ASK_COUNT
    type: u64
    depth: 16384
    index_from: PRICE_IDX
    comment: Ask count per level

seam_nodes:
  - name: IMBALANCE_OUT
    from: IMBALANCE
    type: u64
    comment: Public imbalance output
```

### Multi-Input Indicator (4 inputs, 3 registers, 3 tables, 3 relay outputs)

```yaml
device: complexindicator
kind: indicator
comment: Multi-dimensional market analysis

cross_module_inputs:
  - name: DOM_BID_QTY
    source: dom
    type: u64
    comment: Bid quantity per level
  - name: DOM_ASK_QTY
    source: dom
    type: u64
    comment: Ask quantity per level
  - name: DOM_COUNT
    source: dom
    type: u64
    comment: Event count per level
  - name: DOM_TIME
    source: dom
    type: u64
    comment: Timestamp per level

dff_nodes:
  - name: MAX_VALUE
    type: u64
    comment: Maximum value
  - name: MIN_VALUE
    type: u64
    comment: Minimum value
  - name: TOTAL
    type: u64
    comment: Sum total

tables:
  - name: TABLE_A
    type: u64
    depth: 16384
    index_from: PRICE_IDX
    comment: First accumulator
  - name: TABLE_B
    type: u64
    depth: 16384
    index_from: PRICE_IDX
    comment: Second accumulator
  - name: TABLE_C
    type: u64
    depth: 16384
    index_from: PRICE_IDX
    comment: Third accumulator

seam_nodes:
  - name: MAX_OUT
    from: MAX_VALUE
    type: u64
    comment: Maximum value relay
  - name: MIN_OUT
    from: MIN_VALUE
    type: u64
    comment: Minimum value relay
  - name: TOTAL_OUT
    from: TOTAL
    type: u64
    comment: Sum total relay
```

## Validation

### Required Fields Check

All YAML specs must have:
- `device` — lowercase module name
- `kind` — module type (one of: oscillator, clock, gateway, accumulator, memory, indicator)
- `comment` — one-line description

### Optional Fields

- `dff_nodes` — sequential state (0 or more)
- `config_nodes` — constants (0 or more)
- `tables` — arrays indexed by address (0 or more)
- `cross_module_inputs` — upstream lanes (0 or more)
- `seam_nodes` — relay outputs (0 or more)
- `history_ring` — snapshot ring (optional)

### Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing required field: device` | device not in YAML | Add `device: myname` |
| `Missing required field: kind` | kind not in YAML | Add `kind: indicator` |
| `Missing required field: comment` | comment not in YAML | Add `comment: Description` |
| `FileNotFoundError: spec.yaml` | File doesn't exist | Check filename and path |
| `YAML parse error` | Invalid YAML syntax | Check indentation and syntax |

## Tips

1. **Start minimal** — just device, kind, comment; add nodes incrementally
2. **Use consistent naming** — UPPERCASE for registers (FP_POC_PRICE, not fp_poc_price)
3. **Table depth as power-of-2** — common choices: 16384 (16K price levels), 256 (small tables)
4. **Comments matter** — they appear in the parts list; be specific
5. **Check for typos** — source module names must be correct (dom, wire, etc.)
6. **Validate your spec** — run the tool and review the output before committing

## Next Steps

1. Create `.yaml` spec file
2. Run `spec-to-partslist.py`
3. Review generated `PARTS_LIST.md`
4. Use parts list as grounding for `netlist-builder` subagent
5. Commit spec + parts list to git
6. Build emitter, netlist, and device code

## Resources

- **Full reference:** `README.md` (tool documentation)
- **Schema:** `spec-schema.yaml` (complete YAML schema)
- **Examples:** `footprint.yaml`, `tpo.yaml` (test specs)
- **Generated:** `FOOTPRINT_PARTS_LIST.md`, `TPO_PARTS_LIST.md` (example outputs)
- **Integration:** `SPEC.md` (meta-generator pipeline overview)
