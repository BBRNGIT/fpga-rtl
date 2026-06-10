/* display.c — external display: scan the tai lanes RAW and print them. NO logic.
 * (feedback_hft_display_rule) */
#include <stdio.h>
#include "tai_gen.h"
#include "display.h"

void display_show(const word_t *r) {
    printf("tai  (authoritative TAI timestamp — plain counter off taisoc, no discipline)\n");
    printf("  POWER   RUN_UNTIL       TAI_NS\n");
    printf("  %5llu  %10llu  %11llu\n",
           (unsigned long long)r[TAI_TAI_POWER],
           (unsigned long long)r[TAI_TAI_RUN_UNTIL],
           (unsigned long long)r[TAI_TAI_NS]);
}
