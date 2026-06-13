/* ingress_run.c — driver proving the off-fabric ingress display (adapter + wire)
 * through the SAME pipeline: off-fabric view -> framebuffer slice -> GTY pin ->
 * display adapter -> TUI. The adapter self-runs (reads the record file, emits to
 * wire); we relay its latest packet + the wire lanes into the framebuffer and
 * render. The TUI shows adapter==wire (ingress integrity).
 */
#include "adapter.h"           /* adapter_start, adapter_wire_bus (off-fabric ingress) */
#include "display_adapter.h"   /* on-fabric framebuffer + off-fabric display adapter */
#include "ingress_view.h"      /* off-fabric display views */
#include "tui.h"
#include <stdio.h>

#ifndef RECORD_FILE
#define RECORD_FILE "adapter/data_synth.bin"
#endif

int main(void) {
    /* run the real ingress: adapter powers on, reads the file, drives the wire. */
    const uint64_t *regs = adapter_start(RECORD_FILE, 1ULL, 100ULL, 0ULL, 1ULL);
    const uint64_t *wire = adapter_wire_bus();

    fpga_device_init();
    fb_bind_pin();
    display_adapter_t disp; display_adapter_init(&disp, 1);

    uint64_t frame[FB_NWORDS]; for (unsigned i = 0; i < FB_NWORDS; i++) frame[i] = 0;
    /* RELAY (compute side): each module's display view -> its framebuffer slice. */
    adapter_display_view(regs, frame + 0);     /* slice [0..9]  */
    wire_display_view(wire,  frame + 10);      /* slice [10..17] */
    fb_write(frame, 18);

    display_adapter_tick(&disp);               /* display clock sample */
    tui_render_ingress(display_adapter_frame(&disp), 0);
    return 0;
}
