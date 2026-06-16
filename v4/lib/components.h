/* components.h — declarations for the reusable digital-component library.
 * A LINKABLE library of real parts (compiled from components.c), NOT a header
 * that pastes logic. Declares part types + terminals; bodies live in components.c.
 *
 * Every part is a physical DEVICE: terminals (pointers to connected wires) +
 * internal sub-components + internal wires + a settle() that drives its output.
 * Compound parts are built by REUSING the nand component.
 */
#ifndef COMPONENTS_H
#define COMPONENTS_H

typedef enum { LO=0, HI=1, X=2, Z=3 } level;
typedef struct { level level; } wire;

/* NAND — the one primitive device (two inputs, one output). */
typedef struct { wire *A, *B, *Y; } nand;
void nand_settle(nand *g);

/* gates: each holds its sub-nands + internal wires, wired in place. */
typedef struct { nand g0; wire *A, *Y; } not;
typedef struct { nand g0; not n0; wire mid; wire *A, *B, *Y; } and;
typedef struct { not na, nb; nand g0; wire ma, mb; wire *A, *B, *Y; } or;
typedef struct { nand g0, g1, g2, g3; wire t, m1, m2; wire *A, *B, *Y; } xor;
typedef struct { not ns; and aa, ab; or oo; wire nsel, pa, pb; wire *A, *B, *SEL, *Y; } mux;
typedef struct { nand g_s, g_r, g_q, g_qn; not inv; wire s, r, qn_w, ndi; wire *D, *G, *Q; } latch;
typedef struct { level prev; wire *IN; } edge;

/* REG — the Verilog `reg`: a storage cell that holds a level. It is built on a latch. */
typedef struct { latch cell; wire g_on; wire *Q; } reg;
typedef struct { latch mem; edge clk; wire g_open; wire *D, *C, *Q; } dff;

/* WIRE-IN-PLACE constructors: build the part into *p, wiring its internal sub-components. */
void wire_not(not *p, wire *A, wire *Y);
void wire_and(and *p, wire *A, wire *B, wire *Y);
void wire_or(or *p, wire *A, wire *B, wire *Y);
void wire_xor(xor *p, wire *A, wire *B, wire *Y);
void wire_mux(mux *p, wire *A, wire *B, wire *SEL, wire *Y);
void wire_latch(latch *p, wire *D, wire *G, wire *Q);
void wire_reg(reg *p, wire *D, wire *Q);
void wire_dff(dff *p, wire *D, wire *C, wire *Q);

/* REG drivers: clocked = capture-on-edge; combinational = follow. */
void reg_capture(reg *p, edge *trigger);
void reg_drive(reg *p);

/* settle: each compound settles its sub-components in order. */
void not_settle(not *p);
void and_settle(and *p);
void or_settle(or *p);
void xor_settle(xor *p);
void mux_settle(mux *p);
void latch_settle(latch *p);
void dff_settle(dff *p);
void tri1_settle(wire *p);
void tri0_settle(wire *p);

int edge_pos(edge *e);
int edge_neg(edge *e);

/* SOURCE COMPONENTS — constant drivers. */
typedef struct { wire *P; } vcc;
typedef struct { wire *P; } gnd;

void wire_vcc(vcc *v, wire *P);
void wire_gnd(gnd *g, wire *P);
void vcc_settle(vcc *v);
void gnd_settle(gnd *g);

/* Utilities. */
level resolve_z(level in);
level resolve_tri1(level in);
level resolve_tri0(level in);

/* Language verbs — operators that build and settle real wired components. */
level rd(const wire *w);
void ASSIGN(wire *dst, level v);
level AND(level a, level b);
level OR(level a, level b);
level NOT(level a);
level XOR(level a, level b);
level MUX(level a, level b, level sel);
level EQ(level a, level b);
level RESZ(level in);

#endif
