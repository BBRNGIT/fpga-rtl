# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **C-as-RTL hardware design framework**. C code IS the hardware specification — not a
generator of Verilog, not a simulator, not a wrapper. The **active work** is a ground-up v3
transcription of the **Xilinx XCZU19EG** (Zynq UltraScale+ MPSoC) into a complete C model of
the device, driven entirely by tools that read the vendor docs.

- **`v3_staging/`** — ACTIVE. The v3 toolchain, extraction artifacts, and realization.
- **`archive/`** — v1/v2 (`.bbhft`, `.hft_staging`): the legacy HFT-module system + the
  `gate.sh`/`graduate.sh`/`.hft` vault workflow. Historical reference only; do not revive.
- **`engr.md`** — the operating persona + a re-read-before-acting reminder of the laws below.
- **`memory/`** (under `~/.claude/projects/.../memory/`) — binding conduct laws; `MEMORY.md` indexes them.

## Immutable laws (binding — violations are rejected)

1. **C IS the RTL.** Every output is C (or the spec/netlist that emits C). NEVER write or
   generate Verilog/SystemVerilog/VHDL/TCL/schematics/firmware. Verilog instantiation
   templates in vendor docs are *read* as a machine-readable port/param source, never emitted.
2. **Tools build hardware, not hands.** Deliverables are emitters/specs/generators/harnesses.
   Do NOT hand-write device ticks, `cell_*()` compositions, `*_gen.h`, or netlist logic. Both
   `.net.json` and `*_gen.h` are TOOL OUTPUTS, committed as validation artifacts.
3. **Branchless gate-level datapath.** No `if`/`?:`/`switch`/`for`/`while` in a generated tick.
   Arithmetic is structural cells only (`cell_addsub`/`cell_mux`/`cell_cmp_*`/`cell_sar`), never
   native `+`/`-`/`*`. Conditionals live ONLY in ingress buffers, offline prep, or external
   display/probe. No floats, no heap, no function pointers; every value reads from a register.
4. **Single-writer + grid-positional identity.** A module writes only its own registers. FPGA
   internals are tiled in a grid; the grid coordinate (X,Y) IS the identity — NO address
   registry, NO allocation phase. (`memory/grid-positional-identity-not-addressing.md`.)
5. **Index Doctrine.** One quantum = the internal clock tick. Time = bounded tick-counts; price
   = a direct pip-index within a frame, never absolute/stored. (`memory/index_doctrine_*.md`.)
6. **Physical-primitive LAYERED model (UG574-grounded).** Do NOT gate-decompose UNISIM
   config-variants. `FDRE/FDSE/FDCE/FDPE` are ONE configurable storage element. Three layers:
   **physical fabric elements** (counted by DS891) ← **config space** (INIT/IS_*_INVERTED) ←
   **UNISIM catalogue** (configured uses). (`memory/physical-primitive-layered-model.md`.)
7. **No AI-imposed design.** Specs match the real hardware doc EXACTLY. NEVER invent ports,
   connections, counts, fields, or "defaults." DERIVING a decomposition from documented behavior
   is legitimate; fabricating a FACT is not. Missing info ⇒ STOP AND ASK. (`memory/no-ai-imposed-design.md`.)
8. **Parallel tool copies; agents OBSERVE.** Scale work by sharding across many concurrent copies
   of our tools (the harness runs/observes them). "Agents" means parallel tool processes, NOT
   manual labor by multiple agents. Proceed decisively; no optional A/B vibe questions.

## The pipeline: extract once → parse → realize

**Extraction is one-time and committed.** `cache/*.jsonl` (one JSON per page: text, tables,
Verilog regions, vector shapes) is the canonical parse input for every doc and is checked in.
`extract.py` is idempotent (skips a doc whose cache exists; `--force` to re-extract). Source
PDFs are NOT committed — re-acquire with `fetch_docs.sh` only to re-extract or run `figblocks`.

```
PDF --extract--> cache/<doc>.jsonl --+-- catalog.py   -> catalog.json (parts list, layered)
                                     +-- richtext.py  -> registers/fields/DRP/routing (sharded)
                                     +-- psports.py   -> PS interface blocks (UG1085)
                                     +-- txports.py   -> transceiver ports (UG576/578)
                                     +-- figparse.py / figblocks.py -> figure connectivity
                          board_net.json (Z19) + ds_resources.json (DS891) join in
                                     |
                          hierarchy.py -> hierarchy.json + hierarchy.html + device_tree/
                                          (the hierarchical netlist; physical proof of extraction)
                                     |
                          realize.py (P1..P6) -> the device C model
```

The v3 library pipeline (for realized primitives): `templates.py` decomposition builders →
`assemble.py` → `library.json` → `netc.py` (validate/render → `device.json`).

## Realization phases (canonical, in `realize.py` — roadmap as code, not memory)

`V3_REALIZATION_ROADMAP.md` is the canonical doc; `realize.py` is its executable form and
measures progress from disk artifacts. P1 primitive library (physical elements + config-map) →
P2 container casting (tiles arrayed at DS891 counts) → P3 interconnect (clock fabric transcribed
+ logic PIP crossbar synthesized) → P4 PS (UG1085) → P5 load design → P6 unify/boot/validate.
Phases gate in order; full authentic counts; protect against monolithic files (code is O(tile
*types*), counts live in static arrays).

## Common commands

```sh
cd v3_staging/tools

python3 realize.py status              # canonical phase progress, measured from disk
python3 realize.py plan P1             # a phase's canonical steps + gate + parallelism
python3 realize.py worklist P1         # concrete pending items of a phase

python3 build.py                       # run the full extraction/parse pipeline (idempotent)
python3 extract.py ../../<doc>.pdf     # extract one doc to cache (--force to re-extract)
./fetch_docs.sh                        # re-download source PDFs from the mirror on demand

python3 catalog.py                     # rebuild the parts catalogue from the full cache
python3 richtext.py cache/<doc>.jsonl --pages A-B   # shard a doc; --merge out.json shards...
python3 figblocks.py ../../<doc>.pdf --pages A-B    # block-diagram connectivity (shard by page)
python3 hierarchy.py --materialize     # rebuild the hierarchical netlist + device_tree/ folders
```

**Sharding pattern** (used for richtext/figblocks): launch N `--pages A-B` copies in the
background, `wait`, then `--merge` (or a dict-union) — the harness observes the processes.

## Key artifacts & docs

- `v3_staging/V3_REALIZATION_ROADMAP.md` — the phased plan (P1–P6) + scale architecture.
- `v3_staging/tools/catalog.json` — 148 primitives (interface + group + source), layered.
- `v3_staging/hierarchy.json` / `hierarchy.html` / `device_tree/` — the hierarchical netlist
  (device → PL/PS/Board → physical element → config → ports) with board/figure/routing edges;
  the pre-build proof of correctness.
- `*_richtext.json`, `figblocks_out.json`, `ps_ports.json`, `tx_ports.json`, `board_net.json`,
  `ds_resources.json` — committed parse outputs (avoid re-parsing).
- `FOUNDER_VISION.md` — canonical architecture reference and design philosophy.

## Pitfalls

- Re-processing PDFs: the cache is committed and `extract.py` is idempotent — don't re-extract.
- Gate-decomposing UNISIM config-variants (Law #6) — map to a physical element + config instead.
- Inventing facts not in the docs (Law #7) — pull the authoritative doc (`fetch_docs.sh`) or STOP.
- Hand-writing hardware artifacts (Law #2) — write/extend the tool that emits them.
- Bespoke per-task scripts where a tool should generalize — prefer parameterized tools + sharding.
