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

/* ---- 4-state logic value (Verilog's 0/1/x/z) ------------------------------- */
typedef enum { LO=0, HI=1, X=2, Z=3 } logic_t;

/* ---- a net / signal: a value sits on it (Verilog `wire`/`reg`/port) --------- */
typedef struct { logic_t v; } net_t;

/* ---- Verilog-style sized binary literals: 1'b0, 1'b1, 1'bx, 1'bz ----------- */
/* Usage in C: reg X = _1b0; (declaration) or X = _1b0; (assignment)
 * Compound literals (net_t){...} work in both contexts. */
#define _1b0  (net_t){ LO }    /* 1'b0: 1-bit binary 0 */
#define _1b1  (net_t){ HI }    /* 1'b1: 1-bit binary 1 */
#define _1bx  (net_t){ X }     /* 1'bx: 1-bit binary X (don't-care) */
#define _1bz  (net_t){ Z }     /* 1'bz: 1-bit binary Z (high-impedance) */

/* ---- directives -----------------------------------------------------------
 * `timescale and `celldefine are simulation/tool markers with no runtime effect;
 * we define them so the line is valid C and the description is preserved. */
#define timescale(unit, prec)        /* `timescale <unit> / <prec> : sim time unit (marker) */
#define celldefine                   /* `celldefine    : cell-boundary marker */
#define endcelldefine                /* `endcelldefine : end cell-boundary marker */

/* ---- module / endmodule : a part. The part is a C block (function) that takes
 * its ports as net pointers. `module NAME(ports)` opens it; `endmodule` closes it. */
#define module(name)   void name      /* module NAME(...) -> a C function NAME(...) */
#define endmodule                      /* the closing brace is written explicitly */

/* ---- ports : a port is a net the part connects to. Declared as net pointers in
 * the module's parameter list; direction is recorded by the keyword. ---------- */
#define output  net_t *                /* output PORT  -> net the part drives  */
#define input   const net_t *          /* input  PORT  -> net the part reads   */
#define inout   net_t *                /* inout  PORT  -> bidirectional net     */

/* ---- parameter : a named constant of the part (string or value). ----------- */
#define parameter  static const int    /* parameter X = V; -> a named constant (type: int) */
#define parameter_str  static const char *  /* parameter_str X = "V"; -> string parameter */

/* ---- wire : internal net / signal (Verilog `wire`, local variable in C) ------- */
#define wire   net_t                   /* wire X; -> an internal net variable    */

/* ---- reg : register / storage variable (Verilog `reg`, same as wire in our C) - */
#define reg    net_t                   /* reg X; -> a variable that can be assigned to */

/* ---- localparam : local constant (similar to parameter but local scope) ------- */
#define localparam  static const int   /* localparam X = V; -> a local constant (type: int) */

/* ---- tri0 : tri-state net with pull-down to logic 0 (Xilinx test signal) ----- */
#define tri0   net_t                   /* tri0 X = init; -> a net with pull-down */

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
#define wire_bits(name, hi, lo)  net_t name[((hi)-(lo)+1)]  /* wire [hi:lo] name; */

/* ---- tri / tri1 / tri0 : tri-state net types with drive strength -------------------- */
/* Usage: tri(weak1, strong0) X = init;  (function-like macro consumes drive strength)
 * The drive strength (s0, s1) is recorded in the source code; tri expands to net_t. */
#define tri(s0, s1) net_t              /* tri(s0, s1) X; -> net_t X; (strength preserved in source) */
#define tri1   net_t                   /* tri1 X; -> a tri-state net with pull-up */
/* tri0 already defined above */

/* ---- assign : continuous assignment with drive strength -------------------- */
/* Usage: assign(strong1, weak0) X = Y;  (drive strength is preserved in source) */
#define assign(s0, s1)                 /* assign(s0, s1) net = expr; (strength preserved in source) */

/* ---- initial begin...end : initialization block (behavioral specification) ---------- */
/* In C, we preserve initial blocks as structured comments showing initialization behavior */
#define initial                        /* initial begin...end; -> behavioral init (comment) */

/* ---- delay notation: #(N) — timing delay in simulation -------------------------------- */
/* In C, delays are simulation-only markers; timing is not synthesized, but sequencing is */
#define DELAY(n)                       /* #(n) -> timing delay (no-op in C transcription) */

/* ---- begin / end : block delimiters (behavioral blocks: initial, always) --------------- */
#define begin  {                       /* begin -> opening brace */
#define end    }                       /* end   -> closing brace */

/* ---- primitive gate instantiations (part of cell specification) ----------------------- */
/* In Verilog, gates like `not`, `buf`, `pullup` are instantiated as primitives.
 * In transcription, we document the gate instantiation while remaining valid C. */
#define gate_instantiation(type, name, ...) /* primitive gate instantiation */
#define not(...) /* not gate: __VA_ARGS__ */
#define buf(...) /* buf gate: __VA_ARGS__ */
#define pullup(...) /* pullup gate: __VA_ARGS__ */

/* ---- specify blocks (timing specification, simulation-only) ----------------------------- */
/* `specify...endspecify blocks define timing constraints (delays, widths, etc.).
 * These are simulation markers; timing is not synthesized in the build phase. */
#define specify                        /* specify block: timing constraints */
#define endspecify                     /* end of specify block */
#define specparam                      /* specparam: timing constant */
#define $width                         /* $width timing check */

#endif /* VERILOG_H */
