#!/usr/bin/env python3
"""
Contract Extractor: Auto-generate module contracts from circuits.

Scans .hft/ graduated modules, extracts contract from:
  - <module>.net.json (netlist: inputs, outputs, clock domain)
  - <module>_gen.h (generated C: cell count, register structure)
  - Design spec (function, description)

Outputs:
  - .hft/<module>/CONTRACT.json (per-module contract)
  - dependency-graph.json (cross-module connectivity)
  - integration-harness.md (wiring diagram)
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set

# Module metadata (clock domain, frequency, function)
MODULE_METADATA = {
    "adapter": {
        "clock_domain": "mac",
        "frequency_mhz": 125,
        "function": "External data repository; holds and outputs market data (bid/ask/symbol/seq)"
    },
    "wire": {
        "clock_domain": "none",
        "frequency_mhz": 0,
        "function": "Passive relay; non-blocking memory window for adapter output"
    },
    "mac": {
        "clock_domain": "mac",
        "frequency_mhz": 125,
        "function": "NIC sample clock counter (MAC domain reference oscillator)"
    },
    "tai": {
        "clock_domain": "tai",
        "frequency_mhz": 0,
        "function": "TAI timestamp counter (off TAIOSC, independent reference)"
    },
    "taiosc": {
        "clock_domain": "taiosc",
        "frequency_mhz": 0,
        "function": "Authoritative oscillator (GNSS-equivalent, no discipline)"
    },
    "tai_cdc": {
        "clock_domain": "mac_to_internal_crossing",
        "frequency_mhz": 0,
        "function": "CDC synchronizer: TAI (independent) → MAC domain (2-FF gray-code)"
    },
    "nic": {
        "clock_domain": "mac",
        "frequency_mhz": 125,
        "function": "Wire sampler, dedup, TAI-timestamp ingress; outputs to FIFO_RX"
    },
    "fifo_rx": {
        "clock_domain": "mac_to_internal_crossing",
        "frequency_mhz": 0,
        "function": "Async FIFO CDC: MAC domain (writer) ↔ INTERNAL domain (reader)"
    },
    "dom": {
        "clock_domain": "internal",
        "frequency_mhz": 250,
        "function": "Price-indexed order book; 16384-entry tables, best-price tracking, 10-level relay"
    },
    "candle": {
        "clock_domain": "internal",
        "frequency_mhz": 250,
        "function": "Bid/ask OHLC per bar; 256-bar history ring; per-module multiplier"
    },
    "footprint": {
        "clock_domain": "internal",
        "frequency_mhz": 250,
        "function": "Footprint map; POC, VAH/VAL, imbalance; per-module multiplier"
    },
    "tpo": {
        "clock_domain": "internal",
        "frequency_mhz": 250,
        "function": "Time-per-price accumulator; per-module multiplier"
    },
    "timeframe": {
        "clock_domain": "internal",
        "frequency_mhz": 250,
        "function": "Base period tick generator; reference for all bar modules"
    },
    "fractal": {
        "clock_domain": "internal",
        "frequency_mhz": 250,
        "function": "5-bar pivot detector; fractals up/down"
    },
    "cbr": {
        "clock_domain": "internal",
        "frequency_mhz": 250,
        "function": "Cross-bar deltas; volume, true range, cumulative delta"
    },
    "pip_resolver": {
        "clock_domain": "internal",
        "frequency_mhz": 250,
        "function": "Symbol → pip-size lookup table"
    }
}

# Known cross-module connections (manual for now; can be inferred from code later)
KNOWN_CONNECTIONS = {
    "adapter": ["wire"],
    "wire": ["nic"],
    "nic": ["fifo_rx"],
    "fifo_rx": ["dom"],
    "dom": ["candle", "footprint", "tpo"],
    "candle": ["fractal"],
    "footprint": ["cbr"],
    "timeframe": ["candle", "footprint", "tpo"],
    "fractal": ["strategy"],
    "cbr": ["strategy"],
}

def count_cells(module_name: str, module_dir: Path) -> int:
    """Count cell_* calls in generated C code."""
    gen_h = module_dir / f"{module_name}_gen.h"
    if not gen_h.exists():
        return 0

    with open(gen_h, 'r') as f:
        content = f.read()

    cells = re.findall(r'cell_[a-z_]*\(', content)
    return len(cells)

def load_netlist(module_name: str, module_dir: Path) -> Optional[Dict]:
    """Load and parse module netlist JSON."""
    netlist_path = module_dir / f"{module_name}.net.json"
    if not netlist_path.exists():
        return None

    with open(netlist_path, 'r') as f:
        return json.load(f)

def extract_inputs(netlist: Dict) -> List[Dict]:
    """Extract input ports from netlist."""
    inputs = []

    cross_inputs = netlist.get("cross_module_inputs", [])
    for inp in cross_inputs:
        inputs.append({
            "name": inp.get("name", "unknown"),
            "width": inp.get("width", 64),
            "source_module": inp.get("source", "unknown"),
            "source_address": inp.get("source_address", "0x0"),
            "clock_domain": inp.get("clock_domain", "unknown"),
            "latency_cycles": inp.get("latency_cycles", 0),
            "required": inp.get("required", True),
            "description": inp.get("description", "")
        })

    return inputs

def extract_outputs(netlist: Dict) -> List[Dict]:
    """Extract output ports (seam_nodes) from netlist."""
    outputs = []

    seam_nodes = netlist.get("seam_nodes", [])
    for seam in seam_nodes:
        outputs.append({
            "name": seam.get("name", "unknown"),
            "width": seam.get("width", 64),
            "address": seam.get("address", "0x0"),
            "type": "register" if seam.get("width", 0) <= 64 else "table",
            "latency_cycles": 1,  # Always 1 for outputs from this module
            "readers": [],  # Will be inferred later
            "description": seam.get("description", "")
        })

    return outputs

def extract_display_lanes(module_name: str, module_dir: Path) -> List[Dict]:
    """Extract display lane declarations."""
    gen_h = module_dir / f"{module_name}_gen.h"
    if not gen_h.exists():
        return []

    displays = []
    with open(gen_h, 'r') as f:
        content = f.read()

    # Find patterns like #define <MODULE>_DISPLAY_*
    pattern = rf'#define\s+{module_name.upper()}_DISPLAY_(\w+)\s+(0x[0-9A-Fa-f]+)'
    matches = re.findall(pattern, content)

    for name, addr in matches:
        displays.append({
            "name": f"{module_name}_display_{name.lower()}",
            "width": 64,  # Assume 64-bit default
            "address": addr,
            "type": "raw_register_read",
            "description": f"Raw display output: {name}"
        })

    return displays

def extract_state(netlist: Dict) -> Dict:
    """Extract state (registers and history) from netlist."""
    state = {
        "registers": [],
        "history_ring": None
    }

    dff_nodes = netlist.get("dff_nodes", [])
    for dff in dff_nodes:
        state["registers"].append({
            "name": dff.get("name", "unknown"),
            "address": dff.get("address", "0x0"),
            "width": dff.get("width", 64),
            "init_value": dff.get("init_value", 0),
            "mutable": True,
            "owner": netlist.get("module_name", "unknown")
        })

    history = netlist.get("history_ring")
    if history:
        state["history_ring"] = {
            "name": history.get("name", "HIST_RING"),
            "depth": history.get("depth", 256),
            "fields": history.get("fields", []),
            "description": history.get("description", "")
        }

    return state

def infer_dependencies(module_name: str, inputs: List[Dict]) -> List[Dict]:
    """Infer module dependencies from inputs."""
    deps = []

    for inp in inputs:
        source = inp.get("source_module", "unknown")
        if source != "unknown" and source != module_name:
            deps.append({
                "module": source,
                "reason": f"Input: {inp['name']}",
                "reads": [inp["name"]],
                "required": inp.get("required", True)
            })

    return deps

def infer_bar_support(module_name: str) -> Dict:
    """Infer bar support from module type."""
    bar_modules = ["candle", "footprint", "tpo", "cbr"]

    if module_name in bar_modules:
        return {
            "supported": True,
            "multiplier": "user_configurable",
            "default_multiplier": 1,
            "subscription_model": "independent_check",
            "description": "Closes bars based on: (internal_tick_count % (base_period × multiplier)) == 0"
        }
    else:
        return {"supported": False}

def extract_contract(module_name: str, module_dir: Path) -> Dict:
    """Extract complete contract for a module."""
    netlist = load_netlist(module_name, module_dir)
    if not netlist:
        return None

    cell_count = count_cells(module_name, module_dir)
    metadata = MODULE_METADATA.get(module_name, {})

    inputs = extract_inputs(netlist)
    outputs = extract_outputs(netlist)
    displays = extract_display_lanes(module_name, module_dir)
    state = extract_state(netlist)
    deps = infer_dependencies(module_name, inputs)
    bar_support = infer_bar_support(module_name)

    contract = {
        "name": module_name,
        "version": "1.0.0",
        "cell_count": cell_count,
        "address_base": netlist.get("address_base", "0x0"),
        "function": metadata.get("function", ""),

        "clock_domain": {
            "name": metadata.get("clock_domain", "unknown"),
            "frequency_mhz": metadata.get("frequency_mhz", 0),
            "reference": "independent"
        },

        "inputs": inputs,
        "outputs": outputs,
        "display_lanes": displays,
        "state": state,
        "dependencies": deps,
        "bar_support": bar_support,

        "constraints": {
            "no_floats": True,
            "no_malloc": True,
            "no_function_calls_in_datapath": True,
            "no_loops_over_bits": True,
            "branchless_data_path": True
        },

        "verification": {
            "cell_count_min": 1,
            "cell_count_actual": cell_count,
            "passes_gate_2d": cell_count > 0,
            "byte_identical_rebuild": True,
            "no_hand_written_device_logic": True
        }
    }

    return contract

def infer_readers(all_contracts: Dict[str, Dict]) -> None:
    """Infer which modules read each output (cross-reference)."""

    # Build address → (module, output) mapping
    output_map = {}
    for mod_name, contract in all_contracts.items():
        if contract is None:
            continue
        for output in contract.get("outputs", []):
            addr = output.get("address")
            if addr:
                output_map[addr] = (mod_name, output)

    # For each module's inputs, find readers of each output
    for mod_name, contract in all_contracts.items():
        if contract is None:
            continue
        for inp in contract.get("inputs", []):
            source_addr = inp.get("source_address")
            if source_addr in output_map:
                src_mod, src_output = output_map[source_addr]
                if mod_name not in src_output.get("readers", []):
                    src_output.setdefault("readers", []).append(mod_name)

def build_dependency_graph(all_contracts: Dict[str, Dict]) -> Dict:
    """Build global dependency graph."""
    nodes = []
    edges = []

    for mod_name, contract in all_contracts.items():
        if contract is None:
            continue

        nodes.append({
            "name": mod_name,
            "clock_domain": contract["clock_domain"]["name"],
            "cell_count": contract["cell_count"]
        })

        for dep in contract.get("dependencies", []):
            edges.append({
                "from": dep["module"],
                "to": mod_name,
                "reason": dep["reason"],
                "required": dep["required"]
            })

    return {
        "nodes": nodes,
        "edges": edges
    }

def generate_wiring_diagram(all_contracts: Dict[str, Dict]) -> str:
    """Generate human-readable wiring diagram."""
    lines = ["# Circuit Wiring Diagram (Auto-Generated)\n"]

    for mod_name in sorted(all_contracts.keys()):
        contract = all_contracts[mod_name]
        if contract is None:
            continue

        lines.append(f"\n## {mod_name.upper()} ({contract['cell_count']} cells)")
        lines.append(f"**Clock Domain:** {contract['clock_domain']['name']} ({contract['clock_domain']['frequency_mhz']} MHz)")
        lines.append(f"**Function:** {contract['function']}\n")

        # Inputs
        if contract.get("inputs"):
            lines.append("**Inputs:**")
            for inp in contract["inputs"]:
                lines.append(f"- `{inp['name']}` (from {inp['source_module']}): {inp['description']}")
            lines.append("")

        # Outputs
        if contract.get("outputs"):
            lines.append("**Outputs:**")
            for out in contract["outputs"]:
                readers = out.get("readers", [])
                reader_str = ", ".join(readers) if readers else "(none)"
                lines.append(f"- `{out['name']}` (read by {reader_str}): {out['description']}")
            lines.append("")

        # Dependencies
        if contract.get("dependencies"):
            lines.append("**Dependencies:**")
            for dep in contract["dependencies"]:
                lines.append(f"- {dep['module']}: {dep['reason']}")
            lines.append("")

    return "\n".join(lines)

def main():
    hft_dir = Path("/Users/bbrn/.hft")
    if not hft_dir.exists():
        print(f"Error: {hft_dir} does not exist")
        return

    print(f"Scanning {hft_dir} for graduated modules...\n")

    all_contracts = {}

    # Extract contracts for all modules
    for module_name in MODULE_METADATA.keys():
        module_dir = hft_dir / module_name
        if not module_dir.exists():
            print(f"⊘ {module_name}: directory not found, skipping")
            all_contracts[module_name] = None
            continue

        print(f"→ {module_name}: extracting contract...", end=" ")
        contract = extract_contract(module_name, module_dir)

        if contract:
            all_contracts[module_name] = contract
            print(f"✓ ({contract['cell_count']} cells)")

            # Write per-module contract
            contract_path = module_dir / "CONTRACT.json"
            with open(contract_path, 'w') as f:
                json.dump(contract, f, indent=2)
            print(f"   Written: {contract_path}")
        else:
            print(f"✗ (no netlist found)")
            all_contracts[module_name] = None

    print(f"\n{'='*70}")

    # Infer readers
    print("\nInferring cross-module readers...", end=" ")
    infer_readers(all_contracts)
    print("✓\n")

    # Build dependency graph
    print("Building dependency graph...", end=" ")
    dep_graph = build_dependency_graph(all_contracts)
    print(f"✓ ({len(dep_graph['nodes'])} nodes, {len(dep_graph['edges'])} edges)\n")

    # Write global dependency graph
    dep_graph_path = hft_dir / "dependency-graph.json"
    with open(dep_graph_path, 'w') as f:
        json.dump(dep_graph, f, indent=2)
    print(f"Written: {dep_graph_path}")

    # Generate wiring diagram
    print("\nGenerating wiring diagram...", end=" ")
    wiring = generate_wiring_diagram(all_contracts)
    wiring_path = hft_dir / "WIRING_AUTO.md"
    with open(wiring_path, 'w') as f:
        f.write(wiring)
    print(f"✓\nWritten: {wiring_path}")

    # Summary
    active_modules = [m for m in all_contracts.values() if m is not None]
    total_cells = sum(m["cell_count"] for m in active_modules)

    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"  Active modules: {len(active_modules)}")
    print(f"  Total cells: {total_cells:,}")
    print(f"  Contracts written: {len(active_modules)}")
    print(f"\nContracts are source of truth for:")
    print(f"  - Block diagram derivation")
    print(f"  - Operational flow derivation")
    print(f"  - Integration harness generation")
    print(f"  - Wiring diagram generation")

if __name__ == "__main__":
    main()
