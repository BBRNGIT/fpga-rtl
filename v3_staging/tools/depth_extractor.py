#!/usr/bin/env python3
"""
depth_extractor.py — Configuration-depth metadata for hard-IP folding (Law #13 honest provenance).

Provenance policy (Law #13 "extracted, not invented"): every element this tool emits carries a
"provenance" field that is EITHER a real datasheet cite (e.g. "ug579 page 28 table 1 ...") for
values genuinely table-scanned from the UG cache, OR the honest label "curated-constant" for values
that are hand-curated UG reference constants whose table extraction is still pending. Nothing here
claims extraction it does not perform.

Currently extracted (table-scanned from cache):
  - DSP48E2 OPMODE multiplexer-select configuration (UG579, W/X/Y/Z multiplexer-output tables)

Curated UG reference constants (full extraction pending — labeled "curated-constant"):
  - BRAM (RAMB36E2/RAMB18E2) width_variants, URAM288 depth_variants, GTY/GTH line_rates/protocols

Usage: python depth_extractor.py
Outputs: depth_variants.json (augment dict, each element provenance-tagged)
"""
import json, os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")

# --------- Cache reader + table scan (pattern copied from clkfab.py:load_cache/extract_table_rows) ---------
def load_cache(cachedir, pattern):
    """Load all matching .jsonl cache records (one JSON object per line)."""
    recs = []
    for cf in sorted(glob.glob(os.path.join(cachedir, f"{pattern}.jsonl"))):
        for line in open(cf):
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return recs

def normalize_text(s):
    """Collapse whitespace/newlines in a cell."""
    return re.sub(r'\s+', ' ', (s or "").strip())

def extract_table_rows(rec, column_criteria):
    """Return [(raw_header, data_rows)] for tables in rec whose header matches column_criteria.

    column_criteria: callable(normalized_lower_header_list) -> bool.
    """
    results = []
    for tb in rec.get("tables", []):
        rows = tb.get("rows", [])
        if not rows:
            continue
        header = [normalize_text(c).lower() if c else "" for c in rows[0]]
        if column_criteria(header):
            results.append((rows[0], rows[1:]))
    return results

# ==================== DSP48E2 Depth (UG579) ====================
def extract_dsp_opmode_config(recs):
    """REAL extraction: scan UG579 for the W/X/Y/Z multiplexer OPMODE-select tables.

    These tables (UG579, "<mux> Multiplexer Output" vs OPMODE[8:0] bit fields) enumerate the
    valid OPMODE configurations of the DSP48E2 datapath. Each emitted row carries a
    "provenance" cite of the source page + table index in the cache.
    """
    def is_opmode_mux_table(header):
        opmode_cols = [h for h in header if "opmode" in h]
        has_mux_out = any("multiplexer" in h and "output" in h for h in header)
        return len(opmode_cols) >= 4 and has_mux_out

    extracted = []
    for rec in recs:
        page = rec.get("page")
        for ti, tb in enumerate(rec.get("tables", [])):
            rows = tb.get("rows", [])
            if not rows:
                continue
            header = [normalize_text(c).lower() if c else "" for c in rows[0]]
            if not is_opmode_mux_table(header):
                continue
            opmode_idx = [i for i, h in enumerate(header) if "opmode" in h]
            mux_idx = next(i for i, h in enumerate(header)
                           if "multiplexer" in h and "output" in h)
            mux_name = (normalize_text(rows[0][mux_idx]).split() or ["?"])[0]
            cite = f"ug579 page {page} table {ti + 1} ({mux_name} multiplexer OPMODE select)"
            for row in rows[1:]:
                if mux_idx >= len(row):
                    continue
                out_val = normalize_text(row[mux_idx])
                if not out_val:
                    continue
                bits = {normalize_text(rows[0][i]).replace("\n", " "): normalize_text(row[i])
                        for i in opmode_idx if i < len(row)}
                extracted.append({
                    "mux": mux_name,
                    "opmode_bits": bits,
                    "output": out_val,
                    "notes": normalize_text(row[mux_idx + 1]) if mux_idx + 1 < len(row) else "",
                    "provenance": cite,
                })
    return extracted

def extract_dsp_modes(recs):
    """
    DSP48E2 configuration depth. OPMODE multiplexer-select config is table-scanned from UG579
    (see extract_dsp_opmode_config — provenance-cited). The pipeline/width/accumulator fields
    below remain curated UG reference constants (full extraction pending) and are labeled
    "curated-constant" so primitives.json never shows them as extracted.
    """
    opmode_config = extract_dsp_opmode_config(recs)
    if opmode_config:
        # one real cite proves the extraction path; reference the page it came from
        provenance = opmode_config[0]["provenance"].rsplit(" table ", 1)[0] \
            + " (OPMODE mux-select tables); pipeline/width fields curated-constant"
    else:
        provenance = "curated-constant"

    dsp_modes = {
        "provenance": provenance,
        # --- extracted (table-scanned, per-row provenance) ---
        "opmode_config": opmode_config,
        # --- curated UG reference constants (full extraction pending) ---
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
    Curated UG reference constants (full extraction pending) for RAMB36E2 / RAMB18E2:
    RAM (single/dual port), FIFO (sync/async), width variants, ECC modes. RAMB36E2 width configs
    (72, 64, 36, 32, 18, 9 bits); RAMB18E2 (36, 32, 18, 9). FIFO depth = memory capacity / width.
    These values are hand-curated from UG573 and tagged "curated-constant" — not table-scanned.
    """
    ramb36_modes = {
        "provenance": "curated-constant",
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
        "provenance": "curated-constant",
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
    Curated UG reference constants (full extraction pending) for URAM288: fixed 72-bit width,
    variable depth via cascading (4Kb to 36Kb per site), ECC modes (SBITERR/DBITERR injection),
    port configuration (independent read/write). Hand-curated from UG573, tagged "curated-constant".
    """
    uram_modes = {
        "provenance": "curated-constant",
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
    Curated UG reference constants (full extraction pending) for GTY/GTH transceivers:
    line rates (1.6–32.75 Gbps), protocol modes (8b10b, 64b66b, PAM4), datawidth (16–64 bit),
    adaptive equalization (CTLE, VGA, DFE), quad PLL (QPLL0/QPLL1). Hand-curated from UG576/578
    and tagged "curated-constant" — not yet table-scanned from the cache.
    """
    gty_modes = {
        "provenance": "curated-constant",
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
        "provenance": "curated-constant",
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
        "provenance": "curated-constant",
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
    Assemble all variants into augment dict: keys are element names, values are variant configs
    ready to merge into configmap.json. Every element carries a "provenance" field — either a real
    UG cite (DSP48E2 OPMODE config, table-scanned) or the honest label "curated-constant".

    Return shape is stable for configmap.py (it reads modes/pipeline_configs/width_variants/
    depth_variants/line_rates/protocols/datawidth_modes/quad_pll_types); the added provenance keys
    are additive and ignored by existing consumers.
    """
    recs = load_cache(CACHE, "ug579*")  # DSP datasheet pages for real OPMODE extraction

    augment = {}

    # DSP48E2 (OPMODE config table-scanned from UG579; remaining fields curated)
    augment["DSP48E2"] = {
        "_augment": "config_variants",
        **extract_dsp_modes(recs)
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

    # Law #13 guarantee: no element ships without an honest provenance label.
    for el, cfg in augment.items():
        cfg.setdefault("provenance", "curated-constant")

    return augment

if __name__ == "__main__":
    augment = build_depth_augment()

    # Save raw variants
    with open(os.path.join(HERE, "depth_variants.json"), "w") as f:
        json.dump(augment, f, indent=2)

    print(f"depth_extractor: {len(augment)} element depth configs")
    for el in sorted(augment.keys()):
        cfg = augment[el]
        modes = cfg.get("modes", [])
        variants = cfg.get("width_variants", [])
        opmode = cfg.get("opmode_config", [])
        extra = f", {len(opmode)} opmode rows (extracted)" if opmode else ""
        print(f"  {el}: {len(modes)} modes, {len(variants)} variants{extra}")
        print(f"      provenance: {cfg.get('provenance')}")
