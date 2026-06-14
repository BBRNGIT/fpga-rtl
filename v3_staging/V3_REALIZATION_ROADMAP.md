# V3 Realization Roadmap — Extracted Data → XCZU19EG C-Hardware

**Purpose:** a deterministic, tool-driven plan to realize the fully-extracted XCZU19EG
data into a complete C model of the device, then load our design onto it. No vibe coding:
every step is a tool run, gated, parallelized, and observed.

## Guardrails (binding — every phase honors these)

- **C IS the RTL (Law #9).** Every output is C (or the spec/netlist that emits C). No Verilog/TCL.
- **Tools build, hands don't (Law #3, #11).** Deliverables are emitters/specs/generators. No
  hand-written `*_gen.h`, tick, or netlist logic.
- **Parallel tool instances; agents OBSERVE (founder directive 2026-06-14).** Work is sharded
  across many concurrent copies of our tools; agents/harness monitor processes, collect gate
  results, retry transients, halt on validation failure. Agents never do manual labor.
- **Grid-positional identity (binding memory).** A tile's grid coordinate (X,Y) IS its identity.
  NO address registry, NO allocation phase. (This supersedes the older factory "address every
  entity" step — identity is position, not an allocated handle.)
- **Container model (binding memory).** The FPGA ships CONTAINED (native clocks, RAM, lanes,
  logic, IO, interconnect). We CAST the populated container, then LOAD/CONFIGURE our design
  onto it — never "place modules on an empty blank."
- **No AI-imposed design (Law #13).** Realization uses ONLY extracted facts + decompositions
  derived from documented behavior. Open design choices are flagged for the founder, not filled.
- **Gate everything (Law #12).** Nothing advances without passing `gate.sh` stages.

## Inputs — what Phase 0 (extraction) produced (DONE)

| Artifact | Content |
|---|---|
| `catalog.json` | 148 primitives + PS blocks: interface (ports/params) per primitive |
| `ds_resources.json` | authentic counts (1.14M cells, 522K LUT, 984 BRAM, 1968 DSP, 44 GTH, 28 GTY, 11 CMT…) |
| `board_net.json` | 803 board connections (external pinout) |
| `figblocks_out` / `ug576/578_figblocks` | 340 figures, ~3.7K blocks, ~940 internal connections |
| `*_richtext.json` | registers, fields, address-map, routing, sequences, DRP attributes |
| `ps_ports.json` | PS interface (DDR/GEM/DP/MIO/power + PS-PL AXI seam) |
| UG572 data | clock fabric (routing/distribution tracks, clock regions) |

---

## Phase Plan

Each phase: **goal · inputs · tool · parallelization (N instances) · gate · open decisions.**

### P1 — Primitive Library Realization (parts → C cells)
- **Goal:** every catalogued primitive → a synthesizable C model from Tier-0 atoms
  (gate/dff/latch/cfgcell/iobuf + behavioral leaves for analog/hard-IP).
- **Layers:** INTERFACE = extracted ports/params (as-is). INTERNALS = decomposition DERIVED
  from documented behavior (flip-flops are axioms; analog/PS/transceiver hard blocks = behavioral
  leaves with their documented interface). Deriving ≠ inventing.
- **Tool:** per-primitive `<prim>_logic.yaml` → `gen_module_net.py` → `<prim>.net.json` →
  `gennet.py` → `<prim>_gen.h`.
- **Parallelization:** 1 job per primitive ≈ **148 jobs**, run 30–100 concurrent; harness
  observes each job's gate result.
- **Gate:** `validate.py` (single-writer/no-overlap/no-floating) + byte-match (2e) + cells-canon (2f)
  + logic-content (2d) per primitive.
- **Open decision:** modeling depth of hard-IP/analog leaves (interface-only vs deeper).

### P2 — Container Casting (the blank, arrayed at authentic count)
- **Goal:** cast THE one blank container — tile types arrayed at grid (X,Y) by DS891 counts,
  with native clocks, RAM, IO, lanes. ONE identical blank; a blank assigns nothing.
- **Tool:** blank caster (from spec, fed as-is) + array tool (authentic counts) → grid placement
  by coordinate.
- **Parallelization:** shard the grid by SLR / clock-region / column → **~50–100 region-builder
  instances** build tile arrays in parallel; harness stitches.
- **Gate:** blank-identity (2k), clock-rule (2g).
- **Open decision:** full authentic counts (8.1M cells — heavy, proven feasible by `.bbhft` VU9P)
  vs a right-sized container for iteration speed.

### P3 — Interconnect Fabric (clock + logic + routing)
- **Goal:** the connectivity layer. CLOCK fabric = transcribe UG572 (routing/distribution tracks,
  clock regions, roots). LOGIC fabric = synthesize the INT-tile PIP crossbar from primitives
  (proven in `.bbhft`). ROUTER = `route.py`: connections → PIP config/bitstream.
- **Inputs:** UG572 clock data; `board_net` + `figblocks` + `richtext.routing` connections.
- **Parallelization:** per-clock-region + per-INT-tile router instances → **~50+ concurrent**;
  harness observes routing convergence + reroute.
- **Gate:** single-driver-per-wire, no-shorts (`validate.py` / router checks).

### P4 — PS Realization (UG1085 → PS C blocks)
- **Goal:** PS interface blocks (`ps_ports`) + registers/DRP (`richtext`) → behavioral PS leaves
  with documented interfaces; wire the PS-PL AXI seam (S_AXI_HP/HPC/ACE/ACP, M_AXI_HPM, EMIO,
  clocks, interrupts) to the PL fabric.
- **Parallelization:** 1 job per PS block (DDR/GEM/DP/USB/SATA/PS-GTR/PMU…) → **~10–20 concurrent**.
- **Gate:** module-contract (2i), build-purity (2j).
- **Open decision:** PS scope depth (full controller modeling vs seam-only).

### P5 — Configuration / Load (design onto the container)
- **Goal:** LOAD the HFT design payload (existing modules — adapter, nic, tai, dom, timeframe,
  indicators…) onto the cast container via the router (system block diagram → PIP/bitstream).
  Configure the container; do not place on an empty blank.
- **Parallelization:** per-module install/route instances.
- **Gate:** module-contract (2i), index-doctrine (2h), build-purity (2j), arithmetic (2b),
  build-sequence (2c).
- **Open decision:** which modules constitute the load payload (the design).

### P6 — Unify · Boot · Validate (one `fpga_device`)
- **Goal:** unify all layers into ONE `fpga_device` C model. POST = fabric + native clocks tick
  on power (the `.bbhft` proof, extended to ZU19EG PL+PS).
- **Gate:** full `gate.sh` (1, 2, 2b–2k, 3) + clean-room determinism rebuild.

### P7 — Higher layers (strategy / OMS / execution / signals)
- Out of current scope; sequenced after the device is realized and booting.

---

## Orchestration — the factory line at scale (30–100 parallel)

- **Conductor:** an extended `build.py`-style harness owns each phase as a **work-list**
  (primitives, tiles, regions, modules). It is the only thing that compiles/commits.
- **Workers:** N concurrent copies of the relevant tool pull from the work-list (the sharding
  pattern already proven on `richtext`/`figblocks`). Concurrency capped to machine capacity
  (30–100).
- **Observers:** agents/harness monitor each process — collect exit code + gate verdict, retry
  transient (exit 2), HALT on validation failure (exit 1), and report. No agent reads/writes
  hardware by hand.
- **Spine:** `gate.sh` runs per-artifact; the work-list only advances a phase when its artifacts
  pass. Clean-room rebuild proves determinism before graduation.

## Phase gating (no skipping)
P1 → P2 → P3 → P4 → P5 → P6. Each is a hard gate on the next. P4 (PS) can run parallel to P3
once P2 is cast, since PS and PL fabrics are independent until the P5 seam.

## Open founder decisions (flagged, not chosen — Law #13)
1. **Realization scope:** full PL+PS, or PL-first then PS?
2. **Container sizing:** authentic 8.1M-cell counts vs right-sized for iteration.
3. **Design payload (P5):** which HFT modules load onto the container.
4. **Hard-IP/analog depth (P1/P4):** interface-only behavioral leaves vs deeper internals.
