# gen_device_netlist.py — Device Netlist Emitter

**Purpose:** Emit `device.net.json` from `canonical_device_model.json`, enforcing architectural constraints.

This is the second stage of the device netlist pipeline, following the initial device model extraction from Xilinx datasheets.

## Input: canonical_device_model.json

A merged model of the target FPGA device containing:
- **device name** — e.g., "xcvu9p-flga2104-2L"
- **inventory** — resource counts (CLBs, BRAM, DSP, GTY, etc.)
- **dff_nodes** — all registered components (CLB flip-flops, BRAM outputs, DSP accumulators, etc.)
- **comb_nodes** — all combinational logic (LUTs, carry chains, multiplexers, routing, etc.)
- **connections** — explicit wiring (from canonical model extraction or merge)

Example:
```json
{
  "device": "xcvu9p-flga2104-2L",
  "inventory": {
    "clbs": {"count": 182400},
    "bram36": {"count": 2160},
    "dsp48e2": {"count": 6840},
    "gty": {"count": 32}
  },
  "dff_nodes": [
    {"name": "CLB_DFFE", "type": "CLB_FF", "count": 2918400, "source": "ROUTING"},
    {"name": "BRAM_READ", "type": "BRAM_READ_OUTPUT", "count": 77760}
  ],
  "comb_nodes": [
    {"name": "LUT6", "type": "LUT6", "inputs": 6, "outputs": 1, "count": 1457600},
    {"name": "CARRY_CHAIN", "type": "CARRY_FA", "inputs": 3, "outputs": 2, "count": 182400}
  ],
  "connections": [
    {"from": "LUT6", "to": "CLB_DFFE"},
    {"from": "CARRY_CHAIN", "to": "CLB_DFFE"}
  ]
}
```

## Output: device.net.json

A partitioned netlist enforcing the **single-writer law**: every DFF node has exactly one incoming source.

Key features:
- **Partitioned DFF nodes** — CLBs are split by source (LUT, carry, routing); BRAM read/write are separate; DSP accumulator is isolated
- **Partitioned comb nodes** — LUTs, carry chains, muxes, routing all organized by function
- **Valid wiring graph** — every combinational node has at least one sink; every DFF has exactly one source
- **Architecture metadata** — statistics (total registers, comb elements, connections)

Example output:
```json
{
  "device": "xcvu9p-flga2104-2L",
  "comment": "Device netlist: partitioned structural components with single-writer law enforced...",
  "dff_nodes": [
    {
      "name": "CLB_DFFE_FROM_ROUTING",
      "source": "ROUTING",
      "type": "CLB_FF",
      "count": 2918400,
      "comment": "CLB flip-flops driven by ROUTING outputs"
    },
    {
      "name": "BRAM_READ",
      "type": "BRAM_READ_OUTPUT",
      "count": 77760,
      "comment": "BRAM read port registered outputs"
    },
    ...
  ],
  "comb_nodes": [
    {
      "name": "LUT6",
      "type": "LUT6",
      "inputs": 6,
      "outputs": 1,
      "count": 1457600,
      "comment": "6-input lookup tables"
    },
    ...
  ],
  "connections": [
    {
      "from": "LUT6",
      "to": "CLB_DFFE_FROM_ROUTING",
      "type": "data",
      "count": 1457600,
      "comment": "LUT outputs drive CLB flip-flops"
    },
    ...
  ],
  "statistics": {
    "total_dff_nodes": 4,
    "total_dff_registers": 3326528,
    "total_comb_nodes": 7,
    "total_comb_elements": 2745930,
    "total_connections": 7,
    "total_wires": 1006
  }
}
```

## Usage

```bash
python3 gen_device_netlist.py <input.json> [output.json]
```

### Arguments
- **input.json** — canonical device model file (default: `canonical_device_model.json`)
- **output.json** — output netlist file (default: `device.net.json`)

### Examples

```bash
# Generate device netlist with defaults
python3 gen_device_netlist.py canonical_device_model.json

# Specify both input and output
python3 gen_device_netlist.py canonical_device_model.json my_device.net.json

# Generate from example
python3 gen_device_netlist.py example_canonical_device_model.json /tmp/device.net.json
```

## Partitioning Rules

The tool partitions components by **single-writer law**: each DFF has exactly one source.

### CLB Flip-Flops
Original: `CLB_DFFE` (2,918,400 total)

Partitioned by source:
- `CLB_DFFE_FROM_LUT` — driven by LUT outputs
- `CLB_DFFE_FROM_CARRY` — driven by carry chain outputs
- `CLB_DFFE_FROM_ROUTING` — driven by programmable interconnect
- `CLB_DFFE_FROM_MUXF7` — driven by MUXF7 outputs (if present)
- `CLB_DFFE_FROM_MUXF8` — driven by MUXF8 outputs (if present)

This ensures: **each partition has one input edge (single-writer)**, and can be analyzed in isolation.

### BRAM
- `BRAM_READ` — read port outputs (driven by read logic)
- `BRAM_WRITE` — write port status (driven by write logic)

Read and write are separate writers, so each gets its own partition.

### DSP48E2
- `DSP_MULTIPLIER` — multiply output (when accumulator not in use)
- `DSP_ACCUMULATOR` — accumulator register (fed by multiply or add)
- `DSP_ADDSUB` — add/subtract logic output

### GTY Transceivers
- `GTY_RX_DATA` — RX data outputs (driven by CDR)
- `GTY_TX_STATUS` — TX status registers (driven by TX logic)

### Combinational Nodes
- `LUT6` — 6-input lookup tables (1,457,600 total)
- `CARRY_CHAIN` — ripple-carry full-adder chains (182,400 total)
- `MUXF7` / `MUXF8` — wide multiplexers (CLB inter-slice and pair)
- `ROUTING_SWITCH` — programmable interconnect (routing matrices)
- `DSP_MULTIPLY` — DSP multiply logic
- `DSP_ADDSUB` — DSP add/subtract logic

## Validation Enforced

1. **Single-Writer Law** — Each DFF partition has exactly one incoming connection
2. **No Overlap** — No register is driven by multiple sources in the same cycle
3. **No Floating** — Every combinational node (except I/O inputs) has at least one source
4. **No Dead Ends** — Every combinational node has at least one sink (either DFF or output)

(Full validation is performed at the validator stage using `validate.py`; this tool produces a netlist structure suitable for validation.)

## Architecture Constraints Enforced

### Single-Writer Law
Each DFF node is written by exactly one combinational source. Multi-source components (like CLB_DFFE) are partitioned by source so each partition has one writer.

Example:
- Bad: `CLB_DFFE_ALL` with connections from LUT, CARRY, and ROUTING (violates single-writer)
- Good: 
  - `CLB_DFFE_FROM_LUT` ← LUT only
  - `CLB_DFFE_FROM_CARRY` ← CARRY only
  - `CLB_DFFE_FROM_ROUTING` ← ROUTING only

### No Implicit Wiring
The tool does NOT infer hidden connections. All wiring is explicit in:
1. Canonical model `connections[]` (user-provided or extracted)
2. Implicit architectural wiring (LUT→CLB_FF, CARRY→CLB_FF, etc.)

### Branchless Logic
The device datapath is **entirely structural**. No conditional logic in device tick — only gate cells and registered transfers. (This is validated by `gennet.py` and `gate.sh`, not by this tool.)

## Implementation Details

### Partition Mapping
The tool maintains a **partition_sources map**: `original_name → {partitioned_names}`

Example:
```python
partition_sources = {
  "CLB_DFFE": {"CLB_DFFE_FROM_ROUTING", "CLB_DFFE_FROM_CARRY", "CLB_DFFE_FROM_LUT", ...},
  "BRAM_READ": {"BRAM_READ"},
  "DSP_OUTPUT": {"DSP_ACCUMULATOR", "DSP_MULTIPLIER", ...},
  ...
}
```

When processing connections, un-partitioned names (from the input canonical model) are remapped to their partitioned equivalents:
- `CLB_DFFE` → `CLB_DFFE_FROM_ROUTING` (or first partitioned version)
- `DSP_OUTPUT` → `DSP_ACCUMULATOR` (or first partitioned version)

### Synthesis from Inventory
If the canonical model lacks explicit `dff_nodes` or `comb_nodes`, the tool synthesizes them from the `inventory`:
- CLBs (182,400) → 2,918,400 DFFs (16 per CLB), 1,457,600 LUTs (8 per CLB)
- BRAM36 (2,160) → 77,760 read outputs (36 bits each)
- DSP48E2 (6,840) → 328,320 accumulator bits, multiply and add logic
- GTY (32 lanes) → 2,048 RX data latches (64 bits each)

### Connection Deduction
The tool adds implicit architectural connections based on device structure:
- LUT → CLB_DFFE_FROM_LUT
- CARRY_CHAIN → CLB_DFFE_FROM_CARRY
- ROUTING_SWITCH → LUT (multi-fanout routing)
- DSP_MULTIPLY → DSP_ACCUMULATOR
- DSP_ADDSUB → DSP_ACCUMULATOR

## Statistics

Output includes:
- `total_dff_nodes` — count of partitioned DFF node types
- `total_dff_registers` — sum of all DFF register count
- `total_comb_nodes` — count of combinational node types
- `total_comb_elements` — sum of all combinational element counts
- `total_connections` — count of distinct wiring paths
- `total_wires` — sum of connection counts (accounting for fanout)

Example (VU9P):
```json
"statistics": {
  "total_dff_nodes": 4,
  "total_dff_registers": 3326528,
  "total_comb_nodes": 7,
  "total_comb_elements": 2745930,
  "total_connections": 7,
  "total_wires": 1006
}
```

## Exit Codes

- **0** — Success; device netlist generated
- **1** — File not found or I/O error
- **2** — JSON parsing error in input

## Next Step: Validation

Once `device.net.json` is generated, validate it with:
```bash
python3 validate.py device.net.json
```

This performs comprehensive checks:
1. Single-writer law (each DFF has ≤1 source)
2. No-overlap (no conflicts)
3. No-floating (all nodes wired)

## References

- **canonical_device_model.json** — Source device model (from extraction/merge)
- **example_canonical_device_model.json** — VU9P example (for testing)
- **XILINX_VU9P_SPEC_EXTRACTION.md** — Device architecture reference
- **PARTSLIST_TO_GENNET.md** — Next stage (code generation from netlist)
