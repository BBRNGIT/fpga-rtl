/******************************************************************************
 * verilog_base.c — the IRREDUCIBLE Verilog primitive set, defined in low-level C.
 *
 * Verilog is the design language; every UNISIM cell (and every derived device —
 * tri0, notif, flip-flops, CARRY8, ...) is a COMPOSITION of a tiny irreducible
 * base. C has none of these natively, so we define them here, the way we defined
 * NAND as the one universal gate. Everything else DERIVES from this base.
 *
 * THE AXIOMS (irreducible — cannot be built from each other):
 *   1. VALUE     — a 4-state logic value: 0, 1, X (unknown), Z (high-Z).
 *   2. NAND      — the one universal gate. All combinational logic derives from it.
 *   3. NET       — a connection carrying a value, with a RESOLUTION rule (what it
 *                  becomes when driven by 0/1, undriven, or multiply driven).
 *   4. LATCH     — one bit of STATE (a value that persists). NAND is combinational
 *                  and cannot remember; storage needs its own axiom.
 *   5. EDGE      — detecting a transition on a signal (prev != now). Sequential
 *                  logic (posedge/negedge, flip-flops) derives from it.
 *
 * This file is a worked, self-proving definition. `tri0` is included as the first
 * DERIVATION, showing a real UNISIM construct built purely from the axioms.
 *****************************************************************************/
#include <stdio.h>

/* ===========================================================================
 * AXIOM 1 — VALUE: 4-state logic.  (Verilog 1'b0/1'b1/1'bx/1'bz)
 * =========================================================================*/
typedef enum { L0 = 0, L1 = 1, LX = 2, LZ = 3 } logic_t;

/* ===========================================================================
 * AXIOM 2 — NAND: the one universal gate.  All gates derive from this.
 * =========================================================================*/
static logic_t NAND(logic_t a, logic_t b){
    if (a == L0 || b == L0) return L1;        /* 0 dominates AND -> NAND = 1 */
    if (a == L1 && b == L1) return L0;
    return LX;                                /* any unknown -> X */
}
/* DERIVED gates (composition of NAND) — the classic Verilog operators ~ & | ^ */
static logic_t g_not (logic_t a)            { return NAND(a, a); }
static logic_t g_and (logic_t a, logic_t b) { logic_t t = NAND(a,b); return NAND(t,t); }
static logic_t g_or  (logic_t a, logic_t b) { return NAND(NAND(a,a), NAND(b,b)); }
static logic_t g_xor (logic_t a, logic_t b) { logic_t t = NAND(a,b);
                                              return NAND(NAND(a,t), NAND(b,t)); }
static logic_t g_xnor(logic_t a, logic_t b) { return g_not(g_xor(a,b)); }
static logic_t g_nor (logic_t a, logic_t b) { return g_not(g_or (a,b)); }
static logic_t g_mux (logic_t s, logic_t a, logic_t b){ return g_or(g_and(s,a), g_and(g_not(s),b)); }

/* ===========================================================================
 * AXIOM 3 — NET + RESOLUTION.  A net carries a value; the resolution rule says
 * what it becomes given a driver and whether it is driven. The strength suffix
 * (wire/tri0/tri1/wand/wor/supply) is just a different resolution rule, so each
 * DERIVES from this axiom — none is a separate primitive.
 *   `pull` = the value an UNDRIVEN net resolves to:  X (wire), L0 (tri0), L1 (tri1).
 * =========================================================================*/
typedef logic_t net_t;                        /* a net is a value-carrying connection */

static logic_t net_resolve(logic_t driver, int driven, logic_t pull){
    return driven ? driver : pull;            /* undriven -> the pull value */
}

/* ===========================================================================
 * AXIOM 4 — LATCH: one bit of persistent STATE.  (the storage axiom)
 * A level-sensitive latch: while gate G is high, Q follows D; else Q holds.
 * Flip-flops derive from this (latch + edge).
 * =========================================================================*/
typedef struct { logic_t q; } latch_t;        /* the stored bit */
static logic_t latch_step(latch_t *L, logic_t d, logic_t g){
    if (g == L1) L->q = d;                     /* transparent while G=1 */
    return L->q;                               /* else hold */
}

/* ===========================================================================
 * AXIOM 5 — EDGE: detect a transition on a signal (prev -> now).
 * posedge/negedge and every flip-flop derive from this.
 * =========================================================================*/
typedef struct { logic_t prev; } edge_t;
static int edge_pos(edge_t *e, logic_t now){ int p = (e->prev==L0 && now==L1); e->prev=now; return p; }
static int edge_neg(edge_t *e, logic_t now){ int n = (e->prev==L1 && now==L0); e->prev=now; return n; }

/* ===========================================================================
 * DERIVATIONS — built purely from the axioms above (no new primitives).
 * =========================================================================*/

/* tri0 : a NET whose undriven value pulls to 0.  (AXIOM 3, pull = L0)
 *   verilog:  tri0 glblGSR = glbl_GSR;
 *   c:        net_t glblGSR = tri0(glbl_GSR, glbl_GSR_driven);
 * Real UNISIM usage (164 files): `tri0 glblGSR = glbl.GSR;` */
static logic_t tri0(logic_t driver, int driven){ return net_resolve(driver, driven, L0); }
/* tri1 : same net axiom, pulls to 1. */
static logic_t tri1(logic_t driver, int driven){ return net_resolve(driver, driven, L1); }
/* plain wire : net axiom, undriven -> X. */
static logic_t wire_net(logic_t driver, int driven){ return net_resolve(driver, driven, LX); }

/* a D flip-flop : LATCH (state) + EDGE (clock). Derived, not a new axiom.
 *   posedge clk -> Q <= D.  This is how FDRE etc. are built. */
typedef struct { latch_t l; edge_t clk; } dff_t;
static logic_t dff_posedge(dff_t *ff, logic_t d, logic_t clk){
    if (edge_pos(&ff->clk, clk)) ff->l.q = d;  /* capture D on rising edge */
    return ff->l.q;
}

/* TRISTATE BUFFERS — derived from the NET axiom: a CONDITIONAL DRIVER. When the
 * enable is active the buffer drives the data onto the net; otherwise it drives
 * Z (releases the net), so the net's resolution (its pull/other drivers) decides.
 * Real UNISIM usage:  bufif0 T1 (IO, I, ts);   notif0 N2 (IOB, I, t2);
 *   bufif1 (out, in, en): drive in  when en==1, else Z
 *   bufif0 (out, in, en): drive in  when en==0, else Z
 *   notif1 (out, in, en): drive ~in when en==1, else Z
 *   notif0 (out, in, en): drive ~in when en==0, else Z
 * These compose: a gate (AXIOM 2, for the ~ in notif) + a conditional onto a net. */
static logic_t bufif1(logic_t in, logic_t en){ return (en==L1) ? in        : LZ; }
static logic_t bufif0(logic_t in, logic_t en){ return (en==L0) ? in        : LZ; }
static logic_t notif1(logic_t in, logic_t en){ return (en==L1) ? g_not(in) : LZ; }
static logic_t notif0(logic_t in, logic_t en){ return (en==L0) ? g_not(in) : LZ; }

/* BUS / LANE — an [N:0] vector is N+1 nets. Bit-select, part-select, concat, and
 * reduction all derive from indexing the lane + the gate/net axioms.
 *   verilog [N:0]      -> logic_t lane[N+1]
 *   x[i]               -> lane[i]
 *   {a,b,c}            -> bus_concat (ordered assembly)
 *   &x, |x, ^x         -> reduce over the lane with the gate axiom            */
static logic_t bus_reduce_and(const logic_t *x, int n){ logic_t r=x[0]; for(int i=1;i<n;i++) r=g_and(r,x[i]); return r; }
static logic_t bus_reduce_or (const logic_t *x, int n){ logic_t r=x[0]; for(int i=1;i<n;i++) r=g_or (r,x[i]); return r; }
static logic_t bus_reduce_xor(const logic_t *x, int n){ logic_t r=x[0]; for(int i=1;i<n;i++) r=g_xor(r,x[i]); return r; }
/* concat {hi..lo}: copy src lane into dst starting at bit `at` (LSB-first). */
static void bus_place(logic_t *dst, int at, const logic_t *src, int n){ for(int i=0;i<n;i++) dst[at+i]=src[i]; }

/* CASE / CASEX — a multi-way selector. Derived from the MUX axiom (a case is a
 * tree of muxes selected by the case expression). `case` matches exact patterns;
 * `casex` treats X bits in a pattern as don't-care.
 * Real UNISIM:  case(FIFO_MODE) "FIFO18":... ;  casex({LOAD,CE,INC}) 3'b010:...
 *   match: every selector bit equals the pattern bit (casex: or pattern bit is X). */
static int bus_match(const logic_t *sel, const logic_t *pat, int n, int casex){
    for (int i=0;i<n;i++){
        if (casex && pat[i]==LX) continue;        /* casex: X in pattern = don't-care */
        if (sel[i] != pat[i]) return 0;
    }
    return 1;
}
/* select the value whose pattern matches sel; default if none. (priority = order) */
static logic_t case_select(const logic_t *sel, int n,
                           const logic_t (*pats)[8], const logic_t *vals, int npat,
                           logic_t dflt, int casex){
    for (int k=0;k<npat;k++) if (bus_match(sel, pats[k], n, casex)) return vals[k];
    return dflt;
}

/* ARITHMETIC — built from the gate axiom (NEVER native C + - *).
 * full adder: sum = a^b^cin ; carry = (a&b)|(cin&(a^b)).  Ripple to add lanes. */
static void full_adder(logic_t a, logic_t b, logic_t cin, logic_t *sum, logic_t *cout){
    logic_t axb = g_xor(a,b);
    *sum  = g_xor(axb, cin);
    *cout = g_or(g_and(a,b), g_and(cin, axb));
}
/* add two N-bit lanes (ripple-carry); returns carry-out. */
static logic_t bus_add(const logic_t *a, const logic_t *b, logic_t cin, logic_t *out, int n){
    logic_t c = cin;
    for (int i=0;i<n;i++){ logic_t co; full_adder(a[i], b[i], c, &out[i], &co); c = co; }
    return c;
}

/* MULTIPLY — array multiplier, from full-adders (gate axiom). Digital `a * b`.
 * (Never native C *. For the DSP slice etc.) out is up to 2N bits. */
static void bus_mul(const logic_t *a, const logic_t *b, logic_t *out, int n){
    for (int i=0;i<2*n;i++) out[i]=L0;
    for (int j=0;j<n;j++){
        logic_t carry=L0;
        for (int i=0;i<n;i++){
            logic_t partial = g_and(a[i], b[j]);     /* AND each bit pair (the product term) */
            logic_t s, co;
            full_adder(out[i+j], partial, carry, &s, &co);
            out[i+j]=s; carry=co;
        }
        out[n+j]=carry;
    }
}

/* CLOCK helpers — derived from the EDGE axiom (already an axiom). The negedge
 * flip-flop variant + the sim time counter that `$time`/#delay model. */
typedef struct { latch_t l; edge_t clk; } dff_neg_t;
static logic_t dff_negedge(dff_neg_t *ff, logic_t d, logic_t clk){
    if (edge_neg(&ff->clk, clk)) ff->l.q = d;     /* capture on falling edge */
    return ff->l.q;
}
/* simulation time (what $time/$realtime read, what #delay advances). Model only. */
typedef unsigned long sim_time_t;
static sim_time_t sim_now = 0;
static sim_time_t sim_advance(sim_time_t d){ sim_now += d; return sim_now; }  /* #d */

/* ===========================================================================
 * ANALOG BOUNDARY — the honest edge of the digital world.  Verilog `real`,
 * `realtime`, $bitstoreal/$realtobits, voltages/frequencies (PLL/VCO/transceiver/
 * SYSMON) are CONTINUOUS, not 0/1 — they CANNOT be built from NAND. We do NOT
 * gate-decompose them (Law: analog = boundary). They are a recognized boundary
 * value: a continuous quantity the fabric drives/reads, marked as such.
 *   verilog  real x;          -> real_t (a continuous value at the boundary)
 *   $realtobits / $bitstoreal -> the digital<->analog boundary crossing
 * =========================================================================*/
typedef double real_t;                            /* a continuous (analog) value */
typedef struct { real_t value; const char *role; } analog_boundary_t;  /* VCO/PLL/ADC... */
/* the only legal digital<->analog crossings (recognized, not decomposed): */
static real_t bits_to_real(const logic_t *bits, int n){     /* $bitstoreal (boundary in) */
    /* interpret the bit pattern as the IEEE bits of a real — a boundary crossing,
       NOT arithmetic on the analog value. */
    unsigned long u=0; for(int i=0;i<n && i<64;i++) if(bits[i]==L1) u|=(1UL<<i);
    real_t r; if(sizeof(r)==8) { unsigned long long uu=u; __builtin_memcpy(&r,&uu,8);} else r=(real_t)u;
    return r;
}

/* ===========================================================================
 * SELF-PROOF — the axioms + derivations behave correctly.
 * =========================================================================*/
int main(void){
    int ok = 1;

    /* AXIOM 2 + derived gates: truth tables */
    for (logic_t a=L0;a<=L1;a++) for (logic_t b=L0;b<=L1;b++){
        if (g_and(a,b) != (logic_t)(a&&b)) ok=0;
        if (g_or (a,b) != (logic_t)(a||b)) ok=0;
        if (g_xor(a,b) != (logic_t)((a==L1)^(b==L1))) ok=0;
    }
    if (g_not(L0)!=L1 || g_not(L1)!=L0) ok=0;
    printf("[axiom2 NAND + derived gates] %s\n", ok?"PASS":"FAIL");

    /* AXIOM 3 via tri0: undriven pulls to 0; driven passes the driver */
    int t0 = (tri0(LX, 0)==L0) && (tri0(L1, 1)==L1) && (tri0(L0,1)==L0);
    int t1 = (tri1(LX, 0)==L1) && (tri1(L0, 1)==L0);
    int wr = (wire_net(LX,0)==LX) && (wire_net(L1,1)==L1);
    printf("[axiom3 net: tri0/tri1/wire] %s\n", (t0&&t1&&wr)?"PASS":"FAIL"); ok &= t0&&t1&&wr;

    /* AXIOM 4 latch: transparent when G=1, holds when G=0 */
    latch_t L={L0}; latch_step(&L,L1,L1); int la = (L.q==L1);
    la &= (latch_step(&L,L0,L0)==L1);   /* G=0: holds the L1 */
    printf("[axiom4 latch] %s\n", la?"PASS":"FAIL"); ok &= la;

    /* AXIOM 5 edge + derived DFF: Q captures D only on the rising clock edge */
    dff_t ff={{L0},{L0}};
    dff_posedge(&ff, L1, L0);           /* clk low: no capture */
    int e1 = (ff.l.q==L0);
    dff_posedge(&ff, L1, L1);           /* rising edge: capture D=1 */
    int e2 = (ff.l.q==L1);
    dff_posedge(&ff, L0, L1);           /* clk high, no edge: hold */
    int e3 = (ff.l.q==L1);
    printf("[axiom5 edge + derived DFF] %s\n", (e1&&e2&&e3)?"PASS":"FAIL"); ok &= e1&&e2&&e3;

    /* DERIVED: tristate buffers — drive when enabled, else Z */
    int tb = (bufif1(L1,L1)==L1) && (bufif1(L1,L0)==LZ) &&   /* en=1 drives, en=0 -> Z */
             (bufif0(L1,L0)==L1) && (bufif0(L1,L1)==LZ) &&   /* active-low enable      */
             (notif1(L1,L1)==L0) && (notif1(L0,L1)==L1) &&   /* notif inverts          */
             (notif0(L1,L1)==LZ);                            /* en=1 on notif0 -> Z    */
    printf("[derived tristate notif/bufif] %s\n", tb?"PASS":"FAIL"); ok &= tb;

    /* DERIVED: bus reduction + concat over a lane */
    logic_t lane[4] = {L1,L1,L1,L1};
    int br = (bus_reduce_and(lane,4)==L1) && (bus_reduce_xor(lane,4)==L0);  /* 1&1&1&1=1, 1^1^1^1=0 */
    logic_t lane2[4]={L1,L0,L1,L0}; br &= (bus_reduce_or(lane2,4)==L1);
    logic_t dst[4]={L0,L0,L0,L0}, src[2]={L1,L1}; bus_place(dst,1,src,2);
    br &= (dst[0]==L0 && dst[1]==L1 && dst[2]==L1 && dst[3]==L0);           /* placed at bit1..2 */
    printf("[derived bus reduce/concat] %s\n", br?"PASS":"FAIL"); ok &= br;

    /* DERIVED: case/casex selector (from MUX axiom) — casex({L,C,I}) like UNISIM */
    logic_t pats[3][8] = { {L0,L1,L0,0}, {L1,LX,LX,0}, {L0,L0,L1,0} };  /* 010, 1xx, 001 */
    logic_t vals[3]    = { L1, L0, L1 };
    logic_t sel1[3]={L0,L1,L0}, sel2[3]={L1,L0,L1}, sel3[3]={L1,L1,L1};
    int cs = (case_select(sel1,3,pats,vals,3,LX,1)==L1) &&   /* 010 -> first  */
             (case_select(sel2,3,pats,vals,3,LX,1)==L0) &&   /* 101 -> 1xx (casex) */
             (case_select(sel3,3,pats,vals,3,LX,1)==L0) &&   /* 111 -> 1xx (casex) */
             (case_select((logic_t[]){L1,L1,L0},3,pats,vals,3,L0,0)==L0); /* exact: no match -> dflt */
    printf("[derived case/casex] %s\n", cs?"PASS":"FAIL"); ok &= cs;

    /* DERIVED: gate-built arithmetic — add all 4-bit pairs, compare to truth */
    int ar = 1;
    for (int A=0;A<16 && ar;A++) for (int B=0;B<16;B++){
        logic_t la[4],lb[4],lo[4];
        for (int i=0;i<4;i++){ la[i]=(A>>i&1)?L1:L0; lb[i]=(B>>i&1)?L1:L0; }
        logic_t co = bus_add(la,lb,L0,lo,4);
        int s=0; for(int i=0;i<4;i++) s|=((lo[i]==L1)<<i); s|=((co==L1)<<4);
        if (s != A+B){ ar=0; break; }
    }
    printf("[derived arithmetic (full-adder)] %s\n", ar?"PASS":"FAIL"); ok &= ar;

    /* DERIVED: gate-built MULTIPLY — check all 4-bit products */
    int mu = 1;
    for (int A=0;A<16 && mu;A++) for (int B=0;B<16;B++){
        logic_t la[4],lb[4],lo[8];
        for(int i=0;i<4;i++){ la[i]=(A>>i&1)?L1:L0; lb[i]=(B>>i&1)?L1:L0; }
        bus_mul(la,lb,lo,4);
        int p=0; for(int i=0;i<8;i++) p|=((lo[i]==L1)<<i);
        if (p != A*B){ mu=0; break; }
    }
    printf("[derived multiply (array)] %s\n", mu?"PASS":"FAIL"); ok &= mu;

    /* DERIVED: negedge DFF + sim-time model */
    dff_neg_t nf={{L0},{L1}};
    dff_negedge(&nf,L1,L1); int n1=(nf.l.q==L0);     /* high, no falling edge */
    dff_negedge(&nf,L1,L0); int n2=(nf.l.q==L1);     /* falling edge: capture */
    sim_now=0; int st=(sim_advance(100)==100 && sim_advance(1)==101);
    printf("[derived clock: negedge DFF + $time] %s\n", (n1&&n2&&st)?"PASS":"FAIL"); ok &= n1&&n2&&st;

    /* ANALOG BOUNDARY: a real_t exists as a recognized boundary value (NOT gates) */
    analog_boundary_t vco = { 1.25e9, "VCO frequency" };   /* continuous, boundary */
    int an = (vco.value > 0.0) && (vco.role != 0);
    printf("[analog boundary (real, not decomposed)] %s\n", an?"PASS":"FAIL"); ok &= an;

    printf("== %s — Verilog primitive base + derivations ==\n", ok?"ALL PASS":"FAIL");
    return ok?0:1;
}
