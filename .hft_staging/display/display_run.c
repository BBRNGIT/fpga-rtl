/* display_run.c — the driver (compute + relay + display adapter). This is the
 * "system" side that the BIOS will eventually own: it runs the fabric, relays the
 * module display view into the framebuffer, ticks the display adapter, and hands
 * each sampled frame to the pure TUI. It is the ONLY place that touches both the
 * fabric and the adapter; the TUI (tui.c) sees only frames.
 */
#include "dom_synth_load.h"        /* fabric + cell-synthesized dom */
#include "display_adapter.h"       /* off-fabric display adapter (own clock + read bank) */
#include "tui.h"                   /* pure renderer */
#include <stdio.h>

/* compute-domain RELAY: the module's declared display view -> framebuffer slice. */
static void relay_dom(void) {
    word_t v[FB_NWORDS] = {0};
    synth_dom_display_view(v);                 /* declared in dom_logic.yaml */
    fb_write(v, FB_NWORDS);
}

int main(int argc, char **argv) {
    int live_term = (argc > 1 && argv[1][0] == 'l');
    fpga_device_init();
    synth_dom_load();
    fb_bind_pin();                             /* framebuffer -> GTY display pin */
    display_adapter_t disp; display_adapter_init(&disp, 64);

    if (live_term) printf("\033[2J");
    else printf("DOM monitor — compute free-runs; display samples at decimated rate.\n\n");

    unsigned long seq = 2463534242u;
    for (unsigned long t = 0; t < 384; t++) {
        seq ^= seq<<13; seq ^= seq>>17; seq ^= seq<<5;
        word_t bid = 100000u + (seq % 50u), ask = bid + 5u + ((seq>>8)%5u);
        word_t in[7] = { 1u, 1000000u, bid, ask, t, 1u, 0u };
        for (int k=0;k<7;k++) for (int i=0;i<64;i++) synth_dom_in[k][i]=(in[k]>>i)&1u;
        synth_dom_tick();                      /* compute edge (fabric), free-running */
        relay_dom();                           /* relay -> framebuffer, free-running */
        if (display_adapter_tick(&disp))       /* display clock atomic sample */
            tui_render_dom(display_adapter_frame(&disp), disp.clk/disp.period, live_term);
    }
    return 0;
}
