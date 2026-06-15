#!/usr/bin/env python3
"""
trm_doc_e.py — TRM Documentation Extractor & Architecture Tree Generator.
Reads UG1085 (Zynq UltraScale+ TRM) and generates a machine-readable device
architecture tree: filesystem structure + JSON indices + Markdown navigation.

Mirrors device architecture: FPGA root, major blocks as folders,
sub-components nested, leaf files as cells with connections/properties.

Usage: trm_doc_e.py [--output /path/to/output] [--pdf /path/to/ug1085.pdf]
"""
import json
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache")
DEVICE = os.path.join(ROOT, "device")
DEFAULT_OUTPUT = os.path.join(DEVICE, "architecture_tree")

# ============================================================================
# DEVICE ARCHITECTURE SCHEMA (extracted from UG1085)
# ============================================================================

DEVICE_HIERARCHY = {
    "FPGA": {
        "type": "device",
        "name": "Zynq UltraScale+ MPSoC",
        "device_name": "XCZU19EG",
        "description": "Zynq UltraScale+ with 4 processing cores, 2 real-time cores, GPU, dual power domains",
        "children": ["PS", "PL", "CLOCKING", "RESET", "POWER_DOMAINS", "BOUNDARY"],

        "PS": {
            "type": "domain",
            "name": "Processing System",
            "description": "Processor subsystem with APU, RPU, GPU, DDR controller, interconnect",
            "children": ["FPD", "LPD"],

            "FPD": {
                "type": "power_domain",
                "name": "Full-Power Domain (FPD)",
                "description": "Full-power processor domain: APU, GPU, DDR, FPD interconnect",
                "power_rail": "VCCINT_FPD",
                "children": ["APU", "GPU", "DDR_CONTROLLER", "FPD_MAIN_SWITCH", "CCI", "FPD_SLCR"],

                "APU": {
                    "type": "processor_unit",
                    "name": "Application Processing Unit",
                    "description": "ARM Cortex-A53 quad-core processor with GIC, L2 cache",
                    "cores": 4,
                    "processor": "ARM Cortex-A53",
                    "frequency_mhz": 1500,
                    "l2_cache_kb": 2048,
                    "references": {"chapter": 3, "pages": "51-77", "tables": ["3-1", "3-2"]},
                    "connections": [
                        {
                            "to": "CCI",
                            "signal": "ACE",
                            "width": 128,
                            "direction": "bidirectional",
                            "coherency": "full",
                            "via": "ADB (AXI Domain Bridge)"
                        }
                    ]
                },

                "GPU": {
                    "type": "processor_unit",
                    "name": "Graphics Processing Unit",
                    "description": "Mali-400 GPU for graphics acceleration",
                    "references": {"chapter": 5, "pages": "95-114"},
                    "connections": [
                        {
                            "to": "CCI",
                            "signal": "ACE-Lite",
                            "width": 128,
                            "direction": "master",
                            "coherency": "I/O coherent"
                        }
                    ]
                },

                "DDR_CONTROLLER": {
                    "type": "memory_controller",
                    "name": "DDR Memory Controller",
                    "description": "DDR4 SDRAM controller with 6 slave ports",
                    "data_width": 512,
                    "references": {"chapter": 17, "pages": "424-512", "tables": ["17-1", "17-2"]},
                    "children": ["DDR_PORT_0", "DDR_PORT_1", "DDR_PORT_2", "DDR_PORT_3", "DDR_PORT_4", "DDR_PORT_5"],
                    "connections": [
                        {"to": "FPD_MAIN_SWITCH", "direction": "slave"},
                        {"to": "CCI", "signal": "DDR_Slave", "direction": "slave"}
                    ],

                    "DDR_PORT_0": {"port_id": 0, "arbiter": "QoS", "description": "Priority port"},
                    "DDR_PORT_1": {"port_id": 1, "arbiter": "QoS", "description": "Standard port"},
                    "DDR_PORT_2": {"port_id": 2, "arbiter": "QoS"},
                    "DDR_PORT_3": {"port_id": 3, "arbiter": "QoS"},
                    "DDR_PORT_4": {"port_id": 4, "arbiter": "QoS"},
                    "DDR_PORT_5": {"port_id": 5, "arbiter": "QoS"}
                },

                "FPD_MAIN_SWITCH": {
                    "type": "interconnect",
                    "name": "FPD Main Switch",
                    "description": "128-bit AXI switch: APU/GPU/SATA/PCIe → DDR + LPD slaves",
                    "data_width": 128,
                    "references": {"chapter": 15, "pages": "364-380"},
                    "connections": [
                        {"to": "DDR_CONTROLLER", "direction": "master"},
                        {"to": "CCI", "direction": "master"}
                    ]
                },

                "CCI": {
                    "type": "interconnect",
                    "name": "Coherency and Interconnect (CCI-400)",
                    "description": "Central coherent interconnect: ACE ports for APU/GPU/PL, DDR masters, SMMU DVM",
                    "data_width": 128,
                    "ports": {
                        "ACE_slave": [0, 1],
                        "ACE_lite_slave": [2, 3, 4],
                        "ACE_lite_master": [0, 1],
                        "DVM": "SMMU message interface"
                    },
                    "references": {"chapter": 15, "pages": "369-380"},
                    "connections": [
                        {"to": "APU", "signal": "ACE", "direction": "slave"},
                        {"to": "GPU", "signal": "ACE-Lite", "direction": "slave"},
                        {"to": "DDR_CONTROLLER", "signal": "DDR_Master", "direction": "master"}
                    ]
                },

                "FPD_SLCR": {
                    "type": "config",
                    "name": "FPD System Level Control Registers",
                    "description": "Configuration and control registers for FPD domain"
                }
            },

            "LPD": {
                "type": "power_domain",
                "name": "Low-Power Domain (LPD)",
                "description": "Low-power subsystem: RPU, OCM, peripherals, LPD interconnect",
                "power_rail": "VCCINT_LPD",
                "children": ["RPU", "OCM", "LPD_MAIN_SWITCH", "IOP_PERIPHERALS", "LPD_DMA"],

                "RPU": {
                    "type": "processor_unit",
                    "name": "Real-time Processing Unit",
                    "description": "ARM Cortex-R5 dual-core real-time processor",
                    "cores": 2,
                    "processor": "ARM Cortex-R5",
                    "frequency_mhz": 600,
                    "tcm_kb": 128,
                    "references": {"chapter": 4, "pages": "79-94"},
                    "connections": [
                        {"to": "LPD_MAIN_SWITCH", "signal": "AXI", "direction": "master"}
                    ]
                },

                "OCM": {
                    "type": "memory",
                    "name": "On-Chip Memory",
                    "description": "Tightly-coupled memory: 256 KB total, accessible from RPU and FPD",
                    "capacity_kb": 256,
                    "references": {"chapter": 18, "pages": "514-519"}
                },

                "LPD_MAIN_SWITCH": {
                    "type": "interconnect",
                    "name": "LPD Main Switch",
                    "description": "Low-power AXI switch: RPU/IOP → OCM/FPD bridge",
                    "data_width": 32,
                    "references": {"chapter": 15, "pages": "364-368"},
                    "connections": [
                        {"to": "RPU", "direction": "slave"},
                        {"to": "OCM", "direction": "master"},
                        {"to": "FPD", "via": "TBU2", "direction": "master"}
                    ]
                },

                "IOP_PERIPHERALS": {
                    "type": "peripheral_group",
                    "name": "I/O Peripherals",
                    "description": "UART, CAN, I2C, SPI, QSPI, GEM, SDIO, USB, etc.",
                    "references": {"chapter": "20-34", "pages": "552-1046"},
                    "children": ["UART_0", "UART_1", "CAN_0", "CAN_1", "I2C_0", "I2C_1", "SPI", "QSPI", "GEM", "SDIO", "USB"]
                },

                "LPD_DMA": {
                    "type": "dma_engine",
                    "name": "LPD DMA Controller",
                    "description": "4-channel DMA engine for LPD peripherals",
                    "channels": 4
                }
            }
        },

        "PL": {
            "type": "domain",
            "name": "Programmable Logic",
            "description": "User-programmable FPGA fabric and hard blocks",
            "children": ["FABRIC", "HARD_BLOCKS"],

            "FABRIC": {
                "type": "fabric",
                "name": "FPGA Fabric",
                "description": "General routing interconnect (switch matrices), CLB, LUT, carry, distributed RAM",
                "grid": [64, 64],
                "routing_resources": {
                    "switch_matrices": "per-tile general interconnect (Vivado-internal)",
                    "track_types": "routing and distribution (clock domain)"
                },
                "references": {"chapter": "UG574 (CLB), UG573 (Memory), UG579 (DSP)"}
            },

            "HARD_BLOCKS": {
                "type": "peripheral_group",
                "name": "Hard IP Blocks",
                "description": "Embedded functional blocks in PL",
                "references": {"chapter": 36, "pages": "1082-1095"},
                "children": ["PCIE", "ETHERNET_100G", "GTH", "GTY", "VCU", "RFSOC"]
            }
        },

        "CLOCKING": {
            "type": "subsystem",
            "name": "Clock Subsystem",
            "description": "PLL, clock distribution, clock regions, segmentation",
            "references": {"chapter": 37, "pages": "1096-1122"},
            "clock_regions": {"x": 6, "y": 4},
            "clock_tracks_per_region": {"routing": 24, "distribution": 24}
        },

        "RESET": {
            "type": "subsystem",
            "name": "Reset Subsystem",
            "description": "Global, domain, and module resets",
            "references": {"chapter": 38, "pages": "1123-1134"}
        },

        "POWER_DOMAINS": {
            "type": "config_group",
            "name": "Power Domains",
            "description": "Power islands and isolation",
            "children": ["FPD_DOMAIN", "LPD_DOMAIN", "PLPD_DOMAIN", "BPD_DOMAIN"],

            "FPD_DOMAIN": {"name": "Full-Power Domain", "rails": ["VCCINT_FPD"]},
            "LPD_DOMAIN": {"name": "Low-Power Domain", "rails": ["VCCINT_LPD"]},
            "PLPD_DOMAIN": {"name": "PL Low-Power Domain", "rails": ["VCCINT_PLPD"]},
            "BPD_DOMAIN": {"name": "Battery-backed Power Domain", "rails": ["VCCBATT"]}
        },

        "BOUNDARY": {
            "type": "interface_group",
            "name": "PS↔PL Boundary Interfaces",
            "description": "All signals crossing the PS-PL die boundary",
            "references": {"chapter": 2, "pages": "40-49", "chapter_detailed": 35, "pages_detailed": "1055-1077"},
            "children": ["AXI_INTERFACES", "INTERRUPTS", "CLOCKS_BOUNDARY", "EMIO", "SYSTEM_SIGNALS", "DEBUG"]
        }
    }
}

AXI_INTERFACES = {
    "S_AXI_HP0_FPD": {
        "direction": "PL→PS",
        "data_width": 32,
        "address_width": 49,
        "master_id_width": 6,
        "fifo_depth": 128,
        "max_outstanding": 8,
        "coherency": "non-coherent",
        "destination": "FPD Main Switch → DDR",
        "use_case": "High-performance PL→PS data transfers (non-coherent)",
        "table_ref": "35-1"
    },
    "S_AXI_HP1_FPD": {
        "direction": "PL→PS",
        "data_width": 32,
        "address_width": 49,
        "master_id_width": 6,
        "fifo_depth": 128,
        "max_outstanding": 8,
        "coherency": "non-coherent",
        "xpi_share": "XPI_4",
        "table_ref": "35-1"
    },
    "S_AXI_HP2_FPD": {
        "direction": "PL→PS",
        "data_width": 32,
        "address_width": 49,
        "master_id_width": 6,
        "fifo_depth": 128,
        "coherency": "non-coherent",
        "xpi_share": "XPI_4",
        "table_ref": "35-1"
    },
    "S_AXI_HP3_FPD": {
        "direction": "PL→PS",
        "data_width": 32,
        "address_width": 49,
        "master_id_width": 6,
        "fifo_depth": 128,
        "coherency": "non-coherent",
        "xpi_share": "FPD_DMA",
        "table_ref": "35-1"
    },
    "S_AXI_HPC0_FPD": {
        "direction": "PL→PS",
        "data_width": 128,
        "address_width": 49,
        "master_id_width": 6,
        "fifo_depth": 128,
        "max_outstanding": 8,
        "coherency": "I/O coherent (one-way snoop)",
        "destination": "CCI ACE-Lite slave",
        "use_case": "PL snoops APU L1/L2 caches (I/O coherency)",
        "table_ref": "35-1"
    },
    "S_AXI_HPC1_FPD": {
        "direction": "PL→PS",
        "data_width": 128,
        "address_width": 49,
        "master_id_width": 6,
        "fifo_depth": 128,
        "coherency": "I/O coherent (one-way snoop)",
        "destination": "CCI ACE-Lite slave",
        "table_ref": "35-1"
    },
    "S_AXI_ACE_FPD": {
        "direction": "PL→PS",
        "data_width": 128,
        "address_width": 40,
        "master_id_width": 6,
        "coherency": "Full ACE (bidirectional coherency)",
        "snoop_channels": ["ACADDR", "CRRESP", "CDDATA"],
        "destination": "CCI ACE slave (full coherency)",
        "use_case": "PL cache coherent with APU (bidirectional snooping)",
        "table_ref": "35-1"
    },
    "S_AXI_ACP_FPD": {
        "direction": "PL→PS",
        "data_width": 128,
        "address_width": 40,
        "master_id_width": 5,
        "coherency": "APU SCU cache-coherent (high-latency)",
        "destination": "APU L1/L2 cache (direct SCU port)",
        "restrictions": ["64B and 16B INCR txns only", "max 4 outstanding"],
        "use_case": "Legacy cache coherency (not recommended; use ACE or HPC)",
        "table_ref": "35-1"
    },
    "S_AXI_LPD": {
        "direction": "PL→PS",
        "data_width": 32,
        "address_width": 49,
        "master_id_width": 6,
        "fifo_depth": 128,
        "coherency": "non-coherent",
        "destination": "LPD Main Switch → IOP/OCM/TCM",
        "use_case": "Low-latency PL→LPD (works when FPD powered down)",
        "table_ref": "35-3"
    },
    "M_AXI_HPM0_FPD": {
        "direction": "PS→PL",
        "data_width": 32,
        "address_width": 40,
        "master_id_width": 16,
        "sources": ["APU", "FPD DMA", "PCIe"],
        "use_case": "FPD masters driving PL slaves",
        "table_ref": "35-1"
    },
    "M_AXI_HPM1_FPD": {
        "direction": "PS→PL",
        "data_width": 32,
        "address_width": 40,
        "master_id_width": 16,
        "sources": ["APU", "FPD DMA"],
        "table_ref": "35-1"
    },
    "M_AXI_HPM0_LPD": {
        "direction": "PS→PL",
        "data_width": 32,
        "address_width": 32,
        "master_id_width": 16,
        "sources": ["RPU", "IOP peripherals"],
        "address_space": "lowest 512 MB",
        "use_case": "Low-power LPD→PL (works when FPD powered down)",
        "table_ref": "35-3"
    }
}

BOUNDARY_SIGNALS = {
    "interrupts": {
        "pl_to_ps": 16,
        "ps_to_pl": 100,
        "pmu_ipi": {"pl_to_lpdpmu": 4, "lpdpmu_to_pl": 7},
        "references": "Table 2-5"
    },
    "clocks": {
        "pl_clk": 4,
        "f2p_clk": 2,
        "rtc_clk": 1,
        "references": "Table 2-10"
    },
    "processor_comms": {
        "p2f_pmu": 32,
        "f2p_pmu": 32,
        "apu_wfi_wfe": 2,
        "references": "Table 2-5"
    },
    "emio": {
        "description": "Extended MIO: GPIO, GEM, SPI, UART, I2C, CAN, etc. into PL",
        "gpio_banks": [3, 4, 5],
        "gpio_channels": 96
    },
    "system_errors": {
        "ps_to_pl": 49,
        "seu_alarm": 1,
        "references": "Table 2-6"
    }
}

# ============================================================================
# TREE GENERATOR
# ============================================================================

class TreeGenerator:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.index = {}
        self.tree = {}

    def generate(self):
        """Generate the full architecture tree."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate device hierarchy
        self._generate_hierarchy(DEVICE_HIERARCHY["FPGA"], self.output_dir, "FPGA")

        # Generate boundary interfaces
        self._generate_boundary(self.output_dir)

        # Generate main index
        self._generate_main_index()

        print(f"[trm_doc_e] Generated architecture tree at: {self.output_dir}")
        print(f"[trm_doc_e] Total entries: {len(self.index)}")

    def _generate_hierarchy(self, node, parent_dir, node_name):
        """Recursively generate filesystem tree from hierarchy."""
        if isinstance(node, dict) and "type" in node:
            # Create folder for this node
            node_dir = parent_dir / node_name
            node_dir.mkdir(exist_ok=True)

            # Write cell.json
            cell_data = {k: v for k, v in node.items() if k != "children"}
            with open(node_dir / "cell.json", "w") as f:
                json.dump(cell_data, f, indent=2)

            self.index[node_name] = {
                "path": str(node_dir.relative_to(self.output_dir.parent)),
                "type": node.get("type", "unknown"),
                "name": node.get("name", node_name)
            }

            # Generate Markdown
            self._write_markdown(node_dir, node_name, node)

            # Recurse for children
            if "children" in node:
                for child_name in node["children"]:
                    if child_name in node:
                        self._generate_hierarchy(node[child_name], node_dir, child_name)

    def _generate_boundary(self, parent_dir):
        """Generate PS↔PL boundary interface documentation."""
        boundary_dir = parent_dir / "BOUNDARY"
        boundary_dir.mkdir(exist_ok=True)

        # Write AXI interfaces
        axi_dir = boundary_dir / "AXI_INTERFACES"
        axi_dir.mkdir(exist_ok=True)

        for iface_name, iface_spec in AXI_INTERFACES.items():
            with open(axi_dir / f"{iface_name}.json", "w") as f:
                json.dump(iface_spec, f, indent=2)
            self.index[f"AXI/{iface_name}"] = {
                "path": str((axi_dir / iface_name).relative_to(self.output_dir.parent)),
                "type": "axi_interface"
            }

        # Write boundary signals
        signals_file = boundary_dir / "signals.json"
        with open(signals_file, "w") as f:
            json.dump(BOUNDARY_SIGNALS, f, indent=2)

    def _write_markdown(self, node_dir, node_name, node):
        """Write Markdown documentation for a node."""
        lines = [f"# {node.get('name', node_name)}\n"]

        if "description" in node:
            lines.append(f"{node['description']}\n")

        if "type" in node:
            lines.append(f"**Type:** `{node['type']}`\n")

        # Properties
        for key in ["data_width", "address_width", "cores", "capacity_kb", "frequency_mhz"]:
            if key in node:
                lines.append(f"- **{key}:** {node[key]}\n")

        # Children
        if "children" in node:
            lines.append(f"\n## Sub-components\n")
            for child in node["children"]:
                lines.append(f"- [{child}]({child}/README.md)\n")

        # Connections
        if "connections" in node:
            lines.append(f"\n## Connections\n")
            for conn in node["connections"]:
                lines.append(f"- **{conn['to']}**: {conn.get('signal', 'AXI')} ")
                lines.append(f"({conn.get('width', 'N/A')} bits, {conn.get('direction', 'N/A')})\n")

        # References
        if "references" in node:
            lines.append(f"\n## References (UG1085)\n")
            for key, val in node["references"].items():
                lines.append(f"- {key}: {val}\n")

        with open(node_dir / "README.md", "w") as f:
            f.writelines(lines)

    def _generate_main_index(self):
        """Generate main index.json and INDEX.md."""
        index_file = self.output_dir / "index.json"
        with open(index_file, "w") as f:
            json.dump(self.index, f, indent=2)

        # Generate INDEX.md
        index_md = self.output_dir / "INDEX.md"
        with open(index_md, "w") as f:
            f.write("# FPGA Device Architecture Index\n\n")
            f.write("Extracted from UG1085 (Zynq UltraScale+ TRM)\n\n")
            f.write("## Top-level domains\n\n")
            f.write("- [PS (Processing System)](PS/README.md)\n")
            f.write("- [PL (Programmable Logic)](PL/README.md)\n")
            f.write("- [BOUNDARY (PS↔PL Interfaces)](BOUNDARY/)\n")
            f.write("- [CLOCKING](CLOCKING/README.md)\n")
            f.write("- [RESET](RESET/README.md)\n")
            f.write("- [POWER_DOMAINS](POWER_DOMAINS/README.md)\n\n")
            f.write(f"**Total entries:** {len(self.index)}\n")

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="TRM Documentation Extractor & Architecture Tree Generator"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--pdf",
        help="Path to UG1085 PDF (optional, for future enhancement)"
    )
    args = parser.parse_args()

    gen = TreeGenerator(args.output)
    gen.generate()

    print("\n[trm_doc_e] SUCCESS")
    print(f"[trm_doc_e] Architecture tree ready at: {args.output}")
    print(f"[trm_doc_e] Start with: {args.output}/INDEX.md")

if __name__ == "__main__":
    main()
