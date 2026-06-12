---
name: Digital Silicon Factory Pipeline
description: The build is a silicon factory — C is the fabric, nothing by hand; phase order parts→boards→address-all→install→synthesize→higher-layers
type: enforcement
source: Founder doctrine 2026-06-12; .hft_staging/SILICON_FACTORY.md, memory/silicon-factory-phases.md
---

# Digital Silicon Factory Pipeline

**Core frame:** the pipeline is a **factory that manufactures silicon**; **C is the
fabric**; metatools are the machines; **nothing is done by hand.** This extends the
no-manual-coding law to ALL factory operations — build, address, install/de-install,
synthesize. If an operation lacks a tool, **build the tool, then run it.**

## The 3 FPGAs (canonical device set)

`fpga-in` (ingress boundary) · `fpga-main` (core compute) · `fpga-control`
(control/management). An FPGA **blank** is an internally-connected fabric — modules are
not hand-wired into it. A blank is built as-is (no allocation/addresses until
specialization; blank-enforcement law).

## Phase order (each gates the next — do not skip ahead)

1. **Parts** — build every module via the metatools, conformed, gated, graduated.
2. **Boards** — build the 3 FPGA blanks (real-part-referenced, deterministic); define
   the **power harness** (programmatic on/off + start/stop).
3. **Address** — the registry meta tool stamps a **unique address on EVERY entity**
   (every module, lane, wire, flip-flop register, memory, and the 3 FPGAs). One
   complete registry. This is a global identity pass — **NOT** "placing modules into an
   FPGA."
4. **Install/de-install** — a defined **format + tool** seats/unseats a module into a
   board (binds registry addresses + power/clock). **Manual install/de-install is
   FORBIDDEN.**
5. **Synthesize** — emit the complete C model of each populated board; system gate.
6. **Higher layers** — strategy, OMS, execution, signals — built as modules via the
   same line, only after everything beneath works.

## Why

Deterministic tool operations mean: **design a module (spec) → address it → install it →
synthesize** — with no millions of hand-written lines. Determinism comes from the FPGA
(fixed fabric/clocks/timing) and byte-match-reproducible tool artifacts. Relates to
[[Build vs Assignment Separation]], the Index Doctrine (Law #10), and the system contract.
