---
title: CLAUDE.md
subtitle: Project Instructions for Claude Code (claude.ai/code)
description: >-
  Complete guidance for the C-as-RTL hardware design framework. Specifies the
  emitter-first pipeline for generating complete C hardware models for any device
  type (FPGA, ASIC, PCB, MCU). Covers architecture enforcement, development
  workflow, and immutable architectural laws.
version: "2.0.0"
status: "Active"
type: "Architectural Guidance"
language: "Markdown"
audience: "Claude Code agents, hardware engineers, RTL designers"

immutable_laws:
  - name: "C IS THE RTL"
    number: 9
    reference: "memory/c_is_rtl_immutable_law.md"
    enforcement: "skills/c_is_rtl_enforcement.md"
    summary: "C code IS the hardware specification. All device types (FPGA, ASIC, PCB, MCU) output C only. Device type is a parameter, not hardcoded."
  
  - name: "Immutability of .hft (Write-Once Vault)"
    number: 8
    summary: "Graduated components are byte-identical and immutable. Updates require new versioned paths."
  
  - name: "Self-Running Clocks, No External Step"
    number: 7
    summary: "Clocks advance from internal power, not from replay/testbench. No replay/CSV tokens in device registers."
  
  - name: "Data Law: Price-Only at Wire"
    number: 6
    summary: "Bid/ask only at boundaries. Derived metrics are read-only and non-blocking."
  
  - name: "No Floats, No Heap, No Function Pointers, No Ghost Values"
    number: 5
    summary: "Fixed integers, static arrays only. Every operand explicit in netlist."
  
  - name: "Single-Writer Law"
    number: 4
    summary: "Each register written by exactly one module. Placement = wiring."
  
  - name: "Build-Sequence Law"
    number: 3
    summary: "Device logic is generated, never hand-written. Netlist → gennet → C code."
  
  - name: "Gate-Level Arithmetic"
    number: 2
    summary: "Structural cells only. No native +/-/* in device tick. Use cell_addsub, cell_mux, etc."
  
  - name: "Flip-Flop Level & Branchless Device Logic"
    number: 1
    summary: "Every signal is a register. Device data path is entirely branchless."

memory_references:
  immutable_law: "memory/c_is_rtl_immutable_law.md"
  enforcement: "skills/c_is_rtl_enforcement.md"
  fileset_pattern: "memory/fileset_pattern_universal_device_types.md"
  separation_law: "memory/fpga_device_module_separation_law.md"
  address_allocation: "memory/address_allocation_must_be_programmatic.md"
  memory_index: "memory/MEMORY.md"

canonical_references:
  - "FOUNDER_VISION.md"
  - ".hft/README.md"
  - ".hft_staging/DESIGN_GUIDE.md"

repository_structure:
  staging: ".hft_staging/ (development, cloned & specialized)"
  vault: ".hft/ (immutable, write-once)"
  graduate_workflow: "develop → validate → commit → graduate"

key_commands:
  validate_component: ".hft_staging/gate.sh .hft_staging/<module>"
  generate_c: "cd .hft_staging/<module> && make gen"
  run_test: "cd .hft_staging/<module> && make test"
  graduate: ".hft_staging/graduate.sh <module>"
  specialize_device: "python3 gen_device_specialization.py --type <type> <spec> <modules> <output>"

tags:
  - "C-as-RTL"
  - "hardware-design"
  - "emitter-first"
  - "netlist-generation"
  - "architecture-enforcement"
  - "immutable-laws"
  - "FPGA"
  - "ASIC"
  - "PCB"
  - "MCU"
  - "gate-level"
  - "flip-flop-level"
  - "universal-device-generation"

created: "2025-06-10"
updated: "2025-06-10"
author: "Founder Vision"
maintainers: ["Claude Code agents", "Hardware architects"]
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **C-as-RTL hardware design framework** — a universal system that generates complete C hardware models for any device type (FPGA, ASIC, PCB, MCU, custom silicon). A collection of flip-flop-level digital components, specified as pure C code, deployed to any target technology. Components include adapters, indicators (candle, footprint, CBR), data structures (FIFO, wire), and infrastructure (MAC, NIC, timing).

**Key philosophy:** Architecture is king, not results. A passing binary with the wrong structure is rejected. Always defer to the founder's blueprints and established patterns (especially the adapter pattern).

**Reference:** See FOUNDER_VISION.md for the canonical architecture reference, system model, and design philosophy.

## 🚫 IMMUTABLE ARCHITECTURAL LAW: C IS THE RTL

**C code IS the hardware specification.** Not a generator. Not a simulator. Not a wrapper.

- All device types (FPGA, ASIC, PCB, MCU, custom) output **C only** — no Verilog, no schematics, no firmware images.
- Device type is a **parameter** in `gen_device_specialization.py`, not hardcoded in separate tools.
- The fileset pattern is **universal** — same structure for all device types.
- Output is always `device_<type>_*_gen.h` — a complete C model of the realized hardware.
- Validation rules (single-writer, no-overlap, no-floating) are **device-agnostic**.

**This is immutable and non-negotiable.** See `memory/c_is_rtl_immutable_law.md` and `skills/c_is_rtl_enforcement.md`.

## Repository Structure

### Two-Tier Repository

- **`.hft_staging/`** — Development repository. All new components start here. Holds uncommitted, in-progress, and validated-but-not-yet-graduated work. Each component is a self-contained directory with its own Makefile and sources.
- **`.hft/`** — Immutable vault repository. Holds byte-identical copies of *validated, committed* sources from staging. Protected by a pre-commit hook that blocks any modification or deletion of already-tracked files (write-once/immutable policy).

Workflow: develop → validate → commit → graduate.

## Architecture Enforcement Tools

The project's constraints are enforced at commit and graduation time by automatic validators — not guidance, but hard blocks:

- **`gate.sh`** — Pre-graduation validator that runs 3 main stages with substeps:
  1. Netlist validator (`validate.py`) — single-writer, no-overlap, no-floating checks
  2. Build + test + gate checks (working tree):
     - Build and run thin test
     - Gate-level arithmetic check — AWK scan for native `+`/`-`/`*` outside `cell_*()` in tick
     - Build-sequence check — no hand-written `cell_*()` or `*_tick` in `.c`/`.h`
     - Logic-content check — at least one structural cell in `*_gen.h` (catches stubs)
  3. Clean-room build — rebuild from committed HEAD in temp dir to prove determinism
  
  Must pass before `graduate.sh` will promote a component.

- **Vault immutability** — Graduated components in `.hft/` are write-once. To update a graduated component, create a new versioned path (e.g., `candle_v2/`) rather than editing in place. See Architectural Law #8 for details.

**Note:** Pre-commit hooks for generated file validation are documented in the architecture but not yet active in this repository. Currently, validation happens via `gate.sh` before graduation.

These validators are not suggestions — they are programmatic enforcers of the architecture.

### Component Structure

Each component (e.g., `.hft_staging/adapter/`) follows this template:

```
<MODULE>.md              — Design doc: registers, READ→COMPUTE→WRITE flow, clock domain, connections
gen_<module>_net.py      — Netlist emitter (DELIVERABLE: you write this)
<module>.net.json        — Generated netlist (output of emitter; do not hand-edit logic)
cells.h                  — Branchless primitives (buf/not/and/or/xor/mux/eqmask/dff/fa/gate)
gennet.py                — Netlist → device C generator (reference: adapter/gennet.py)
validate.py              — Gate-level validator (reference: adapter/validate.py)
<module>.c/.h            — Host glue and starter (no main(); modules are passive)
buffer.c/.h              — Input side (ONLY place conditionals; external data ingestion)
display.c/.h             — Output side (reads lanes raw; no compute)
test_<module>.c          — Thin test: power-on + display only (≤45 lines)
probe.c                  — Diagnostic: per-tick waveform dump (logic analyzer view)
Makefile                 — Build targets: validate, gen, test, probe, xau; this tree only
.gitignore               — Ignore sibling *_gen.h + compiled + *.bin; own <mod>_gen.h is COMMITTED
```

## Key Architectural Laws

These are **non-negotiable.** Violations block graduation.

### 1. Flip-Flop Level & Branchless Device Logic

- Every signal, flip-flop, gate is its own addressed register.
- Device data path is **entirely branchless**: no `if`/`?:`/`switch`/`for`/`while` inside generated tick.
- Operations are **mask algebra & gate primitives only** (cell_mux, cell_and, cell_dff, cell_addsub, etc.).
- Conditionals live ONLY in:
  - The buffer (ingress, external data conditioning)
  - Offline `prep` (CSV→binary conversions outside the system)
  - External display/probe
  - Never in the generated device.

### 2. Gate-Level Arithmetic (Enforced by gate.sh / graduate.sh)

The device datapath must use **structural cells only**. Native C arithmetic (`+`, `-`, `*`) is forbidden inside the generated `*_tick()` function.

- **Additions/subtractions** → `cell_addsub` (carry-chain primitive)
- **Comparisons** → `cell_cmp_*` or gate netlists
- **Multiplexers** → `cell_mux`
- **Shifts** → `cell_sar` (shift-arithmetic-right) or bit-select masks

The gate validates this via an AWK pass over `*_gen.h`: strips comments, verifies no `+`/`-`/`*` tokens outside `cell_*()` calls within the tick body. A violation causes graduation to fail.

### 3. Build-Sequence Law (Device Logic is Generated, Not Hand-Written)

**Your deliverable is the netlist + the gennet GENERATOR.** You do not hand-code flip-flop logic.

- **You write:** `gen_<module>_net.py` (emitter), `<module>.net.json` (netlist), `gennet.py` (generator)
- **You do NOT write:** Device tick (`*_tick`), `cell_*()` compositions, or `*_gen.h`
- **gennet.py produces:** `*_gen.h` with explicit READ→COMPUTE→WRITE phases and all cell calls

The flow is: `.net.json` → `gennet.py <module>.net.json` → `*_gen.h` (generated, committed as validation spec).

A pre-commit hook (`check_generated.sh`) validates: running `gennet.py` against the committed netlist byte-matches the committed `*_gen.h`. Any hand-written tick or cell call outside `*_gen.h` is rejected.

### 4. Single-Writer Law

- A device writes only its own registers; consumers only read.
- No two components write the same register.
- Placement = wiring; register addresses define data flow.

### 5. No Floats, No Heap, No Function Pointers, No "Ghost" Values

- No `float`/`double`.
- No `malloc`/`calloc`/`realloc` (no heap).
- No function pointers.
- No inferred operands (every value reads from a committed register; no hidden aggressor/mid/side inference).
- Every operand is explicit in the netlist.

### 6. Data Law: Price-Only at Wire

Bid, ask, time, symbol, pip, commission, seq, valid. Downstream derives spread, mid, qty, side from these primitives. No invented fields.

### 7. Self-Running Clocks, No External Step

- Clocks advance from an internal power bit, not from external replay/testbench commands.
- No tokens like `replay`, `source-type`, `CSV`, `file` in any device register or address map.

### 8. Immutability of .hft (Write-Once Vault)

- Once a component is graduated into `.hft/`, it is byte-identical and immutable.
- To update a graduated component, create a new versioned path (e.g., `candle_v2/`) rather than editing in place.
- Rare re-graduation requires an environment override: `HFT_ALLOW_REGRADUATE=1 git commit ...`

### 9. C IS The RTL (Universal Device Generation — IMMUTABLE)

**C code IS the complete hardware specification.** Not a generator of Verilog. Not a simulator. Not a wrapper.

- **All device types output C only** — no Verilog, no schematics, no firmware images.
  - FPGA → `device_fpga_*_gen.h` (complete C model of FPGA)
  - ASIC → `device_asic_*_gen.h` (complete C model of ASIC)
  - PCB → `device_pcb_*_gen.h` (complete C model of PCB)
  - MCU → `device_mcu_*_gen.h` (complete C model of MCU)
  
- **Device type is a parameter** — not hardcoded in separate tools.
  - Use: `gen_device_specialization.py --type fpga|asic|pcb|mcu`
  - Not: `gen_fpga_specialization.py`, `gen_asic_specialization.py`, etc.

- **Fileset pattern is universal** — same structure for all device types.
  - Same template: `DEVICE_<TYPE>_DESIGN.md`
  - Same emitter: `gen_device_<type>_*_net.py`
  - Same netlist: `device_<type>_*.net.json`
  - Same generator: `gennet_device_<type>_*.py`
  - Same output: `device_<type>_*_gen.h` (C)

- **Validation is device-agnostic** — single-writer, no-overlap, no-floating apply to all types.

- **Netlist maps to device primitives** — emitter translates modules to technology-specific components.
  - FPGA: CLB, BRAM, DSP, GTY, I/O banks
  - ASIC: Standard cells, SRAM, gates
  - PCB: IC packages, resistors, capacitors
  - MCU: ARM cores, RAM, GPIO, UART

**This law is immutable.** No deviations permitted. See `memory/c_is_rtl_immutable_law.md` and `skills/c_is_rtl_enforcement.md`.

### 10. The Index Doctrine — One Quantum; Price & Time Are Indices, Not Stored Data

**There is one fundamental unit: the internal clock tick.** Everything called "time"
is a bounded count of it, and price is a natural index *within* a time frame — never
an absolute stored coordinate.

- **One quantum.** `taiosc` mints the internal clock tick (the sole oscillator).
  `tai` = accumulated ticks = time itself ("now" is tick-count since power-on; there
  is no absolute wall-clock — ingress re-stamps external time onto the tick-count).
- **Frames are bounded tick-counts.** `timeframe` counts ticks and rolls `BAR_SEQ`
  at the period — a *bar is N internal ticks*. The bar is not a fundamental axis; it
  is a coarsened stride on the one tick axis. DOM lives at the raw tick (stride 1);
  candle/footprint/tpo live at the bar (stride = period ticks). Same axis.
- **Price is a natural in-frame index.** Within a frame, price is a **pip-offset**
  (`offset = price − frame_origin`, in pip units from `pip_resolver`), origin set by
  a *time event* — bar-open for the bar indicators, current top-of-book per tick for
  DOM. **There is no absolute price**; it is an external abstraction that does not
  apply here. The price canvas expands/shrinks to what the frame covered (bar pip-range
  / book pip-depth); its only sizing knob is the max pip-span a frame may occupy.
- **Modules are price-indexed activity counters.** Each stores a *measure* at a
  price-index (volume, count, depth), sampled at its tick-stride. DOM is the live
  per-tick layer; the bar indicators accumulate the same activity over `period` ticks.
  tpo = time-touches per pip; footprint = volume per pip; candle = the bar's pip-extremes.
- **Price is stored as a VALUE only when it is the measured quantity** (e.g. candle's
  OHLC), and **never as the axis** — when price is the axis it is the address, not data.
  Therefore: no allocation, no free-slot search, no stored price keys, no anchor/window
  subsystem. The index *is* the match; the position *is* the price.
- **`pip_resolver` owns nothing** — it is a per-symbol lookup that publishes the pip
  size (the price-index separation). `timeframe` is a tick accumulator (the bar stride).
  Neither is an "axis authority"; time (tick-count) is the only persistent reference.

This unifies the clock hierarchy (`taiosc → tai → timeframe`) with the data model:
the oscillator produces the quantum, `tai` counts it into time, `timeframe` bounds it
into bars, and every module projects price-indexed activity onto that one tick axis.
See `memory/index_doctrine_price_time_as_index.md`.

## Development Workflow

### 1. Design Phase

Before any code, write `<MODULE>.md` with:
- Register definitions (IN/OUT from spec)
- READ→COMPUTE→WRITE behavior (boolean/mask operations per clock edge)
- Clock domain + address window
- Connections: which lanes read/write, who consumes
- Flag any open decisions for the founder (don't silently choose)

Reference documents: `.hft_staging/SPEC_REGISTERS.md`, `.hft_staging/ARCHITECTURE_CLARIFICATIONS.md`, `.hft_staging/BLOCK_DIAGRAM_DETAILED.md`.

**Emitter & Generator Workflow:** Each component follows a **three-stage code-generation pipeline** (described in FOUNDER_VISION.md):
- **Emitter** (`gen_<module>_net.py`) — Hand-written Python script that outputs the netlist JSON: `python3 gen_<module>_net.py > <module>.net.json`
- **Netlist** (`<module>.net.json`) — Generated JSON specification (COMMITTED to git). Defines registers, gates, and wiring. Validate with: `python3 validate.py <module>.net.json`
- **Generator** (`gennet.py`) — Hand-written Python script that converts netlist to device C: `python3 gennet.py <module>.net.json > <module>_gen.h`. Output (`<module>_gen.h`) is committed as a validation artifact — it proves the netlist was generated deterministically.

**Device Specialization Workflow:** Device implementations use a **meta tool** to eliminate hand-wired allocation:
- **Blank template** (`DEVICE_DESIGN.md`) — Pure device reference (specs, generic structure, no device-specific allocation)
- **Module list** (YAML) — Which modules go where, cell counts, requirements
- **Meta tool** (`gen_device_specialization.py --type <type>`) — Parametrized by device type, generates:
  1. Specialized device doc (`DEVICE_<TYPE>_<NAME>.md`) with programmatic allocation
  2. Emitter skeleton (`gen_device_<type>_<name>_net.py`) with hardcoded resource allocation
  3. Validation report (constraints satisfied)
- **Emitter** — User fills in wiring logic, generates composite netlist
- **Netlist** — Device-level netlist (all modules + interconnect + CDC regions)

**Key principle:** All allocation is programmatic. Device type is a parameter. All outputs are C.

### 2. Template & Scaffold

Copy the adapter structure as a template. Most files (cells.h, Makefile, validate.py, test structure, display.c) are nearly identical across components. Change only:
- The netlist + emitter
- The specific READ→COMPUTE→WRITE logic
- Display fields

### 3. Build & Validate

```sh
# Inside a component directory (e.g., .hft_staging/adapter/)
make validate     # netlist validator (single-writer/no-overlap/no-floating)
make gen          # gennet: .net.json → *_gen.h
make test         # compile & run thin test
make probe        # per-tick waveform diagnostic
make xau          # real data test (if applicable)

# Validate the entire component
.hft_staging/gate.sh .hft_staging/<module>
```

`gate.sh` runs 3 main stages:
1. Netlist validator (single-writer, no-overlap, no-floating checks)
2. Build + test + gate checks: build and test, then check arithmetic, build-sequence, and logic-content
3. Clean-room build from committed HEAD to prove determinism

### 4. Commit & Graduate

Only commit a component once it passes the gate:

```sh
git add <explicit paths>        # never git add -A; name each file
git commit -m "<stage>: <type>: <lowercase desc>"
.hft_staging/graduate.sh <module>
```

`graduate.sh` validates, cleans, builds, and copies the byte-identical source from HEAD into `.hft/<module>/`, then commits to the vault with immutability guards.

### 5. Dependencies & Seams

Components may depend on sibling published interfaces:

- **Adapter** reads the wire's canonical lane map. Wire publishes `wire.net.json` and its `gennet.py`. Adapter's Makefile regenerates `wire_gen.h` from the wire's source at build time.
- This is clean-room safe: the whole staging tree is archived from HEAD, build happens inside the component subdir, and sibling sources are exactly as committed.

## Common Commands

### Module Development

```sh
# Validate and test a component
.hft_staging/gate.sh .hft_staging/adapter

# Generate device C from netlist (must do this after any netlist edit)
cd .hft_staging/adapter && make gen

# Run the thin test
cd .hft_staging/adapter && make test

# Run per-tick diagnostic
cd .hft_staging/adapter && make probe

# Graduate to vault (only after gate.sh PASS)
.hft_staging/graduate.sh adapter

# Re-graduate if needed (rare)
HFT_ALLOW_REGRADUATE=1 .hft_staging/graduate.sh adapter

# Clean build artifacts
cd .hft_staging/<module> && make clean
```

### Device Specialization

```sh
# Specialize a blank device template with programmatic allocation (parametrized by device type)
python3 gen_device_specialization.py --type fpga \
  DEVICE_DESIGN.md \
  fpga_nic_modules.yaml \
  device_fpga_nic/

# Or ASIC, PCB, MCU:
python3 gen_device_specialization.py --type asic ...
python3 gen_device_specialization.py --type pcb ...
python3 gen_device_specialization.py --type mcu ...

# Output:
#   device_<type>_<name>/DEVICE_<TYPE>_<NAME>.md (design doc with allocated resources)
#   device_<type>_<name>/gen_device_<type>_<name>_net.py (emitter skeleton)
#   device_<type>_<name>/validation_report.txt (constraint check)

# Then build the device netlist (user fills in gen_device_<type>_<name>_net.py wiring)
cd device_<type>_<name> && python3 gen_device_<type>_<name>_net.py > device_<type>_<name>.net.json

# Validate the device netlist
python3 validate_device.py device_<type>_<name>.net.json
```

### Makefile Targets (within a component directory)

- `make validate` — Run netlist validator (single-writer, no-overlap, no-floating checks)
- `make gen` — Generate `*_gen.h` from `<module>.net.json` using gennet.py
- `make test` — Compile and run thin test (power-on + display only)
- `make probe` — Per-tick waveform diagnostic dump (logic analyzer view)
- `make xau` — Optional real-data test (if data_xau_test.csv exists)
- `make clean` — Remove compiled artifacts and generated files

### What "Graduated" Means

Graduation is the process of promoting a validated, committed component from `.hft_staging/<module>/` to `.hft/<module>/` (the immutable vault). Only run `graduate.sh` after `gate.sh` passes. A graduated component is byte-identical and immutable — updates require new versioned paths (e.g., `candle_v2/`).

## Key Design Patterns

### The Adapter Pattern (Reference)

The adapter is the proven template. It:
- Reads price data from the wire bus (no conditionals; pure mask algebra).
- Buffers ingress data (conditionals live here, not in device).
- Outputs a synthesized (flat) price record with mid-price.
- Uses a single flip-flop register for state (ADAPTER_PRICE_LIVE).
- Demonstrates the READ→COMPUTE→WRITE structure in gennet.py.

**Study `.hft_staging/adapter/` first.** Most new components inherit its structure.

### Indicator Architecture (Reference)

Indicators (candle, footprint, CBR) follow the indicator template. See `.hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md`.

Each indicator specifies:
- Input interface (e.g., DOM bid/ask, timeframe bar boundaries)
- Register state (live during bar, completed at bar close, history ring)
- Combinational logic (bar logic, ring indexing, accumulation)
- Output interface (seam nodes: completed bars, live bar, history)

The netlist is the source of truth; gennet generates the device C.

## Key Documents

- **`FOUNDER_VISION.md`** — Canonical architecture reference, system model, and design philosophy
- **`.hft/README.md`** — Vault immutability laws
- **`.hft_staging/DESIGN_GUIDE.md`** — Full component build process (steps 0–6)
- **`.hft_staging/INDICATOR_ARCHITECTURE_TEMPLATE.md`** — Template for indicator specs
- **`.hft_staging/ARCHITECTURE_CLARIFICATIONS.md`** — System-wide cross-module connections
- **`.hft_staging/BLOCK_DIAGRAM_DETAILED.md`** — Data flow diagram
- **`.hft_staging/DEVICE_DESIGN.md`** — Blank device template (reference only)
- **`.hft_staging/GEN_DEVICE_SPECIALIZATION_QUICKSTART.md`** — Device specialization guide (5-minute intro)
- **Adapter component (`adapter/`)** — Proven reference implementation

## Common Pitfalls

1. **Hand-writing device logic** — The gate will reject it. Write the netlist + gennet instead.
2. **Conditional logic in device tick** — Use `cell_mux` (conditional write via mask) instead.
3. **Floats, malloc, or function pointers** — Not allowed. All state is registers; selection is mask algebra.
4. **Forgetting `make clean` before `graduate.sh`** — The graduate gate does a clean build; stale artifacts can hide broken logic.
5. **Editing files in `.hft/`** — Pre-commit hook blocks it. Create a new versioned path instead.
6. **Not validating netlist before build** — Always run `make validate` first; it catches single-writer and overlap issues early.
7. **Inventing vocabulary not in founder's docs** — Adhere strictly to registers, signal names, and abstractions in the spec.
8. **Uncommitted changes at graduation** — `graduate.sh` copies from HEAD; all work must be committed first.

## Testing Philosophy

- **Thin test:** Power-on + display only (≤45 lines). No inject, step, replay, or CSV token.
- **Probe:** Per-tick waveform (logic analyzer). Inspect any prepped dataset.
- **Real data (xau):** Optional; tests against live tick data if available.

Tests run the *actual device* with real data, not mocks or simulation. Testbench ≠ device.

## Gate-Level Details (for advanced work)

The gate enforces several constraints via AWK/shell passes:

1. **Netlist validator (`validate.py`)** — Scans `.net.json` for single-writer (each register written by exactly one node), no-overlap (no read/write conflicts), no-floating (all nodes wired).
2. **Arithmetic check** — AWK pass over `*_gen.h`: strips comments, verifies no native `+`/`-`/`*` outside `cell_*()` in tick body.
3. **Build-sequence check** — No `cell_*()` or `*_tick` in hand-written `.c`/`.h`; only in `*_gen.h` (from gennet).
4. **Logic-content check** — At least one `cell_*()` call in `*_gen.h` (catches register stubs, which are incomplete).

See `.hft_staging/gate.sh` for the full script logic.

## Graduation Guarantees

A graduated component guarantees:
- Source is committed (no dirty working-tree artifacts).
- Netlist validates (single-writer, no-overlap, no-floating).
- Builds from committed HEAD (clean-room, dependency-aware).
- No native arithmetic in device tick.
- No hand-written device logic.
- Contains structural cell logic (not a stub).
- Byte-identical to committed HEAD (no build drift).

## Project Notes

- **Timeframe:** See `.hft_staging/timeframe/` for clock and bar-boundary signals.
- **Wire:** See `.hft_staging/wire/` for the lane seam and cross-component wiring.
- **DOM:** Decision-of-market state (bid/ask depth) — sourced from external ingress.
- **TAI:** Timestamp; see `.hft_staging/tai/` for TAI counter and CDC logic.

## Getting Help

If a component build fails:
1. Run `make validate` in isolation; fixes most netlist issues.
2. Check `.hft_staging/gate.sh` output for specific failures (arithmetic, build-sequence, clean-room).
3. Refer to `.hft_staging/DESIGN_GUIDE.md` step 5 for iteration patterns.
4. Study the adapter's gennet.py and netlist for gate-level patterns.

When unsure about architecture, defer to the founder's specs in `.hft_staging/ARCHITECTURE_CLARIFICATIONS.md` and component-specific `.md` files.
