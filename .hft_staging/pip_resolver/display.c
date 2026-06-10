/* display.c — external display: scan the PIP_RESOLVER output + status lanes RAW
 * and print them. NO logic, NO compute (feedback_hft_display_rule). */
#include <stdio.h>
#include "pip_resolver_gen.h"
#include "display.h"

void display_show(const uint64_t *r) {
    printf("pip_resolver  (per-symbol pip lookup — sample SEAM_SYMBOL, index static table, publish PIP_RESOLUTION_REG)\n");
    printf("  --- pip resolution output (latest resolved symbol) ---\n");
    printf("  PIP_VALID=%llu  PIP_SYMBOL=%llu  PIP_RESOLUTION_REG=%llu\n",
           (unsigned long long)r[PIP_PIP_VALID],
           (unsigned long long)r[PIP_PIP_SYMBOL],
           (unsigned long long)r[PIP_PIP_RESOLUTION_REG]);
    printf("  PIP_TICKS=%llu  TABLE_DEPTH=%u\n",
           (unsigned long long)r[PIP_PIP_TICKS], PIP_TABLE_DEPTH);
}
