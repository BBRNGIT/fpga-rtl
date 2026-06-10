# C-as-RTL Workflow Discussion: Verilog Pattern Applied to Our System

## Executive Summary

We want to mirror the **Verilog workflow pattern** (Design → Simulate → Synthesize → P&R → Bitstream → Load) but tailored to **our C-as-RTL system**, not targeting real hardware synthesis.

**Key finding:** The 6 Verilog stages are not 1:1 with our stages. Some compress, some expand, some mean something fundamentally different.

---

## What We Have Now (Current System State)

### Existing Modules (15 graduated, validated)
```
NIC FPGA (125 MHz MAC):
  adapter, wire, mac, tai, taiosc, tai_cdc, nic, fifo_rx (writer)

Pipeline FPGA (250 MHz INTERNAL):
  dom, candle, footprint, tpo, timeframe, fractal, cbr, pip_resolver, fifo_rx (reader)
  [future: strategy, risk, OMS, SOR, outbound]

Independent:
  taiosc, tai (free-running oscillators)
```

### Existing Tools & Artifacts
```
DESIGN stage (complete):
  ├─ Spec: *.md (design intent)
  ├─ Emitter: gen_*.py (produces *.net.json)
  ├─ Generator: gennet.py (produces *_gen.h)
  └─ Output: *.net.json, *_gen.h (committed to .hft/)

SIMULATE stage (partial):
  ├─ Thin tests: test_synth.c (power-on + display, <45 lines)
  ├─ Market replay: make feed (CSV input, deterministic)
  └─ Missing: clock dispatcher, waveform export, golden trace builder

SYNTHESIZE stage (partial):
  ├─ Netlist validator: validate.py (single-writer, no-overlap, no-floating)
  ├─ Gate validator: gate.sh 2d (cell_count > 0)
  └─ Missing: optimizer, timing analyzer, cell-lib checker

PLACE & ROUTE stage (missing):
  └─ Concept: assign modules to FPGA instances, route signals

BITSTREAM stage (missing):
  └─ Concept: generate final system config/test harness

LOAD stage (missing):
  └─ Concept: run/deploy the final system
```

### Existing Artifacts (What Flows Between Tools)
```
*.md (spec)
  ↓ gen_*.py emitter
*.net.json (netlist: registers, cells, I/O)
  ↓ validate.py validator
  ↓ gennet.py generator
*_gen.h (device C: READ/COMPUTE/WRITE ticks)
  ↓ make feed (simulator)
register state + waveform (if captured)
```

---

## Verilog Workflow Stages — What They Mean for US

### Stage 1: DESIGN
**Verilog meaning:** Write RTL (Verilog/SystemVerilog text), describe digital logic.

**Our meaning:** Write C specs + emit netlists + generate device C.
- **Input:** Design intent (`.md` specification, architecture, register layout)
- **Process:**
  1. Hand-write spec (what the module should do, what registers, what logic)
  2. Hand-write emitter script (`gen_*.py`) that describes the circuit structure
  3. Emitter produces netlist (`*.net.json`): register declarations (dff_nodes), logic gates (comb_nodes), I/O ports
  4. Generator script (`gennet.py`) reads netlist → emits device C (`*_gen.h`)
  5. Device C is the "compiled RTL" — directly executable C code that models the circuit
- **Output:** `*.net.json` (circuit description), `*_gen.h` (executable model)
- **Status:** ✓ Complete. Already building modules this way (adapter through pip_resolver).
- **Gaps:** None known; process is sound and working.

### Stage 2: SIMULATE
**Verilog meaning:** Run behavioral/RTL simulation to verify logic correctness.

**Our meaning:** Run C clock-by-clock, verify register state against spec.
- **Input:** `*_gen.h` (device C), input stimuli (e.g., market CSV from `make feed`)
- **Current state:**
  - ✓ We run C ticks (`.hft_staging/make feed` drives the simulator)
  - ✓ Deterministic playback (same CSV → same register trace)
  - ✓ Thin tests (power-on + display, verify sanity)
  - ✗ Missing: clock dispatcher (currently hardcoded; should be configurable)
  - ✗ Missing: waveform export (VCD/FST for external viewing)
  - ✗ Missing: golden trace builder (deterministic regression reference)
  - ✗ Missing: probe/timing extractor (which registers settle when?)
- **Output:** Register state traces, waveforms (if exported), pass/fail
- **What makes ours different:** 
  - Verilog sim is event-driven; ours is cycle-accurate C (no events, pure state+logic)
  - We have 5 independent clocks; sim must respect their independence (not synchronize them)
  - We have display lanes; sim must capture them (for TUI later)
- **Critical missing tool:** Clock dispatcher (orchestrates 5 independent oscillators + defines execution order if sequenced)

### Stage 3: SYNTHESIZE
**Verilog meaning:** Convert RTL to gate-level netlist (combinational + sequential logic); optimize gates.

**Our meaning:** Validate + optimize gate graphs (the netlist is already in gate form).
- **Input:** `*.net.json` (netlist with gates already specified)
- **Current state:**
  - ✓ We have netlists in gate form (dff_nodes = registers, comb_nodes = gates)
  - ✓ validate.py enforces design rules (single-writer, no-overlap, no-floating)
  - ✓ gate.sh stage 2d counts cells (verifies no stubs)
  - ✗ Missing: logic optimizer (redundancy removal, common-subexpression elimination)
  - ✗ Missing: static timing analyzer (critical path, slack per clock domain)
  - ✗ Missing: cell-library validator (all referenced cells exist in `cells.h`)
- **Output:** Optimized netlist (if optimized), timing report
- **What makes ours different:**
  - Verilog's synthesis is RTL→gates (our gates are already explicit)
  - Our "synthesis" is mostly validation + optimization (gates don't change structure, just efficiency)
  - We don't synthesize to a specific FPGA library (we use generic gates: cell_addsub, cell_mux, cell_cmp, etc.)
- **Critical insight:** Our synthesis is fundamentally different — we're not converting RTL to gates; gates are already the design. We're validating + optimizing them.

### Stage 4: PLACE & ROUTE
**Verilog meaning:** Physical placement (where gates live on chip) + signal routing (how wires connect them).

**Our meaning:** Assign modules to FPGA instances + define signal routing (mostly logical, not physical).
- **Input:** Optimized netlist (from stage 3), module-to-instance mapping, FPGA template
- **What it should do:**
  1. Take the 15 modules + assign each to a home FPGA (NIC, Pipeline, CPU)
  2. Determine which modules are co-located (on same FPGA) vs. separated (cross-FPGA)
  3. For co-located: signals are "local" (1-cycle latency, same clock domain)
  4. For separated: signals must cross domain boundaries via CDC or SLR seams
  5. Generate routing constraints (which register → which pin, if external I/O)
  6. Generate placement map (module coordinates in fabric, if we model fabric)
- **Output:** Placement.json, routing constraints, pin map
- **What makes ours different:**
  - Verilog P&R is about physical silicon (place gates on CLBs, route metal)
  - Our P&R is mostly logical (assign modules to instances, route through known seams)
  - We don't have a detailed fabric model (no actual coordinates; just "NIC FPGA" vs "Pipeline FPGA")
  - We DO have explicit seam crossing rules (2-FF CDC, registered latency)
- **Critical missing tool:** Module placer + seam router (assigns modules to instances, validates CDC)
- **Existing support:** Contract schema + dependency graph (already produced by contract-extractor)

### Stage 5: BITSTREAM
**Verilog meaning:** Convert placed+routed design to FPGA bitstream (binary configuration file that programs the hardware).

**Our meaning:** Generate final system configuration / test harness.
- **Input:** Placed+routed layout (from stage 4), constraints
- **What it should do:**
  1. Validate timing closure (all paths meet cycle budgets: 4ns @ 250MHz, 8ns @ 125MHz)
  2. Generate... what?
     - **Option A:** A C test harness (compile + run the simulator)
     - **Option B:** A configuration file (describes module assignments, routing, constraints)
     - **Option C:** A system descriptor (JSON specifying the final deployed state)
- **Output:** Bitstream equivalent (TBD)
- **What makes ours different:**
  - Verilog's bitstream is a binary file that physically programs the FPGA
  - Ours is... unclear. Not physical. Maybe a config? A test? A deployment descriptor?
  - This is the largest open question.
- **Critical missing tool:** Timing closure validator + bitstream emitter

### Stage 6: LOAD
**Verilog meaning:** Program the FPGA with the bitstream (load into hardware, run).

**Our meaning:** Execute / deploy the system.
- **Input:** Bitstream equivalent (from stage 5)
- **What it should do:**
  1. Load... where? (Simulator? Test environment? Production?)
  2. Verify... what? (Does it match the golden trace from simulation?)
  3. Expose... what? (Instrumentation hooks for observability?)
- **Output:** Running system, verification report, live observability
- **What makes ours different:**
  - Verilog's load is "program the FPGA chip with JTAG/Ethernet"
  - Ours is... compile + run? Inject into simulator? Deploy to production? (Unclear)
  - We have golden traces from simulation; hardware must match them
- **Critical missing tool:** "Loader" (whatever that means for us)

---

## Which Verilog Stages Apply to Us? (Analysis)

| Stage | Verilog Meaning | Our Meaning | Exists? | Necessary? | Gap |
|---|---|---|---|---|---|
| **DESIGN** | Write RTL | Write specs + emit netlists | ✓ Complete | ✓ Yes | None |
| **SIMULATE** | Verify logic | Run C, check registers | ⚠ Partial | ✓ Yes | Clock dispatcher, waveform export, golden trace |
| **SYNTHESIZE** | RTL→gates | Validate + optimize gates | ⚠ Partial | ✓ Yes | Optimizer, STA, cell-lib validator |
| **PLACE & ROUTE** | Physical placement | Assign modules to instances | ✗ Missing | ? Unknown | Depends on what we need P&R to do |
| **BITSTREAM** | Program config | Final system config | ✗ Missing | ? Unknown | Unclear what "bitstream" means for us |
| **LOAD** | Program hardware | Deploy/run system | ✗ Missing | ? Unknown | Depends on deployment target |

---

## Open Questions (To Resolve in Next Phase)

### 1. **Is Place & Route Necessary?**
   - Verilog: Physical placement on silicon (mandatory)
   - Ours: Assign modules to FPGA instances (is this optional? Or do we validate it?)
   - **Question:** Can we just hardcode module → instance assignments in contracts, or do we need a formal P&R stage?
   - **Implication:** If P&R is just "declare which modules go where," it's trivial (one config file). If it's "validate CDC, check timing," it's substantial.

### 2. **What Is Our Bitstream?**
   - Verilog: Binary file programmed into FPGA
   - Ours: ???
   - **Options:**
     - **(A) C test harness:** Compile `*_gen.h` + `make feed` → executable that runs the simulator
     - **(B) Config file:** JSON/TOML describing final system state (modules, routes, constraints)
     - **(C) Both:** Bitstream is the config; loading means compiling + running with that config
   - **Critical:** This determines what stages 5–6 do.

### 3. **What Is Our Load?**
   - Verilog: Program the FPGA, run (result: silicon executing)
   - Ours: ???
   - **Options:**
     - **(A) Compile + run simulator:** `bitstream → gcc → ./hft_pipeline`
     - **(B) Load into test environment:** Inject bitstream into a test harness, run deterministic tests
     - **(C) Deploy to production:** ???
     - **(D) Multiple of above:** Different "load" modes for different use cases
   - **Critical:** This determines the final stage of the workflow.

### 4. **Is the Workflow Linear or Iterative?**
   - Verilog: Linear (Design → Simulate → Synthesize → P&R → Bitstream → Load)
   - Ours: ???
   - **Question:** Do we loop back? (e.g., Simulate finds bug → redesign → re-simulate)
   - **Implication:** If linear, the workflow is a pipeline. If iterative, we need feedback loops and gating.

### 5. **Where Do Contracts Fit?**
   - Contract schema specifies module I/O
   - Is contract validation part of DESIGN? SYNTHESIZE? P&R?
   - **Answer:** Likely DESIGN + early SYNTHESIZE (validate contracts before building)

### 6. **Where Does the Golden Trace Fit?**
   - Golden trace is produced in SIMULATE (deterministic replay)
   - Used in LOAD to verify final system matches simulation
   - **Answer:** Golden trace is the regression backbone connecting simulation to hardware (or final deployed state)

---

## Proposed Workflow for Our System (Draft)

Based on the analysis above, here's a proposed workflow tailored to us:

```
DESIGN phase (complete):
  spec.md → gen_*.py → *.net.json → gennet.py → *_gen.h

SIMULATE phase (enhance):
  *_gen.h + input CSV → [clock dispatcher] → register traces
  register traces → [waveform exporter] → *.vcd
  register traces → [golden trace builder] → golden.trace.json
  golden.trace.json (regression reference for later verification)

SYNTHESIZE phase (enhance):
  *.net.json → [cell-lib validator] → OK ✓
  *.net.json → [optimizer] → *.opt.net.json
  *.opt.net.json → [STA] → slack.report

PLACE & ROUTE phase (new, if necessary):
  *.opt.net.json + contracts → [placer] → placement.json
  placement.json → [router] → routes.json
  routes.json → [constraint gen] → constraints.json
  (Question: Is this phase necessary? Or just declare assignments in contracts?)

BITSTREAM phase (new, if necessary):
  constraints.json → [bitstream emitter] → ??? (C harness? Config file?)
  (Question: What is bitstream?)

LOAD phase (new, if necessary):
  bitstream → [loader] → running system
  running system → [verifier] → vs. golden.trace.json → pass/fail
  (Question: What does load mean?)
```

---

## False Parallels (Where Verilog Doesn't Apply)

| Verilog Concept | Why It Doesn't Apply | Our Alternative |
|---|---|---|
| **RTL synthesis** | We don't go from high-level RTL to gates; gates are already explicit | Validation + optimization of existing gates |
| **Physical placement** | We don't have physical coordinates; modules don't have area constraints (beyond cell count) | Logical assignment of modules to FPGA instances |
| **Detailed routing** | We don't model metal layers or wire delays; routing is mostly pre-defined via seams | Signal routing respects pre-defined seam boundaries (SLR crossings, CDC) |
| **Bitstream generation** | Ours isn't a binary programming file; it's something else | ??? (TBD) |
| **Hardware programming** | We're not programming physical silicon (at least not yet) | ??? (TBD) |

---

## Summary: Key Design Decisions Needed

Before we build tools, we must decide:

1. **Do we need a formal Place & Route phase?**
   - YES: If we want to validate CDC, check for cross-FPGA paths, ensure seam routing is correct
   - NO: If we just hardcode module assignments in contracts and skip validation

2. **What is our Bitstream equivalent?**
   - C test harness (compile + run)
   - Configuration file (JSON/TOML)
   - Both (config determines how harness runs)
   - Something else?

3. **What does Load mean?**
   - Compile + run the simulator
   - Run deterministic tests
   - Deploy to production
   - Multiple modes for different use cases

4. **Is the workflow linear or iterative?**
   - Linear (one-pass pipeline)
   - Iterative (feedback loops for bug fixes, design iterations)

5. **What tools are "nice-to-have" vs. "must-have"?**
   - Optimizer: nice-to-have (validation works without it)
   - STA: must-have (need to verify timing budgets)
   - Clock dispatcher: must-have (need to respect independent clocks)
   - P&R: depends on decision #1 above

---

## Next Steps

**Phase 2: Tool Taxonomy**
Once the above questions are resolved, we can design the tool taxonomy (what tools exist, what they do, inputs/outputs).

**Phase 3: Flow Diagram**
Visualize the workflow with boxes (stages), arrows (artifacts), and fork points (design decisions).

**Phase 4: Tool Design & Implementation**
Build the tools based on the taxonomy and diagram.
