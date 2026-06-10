# Module Contract Schema — Auto-Generated from Circuits

## Why: Contracts from Circuits, Not Hand-Written

**Contract = the module's promised interface, derived from its actual structure.**

Extract from:
- `.hft/<module>/<module>.net.json` (netlist: input/output ports)
- `.hft/<module>/<module>_gen.h` (generated C: register reads/writes, clock edges)
- Module's design spec (clock domain, function)

**Result:** A schema that describes what each module IS, not what we hope it is.

---

## Contract Schema (JSON)

```json
{
  "name": "dom",
  "version": "1.0.0",
  "cell_count": 84,
  "address_base": "0x2100000",
  "function": "Price-indexed order book with 10-level depth ladder",

  "clock_domain": {
    "name": "internal",
    "frequency_mhz": 250,
    "reference": "independent"
  },

  "inputs": [
    {
      "name": "packet_from_fifo",
      "width": 64,
      "source_module": "fifo_rx",
      "source_address": "0x2000000",
      "clock_domain": "internal",
      "latency_cycles": 0,
      "description": "Packet: {ts_47b, bid_8b, ask_8b, symbol_6b, pip_1b, comm_1b, seq_12b}",
      "required": true
    },
    {
      "name": "fifo_valid",
      "width": 1,
      "source_module": "fifo_rx",
      "clock_domain": "internal",
      "description": "FIFO has valid packet (rd_ptr != wr_ptr_synced)",
      "required": true
    },
    {
      "name": "timeframe_base_tick",
      "width": 1,
      "source_module": "timeframe",
      "clock_domain": "internal",
      "description": "Reference base period tick (pulse)",
      "required": false,
      "note": "Used only if DOM subscribes to base; optional"
    }
  ],

  "outputs": [
    {
      "name": "best_bid_price",
      "width": 64,
      "address": "0x2100000",
      "type": "register",
      "description": "Best bid price (u64, bps)",
      "latency_cycles": 1,
      "readers": ["candle", "footprint", "display_tui"]
    },
    {
      "name": "best_ask_price",
      "width": 64,
      "address": "0x2100008",
      "type": "register",
      "description": "Best ask price (u64, bps)",
      "latency_cycles": 1,
      "readers": ["candle", "footprint", "display_tui"]
    },
    {
      "name": "depth_bid",
      "width": 640,
      "address": "0x2100010",
      "type": "table",
      "table_entry_count": 10,
      "description": "Bid-side depth (10 levels, qty each)",
      "latency_cycles": 1,
      "readers": ["footprint", "display_tui"]
    },
    {
      "name": "depth_ask",
      "width": 640,
      "address": "0x2100050",
      "type": "table",
      "table_entry_count": 10,
      "description": "Ask-side depth (10 levels, qty each)",
      "latency_cycles": 1,
      "readers": ["footprint", "display_tui"]
    }
  ],

  "display_lanes": [
    {
      "name": "dom_display_best_bid",
      "width": 64,
      "address": "0x2100100",
      "type": "raw_register_read",
      "description": "Raw best bid for TUI (no reformat)"
    },
    {
      "name": "dom_display_best_ask",
      "width": 64,
      "address": "0x2100108",
      "description": "Raw best ask for TUI"
    },
    {
      "name": "dom_display_depth",
      "width": 1280,
      "address": "0x2100110",
      "description": "Raw depth ladder (both sides)"
    },
    {
      "name": "dom_display_bar_seq",
      "width": 64,
      "address": "0x2100150",
      "description": "Current bar sequence number"
    }
  ],

  "state": {
    "registers": [
      {
        "name": "DOM_BEST_BID_PRICE",
        "address": "0x2100000",
        "width": 64,
        "init_value": 0,
        "mutable": true,
        "owner": "dom"
      },
      {
        "name": "DOM_DEPTH_BID_QTY",
        "address": "0x2100010",
        "width": 640,
        "table_indexed": true,
        "index_width": 10,
        "init_value": 0,
        "mutable": true,
        "owner": "dom"
      }
    ],
    "history_ring": {
      "name": "DOM_HIST_RING",
      "depth": 256,
      "fields": ["best_bid", "best_ask", "depth_bid[10]", "depth_ask[10]", "bar_seq"],
      "description": "256 historical snapshots, indexed by bar sequence"
    }
  },

  "dependencies": [
    {
      "module": "fifo_rx",
      "reason": "Packet ingress from MAC domain",
      "reads": ["packet_data", "wr_gray_synced"],
      "required": true
    },
    {
      "module": "timeframe",
      "reason": "Base period reference (optional subscription)",
      "reads": ["timeframe_base_tick"],
      "required": false
    },
    {
      "module": "pip_resolver",
      "reason": "Symbol-to-pip-size lookup",
      "reads": ["symbol"],
      "writes_to": ["pip_resolver"],
      "required": true
    }
  ],

  "bar_support": {
    "supported": true,
    "multiplier": "user_configurable",
    "default_multiplier": 1,
    "subscription_model": "independent_check",
    "description": "Closes bars based on: (internal_tick_count % (base_period × multiplier)) == 0"
  },

  "constraints": {
    "no_floats": true,
    "no_malloc": true,
    "no_function_calls_in_datapath": true,
    "no_loops_over_bits": true,
    "branchless_data_path": true
  },

  "verification": {
    "cell_count_min": 1,
    "cell_count_actual": 84,
    "passes_gate_2d": true,
    "byte_identical_rebuild": true,
    "no_hand_written_device_logic": true
  }
}
```

---

## Contract Extraction Rules (Auto-Gen Algorithm)

### 1. **Module Metadata**
- `name`: directory name in `.hft/<name>`
- `version`: from `.hft/<name>/<name>_VERSION` or metadata
- `cell_count`: from `grep -o "cell_[a-z_]*(" <name>_gen.h | wc -l`
- `address_base`: from generated code `#define <NAME>_BASE 0x...`
- `function`: from design spec or netlist comment

### 2. **Clock Domain**
- Read from `.hft/<name>/<name>.net.json` `clock_domain` field
- Or infer from module name:
  - `adapter`, `wire`, `mac`, `tai`, `taiosc`, `tai_cdc`, `nic` → MAC (125 MHz)
  - `dom`, `candle`, `footprint`, `tpo`, `timeframe`, `fractal`, `cbr`, `pip_resolver` → INTERNAL (250 MHz)
- Reference: independent (always)

### 3. **Input Ports**
- Parse `.hft/<name>/<name>.net.json` `cross_module_inputs` array
- For each input:
  - `name`: signal name
  - `width`: bit width
  - `source_module`: which module writes this
  - `source_address`: where it lives
  - `clock_domain`: source clock (may differ from consumer)
  - `latency_cycles`: 0 if same cycle, 1 if registered cross-cycle
  - `required`: true if module cannot operate without it
  - `description`: what it represents

Example from DOM's netlist:
```json
"cross_module_inputs": [
  {
    "name": "packet_from_fifo",
    "width": 64,
    "source": "fifo_rx_output"
  }
]
```
→ Extract `source_module`, `source_address`, `clock_domain`, `latency_cycles`.

### 4. **Output Ports**
- Parse `.hft/<name>/<name>.net.json` `seam_nodes` (outputs to other modules)
- For each seam:
  - `name`: register name
  - `width`: bit width
  - `address`: backplane address
  - `type`: "register" or "table"
  - `latency_cycles`: always 1 (registered output from this module)
  - `readers`: infer from other modules' inputs (which module reads this address?)
  - `description`: semantic meaning

Example from DOM's netlist:
```json
"seam_nodes": [
  {
    "name": "DOM_BEST_BID_PRICE",
    "address": "0x2100000",
    "width": 64
  }
]
```
→ Extract readers by searching all other modules for reads of `0x2100000`.

### 5. **Display Lanes**
- Look for register declarations like `<MODULE>_DISPLAY_*` in generated code
- Extract:
  - `name`: signal name
  - `width`: bit width
  - `address`: where it lives
  - `type`: always "raw_register_read"
  - `description`: what it shows (no compute, just raw data)

### 6. **State (Registers & History)**
- Parse `dff_nodes` from netlist (live registers)
- Parse `history_ring` nodes (committed past)
- For each register:
  - `name`: C macro name
  - `address`: backplane address
  - `width`: bit width
  - `init_value`: reset value (or infer 0)
  - `mutable`: true (can be written by this module)
  - `owner`: this module (no other module can write)

### 7. **Dependencies**
- For each input, infer a dependency:
  - `module`: source module name
  - `reason`: what this input is for
  - `reads`: what fields/registers
  - `required`: true if critical, false if optional

### 8. **Bar Support**
- If module closes bars:
  - `supported`: true
  - `multiplier`: "user_configurable" or "fixed"
  - `default_multiplier`: 1 (or other)
  - `subscription_model`: "independent_check" (each module checks condition)
- If module doesn't close bars:
  - `supported`: false

### 9. **Constraints**
- Parse code for violations:
  - `no_floats`: grep for `float`, `double` (should be absent)
  - `no_malloc`: grep for `malloc`, `calloc` (should be absent)
  - `no_function_calls_in_datapath`: grep for function calls in COMPUTE phase
  - `no_loops_over_bits`: grep for `for` loops (should use builtins)
  - `branchless_data_path`: grep for `if`/`else` in COMPUTE (should use `cell_mux`)

### 10. **Verification**
- `cell_count_min`: 1 (gate.sh 2d rejects if 0)
- `cell_count_actual`: counted above
- `passes_gate_2d`: true if cell_count > 0
- `byte_identical_rebuild`: check if `make clean && gate.sh` produces byte-identical `*_gen.h`
- `no_hand_written_device_logic`: grep for device tick function (should be generated, not hand-written)

---

## Auto-Gen Tool Workflow

```bash
# 1. Scan all modules
for module in adapter wire mac tai taiosc tai_cdc nic fifo_rx dom candle footprint tpo timeframe fractal cbr pip_resolver; do
  
  # 2. Extract contract
  contract = extract_contract(.hft/${module})
  
  # 3. Infer cross-module readers
  for other_module in all_modules:
    for output in contract.outputs:
      if other_module reads output.address:
        contract.outputs[output].readers.append(other_module)
  
  # 4. Infer dependencies
  for input in contract.inputs:
    find source_module that writes input.source_address
    add dependency(source_module)
  
  # 5. Validate constraints
  contract.constraints = validate(module)
  
  # 6. Write contract JSON
  write(.hft/${module}/CONTRACT.json, contract)

done

# 7. Build global dependency graph
contracts = {name: load(.hft/${name}/CONTRACT.json) for name in all_modules}
dependency_graph = build_graph(contracts)

# 8. Validate graph (no cycles, all inputs satisfied)
validate_graph(dependency_graph)

# 9. Generate integration artifacts
generate_clock_dispatch(contracts)
generate_integration_harness(contracts)
generate_wiring_diagram(contracts)
```

---

## Output: Per-Module Contract Files

```
.hft/adapter/CONTRACT.json
.hft/wire/CONTRACT.json
.hft/mac/CONTRACT.json
.hft/tai/CONTRACT.json
.hft/taiosc/CONTRACT.json
.hft/tai_cdc/CONTRACT.json
.hft/nic/CONTRACT.json
.hft/fifo_rx/CONTRACT.json
.hft/dom/CONTRACT.json
.hft/candle/CONTRACT.json
.hft/footprint/CONTRACT.json
.hft/tpo/CONTRACT.json
.hft/timeframe/CONTRACT.json
.hft/fractal/CONTRACT.json
.hft/cbr/CONTRACT.json
.hft/pip_resolver/CONTRACT.json
```

Each contract is **auto-generated from the circuit** and describes:
- What it reads (inputs, sources, latency)
- What it writes (outputs, addresses, readers)
- What it displays (raw lanes for TUI)
- What it depends on (other modules)
- How it handles bars (subscription model, multiplier)
- Whether it passes structural validation (cell count, constraint compliance)

---

## Global Contract Artifacts (Derived from All Modules)

### 1. **dependency-graph.json**
```json
{
  "nodes": [
    {"name": "adapter", "clock_domain": "mac", "cell_count": 208},
    {"name": "wire", "clock_domain": "none", "cell_count": 0},
    ...
  ],
  "edges": [
    {"from": "adapter", "to": "wire", "signal": "bid_price", "latency": 1},
    {"from": "wire", "to": "nic", "signal": "bid_price", "latency": 0},
    {"from": "nic", "to": "fifo_rx", "signal": "packet", "latency": 8},
    {"from": "fifo_rx", "to": "dom", "signal": "packet", "latency": 2},
    ...
  ]
}
```

### 2. **integration-harness.c**
Generated glue code:
```c
// Auto-generated from contracts
// All modules' clock_edge_*() calls, sequenced by dependency graph

void fpga_tick(void) {
  // Read phase (all modules, any order — inputs frozen from prior tick)
  
  // Compute phase (all modules, any order — all inputs available)
  
  // Write phase (all modules, any order — latch outputs)
  
  // Display refresh (async, non-blocking)
}
```

### 3. **wiring-diagram.md**
Human-readable connectivity:
```
adapter[208 cells]
  └─ outputs: bid, ask, symbol, seq
  └─ writes to: WIRE

wire[0 cells]
  └─ relays: bid, ask, symbol, seq from adapter
  └─ reads by: NIC

NIC[180 cells]
  ├─ reads: WIRE (bid, ask, symbol, seq)
  ├─ reads: TAI_MAC (timestamp from tai_cdc)
  └─ outputs: packet {ts, bid, ask, symbol, pip, seq}
  └─ writes to: FIFO_RX

FIFO_RX[8211 cells]
  ├─ writes from: NIC (MAC domain)
  ├─ reads by: DOM (INTERNAL domain)
  └─ CDC: 2-FF gray-code sync on wr_gray, rd_gray

DOM[84 cells]
  ├─ reads: FIFO_RX (packet)
  ├─ reads: PIP_RESOLVER (symbol → pip)
  └─ outputs: BEST_BID, BEST_ASK, DEPTH_BID[10], DEPTH_ASK[10]
  └─ read by: CANDLE, FOOTPRINT, TPO, display_tui

CANDLE[16 cells]
  ├─ reads: DOM (best bid, best ask, depth)
  ├─ reads: TIMEFRAME_BASE_TICK (if subscribed)
  ├─ multiplier: user-configurable (default 1)
  └─ outputs: OHLC_BID, OHLC_ASK, VOLUME_BID, VOLUME_ASK, HIST_RING
  
... (and so on for all modules)
```

---

## Contract as Source of Truth

Once contracts are extracted and validated:
- **Block diagram is derived from contracts** (not the reverse)
- **Operational flow is derived from contracts** (execution order, dependencies, latency)
- **Integration harness is generated from contracts** (wiring, glue code)
- **Any code change must update the contract** (contract is the spec, code is the impl)

**Contracts become the canonical wiring specification for the entire system.**
