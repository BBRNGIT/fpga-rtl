# C-as-RTL Toolchain Architecture: Design → Simulate → Synthesize → P&R → Bitstream → Load

## Complete Workflow (from AGT Planner)

Six stages, grounded on existing artifacts (`*.net.json`, `*_gen.h`, `contract-extractor` output):

```
DESIGN                  SIMULATE         SYNTHESIZE            PLACE & ROUTE         BITSTREAM              LOAD
(exists)                (new)            (enhance)             (NEW ARCH)            (new)                  (new)
│                       │                │                      │                     │                      │
spec.md                T2.1 sim-core     T3.1 cell validator   T4.1 template         T5.1 timing           T6.1 programmer
  ↓                     T2.2 waveform    T3.2 optimizer        instantiate           closure                interface
gen_*.py                T2.3 golden      T3.3 STA              T4.2 placer           T5.2 bitstream        T6.2 in-circuit
  ↓                     trace replay     T2.4 timing probe     T4.3 intra-router     emitter               verifier
*.net.json              T2.4 activity    ─────────────→        T4.4 seam router      T5.3 config           T6.3 instrumentation
  ↓                     ↓ VCD export     ↓ slack report        T4.5 pin assigner     gen (manifest)        hooks
gennet.py                                ↓ critical path       T4.6 constraints      ↓ *.bit or *.cfg      ↓ live taps
  ↓                     Golden trace     ↓ activity profile    gen                   ↓ closure pass/fail    ↓ live VCD
*_gen.h                 (regression      ↓ optimized netlist   ↓ placement.json      ↓ load manifest
                        reference)       ↓ cell-lib OK         ↓ routes.json
                        ↓                                      ↓ pin map
                        DET replay pass                        ↓ constraints
                        (feeds STA)
```

## Tool Taxonomy (Existing + New)

| Tool | Stage | Responsibility | Input | Output | New? | Depends On |
|---|---|---|---|---|---|---|
| **T1.1: netlist-schema-formalizer** | DESIGN | Publish implicit `.net.json` schema | 15 `*.net.json` | `netlist.schema.json` | YES | — |
| **T2.1: sim-core (clock dispatcher)** | SIMULATE | Drive ticks via 5 independent clocks | `*_gen.h`, clock dispatch order | register time-series | YES | T1.1 |
| **T2.2: probe/waveform exporter** | SIMULATE | Tap registers → VCD/FST | sim-core memory dumps | `*.vcd` | YES | T2.1 |
| **T2.3: deterministic-replay harness** | SIMULATE | Same CSV → byte-identical trace | market CSV, sim-core | pass/fail + diff | YES | T2.1 |
| **T2.4: probe-timing extractor** | SIMULATE | Per-register settle cycles → STA input | sim-core | activity profile | YES | T2.1 |
| **T3.1: cell-library validator** | SYNTHESIZE | Verify all `cell_*` exist, arity OK | `*.net.json` + `cells.h` | mismatch report | YES | T1.1 |
| **T3.2: logic optimizer** | SYNTHESIZE | Redundancy removal, hazard analysis | `*.net.json` | `*.opt.net.json` | YES | T1.1, T3.1 |
| **T3.3: static timing analyzer** | SYNTHESIZE | Critical path / slack per domain | `*.opt.net.json` + activity | slack report, path list | YES | T3.2 |
| **T4.1: FPGA-template instantiator** | PLACE & ROUTE | Clone 3 fabric instances (NIC/Pipeline/CPU) | `registry-modules.json`, topology, template | `fabric.instances.json` | YES | T1.1 |
| **T4.2: module placer** | PLACE & ROUTE | Slot/coordinate assignment per fabric | T4.1 + cell counts | `*.placement.json` | YES | T4.1, T3.3 |
| **T4.3: intra-FPGA router** | PLACE & ROUTE | Route register lanes within each FPGA | placement + dependency graph | intra-routes | YES | T4.2 |
| **T4.4: cross-FPGA seam router** | PLACE & ROUTE | Route NIC→Pipeline seam (CDC-aware) | `CONTRACT.json` seams, T4.2 | seam routes + CDC constraints | YES | T4.2, contract-extractor |
| **T4.5: pin assigner** | PLACE & ROUTE | Module ports → physical FPGA pins | routes + board pinout | pin map | YES | T4.3, T4.4 |
| **T4.6: constraint generator** | PLACE & ROUTE | Emit timing/area/power constraints | all T4.x | `*.constraints.json` (+ `.xdc`) | YES | T4.5 |
| **T5.1: timing-closure gate** | BITSTREAM | Re-run STA on placed+routed design | `*.par.json` + constraints | closure pass/fail | YES | T4.6, T3.3 |
| **T5.2: bitstream emitter** | BITSTREAM | Layout → FPGA config format | closed layout | `*.bit` (vendor) or `*.simcfg` | YES | T5.1 |
| **T5.3: config-file generator** | BITSTREAM | Per-FPGA load manifest | T5.2 | `load.manifest.json` | YES | T5.2 |
| **T6.1: programmer interface** | LOAD | Abstract transport (JTAG/Ethernet/sim) | `*.bit` + manifest | device-loaded ack | YES | T5.3 |
| **T6.2: in-circuit verifier** | LOAD | Power-on sanity check vs. golden trace | live device + golden trace | go/no-go | YES | T6.1, T2.3 |
| **T6.3: instrumentation hooks** | LOAD | Live register taps (reuse VCD export) | live device | live VCD stream | YES | T6.1, T2.2 |

## Implementation Phases (Build Order)

### Phase 1: Solidify Front Half + Golden Trace (Low Risk, High Leverage)
**Goal:** Trustworthy simulation that will verify the bitstream later.

- **T1.1** — Formalize `netlist.schema.json` from existing 15 `*.net.json` files
- **T3.1** — Cell-library validator (cheap gate, prevents typos in netlists)
- **T2.1** — Sim-core: clock dispatcher honoring 5 independent oscillators + `CLK_DEP_TABLE`
- **T2.3** — Deterministic replay harness: same CSV → byte-identical register trace
- **Outcome:** Golden trace is the regression reference; everything downstream is verified against it.

### Phase 2: Analysis Backbone (STA, Probes)
**Goal:** Answer "does this meet timing?" before touching place-and-route.

- **T3.2** — Logic optimizer (re-validated against schema)
- **T3.3** — Static timing analyzer: critical path, slack per clock domain (4 ns @ 250 MHz, 8 ns @ 125 MHz)
- **T2.2** — Waveform exporter (integrate with GTKWave for visibility)
- **T2.4** — Probe-timing extractor (real activity → STA fed real numbers)
- **Outcome:** You can answer timing/slack questions; STA engine is built once, reused at T5.1 with post-route delays.

### Phase 3: Place & Route (Largest Effort, Highest Risk)
**Goal:** A placed, routed, constrained 3-FPGA layout ready for bitstream.

- **T4.1** — FPGA-template instantiator (3 clones from one template)
- **T4.2** — Module placer (area-aware: fifo_rx dominates at 8211 cells)
- **T4.3** — Intra-FPGA router (register lanes between co-located modules)
- **T4.4** — Cross-FPGA seam router (NIC→Pipeline, CDC-aware, the highest-risk tool)
- **T4.5** — Pin assigner (module ports → FPGA pins)
- **T4.6** — Constraint generator (`.constraints.json` + optional `.xdc` for Vivado)
- **Outcome:** A fully constrained 3-FPGA layout ready for timing closure.

### Phase 4: Bitstream + Load (Integration)
**Goal:** Load the config onto real or simulated FPGA, verify against golden trace.

- **T5.1** — Timing-closure gate (final STA on real delays; hard fail if any path misses budget)
- **T5.2** — Bitstream emitter (convert layout → vendor format or sim-fabric config)
- **T5.3** — Config-file generator (load manifest, per-FPGA ordering)
- **T6.1** — Programmer interface (JTAG/Ethernet/sim backend)
- **T6.2** — In-circuit verifier (power-on sanity vs. golden trace from Phase 1)
- **T6.3** — Instrumentation hooks (live register taps, live VCD)
- **Outcome:** Bitstream loaded, silicon verifies against golden trace, sim ≡ hardware proved.

---

## Critical Data Flows (The Artifacts Bus)

All artifacts are **validated JSON/C files** at each hop. No in-memory coupling.

```
Phase 1:
  15 × *.net.json     → [T1.1 schema check]           → netlist.schema.json
  *.net.json          → [T3.1 cell validator]         → cell-lib OK ✓
  *.net.json          → [T2.1 sim-core]               → register time-series
  register time-series → [T2.3 golden trace builder]   → golden.trace.json
  time-series         → [T2.4 activity extractor]      → activity.json

Phase 2:
  *.net.json          → [T3.2 optimizer]              → *.opt.net.json
  *.opt.net.json      → [T3.3 STA + T2.4 activity]    → slack.report + critical-paths.json

Phase 3:
  registry-modules    → [T4.1 instantiator]          → fabric.instances.json
  fabric.instances    → [T4.2 placer]                → placement.json
  placement.json      → [T4.3 intra-router]          → intra-routes.json
  intra-routes.json   → [T4.4 seam-router]           → seam-routes.json + CDC-constraints.json
  seam-routes.json    → [T4.5 pin assigner]          → pin-map.json
  pin-map.json        → [T4.6 constraints gen]       → constraints.json (+ .xdc)

Phase 4:
  constraints.json    → [T5.1 timing-closure]        → closure.report (pass/fail)
  closure.report      → [T5.2 bitstream emitter]     → *.bit or *.simcfg
  *.bit               → [T5.3 manifest gen]          → load.manifest.json
  load.manifest.json  → [T6.1 programmer]            → device loaded ✓
  device state        → [T6.2 in-circuit verifier]   → vs. golden.trace.json → go/no-go
  device state        → [T6.3 instrumentation]       → live.vcd
```

---

## Critical Dependencies & Build Order Laws

1. **T1.1 (netlist schema) is the root** — everything else reads it. Build first.
2. **T3.3 (STA) is the second pivot** — P&R cannot place without path delays; bitstream cannot close without STA. The STA *engine* is built once and reused.
3. **Golden trace (T2.3) is the regression backbone** — produced in Phase 1, consumed at T6.2 (silicon verification). If it breaks, everything breaks.
4. **contract-extractor output (already exists)** — `dependency-graph.json` and `CONTRACT.json` are direct inputs to T4.3/T4.4. No new connectivity extraction needed.
5. **T4.4 (seam router) carries the CDC law** — it is the one tool that can violate clock-domain separation. Must be specified against CLAUDE.md CDC rules, not invented.

---

## Three Critical Fork Points (Resolve Before Phase 3)

### Fork 1: Vivado vs. Custom P&R vs. Hybrid?

| Option | P&R Effort | Bitstream Effort | Real Hardware | Vendor Lock | C-as-RTL Purity |
|---|---|---|---|---|---|
| **(a) Vivado backend** | Low (vendor tool) | Zero | YES | High | Low (need Verilog shim) |
| **(b) Custom P&R** | HIGH (T4.x build) | Medium (T5.2) | Possible (complex) | None | High (all in C) |
| **(c) Hybrid (Rec.)** | Medium (custom T4.x) | Low (vendor T5.2) | YES | Low | Medium (P&R in C, bitstream vendored) |

**Recommendation:** Hybrid. T4.x (placement/routing/constraints) is where your project-specific knowledge lives (CDC-aware seam routing, independent clocks). T5.2 (bitstream generation) is where a vendor tool excels. T4.6 emits `.xdc` for Vivado, letting their P&R finish the job if you choose (a), or custom P&R handles all of it if you choose (b).

### Fork 2: Real Xilinx XCVU13P or Software Fabric?

- **Real silicon** — T6.1 transport is JTAG/Ethernet programmer. Phase 4 full build. Most effort, real performance, real constraints (power, thermal).
- **Software fabric** — T6.1 is just "load `.simcfg` into sim-core". Phase 4 collapses to T5.3→T6.2 (bitstream is a config struct, not a vendor file). Fastest validation, no hardware cost, perfect for development.

**Recommendation:** Software fabric first (Phase 3–4 complete in weeks, not months). Real silicon comes after you've proven the design on the software fabric (T6.2 in-circuit verifier comparing to golden trace validates that sim→hardware works).

### Fork 3: Optimizer Design (Separate Artifact or Replace?)

T3.2 changes the netlist, but the **build-sequence law** requires byte-identical rebuilds of committed `*.net.json`/`*_gen.h`.

- **Option A:** `*.opt.net.json` is a separate committed artifact (doesn't touch the originals).
- **Option B:** T3.2 replaces the original `*.net.json` (easier, but breaks immutability).

**Recommendation:** Option A (separate artifact). Preserves the clean-room law and lets you compare original vs. optimized netlists if a bug appears.

---

## Validation Checkpoints (Gate Integration)

Extend the existing `gate.sh` with Phase gates:

```bash
# Current gates (already exist)
gate_2a_validate()    # validate.py checks netlist structure
gate_2b_build()       # compile C
gate_2c_generated()   # no hand-written device logic
gate_2d_cell_count()  # cell_count > 0

# Phase 1 gates (new)
gate_phase1_design()  # T1.1 schema validation
gate_phase1_simulate() # T2.1 clock dispatch works, T2.3 golden trace reproducible
gate_phase1_analyze() # T3.1 cell-lib OK, T3.3 STA passes

# Phase 2 gates (new)
gate_phase2_p_and_r() # T4.x outputs valid placement.json, routes.json

# Phase 3 gates (new)
gate_phase3_closure() # T5.1 timing closes, T5.2 bitstream generated

# Phase 4 gates (new)
gate_phase4_load()    # T6.1 device loaded, T6.2 in-circuit verifier vs. golden ✓

# Invocation:
gate.sh --to=phase1       # DESIGN + SIMULATE + SYNTHESIZE
gate.sh --to=phase2       # ... + PLACE & ROUTE
gate.sh --to=phase3       # ... + BITSTREAM
gate.sh --to=phase4       # ... + LOAD (full RTL→silicon validation)
```

---

## Current Tool Inventory (What We Have)

- **T1.1 (schema)** — Implicit in `*.net.json` structure; formalize with JSON Schema.
- **T2.1 (sim-core)** — Skeleton in `make feed` (C simulator loop) and thin tests; enhance with clock dispatch.
- **T3.1 (cell-lib validator)** — Part of `validate.py`; extract into standalone.
- **T3.3 (STA)** — Nonexistent; design as a standalone Python tool (read netlists, compute critical path, output slack).
- **contract-extractor output** — Already built (`CONTRACT.json`, `dependency-graph.json`).
- **Everything else (T2.2–T6.3)** — New builds.

---

## Estimated Effort (Relative Sizing)

| Phase | Tools | Estimated Effort | Risk |
|---|---|---|---|
| Phase 1 (Front half + golden) | T1.1, T2.1, T2.3, T3.1, T3.3 | 2–3 weeks | Low (mostly know the rules) |
| Phase 2 (Optimizer + probes) | T2.2, T2.4, T3.2 | 1 week | Low (well-defined algorithms) |
| Phase 3 (P&R) | T4.1–T4.6 | 4–6 weeks | High (T4.4 seam router is novel) |
| Phase 4 (Bitstream + load) | T5.1–T6.3 | 2–3 weeks | Medium (depends on fork decisions) |
| **Total** | — | **9–13 weeks** | — |

(Assumes one engineer full-time, working linearly. Phases 1–2 can overlap with Phase 3 front end.)

---

## Summary: The Verilog Workflow, in C-as-RTL

You now have the **complete design for a six-stage toolchain** that mirrors Verilog's flow:

- **Design phase** (done) → C modules, netlists, generated device logic
- **Simulate phase** (build) → clock dispatcher, golden trace, regression
- **Synthesize phase** (enhance) → optimization, timing analysis, validation
- **Place & route** (new) → 3-FPGA template, module placement, signal routing, constraints
- **Bitstream** (new) → timing closure, config generation
- **Load** (new) → programmer interface, in-circuit verification against golden trace

The **golden trace** is the thread connecting simulation to silicon: build once in Phase 1, verify every bitstream against it in Phase 4.

**Next step:** Resolve the three fork points (Vivado vs. custom vs. hybrid; real vs. software; optimizer design), then start Phase 1 tools.
