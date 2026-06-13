/* display_adapter.h — the OFF-FABRIC display adapter (egress-side mirror of the
 * ingress `adapter`, but for the MONITOR boundary — NOT the trading egress).
 *
 * It is the SOLE reader of the framebuffer (via the display pin). It has its own
 * embedded display clock and its own read-bank RAM. On each display-clock tick
 * at the refresh cadence it takes an ATOMIC sample of the framebuffer into its
 * read bank; between samples the bank is a frozen, coherent frame. The TUI may
 * touch ONLY this adapter's published frame — never the framebuffer, pin, or fabric.
 *
 * Decoupling is structural: compute writes the framebuffer at MHz; this adapter
 * samples at the (slow) display rate; neither clock drives the other.
 */
#ifndef DISPLAY_ADAPTER_H
#define DISPLAY_ADAPTER_H
#include "fb.h"

typedef struct {
    unsigned long clk;             /* embedded display clock (counts display ticks) */
    unsigned long period;          /* compute-ticks-per-sample = compute_freq/refresh_freq */
    word_t bank[FB_NWORDS];        /* read bank: the frozen frame the TUI sees */
} display_adapter_t;

static inline void display_adapter_init(display_adapter_t *a, unsigned long period) {
    a->clk = 0; a->period = period;
    for (unsigned i = 0; i < FB_NWORDS; i++) a->bank[i] = 0u;
}

/* embedded display clock edge. At the refresh cadence, ATOMICALLY sample the
 * framebuffer (one pass over the pin) into the read bank. Returns 1 on a sample. */
static inline int display_adapter_tick(display_adapter_t *a) {
    a->clk++;
    if (a->period && (a->clk % a->period) == 0) {
        for (unsigned i = 0; i < FB_NWORDS; i++) a->bank[i] = fb_pin_read(i);
        return 1;
    }
    return 0;
}

/* the ONLY interface the TUI may use: a read-only, coherent frame. */
static inline const word_t *display_adapter_frame(const display_adapter_t *a) { return a->bank; }

#endif /* DISPLAY_ADAPTER_H */
