///////////////////////////////////////////////////////////////////////////////
//   ___   ___
//  | _ ) | _ )    Vendor : TeamBB
//  | _ \ | _ \    Version : 0.0.4
//  |___/ |___/    Description : Functional FPGA Library Component
//                          Global Simulation Signals
//   ___   ___     Filename : glbl.c
//  | _ ) | _ )    Timestamp : Mon Jun 16 00:00:00 UTC 2026
//  | _ \ | _ \
//  |___/ |___/    Source : unisim_src/verilog/src/glbl.v
//
///////////////////////////////////////////////////////////////////////////////
// ---
// cell: glbl
// kind: parts-list-entry
// source: unisim_src/verilog/src/glbl.v
// vendor: TeamBB
// version: 0.0.4
// description: Global Simulation Signals
// ports: internal only (no external ports)
// params: ROC_WIDTH, TOC_WIDTH, GRES_WIDTH, GRES_START
// function: Provides global control signals for FPGA simulation and initialization
// built_from_nand: false
// ---
//
// Description : Global Simulation Signals
//
// Revision:
//    06/16/26 - Transcribed glbl.v -> glbl.c (TeamBB parts-list entry).
///////////////////////////////////////////////////////////////////////////////
#include "../../lib/verilog.h"

timescale(1 ps, 1 ps)

celldefine

module(glbl)()
{
    parameter ROC_WIDTH = 100000;
    parameter TOC_WIDTH = 0;
    parameter GRES_WIDTH = 10000;
    parameter GRES_START = 10000;

    wire GSR;
    wire GTS;
    wire GWE;
    wire PRLD;
    wire GRESTORE;
    tri1 p_up_tmp;
    tri (weak1, strong0) PLL_LOCKG = p_up_tmp;

    wire PROGB_GLBL;
    wire CCLKO_GLBL;
    wire FCSBO_GLBL;
    wire_bits(DO_GLBL, 3, 0);
    wire_bits(DI_GLBL, 3, 0);

    var GSR_int;
    var GTS_int;
    var PRLD_int;
    var GRESTORE_int;

    wire JTAG_TDO_GLBL;
    wire JTAG_TCK_GLBL;
    wire JTAG_TDI_GLBL;
    wire JTAG_TMS_GLBL;
    wire JTAG_TRST_GLBL;

    reg JTAG_CAPTURE_GLBL;
    reg JTAG_RESET_GLBL;
    reg JTAG_SHIFT_GLBL;
    reg JTAG_UPDATE_GLBL;
    reg JTAG_RUNTEST_GLBL;

    var JTAG_SEL1_GLBL = _1b0;
    var JTAG_SEL2_GLBL = _1b0;
    var JTAG_SEL3_GLBL = _1b0;
    var JTAG_SEL4_GLBL = _1b0;

    var JTAG_USER_TDO1_GLBL = _1bz;
    var JTAG_USER_TDO2_GLBL = _1bz;
    var JTAG_USER_TDO3_GLBL = _1bz;
    var JTAG_USER_TDO4_GLBL = _1bz;

    assign (strong1, weak0) GSR = GSR_int;
    assign (strong1, weak0) GTS = GTS_int;
    assign (weak1, weak0) PRLD = PRLD_int;
    assign (strong1, weak0) GRESTORE = GRESTORE_int;

    initial begin
        GSR_int = _1b1;
        PRLD_int = _1b1;
        DELAY(ROC_WIDTH)
        GSR_int = _1b0;
        PRLD_int = _1b0;
    end

    initial begin
        GTS_int = _1b1;
        DELAY(TOC_WIDTH)
        GTS_int = _1b0;
    end

    initial begin
        GRESTORE_int = _1b0;
        DELAY(GRES_START);
        GRESTORE_int = _1b1;
        DELAY(GRES_WIDTH);
        GRESTORE_int = _1b0;
    end
}

endmodule

endcelldefine
