/* display.c — external display: scan the timeframe lanes RAW and print them. NO
 * logic, NO compute, NO reformat. (feedback_hft_display_rule) */
#include <stdio.h>
#include "timeframe_gen.h"
#include "display.h"

void display_show(const word_t *r) {
    printf("timeframe  (bar-boundary clock — rollover detector, a guide not a master)\n");
    printf("  POWER     PERIOD_NS        TAI_IN     BAR_SEQ  BAR_CLOSED     BAR_START\n");
    printf("  %5llu  %12llu  %12llu  %10llu  %10llu  %12llu\n",
           (unsigned long long)r[TIMEFRAME_TF_POWER],
           (unsigned long long)r[TIMEFRAME_TF_PERIOD_NS],
           (unsigned long long)r[TIMEFRAME_TF_TAI_IN],
           (unsigned long long)r[TIMEFRAME_TF_BAR_SEQ],
           (unsigned long long)r[TIMEFRAME_TF_BAR_CLOSED],
           (unsigned long long)r[TIMEFRAME_TF_BAR_START]);
}
