/* components.c — the reusable digital-component library, sculpted from NAND.
 * Each part is a real DEVICE built by WIRING nand components through its own
 * internal wires. Parts are built IN PLACE (a part has a fixed address, because
 * it points to its own internal wires — copying would break that wiring).
 */
#include "components.h"

/* ===========================================================================
 * NAND — the one primitive. Behaviour = the silicon fact, held as a table.
 *            B= LO   HI    X     Z
 * =========================================================================*/
static const level NAND_BEHAVIOUR[4][4] = {
/*A=LO*/ { HI,  HI,  HI,  HI },
/*A=HI*/ { HI,  LO,  X,   X  },
/*A=X */ { HI,  X,   X,   X  },
/*A=Z */ { HI,  X,   X,   X  },
};
void nand_settle(nand *g){ g->Y->level = NAND_BEHAVIOUR[g->A->level][g->B->level]; }

/* ---- NOT = one NAND, both inputs tied to A -------------------------------- */
void wire_not(not *p, wire *A, wire *Y){
    p->A=A; p->Y=Y;
    p->g0.A=A; p->g0.B=A; p->g0.Y=Y;
}
void not_settle(not *p){ nand_settle(&p->g0); }

/* ---- AND = NAND then NOT -------------------------------------------------- */
void wire_and(and *p, wire *A, wire *B, wire *Y){
    p->A=A; p->B=B; p->Y=Y; p->mid.level=X;
    p->g0.A=A; p->g0.B=B; p->g0.Y=&p->mid;     /* NAND(A,B) -> mid */
    wire_not(&p->n0, &p->mid, Y);              /* NOT(mid)  -> Y   */
}
void and_settle(and *p){ nand_settle(&p->g0); not_settle(&p->n0); }

/* ---- OR = NAND(~A, ~B) ---------------------------------------------------- */
void wire_or(or *p, wire *A, wire *B, wire *Y){
    p->A=A; p->B=B; p->Y=Y; p->ma.level=X; p->mb.level=X;
    wire_not(&p->na, A, &p->ma);
    wire_not(&p->nb, B, &p->mb);
    p->g0.A=&p->ma; p->g0.B=&p->mb; p->g0.Y=Y;
}
void or_settle(or *p){ not_settle(&p->na); not_settle(&p->nb); nand_settle(&p->g0); }

/* ---- XOR = 4 NANDs -------------------------------------------------------- */
void wire_xor(xor *p, wire *A, wire *B, wire *Y){
    p->A=A; p->B=B; p->Y=Y; p->t.level=X; p->m1.level=X; p->m2.level=X;
    p->g0.A=A;      p->g0.B=B;      p->g0.Y=&p->t;
    p->g1.A=A;      p->g1.B=&p->t;  p->g1.Y=&p->m1;
    p->g2.A=B;      p->g2.B=&p->t;  p->g2.Y=&p->m2;
    p->g3.A=&p->m1; p->g3.B=&p->m2; p->g3.Y=Y;
}
void xor_settle(xor *p){ nand_settle(&p->g0); nand_settle(&p->g1); nand_settle(&p->g2); nand_settle(&p->g3); }

/* ---- MUX: Y = SEL ? B : A  =  (A & ~SEL) | (B & SEL) ---------------------- */
void wire_mux(mux *p, wire *A, wire *B, wire *SEL, wire *Y){
    p->A=A; p->B=B; p->SEL=SEL; p->Y=Y;
    p->nsel.level=X; p->pa.level=X; p->pb.level=X;
    wire_not(&p->ns, SEL, &p->nsel);
    wire_and(&p->aa, A, &p->nsel, &p->pa);
    wire_and(&p->ab, B, SEL,     &p->pb);
    wire_or (&p->oo, &p->pa, &p->pb, Y);
}
void mux_settle(mux *p){ not_settle(&p->ns); and_settle(&p->aa); and_settle(&p->ab); or_settle(&p->oo); }

/* ---- LATCH (D-latch, cross-coupled NANDs; transparent when G=1) -----------
 *   s = NAND(D,G) ; r = NAND(~D,G) ; Q = NAND(s,Qn) ; Qn = NAND(r,Q)          */
void wire_latch(latch *p, wire *D, wire *G, wire *Q){
    p->D=D; p->G=G; p->Q=Q;
    p->s.level=HI; p->r.level=HI; p->qn_w.level=HI; p->ndi.level=X;
    Q->level = LO;
    wire_not(&p->inv, D, &p->ndi);
    p->g_s.A=D;      p->g_s.B=G;       p->g_s.Y=&p->s;
    p->g_r.A=&p->ndi;p->g_r.B=G;       p->g_r.Y=&p->r;
    p->g_q.A=&p->s;  p->g_q.B=&p->qn_w;p->g_q.Y=Q;
    p->g_qn.A=&p->r; p->g_qn.B=Q;      p->g_qn.Y=&p->qn_w;
}
void latch_settle(latch *p){
    not_settle(&p->inv);
    nand_settle(&p->g_s); nand_settle(&p->g_r);
    for (int i=0;i<4;i++){ nand_settle(&p->g_q); nand_settle(&p->g_qn); }  /* settle the loop */
}

/* ---- EDGE ----------------------------------------------------------------- */
int edge_pos(edge *e){ int p=(e->prev==LO && e->IN->level==HI); e->prev=e->IN->level; return p; }
int edge_neg(edge *e){ int p=(e->prev==HI && e->IN->level==LO); e->prev=e->IN->level; return p; }

/* ---- Z-RESOLVE: weak pulldown conditioning  X_in = (X !== 1'bz) && X --------
 * The silicon fact: an undriven (Z) input is pulled to LO; a driven level passes
 * through; an unknown stays unknown. Held as the 4-state map (one entry per in). */
static const level ZRESOLVE_BEHAVIOUR[4] = {
/* in = LO */ LO,
/* in = HI */ HI,
/* in = X  */ X,
/* in = Z  */ LO,    /* (X !== 1'bz) is false -> 0 */
};
level resolve_z(level in){ return ZRESOLVE_BEHAVIOUR[in]; }

/* ---- TRI1 / TRI0: a tri net with a pull. An undriven (Z) tri1 net floats to HI
 * (a weak pull-up); a tri0 net floats to LO (a weak pull-down). A driven level
 * passes through; X stays X. The silicon fact of a pulled net, held as a 4-state map. */
static const level TRI1_BEHAVIOUR[4] = {
/* in = LO */ LO,
/* in = HI */ HI,
/* in = X  */ X,
/* in = Z  */ HI,    /* undriven tri1 pulls up to 1 */
};
static const level TRI0_BEHAVIOUR[4] = {
/* in = LO */ LO,
/* in = HI */ HI,
/* in = X  */ X,
/* in = Z  */ LO,    /* undriven tri0 pulls down to 0 */
};
level resolve_tri1(level in){ return TRI1_BEHAVIOUR[in]; }
level resolve_tri0(level in){ return TRI0_BEHAVIOUR[in]; }

/* ---- REG: the Verilog `reg`, a storage cell. Built on a latch. ------------- *
 * The reg holds its value; its DRIVER decides flip-flop vs wire behaviour:     */
void wire_reg(reg *p, wire *D, wire *Q){
    p->Q = Q; p->g_on.level = LO;            /* gate normally closed (reg holds) */
    wire_latch(&p->cell, D, &p->g_on, Q);    /* latch wired to the REAL D, once */
}
/* always @(edge): when the trigger edge fires, open the latch so it captures D. */
void reg_capture(reg *p, edge *trigger){
    if (edge_pos(trigger)) {                 /* the clock edge is a real detector */
        p->g_on.level = HI;                  /* open: latch becomes transparent -> Q<=D */
        latch_settle(&p->cell);
        p->g_on.level = LO;                  /* close: hold the captured value */
    }
    /* else: hold (the cross-coupled NANDs retain Q) */
}
/* always @(*): the reg follows D combinationally (a procedurally-written wire). */
void reg_drive(reg *p){
    p->g_on.level = HI;                      /* transparent: Q tracks D each settle */
    latch_settle(&p->cell);
}

/* ---- DFF = latch + edge --------------------------------------------------- */
void wire_dff(dff *p, wire *D, wire *C, wire *Q){
    p->D=D; p->C=C; p->Q=Q;
    p->clk.prev = C->level; p->clk.IN = C;
    p->g_open.level = HI;                       /* latch held transparent at capture */
    wire_latch(&p->mem, D, &p->g_open, Q);      /* part's own g_open wire (fixed addr) */
}
void dff_settle(dff *p){
    if (edge_pos(&p->clk)) latch_settle(&p->mem);   /* capture D on rising edge of C */
    /* else hold */
}

/* ---- VCC: constant source, always drives HI (logic 1) ----------------------- */
void wire_vcc(vcc *v, wire *P){
    v->P = P;
}
void vcc_settle(vcc *v){
    v->P->level = HI;  /* VCC always drives its output to logic 1 */
}

/* ---- GND: constant source, always drives LO (logic 0) ----------------------- */
void wire_gnd(gnd *g, wire *P){
    g->P = P;
}
void gnd_settle(gnd *g){
    g->P->level = LO;  /* GND always drives its output to logic 0 */
}

/* ---- tri1: tri-state net with weak pull-up --------------------------------- */
void tri1_settle(wire *p){
    p->level = resolve_tri1(p->level);  /* weakly pull undriven nets to HI */
}

/* ---- tri0: tri-state net with weak pull-down ------------------------------- */
void tri0_settle(wire *p){
    p->level = resolve_tri0(p->level);  /* weakly pull undriven nets to LO */
}

/* ===========================================================================
 * THE LANGUAGE — the verbs a replica uses to STATE its connections, exactly as
 * Verilog states them. Each operator BUILDS its real wired component on local
 * wires, SETTLES it, and yields the output net's level. The operator IS the
 * component — no native C decides the value; the wired NAND-network does.
 * ========================================================================= */
level rd(const wire *w){ return w->level; }          /* read a net's value */
void    ASSIGN(wire *dst, level v){ dst->level = v; } /* drive a named net (Verilog `assign`) */

level NOT(level a){
    wire A={a}, Y={X}; not g; wire_not(&g,&A,&Y); not_settle(&g); return Y.level;
}
level AND(level a, level b){
    wire A={a}, B={b}, Y={X}; and g; wire_and(&g,&A,&B,&Y); and_settle(&g); return Y.level;
}
level OR(level a, level b){
    wire A={a}, B={b}, Y={X}; or g; wire_or(&g,&A,&B,&Y); or_settle(&g); return Y.level;
}
level XOR(level a, level b){
    wire A={a}, B={b}, Y={X}; xor g; wire_xor(&g,&A,&B,&Y); xor_settle(&g); return Y.level;
}
level MUX(level a, level b, level sel){
    wire A={a}, B={b}, S={sel}, Y={X}; mux m; wire_mux(&m,&A,&B,&S,&Y); mux_settle(&m); return Y.level;
}
/* EQ(a,b) = XNOR(a,b) = NOT(XOR(a,b)) : HI when the two levels match, via wired parts. */
level EQ(level a, level b){ return NOT(XOR(a,b)); }
/* RESZ(in) = the z-resolve net (in !== 1'bz) && in. */
level RESZ(level in){ return resolve_z(in); }
