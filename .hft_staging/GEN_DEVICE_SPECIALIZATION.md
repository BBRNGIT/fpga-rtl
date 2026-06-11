# GEN_DEVICE_SPECIALIZATION.md — universal device specialization meta tool

`gen_device_specialization.py` is the single entry point for device
specialization mandated by **Architectural Law #9 (C IS the RTL)**. Device
type is a **parameter** (`--type fpga|asic|pcb|mcu`); all type-specific
knowledge lives in per-type YAML profiles. All outputs are C (or artifacts on
the path to C). It supersedes the deprecated `gen_fpga_specialization.py`
(FPGA-hardcoded) and the removed `tools/` scripts (see `tools/DEPRECATED.md`).

## The Three Modes (founder law — DISTINCT, never fused)

Build, assignment, and connection are separate concerns. Each mode reads the
previous mode's **committed** artifacts and emits its own validation report.

### 1. `build` — scaffold (NO addresses, NO placement, NO wiring)

```sh
python3 .hft_staging/gen_device_specialization.py build \
    --type fpga --name nic demo/device_fpga_nic
```

Outputs (the universal fileset pattern, same for every device type):

| File | Purpose |
|------|---------|
| `DEVICE_<TYPE>_<NAME>.md` | Blank design doc (profile reference, stage map) |
| `gen_device_<type>_<name>_net.py` | Emitter skeleton — loads the ASSIGN registry at run time; never hardcodes addresses |
| `gennet_device_<type>_<name>.py` | Netlist → C generator stub (adapter-pattern READ→COMPUTE→WRITE) |
| `build_report.txt` | Stage report (asserts no addresses/wiring emitted) |

### 2. `assign` — registry address allocation + resource assignment

```sh
python3 .hft_staging/gen_device_specialization.py assign \
    --type fpga .hft_staging/fpga_nic_modules.yaml demo/device_fpga_nic
```

Reads a module list YAML (`device_name` or legacy `fpga_name`, plus
`modules: [{name, cells, bram, io, …, clock_domain}]`). Runs the greedy
allocator (ported from the deprecated tool, parametrized from the profile):
profile alignment (e.g. 0x1000), CDC region reserved at the top of the
address space, window size derived from resource budgets (e.g. BRAM blocks ×
2304 bytes — identical math to the deprecated tool).

Outputs:
- `device_<type>_<name>_registry.json` — the **committed register map**:
  per-module address windows, clock domains, assigned resource units,
  CDC region, profile reference.
- `assign_report.txt` — validation: cross-module **no-overlap**,
  **single-writer** (one module = one writer per window; duplicates fail),
  clock domains must exist in the profile (or end in `_crossing`),
  resource usage vs. catalog capacity (integer percent — no floats).

Exit 1 on any violation.

### 3. `connect` — module-to-module wiring / seam netlist

```sh
python3 .hft_staging/gen_device_specialization.py connect \
    --type fpga demo/device_fpga_nic/device_fpga_nic_registry.json \
    demo/fpga_nic_connections.yaml demo/device_fpga_nic
```

Reads the committed registry plus a connections YAML
(`connections: [{from: mod.NODE, to: mod.NODE}]`). For every connection whose
endpoints sit in different clock domains, an explicit `gray_2ff` CDC node is
emitted and given a slot inside the reserved CDC region (min latency 2).

Outputs:
- `device_<type>_<name>.net.json` — seam netlist following
  `validate_device.py` conventions (`modules`, `cdc_nodes`,
  `cross_module_wiring`, seam registers as `dff_nodes`).
- `connect_report.txt` — validation: seam-level **single-writer** (each
  destination has exactly one source), **clock rule** (cross-domain only via
  CDC), CDC-region fit.

Then check device-agnostic laws with the repo validator:

```sh
python3 validate_device.py demo/device_fpga_nic/device_fpga_nic.net.json
```

## Device Profiles (`.hft_staging/device_profiles/<type>.yaml`)

NOTHING type-specific is hardcoded in the Python. A profile declares:

- `address_space`, `slot_alignment`, `cdc_region_size`, `module_base`
- `clock_domains:` name → `{frequency_hz (integer), source}`
- `resources:` the primitive catalog — each entry maps a module-list field
  (`maps:`) onto device primitives with `capacity`, `per_unit`, and optional
  `bytes_per_unit`/`bytes_per_cell` (drives window sizing).

| Type | Primitive catalog |
|------|-------------------|
| fpga | clb, bram, dsp, gty, io_bank |
| asic | stdcell, sram, gate |
| pcb  | package, resistor, capacitor, logic_ic |
| mcu  | core, ram, gpio, uart |

Adding a device type = adding a profile YAML. No Python changes.

Integers only throughout — frequencies in Hz, utilization in integer percent.
**No floats anywhere in emitted artifacts** (Law #5).

## Circuit-Builder Catalog (`.hft_staging/circuitlib.py`)

Emitters author with the extended catalog; the netlist and the generated C
contain **canonical cells only** (cells.h: buf/not/and/or/xor/mux/eqmask/fa/
gate/addsub/dff). Lowering is implemented as unit-testable pure functions:

| Primitive | `circuitlib.lower(kind, name, …)` | Lowers to |
|-----------|-----------------------------------|-----------|
| SR flip-flop | `sr_ff(name, s, r)` | not, and, or → dff (set-dominant) |
| JK flip-flop | `jk_ff(name, j, k)` | (J&~q)\|(~K&q) → dff |
| T flip-flop | `t_ff(name, t)` | xor(q,t) → dff |
| D latch | `d_latch(name, d, en)` | dff with enable |
| Counter | `counter(name, en)` | gate(ONE,en) → addsub → dff |
| Shift register | `shift_register(name, din, stages)` | dff chain |

Constants `ZERO`/`ONE` are config nodes declared once per device.
`circuitlib.simulate()` is a reference tick-evaluator (test instrument only)
that mirrors the generated READ→COMPUTE→WRITE phases; truth tables are
verified in `.hft_staging/test_circuitlib.py`:

```sh
python3 .hft_staging/test_circuitlib.py     # or: pytest .hft_staging/test_circuitlib.py
```

## Worked Example (FPGA NIC, reproducing the deprecated tool)

```sh
# 1. BUILD — blank fileset, no addresses
python3 .hft_staging/gen_device_specialization.py build \
    --type fpga --name nic demo/device_fpga_nic

# 2. ASSIGN — port of the old fpga_nic_modules.yaml input
python3 .hft_staging/gen_device_specialization.py assign \
    --type fpga .hft_staging/fpga_nic_modules.yaml demo/device_fpga_nic
#   adapter 0x00000000, wire 0x00001000, …, fifo_rx 0x00007000–0x0002b000
#   (fifo_rx window = 64 BRAM × 2304 B = 0x24000 — same math as the
#    deprecated gen_fpga_specialization.py), CDC reserved at 0x0ff00000.

# 3. CONNECT — seams + automatic CDC for cross-domain hops
python3 .hft_staging/gen_device_specialization.py connect \
    --type fpga demo/device_fpga_nic/device_fpga_nic_registry.json \
    demo/fpga_nic_connections.yaml demo/device_fpga_nic

# 4. VALIDATE — device-agnostic laws
python3 validate_device.py demo/device_fpga_nic/device_fpga_nic.net.json

# 5. EMIT C — designer fills in module logic via circuitlib, then:
cd demo/device_fpga_nic
python3 gen_device_fpga_nic_net.py > device_fpga_nic.net.json
python3 gennet_device_fpga_nic.py device_fpga_nic.net.json \
    > device_fpga_nic_gen.h        # C IS the RTL — the only output form
```

The same five steps run unchanged for `--type mcu` (see
`demo/mcu_ctrl_modules.yaml` / `demo/mcu_ctrl_connections.yaml`), asic, pcb.

## Dependencies

stdlib + PyYAML if available; a built-in parser handles the simple YAML
subset used by profiles and module lists when PyYAML is absent.
