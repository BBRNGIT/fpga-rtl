/* test_synth.c — THIN test: power on the taisoc oscillator, display it. Nothing
 * else. No clock loop, no stepping, no orchestration, no data injection. The
 * device's own clock self-runs from the power bit (inside the starter), bounded
 * by the configured run count; the display reads the lanes raw. (test_harness_law) */
#include "taisoc.h"
#include "display.h"

/* configured self-run bound: how far the oscillator counts before power drops.
 * This is configuration handed to the starter, not external stepping. */
#define RUN_UNTIL  16ULL

int main(void) {
    const word_t *regs = taisoc_start(RUN_UNTIL);
    display_show(regs);
    return 0;
}
