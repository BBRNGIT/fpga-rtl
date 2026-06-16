/* verilog.h — the Verilog vocabulary, defined in C.
 *
 * The UNISIM .v files are our FPGA's parts list. We transcribe each .v into a .c
 * that reads like the Verilog AND compiles as C. The Verilog tokens that aren't
 * native C (`timescale, module, output, parameter, assign, 1'b0, ...) are DEFINED
 * here, once, so a parts-list .c can use them verbatim-in-shape and still be C.
 *
 * This is NOT the build. No NAND, no gate decomposition. These definitions only
 * carry the .v's DESCRIPTION (names, ports, connections, params) faithfully into a
 * compilable C form. The real parts get built (from NAND) in a later phase.
 *
 * Grown on demand: each new cell that needs a construct C lacks adds it here.
 */
#ifndef VERILOG_H
#define VERILOG_H

/* ---- Link to real components first (for level, wire definitions) --------- */
#include "components.h"

/* ---- Use level from components.h (4-state logic: 0/1/x/z) --------- */
/* wire from components.h IS the actual signal type */
typedef wire net;  /* Alias: net = wire (for Verilog compatibility) */
typedef wire var;  /* Alias: var = wire (Verilog `reg` = storage variable, simulation-only) */

/* ---- Verilog-style sized binary literals: 1'b0, 1'b1, 1'bx, 1'bz ----------- */
/* Usage in C: reg X = _1b0; (declaration) or X = _1b0; (assignment)
 * Compound literals (net){...} work in both contexts. */
#define _1b0  (net){ LO }    /* 1'b0: 1-bit binary 0 */
#define _1b1  (net){ HI }    /* 1'b1: 1-bit binary 1 */
#define _1bx  (net){ X }     /* 1'bx: 1-bit binary X (don't-care) */
#define _1bz  (net){ Z }     /* 1'bz: 1-bit binary Z (high-impedance) */

/* ---- directives -----------------------------------------------------------
 * `timescale and `celldefine are simulation/tool markers with no runtime effect;
 * we define them so the line is valid C and the description is preserved. */
#define timescale(unit, prec)        /* `timescale <unit> / <prec> : sim time unit (marker) */
#define celldefine                   /* `celldefine    : cell-boundary marker */
#define endcelldefine                /* `endcelldefine : end cell-boundary marker */

/* ---- module / endmodule : a part. The part is a C function with net pointers.
 * `module(NAME)(ports)` opens it; `endmodule` closes it.
 * Ports are C parameters (net *), direction is documented in YAML/comments. */
#define module(name)   void name      /* module(NAME)(ports) -> void NAME(ports) */
#define endmodule                      /* the closing brace is written explicitly */

/* ---- ports : a port is a net (wire/net *) the part connects to.
 * Direction (input, output, inout) is declared in YAML metadata, not in C macro.
 * This avoids macro conflicts in the parameter list. */
#define output                         /* output PORT: documented in YAML */
#define input                          /* input PORT: documented in YAML */
#define inout                          /* inout PORT: documented in YAML */

/* ---- parameter : a named constant of the part (string or value). ----------- */
#define parameter  static const int    /* parameter X = V; -> a named constant (type: int) */
#define parameter_str  static const char *  /* parameter_str X = "V"; -> string parameter */

/* ---- wire, reg : signal types (from components.h) -----
 * wire and reg are actual type names from components.h, not macros.
 * wire X; declares X as a wire (4-state signal)
 * reg X; declares X as a reg (storage variable, initialized from wire) */
/* No macros needed — use the types directly from components.h */

/* ---- localparam : local constant (similar to parameter but local scope) ------- */
#define localparam  static const int   /* localparam X = V; -> a local constant (type: int) */

/* ---- tri0 : tri-state net with pull-down to logic 0 (Xilinx test signal) ----- */
#define tri0   net                   /* tri0 X = init; -> a net with pull-down */

/* ---- bit vectors: [hi:lo] notation (bit range specification, preserved exactly) */
/* Verilog vectors use [hi:lo] notation to specify the bit range (e.g., [3:0] = bits 3,2,1,0).
 * In C, we preserve this notation as written because it carries semantic meaning beyond just size.
 * The bit range appears in the C code verbatim, with understanding that the .v structure IS preserved.
 * Example: wire [3:0] X; in .v becomes wire [3:0] X; in .c (no reinterpretation). */
/* NOTE: The compiler sees [3:0] as a C array size [4], but the citation comment preserves the .v. */

/* ---- drive strength constants: strong0, weak0, pull0, highz0 / strong1, weak1, pull1, highz1 */
/* Verilog drive strength models electrical output characteristics (tri-state, open-collector).
 * Examples: (strong1, weak0) = drives 1 strongly, 0 weakly (pull-up)
 *           (weak1, strong0) = drives 1 weakly, 0 strongly (open-drain)
 * Defined as enum constants so they work as identifiers in (s0, s1) notation. */
enum { strong0, weak0, pull0, highz0, strong1, weak1, pull1, highz1 };

/* ---- bit range vectors: wire [hi:lo] notation ----------------------------------------- */
/* Verilog: wire [3:0] DO_GLBL;  means a 4-bit vector with bits indexed 3,2,1,0
 * C representation: wire_bits(DO_GLBL, 3, 0);  preserves the range [3:0] semantically */
#define wire_bits(name, hi, lo)  net name[((hi)-(lo)+1)]  /* wire [hi:lo] name; */

/* ---- tri / tri1 / tri0 : tri-state net types with drive strength -------------------- */
/* Usage: tri(weak1, strong0) X = init;  (function-like macro consumes drive strength)
 * The drive strength (s0, s1) is recorded in the source code; tri expands to net. */
#define tri(s0, s1) net              /* tri(s0, s1) X; -> net X; (strength preserved in source) */
#define tri1   net                   /* tri1 X; -> a tri-state net with pull-up */
/* tri0 already defined above */

/* ---- assign : continuous assignment with optional drive strength -------------------- */
/* Usage:
 *   assign P = _1b1;              simple assignment (strength is a marker)
 *   assign(s0, s1) Y = X;         assignment with drive strength marked in source
 *
 * assign is a marker for a continuous assignment. Drive strength (s0, s1) is
 * preserved in the source code for documentation, but the actual assignment
 * is handled by the following `net = value;` statement. */
#define assign(s0, s1)                 /* (s0, s1) strength marker for continuous assign */

/* ---- initial begin...end : initialization block (behavioral specification) ---------- */
/* In C, we preserve initial blocks as structured comments showing initialization behavior */
#define initial                        /* initial begin...end; -> behavioral init (comment) */

/* ---- delay notation: #(N) — timing delay in simulation -------------------------------- */
/* In C, delays are simulation-only markers; timing is not synthesized, but sequencing is */
#define DELAY(n)                       /* #(n) -> timing delay (no-op in C transcription) */

/* ---- begin / end : block delimiters (behavioral blocks: initial, always) --------------- */
#define begin  {                       /* begin -> opening brace */
#define end    }                       /* end   -> closing brace */

/* ---- primitive gate instantiations (instantiate real components) ----------------------- */
/* Verilog primitives (not, buf, pullup, etc.) are instantiated as real components.
 * Each macro creates the component and wires it. */
#define not(name, output, input) \
    do { \
        static not _not_##name; \
        wire_not(&_not_##name, input, output); \
        not_settle(&_not_##name); \
    } while(0)

#define buf(name, output, input) \
    do { \
        /* buf is identity: output = input (no gate needed, direct wire) */ \
        *(output) = *(input); \
    } while(0)

#define and(name, output, a, b) \
    do { \
        static and _and_##name; \
        wire_and(&_and_##name, a, b, output); \
        and_settle(&_and_##name); \
    } while(0)

#define or(name, output, a, b) \
    do { \
        static or _or_##name; \
        wire_or(&_or_##name, a, b, output); \
        or_settle(&_or_##name); \
    } while(0)

#define nand(name, output, a, b) \
    do { \
        static nand _nand_##name; \
        _nand_##name.A = a; \
        _nand_##name.B = b; \
        _nand_##name.Y = output; \
        nand_settle(&_nand_##name); \
    } while(0)

#define pullup(name, net) \
    do { \
        /* pullup: drive net to HI (weak pull-up) */ \
        if ((net)->level == Z || (net)->level == X) { \
            (net)->level = HI; \
        } \
    } while(0)

#define pulldown(name, net) \
    do { \
        /* pulldown: drive net to LO (weak pull-down) */ \
        if ((net)->level == Z || (net)->level == X) { \
            (net)->level = LO; \
        } \
    } while(0)

/* ---- specify blocks (timing specification, simulation-only) ----------------------------- */
/* `specify...endspecify blocks define timing constraints (delays, widths, etc.).
 * These are simulation markers; timing is not synthesized in the build phase. */
#define specify                        /* specify block: timing constraints */
#define endspecify                     /* end of specify block */
#define specparam                      /* specparam: timing constant */
#define $width                         /* $width timing check */

#endif /* VERILOG_H */
