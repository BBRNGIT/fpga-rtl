/* test_tpo.c — thin test: power-on + synthetic abstract payload + display.
 * tpo is built to ABSTRACT ports (no DOM/wiring); the testbench drives them.
 * tpo counts time-ticks spent at each price-index over the bar. */
#include <stdio.h>
#include "tpo_gen.h"

int main(void) {
    word_t r[TPO_REG_COUNT] = {0};
    tpo_init(r);

    r[TPO_IN_BAR_TIME] = 4242u;
    /* price sits at index 3 for 4 ticks, visits index 6 for 1 of them */
    for (int t = 0; t < 4; t++) {
        r[TPO_IN_TOUCH_3] = 1u;
        r[TPO_IN_TOUCH_6] = (t == 2) ? 1u : 0u;
        tpo_tick(r);
    }
    printf("bar0 time-ticks: price idx3=%llu idx6=%llu\n",
           (unsigned long long)r[TPO_TPO_TIME_3],
           (unsigned long long)r[TPO_TPO_TIME_6]);

    /* boundary: commit bar0 into the record store, start bar1 fresh */
    r[TPO_IN_BAR_BOUNDARY] = 1u;
    r[TPO_IN_TOUCH_3] = 0u;
    r[TPO_IN_TOUCH_6] = 0u;
    tpo_tick(r);

    printf("record store slot0: TIME=%llu TPO[3]=%llu TPO[6]=%llu\n",
           (unsigned long long)r[TPO_TPO_HIST_0_TIME],
           (unsigned long long)r[TPO_TPO_HIST_0_TPO_3],
           (unsigned long long)r[TPO_TPO_HIST_0_TPO_6]);
    return 0;
}
