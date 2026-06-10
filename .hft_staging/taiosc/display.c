/* display.c — external display: scan the taisoc lanes RAW and print them.
 * NO logic — it only reads the addressed-memory values and prints them verbatim.
 * (feedback_hft_display_rule) */
#include <stdio.h>
#include "taisoc_gen.h"
#include "display.h"

void display_show(const word_t *r) {
    printf("taisoc  (TAI oscillator reference — free-running counter + edge strobe)\n");
    printf("  POWER     CYCLE   EDGE   RUN_UNTIL\n");
    printf("  %5llu  %8llu  %5llu  %10llu\n",
           (unsigned long long)r[TAISOC_TAISOC_POWER],
           (unsigned long long)r[TAISOC_TAISOC_CYCLE],
           (unsigned long long)r[TAISOC_TAISOC_EDGE],
           (unsigned long long)r[TAISOC_TAISOC_RUN_UNTIL]);
}
