---
name: Build vs Assignment Separation
description: Building a module is a distinct task from assigning its inputs/outputs to pins and addresses — never fuse them
type: enforcement
source: Founder directive 2026-06-11; CLAUDE.md, memory/build-vs-assignment-task-separation.md
---

# Build vs Assignment Separation

**Core Rule:** Building a module and assigning it (addresses, pins, registry, inter-module
wiring) are **two distinct task phases**. You **build all modules to spec first**; only
once every module is built do you begin assigning inputs/outputs to pins and addresses.
Never combine the two in one task, one agent, or one commit.

## The two phases

- **BUILD (to spec, standalone):** construct the module from its own spec, test it
  standalone, promote it as-is. The module declares an **abstract input/output interface**
  (named, parameterized ports) and computes against that. No addresses, no pins, no
  registry, no binding to any other module.
- **ASSIGN (later, after all modules exist):** allocate addresses, place on pins,
  populate the registry, and bind one module's outputs to another's inputs (connection).
  This is the meta-tool's `assign` / `connect` job, run per artifact, as its own task.

## The sharp boundary (this is where it gets violated)

While **building** a module you must **NOT inspect or bind to another module's concrete
published registers, table depths, addresses, or pins** to shape it. That is *assignment
leakage* — it couples the build to a specific producer and breaks standalone
reproducibility.

- "footprint counts from DOM's payload" does **NOT** mean reference DOM's registers at
  build time. footprint declares an **abstract payload port** (e.g. "a per-tick
  price-indexed bid/ask activity payload of parameterized width + a bar-boundary signal")
  and counts from *that*. It is tested with a **synthetic payload**.
- Binding `footprint ← DOM` (real registers, widths, pins, addresses) happens **only** in
  the later assignment/connection phase, after all modules are built.

### ❌ NOT allowed (build phase)
- Reading `dom.net.json` to set footprint's input width or names.
- Putting absolute addresses / pin maps / `window_base` bindings in a module build artifact.
- A module spec hard-referencing another module's concrete register namespace
  (e.g. `DOM_BID_QTY`, `DOM_BEST_BID_PRICE_REG`) to define its own structure.

### ✅ Allowed (build phase)
- Abstract, parameterized input/output ports on the module's own spec.
- A standalone testbench driving those ports with synthetic data.
- Building, gating, and graduating the module with no knowledge of any peer.

## Why this matters

A graduated build artifact must be **pure construction** — reproducible independent of any
system context. If a module's build depends on a peer's address map or table depth, it is
no longer standalone, the vault is no longer honest, and a change to the peer silently
invalidates it. Keeping assignment separate also lets allocation stay fully programmatic
([[address_allocation_must_be_programmatic]]) and device blanks stay blank
([[fpga_device_blank_enforcement]]).

## Enforcement

- `checks/check_build_no_assignment.py`: a module build artifact must carry no assignment
  data — no absolute addresses/pins (`window_base`, etc.), and no hard references to a
  *peer* module's concrete register namespace. Run with `--strict` to fail.
- **Status: report-mode.** A baseline scan (2026-06-11) shows this law is currently
  violated codebase-wide — every module netlist carries an allocated `window_base`, and
  candle/footprint/tpo bind to peer `DOM_*`/`TF_*` registers. The check therefore runs in
  report mode until the **build/assignment remediation** lands (strip `window_base` out of
  build artifacts into the assignment/registry phase; replace peer-register seam_inputs
  with abstract ports). It flips to `--strict` in `gate.sh` once the baseline is clean.
- See also `memory/build-vs-assignment-task-separation.md`, CLAUDE.md, and the Index
  Doctrine (Law #10) for the data-model side.
