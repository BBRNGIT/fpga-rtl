/* nand_lowlevel.c — the low-level style: NAND is a TRUTH-TABLE LOOKUP (data, not
 * C logic). Everything above NAND is described by COMPOSING NAND — no native C
 * operators (if/?:/==/&&/||) and no control flow in the hardware logic.
 *
 * The only substrate used: the logic_t value, a constant table, and array index.
 */
#include <stdio.h>

/* AXIOM 1 — VALUE: 4-state. 0,1,X,Z. */
typedef enum { L0=0, L1=1, LX=2, LZ=3 } logic_t;

/* AXIOM 2 — NAND, as a 4x4 TRUTH TABLE (pure data: no if/==/&&).
 * Rows = a, cols = b. Verilog 4-state NAND:
 *   any 0 -> 1 ; 1,1 -> 0 ; otherwise (involving X or Z) -> X.
 * Z is treated as X at a gate input (the .v does this via resolution).
 *            b=0  b=1  b=X  b=Z                                                  */
static const logic_t NAND_T[4][4] = {
/* a=0 */  { L1,  L1,  L1,  L1 },   /* 0 dominates -> always 1 */
/* a=1 */  { L1,  L0,  LX,  LX },   /* 1,0->1 ; 1,1->0 ; 1,X->X */
/* a=X */  { L1,  LX,  LX,  LX },
/* a=Z */  { L1,  LX,  LX,  LX },
};

/* the gate: a single table lookup. no native logic. */
static logic_t NAND(logic_t a, logic_t b){ return NAND_T[a][b]; }

/* ---- everything below is PURE NAND COMPOSITION (no native C ops) ----------- */
static logic_t NOT (logic_t a)            { return NAND(a, a); }
static logic_t AND (logic_t a, logic_t b) { return NOT(NAND(a, b)); }
static logic_t OR  (logic_t a, logic_t b) { return NAND(NOT(a), NOT(b)); }
static logic_t XOR (logic_t a, logic_t b) { logic_t t = NAND(a, b);
                                            return NAND(NAND(a, t), NAND(b, t)); }

/* MUX described as gates (replaces C `sel ? a : b`):  (a & ~sel) | (b & sel) */
static logic_t MUX (logic_t sel, logic_t a, logic_t b){
    return OR( AND(a, NOT(sel)), AND(b, sel) );
}

/* tri0 described with gates (replaces `driven ? d : L0`):
 *   when driven=1 -> d ; when driven=0 -> 0.  That is just AND(d, driven):
 *   AND(d,1)=d, AND(d,0)=0. No ternary. */
static logic_t TRI0(logic_t d, logic_t driven){ return AND(d, driven); }
/* tri1: when undriven pull to 1 -> OR(d, NOT(driven)):
 *   driven=1 -> OR(d,0)=d ; driven=0 -> OR(d,1)=1. */
static logic_t TRI1(logic_t d, logic_t driven){ return OR(d, NOT(driven)); }

/* equality of two bits as a GATE (replaces C `a==b`): XNOR = NOT(XOR). */
static logic_t EQ  (logic_t a, logic_t b){ return NOT(XOR(a, b)); }

/* ---- proof: built from NAND-the-table, behaves correctly --------------------*/
int main(void){
    /* show NAND is a lookup */
    printf("NAND table: 00->%d 01->%d 10->%d 11->%d\n", NAND(L0,L0),NAND(L0,L1),NAND(L1,L0),NAND(L1,L1));

    /* gates from NAND */
    printf("NOT 0=%d 1=%d | AND 11=%d 10=%d | OR 00=%d 01=%d | XOR 10=%d 11=%d\n",
           NOT(L0),NOT(L1), AND(L1,L1),AND(L1,L0), OR(L0,L0),OR(L0,L1), XOR(L1,L0),XOR(L1,L1));

    /* mux, tri0/tri1, eq — all gate-composed */
    printf("MUX sel0->a(=%d) sel1->b(=%d)\n", MUX(L0,L1,L0), MUX(L1,L1,L0));
    printf("TRI0 driven(1,1)=%d undriven(1,0)=%d | TRI1 undriven(0,0)=%d\n",
           TRI0(L1,L1), TRI0(L1,L0), TRI1(L0,L0));
    printf("EQ 11=%d 10=%d\n", EQ(L1,L1), EQ(L1,L0));
    return 0;
}
