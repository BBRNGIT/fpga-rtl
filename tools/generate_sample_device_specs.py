#!/usr/bin/env python3
"""
generate_sample_device_specs.py — Generate sample device spec files for testing.

Creates example device_specs.json (from datasheet parser), f4pga database,
and Trellis specs for testing the merge tool.

This helper generates realistic test data matching the merge_device_sources.py
input format expectations.
"""

import json
import sys
from pathlib import Path


def generate_datasheet_specs() -> dict:
    """Generate sample datasheet specs (primary source)."""
    return {
        "source": "datasheet",
        "devices": {
            "xcvu9p-flga2104-2L": {
                "name": "Xilinx Virtex UltraScale+ XCVU9P",
                "device_code": "xcvu9p",
                "package": "flga2104",
                "speed_grade": "-2L",
                "parts": [
                    {
                        "name": "CLB",
                        "type": "CLB",
                        "count": 182400,
                        "io_per_unit": 50,
                        "note": "Configurable Logic Blocks"
                    },
                    {
                        "name": "BRAM",
                        "type": "BRAM",
                        "count": 912,
                        "io_per_unit": 1024,
                        "note": "36KB BRAM blocks"
                    },
                    {
                        "name": "DSP48E2",
                        "type": "DSP",
                        "count": 3456,
                        "io_per_unit": 2,
                        "note": "DSP48E2 slices"
                    },
                    {
                        "name": "IOB",
                        "type": "IOB",
                        "count": 2104,
                        "io_per_unit": 1,
                        "note": "I/O blocks"
                    },
                    {
                        "name": "MMCM",
                        "type": "MMCM",
                        "count": 4,
                        "io_per_unit": 0,
                        "note": "Mixed-Mode Clock Manager"
                    },
                ]
            },
            "xcku9p-ffva1156-2L": {
                "name": "Xilinx Kintex UltraScale XCKU9P",
                "device_code": "xcku9p",
                "package": "ffva1156",
                "speed_grade": "-2L",
                "parts": [
                    {
                        "name": "CLB",
                        "type": "CLB",
                        "count": 119280,
                        "io_per_unit": 50,
                    },
                    {
                        "name": "BRAM",
                        "type": "BRAM",
                        "count": 600,
                        "io_per_unit": 1024,
                    },
                    {
                        "name": "DSP48E1",
                        "type": "DSP",
                        "count": 2880,
                        "io_per_unit": 2,
                    },
                    {
                        "name": "IOB",
                        "type": "IOB",
                        "count": 1156,
                        "io_per_unit": 1,
                    },
                ]
            }
        }
    }


def generate_f4pga_specs() -> dict:
    """Generate sample f4pga device database specs."""
    return {
        "source": "f4pga",
        "schema_version": "2.0",
        "devices": {
            "xcvu9p_flga2104": {
                "name": "Xilinx Virtex UltraScale+ XCVU9P-FLGA2104",
                "family": "vu",
                "parts": [
                    {
                        "name": "CLB",
                        "type": "CLB",
                        "count": 182400,
                        "io_per_unit": 50,
                    },
                    {
                        "name": "BRAM",
                        "type": "BRAM",
                        "count": 912,
                        "io_per_unit": 1024,
                    },
                    {
                        "name": "DSP",
                        "type": "DSP",
                        "count": 3480,  # 0.7% difference from datasheet
                        "io_per_unit": 2,
                    },
                    {
                        "name": "IOB",
                        "type": "IOB",
                        "count": 2104,
                        "io_per_unit": 1,
                    },
                ],
                "routing": {
                    "local": 1641600,
                    "regional": 2500000,
                    "long_lines": 18720,
                }
            },
            "xcku9p_ffva1156": {
                "name": "Xilinx Kintex UltraScale XCKU9P-FFVA1156",
                "family": "ku",
                "parts": [
                    {
                        "name": "CLB",
                        "type": "CLB",
                        "count": 119280,
                        "io_per_unit": 50,
                    },
                    {
                        "name": "BRAM",
                        "type": "BRAM",
                        "count": 600,
                        "io_per_unit": 1024,
                    },
                    {
                        "name": "DSP",
                        "type": "DSP",
                        "count": 2880,
                        "io_per_unit": 2,
                    },
                    {
                        "name": "IOB",
                        "type": "IOB",
                        "count": 1156,
                        "io_per_unit": 1,
                    },
                ],
                "routing": {
                    "local": 1073520,
                    "regional": 1600000,
                    "long_lines": 12240,
                }
            }
        }
    }


def generate_trellis_specs() -> dict:
    """Generate sample Project Trellis ECP5 specs."""
    return {
        "source": "trellis",
        "schema_version": "1.0",
        "note": "ECP5 bitstream reference from Project Trellis",
        "devices": {
            "LFE5U85F": {
                "name": "Lattice ECP5 LFE5U85F",
                "family": "ecp5",
                "package": "BG381",
                "parts": [
                    {
                        "name": "SLICE",
                        "type": "CLB",
                        "count": 10848,
                        "io_per_unit": 4,
                    },
                    {
                        "name": "DPRAM",
                        "type": "BRAM",
                        "count": 432,
                        "io_per_unit": 512,
                    },
                    {
                        "name": "DSUPPORT",
                        "type": "DSP",
                        "count": 108,
                        "io_per_unit": 1,
                    },
                    {
                        "name": "IO",
                        "type": "IOB",
                        "count": 381,
                        "io_per_unit": 1,
                    },
                ],
                "routing": {
                    "local": 43392,
                    "span4": 10848,
                    "span12": 2712,
                }
            }
        }
    }


def main():
    """Generate sample device spec files."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate sample device spec files for testing merge_device_sources.py"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory (default: current directory)"
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate datasheet specs
    datasheet = generate_datasheet_specs()
    datasheet_path = output_dir / "device_specs.json"
    with open(datasheet_path, 'w') as f:
        json.dump(datasheet, f, indent=2)
    print(f"Generated {datasheet_path}")

    # Generate f4pga specs
    f4pga = generate_f4pga_specs()
    f4pga_path = output_dir / "f4pga_devices.json"
    with open(f4pga_path, 'w') as f:
        json.dump(f4pga, f, indent=2)
    print(f"Generated {f4pga_path}")

    # Generate Trellis specs
    trellis = generate_trellis_specs()
    trellis_path = output_dir / "trellis_ecp5.json"
    with open(trellis_path, 'w') as f:
        json.dump(trellis, f, indent=2)
    print(f"Generated {trellis_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
