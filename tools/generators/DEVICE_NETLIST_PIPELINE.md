# Device Netlist Pipeline

**Complete workflow** for generating and validating FPGA device netlists.

## Three-Stage Pipeline

```
Stage 0: Device Extraction (external)
  Xilinx Datasheet (PG252, DS922)
     ↓
  [parse_xilinx_spec.py or manual extraction]
     ↓
  canonical_device_model.json (device parts + connections)

Stage 1: Netlist Emission (THIS TOOL)
  canonical_device_model.json
     ↓
  [gen_device_netlist.py]
     ↓
  device.net.json (partitioned, single-writer)

Stage 2: Code Generation
  device.net.json
     ↓
  [gennet_device.py]
     ↓
  device_gen.h (C code model)
```

## Stage 1: Netlist Emission

### Tool
**`gen_device_netlist.py`** — Emit `device.net.json` from `canonical_device_model.json`

### Purpose
Transform an unstructured device model into a partitioned netlist that enforces architectural constraints:
1. **Single-writer law** — each DFF node has exactly one incoming edge
2. **No-overlap** — no register conflicts
3. **No-floating** — all nodes are wired
4. **No dead ends** — all logic has sinks

### Input
`canonical_device_model.json` — flat list of device components

```json
{
  "device": "xcvu9p-flga2104-2L",
  "inventory": { "clbs": {...}, "bram36": {...}, ... },
  "dff_nodes": [
    {"name": "CLB_DFFE", "type": "CLB_FF", "count": 2918400, "source": "ROUTING"},
    ...
  ],
  "comb_nodes": [
    {"name": "LUT6", "type": "LUT6", "inputs": 6, "count": 1457600},
    ...
  ],
  "connections": [
    {"from": "LUT6", "to": "CLB_DFFE"},
    ...
  ]
}
```

### Output
`device.net.json` — partitioned netlist

```json
{
  "device": "xcvu9p-flga2104-2L",
  "dff_nodes": [
    {"name": "CLB_DFFE_FROM_ROUTING", "source": "ROUTING", "count": 2918400, ...},
    {"name": "CLB_DFFE_FROM_LUT", "source": "LUT", "count": 0, ...},
    {"name": "BRAM_READ", "type": "BRAM_READ_OUTPUT", "count": 77760, ...},
    ...
  ],
  "comb_nodes": [
    {"name": "LUT6", "type": "LUT6", "inputs": 6, "count": 1457600, ...},
    {"name": "CARRY_CHAIN", "type": "CARRY_FA", "inputs": 3, "count": 182400, ...},
    ...
  ],
  "connections": [
    {"from": "LUT6", "to": "CLB_DFFE_FROM_ROUTING", "count": 1457600, ...},
    {"from": "CARRY_CHAIN", "to": "CLB_DFFE_FROM_CARRY", "count": 182400, ...},
    ...
  ],
  "statistics": { ... }
}
```

### Key Transformations

#### 1. DFF Partitioning
Un-partitioned multi-source components are split by input source:

| Input | Output (Partitions) | Single-Writer Guarantee |
|-------|---------------------|------------------------|
| CLB_DFFE (2.9M) | CLB_DFFE_FROM_LUT | Each driven by LUTs only |
| | CLB_DFFE_FROM_CARRY | Each driven by carry chains only |
| | CLB_DFFE_FROM_ROUTING | Each driven by routing only |
| BRAM_READ (77K) | BRAM_READ | Driven by BRAM read logic only |
| BRAM_WRITE (status) | BRAM_WRITE | Driven by BRAM write logic only |
| DSP_OUTPUT (328K) | DSP_ACCUMULATOR | Driven by accumulator logic |
| | DSP_MULTIPLIER | Driven by multiply logic |

#### 2. Connection Remapping
Original connections using un-partitioned names are remapped to partitioned equivalents:

```
Original:   LUT6 → CLB_DFFE
Remapped:   LUT6 → CLB_DFFE_FROM_LUT
```

#### 3. Implicit Connection Deduction
Architectural knowledge is applied to deduce additional connections:
- LUT outputs → CLB_DFFE_FROM_LUT (wiring pattern)
- CARRY_CHAIN outputs → CLB_DFFE_FROM_CARRY (wiring pattern)
- ROUTING_SWITCH → LUT inputs (programmable interconnect)
- DSP_MULTIPLY → DSP_ACCUMULATOR (pipeline stage)

### Usage

```bash
# Generate device netlist
python3 gen_device_netlist.py canonical_device_model.json device.net.json

# With example
python3 gen_device_netlist.py example_canonical_device_model.json /tmp/device.net.json
```

### Next: Validation

After emission, validate the netlist:

```bash
# (When validate_device.py exists)
python3 validate_device.py device.net.json

# Expected output:
#   ✓ Single-writer law: each DFF has ≤1 source
#   ✓ No-overlap: no register conflicts
#   ✓ No-floating: all nodes are wired
#   ✓ Valid netlist
```

Validation checks:
1. Each DFF node is driven by ≤1 source
2. No register is written by multiple sources
3. No isolated nodes (every node has input or is I/O)
4. All connection references are valid

## Complete Workflow Example

```bash
# Step 1: Extract device model from Xilinx spec (external)
# Produces: canonical_device_model.json

# Step 2: Emit netlist (THIS TOOL)
cd tools/generators
python3 gen_device_netlist.py ../../../canonical_device_model.json \
                               ../../../device.net.json

# Step 3: Validate netlist (future)
python3 validate_device.py ../../../device.net.json
# Expected: PASS (all constraints satisfied)

# Step 4: Generate device C code (future)
python3 gennet_device.py ../../../device.net.json > ../../../device_gen.h

# Step 5: Integrate into build
# The device_gen.h is included in the device model code;
# it defines the actual device architecture (registers, wiring, primitives).
```

## Architecture Constraints

### Single-Writer Law
Every flip-flop is the **output of exactly one combinational source**. This ensures:
- Deterministic behavior (no multiple drivers → contention)
- Unambiguous wiring (one source per register)
- Modular analysis (can trace each FF independently)

**Violation Example (BAD):**
```json
{
  "name": "CLB_DFFE_ALL",
  "count": 2918400,
  "connections": [
    {"from": "LUT", "to": "CLB_DFFE_ALL"},
    {"from": "CARRY", "to": "CLB_DFFE_ALL"},
    {"from": "ROUTING", "to": "CLB_DFFE_ALL"}
  ]
}
// Problem: one node, three writers → undefined behavior
```

**Correct Example (GOOD):**
```json
{
  "name": "CLB_DFFE_FROM_LUT",
  "count": N,
  "connections": [{"from": "LUT", "to": "CLB_DFFE_FROM_LUT"}]
},
{
  "name": "CLB_DFFE_FROM_CARRY",
  "count": M,
  "connections": [{"from": "CARRY", "to": "CLB_DFFE_FROM_CARRY"}]
},
{
  "name": "CLB_DFFE_FROM_ROUTING",
  "count": P,
  "connections": [{"from": "ROUTING", "to": "CLB_DFFE_FROM_ROUTING"}]
}
// Each partition has exactly one writer
```

### Synthesis from Inventory
If explicit `dff_nodes` or `comb_nodes` are missing, the tool synthesizes them from the `inventory`:

```python
# From Xilinx VU9P architecture
inventory = {
  "clbs": {"count": 182400},
  "bram36": {"count": 2160},
  "dsp48e2": {"count": 6840},
  "gty": {"count": 32}
}

# Synthesized DFF nodes
CLB flip-flops:    182,400 CLBs × 16 FFs = 2,918,400
BRAM outputs:      2,160 BRAMs × 36 bits = 77,760
DSP accumulators:  6,840 DSPs × 48 bits = 328,320
GTY RX data:       32 lanes × 64 bits = 2,048

Total: 3,326,528 registers
```

This ensures that even if the canonical model is incomplete, a valid device netlist is generated.

## File Structure

```
tools/generators/
  ├─ gen_device_netlist.py           ✅ IMPLEMENTED (706 lines, 15 methods)
  │  └─ Main tool: canonical → device.net.json
  │
  ├─ GEN_DEVICE_NETLIST.md           ✅ Complete documentation
  │  └─ Full reference for this tool
  │
  ├─ DEVICE_NETLIST_PIPELINE.md      ✅ This file
  │  └─ End-to-end workflow guide
  │
  ├─ example_canonical_device_model.json  ✅ Test example (VU9P)
  │  └─ Full device model for testing
  │
  ├─ validate_device.py              ⏳ Planned (Stage 2 validation)
  │  └─ Netlist validator (single-writer, no-overlap, no-floating)
  │
  ├─ gennet_device.py                ✅ Exists (Stage 3 code generation)
  │  └─ Netlist → device_gen.h
  │
  └─ README.md                        ✅ Meta-generator overview
     └─ All three stages documented
```

## Testing

Included test:

```bash
cd tools/generators
python3 << 'EOF'
from gen_device_netlist import DeviceNetlistEmitter
import json

with open('example_canonical_device_model.json') as f:
    model = json.load(f)

emitter = DeviceNetlistEmitter(model)
netlist = emitter.emit()

# Verify key properties
assert netlist['device'] == 'xcvu9p-flga2104-2L'
assert len(netlist['dff_nodes']) > 0
assert len(netlist['comb_nodes']) > 0
assert netlist['statistics']['total_dff_registers'] == 3326528

print('✓ All tests passed')
EOF
```

## References

- **XILINX_VU9P_SPEC_EXTRACTION.md** — Device architecture details
- **GEN_DEVICE_NETLIST.md** — Complete tool documentation
- **README.md** — Meta-generator overview
- **Xilinx PG252** — Virtex UltraScale+ Product Guide
- **Xilinx DS922** — Virtex UltraScale+ Datasheet
