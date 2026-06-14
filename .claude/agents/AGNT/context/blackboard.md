# FPGA-RTL Project Context (Re-grounded 2026-06-14)

> Authoritative sources (read these directly, do not trust summaries): `CLAUDE.md`,
> `engr.md`, `v3_staging/V3_REALIZATION_ROADMAP.md`, and the binding memories under
> `~/.claude/projects/-Users-bbrn-fpga-rtl/memory/` (indexed by its `MEMORY.md`).
> This file is a working summary of those; if it conflicts with them, THEY win.

## Project Identity
- **Name:** FPGA-RTL — a **C-as-RTL hardware design framework**.
- **Active work:** ground-up **v3** transcription of the **Xilinx XCZU19EG** (Zynq
  UltraScale+ MPSoC) into a complete **C model of the device**, driven by tools that
  read the vendor PDFs. C IS the silicon.
- **Active tree:** `v3_staging/`. `archive/` holds v1/v2 (legacy `.hft`/`.bbhft`,
  `gate.sh`/`graduate.sh` vault) — historical reference ONLY, do not revive.

## CRITICAL — what this is NOT (correcting prior stale assumptions)
- **NO Vivado / Vitis / Quartus. NO synthesis step.** The C model is the silicon — there
  is no "C-to-RTL compilation" and no bitstream-via-vendor-tool. (Bitstream here means the
  router's PIP config produced by our own `route.py`, not a Vivado bitstream.)
- **NO Verilog / SystemVerilog / VHDL / TCL / schematics / firmware images are ever
  emitted.** Verilog instantiation templates in the vendor docs are *read* as a
  machine-readable port/param source, never written out.
- The toolchain is **Python tools** that parse cached doc extracts and emit **C** (plus the
  spec/netlist that emit C). Build/validate is `realize.py` + `netc.py` + clean-room
  rebuild — NOT a hardware-vendor flow.

## Immutable laws (binding — violations are REJECTED, not warnings)
1. **C IS the RTL.** Every output is C, or the spec/netlist that emits C. Never emit HDL.
2. **Tools build hardware, not hands.** Deliverables are emitters / specs / generators /
   harnesses. NEVER hand-write a device tick, `cell_*()` composition, `*_gen.h`, netlist,
   `.net.json`, or catalogue output. Both `.net.json` and `*_gen.h` are TOOL OUTPUTS,
   committed as validation artifacts. If a gate fails, fix the TOOL, never the artifact.
3. **Branchless gate-level datapath.** No `if`/`?:`/`switch`/`for`/`while` in a generated
   tick. Arithmetic is structural cells only (`cell_addsub`/`cell_mux`/`cell_cmp_*`/
   `cell_sar`) — never native `+`/`-`/`*`. No floats, heap, or function pointers; every
   value reads from a register. Conditionals live ONLY in ingress buffers, offline prep, or
   external display/probe. (Uniform array replication of identical fabric tiles is
   structural arraying, not a data branch — needs an explicit fabric-container exemption
   declared in `enforcement_registry.yaml`, never inline.)
4. **Single-writer + grid-positional identity.** A module writes only its own registers;
   consumers only read. FPGA internals are tiled in a grid — the grid coordinate (X,Y) IS
   the identity. NO address registry, NO allocation phase, NO stored address handles.
5. **Index Doctrine.** One quantum = internal clock tick. Time = bounded tick-counts;
   price = a direct pip-index within a frame, never absolute/stored.
6. **Physical-primitive LAYERED model (UG574-grounded).** Do NOT gate-decompose UNISIM
   config-variants. `FDRE/FDSE/FDCE/FDPE` are ONE configurable storage element. Three
   layers: physical fabric elements (counted by DS891) ← config space (INIT/IS_*_INVERTED)
   ← UNISIM catalogue (configured uses). P1 = a small physical primitive set + config
   model, NOT 148 gate netlists.
7. **No AI-imposed design.** Specs match the real hardware doc EXACTLY. NEVER invent ports,
   connections, counts, fields, clock tables, or "defaults." DERIVING a decomposition from
   documented behavior is legitimate; FABRICATING a fact is not. **Missing info ⇒ STOP AND
   ASK, never fill.** (Past violation cost ~10 hours.)
8. **Parallel tool copies; agents OBSERVE.** Scale by sharding work across many concurrent
   copies of our tools; the harness runs/observes them. "Agents" = parallel tool processes,
   NOT manual labor. Proceed decisively, report as statements — no optional A/B vibe
   questions; reserve questions for missing facts (Law #7) or hard-to-reverse founder-only
   decisions.
9. **FPGA is a CONTAINER — load, don't place.** The device ships CONTAINED (native clocks,
   RAM, lanes, logic, IO, interconnect). We CAST the populated container, then LOAD/CONFIGURE
   our design onto it. Binding verbs: load / configure. Never "place modules on an empty blank."

## The pipeline: extract once → parse → realize
- **Extraction is one-time and committed.** `v3_staging/tools/cache/*.jsonl` (11 docs,
  one JSON per page: text, tables, Verilog regions, vector shapes) is the canonical parse
  input and is checked into git. `extract.py` is idempotent (`--force` to re-extract).
  **Source PDFs are NOT committed** — re-acquire via `fetch_docs.sh` only to re-extract or
  run `figblocks`. **Do not re-extract — the cache is the source of truth.**
- Parse stage: `catalog.py` → catalog.json (149 primitives, layered); `richtext.py` →
  registers/fields/DRP/routing (sharded); `psports.py` (UG1085 PS blocks); `txports.py`
  (UG576/578 transceivers); `figparse.py`/`figblocks.py` → figure connectivity. Joins:
  `board_net.json` (Z19) + `ds_resources.json` (DS891).
- `hierarchy.py --materialize` → hierarchy.json + hierarchy.html + device_tree/ — the
  hierarchical netlist, the pre-build proof of correctness.
- v3 library pipeline (realized primitives): `<prim>_logic.yaml` → `gen_module_net.py` →
  `<prim>.net.json` → `gennet.py` → `<prim>_gen.h` (C); then `assemble.py` → `library.json`
  → `netc.py` (validate + render → `device.json`, `explorer.html`).

## Realization phases — CURRENT STATUS (measured from disk by `realize.py status`)
`V3_REALIZATION_ROADMAP.md` is canonical; `realize.py` is its executable form. Phases gate
strictly in order P1→P2→P3→P4→P5→P6 (P4 may run parallel to P3 once P2 is cast).

- **P1 Primitive Library (layered) — ACTIVE, 130/141.** 98 physical elements realized
  (configmap) + 22 blocks in `library.json`. Physical elements (CLB storage element, LUT6,
  CARRY8, MUXF7/8/9, BRAM, DSP48E2, IO buffer, routing PIP) + config model mapping the 149
  catalogue entries onto configurations. Authority docs cached: UG574 (CLB), UG573 (memory),
  UG579 (DSP), UG570 (config). Open: modeling depth of hard-IP/analog leaves.
- **P2 Container Casting — DONE, 1/1.** Blank cast: 98 types, **2,126,341 instances**,
  compiles + passes power-on POST. ONE identical blank; native clocks/RAM/IO/lanes; grid
  (X,Y) placement. (Founder: full authentic counts ~8.1M cells is the target sizing;
  monolithic-file risk handled by Scale Architecture — code is O(tile TYPES), hard per-file
  ceiling + auto-shard, separate compilation.)
- **P3 Interconnect Fabric — ACTIVE, 1/2.** INT_TILE PIP crossbar synthesized and
  netc-validated. **PENDING: the router (`route.py`)** — clock routing/distribution tracks
  (transcribe UG572) + router convergence/reroute (connections → PIP config). This is the
  current frontier of work. Inputs: UG572 tracks/regions, board_net + figblocks +
  richtext.routing. Gate: single-driver-per-wire, no-shorts.
- **P4 PS Realization (UG1085) — PENDING.** PS interface blocks (`ps_ports`) + registers/DRP
  → behavioral PS leaves; wire PS-PL AXI seam. NOTE: v3 catalogue covers **PL only**; the PS
  domain (PS_DDR/MIO/DisplayPort/USB/SATA/PS-GTR, ~378 board connections) has ZERO catalogued
  primitives. Founder decision: PL first, then PS.
- **P5 Configuration / Load — BLOCKED on P3.** LOAD the HFT design payload onto the cast
  container via the router. Open: which modules constitute the payload.
- **P6 Unify / Boot / Validate — BLOCKED on P4,P5.** Unify all layers into ONE `fpga_device`;
  POST = fabric + native clocks tick on power. Gate: full gate stages + clean-room rebuild.

## Project gate (the acceptance signal — use THIS, not generic stack gates)
- **`netc.py`** validates + renders the library → `device.json` + `explorer.html`
  (currently: "OK — 22 blocks validated + rendered").
- **`validate.py`-class checks** (per-artifact, invoked through the realize/gate spine):
  single-writer / no-overlap / no-floating, byte-match, cells-canon, logic-content,
  clock-rule, blank-identity, module-contract (gate 2i), index-doctrine (2h),
  build-purity (2j), arithmetic (2b), build-sequence (2c).
- **Clean-room determinism rebuild** proves a phase before graduation.
- There is NO semgrep / CVE / OSV / npm / lint / Docker gate here. If a generic ecosystem
  gate is proposed, it does NOT apply — use the project's own gate above. (The deploy
  `agnt.config.json` says `type: node`; that is a deploy-config artifact and is INCORRECT —
  this is a Python-tooling + C-emission hardware project, not Node.)

## Key commands (run from `v3_staging/tools/`)
```sh
python3 realize.py status          # canonical phase progress, measured from disk
python3 realize.py plan P3         # a phase's steps + gate + parallelism
python3 realize.py worklist P3     # concrete pending items
python3 build.py                   # full extraction/parse pipeline (idempotent)
python3 catalog.py                 # rebuild parts catalogue from cache
python3 netc.py                    # validate + render library -> device.json / explorer.html
python3 hierarchy.py --materialize # rebuild hierarchical netlist + device_tree/
```
**Sharding pattern** (richtext/figblocks/region builders): launch N `--pages A-B` (or
per-region) copies in the background, `wait`, then `--merge`; the harness observes the
processes. Concurrency 30–100, capped to machine capacity.

## How AGNT must work on this codebase
- **Build the generator, not the device.** Any request to "write/fix a `*_gen.h`, tick,
  netlist, or catalogue entry" means edit the TOOL that emits it, then re-run the tool. A
  passing binary with the wrong structure is a REJECTION.
- **Ground every task in the real doc before acting.** Do not invent counts/ports/fields.
  Missing fact ⇒ STOP AND ASK (Law #7).
- **Never coin vocabulary or directories absent from the docs/memories.** Use the project's
  own terms (configmap, blank, container, INT_TILE, PIP, grid (X,Y), tick, cell, pip-index).
- **Only the orchestrator compiles and commits.** Subagents cannot run `cc`/`make` or
  destructive git; they emit tools/specs and report. Commits carry the founder's identity.
- **Acceptance = the project gate** (`realize.py`/`netc.py`/validate + clean-room rebuild).
  Report COMPLETE tersely when the gate passes; raise a Scribe brief only when a genuine
  human decision is required (BLOCKED, go/no-go, or a destructive/outward-facing action).

## Pitfalls (do not repeat)
- Re-extracting PDFs — the cache is committed and `extract.py` is idempotent. Don't.
- Gate-decomposing UNISIM config-variants (Law #6) — map to physical element + config.
- Inventing facts not in the docs (Law #7) — pull the doc or STOP.
- Hand-writing hardware artifacts (Law #2) — extend the emitter instead.
- Assuming Vivado/Verilog/synthesis — there is none; C is the silicon.
- Bespoke per-task scripts where a tool should generalize — prefer parameterized tools + sharding.

---
Re-grounded against CLAUDE.md, engr.md, V3_REALIZATION_ROADMAP.md, `realize.py status`,
and the binding memory set. Supersedes the prior blackboard, which incorrectly described a
Vivado/Verilog synthesis flow and stale phase status.
