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
- `.hft_staging/gen_fpga_specialization.py` — FPGA implementation (reference)

## If You Need Device Tools

All device-specialization logic is now in `.hft_staging/gen_device_specialization.py`.

For datasheet parsing or parts extraction, integrate directly into the meta tool as embedded functions, or create a separate **spec extraction** tool that feeds the meta tool (not the other way around).

**Principle:** Parse specs → feed to meta tool → meta tool generates everything.
