/* test_footprint.c — thin test: power-on + synthetic abstract payload + display.
 * footprint is built to ABSTRACT ports (no DOM/wiring); the testbench drives them. */
#include <stdio.h>
#include "footprint_gen.h"

int main(void) {
    word_t r[FOOTPRINT_REG_COUNT] = {0};
    footprint_init(r);

    r[FOOTPRINT_IN_BAR_TIME] = 1000u;
    for (int t = 0; t < 3; t++) {
        r[FOOTPRINT_IN_BID_ACT_2] = 5u;
        r[FOOTPRINT_IN_ASK_ACT_2] = 3u;
        r[FOOTPRINT_IN_ASK_ACT_5] = 7u;
        footprint_tick(r);
    }
    printf("bar0 accumulators: idx2 bid=%llu ask=%llu | idx5 ask=%llu\n",
           (unsigned long long)r[FOOTPRINT_FP_BID_VOL_2],
           (unsigned long long)r[FOOTPRINT_FP_ASK_VOL_2],
           (unsigned long long)r[FOOTPRINT_FP_ASK_VOL_5]);

    r[FOOTPRINT_IN_BAR_BOUNDARY] = 1u;
    r[FOOTPRINT_IN_BID_ACT_2] = 0u;
    r[FOOTPRINT_IN_ASK_ACT_2] = 0u;
    r[FOOTPRINT_IN_ASK_ACT_5] = 0u;
    footprint_tick(r);

    printf("record store slot0: TIME=%llu VOL[2]=%llu VOL[5]=%llu\n",
           (unsigned long long)r[FOOTPRINT_FP_HIST_0_TIME],
           (unsigned long long)r[FOOTPRINT_FP_HIST_0_VOL_2],
           (unsigned long long)r[FOOTPRINT_FP_HIST_0_VOL_5]);
    return 0;
}
