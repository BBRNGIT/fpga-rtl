# v3 Continuation Handoff — XCZU19EG C-as-RTL

For an incoming agent. Read this, then `CLAUDE.md` + `engr.md` + `memory/MEMORY.md` (binding laws).
Honest depth labels throughout: **REAL** (faithful, usable), **SKELETON** (compiles/proves but shallow),
**PENDING** (not built). Do not trust a bare "DONE" — `realize.py` measures *existence + a gate*, not fidelity.

## 1. The mission (immutable)
Transcribe the real Xilinx part **XCZU19EG** (Zynq UltraScale+ MPSoC) into a **complete C model that
IS the hardware** — emitted entirely by TOOLS that read the vendor docs. No Verilog/TCL, no hand-written
hardware, no invented facts. "C IS the RTL." End goal: a single `fpga_device` C model you can load a
design onto and run, reviewable via a BIOS console.

## 2. Intent: v1/v2 → v3 (why the rebuild)
- **v1/v2** (`archive/.bbhft`, `archive/.hft_staging`): an HFT-trading-module system built on a **VU9P**
  FPGA model, with a `gate.sh`/`graduate.sh`/`.hft`-vault workflow. It **proved the core idea**: a VU9P
  container (8.1M cells, native clocks ticking on power) booted in C. But it tangled the *device* with
  *HFT app logic* and carried hand-written artifacts. Archived; **do not revive**.
- **v3** (`v3_staging/`): ground-up rebuild on the **correct part (XCZU19EG)**, strict **tools-only**,
  strict **extract-then-realize** separation, and a hard rule: the device is built from the docs, the
  design is a separate later payload. The VU9P "8.1M" target in some docs is **stale** — ZU19EG's
  authentic physical-element sum is ~2.1M (see `cast.py` M1 note).

## 3. What v3 has actually produced (honest)
### REAL & reusable — the blueprint
- **Extraction (one-time, committed cache):** 11 vendor docs → faithful machine-readable spec. Outputs
  (all committed): `catalog.json` (148 primitives, ports/params/group), `*_richtext.json`
  (registers/fields/DRP/sequences/routing), `figblocks_out.json` (340+ block diagrams → connectivity),
  `board_net.json` (803 board connections), `ds_resources.json` (DS891 counts), `ps_ports.json`,
  `tx_ports.json`. **Nothing invented**; gaps flagged (E3 not-in-part, PS→UG1085).
- **The proof model:** `hierarchy.json` + `device_tree/` — the whole circuit as a navigable graph +
  folder tree (device→PL/PS/Board→element→config→ports, every pin/ball + edge). The pre-build map.
- **The layered primitive model** (UG574-grounded, BINDING): physical elements ← config ← UNISIM uses.
  `FDRE/FDSE/FDCE/FDPE` = ONE configurable storage element, not 4 netlists. See
  `memory/physical-primitive-layered-model.md` + `phys.py`/`configmap.py`.

### SKELETON — compiles + POSTs, but shallow
- **P1–P6 pipeline** emits a unified `device/fpga_device_gen.h` that **compiles and runs a power-on POST**
  (reports 2.1M cells, 7 PS blocks, PIP bits, placed blocks → "DEVICE BOOTS"). It is a **structural shell**:
  - CLB primitives = **real gate-level** (storage_element/LUT6/CARRY8/MUXF, validated by `netc`).
  - Hard blocks (BRAM/DSP/transceiver/PS/most IO) = **interface-only behavioral leaves** (ports, no internals).
  - Interconnect: INT_TILE crossbar **real**; placement/router = **synthetic hash proof** (routability only).
  - The device **tick is a declared placeholder** (has a branch — violates Law #3, flagged for replacement).

### Enforcement / review (REAL)
- **Bulletproof engine:** `jobgen.py`→`jobs.json`→`runner.py` → ~82 per-minute jobs (integrity + progress)
  → `device/bulletproof.json` + `views/dashboard.html`. Measures from disk; no self-report.
- **`hooks/preguard.py`** — harness PreToolUse gate: blocks phase tools while red, blocks Verilog/
  hand-edits, self-protects, `FOUNDER_OVERRIDE=1` bypass. (NOT yet installed in `~/.claude/settings.json` —
  founder-gated; cron also not installed.)
- **BIOS** (`bios/`): boots the device, but in **bare-fabric mode** (no native clocks) and still
  **`.bbhft`-coupled**. Fix spec: `specs/PROMPT_gen_bios_v3.md`.

## 4. The toolchain (data flow)
```
PDFs --extract.py--> cache/*.jsonl (committed, FROZEN)
  cache --> catalog.py / richtext.py / figblocks.py / psports.py / txports.py / phys.py --> extracted JSON
  extracted --> hierarchy.py --> hierarchy.json + device_tree/ (proof)
  P1: phys.py + configmap.py + phys_lib.py + templates.py --> integrate.py --> device/library.json --> netc.py
  P2: cast.py --> container.json ; gen_container.py --> container_gen.h
  P3: pip_lib.py (INT_TILE/CLK_ROOT) ; route.py --> routes.json     [clkfab.py = PENDING]
  P4: ps_realize.py --> ps_realize.json
  P5: map.py --> loadmap.json
  P6: unify.py --> fpga_device_gen.h (compiles + POSTs)
  ALWAYS: realize.py status (phase truth) ; runner.py (bulletproof board)
```
`realize.py` is the canonical P1–P6 controller (roadmap as code). `V3_REALIZATION_ROADMAP.md` is the doc.

## 5. THE GAP — what's left to make it a working device (prioritized)
1. **Clock fabric — `clkfab.py` (PENDING, highest leverage).** Transcribe UG572 clock regions/tracks +
   emit native MMCM/PLL clocks so the device (and BIOS) actually *ticks on power*. Reuse
   `templates.py:divider()` (proven UG572 M/D/O counter). Also unblocks the BIOS power-on.
2. **Hard-block depth.** DSP48E2 (UG579 pre-adder/mult/ALU), BRAM (UG573), transceiver datapath, PS
   controllers — currently interface-only leaves; deepen "where documented" (Law #7: derive, don't invent).
3. **Real placement.** Replace `route.py`'s synthetic hash `coord()` with floorplan-aware placement
   (clock-region/column structure); router gate (single-driver) is already correct.
4. **Branchless final tick.** Replace the POST placeholder in `unify.py` with structural cells (Law #3).
5. **Real design payload (P5).** `map.py` currently loads a demo (the device's own block diagram). A real
   design is a founder decision (deferred to the mapping tool against the working blank).
6. **Activate enforcement** (founder): install `preguard` in settings.json + the per-minute cron.

## 6. How to continue (entry points)
- **Source of truth:** `python3 tools/realize.py status` (phases), `python3 tools/runner.py` (bulletproof board).
- **Rules first:** `CLAUDE.md`, `engr.md`, `memory/MEMORY.md`. Binding: C-is-RTL; tools-not-hands;
  layered physical-primitive model; no-AI-imposed (missing fact ⇒ STOP & ASK); grid-positional identity;
  parallel tool copies (agents observe, no manual labor); branchless tick.
- **Don't re-extract** — cache is frozen/committed (`extract.py` skips). Read committed artifacts only.
- **Keep it green** — every change must leave `runner.py` BULLETPROOF; phase tools are (or will be) gated.
- **Spec-driven handoff pattern:** `specs/PROMPT_gen_bios_v3.md` is the model for delegating a task with
  exact acceptance criteria — write one per major build.
- **Honest labels:** report depth (REAL/SKELETON/PENDING), never a bare "DONE."

## 7. Repo state warning
**~138 local commits are UNPUSHED** (`origin/master` is frozen at `c9d153c`). All v3 work is local only —
push (`git push origin master`) to make it visible/backed up. Layout: `tools/` (source), `extracted/`+
`tools/*.json` (data), `device/` (generated C/netlists), `views/` (HTML), `cache/` (frozen), `specs/` (docs).
