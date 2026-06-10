#!/usr/bin/env python3
"""parse_datasheets.py — Extract structured device specs from Xilinx PDF datasheets.

This tool parses Xilinx FPGA datasheets (e.g., DS922 for VU9P) and extracts:
  - Device name, family, package, speed grade
  - Resource counts (CLBs, LUTs, BRAM, DSP, transceivers, I/O banks)
  - Connectivity information (LUT inputs/outputs, carry chains, routing resources)

Output: device_specs.json with structured specification for use by gen_device_net.py
and the broader FPGA device netlist pipeline.

Implementation:
  1. Try to extract from PDF using pdfplumber (if available and PDF provided)
  2. Fall back to hardcoded VU9P specs from XILINX_VU9P_SPEC_EXTRACTION.md
  3. Support device-specific overrides via command-line or JSON config
  4. Validate output JSON structure
"""

import json
import sys
import argparse
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

# Try to import pdfplumber for PDF parsing
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


# ============================================================================
# Hardcoded VU9P Specification
# ============================================================================
# Source: XILINX_VU9P_SPEC_EXTRACTION.md (canonical extraction from DS922)

VU9P_SPEC = {
    "device": {
        "name": "xcvu9p-flga2104-2L",
        "family": "Virtex UltraScale+",
        "package": "FLGA2104",
        "speed_grade": "-2",
        "temperature_grade": "Commercial (0°C to 85°C)",
    },
    "resources": {
        "clbs": 182400,
        "luts": 1457600,
        "flip_flops": 2918400,
        "distributed_ram_bits": 96 * 1024 * 1024,  # 96 Mbit
        "bram36": 2160,
        "bram18": 4320,  # Can use BRAM36 split
        "bram_total_bits": 77 * 1024 * 1024 + 760 * 1024,  # 77.76 Mb
        "dsp48e2": 6840,
        "cmt_tiles": 6,
        "mmcm": 6,
        "pll": 6,
        "gty_transceivers": 32,
        "gty_max_speed_gbps": 32.75,
        "gth_transceivers": 0,
        "io_banks": 44,
        "xadc": 1,
    },
    "connectivity": {
        "lut_inputs": 6,
        "lut_outputs": 1,
        "ff_per_clb": 16,
        "luts_per_clb": 8,
        "carry_chain_length": 4,
        "routing_resources": {
            "local": 9120000,  # 50 short nets per CLB
            "regional": 2500000,
            "general": 2000000,
        },
        "clock_buffers": {
            "bufg": 32,
            "bufgctrl": 16,
        },
        "global_clock_distribution": 150,  # Total CMT + buffer connections
    },
    "structure": {
        "slices_per_clb": 2,
        "luts_per_slice": 4,
        "ffs_per_slice": 8,
        "carry_chains_per_clb": 1,
        "bram36_ports": {
            "address_bits_a": 15,
            "address_bits_b": 15,
            "data_width_a": 36,
            "data_width_b": 36,
            "connections_per_bram": 120,
        },
        "dsp48e2_ports": {
            "a_width": 30,
            "b_width": 18,
            "d_width": 25,
            "c_width": 48,
            "p_width": 48,
            "connections_per_dsp": 150,
        },
        "gty_per_quad": 4,
        "gty_tx_data_width": 64,
        "gty_rx_data_width": 64,
        "io_per_bank": 40,  # Average
    },
    "metadata": {
        "source": "XILINX_VU9P_SPEC_EXTRACTION.md",
        "datasheet": "DS922 (Virtex UltraScale+ Datasheet)",
        "product_guide": "PG252 (Virtex UltraScale+ Product Guide)",
        "extracted_date": "2026-06-10",
    },
}


# ============================================================================
# PDF Extraction (if pdfplumber available)
# ============================================================================

def extract_device_header_from_pdf(pdf_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract device name, family, package, and speed grade from PDF first pages.
    Looks for common patterns like "xcvu9p-flga2104-2L" in datasheet cover/intro.
    """
    if not HAS_PDFPLUMBER:
        return None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Check first 5 pages for device specs
            for page_num in range(min(5, len(pdf.pages))):
                page = pdf.pages[page_num]
                text = page.extract_text()
                if not text:
                    continue

                # Pattern: xcXXXX-XXXXX-X (device code)
                device_match = re.search(
                    r"(xc[a-z0-9]+-[a-z0-9]+-[0-9])",
                    text,
                    re.IGNORECASE,
                )
                if device_match:
                    device_name = device_match.group(1).lower()
                    # Parse device name components
                    parts = device_name.split("-")
                    if len(parts) >= 3:
                        return {
                            "device_name": device_name,
                            "package": parts[1] if len(parts) > 1 else None,
                            "speed_grade": parts[2] if len(parts) > 2 else None,
                        }
    except Exception as e:
        print(f"Warning: PDF extraction failed: {e}", file=sys.stderr)
        return None

    return None


def extract_resources_from_pdf(pdf_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract resource counts (CLBs, BRAM, DSP, etc.) from PDF tables.
    Typically found in datasheet "Summary" or "Resources" section.
    """
    if not HAS_PDFPLUMBER:
        return None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    # Try to find a table with resource data
                    flattened = []
                    for row in table:
                        flattened.extend(row if row else [])

                    text_lower = " ".join(str(cell).lower() for cell in flattened)

                    # Check if this looks like a resource table
                    if any(
                        keyword in text_lower
                        for keyword in ["clb", "lut", "bram", "dsp", "gty"]
                    ):
                        # Parse table for numeric values
                        resources = {}
                        for row in table:
                            if not row or len(row) < 2:
                                continue

                            label = str(row[0]).lower().strip()
                            try:
                                value = int(
                                    str(row[1])
                                    .replace(",", "")
                                    .replace("(", "")
                                    .replace(")", "")
                                    .split()[0]
                                )

                                # Map common labels to resource names
                                if "clb" in label:
                                    resources["clbs"] = value
                                elif "lut" in label and "clb" not in label:
                                    resources["luts"] = value
                                elif "bram36" in label or ("bram" in label and "36" in label):
                                    resources["bram36"] = value
                                elif "dsp48" in label or ("dsp" in label and "48" in label):
                                    resources["dsp48e2"] = value
                                elif "gty" in label:
                                    resources["gty_transceivers"] = value
                                elif "io" in label and "bank" in label:
                                    resources["io_banks"] = value

                            except (ValueError, IndexError):
                                continue

                        if resources:
                            return resources

    except Exception as e:
        print(f"Warning: Resource extraction failed: {e}", file=sys.stderr)
        return None

    return None


# ============================================================================
# Device Spec Builder
# ============================================================================

def build_device_spec(
    device_name: Optional[str] = None,
    package: Optional[str] = None,
    speed_grade: Optional[str] = None,
    family: Optional[str] = None,
    resources: Optional[Dict[str, int]] = None,
    connectivity: Optional[Dict[str, Any]] = None,
    use_vu9p_defaults: bool = True,
) -> Dict[str, Any]:
    """
    Build a complete device spec, starting with defaults and overlaying provided values.

    Args:
        device_name: Full device name (e.g., "xcvu9p-flga2104-2L")
        package: Package code (e.g., "FLGA2104")
        speed_grade: Speed grade (e.g., "-2")
        family: Family name (e.g., "Virtex UltraScale+")
        resources: Dict of resource counts to override
        connectivity: Dict of connectivity specs to override
        use_vu9p_defaults: If True, start with VU9P as baseline

    Returns:
        Complete device spec dictionary
    """
    # Start with VU9P defaults if requested
    if use_vu9p_defaults:
        spec = json.loads(json.dumps(VU9P_SPEC))  # Deep copy
    else:
        spec = {
            "device": {},
            "resources": {},
            "connectivity": {},
            "structure": {},
            "metadata": {},
        }

    # Override device header info
    if device_name:
        spec["device"]["name"] = device_name
    if package:
        spec["device"]["package"] = package
    if speed_grade:
        spec["device"]["speed_grade"] = speed_grade
    if family:
        spec["device"]["family"] = family

    # Override resource counts
    if resources:
        spec["resources"].update(resources)

    # Override connectivity
    if connectivity:
        spec["connectivity"].update(connectivity)

    return spec


def validate_device_spec(spec: Dict[str, Any]) -> bool:
    """
    Validate device spec structure.
    Ensures all required fields are present and have sensible values.
    """
    required_keys = ["device", "resources", "connectivity"]
    for key in required_keys:
        if key not in spec:
            print(f"Error: Missing required key '{key}'", file=sys.stderr)
            return False

    # Validate device info
    device = spec.get("device", {})
    if not device.get("name"):
        print("Error: Device name is required", file=sys.stderr)
        return False

    # Validate resources (at least some should be present)
    resources = spec.get("resources", {})
    if not resources:
        print("Error: No resources defined", file=sys.stderr)
        return False

    # Basic sanity check: total resources should be reasonable
    clbs = resources.get("clbs", 0)
    luts = resources.get("luts", 0)
    if clbs > 0 and luts > 0:
        # CLB = 8 LUTs, so luts should be ~8*clbs
        ratio = luts / (clbs * 8)
        if ratio < 0.5 or ratio > 2.0:
            print(
                f"Warning: LUT/CLB ratio {ratio:.2f} seems unusual (expected ~1.0)",
                file=sys.stderr,
            )

    return True


# ============================================================================
# Main Tool
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Parse Xilinx FPGA datasheets and extract device specifications.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract from VU9P hardcoded spec (default)
  python3 parse_datasheets.py -o device_specs.json

  # Try to extract from PDF (if pdfplumber available)
  python3 parse_datasheets.py -d DS922_VU9P.pdf -o device_specs.json

  # Extract from PDF, override with custom values
  python3 parse_datasheets.py -d datasheet.pdf \\
    --device-name xcvu9p-custom-2L \\
    --package FLGA2104 \\
    --speed-grade -2 \\
    -o device_specs.json

  # Generate spec for different device (if data available)
  python3 parse_datasheets.py --device-name xcvu13p-flga2104-3L -o vu13p_specs.json
        """,
    )

    parser.add_argument(
        "-d",
        "--datasheet",
        type=str,
        help="Path to Xilinx datasheet PDF (optional; uses VU9P defaults if not provided)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="device_specs.json",
        help="Output JSON file (default: device_specs.json)",
    )
    parser.add_argument(
        "--device-name",
        type=str,
        help="Override device name (e.g., xcvu9p-flga2104-2L)",
    )
    parser.add_argument(
        "--package",
        type=str,
        help="Override package code (e.g., FLGA2104)",
    )
    parser.add_argument(
        "--speed-grade",
        type=str,
        help="Override speed grade (e.g., -2)",
    )
    parser.add_argument(
        "--family",
        type=str,
        help="Override device family (e.g., Virtex UltraScale+)",
    )
    parser.add_argument(
        "--no-vu9p-defaults",
        action="store_true",
        help="Do not use VU9P defaults; start with empty spec",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate spec and exit without writing file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        print("parse_datasheets.py: Device Spec Extraction Tool")
        print(f"  Output: {args.output}")
        if args.datasheet:
            print(f"  PDF Input: {args.datasheet}")
        print(f"  Use VU9P defaults: {not args.no_vu9p_defaults}")

    # Check if PDF parsing is available
    if args.datasheet and not HAS_PDFPLUMBER:
        print(
            "Warning: pdfplumber not available; install with: pip install pdfplumber",
            file=sys.stderr,
        )
        print("Falling back to hardcoded specs.", file=sys.stderr)

    # Extract from PDF if provided
    pdf_resources = None
    pdf_device = None

    if args.datasheet and Path(args.datasheet).exists():
        if args.verbose:
            print(f"Extracting from PDF: {args.datasheet}")

        pdf_device = extract_device_header_from_pdf(args.datasheet)
        if pdf_device and args.verbose:
            print(f"  Device from PDF: {pdf_device}")

        pdf_resources = extract_resources_from_pdf(args.datasheet)
        if pdf_resources and args.verbose:
            print(f"  Resources from PDF: {pdf_resources}")

    elif args.datasheet and not Path(args.datasheet).exists():
        print(f"Error: Datasheet file not found: {args.datasheet}", file=sys.stderr)
        sys.exit(1)

    # Build spec
    device_name = args.device_name or (pdf_device.get("device_name") if pdf_device else None)
    package = args.package or (pdf_device.get("package") if pdf_device else None)
    speed_grade = args.speed_grade or (
        pdf_device.get("speed_grade") if pdf_device else None
    )
    family = args.family

    spec = build_device_spec(
        device_name=device_name,
        package=package,
        speed_grade=speed_grade,
        family=family,
        resources=pdf_resources,
        use_vu9p_defaults=not args.no_vu9p_defaults,
    )

    # Validate
    if not validate_device_spec(spec):
        sys.exit(1)

    if args.verbose:
        print(f"✓ Spec validation passed")
        print(f"  Device: {spec['device']['name']}")
        print(f"  Resources: {len(spec['resources'])} entries")
        print(f"  Connectivity: {len(spec['connectivity'])} entries")

    if args.validate_only:
        if args.verbose:
            print("Validation-only mode; skipping file write.")
        sys.exit(0)

    # Write output
    try:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(spec, f, indent=2)
            f.write("\n")

        if args.verbose:
            print(f"✓ Wrote {args.output}")
            print(f"  Size: {output_path.stat().st_size} bytes")
        else:
            print(f"Wrote device spec to {args.output}")

    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
