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

### P1 — Primitive Library Realization (LAYERED — physical elements, not gate-decomposed variants)
- **Goal:** realize the FPGA's **physical fabric primitive set** + a config model that maps the
  148 catalogue entries onto **configurations** of those elements. NOT 148 gate netlists.
- **The 3-layer model (binding — UG574-confirmed; see `physical-primitive-layered-model` memory):**
  1. **Physical elements** — CLB storage element (configurable FF/latch, sync/async set/reset, CE),
     LUT6/SRAM (also distributed RAM + SRL in SLICEM), CARRY8, MUXF7/8/9, BRAM, DSP48E2, IO buffer,
     routing PIP. These are what DS891 COUNTS and what P2 arrays. (`FDSE` = storage element in
     sync-set config — the doc says so verbatim.)
  2. **Config space** — INIT / IS_*_INVERTED / mode bits (cfgcell).
  3. **UNISIM catalogue** — configured USES of layer 1 (FDRE, RAM64X1S, SRL16…), not new hardware.
- **Class-dependent:** clocking/logic-glue (BUFGCTRL — 24 blocks already built) = genuine gate logic.
  CLB = physical configurable elements (UG574). Hard blocks (DSP/BRAM/transceiver/PS) = behavioral
  leaves with documented register/DRP interface (UG573/579 + richtext). Deriving ≠ inventing.
- **Authority docs (cached):** UG574 (CLB), UG573 (memory), UG579 (DSP), UG570 (config).
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

## Founder decisions (RESOLVED 2026-06-14)
1. **Scope: PL first, then PS.** P3 (PL interconnect) completes and boots before P4 (PS) folds in.
2. **Sizing: full authentic counts** (real ZU19EG, ~8.1M cells). The AI-effort/hallucination
   concern is void — the generator emits deterministically and v2 proved the machine compiles at
   scale. The real risk is MONOLITHIC FILES → handled by the Scale Architecture below.
3. **Hard-IP/analog depth: deeper where documented.** Decompose to gates wherever the docs give
   enough behavior (e.g. DRP-attribute logic); behavioral leaves ONLY where they genuinely can't
   be gates (analog PLL/VCO/charge-pump, opaque ARM cores).
4. **Design payload (P5):** still open — which HFT modules load onto the container.

## Scale Architecture — full counts without monolithic files (binding for P1/P2)

Full authentic counts do NOT mean giant files. Three rules make 8.1M cells tractable:

1. **Code is O(tile TYPES), not O(count).** A tile type (e.g. one CLB slice) is generated ONCE.
   The 8.1M is an ARRAY DIMENSION (static arrays sized from `ds_resources.json`), not 8.1M lines.
   Generated C stays small and modular BY CONSTRUCTION — bounded by the ~tens of tile types.
2. **Hard per-file ceiling + auto-shard.** The emitter splits any generated unit exceeding a
   line/byte cap into numbered region shards, each its own translation unit. NEW gate check:
   fail if any generated file exceeds the ceiling (protects against monolithic drift).
3. **Separate compilation + parallel `cc`.** Many small TUs → linked; compiled in parallel across
   the 30–100 cores. This is also why full counts compile fine (v2-proven).

**Fabric iteration vs the branchless law:** the device DATAPATH stays branchless (no data-dependent
control flow). Iterating a uniform array of *identical* fabric tiles is structural replication
(hardware arraying), not a data branch — it needs an explicit fabric-container exemption declared
in `enforcement_registry.yaml` (never inline). Flagged for P2 setup.

**Memory:** ~8.1M static cell structs live in BSS (no heap — compliant). Keep the cell struct lean;
size the footprint before P2 mass-casting and confirm RAM headroom.
