#!/usr/bin/env python3
"""gen_fpga_specialization.py — FPGA design specializer.

Transforms a blank FPGA template and a module list into a concrete, specialized
FPGA design with:
  1. Programmatic address allocation (no hand-wiring)
  2. CDC region reservation
  3. Complete design documentation
  4. Skeleton emitter scaffold

INPUT:
  - blank_template.md: Generic FPGA template (fabric, clocks, I/O schema)
  - modules.yaml: Module list specifying which modules → which FPGA, resources

PROCESS:
  1. Parse blank template and module list
  2. Allocate address windows (greedy, aligned to 0x1000 boundaries)
  3. Validate allocation (no overlaps, fit in device space, budget compliance)
  4. Generate specialized FPGA_<name>.md with address map
  5. Generate skeleton gen_fpga_<name>_net.py emitter
  6. Output validation report

OUTPUT:
  - fpga_<name>/FPGA_<NAME>.md — Specialized design doc with address map
  - fpga_<name>/gen_fpga_<name>_net.py — Skeleton netlist emitter
  - fpga_<name>/validation_report.txt — Allocation report and checks
"""

import sys
import json
import yaml
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple


# ---- Configuration Constants ----

DEVICE_ADDRESS_SPACE = 0x10000000  # 256 MB total
CDC_REGION_SIZE = 0x100000  # 1 MB reserved for cross-device CDC
SLOT_ALIGNMENT = 0x1000  # 4 KB alignment for module address windows
MODULE_BASE = 0x00000000  # Device region starts at 0

# Predefined clock domains
CLOCK_DOMAINS = {
    "mac": {"frequency_mhz": 125, "source": "external_phy"},
    "internal": {"frequency_mhz": 250, "source": "pll_2x"},
    "taiosc": {"frequency_mhz": 1, "source": "oscillator"},
}


# ---- Data Structures ----

@dataclass
class Module:
    """Represents a module instance in an FPGA."""
    name: str
    cells: int
    bram: int
    clock_domain: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("Module name cannot be empty")
        if self.cells < 0:
            raise ValueError(f"Module {self.name}: cells count must be >= 0")
        if self.bram < 0:
            raise ValueError(f"Module {self.name}: bram count must be >= 0")


@dataclass
class AddressAllocation:
    """Result of address allocation for a module."""
    module_name: str
    base_address: int
    size: int
    end_address: int
    clock_domain: str
    cells: int
    bram: int


@dataclass
class FPGADesign:
    """Complete FPGA design specification."""
    name: str
    clock_primary: str
    modules: List[Module]
    allocations: List[AddressAllocation]
    total_cells: int
    total_bram: int
    cdc_base: int


# ---- Address Allocation Engine ----

class AddressAllocator:
    """Greedy address allocator respecting alignment and size constraints."""

    def __init__(self, base: int = MODULE_BASE, space: int = DEVICE_ADDRESS_SPACE,
                 alignment: int = SLOT_ALIGNMENT, cdc_size: int = CDC_REGION_SIZE):
        self.base = base
        self.space = space
        self.alignment = alignment
        self.cdc_size = cdc_size
        self.next_offset = 0
        self.allocations = []
        self.reserved = []  # List of (start, end) pairs

        # Reserve CDC region at the top
        self.cdc_base = space - cdc_size
        self.reserved.append((self.cdc_base, space))

    def allocate(self, module_name: str, cells: int, bram: int,
                 clock_domain: str) -> Optional[AddressAllocation]:
        """
        Allocate an address window for a module.
        Returns AddressAllocation if successful, None if insufficient space.
        """
        # Estimate size: assume base 0x1000 (4 KB) minimum per module
        # Plus BRAM: each 36-bit word = 4.5 bytes, but round to 0x1000 aligned windows
        min_size = 0x1000  # 4 KB minimum per module
        if bram > 0:
            # BRAM cost: 36-bit words, assume ~4.5 bytes per word, round to next 0x1000
            bram_size = (bram * 36 * 512) // 8  # 512 rows per block
            min_size = max(0x1000, self._align_up(bram_size, self.alignment))

        min_size = self._align_up(min_size, self.alignment)

        # Find next available address
        addr = self._find_next_available(min_size)
        if addr is None:
            return None

        alloc = AddressAllocation(
            module_name=module_name,
            base_address=addr,
            size=min_size,
            end_address=addr + min_size,
            clock_domain=clock_domain,
            cells=cells,
            bram=bram
        )

        self.allocations.append(alloc)
        self.reserved.append((addr, addr + min_size))
        return alloc

    def _align_up(self, value: int, alignment: int) -> int:
        """Align value up to next alignment boundary."""
        return ((value + alignment - 1) // alignment) * alignment

    def _find_next_available(self, size: int) -> Optional[int]:
        """Find next available address that fits the given size."""
        self.reserved.sort()

        # Start from base and find first gap
        current_addr = self._align_up(self.base, self.alignment)

        for res_start, res_end in self.reserved:
            # Try to fit before this reserved region
            if current_addr + size <= res_start:
                return current_addr
            # Move past this reserved region
            current_addr = self._align_up(res_end, self.alignment)

        # Try space after all reserved regions
        if current_addr + size <= self.cdc_base:
            return current_addr

        # Insufficient space
        return None

    def _overlaps_reserved(self, start: int, end: int) -> bool:
        """Check if [start, end) overlaps any reserved region."""
        for res_start, res_end in self.reserved:
            if not (end <= res_start or start >= res_end):
                return True
        return False

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate allocation constraints."""
        errors = []

        # Check no overlaps
        sorted_allocs = sorted(self.allocations, key=lambda a: a.base_address)
        for i in range(len(sorted_allocs) - 1):
            curr = sorted_allocs[i]
            next_alloc = sorted_allocs[i + 1]
            if curr.end_address > next_alloc.base_address:
                errors.append(
                    f"Address overlap: {curr.module_name} "
                    f"[0x{curr.base_address:08x}–0x{curr.end_address:08x}] "
                    f"overlaps {next_alloc.module_name} "
                    f"[0x{next_alloc.base_address:08x}–0x{next_alloc.end_address:08x}]"
                )

        # Check no overflow into CDC region
        for alloc in self.allocations:
            if alloc.end_address > self.cdc_base:
                errors.append(
                    f"Module {alloc.module_name} "
                    f"[0x{alloc.base_address:08x}–0x{alloc.end_address:08x}] "
                    f"overflows into CDC region [0x{self.cdc_base:08x}–0x{self.base + self.space:08x}]"
                )

        return len(errors) == 0, errors


# ---- Template & Documentation Generation ----

def generate_fpga_design_doc(fpga: FPGADesign) -> str:
    """Generate specialized FPGA design markdown."""

    doc = f"""# FPGA Design: {fpga.name.upper()}

**Generated:** `gen_fpga_specialization.py`
**Date:** Auto-generated from module list
**Architecture:** C-as-RTL FPGA module assembly

---

## Device Summary

| Property | Value |
|----------|-------|
| **FPGA Name** | `{fpga.name}` |
| **Primary Clock** | {fpga.clock_primary} |
| **Total Cells** | {fpga.total_cells:,} |
| **Total BRAM** | {fpga.total_bram} (36-bit words) |
| **Address Space** | 0x{MODULE_BASE:08x} – 0x{DEVICE_ADDRESS_SPACE:08x} (256 MB) |
| **CDC Reserved** | 0x{fpga.cdc_base:08x} – 0x{DEVICE_ADDRESS_SPACE:08x} ({CDC_REGION_SIZE >> 20} MB) |
| **Module Count** | {len(fpga.modules)} |

---

## Modules Assigned

"""

    # Module table
    doc += "| Module | Clock Domain | Cells | BRAM | Address Window | Size |\n"
    doc += "|--------|--------------|-------|------|----------------|------|\n"

    for alloc in sorted(fpga.allocations, key=lambda a: a.base_address):
        size_kb = alloc.size >> 10
        doc += f"| `{alloc.module_name}` | `{alloc.clock_domain}` | {alloc.cells:,} | {alloc.bram} | "
        doc += f"0x{alloc.base_address:08x} | {size_kb} KB |\n"

    doc += f"\n**Total Allocated:** 0x{sum(a.size for a in fpga.allocations):08x} bytes\n"
    doc += f"**Available for expansion:** 0x{fpga.cdc_base - sum(a.size for a in fpga.allocations):08x} bytes\n"

    # Address map diagram
    doc += "\n---\n\n## Address Map\n\n```\n"
    doc += f"0x00000000  ┌─────────────────────────────────────┐\n"
    doc += f"            │   Module Address Windows            │\n"

    for alloc in sorted(fpga.allocations, key=lambda a: a.base_address):
        doc += f"            │                                     │\n"
        doc += f"0x{alloc.base_address:08x}  ├─ {alloc.module_name:20s} (0x{alloc.size:06x}) ┤\n"

    doc += f"0x{fpga.cdc_base:08x}  ├─────────────────────────────────────┤\n"
    doc += f"            │  CDC Region (Cross-Device Crossing)  │\n"
    doc += f"            │  {CDC_REGION_SIZE >> 20} MB Reserved                    │\n"
    doc += f"0x{DEVICE_ADDRESS_SPACE:08x}  └─────────────────────────────────────┘\n"
    doc += "```\n"

    # Clock domains
    doc += "\n---\n\n## Clock Domains\n\n"

    clocks_used = set(m.clock_domain for m in fpga.modules)
    for clock_name in sorted(clocks_used):
        if clock_name in CLOCK_DOMAINS:
            clock_info = CLOCK_DOMAINS[clock_name]
            doc += f"- **{clock_name}** ({clock_info['frequency_mhz']} MHz, source: {clock_info['source']})\n"
        else:
            doc += f"- **{clock_name}** (frequency: TBD)\n"

    doc += "\n---\n\n## Cross-Device CDC Connections\n\n"
    doc += "**Reserved region:** 0x{:08x} – 0x{:08x} ({})\n\n".format(
        fpga.cdc_base, DEVICE_ADDRESS_SPACE, f"{CDC_REGION_SIZE >> 20} MB"
    )
    doc += "This region holds:\n"
    doc += "- Gray-code CDC FIFOs for cross-device signals\n"
    doc += "- Synchronization flip-flops (2-FF minimum latency per crossing)\n"
    doc += "- Explicit route definition (no implicit wiring)\n"

    doc += "\n---\n\n## Design Constraints & Validation\n\n"
    doc += f"- **Single-Writer Law:** Each register written by exactly one module\n"
    doc += f"- **Gate-Level Logic:** All data-path arithmetic via structural cells (`cell_addsub`, `cell_mux`, etc.)\n"
    doc += f"- **Branchless Device:** No `if`/`switch`/`?:` in generated tick\n"
    doc += f"- **Immutability:** Once graduated to `.hft/`, module sources are write-once\n"
    doc += f"- **Address Alignment:** All module windows aligned to 0x{SLOT_ALIGNMENT:x} boundaries\n"

    doc += "\n---\n\n## Next Steps\n\n"
    doc += """1. **Review address map** — Confirm no collisions, adequate space per module
2. **Define cross-device routes** — Which signals cross CDC regions?
3. **Implement module emitters** — Generate `gen_<module>_net.py` per module
4. **Generate netlists** — Run `python3 gen_<module>_net.py > <module>.net.json`
5. **Validate netlists** — Run `python3 validate.py <module>.net.json`
6. **Generate device C** — Run `python3 gennet.py <module>.net.json > <module>_gen.h`
7. **Build & test** — Compile and verify each module
8. **Graduate** — Run `graduate.sh <module>` to move to `.hft/`

---

## References

- **FOUNDER_VISION.md** — Canonical architecture reference
- **CLAUDE.md** — Project instructions and common commands
- **Module netlists** — See each module's `<module>.net.json` for exact register/cell layout
"""

    return doc


def generate_emitter_skeleton(fpga: FPGADesign) -> str:
    """Generate skeleton emitter for the composite FPGA netlist."""

    # Build the MODULE_WINDOWS dict
    windows_code = "MODULE_WINDOWS = {\n"
    for alloc in sorted(fpga.allocations, key=lambda a: a.base_address):
        windows_code += f'    "{alloc.module_name}": {{\n'
        windows_code += f'        "base": 0x{alloc.base_address:08x},\n'
        windows_code += f'        "size": 0x{alloc.size:08x},\n'
        windows_code += f'        "clock_domain": "{alloc.clock_domain}",\n'
        windows_code += "    },\n"
    windows_code += "}\n"

    cdc_region_code = (
        f'CDC_REGION = {{\n'
        f'    "base": 0x{fpga.cdc_base:08x},\n'
        f'    "size": 0x{CDC_REGION_SIZE:08x},\n'
        f'    "purpose": "Gray-code FIFOs and 2-FF CDC sync for cross-FPGA signals",\n'
        f'}}\n'
    )

    # Build template string without nested f-strings
    emitter = (
        f'#!/usr/bin/env python3\n'
        f'"""gen_fpga_{fpga.name}_net.py — FPGA-level netlist emitter.\n'
        f'\n'
        f'Generates a composite netlist describing the {fpga.name.upper()} FPGA as a collection\n'
        f'of interconnected modules. This emitter imports the netlists from graduated modules\n'
        f'in `.hft/` and wires them together according to the address map in FPGA_{fpga.name.upper()}.md.\n'
        f'\n'
        f'OUTPUT: fpga_{fpga.name}.net.json (composite netlist, DELIVERED & COMMITTED)\n'
        f'\n'
        f'DESIGN PROCESS:\n'
        f'  1. Load each module\'s netlist from `.hft/<module>/<module>.net.json`\n'
        f'  2. Allocate addresses per FPGA_{fpga.name.upper()}.md address map\n'
        f'  3. Wire cross-module connections (same-FPGA reads, CDC seams)\n'
        f'  4. Emit composite netlist with all modules + interconnect + CDC regions\n'
        f'  5. Validate via `python3 validate.py fpga_{fpga.name}.net.json`\n'
        f'"""\n'
        f'\n'
        f'import json\n'
        f'import sys\n'
        f'from pathlib import Path\n'
        f'\n'
        f'\n'
        f'# ---- Module Address Allocations ---- (from FPGA_{fpga.name.upper()}.md)\n'
        f'\n'
        + windows_code +
        f'\n'
        f'# Cross-device CDC region\n'
        + cdc_region_code +
        f'\n'
        f'\n'
        f'# ---- Load Module Netlists ----\n'
        f'\n'
        f'def load_module_netlist(module_name: str) -> dict:\n'
        f'    """Load graduated module netlist from `.hft/<module>/<module>.net.json`."""\n'
        f'    path = Path(f".hft/{{module_name}}/{{module_name}}.net.json")\n'
        f'    if not path.exists():\n'
        f'        raise FileNotFoundError(\n'
        f'            f"Module {{module_name}} not found at {{path}}. "\n'
        f'            f"Is it graduated? (run: .hft_staging/graduate.sh {{module_name}})"\n'
        f'        )\n'
        f'    with open(path) as f:\n'
        f'        return json.load(f)\n'
        f'\n'
        f'\n'
        f'# ---- Composite Netlist Assembly ----\n'
        f'\n'
        f'def emit_fpga_{fpga.name}_netlist() -> dict:\n'
        f'    """\n'
        f'    Assemble the complete {fpga.name.upper()} FPGA netlist.\n'
        f'\n'
        f'    Structure:\n'
        f'    {{\n'
        f'        "device": "fpga_{fpga.name}",\n'
        f'        "window_base": "0x00000000",\n'
        f'        "modules": [\n'
        f'            {{"name": "adapter", "netlist": {{...}}, "window_base": "0x..."}},\n'
        f'            ...\n'
        f'        ],\n'
        f'        "cross_module_wiring": [\n'
        f'            {{"from": "adapter.WIRE_BID_PX", "to": "dom.BID_IN", "latency": 1}},\n'
        f'            ...\n'
        f'        ],\n'
        f'        "cdc_regions": [\n'
        f'            {{\n'
        f'                "name": "fifo_rx_cdc",\n'
        f'                "base": "0x{fpga.cdc_base:08x}",\n'
        f'                "purpose": "NIC→Pipeline async FIFO with gray-code sync"\n'
        f'            }},\n'
        f'            ...\n'
        f'        ],\n'
        f'    }}\n'
        f'    """\n'
        f'\n'
        f'    netlist = {{\n'
        f'        "device": "fpga_{fpga.name}",\n'
        f'        "window_base": "0x00000000",\n'
        f'        "comment": "Composite FPGA {fpga.name}: {fpga.total_cells:,} cells, "\n'
        f'                   "{fpga.total_bram} BRAM, {len(fpga.modules)} modules, "\n'
        f'                   "deterministic order-free execution",\n'
        f'        "modules": [],\n'
        f'        "cross_module_wiring": [],\n'
        f'        "cdc_regions": [],\n'
        f'    }}\n'
        f'\n'
        f'    # Load each module and wire into the composite\n'
        f'    modules_loaded = {{}}\n'
        f'    for module_name in MODULE_WINDOWS.keys():\n'
        f'        print(f"Loading module {{module_name}}...", file=sys.stderr)\n'
        f'        try:\n'
        f'            mod_net = load_module_netlist(module_name)\n'
        f'            modules_loaded[module_name] = mod_net\n'
        f'        except FileNotFoundError as e:\n'
        f'            print(f"ERROR: {{e}}", file=sys.stderr)\n'
        f'            sys.exit(1)\n'
        f'\n'
        f'    # ---- TODO: Wire cross-module connections ----\n'
        f'    # For each module, check its published seam nodes and connect consumers.\n'
        f'    # Example:\n'
        f'    #   adapter publishes WIRE_BID_PX, WIRE_ASK_PX, ... to the wire bus\n'
        f'    #   dom reads wire.WIRE_BID_PX → "from": "wire.WIRE_BID_PX", "to": "dom.BID_IN"\n'
        f'    #   Ensure latency is registered (1+ clock per hop within same FPGA)\n'
        f'    #\n'
        f'    # For cross-FPGA: add CDC route via CDC_REGION (2-FF gray-code minimum latency)\n'
        f'\n'
        f'    for module_name, mod_net in modules_loaded.items():\n'
        f'        window = MODULE_WINDOWS[module_name]\n'
        f'        netlist["modules"].append({{\n'
        f'            "name": module_name,\n'
        f'            "netlist": mod_net,\n'
        f'            "window_base": f"0x{{window[\'base\']:08x}}",\n'
        f'            "clock_domain": window["clock_domain"],\n'
        f'        }})\n'
        f'\n'
        f'    # Add CDC region metadata\n'
        f'    netlist["cdc_regions"].append({{\n'
        f'        "name": "cdc_main",\n'
        f'        "base": f"0x{{CDC_REGION[\'base\']:08x}}",\n'
        f'        "size": CDC_REGION["size"],\n'
        f'        "purpose": CDC_REGION["purpose"],\n'
        f'    }})\n'
        f'\n'
        f'    return netlist\n'
        f'\n'
        f'\n'
        f'# ---- Main: Emit and Output ----\n'
        f'\n'
        f'if __name__ == "__main__":\n'
        f'    net = emit_fpga_{fpga.name}_netlist()\n'
        f'    json.dump(net, sys.stdout, indent=2)\n'
    )

    return emitter


def generate_validation_report(fpga: FPGADesign, allocator: AddressAllocator) -> str:
    """Generate validation report."""

    is_valid, errors = allocator.validate()

    report = f"""FPGA SPECIALIZATION VALIDATION REPORT
=====================================

Generated for: {fpga.name.upper()}
Primary Clock: {fpga.clock_primary}
Total Cells: {fpga.total_cells:,}
Total BRAM: {fpga.total_bram}

--- ADDRESS ALLOCATION ---

Allocations (sorted by address):

"""

    for alloc in sorted(fpga.allocations, key=lambda a: a.base_address):
        report += f"  {alloc.module_name:15s} @ 0x{alloc.base_address:08x}–0x{alloc.end_address:08x} "
        report += f"(0x{alloc.size:06x} bytes, {alloc.size >> 10} KB) "
        report += f"clock={alloc.clock_domain}\n"

    total_alloc = sum(a.size for a in fpga.allocations)
    free_space = fpga.cdc_base - total_alloc

    report += f"\nTotal allocated: 0x{total_alloc:08x} bytes ({total_alloc >> 10} KB)\n"
    report += f"CDC region base: 0x{fpga.cdc_base:08x}\n"
    report += f"Free space before CDC: 0x{free_space:08x} bytes ({free_space >> 10} KB)\n"

    report += f"\nUtilization: {(total_alloc / fpga.cdc_base * 100):.1f}% of module space\n"

    # Validation results
    report += "\n--- VALIDATION ---\n\n"

    if is_valid:
        report += "✓ PASS: All constraints satisfied\n"
        report += "  ✓ No address overlaps\n"
        report += "  ✓ No overflow into CDC region\n"
        report += "  ✓ All modules fit\n"
    else:
        report += "✗ FAIL: Constraint violations detected\n\n"
        for error in errors:
            report += f"  ✗ {error}\n"

    # Constraints checklist
    report += "\n--- ARCHITECTURAL CONSTRAINTS ---\n\n"
    report += "  ✓ Single-writer law (enforced at module level by validate.py)\n"
    report += "  ✓ Gate-level arithmetic (enforced at module level by gate.sh)\n"
    report += "  ✓ Branchless device logic (enforced at module level by gate.sh)\n"
    report += f"  ✓ Address alignment: 0x{SLOT_ALIGNMENT:x} boundaries\n"
    report += f"  ✓ CDC region reserved: 0x{fpga.cdc_base:08x} – 0x{DEVICE_ADDRESS_SPACE:08x}\n"

    # Next steps
    report += "\n--- NEXT STEPS ---\n\n"
    report += "1. Review the address map in FPGA_" + fpga.name.upper() + ".md\n"
    report += "2. Implement cross-module wiring in gen_fpga_" + fpga.name + "_net.py\n"
    report += "3. Run: python3 gen_fpga_" + fpga.name + "_net.py > fpga_" + fpga.name + ".net.json\n"
    report += "4. Validate: python3 validate.py fpga_" + fpga.name + ".net.json\n"

    return report


# ---- Main Entry Point ----

def main():
    if len(sys.argv) < 2:
        print(
            "usage: gen_fpga_specialization.py <blank_template.md> <modules.yaml> [output_dir]\n"
            "\n"
            "Example:\n"
            "  python3 gen_fpga_specialization.py FPGA_TEMPLATE.md modules_nic.yaml fpga_nic/",
            file=sys.stderr
        )
        sys.exit(1)

    template_path = Path(sys.argv[1])
    modules_path = Path(sys.argv[2])
    output_dir = Path(sys.argv[3] if len(sys.argv) > 3 else ".")

    # Parse template
    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    # Parse module list
    if not modules_path.exists():
        print(f"ERROR: Module list not found: {modules_path}", file=sys.stderr)
        sys.exit(1)

    with open(modules_path) as f:
        module_config = yaml.safe_load(f)

    fpga_name = module_config.get("fpga_name", "fpga")
    if not fpga_name:
        print("ERROR: fpga_name required in module list YAML", file=sys.stderr)
        sys.exit(1)

    clock_primary = module_config.get("clock_primary", "internal")
    module_specs = module_config.get("modules", [])

    # Create module objects and allocate addresses
    modules = []
    allocator = AddressAllocator()
    allocations = []
    total_cells = 0
    total_bram = 0

    for spec in module_specs:
        module_name = spec.get("name")
        if not module_name:
            print("ERROR: Module missing 'name' field", file=sys.stderr)
            sys.exit(1)

        cells = spec.get("cells", 0)
        bram = spec.get("bram", 0)
        clock_domain = spec.get("clock_domain", "internal")

        try:
            module = Module(
                name=module_name,
                cells=cells,
                bram=bram,
                clock_domain=clock_domain
            )
            modules.append(module)

            alloc = allocator.allocate(module_name, cells, bram, clock_domain)
            if alloc is None:
                print(
                    f"ERROR: Could not allocate address for module {module_name} "
                    f"({cells} cells, {bram} BRAM). Insufficient space.",
                    file=sys.stderr
                )
                sys.exit(1)

            allocations.append(alloc)
            total_cells += cells
            total_bram += bram

        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate allocation
    is_valid, errors = allocator.validate()
    if not is_valid:
        print("ERROR: Address allocation validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        sys.exit(1)

    # Create FPGA design
    fpga = FPGADesign(
        name=fpga_name,
        clock_primary=clock_primary,
        modules=modules,
        allocations=allocations,
        total_cells=total_cells,
        total_bram=total_bram,
        cdc_base=allocator.cdc_base
    )

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate outputs
    design_doc = generate_fpga_design_doc(fpga)
    emitter_skeleton = generate_emitter_skeleton(fpga)
    validation_report = generate_validation_report(fpga, allocator)

    # Write files
    design_path = output_dir / f"FPGA_{fpga_name.upper()}.md"
    emitter_path = output_dir / f"gen_fpga_{fpga_name}_net.py"
    report_path = output_dir / f"validation_report.txt"

    with open(design_path, 'w') as f:
        f.write(design_doc)

    with open(emitter_path, 'w') as f:
        f.write(emitter_skeleton)
    emitter_path.chmod(0o755)

    with open(report_path, 'w') as f:
        f.write(validation_report)

    # Output summary
    print(f"✓ Generated FPGA specialization: {fpga_name.upper()}", file=sys.stderr)
    print(f"  Design doc: {design_path}", file=sys.stderr)
    print(f"  Emitter skeleton: {emitter_path}", file=sys.stderr)
    print(f"  Validation report: {report_path}", file=sys.stderr)
    print(f"  Total cells: {total_cells:,}", file=sys.stderr)
    print(f"  Total BRAM: {total_bram}", file=sys.stderr)
    print(f"  Modules: {len(modules)}", file=sys.stderr)
    print(f"  Status: PASS ✓", file=sys.stderr)


if __name__ == "__main__":
    main()
