/* display.c — external display: scan the MAC lanes RAW and print them. NO logic.
 * (feedback_hft_display_rule) */
#include <stdio.h>
#include "mac_gen.h"
#include "display.h"

void display_show(const word_t *r) {
    printf("mac  (125 MHz MAC sample clock — free-running counter + sample edge)\n");
    printf("  POWER     CYCLE   EDGE   RUN_UNTIL\n");
    printf("  %5llu  %8llu  %5llu  %10llu\n",
           (unsigned long long)r[MAC_MAC_POWER],
           (unsigned long long)r[MAC_MAC_CYCLE],
           (unsigned long long)r[MAC_MAC_EDGE],
           (unsigned long long)r[MAC_MAC_RUN_UNTIL]);
}
