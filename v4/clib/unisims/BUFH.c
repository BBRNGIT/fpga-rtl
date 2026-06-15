///////////////////////////////////////////////////////////////////////////////
//   ___   ___
//  | _ ) | _ )    Vendor : TeamBB
//  | _ \ | _ \    Version : 0.0.4
//  |___/ |___/    Description : Functional FPGA Library Component
//                          Xilinx Functional Simulation Library Component
//   ___   ___     Filename : BUFH.c
//  | _ ) | _ )    Timestamp : Sun Jun 15 23:30:00  2026
//  | _ \ | _ \
//  |___/ |___/    Source : unisim_src/verilog/src/unisims/BUFH.v
//
///////////////////////////////////////////////////////////////////////////////
// ---
// cell: BUFH
// kind: parts-list-entry
// source: unisim_src/verilog/src/unisims/BUFH.v
// vendor: TeamBB
// version: 0.0.4
// description: Xilinx Functional Simulation Library Component - H Clock Buffer
// built_from_nand: false
// ---
///////////////////////////////////////////////////////////////////////////////
#include "../../lib/verilog.h"

///////////////////////////////////////////////////////////////////////////////
//    Copyright (c) 1995/2004 Xilinx, Inc.
//
//    Licensed under the Apache License, Version 2.0 (the "License");
//    you may not use this file except in compliance with the License.
//    You may obtain a copy of the License at
//
//        http://www.apache.org/licenses/LICENSE-2.0
//
//    Unless required by applicable law or agreed to in writing, software
//    distributed under the License is distributed on an "AS IS" BASIS,
//    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//    See the License for the specific language governing permissions and
//    limitations under the License.
///////////////////////////////////////////////////////////////////////////////
// Revision:
//    04/08/08 - Initial version.
//    09/09/08 - Change to use BUFHCE according to yaml.
//    11/11/08 - Change to not use BUFHCE.
//    12/13/11 - Added `celldefine and `endcelldefine (CR 524859).
// End Revision

timescale(1 ps, 1 ps);

celldefine;

module(BUFH)(output O, input I)
{
#ifdef XIL_TIMING

    parameter LOC = " UNPLACED";
    reg notifier;

#endif

    /* buf B1 (O, I); — Verilog buf gate instantiation */

#ifdef XIL_TIMING

    specify
        (I => O) = (0:0:0, 0:0:0);
	$period (posedge I, 0:0:0, notifier);
        specparam PATHPULSE$ = 0;
    endspecify

#endif
}

endmodule;

endcelldefine;
