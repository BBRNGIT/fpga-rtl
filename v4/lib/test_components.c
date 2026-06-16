/* test_components.c — prove each component by PLACING it (fixed address), WIRING
 * it in place, and checking the device drives its output. Links components.c. */
#include <stdio.h>
#include "components.h"

int main(void){
    int ok = 1;

    { wire_t a={LO},b={LO},y={X}; nand_t g={&a,&b,&y}; int t=1;
      a.level=LO;b.level=LO;nand_settle(&g); t&=(y.level==HI);
      a.level=HI;b.level=HI;nand_settle(&g); t&=(y.level==LO);
      printf("NAND  00->1 11->0 .......... %s\n", t?"ok":"FAIL"); ok&=t; }

    { wire_t a={LO},y={X}; not_t p; wire_not(&p,&a,&y); int t=1;
      a.level=LO;not_settle(&p); t&=(y.level==HI);
      a.level=HI;not_settle(&p); t&=(y.level==LO);
      printf("NOT   0->1 1->0 ............ %s\n", t?"ok":"FAIL"); ok&=t; }

    { int t=1; for(int A=0;A<2;A++)for(int B=0;B<2;B++){
        wire_t a={A?HI:LO},b={B?HI:LO},y={X}; and_t g; wire_and(&g,&a,&b,&y);
        and_settle(&g); t&=(y.level==((A&&B)?HI:LO));
      } printf("AND   all combos ........... %s\n", t?"ok":"FAIL"); ok&=t; }

    { int t=1; for(int A=0;A<2;A++)for(int B=0;B<2;B++){
        wire_t a={A?HI:LO},b={B?HI:LO},y={X}; or_t g; wire_or(&g,&a,&b,&y);
        or_settle(&g); t&=(y.level==((A||B)?HI:LO));
      } printf("OR    all combos ........... %s\n", t?"ok":"FAIL"); ok&=t; }

    { int t=1; for(int A=0;A<2;A++)for(int B=0;B<2;B++){
        wire_t a={A?HI:LO},b={B?HI:LO},y={X}; xor_t g; wire_xor(&g,&a,&b,&y);
        xor_settle(&g); t&=(y.level==((A^B)?HI:LO));
      } printf("XOR   all combos ........... %s\n", t?"ok":"FAIL"); ok&=t; }

    { int t=1; for(int A=0;A<2;A++)for(int B=0;B<2;B++)for(int S=0;S<2;S++){
        wire_t a={A?HI:LO},b={B?HI:LO},s={S?HI:LO},y={X}; mux_t m; wire_mux(&m,&a,&b,&s,&y);
        mux_settle(&m); int exp=S?B:A; t&=(y.level==(exp?HI:LO));
      } printf("MUX   sel?B:A all combos ... %s\n", t?"ok":"FAIL"); ok&=t; }

    { wire_t d={HI},g={HI},q={LO}; latch_t L; wire_latch(&L,&d,&g,&q); int t=1;
      d.level=HI;g.level=HI;latch_settle(&L); t&=(q.level==HI);
      d.level=LO;g.level=LO;latch_settle(&L); t&=(q.level==HI);   /* hold */
      d.level=LO;g.level=HI;latch_settle(&L); t&=(q.level==LO);
      printf("LATCH load/hold ............ %s\n", t?"ok":"FAIL"); ok&=t; }

    { wire_t in={LO}; edge_t e={LO,&in}; int t=1;
      in.level=LO; t&=(edge_pos(&e)==0);
      in.level=HI; t&=(edge_pos(&e)==1);
      in.level=HI; t&=(edge_pos(&e)==0);
      printf("EDGE  rising detect ........ %s\n", t?"ok":"FAIL"); ok&=t; }

    { wire_t d={HI},c={LO},q={LO}; dff_t ff; wire_dff(&ff,&d,&c,&q); int t=1;
      d.level=HI;c.level=LO;dff_settle(&ff); t&=(q.level==LO);
      c.level=HI;dff_settle(&ff); t&=(q.level==HI);
      d.level=LO;c.level=HI;dff_settle(&ff); t&=(q.level==HI);   /* hold */
      printf("DFF   capture-on-edge ...... %s\n", t?"ok":"FAIL"); ok&=t; }

    /* REG as a FLIP-FLOP: same reg, driven by always @(posedge clk) -> captures on edge */
    { wire_t d={HI},c={LO},q={LO}; reg_t r; wire_reg(&r,&d,&q); edge_t clk={LO,&c}; int t=1;
      d.level=HI; c.level=LO; reg_capture(&r,&clk); t&=(q.level==LO);  /* no edge: hold */
      c.level=HI;            reg_capture(&r,&clk); t&=(q.level==HI);  /* rising: capture 1 */
      d.level=LO; c.level=HI; reg_capture(&r,&clk); t&=(q.level==HI);  /* no edge: hold */
      printf("REG   as flip-flop (clocked) %s\n", t?"ok":"FAIL"); ok&=t; }

    /* REG as a WIRE: same reg, driven by always @(*) -> follows D combinationally */
    { wire_t d={LO},q={X}; reg_t r; wire_reg(&r,&d,&q); int t=1;
      d.level=HI; reg_drive(&r); t&=(q.level==HI);   /* tracks D */
      d.level=LO; reg_drive(&r); t&=(q.level==LO);   /* tracks D, no storage */
      printf("REG   as wire (combinational) %s\n", t?"ok":"FAIL"); ok&=t; }

    /* Z-RESOLVE: weak-pulldown input conditioning (Z->LO, levels pass, X holds) */
    { int t=1;
      t&=(resolve_z(LO)==LO); t&=(resolve_z(HI)==HI);
      t&=(resolve_z(X)==X);   t&=(resolve_z(Z)==LO);
      printf("ZRES  (!==z)&&x  Z->0 ...... %s\n", t?"ok":"FAIL"); ok&=t; }

    /* TRI1 / TRI0: undriven net pulls HI / LO; driven level passes; X holds */
    { int t=1;
      t&=(resolve_tri1(Z)==HI); t&=(resolve_tri1(LO)==LO); t&=(resolve_tri1(HI)==HI); t&=(resolve_tri1(X)==X);
      t&=(resolve_tri0(Z)==LO); t&=(resolve_tri0(LO)==LO); t&=(resolve_tri0(HI)==HI); t&=(resolve_tri0(X)==X);
      printf("TRI   tri1->1 / tri0->0 .... %s\n", t?"ok":"FAIL"); ok&=t; }

    /* THE LANGUAGE verbs: AND/OR/NOT/XOR/MUX/EQ/Z/ASSIGN on wires, via wired parts */
    { int t=1;
      for(int A=0;A<2;A++)for(int B=0;B<2;B++){
        level_t a=A?HI:LO,b=B?HI:LO;
        t&=(AND(a,b)==((A&&B)?HI:LO));
        t&=(OR (a,b)==((A||B)?HI:LO));
        t&=(XOR(a,b)==((A^B)?HI:LO));
        t&=(EQ (a,b)==((A==B)?HI:LO));
        t&=(MUX(a,b,LO)==a); t&=(MUX(a,b,HI)==b);
      }
      t&=(NOT(LO)==HI); t&=(NOT(HI)==LO);
      t&=(RESZ(Z)==LO); t&=(RESZ(HI)==HI);
      wire_t n={X}; ASSIGN(&n, OR(AND(HI,HI),AND(LO,HI))); t&=(rd(&n)==HI);
      printf("LANG  AND/OR/NOT/XOR/MUX/EQ/Z/ASSIGN %s\n", t?"ok":"FAIL"); ok&=t; }

    printf("== %s — component library (all parts wired from NAND) ==\n", ok?"ALL PASS":"FAIL");
    return ok?0:1;
}
