/* cells.h — branchless flip-flop / gate primitives for HFT devices.
 *
 * CANONICAL SINGLE SOURCE. This file (.hft_staging/cells/cells.h) is the one
 * authoritative copy of the cell primitive library. Per-component copies of
 * cells.h must byte-match this file modulo the header-guard token (the
 * #ifndef/#define/#endif guard identifier may be component-specific, e.g.
 * ADAPTER_CELLS_H; everything else must be identical). Enforced by
 * .hft_staging/checks/check_cells_canon.sh.
 *
 * Built fresh to the build approach (project_hft_framework_adopted): every
 * flip-flop, gate node, and signal is an addressed register; every operation
 * is a boolean function between addressed registers — no if/switch/?: ,
 * selection is mask algebra, equality is zero-reduction. These primitives are
 * intrinsic to the system: a register IS a dff, a comparator IS a netlist of
 * these gates.
 *
 * NO floats, NO malloc, NO function pointers. Every cell is a pure word function.
 */
#ifndef HFT_CELLS_H
#define HFT_CELLS_H

#include <stdint.h>

/* A wire/register holds one 64-bit word. The device state is a flat array of
 * these, indexed by node address (the address map the netlist assigns). */
typedef uint64_t word_t;

/* ---- combinational gates (bitwise, branchless) ---------------------------- */

static inline word_t cell_buf(word_t a)            { return a; }
static inline word_t cell_not(word_t a)            { return ~a; }
static inline word_t cell_and(word_t a, word_t b)  { return a & b; }
static inline word_t cell_or (word_t a, word_t b)  { return a | b; }
static inline word_t cell_xor(word_t a, word_t b)  { return a ^ b; }

/* 1-bit MUX over full words: sel is 0 or 1 in bit0, broadcast to a mask.
 * out = sel ? b : a  — expressed as mask algebra, no branch.
 * mask = -(sel & 1) → all-ones when sel, all-zeros when !sel. */
static inline word_t cell_mux(word_t a, word_t b, word_t sel) {
    const word_t m = (word_t)0 - (sel & 1ULL);
    return a ^ ((a ^ b) & m);
}

/* eqmask: 1 (bit0) when a == b, else 0. Zero-reduction equality, branchless.
 * d = a^b ; d==0  ⇔  (d | -d) has its sign bit clear. */
static inline word_t cell_eqmask(word_t a, word_t b) {
    const word_t d = a ^ b;
    return (~(d | ((word_t)0 - d))) >> 63;       /* 1 iff d==0 */
}

/* full adder bit: produces sum bit and carry-out bit for single-bit inputs.
 * Used by the comparator/counter netlists which are expanded bit-serially by
 * the generator. a,b,cin are in bit0; returns sum in bit0, cout in bit1. */
static inline word_t cell_fa(word_t a, word_t b, word_t cin) {
    const word_t aa = a & 1ULL, bb = b & 1ULL, cc = cin & 1ULL;
    const word_t s  = aa ^ bb ^ cc;
    const word_t co = (aa & bb) | (cc & (aa ^ bb));
    return s | (co << 1);
}

/* gate: register-backed pass-or-zero. out = en ? val : 0 — mask algebra, no
 * branch. mask = -(en & 1) → all-ones when en, all-zeros when !en. Used to
 * power-gate a multi-bit register value (e.g. the clock step = SPEED while
 * powered, 0 while off) without an if/?: and without a literal in the path.
 * Also the building block of table select: gate exactly one slot through and
 * OR-reduce the rest as 0 (one-hot select with no branch). */
static inline word_t cell_gate(word_t val, word_t en) {
    const word_t m = (word_t)0 - (en & 1ULL);
    return val & m;
}

/* cell_addsub: gate-netlist add/subtract — the STRUCTURAL arithmetic primitive.
 * Returns the 64-bit sum word (not the carry — that is the only difference from
 * the cmp_le carry chain, which returns the final carry-out). sub=0 → a+b;
 * sub=1 → a-b via two's complement: invert b and inject an initial carry of 1
 * (a + ~b + 1). The bit-loop IS the gate expansion of a 64-cell ripple-carry
 * adder — a generator-level unrolling, not a data-path branch (no conditional
 * selects the result, the carry chain does). The DATA arithmetic is cell_fa;
 * the loop index is the only native +/- and is address/index math, not data.
 * This is the founder's gate_level_arithmetic law: no native add/sub/mul. */
static inline word_t cell_addsub(word_t a, word_t b, word_t sub) {
    const word_t s   = sub & 1ULL;
    const word_t bm  = b ^ ((word_t)0 - s);   /* ~b when sub, b otherwise */
    word_t carry = s;                          /* +1 initial carry for subtract */
    word_t sum   = 0ULL;
    word_t i     = 0ULL;
    for (i = 0ULL; i < 64ULL; i = i + 1ULL) {
        const word_t aa = (a  >> i) & 1ULL;
        const word_t bb = (bm >> i) & 1ULL;
        const word_t fa = cell_fa(aa, bb, carry);
        sum   = sum | ((fa & 1ULL) << i);      /* sum bit i */
        carry = (fa >> 1) & 1ULL;              /* carry-out to next bit */
    }
    return sum;
}

/* ---- shift primitive: arithmetic shift right --------------------------------
 * cell_sar(a, n): shift a right by a compile-time constant n (0 < n < 64),
 * replicating the sign bit (bit 63) into the vacated high bits. At gate level
 * a fixed shift is pure rewiring (bit-selects), and the sign fill is the
 * two's-complement broadcast of bit 63 — no adder, no branch. Shifts are
 * sanctioned in the tick body (the arithmetic gate strips >> and << before
 * scanning for native +,-,*). */
static inline word_t cell_sar(word_t a, unsigned n) {
    const word_t sign = (word_t)0 - ((a >> 63) & 1ULL);
    return (a >> n) | (sign << (64u - n));
}

/* ---- sequential primitive: D flip-flop with enable -------------------------
 * The ONE stateful cell. q_next = en ? d : q  (mask algebra, no branch).
 * The device's clock-edge applies this to every dff node each tick; the value
 * latched is the value present at the input on the edge (registered hop). */
static inline word_t cell_dff(word_t q, word_t d, word_t en) {
    const word_t m = (word_t)0 - (en & 1ULL);
    return q ^ ((q ^ d) & m);
}

#endif /* HFT_CELLS_H */
