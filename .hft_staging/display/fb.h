/* fb.h — the on-fabric DISPLAY FRAMEBUFFER (dual-port BRAM) + its GTY display pin.
 *
 * Live framebuffer: a reserved BRAM tile (partitioned away from compute-state BRAM),
 * written CONTINUOUSLY by the compute domain (the install relay) — no throttle.
 * The framebuffer's location is published on a GTY lane = the DISPLAY PIN; the
 * framebuffer READ port is reached THROUGH that pin (fb_pin_read). ONLY the display
 * adapter may call it (layering law: the TUI never reaches the framebuffer; it talks
 * only to its display adapter, as the fabric reads `wire` and never reaches `adapter`).
 */
#ifndef DISPLAY_FB_H
#define DISPLAY_FB_H
#include "fpga_device_gen.h"     /* fpga_bram, fpga_gty_lanes, word_t, bram_block_tick */

#define FB_TILE     100u         /* reserved framebuffer tile (compute-state BRAM is elsewhere) */
#define FB_NWORDS   64u          /* published display words per frame (fits one BRAM tile) */
#define DISPLAY_PIN 0u           /* GTY lane designated as the display-out pin */

/* install-time binding: publish the framebuffer location on the display pin. */
static inline void fb_bind_pin(void) { fpga_gty_lanes[DISPLAY_PIN] = FB_TILE; }

/* compute-domain WRITER (relay): module display view -> framebuffer slice, then
 * latch. Free-running — called every compute tick; never gated by the display. */
static inline void fb_write(const word_t *v, unsigned n) {
    for (unsigned i = 0; i < n; i++) {
        fpga_bram[FB_TILE][0u + i]   = v[i];   /* DIN_i */
        fpga_bram[FB_TILE][576u + i] = 1u;     /* WE_i  */
    }
    bram_block_tick(fpga_bram[FB_TILE]);
    for (unsigned i = 0; i < n; i++) fpga_bram[FB_TILE][576u + i] = 0u; /* clear WE -> hold */
}

/* DISPLAY PIN read = framebuffer read port, located via the GTY pin. SOLE caller:
 * the display adapter. */
static inline word_t fb_pin_read(unsigned i) {
    unsigned tile = (unsigned)fpga_gty_lanes[DISPLAY_PIN];
    return fpga_bram[tile][1152u + i];          /* CELL_i */
}

#endif /* DISPLAY_FB_H */
