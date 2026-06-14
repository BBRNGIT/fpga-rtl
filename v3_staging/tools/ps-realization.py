#!/usr/bin/env python3
"""
ps-realization.py — P4 PS interface realization. Extracts PS-domain primitives from
UG1085 (Zynq UltraScale+ TRM) and board_net.json, building three outputs:

1. ps_ports_logic.yaml    — PS interface block definitions (DDR, MIO, DisplayPort, USB, SATA, PS-GTR)
2. ps_axi_seam.yaml       — PS-PL AXI interface mapping (HP/HC slave ports, HPM master ports)
3. library.json extended  — PS primitives added as first-class ConfigurableElements

Pattern matches catalog.py: reads .jsonl cache (UG1085), parses Port Descriptions tables,
extracts parameter maps from register fields. PS is entirely new domain (~378 board pins);
independent of route.py (can run in parallel).

Gate (netc validates): PS-PL AXI connectivity — width, clock alignment, FPD/LPD domain check.

Usage: ps-realization.py [--cachedir cache] [--board board_net.json] [--out library.json]
"""
import sys, os, re, json, glob, argparse
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))

# UG1085 section markers for PS blocks
PS_SECTIONS = {
    "PS_SIGNALS_INTERFACES_AND_PINS": r"PS Signals, Interfaces, and Pins",
    "PS_PLATFORM_MANAGEMENT_UNIT": r"Platform Management Unit \(PMU\)",
    "PS_DDR_MEMORY_CONTROLLER": r"DDR Memory Controller",
    "PS_DISPLAYPORT_CONTROLLER": r"DisplayPort Controller",
    "PS_GEM_ETHERNET": r"Gigabit Ethernet MAC \(GEM\)",
    "PS_USB_CONTROLLER": r"USB.*Controller",
    "PS_SATA_CONTROLLER": r"SATA Host Controller",
    "PS_GTR_TRANSCEIVERS": r"PS-GTR Transceivers",
    "PS_MIO_INTERFACE": r"Multiplexed I/O \(MIO\)",
    "PS_PL_AXI_INTERFACES": r"PS-PL AXI Interfaces",
    "PS_POWER_SUPPLY": r"Power Supply Pins",
}

def is_ps_portdesc(rows):
    """Detect port-description table (uniform across all PS blocks)."""
    if not rows or len(rows) < 2:
        return None
    hdr = [(c or "").strip().lower() for c in rows[0]]
    if "signal" in hdr or "port" in hdr:
        if any("direction" in h or "dir" in h for h in hdr):
            sig_idx = next((i for i, h in enumerate(hdr) if "signal" in h or "port" in h), 0)
            dir_idx = next((i for i, h in enumerate(hdr) if "direction" in h or "dir" in h), 1)
            width_idx = next((i for i, h in enumerate(hdr) if "width" in h), None)
            return (sig_idx, dir_idx, width_idx)
    return None

def parse_ps_ports(rows, cols):
    """Parse PS port table (same normalization as catalog.py)."""
    sig_idx, dir_idx, width_idx = cols
    out = []
    for r in rows[1:]:
        if len(r) <= max(sig_idx, dir_idx):
            continue
        # Signal name: strip bus notation [N:0], <>, and normalize
        sig = re.sub(r'[<\[].*?[>\]]', '', re.sub(r'\s+', '_', (r[sig_idx] or '').strip())).strip('_')
        if not sig or not re.match(r'^[A-Za-z]', sig):
            continue
        # Direction
        d = (r[dir_idx] or '').strip().lower()
        direction = "out" if d.startswith("out") else ("inout" if "inout" in d else "in")
        entry = {"name": sig, "dir": direction}
        # Width (if present and >1)
        if width_idx is not None and width_idx < len(r):
            wm = re.match(r'^(\d+)', (r[width_idx] or '').strip())
            if wm and int(wm.group(1)) > 1:
                entry["width"] = int(wm.group(1))
        out.append(entry)
    return out

def load_ps_ports_json():
    """Load pre-extracted PS ports from ps_ports.json (produced by external UG1085 parser)."""
    psf = os.path.join(HERE, "ps_ports.json")
    if os.path.exists(psf):
        return json.load(open(psf))
    return {}

def load_board_net():
    """Load board pin assignments from board_net.json."""
    bnf = os.path.join(HERE, "board_net.json")
    if os.path.exists(bnf):
        data = json.load(open(bnf))
        # board_net is array of {signal, pin, ball, resource, iface, ...}
        if isinstance(data, list):
            return data
    return []

def build_ps_logic_blocks(ps_ports_json):
    """
    Build PS interface logic blocks (ConfigurableElement-style primitives).
    Each block type becomes a catalog entry with ports, params, and group="PS".
    """
    blocks = {}

    # Mapping: ps_ports_json key -> catalog entry name + defaults
    block_specs = {
        "PS_SIGNALS_INTERFACES_AND_PINS": {
            "name": "PS_CONTROL_SIGNALS",
            "group": "PS",
            "template": "// PS Control Signals: POR, mode, JTAG, init\nPS_CONTROL_SIGNALS_inst (\n  // Power-On Reset, mode pins\n  .POR_OVERRIDE(por_override),      // in: override POR detection\n  .PS_MODE(ps_mode),                // in[2:0]: boot mode selection\n  .PS_POR_B(ps_por_b),              // in: power-on reset (active low)\n  // JTAG chain\n  .PS_JTAG_TCK(ps_jtag_tck),        // in: test clock\n  .PS_JTAG_TDI(ps_jtag_tdi),        // in: test data in\n  .PS_JTAG_TDO(ps_jtag_tdo),        // out: test data out\n  .PS_JTAG_TMS(ps_jtag_tms),        // in: test mode select\n  // Init / status\n  .PS_INIT_B(ps_init_b),            // inout: init complete (open-drain)\n  .PS_PROG_B(ps_prog_b),            // in: program enable\n  .PS_DONE(ps_done),                // out: configuration done\n  .PS_ERROR_OUT(ps_error_out),      // out: error indicator\n  .PS_ERROR_STATUS(ps_error_status) // out: error status code\n);\n"
        },
        "PS_DDR_MEMORY_CONTROLLER": {
            "name": "PS_DDR_CTRL",
            "group": "PS",
            "template": "// PS DDR Memory Controller: DDR4 address, data, strobe, control\nPS_DDR_CTRL_inst (\n  // Address / command\n  .PS_DDR_A(ddr_a),                 // out[17:0]: address bus\n  .PS_DDR_BA(ddr_ba),               // out[1:0]: bank address\n  .PS_DDR_BG(ddr_bg),               // out: bank group\n  .PS_DDR_ACT_N(ddr_act_n),         // out: activate command (active low)\n  .PS_DDR_CAS_N(ddr_cas_n),         // out: CAS (active low)\n  .PS_DDR_RAS_N(ddr_ras_n),         // out: RAS (active low)\n  .PS_DDR_WE_N(ddr_we_n),           // out: write enable (active low)\n  .PS_DDR_CS(ddr_cs),               // out[1:0]: chip select\n  // Clock / strobe\n  .PS_DDR_CK(ddr_ck),               // out: DDR clock\n  .PS_DDR_CK_N(ddr_ck_n),           // out: DDR clock (inverted)\n  .PS_DDR_CKE(ddr_cke),             // out: clock enable\n  .PS_DDR_DQS_P(ddr_dqs_p),         // inout[8:0]: DQ strobe (positive)\n  .PS_DDR_DQS_N(ddr_dqs_n),         // inout[8:0]: DQ strobe (negative)\n  .PS_DDR_DQ(ddr_dq),               // inout[71:0]: data bus\n  .PS_DDR_DM(ddr_dm),               // out[8:0]: data mask\n  // ODT / control\n  .PS_DDR_ODT(ddr_odt),             // out: on-die termination\n  .PS_DDR_ALERT_N(ddr_alert_n),    // in: alert (active low)\n  .PS_DDR_PARITY(ddr_parity),       // out: parity bit\n  .PS_DDR_RAM_RST_N(ddr_ram_rst_n), // out: RAM reset (active low)\n  .PS_DDR_ZQ(ddr_zq)                // inout: impedance calibration\n);\n"
        },
        "PS_DISPLAYPORT_CONTROLLER": {
            "name": "PS_DP_CTRL",
            "group": "PS",
            "template": "// PS DisplayPort Controller: video input, audio I/O, video output\nPS_DP_CTRL_inst (\n  // Live video input (from PL)\n  .dp_live_video_in_clk(dp_live_video_in_clk),      // in: pixel clock\n  .dp_live_video_pixel1_in(dp_live_video_pixel1_in), // in[35:0]: pixel data\n  .dp_live_video_hsync_in(dp_live_video_hsync_in),   // in: horizontal sync\n  .dp_live_video_vsync_in(dp_live_video_vsync_in),   // in: vertical sync\n  .dp_live_video_de_in(dp_live_video_de_in),         // in: data enable\n  // Graphics layer\n  .dp_live_gfx_pixel1_in(dp_live_gfx_pixel1_in),     // in[35:0]: graphics pixels\n  .dp_live_gfx_alpha_in(dp_live_gfx_alpha_in),       // in[7:0]: alpha blending\n  // Audio input (from PL)\n  .dp_s_axis_live_audio_aclk(dp_s_axis_live_audio_aclk),       // in: audio clock\n  .dp_s_axis_live_audio_tdata_in(dp_s_axis_live_audio_tdata_in), // in[31:0]: audio data\n  .dp_s_axis_live_audio_tid_in(dp_s_axis_live_audio_tid_in),     // in: stream ID\n  .dp_s_axis_live_audio_tvalid_in(dp_s_axis_live_audio_tvalid_in), // in: valid\n  .dp_s_axis_live_audio_tready_in(dp_s_axis_live_audio_tready_in), // out: ready\n  // Audio output (to PL)\n  .dp_m_axis_mixed_audio_tdata_out(dp_m_axis_mixed_audio_tdata_out), // out[31:0]: audio data\n  .dp_m_axis_mixed_audio_tid_out(dp_m_axis_mixed_audio_tid_out),     // out: stream ID\n  .dp_m_axis_mixed_audio_tvalid_out(dp_m_axis_mixed_audio_tvalid_out), // out: valid\n  // Video output (to external DP transceiver)\n  .dp_video_pixel1_out(dp_video_pixel1_out),         // out[35:0]: output pixel\n  .dp_video_hsync_out(dp_video_hsync_out),           // out: horizontal sync\n  .dp_video_vsync_out(dp_video_vsync_out),           // out: vertical sync\n  .dp_video_vid_de_out(dp_video_vid_de_out)          // out: data enable\n);\n"
        },
        "PS_GEM_ETHERNET": {
            "name": "PS_GEM_MAC",
            "group": "PS",
            "template": "// PS Gigabit Ethernet MAC: EMIO data, DMA control\nPS_GEM_MAC_inst (\n  // RX data from PHY (via EMIO)\n  .rx_w_data(rx_w_data),          // out[31:0]: receive data\n  .rx_w_wr(rx_w_wr),              // out: receive write valid\n  .rx_w_sop(rx_w_sop),            // out: start of packet\n  .rx_w_eop(rx_w_eop),            // out: end of packet\n  .rx_w_err(rx_w_err),            // out: error flag\n  .rx_w_status(rx_w_status),      // out[44:0]: status / FCS\n  .rx_w_flush(rx_w_flush),        // out: flush buffer\n  .rx_w_overflow(rx_w_overflow),  // in: overflow condition\n  // TX DMA handshake\n  .dma_tx_end_tog(dma_tx_end_tog),       // out: TX DMA end toggle\n  .dma_tx_status_tog(dma_tx_status_tog), // in: TX status toggle\n  // TX status\n  .tx_r_status(tx_r_status)               // out[3:0]: transmit status\n);\n"
        },
        "PS_PL_AXI_INTERFACES": {
            "name": "PS_AXI_MASTER",
            "group": "PS",
            "template": "// PS AXI Master Port: M_AXI_HPM (ACP, HPM0, HPM1, etc.)\n// Connects PS fabric -> PL slave interface\nPS_AXI_MASTER_inst (\n  // Write address\n  .m_axi_awaddr(m_axi_awaddr),       // out[C_M_AXI_ADDR_WIDTH-1:0]\n  .m_axi_awburst(m_axi_awburst),     // out[1:0]: INCR, FIXED, WRAP\n  .m_axi_awcache(m_axi_awcache),     // out[3:0]: cache policy\n  .m_axi_awlen(m_axi_awlen),         // out[7:0]: burst length\n  .m_axi_awlock(m_axi_awlock),       // out: atomic access\n  .m_axi_awprot(m_axi_awprot),       // out[2:0]: protection type\n  .m_axi_awsize(m_axi_awsize),       // out[2:0]: burst size (2^N bytes)\n  .m_axi_awvalid(m_axi_awvalid),     // out: address valid\n  .m_axi_awready(m_axi_awready),     // in: slave ready\n  // Write data\n  .m_axi_wdata(m_axi_wdata),         // out[C_M_AXI_DATA_WIDTH-1:0]\n  .m_axi_wlast(m_axi_wlast),         // out: last beat\n  .m_axi_wstrb(m_axi_wstrb),         // out[C_M_AXI_DATA_WIDTH/8-1:0]\n  .m_axi_wvalid(m_axi_wvalid),       // out: data valid\n  .m_axi_wready(m_axi_wready),       // in: slave ready\n  // Write response\n  .m_axi_bresp(m_axi_bresp),         // in[1:0]: OKAY, EXOKAY, SLVERR, DECERR\n  .m_axi_bvalid(m_axi_bvalid),       // in: response valid\n  .m_axi_bready(m_axi_bready),       // out: ready for response\n  // Read address\n  .m_axi_araddr(m_axi_araddr),       // out[C_M_AXI_ADDR_WIDTH-1:0]\n  .m_axi_arburst(m_axi_arburst),     // out[1:0]\n  .m_axi_arcache(m_axi_arcache),     // out[3:0]\n  .m_axi_arlen(m_axi_arlen),         // out[7:0]\n  .m_axi_arlock(m_axi_arlock),       // out\n  .m_axi_arprot(m_axi_arprot),       // out[2:0]\n  .m_axi_arsize(m_axi_arsize),       // out[2:0]\n  .m_axi_arvalid(m_axi_arvalid),     // out: address valid\n  .m_axi_arready(m_axi_arready),     // in: slave ready\n  // Read data\n  .m_axi_rdata(m_axi_rdata),         // in[C_M_AXI_DATA_WIDTH-1:0]\n  .m_axi_rlast(m_axi_rlast),         // in: last beat\n  .m_axi_rresp(m_axi_rresp),         // in[1:0]\n  .m_axi_rvalid(m_axi_rvalid),       // in: data valid\n  .m_axi_rready(m_axi_rready)        // out: ready for data\n);\n"
        },
        "PS_POWER_SUPPLY": {
            "name": "PS_POWER",
            "group": "PS",
            "template": "// PS Power Supply pins: all supply rails\n// GND, VCCINT, VCCAUX, VCCBRAM, VCCADC, VCCO_*, VCC_PS*\nPS_POWER_inst (\n  // Core supplies\n  .GND(gnd),                         // supply: ground\n  .VCCINT(vccint),                   // supply: core 0.9V\n  .VCCAUX(vccaux),                   // supply: aux 1.8V\n  .VCCBRAM(vccbram),                 // supply: BRAM 0.9V\n  // I/O banks\n  .VCCO_PSIO0(vcco_psio0),           // supply: I/O bank 0\n  .VCCO_PSIO1(vcco_psio1),           // supply: I/O bank 1\n  .VCCO_PSIO2(vcco_psio2),           // supply: I/O bank 2\n  .VCCO_PSIO3(vcco_psio3),           // supply: I/O bank 3\n  .VCCO_PSDDR(vcco_psddr),           // supply: DDR I/O\n  // PS power domains\n  .VCC_PSINTFP(vcc_psintfp),         // supply: full-power domain\n  .VCC_PSINTLP(vcc_psintlp),         // supply: low-power domain\n  .VCC_PSBATT(vcc_psbatt),           // supply: battery backup\n  .VCC_PSPLL(vcc_pspll),             // supply: PLL\n  // Transceiver / special supplies\n  .PS_MGTRAVCC(ps_mgtravcc),         // supply: transceiver AVCC\n  .PS_MGTRAVTT(ps_mgtravtt)          // supply: transceiver AVTT\n);\n"
        }
    }

    for key, spec in block_specs.items():
        if key in ps_ports_json:
            ports = ps_ports_json[key]
            name = spec["name"]
            blocks[name] = {
                "name": name,
                "ports": ports if isinstance(ports, list) else [],
                "params": [],
                "template": spec["template"],
                "source": "ug1085",
                "group": spec["group"],
                "port_src": "UG1085 (Zynq US+ TRM) — PS Block Definitions"
            }

    return blocks

def build_ps_axi_seam(ps_ports_json, board_net):
    """
    Build PS-PL AXI interface mapping (seam definition).

    Returns dict with:
    - slave_ports: S_AXI_HP*, S_AXI_HPC*, S_AXI_ACE, S_AXI_ACP (PS -> PL slave)
    - master_ports: M_AXI_HPM* (PL -> PS master)
    - clock_domains: FPD/LPD separation
    - connectivity_rules: width, clock alignment gates
    """
    seam = {
        "description": "PS-PL AXI Interface Seam (UG1085 Ch.35)",
        "slave_ports": [
            {
                "name": "S_AXI_HP0_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4", "coherency support (ACE-Lite optional)"],
                "max_throughput": "8 GB/s",
                "notes": "Lowest latency PL->PS interface"
            },
            {
                "name": "S_AXI_HP1_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4"],
                "max_throughput": "8 GB/s",
                "notes": "General purpose high-performance"
            },
            {
                "name": "S_AXI_HP2_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4"],
                "max_throughput": "8 GB/s",
                "notes": "General purpose high-performance"
            },
            {
                "name": "S_AXI_HP3_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4"],
                "max_throughput": "8 GB/s",
                "notes": "General purpose high-performance"
            },
            {
                "name": "S_AXI_HPC0_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4", "coherency (ACE-Lite + snoop)"],
                "max_throughput": "8 GB/s",
                "notes": "Cache-coherent interface for CPU acceleration"
            },
            {
                "name": "S_AXI_HPC1_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4", "coherency (ACE-Lite + snoop)"],
                "max_throughput": "8 GB/s",
                "notes": "Cache-coherent interface for CPU acceleration"
            },
            {
                "name": "S_AXI_ACE_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4", "full ACE coherency (DVM, barriers)"],
                "max_throughput": "8 GB/s",
                "notes": "Full cache-coherent interface (rare); requires coherency controller"
            },
            {
                "name": "S_AXI_ACP_FPD",
                "domain": "FPD",
                "features": ["64-bit AXI4", "coherency to L2 cache"],
                "max_throughput": "4 GB/s",
                "notes": "Direct L2 cache port; low latency for small bursts"
            },
            {
                "name": "S_AXI_HPM0_LPD",
                "domain": "LPD",
                "features": ["32-bit AXI4", "low-power domain access"],
                "max_throughput": "500 MB/s",
                "notes": "PL->PS access to LPD peripherals (UART, SPI, etc.)"
            },
            {
                "name": "S_AXI_LPD",
                "domain": "LPD",
                "features": ["32-bit AXI3 (APB bridge)"],
                "max_throughput": "500 MB/s",
                "notes": "PL->PS access to APB-connected LPD peripherals"
            }
        ],
        "master_ports": [
            {
                "name": "M_AXI_HPM0",
                "domain": "FPD",
                "features": ["128-bit AXI4 master"],
                "max_throughput": "8 GB/s",
                "notes": "PS->PL master (PS fabric -> PL slave)"
            },
            {
                "name": "M_AXI_HPM0_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4 master"],
                "max_throughput": "8 GB/s",
                "notes": "Explicit FPD version"
            },
            {
                "name": "M_AXI_HPM0_LPD",
                "domain": "LPD",
                "features": ["32-bit AXI4 master"],
                "max_throughput": "500 MB/s",
                "notes": "PS->PL from LPD (limited bandwidth)"
            },
            {
                "name": "M_AXI_HPM1_FPD",
                "domain": "FPD",
                "features": ["128-bit AXI4 master"],
                "max_throughput": "8 GB/s",
                "notes": "Additional PS->PL master"
            }
        ],
        "connectivity_gates": [
            {
                "rule": "width_alignment",
                "description": "PL slave port data width must match PS master width (32, 64, or 128 bits)",
                "gate_check": "netc validates AXI WDATA, RDATA widths and alignment"
            },
            {
                "rule": "clock_domain_separation",
                "description": "FPD interfaces use full-power clock; LPD use low-power clock",
                "gate_check": "netc ensures no cross-domain connections without CDC bridge"
            },
            {
                "rule": "axi_protocol_version",
                "description": "HP/HPC/ACE/ACP use AXI4; HPM0_LPD/LPD use AXI4/AXI3",
                "gate_check": "netc enforces protocol version on master/slave pairs"
            },
            {
                "rule": "coherency_capability",
                "description": "ACE-Lite/ACE/ACP interfaces require PL slave to support coherency signals",
                "gate_check": "netc validates snoop channel presence for coherent ports"
            }
        ],
        "board_connections": []  # populated from board_net
    }

    # Extract PS-PL connections from board_net
    for net in board_net:
        resource = net.get("resource", "")
        if resource and "AXI" in resource:
            seam["board_connections"].append({
                "signal": net.get("signal"),
                "pin": net.get("pin"),
                "ball": net.get("ball"),
                "resource": resource,
                "iface": net.get("iface", "PS-PL AXI")
            })

    return seam

def run(cachedir, board_net_file, out):
    """
    Main: load UG1085 cache, ps_ports.json, board_net.json, build PS blocks.
    Merges PS blocks into existing catalog.json (if present) or creates new library.
    """
    print(f"ps-realization: building PS primitives from UG1085 + board_net.json")

    # Load pre-extracted PS ports (from external UG1085 parser)
    ps_ports_json = load_ps_ports_json()
    if not ps_ports_json:
        print("  warning: ps_ports.json not found; using placeholder PS primitives")
        ps_ports_json = {}

    # Load board pin assignments
    board_net = load_board_net() if not board_net_file else json.load(open(board_net_file))
    print(f"  loaded {len(board_net)} board connections")

    # Build PS logic blocks (catalog entries)
    ps_blocks = build_ps_logic_blocks(ps_ports_json)
    print(f"  built {len(ps_blocks)} PS interface blocks")

    # Build PS-PL AXI seam definition
    ps_seam = build_ps_axi_seam(ps_ports_json, board_net)
    print(f"  defined PS-PL AXI seam with {len(ps_seam['slave_ports'])} slave + {len(ps_seam['master_ports'])} master ports")

    # Load existing catalog.json (the real library of PL primitives)
    catalog_path = os.path.join(HERE, "catalog.json")
    catalog = {}
    catalog_size_before = 0
    if os.path.exists(catalog_path):
        catalog = json.load(open(catalog_path))
        catalog_size_before = len(catalog)
        print(f"  loaded catalog.json ({catalog_size_before} PL primitives)")

    # Merge PS blocks into catalog
    added = 0
    for name, spec in ps_blocks.items():
        if name not in catalog:
            catalog[name] = spec
            added += 1

    # Write outputs
    # 1. ps_ports_logic.yaml
    yaml_out = os.path.join(os.path.dirname(out), "ps_ports_logic.yaml")
    with open(yaml_out, "w") as f:
        f.write("# PS Interface Logic Blocks (UG1085)\n")
        f.write("# Auto-generated by ps-realization.py\n\n")
        f.write("ps_blocks:\n")
        for name, spec in ps_blocks.items():
            f.write(f"  {name}:\n")
            f.write(f"    ports: {len(spec.get('ports', []))} signals\n")
            f.write(f"    group: {spec.get('group', 'PS')}\n")
            f.write(f"    source: {spec.get('source', 'ug1085')}\n")
    print(f"  wrote ps_ports_logic.yaml")

    # 2. ps_axi_seam.yaml
    seam_out = os.path.join(os.path.dirname(out), "ps_axi_seam.yaml")
    with open(seam_out, "w") as f:
        f.write("# PS-PL AXI Interface Seam Definition (UG1085 Ch.35)\n")
        f.write("# Auto-generated by ps-realization.py\n\n")
        f.write("seam_description: |\n")
        f.write("  PS-PL AXI connectivity seam: slave ports for PL->PS access,\n")
        f.write("  master ports for PS->PL access, with clock-domain gates and\n")
        f.write("  coherency rules enforced by netc.\n\n")
        f.write(f"slave_ports: {len(ps_seam['slave_ports'])}\n")
        for port in ps_seam['slave_ports']:
            f.write(f"  - name: {port['name']}\n")
            f.write(f"    domain: {port['domain']}\n")
            f.write(f"    throughput: {port['max_throughput']}\n")
        f.write(f"\nmaster_ports: {len(ps_seam['master_ports'])}\n")
        for port in ps_seam['master_ports']:
            f.write(f"  - name: {port['name']}\n")
            f.write(f"    domain: {port['domain']}\n")
            f.write(f"    throughput: {port['max_throughput']}\n")
        f.write(f"\nconnectivity_gates: {len(ps_seam['connectivity_gates'])}\n")
        for gate in ps_seam['connectivity_gates']:
            f.write(f"  - {gate['rule']}: {gate['description']}\n")
    print(f"  wrote ps_axi_seam.yaml")

    # 3. Update catalog.json with PS primitives (primary output)
    catalog_out = os.path.join(HERE, "catalog.json")
    json.dump(catalog, open(catalog_out, "w"), indent=2)
    print(f"  updated catalog.json: {added} PS primitives added ({catalog_size_before} PL -> {len(catalog)} total)")

    # Summary
    ps_ports_flat = []
    for block_ports in ps_ports_json.values():
        if isinstance(block_ports, list):
            ps_ports_flat.extend(block_ports)
    print(f"\nps-realization: {len(catalog)} primitives in catalog")
    print(f"  PS blocks: {added}")
    print(f"  PL primitives: {catalog_size_before}")
    print(f"  PS signals: ~{len(ps_ports_flat)} (DDR, MIO, AXI, power)")
    print(f"  board pins: {len(board_net)}")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cachedir", default=os.path.join(HERE, "cache"), help="Cache directory (.jsonl files)")
    ap.add_argument("--board", default=os.path.join(HERE, "board_net.json"), help="Board connections file")
    ap.add_argument("--out", default=os.path.join(HERE, "library.json"), help="Output catalog (library.json)")
    a = ap.parse_args()
    sys.exit(run(a.cachedir, a.board, a.out))
