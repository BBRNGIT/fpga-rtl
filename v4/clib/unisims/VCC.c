///////////////////////////////////////////////////////////////////////////////
//   ___   ___
//  | _ ) | _ )    Vendor : TeamBB
//  | _ \ | _ \    Version : 0.0.4
//  |___/ |___/    Description : Functional FPGA Library Component
//                          VCC Connection (constant high)
//   ___   ___     Filename : VCC.c
//  | _ ) | _ )    Timestamp : Mon Jun 16 00:00:00 UTC 2026
//  | _ \ | _ \
//  |___/ |___/    Source : unisim_src/verilog/src/unisims/VCC.v
//
///////////////////////////////////////////////////////////////////////////////
// ---
// cell: VCC
// kind: parts-list-entry
// source: unisim_src/verilog/src/unisims/VCC.v
// vendor: TeamBB
// version: 0.0.4
// description: VCC Connection (constant high)
// ports: output P
// params: none
// function: Drives output P to constant logic 1
// built_from_nand: false
// ---
//
// Description : VCC Connection (constant high)
//
// Revision:
//    03/23/04 - Initial version. (from VCC.v)
//    05/23/07 - Changed timescale to 1 ps / 1 ps. (from VCC.v)
//    12/13/11 - Added `celldefine and `endcelldefine (CR 524859). (from VCC.v)
//    06/16/26 - Transcribed VCC.v -> VCC.c (TeamBB parts-list entry).
///////////////////////////////////////////////////////////////////////////////
#include "../../lib/verilog.h"

timescale(1 ps, 1 ps)

celldefine

module(VCC)(net *P)  /* P is output */
{
    /* Verilog: assign P = 1'b1;
     * C equivalent: drive P to constant high
     * (P is a pointer; assign to its contents) */
    P->level = HI;
}

endmodule

endcelldefine
