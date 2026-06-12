# THE DIGITAL SILICON FACTORY — the build doctrine & phase law

This is the mental framework and the **enforceable process law** for how this system
is built. It is not optional framing — it governs the order of work and what may be
done by hand (nothing).

## The frame

Our pipeline is a **factory that manufactures silicon**. **C is the fabric** — the
substrate the hardware is made of (C IS the RTL, Law #9). The metatools are the
machines on the line. We **synthesize** unique C-based hardware, step by step,
**entirely programmatically — nothing is done by hand** (extends
`metatools-build-no-manual-coding`): not the hardware files, not addressing, not
install/de-install, not synthesis. If an operation lacks a tool, **build the tool**.

## The 3 FPGAs (the boards)

The system targets three internally-connected FPGA fabrics:

- **fpga-in** — ingress boundary.
- **fpga-main** — the core compute fabric.
- **fpga-control** — control / management.

An FPGA **blank** *is* an internally-connected fabric: its register system /
interconnect is inherent to the device. Modules do not get hand-wired into it; the
fabric already provides the connectivity. (Blank-enforcement law: a blank is pure
device reference — no module allocation, no addresses — until specialization.)

## The factory line (phase order — each phase gates the next)

1. **Manufacture parts** — build every module from its spec via the metatools
   (emitter → netlist → gennet → C), conformed to all law, gated, graduated. ✅ done
   for the foundational set.
2. **Cast the boards** — build the 3 FPGA blanks (fpga-in / fpga-main / fpga-control)
   as internally-connected fabrics, referenced to a **real FPGA part spec** (resources,
   clock domains, I/O) so the design is deterministic. Built as-is, tested, promoted.
   **Define the power harness** (programmatic on/off + start/stop for the 3 boards).
3. **Address the whole system** — the registry meta tool stamps a **unique,
   identifiable address onto EVERY addressable entity**: every module, lane, wire,
   internal flip-flop register, and memory — **and the 3 FPGAs themselves**. One
   complete registry. This is a global identity pass, granular to each flip-flop —
   **NOT** "placing modules into an FPGA."
4. **Install / de-install** — a defined **format + tool** seats a module into a board
   (binding it to its registry addresses + power/clock) and can unseat it.
   **Programmatic only — manual install/de-install is FORBIDDEN.**
5. **Synthesize** — emit the complete C model of each populated board (the realized
   silicon). System gate + clean-room.
6. **Higher layers** — strategy, OMS, execution, signals — built as modules via the
   same line, **only after everything beneath is working.**

## Why this is the design (determinism + no megacode)

Because every step is a deterministic tool operation, a new capability is: **design a
module (spec) → address it (registry tool) → install it (install tool) → synthesize** —
without writing millions of lines of hand code. The factory does the heavy lifting; the
human authors specs and the machines. Determinism comes from the FPGA (fixed fabric,
fixed clocks, real timing) + tool-produced artifacts (byte-match reproducible).

## The protected enforcement layer (hardened 2026-06-12)

The judges may not be edited by the judged. Enforcement files (`gate.sh`,
`graduate.sh`, `checks/*`, `module_contracts.yaml`, `factory_toolchain.yaml`,
`enforcement_registry.yaml`, the cells canon, the hooks) are **protected**:
modifying or deleting them requires the founder-granted override
`HFT_ALLOW_ENFORCEMENT_CHANGE=1` at commit time. Gate exemptions are granted
ONLY in `enforcement_registry.yaml` (itself protected) — never inline. Never
change an enforcement file in the same stroke as the artifacts it judges.

## Enforcement

- Phase order is a hard sequence: a phase's outputs must gate-pass before the next.
- No-manual-operation extends to ALL factory operations (build, address, install,
  synthesize) — see `metatools-build-no-manual-coding` and `silicon-factory-phases`.
- The 3 FPGAs are the canonical device set (`fpga-in`, `fpga-main`, `fpga-control`).
- **`factory_toolchain.yaml`** is the machine-readable, version-controlled contract for
  every phase's tools, their I/O, the formats, and build status — enforced by
  **`checks/check_factory_contracts.py`** (built tools must exist; no phase skipping;
  boards canonical). The toolchain plan lives in the codebase, not in memory.
- (Per-phase mechanical checks land as each phase's tools are built: blank-conformance,
  registry uniqueness/coverage, install-manifest validity, system synthesis gate.)
