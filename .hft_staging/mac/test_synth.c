/* test_synth.c — THIN test: power on the MAC clock, display it. Nothing else.
 * No clock loop, no stepping, no orchestration, no injection. The device's own
 * clock self-runs from the power bit (inside the starter), bounded by the
 * configured run count; the display reads the lanes raw. (test_harness_law) */
#include "mac.h"
#include "display.h"

#define RUN_UNTIL  16ULL   /* configured self-run bound (config, not stepping) */

int main(void) {
    const word_t *regs = mac_start(RUN_UNTIL);
    display_show(regs);
    return 0;
}
