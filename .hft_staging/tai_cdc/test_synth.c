/* test_synth.c — THIN test: power on the TAI CDC synchronizer, display it.
 * Nothing else. No clock loop, no stepping, no orchestration. The device's own
 * sync self-runs on the MAC edge from the power bit (inside the starter), bounded
 * by the configured tick budget; the display reads the lanes raw. (test_harness_law)
 *
 * TAI_IN is starter config (the source-domain sample): after >= 2 settling edges
 * the gray-decoded TAI_MAC equals TAI_IN — the round-trip the NIC relies on. */
#include "tai_cdc.h"
#include "display.h"

#define TAI_IN_SAMPLE  0x0123456789ABCDEFULL  /* representative source-domain value */
#define RUN_UNTIL      8ULL                    /* configured tick budget (>= 2 to settle) */

int main(void) {
    const word_t *regs = tai_cdc_start(TAI_IN_SAMPLE, RUN_UNTIL);
    display_show(regs);
    return 0;
}
