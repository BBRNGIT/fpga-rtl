/* nand_component.c — a NAND sculpted as a physical COMPONENT in C-clay.
 *
 * A NAND is not a function. It is a DEVICE: three terminals (two inputs, one
 * output) and one physical behaviour. We mould it from the clay (C) as a part
 * that EXISTS, holds its pins, and is wired to other parts (one gate's output
 * terminal IS the wire another gate's input terminal reads).
 */
#include <stdio.h>

/* ---- the clay's atom: a logic level on a terminal (4-state, like silicon) --- */
typedef enum { LO=0, HI=1, X=2, Z=3 } level_t;

/* ---- a WIRE: a conductor. It is a place a value sits; drivers put a level on
 *      it, loads read it. Parts connect by sharing the SAME wire. -------------*/
typedef struct { level_t level; } wire_t;

/* ===========================================================================
 * THE NAND COMPONENT.  A device with three terminals and a fixed behaviour.
 *   terminals:  A (input), B (input), Y (output)
 *   the part holds POINTERS to the wires its terminals connect to, so wiring is
 *   physical: gate2.A = &someWire that gate1.Y also drives.
 * =========================================================================*/
typedef struct {
    wire_t *A;     /* input terminal A  -> connected wire */
    wire_t *B;     /* input terminal B  -> connected wire */
    wire_t *Y;     /* output terminal Y -> connected wire (this part DRIVES it) */
} nand_t;

/* the device's physical behaviour, realised once as a TRUTH TABLE (the silicon
 * fact: output low only when both inputs high; unknown in -> unknown out). This
 * is the part's nature, stored as what-it-is, indexed by the two input levels. */
static const level_t NAND_BEHAVIOUR[4][4] = {
/*  B = LO   HI    X     Z                                      */
/*A=LO*/ { HI,  HI,  HI,  HI },   /* a low input forces output high */
/*A=HI*/ { HI,  LO,  X,   X  },   /* both high -> low ; unknown -> X */
/*A=X */ { HI,  X,   X,   X  },
/*A=Z */ { HI,  X,   X,   X  },
};

/* SETTLE the gate: read the levels on its input terminals, drive its output
 * terminal. This is the part doing its physical job — not a value being returned,
 * but a terminal being driven. */
static void nand_settle(nand_t *g){
    g->Y->level = NAND_BEHAVIOUR[ g->A->level ][ g->B->level ];
}

/* ===========================================================================
 * PROOF: build a tiny circuit by PLACING parts and WIRING their terminals.
 *   - a NOT is one NAND with both inputs tied to the same wire.
 *   - we wire two gates so gate1.Y IS gate2's input wire (physical connection).
 * =========================================================================*/
int main(void){
    /* lay down some wires (conductors) */
    wire_t w_in = { HI }, w_mid = { X }, w_out = { X };

    /* PLACE a NAND used as a NOT: both inputs on w_in, output drives w_mid */
    nand_t inv = { .A = &w_in, .B = &w_in, .Y = &w_mid };

    /* PLACE a second NAND: both inputs on w_mid, output drives w_out (NOT again)
     * so w_out should equal w_in (NOT of NOT). The two gates are WIRED: inv.Y
     * and buf.A/B share w_mid — a physical connection, not a function call. */
    nand_t buf = { .A = &w_mid, .B = &w_mid, .Y = &w_out };

    /* run the circuit: settle each gate (signal propagates through the wires) */
    nand_settle(&inv);    /* w_mid = NOT(w_in) */
    nand_settle(&buf);    /* w_out = NOT(w_mid) = w_in */

    printf("w_in=%d  -> inv -> w_mid=%d  -> buf -> w_out=%d\n",
           w_in.level, w_mid.level, w_out.level);
    printf("NOT(NOT(HI)) = %d  (expect 1)  -> %s\n",
           w_out.level, w_out.level==HI ? "PASS" : "FAIL");

    /* and the raw gate behaviour, as a device driving its Y terminal */
    wire_t a={LO}, b={LO}, y={X};
    nand_t g = { &a,&b,&y };
    a.level=LO; b.level=LO; nand_settle(&g); printf("NAND 00 -> Y=%d\n", y.level);
    a.level=HI; b.level=LO; nand_settle(&g); printf("NAND 10 -> Y=%d\n", y.level);
    a.level=HI; b.level=HI; nand_settle(&g); printf("NAND 11 -> Y=%d\n", y.level);
    return 0;
}
