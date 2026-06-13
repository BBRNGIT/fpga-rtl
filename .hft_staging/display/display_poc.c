/* display_poc.c — vertical slice: dom (on fabric) -> framebuffer -> display
 * adapter -> TUI. Proves the decoupled display path end to end.
 *
 * Layering (no link is skipped):
 *   fabric dom  -> [relay, compute domain] -> framebuffer (BRAM)
 *   framebuffer -> [display pin]          -> display adapter (own clock + bank)
 *   display adapter -> [published frame]  -> TUI
 * The TUI calls ONLY display_adapter_frame(); it never touches the framebuffer,
 * the pin, or the fabric.
 */
#include "dom_synth_load.h"        /* fabric + cell-synthesized dom */
#include "display_adapter.h"
#include <stdio.h>
typedef unsigned long long ull;

/* minimal TUI — reads ONLY the adapter's frame. */
static void tui_render(const display_adapter_t *disp, unsigned long compute_tick) {
    const word_t *f = display_adapter_frame(disp);
    printf("  TUI frame (compute tick %3lu): bid=%llu ask=%llu spread=%llu mid=%llu  totals b/a=%llu/%llu\n",
           compute_tick, (ull)f[0], (ull)f[1], (ull)f[2], (ull)f[3], (ull)f[4], (ull)f[5]);
}

int main(void) {
    fpga_device_init();
    synth_dom_load();

    display_adapter_t disp;
    display_adapter_init(&disp, 64);   /* sample every 64 compute ticks (~refresh decimation) */

    printf("dom runs 256 compute ticks; display samples every 64 — fully decoupled.\n");
    printf("(compute churns the framebuffer continuously; the TUI only sees stable sampled frames)\n\n");

    unsigned long seq = 2463534242u, frames = 0;
    /* inputs order: DOM_POWER, DOM_RUN_UNTIL, BID_PX, ASK_PX, TAI, RD_FIRE, FIFO_EMPTY */
    for (unsigned long t = 0; t < 256; t++) {
        seq ^= seq << 13; seq ^= seq >> 17; seq ^= seq << 5;
        word_t bid = 100000u + (seq % 50u);
        word_t ask = bid + 5u + ((seq >> 8) % 5u);
        word_t in[7] = { 1u, 1000000u, bid, ask, t, 1u, 0u };  /* powered, consume a packet each tick */
        for (int k = 0; k < 7; k++)
            for (int i = 0; i < 64; i++) synth_dom_in[k][i] = (in[k] >> i) & 1u;

        synth_dom_tick();                                       /* compute edge (fabric) */

        /* RELAY (compute domain): dom display view -> framebuffer slice, free-running */
        word_t dv[6] = {
            synth_dom_DOM_BEST_BID_PRICE_REG(), synth_dom_DOM_BEST_ASK_PRICE_REG(),
            synth_dom_DOM_SPREAD_REG(),         synth_dom_DOM_MID_PRICE_REG(),
            synth_dom_DOM_TOTAL_BID_QTY_REG(),  synth_dom_DOM_TOTAL_ASK_QTY_REG()
        };
        fb_write(dv, 6);

        if (display_adapter_tick(&disp)) { tui_render(&disp, t + 1); frames++; }
    }
    printf("\n256 compute ticks -> %lu display frames (decoupled, atomic, flicker-free).\n", frames);
    return 0;
}
