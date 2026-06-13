/* display_tui.c — terminal monitor for DOM (live state + persistent memory),
 * reading ONLY the display adapter. Per DISPLAY_SPEC: dom publishes "entire DOM
 * output per update + DOM persistent memory". Flicker-free: the adapter hands the
 * TUI a frozen atomic frame; the TUI repaints in place (cursor-home overwrite).
 *
 * Framebuffer slice layout for dom (written by the compute-domain relay):
 *   [0..9]  live: bid, ask, spread, mid, total_bid, total_ask, pkt, add, cancel, last_feed
 *   [10..]  persistent memory window: MEM_ROWS newest records * (bid, ask, tai)
 */
#include "dom_synth_load.h"
#include "display_adapter.h"
#include <stdio.h>
typedef unsigned long long ull;

#define MEM_ROWS 8u
#define LIVE     10u

/* ---- the compute-domain RELAY: dom display view -> framebuffer slice --------*/
static void relay_dom(void) {
    word_t v[FB_NWORDS] = {0};
    v[0]=synth_dom_DOM_BEST_BID_PRICE_REG(); v[1]=synth_dom_DOM_BEST_ASK_PRICE_REG();
    v[2]=synth_dom_DOM_SPREAD_REG();         v[3]=synth_dom_DOM_MID_PRICE_REG();
    v[4]=synth_dom_DOM_TOTAL_BID_QTY_REG();  v[5]=synth_dom_DOM_TOTAL_ASK_QTY_REG();
    v[6]=synth_dom_DOM_PKT_COUNT_REG();      v[7]=synth_dom_DOM_ADD_COUNT_REG();
    v[8]=synth_dom_DOM_CANCEL_COUNT_REG();   v[9]=synth_dom_DOM_LAST_FEED_TIME_REG();
    /* newest records first (slot 0 = newest in the shift-in store) */
    word_t (*mb[])(void) = {
        synth_dom_DOM_BOOK_0_BID_PX, synth_dom_DOM_BOOK_1_BID_PX, synth_dom_DOM_BOOK_2_BID_PX,
        synth_dom_DOM_BOOK_3_BID_PX, synth_dom_DOM_BOOK_4_BID_PX, synth_dom_DOM_BOOK_5_BID_PX,
        synth_dom_DOM_BOOK_6_BID_PX, synth_dom_DOM_BOOK_7_BID_PX };
    word_t (*ma[])(void) = {
        synth_dom_DOM_BOOK_0_ASK_PX, synth_dom_DOM_BOOK_1_ASK_PX, synth_dom_DOM_BOOK_2_ASK_PX,
        synth_dom_DOM_BOOK_3_ASK_PX, synth_dom_DOM_BOOK_4_ASK_PX, synth_dom_DOM_BOOK_5_ASK_PX,
        synth_dom_DOM_BOOK_6_ASK_PX, synth_dom_DOM_BOOK_7_ASK_PX };
    word_t (*mt[])(void) = {
        synth_dom_DOM_BOOK_0_TAI, synth_dom_DOM_BOOK_1_TAI, synth_dom_DOM_BOOK_2_TAI,
        synth_dom_DOM_BOOK_3_TAI, synth_dom_DOM_BOOK_4_TAI, synth_dom_DOM_BOOK_5_TAI,
        synth_dom_DOM_BOOK_6_TAI, synth_dom_DOM_BOOK_7_TAI };
    for (unsigned r = 0; r < MEM_ROWS; r++) {
        v[LIVE + r*3 + 0] = mb[r](); v[LIVE + r*3 + 1] = ma[r](); v[LIVE + r*3 + 2] = mt[r]();
    }
    fb_write(v, FB_NWORDS);
}

/* ---- the TUI: reads ONLY the adapter frame, repaints in place --------------*/
static void tui_paint(const display_adapter_t *disp, int home) {
    const word_t *f = display_adapter_frame(disp);
    if (home) printf("\033[H");                       /* cursor home: flicker-free overwrite */
    printf("+-- DOM  Depth of Market -----------------------------------+\n");
    printf("|  BID %-10llu  ASK %-10llu  SPREAD %-6llu  MID %-10llu\n",
           (ull)f[0], (ull)f[1], (ull)f[2], (ull)f[3]);
    printf("|  total bid/ask %llu/%llu   pkts %llu  add %llu  cancel %llu   lastTAI %llu\n",
           (ull)f[4], (ull)f[5], (ull)f[6], (ull)f[7], (ull)f[8], (ull)f[9]);
    printf("+-- persistent memory (newest first) ----------------------+\n");
    printf("|   #     BID         ASK         TAI\n");
    for (unsigned r = 0; r < MEM_ROWS; r++)
        printf("|  %2u  %-10llu  %-10llu  %llu\n", r,
               (ull)f[LIVE+r*3+0], (ull)f[LIVE+r*3+1], (ull)f[LIVE+r*3+2]);
    printf("+----------------------------------------------------------+\n");
    fflush(stdout);
}

int main(int argc, char **argv) {
    int live_term = (argc > 1 && argv[1][0] == 'l');  /* 'l' = live cursor-home repaint */
    fpga_device_init(); synth_dom_load();
    display_adapter_t disp; display_adapter_init(&disp, 64);

    if (live_term) printf("\033[2J");                  /* clear once; then repaint in place */
    else printf("DOM terminal monitor — compute free-runs; display samples at decimated rate.\n\n");

    unsigned long seq = 2463534242u;
    for (unsigned long t = 0; t < 384; t++) {
        seq ^= seq<<13; seq ^= seq>>17; seq ^= seq<<5;
        word_t bid = 100000u + (seq % 50u), ask = bid + 5u + ((seq>>8)%5u);
        word_t in[7] = { 1u, 1000000u, bid, ask, t, 1u, 0u };
        for (int k=0;k<7;k++) for (int i=0;i<64;i++) synth_dom_in[k][i]=(in[k]>>i)&1u;
        synth_dom_tick();          /* compute edge (fabric), free-running */
        relay_dom();               /* relay -> framebuffer, free-running */
        if (display_adapter_tick(&disp)) {           /* display clock sample */
            tui_paint(&disp, live_term);
            if (!live_term) printf("   (display frame %lu, after %lu compute ticks)\n\n", disp.clk/disp.period, t+1);
        }
    }
    return 0;
}
