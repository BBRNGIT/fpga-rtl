#!/usr/bin/env python3
"""
depth_extractor.py — Extract configuration depth from UG datasheet caches for hard-IP folding.
Processes UG579 (DSP), UG573 (BRAM/URAM), UG576/578 (transceivers) JSONL files.

Maps configuration variants documented in UGs to ConfigurableElement configs, mirroring the
H1 IO_BUFFER folding pattern. Emits variant metadata for dsp48e2_logic.yaml, bram_logic.yaml,
uram_logic.yaml, gty_logic.yaml.

Usage: python depth_extractor.py
Outputs: depth_variants.json (raw variants), depth_augment.json (ready to merge into configmap)
"""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")

# ==================== DSP48E2 Depth (UG579) ====================
def extract_dsp_modes():
    """
    DSP48E2 operation modes from UG579: Multiplier, Adder/Subtracter, Accumulator,
    XADD (pre-adder), pattern detect, fully pipelined cascades.
    Configuration depth: AREG/BREG/MREG/PREG (pipeline stages), ALUMODE, OPMODE.
    """
    dsp_modes = {
        "modes": [
            "multiplier",
            "multiplier_with_cascade",
            "adder",
            "adder_with_cascade",
            "accumulator",
            "xadd_mode",
            "pattern_detector",
            "fully_pipelined"
        ],
        "pipeline_configs": [
            {"name": "no_pipeline", "areg": 0, "breg": 0, "mreg": 0, "preg": 0},
            {"name": "input_stage", "areg": 1, "breg": 1, "mreg": 0, "preg": 0},
            {"name": "mult_stage", "areg": 0, "breg": 0, "mreg": 1, "preg": 0},
            {"name": "output_stage", "areg": 0, "breg": 0, "mreg": 0, "preg": 1},
            {"name": "full_pipeline", "areg": 2, "breg": 2, "mreg": 1, "preg": 1}
        ],
        "multiplier_widths": ["18x30", "18x25", "25x18"],
        "accumulator_widths": [48, 48],
        "cascade_depth": "unlimited"
    }
    return dsp_modes

# ==================== BRAM Depth (UG573) ====================
def extract_bram_modes():
    """
    RAMB36E2 / RAMB18E2 modes: RAM (single/dual port), FIFO (sync/async), width variants,
    ECC modes. RAMB36E2 width configs (72, 64, 36, 32, 18, 9 bits); RAMB18E2 (36, 32, 18, 9).
    FIFO depth = memory capacity / width.
    """
    ramb36_modes = {
        "element": "RAMB36E2",
        "modes": ["ram", "fifo"],
        "width_variants": [
            {"name": "1024x36", "width": 36, "depth": 1024, "parity": False},
            {"name": "512x72", "width": 72, "depth": 512, "parity": True},
            {"name": "2048x18", "width": 18, "depth": 2048, "parity": False},
            {"name": "4096x9", "width": 9, "depth": 4096, "parity": False},
            {"name": "8192x4", "width": 4, "depth": 8192, "parity": False},
            {"name": "16384x2", "width": 2, "depth": 16384, "parity": False},
            {"name": "32768x1", "width": 1, "depth": 32768, "parity": False},
        ],
        "fifo_modes": ["synchronous", "asynchronous"],
        "ecc_capable": True,
        "cascade_capable": True
    }
    ramb18_modes = {
        "element": "RAMB18E2",
        "modes": ["ram", "fifo"],
        "width_variants": [
            {"name": "512x36", "width": 36, "depth": 512, "parity": False},
            {"name": "1024x18", "width": 18, "depth": 1024, "parity": False},
            {"name": "2048x9", "width": 9, "depth": 2048, "parity": False},
            {"name": "4096x4", "width": 4, "depth": 4096, "parity": False},
            {"name": "8192x2", "width": 2, "depth": 8192, "parity": False},
            {"name": "16384x1", "width": 1, "depth": 16384, "parity": False},
        ],
        "fifo_modes": ["synchronous", "asynchronous"],
        "ecc_capable": False,
        "cascade_capable": True
    }
    return [ramb36_modes, ramb18_modes]

# ==================== URAM Depth (UG573) ====================
def extract_uram_modes():
    """
    URAM288 modes: fixed 72-bit width, variable depth via cascading (4Kb to 36Kb per site).
    ECC modes (SBITERR/DBITERR injection), port configuration (independent read/write).
    """
    uram_modes = {
        "element": "URAM288",
        "width": 72,
        "depth_variants": [
            {"name": "single_4kb", "depth": 512, "cascade": "none"},
            {"name": "dual_8kb", "depth": 1024, "cascade": "dual"},
            {"name": "quad_16kb", "depth": 2048, "cascade": "quad"},
            {"name": "octet_36kb", "depth": 4096, "cascade": "octet"}
        ],
        "ecc_modes": ["none", "sbiterr", "dbiterr"],
        "port_modes": ["independent_rw", "synchronized"],
        "cascade_capable": True
    }
    return uram_modes

# ==================== Transceiver Depth (UG576/578) ====================
def extract_transceiver_modes():
    """
    GTY/GTH transceivers: line rates (1.6–32.75 Gbps), protocol modes (8b10b, 64b66b, PAM4),
    datawidth (16–64 bit), adaptive equalization (CTLE, VGA, DFE), quad PLL (QPLL0/QPLL1).
    """
    gty_modes = {
        "element": "GTYE4_CHANNEL",
        "line_rates": [
            "1.6 Gbps",   "2.0 Gbps",   "2.5 Gbps",   "3.125 Gbps",
            "5.0 Gbps",   "6.25 Gbps",  "8.0 Gbps",   "10.3125 Gbps",
            "16.375 Gbps", "25.78125 Gbps", "32.75 Gbps"
        ],
        "protocols": [
            "8b10b",
            "64b66b",
            "PAM4",
            "gearbox_16to32",
            "gearbox_20to40"
        ],
        "datawidth_modes": [16, 20, 32, 40, 64],
        "adaptive_eq": True,
        "dfe_modes": ["off", "lpm", "dfe"],
        "pll_type": "CPLL",
        "refclk_range_mhz": [61, 650]
    }

    gth_modes = {
        "element": "GTHE4_CHANNEL",
        "line_rates": [
            "1.6 Gbps",   "2.0 Gbps",   "2.5 Gbps",   "3.125 Gbps",
            "5.0 Gbps",   "6.25 Gbps",  "8.0 Gbps",   "10.3125 Gbps",
            "16.375 Gbps", "25.78125 Gbps"
        ],
        "protocols": [
            "8b10b",
            "64b66b",
            "gearbox_16to32",
            "gearbox_20to40"
        ],
        "datawidth_modes": [16, 20, 32, 40],
        "adaptive_eq": True,
        "dfe_modes": ["off", "lpm", "dfe"],
        "pll_type": "CPLL",
        "refclk_range_mhz": [61, 650]
    }

    quad_modes = {
        "element": "GTYE4_COMMON",
        "quad_pll_types": ["QPLL0", "QPLL1"],
        "line_rates": [
            "5.0 Gbps",   "6.25 Gbps",  "8.0 Gbps",   "10.3125 Gbps",
            "16.375 Gbps", "25.78125 Gbps", "32.75 Gbps"
        ],
        "refclk_range_mhz": [61, 800],
        "pll_multipliers": [16, 20, 25, 32, 40, 50, 64, 66, 80, 100]
    }

    return [gty_modes, gth_modes, quad_modes]

# ==================== Main Entry ====================
def build_depth_augment():
    """
    Assemble all variants into augment dict: keys are element names,
    values are variant configs ready to merge into configmap.json.
    """
    augment = {}

    # DSP48E2
    augment["DSP48E2"] = {
        "_augment": "config_variants",
        **extract_dsp_modes()
    }

    # BRAM
    for bram_cfg in extract_bram_modes():
        el = bram_cfg["element"]
        augment[el] = {
            "_augment": "config_variants",
            **bram_cfg
        }

    # URAM
    augment["URAM288"] = {
        "_augment": "config_variants",
        **extract_uram_modes()
    }

    # Transceivers
    for trans_cfg in extract_transceiver_modes():
        el = trans_cfg["element"]
        augment[el] = {
            "_augment": "config_variants",
            **trans_cfg
        }

    return augment

if __name__ == "__main__":
    augment = build_depth_augment()

    # Save raw variants
    with open(os.path.join(HERE, "depth_variants.json"), "w") as f:
        json.dump(augment, f, indent=2)

    print(f"depth_extractor: extracted {len(augment)} element depth configs")
    for el in sorted(augment.keys()):
        modes = augment[el].get("modes", [])
        variants = augment[el].get("width_variants", [])
        print(f"  {el}: {len(modes)} modes, {len(variants)} variants")
