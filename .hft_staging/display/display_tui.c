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
#define LIVE     12u   /* declared dom display view: 12 live words, then 8x(bid,ask,tai) */

/* ---- the compute-domain RELAY: declared display view -> framebuffer slice ---*/
/* Uses the formal synth_dom_display_view() emitted from dom_logic.yaml's
 * display_outputs — no hand-listed accessors. */
static void relay_dom(void) {
    word_t v[FB_NWORDS] = {0};
    synth_dom_display_view(v);               /* SYNTH_DOM_DISPLAY_WORDS = 36 */
    fb_write(v, FB_NWORDS);
}

/* ---- the TUI: reads ONLY the adapter frame, repaints in place --------------*/
static void tui_paint(const display_adapter_t *disp, int home) {
    const word_t *f = display_adapter_frame(disp);
    if (home) printf("\033[H");                       /* cursor home: flicker-free overwrite */
    printf("+-- DOM  Depth of Market -----------------------------------+\n");
    printf("|  BID %-10llu (q%llu)  ASK %-10llu (q%llu)  SPREAD %-4llu  MID %-10llu\n",
           (ull)f[0], (ull)f[1], (ull)f[2], (ull)f[3], (ull)f[4], (ull)f[5]);
    printf("|  total bid/ask %llu/%llu   pkts %llu  add %llu  cancel %llu   lastTAI %llu\n",
           (ull)f[6], (ull)f[7], (ull)f[8], (ull)f[9], (ull)f[10], (ull)f[11]);
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
    fb_bind_pin();                                      /* bind framebuffer -> GTY display pin */
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
