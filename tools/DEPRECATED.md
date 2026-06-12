# tools/ — DEPRECATED

This directory previously contained hand-written tools for device specialization:
- `parse_datasheets.py`
- `merge_device_sources.py`
- `circuit-introspection.py`
- `contract-extractor.py`
- `generate_sample_device_specs.py`
- And associated documentation and generators/

## Why Removed

These tools violated the immutable architectural law:

> **Build-Sequence Law:** Device logic is generated, never hand-written.

The old approach had multiple hand-written scripts attempting to generate device artifacts. This created:
- Code that could drift from the specification
- Multiple sources of truth (spec → parser → merger → emitter → generator)
- Brittle, non-deterministic builds

## New Approach (Unified)

All device specialization now flows through a **single entry point:**

```bash
python3 .hft_staging/gen_device_specialization.py --type <fpga|asic|pcb|mcu> \
  <blank_spec> <modules_yaml> <output_dir>
```

This single tool:
1. Reads blank template (vendor-neutral spec)
2. Parses module list (which modules, resource requirements)
3. **Generates** (not hand-codes):
   - Specialized device doc with programmatic addresses
   - Emitter skeleton
   - Validation report

**All outputs are generated code**, not human-written stubs. This ensures:
- Single source of truth (the meta tool)
- Deterministic, reproducible builds
- Architecture enforcement at generation time

## References

- `CLAUDE.md` — Law #3 (Build-Sequence Law) and Law #9 (C IS THE RTL)
- `memory/c_is_rtl_immutable_law.md` — Why all outputs must be C and generated

## 2026-06-11 — `gen_fpga_specialization.py` Removed (Law #9 Violation)

`.hft_staging/gen_fpga_specialization.py` has been removed per founder directive.

It violated the immutable architectural law:

> **C IS THE RTL (Law #9):** Device type is a **parameter**, never hardcoded in separate per-device tools.

The tool hardcoded FPGA as the device type, which would have forced parallel `gen_asic_*`, `gen_pcb_*`, `gen_mcu_*` clones — exactly the multiple-sources-of-truth drift this directory was deprecated for.

**Successor:** `gen_device_specialization.py` — the digital-circuit-builder meta tool (forthcoming), a single entry point parametrized by device type:

```bash
python3 gen_device_specialization.py --type <fpga|asic|pcb|mcu> \
  <blank_spec> <modules_yaml> <output_dir>
```

## If You Need Device Tools

All device-specialization logic is now in `.hft_staging/gen_device_specialization.py`.

For datasheet parsing or parts extraction, integrate directly into the meta tool as embedded functions, or create a separate **spec extraction** tool that feeds the meta tool (not the other way around).

**Principle:** Parse specs → feed to meta tool → meta tool generates everything.

## 2026-06-12 — part-assigning specialization era purged (banned hardware + tools)

Removed for violating "A BLANK ASSIGNS NOTHING / meta tools must not hardcode the
device or assign parts" (factory_toolchain.yaml laws; SILICON_FACTORY.md):

- `fpga_nic/`, `fpga_pipeline/`, `fpga_design/`, `fpga_nic_modules.yaml`,
  `fpga_pipeline_modules.yaml` — differentiated/branded FPGA hardware with module
  allocation baked in (the rejected NIC/Pipeline branding; boards are identical
  instances of THE one blank).
- `gen_device_specialization.py` + `GEN_DEVICE_SPECIALIZATION.md` + type profiles
  (`device_profiles/{fpga,mcu,asic,pcb}.yaml`) — a part-ASSIGNING meta tool
  (allocation/assign/connect) with hardcoded clock-domain tables. Superseded by
  the factory line: gen_fpga_blank (construction, assigns nothing) + the phase-3
  registry toolbox (address_assigner/validator/editor/updater) + the phase-4
  install/deinstall tools — the ONLY code permitted to assign.
- Era guides `GEN_FPGA_SPECIALIZATION_*`, `FPGA_SPECIALIZATION_GUIDE.md`,
  `FPGA_TEMPLATE_STRATEGY.md` — documented the deleted tools (agent poison).

Kept: `circuitlib.py`/`test_circuitlib.py` (cell-catalog lowering — construction,
no assignment); research/decision records (FPGA_DEVICE_RESEARCH.md,
DECISION_FPGA_CPU_BACKPLANE.md, XILINX_VU9P_SPEC_EXTRACTION.md).
