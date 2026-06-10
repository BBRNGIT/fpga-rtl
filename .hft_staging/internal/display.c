/* display.c — external display: scan the internal lanes RAW and print them.
 * NO logic. (feedback_hft_display_rule) */
#include <stdio.h>
#include "internal_gen.h"
#include "display.h"

void display_show(const word_t *r) {
    printf("internal  (250 MHz pipeline metronome — free-running counter + edge)\n");
    printf("  POWER     CYCLE   EDGE   RUN_UNTIL\n");
    printf("  %5llu  %8llu  %5llu  %10llu\n",
           (unsigned long long)r[INTERNAL_INTERNAL_POWER],
           (unsigned long long)r[INTERNAL_INTERNAL_CYCLE],
           (unsigned long long)r[INTERNAL_INTERNAL_EDGE],
           (unsigned long long)r[INTERNAL_INTERNAL_RUN_UNTIL]);
}
