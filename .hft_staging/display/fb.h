/* fb.h — the on-fabric DISPLAY FRAMEBUFFER (dual-port BRAM) + its display pin.
 *
 * Live framebuffer: a reserved BRAM tile, written CONTINUOUSLY by the compute
 * domain (the install relay) — no throttle. One cell per published display word.
 * The framebuffer's READ port is the DISPLAY PIN (fb_pin_read) — and ONLY the
 * display adapter is permitted to call it (layering law: the TUI never reaches
 * the framebuffer; it talks only to its display adapter, exactly as the fabric
 * reads `wire` and never reaches back to `adapter`).
 */
#ifndef DISPLAY_FB_H
#define DISPLAY_FB_H
#include "fpga_device_gen.h"     /* fpga_bram, word_t, bram_block_tick */

#define FB_TILE   100u           /* reserved framebuffer tile (compute-state BRAM is elsewhere) */
#define FB_NWORDS 64u            /* published display words per frame (fits one BRAM tile) */

/* compute-domain WRITER (relay): module display view -> framebuffer slice, then
 * latch. Free-running — called every compute tick; never gated by the display. */
static inline void fb_write(const word_t *v, unsigned n) {
    for (unsigned i = 0; i < n; i++) {
        fpga_bram[FB_TILE][0u + i]   = v[i];   /* DIN_i  */
        fpga_bram[FB_TILE][576u + i] = 1u;     /* WE_i   */
    }
    bram_block_tick(fpga_bram[FB_TILE]);
    for (unsigned i = 0; i < n; i++) fpga_bram[FB_TILE][576u + i] = 0u; /* clear WE -> hold */
}

/* DISPLAY PIN = the framebuffer READ port. SOLE caller: the display adapter. */
static inline word_t fb_pin_read(unsigned i) { return fpga_bram[FB_TILE][1152u + i]; }

#endif /* DISPLAY_FB_H */
