# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **C-as-RTL hardware design framework**. C code IS the hardware specification — not a
generator of Verilog, not a simulator, not a wrapper. The **active work** is **V4: transcribing
UNISIM cells from Verilog to C**, building an accurate, discipline-enforced parts catalog for
the **Xilinx XCZU19EG** (Zynq UltraScale+ MPSoC).

- **`v4/`** — ACTIVE. UNISIM transcription, C specification language, enforcement gates.
- **`archive/`** — v1/v2/v3: legacy toolchains. Historical reference only; do not revive.
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

## V4: Exact Digital Replicas of Real FPGA Hardware in C (binding discipline)

**READ FIRST:** `v4/HANDOFF.md` and `v4/lib/verilog.h`. These are the executable spec.

**What this is:** 

The UNISIM Verilog cell library is the **SPEC of the real Xilinx FPGA** — it describes actual
physical hardware (real gates, flip-flops, circuits). V4 creates **EXACT DIGITAL REPLICAS** of
that real hardware **IN C**. The C replicas must match the Verilog spec faithfully, or the entire
design falls apart.

C IS the hardware description language (like Verilog is for the real FPGA).

**The model:**
- Real FPGA: physical circuits, transistors, actual hardware behavior
- Verilog spec: describes that real hardware precisely
- Our C replicas: must describe the same hardware, using C primitives we build
- C primitives: exact digital replicas of real components (NAND, gates, flip-flops, etc.)

**The task is NOT interpretation or decomposition.** We are REPLICATING real hardware.

**How it works:**
1. Read the Verilog spec — understand what real hardware it describes
2. Use our C library of primitives (built as exact digital replicas of real components)
3. Describe each UNISIM cell in C, faithfully matching the Verilog spec
4. Result: C code that accurately describes the same real hardware

**Copy the Verilog text exactly** because:
- The text IS the spec of real hardware
- We cannot change it (it must match exactly or it breaks)
- Our C primitives ARE what Verilog constructs refer to (gates, storage, routing)

**Example:**
- Verilog spec: `assign Y = A & B;` → describes a real AND gate in the FPGA
- Our C: copies the text exactly; `&` is defined in our library as referring to our AND gate replica
- Result: C describes the exact same hardware as the spec

**Hard rules (violations fail — accuracy is non-negotiable):**
1. Copy the `.v` exactly — names, ports, parameters, assignments. No changes.
2. No invented signals, ports, parameters. Spec is spec.
3. Description + revisions inherited from `.v`, never rewritten.
4. Every construct uses verilog.h definitions (which refer to our C primitives).
5. C must accurately match `.v` — ports, parameters, behavior. No interpretation allowed.

**Enforcement: READ FIRST**
- CLAUDE.md (this section) — binding law
- v4/HANDOFF.md (full spec) — how to transcribe correctly
- v4/lib/verilog.h (definitions) — what each construct means

No re-explanation. Rules are locked. Accuracy is non-negotiable.

**Location:** `v4/HANDOFF.md` (full spec), `v4/lib/verilog.h` (C primitives), glbl.c (reference template).

---

## V4 Build Pipeline

**Current phase:** Transcribe UNISIM cells (249 total, GND.c reference done).

```sh
cd v4

python3 build.py
  → Gate 0: Transcribe unisim_src/verilog/src/unisims/*.v → clib/unisims/*.c
  → Gate 1: Compile each .c with cc -c (C syntax valid, verilog.h complete)
  → Gate 2: Lint spec (lint_spec.py: architectural discipline rules)
  → Gate 3: Architecture (arch_check.py: C matches .v sources)
  → Report: X pass, Y fail (all gates must pass)
```

All gates are **automatic** — no human interpretation. Violations fail the build.
See `v4/HANDOFF.md` (spec), `v4/lib/verilog.h` (definitions), `v4/tools/` (gates).

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
