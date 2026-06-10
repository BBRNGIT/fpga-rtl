/* test_synth.c — THIN test: configure the bar period + present a sampled TAI value,
 * power on the rollover detector, display it. Nothing else. No clock loop, no
 * stepping, no orchestration, no injection. The device's own clock self-runs from
 * the power bit (inside the starter), bounded by the configured tick budget; the
 * display reads the lanes raw. (test_harness_law) */
#include "timeframe.h"
#include "display.h"

#define PERIOD_NS   1000ULL  /* bar period: 1000 ns base bar (operator config) */
#define TAI_SAMPLE  4200ULL  /* presented TAI sample (>= period -> a boundary fires) */
#define RUN_UNTIL     16ULL  /* configured self-run tick budget (config, not stepping) */

int main(void) {
    const word_t *regs = timeframe_start(PERIOD_NS, TAI_SAMPLE, RUN_UNTIL);
    display_show(regs);
    return 0;
}
