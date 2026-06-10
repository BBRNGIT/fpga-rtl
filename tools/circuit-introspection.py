#!/usr/bin/env python3
"""
Circuit Introspection Tool — Scan .hft/ and emit circuit topology.

Produces:
  - circuit-topology.json: all modules, addresses, I/O, cell counts
  - CIRCUIT_WIRING.md: human-readable connectivity diagram
  - PINS.md: input/output pins per module (datasheet style)
  - address-map.txt: full backplane allocation
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# Known 15 modules in .hft/
EXPECTED_MODULES = [
    "adapter", "wire", "mac", "internal", "tai", "taiosc", "tai_cdc",
    "nic", "fifo_rx", "dom", "candle", "footprint", "tpo", "fractal", "cbr", "timeframe", "pip_resolver"
]

# Module metadata (hardcoded from architecture; can be cross-ref'd with docs)
MODULE_META = {
    "adapter": {
        "function": "CSV market-data source; paces output by timestamps",
        "chip": "NIC FPGA",
        "clock_domain": "adapter (external, independent)",
        "address_base": "0x17XXXXX",  # in wire window
    },
    "wire": {
        "function": "Passive addressed-memory relay bus (price-only packets)",
        "chip": "shared",
        "clock_domain": "none (passive)",
        "address_base": "0x1700000",
    },
    "mac": {
        "function": "125 MHz reference clock domain (NIC sample/copy rate)",
        "chip": "NIC FPGA",
        "clock_domain": "mac (125 MHz)",
        "address_base": "0x1D00000",
    },
    "internal": {
        "function": "250 MHz reference clock domain (Pipeline fabric)",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x1E00000",
    },
    "tai": {
        "function": "TAI counter (plain increment off taiosc, no discipline)",
        "chip": "NIC FPGA",
        "clock_domain": "taisoc",
        "address_base": "0x1C00000",
    },
    "taiosc": {
        "function": "Authoritative time oscillator (GNSS-equivalent truth)",
        "chip": "NIC FPGA",
        "clock_domain": "taisoc (free-running)",
        "address_base": "0x1B00000",
    },
    "tai_cdc": {
        "function": "Gray-code 2-FF CDC of TAI value into MAC domain",
        "chip": "NIC FPGA",
        "clock_domain": "mac (125 MHz)",
        "address_base": "0x1F00000",
    },
    "nic": {
        "function": "Wire sampler, dedup by seq, TAI stamp, FIFO writer",
        "chip": "NIC FPGA",
        "clock_domain": "mac (125 MHz)",
        "address_base": "0x1A00000",
    },
    "fifo_rx": {
        "function": "Async CDC FIFO MAC→internal (512 slots, gray-code sync)",
        "chip": "boundary (NIC→Pipeline seam)",
        "clock_domain": "mac↔internal CDC",
        "address_base": "0x2000000",
    },
    "dom": {
        "function": "Price-indexed order book (16384-entry tables, best-price, 10-level ladder)",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x2100000",
    },
    "candle": {
        "function": "OHLC dual bid/ask (16-field history ring, volume, true-range)",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x2200000",
    },
    "footprint": {
        "function": "Order-flow imprint (POC, VAH/VAL, imbalance, CVD, stacked)",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x2300000",
    },
    "tpo": {
        "function": "Time-per-price accumulation (bid/ask split, POC, history)",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x2400000",
    },
    "fractal": {
        "function": "5-bar Bill Williams fractal detector (up/down pivots, history)",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x2450000",
    },
    "cbr": {
        "function": "Cross-bar ratio deltas (volume, true-range, footprint delta, high-water)",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x2460000",
    },
    "timeframe": {
        "function": "Bar timeframe tracking (bar-boundary detection, seam)",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x1E80000",
    },
    "pip_resolver": {
        "function": "Symbol-to-pip resolution lookup table",
        "chip": "Pipeline FPGA",
        "clock_domain": "internal (250 MHz)",
        "address_base": "0x2480000",
    },
}

def count_cells(gen_h_path):
    """Count cell_[a-z_]*( calls in a *_gen.h file."""
    if not gen_h_path.exists():
        return 0
    try:
        with open(gen_h_path, 'r') as f:
            content = f.read()
        matches = re.findall(r'cell_[a-z_]*\(', content)
        return len(matches)
    except Exception as e:
        print(f"Error reading {gen_h_path}: {e}", file=sys.stderr)
        return 0

def extract_netlist_io(netlist_path):
    """Extract inputs and outputs from a .net.json netlist."""
    if not netlist_path.exists():
        return {"inputs": [], "outputs": []}
    try:
        with open(netlist_path, 'r') as f:
            netlist = json.load(f)
        inputs = netlist.get("cross_module_inputs", [])
        outputs = netlist.get("seam_nodes", [])
        return {"inputs": inputs, "outputs": outputs}
    except Exception as e:
        print(f"Error reading {netlist_path}: {e}", file=sys.stderr)
        return {"inputs": [], "outputs": []}

def scan_modules(hft_path):
    """Scan .hft/ directory for all modules."""
    hft = Path(hft_path)
    modules = {}

    for module_name in EXPECTED_MODULES:
        module_dir = hft / module_name
        if not module_dir.exists():
            print(f"Warning: Module {module_name} not found at {module_dir}", file=sys.stderr)
            continue

        # Find *_gen.h file
        gen_h_files = list(module_dir.glob("*_gen.h"))
        gen_h = gen_h_files[0] if gen_h_files else None

        netlist = module_dir / f"{module_name}.net.json"

        cell_count = count_cells(gen_h) if gen_h else 0
        io_info = extract_netlist_io(netlist)
        meta = MODULE_META.get(module_name, {})

        modules[module_name] = {
            "name": module_name,
            "cell_count": cell_count,
            "function": meta.get("function", ""),
            "chip": meta.get("chip", "unknown"),
            "clock_domain": meta.get("clock_domain", "unknown"),
            "address_base": meta.get("address_base", ""),
            "inputs": io_info["inputs"],
            "outputs": io_info["outputs"],
            "gen_h_path": str(gen_h) if gen_h else "",
            "netlist_path": str(netlist) if netlist.exists() else "",
        }

    return modules

def generate_topology_json(modules, output_path):
    """Generate circuit-topology.json."""
    topology = {
        "timestamp": "2026-06-09",
        "module_count": len(modules),
        "modules": list(modules.values()),
        "summary": {
            "nic_fpga_modules": [m for m in modules.values() if m["chip"] == "NIC FPGA"],
            "pipeline_fpga_modules": [m for m in modules.values() if m["chip"] == "Pipeline FPGA"],
            "seam_modules": [m for m in modules.values() if "seam" in m["chip"].lower()],
            "total_cells": sum(m["cell_count"] for m in modules.values()),
        }
    }

    with open(output_path, 'w') as f:
        json.dump(topology, f, indent=2)
    print(f"✓ Generated {output_path}")

def generate_wiring_diagram(modules, output_path):
    """Generate CIRCUIT_WIRING.md."""
    lines = [
        "# Circuit Wiring Diagram\n",
        "## Module Connectivity (Producer → Seam → Consumer)\n\n",
    ]

    # Organize by chip
    nic_modules = [m for m in modules.values() if m["chip"] == "NIC FPGA"]
    pipeline_modules = [m for m in modules.values() if m["chip"] == "Pipeline FPGA"]
    boundary = [m for m in modules.values() if "boundary" in m["chip"].lower()]

    lines.append("### NIC FPGA (125 MHz)\n")
    for mod in nic_modules:
        lines.append(f"- **{mod['name']}** ({mod['cell_count']} cells)")
        lines.append(f"  - Function: {mod['function']}\n")

    lines.append("### SLR Boundary (NIC → Pipeline)\n")
    for mod in boundary:
        lines.append(f"- **{mod['name']}**")
        lines.append(f"  - Function: {mod['function']}\n")

    lines.append("### Pipeline FPGA (250 MHz)\n")
    for mod in pipeline_modules:
        lines.append(f"- **{mod['name']}** ({mod['cell_count']} cells)")
        lines.append(f"  - Function: {mod['function']}\n")

    lines.append("## Data Flow\n")
    lines.append("```\n")
    lines.append("adapter (ext) → wire (shared) → nic (MAC 125MHz)\n")
    lines.append("  ↓\n")
    lines.append("fifo_rx (CDC crossing, 512 slots, gray-code sync)\n")
    lines.append("  ↓\n")
    lines.append("dom (Pipeline 250MHz) → candle, footprint, tpo\n")
    lines.append("  ↓\n")
    lines.append("fractal (pattern), cbr (deltas), timeframe (bar sync)\n")
    lines.append("  ↓\n")
    lines.append("strategy → risk → OMS → SOR → outbound\n")
    lines.append("```\n")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"✓ Generated {output_path}")

def generate_pins_sheet(modules, output_path):
    """Generate PINS.md (datasheet-style)."""
    lines = ["# Circuit Pins & Inputs/Outputs\n\n"]

    for mod_name in sorted(modules.keys()):
        mod = modules[mod_name]
        lines.append(f"## {mod['name'].upper()} ({mod['cell_count']} cells)\n")
        lines.append(f"**Function:** {mod['function']}\n")
        lines.append(f"**Chip:** {mod['chip']} | **Clock:** {mod['clock_domain']}\n")
        lines.append(f"**Address:** {mod['address_base']}\n\n")

        if mod["inputs"]:
            lines.append("### Inputs\n")
            for inp in mod["inputs"]:
                if isinstance(inp, dict):
                    lines.append(f"- `{inp.get('name', 'unknown')}` ({inp.get('type', 'u64')})\n")
                else:
                    lines.append(f"- {inp}\n")

        if mod["outputs"]:
            lines.append("### Outputs\n")
            for out in mod["outputs"]:
                if isinstance(out, dict):
                    lines.append(f"- `{out.get('name', 'unknown')}` ({out.get('type', 'u64')})\n")
                else:
                    lines.append(f"- {out}\n")

        lines.append("\n")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"✓ Generated {output_path}")

def generate_address_map(modules, output_path):
    """Generate address-map.txt."""
    lines = ["# HFT Pipeline Backplane Address Map\n\n"]

    # Sort by address
    sorted_modules = sorted(
        modules.values(),
        key=lambda m: m["address_base"] or "0x99999999",
        reverse=True
    )

    for mod in sorted_modules:
        lines.append(f"{mod['address_base']:12s} — {mod['name']:15s} ({mod['cell_count']:4d} cells) {mod['chip']}\n")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"✓ Generated {output_path}")

def publish_to_registries(module, registries):
    """
    Publish a module's spec data to various registry files as it's scanned.
    Registries are built incrementally, one module per write.
    """
    # 1. Module Registry — all modules with metadata
    registries["modules"].append({
        "name": module["name"],
        "chip": module["chip"],
        "clock_domain": module["clock_domain"],
        "cell_count": module["cell_count"],
        "address_base": module["address_base"],
        "function": module["function"],
    })

    # 2. Address Registry — address ↔ module mapping
    if module["address_base"] and module["address_base"] != "0x17XXXXX":
        registries["addresses"].append({
            "address": module["address_base"],
            "module": module["name"],
            "cell_count": module["cell_count"],
        })

    # 3. Pins Registry — all I/O
    for inp in module["inputs"]:
        registries["pins"]["inputs"].append({
            "module": module["name"],
            "pin": inp.get("name", inp) if isinstance(inp, dict) else inp,
            "type": "input",
        })
    for out in module["outputs"]:
        registries["pins"]["outputs"].append({
            "module": module["name"],
            "pin": out.get("name", out) if isinstance(out, dict) else out,
            "type": "output",
        })

    # 4. Cell Registry — module cells
    if module["cell_count"] > 0:
        registries["cells"].append({
            "module": module["name"],
            "cell_count": module["cell_count"],
            "chip": module["chip"],
            "clock_domain": module["clock_domain"],
        })

    # 5. Chip Registry — modules by chip
    chip = module["chip"]
    if chip not in registries["by_chip"]:
        registries["by_chip"][chip] = []
    registries["by_chip"][chip].append(module["name"])

    # 6. Clock Domain Registry — modules by clock
    domain = module["clock_domain"]
    if domain not in registries["by_clock"]:
        registries["by_clock"][domain] = []
    registries["by_clock"][domain].append(module["name"])

    print(f"  ✓ {module['name']:15s} ({module['cell_count']:4d} cells) → registries")

def write_registries(registries, output_dir):
    """Write all registries to disk."""
    print("\nWriting registry files...")

    # Module Registry
    with open(output_dir / "registry-modules.json", 'w') as f:
        json.dump(registries["modules"], f, indent=2)
    print(f"  ✓ registry-modules.json ({len(registries['modules'])} entries)")

    # Address Registry
    with open(output_dir / "registry-addresses.json", 'w') as f:
        json.dump(sorted(registries["addresses"], key=lambda x: x["address"]), f, indent=2)
    print(f"  ✓ registry-addresses.json ({len(registries['addresses'])} entries)")

    # Pins Registry
    with open(output_dir / "registry-pins.json", 'w') as f:
        json.dump(registries["pins"], f, indent=2)
    print(f"  ✓ registry-pins.json ({len(registries['pins']['inputs']) + len(registries['pins']['outputs'])} total pins)")

    # Cell Registry
    with open(output_dir / "registry-cells.json", 'w') as f:
        json.dump(registries["cells"], f, indent=2)
    print(f"  ✓ registry-cells.json ({len(registries['cells'])} modules with cells)")

    # Chip Registry
    with open(output_dir / "registry-by-chip.json", 'w') as f:
        json.dump(registries["by_chip"], f, indent=2)
    print(f"  ✓ registry-by-chip.json ({len(registries['by_chip'])} chips)")

    # Clock Domain Registry
    with open(output_dir / "registry-by-clock.json", 'w') as f:
        json.dump(registries["by_clock"], f, indent=2)
    print(f"  ✓ registry-by-clock.json ({len(registries['by_clock'])} clock domains)")

def main():
    hft_path = Path("/Users/bbrn/_0_0_hft/.hft")
    output_dir = Path("/Users/bbrn/_0_0_hft")

    print(f"Scanning {hft_path}...")

    # Initialize registries
    registries = {
        "modules": [],
        "addresses": [],
        "pins": {"inputs": [], "outputs": []},
        "cells": [],
        "by_chip": {},
        "by_clock": {},
    }

    # Scan and publish each module
    print("\nPublishing modules to registries:")
    modules = {}
    hft = Path(hft_path)
    for module_name in EXPECTED_MODULES:
        module_dir = hft / module_name
        if not module_dir.exists():
            continue

        # Look for <module>_gen.h specifically (not just any *_gen.h in the dir)
        gen_h = module_dir / f"{module_name}_gen.h"
        if not gen_h.exists():
            gen_h = None
        netlist = module_dir / f"{module_name}.net.json"

        cell_count = count_cells(gen_h) if gen_h else 0
        io_info = extract_netlist_io(netlist)
        meta = MODULE_META.get(module_name, {})

        module = {
            "name": module_name,
            "cell_count": cell_count,
            "function": meta.get("function", ""),
            "chip": meta.get("chip", "unknown"),
            "clock_domain": meta.get("clock_domain", "unknown"),
            "address_base": meta.get("address_base", ""),
            "inputs": io_info["inputs"],
            "outputs": io_info["outputs"],
            "gen_h_path": str(gen_h) if gen_h else "",
            "netlist_path": str(netlist) if netlist.exists() else "",
        }

        modules[module_name] = module
        publish_to_registries(module, registries)

    print(f"\nFound {len(modules)} modules")
    total_cells = sum(m["cell_count"] for m in modules.values())
    print(f"Total cells: {total_cells}")

    # Check for stubs (0 cells)
    stubs = [m for m in modules.values() if m["cell_count"] == 0]
    if stubs:
        print(f"\nWARNING: {len(stubs)} modules with 0 cells (passive/reference):")
        for stub in stubs:
            print(f"  - {stub['name']} ({stub['function']})")

    # Write registries to disk
    write_registries(registries, output_dir)

    # Generate outputs
    print("\nGenerating topology documents...")
    generate_topology_json(modules, output_dir / "circuit-topology.json")
    generate_wiring_diagram(modules, output_dir / "CIRCUIT_WIRING.md")
    generate_pins_sheet(modules, output_dir / "PINS.md")
    generate_address_map(modules, output_dir / "address-map.txt")

    print("\n✓ Circuit introspection complete")
    print(f"\nRegistry files (real-time publication):")
    print(f"  registry-modules.json — module inventory")
    print(f"  registry-addresses.json — address ↔ module mapping")
    print(f"  registry-pins.json — all I/O pins")
    print(f"  registry-cells.json — modules with cell counts")
    print(f"  registry-by-chip.json — organization by chip")
    print(f"  registry-by-clock.json — organization by clock domain")
    print(f"\nTopology documents:")
    print(f"  circuit-topology.json — complete metadata")
    print(f"  CIRCUIT_WIRING.md — connectivity diagram")
    print(f"  PINS.md — datasheet-style pins")
    print(f"  address-map.txt — backplane allocation")

if __name__ == "__main__":
    main()
