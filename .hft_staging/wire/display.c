/* display.c — external display: scan the wire bus lanes RAW and print them.
 * NO logic — it only reads the addressed-memory values and prints them verbatim.
 * The wire is 1-deep (the current packet); this shows exactly what the NIC would
 * sample. (feedback_hft_display_rule) */
#include <stdio.h>
#include "wire.h"
#include "display.h"

void display_show(const wire_word_t *w) {
    /* the bus is 1-deep: the latest deposited packet, the value the NIC samples.
     * Read each lane raw; no compute, no reformat. */
    printf("wire bus  (passive addressed-memory boundary; price-only; 1-deep — "
           "the current packet the NIC samples)\n");
    printf("  VALID         bid           ask     src_time    symbol      pip   "
           "commission    seq\n");
    printf("  %5llu  %12llu  %12llu  %9llu  %8llu  %7llu  %10llu  %5llu\n",
           (unsigned long long)w[WIRE_WIRE_VALID],
           (unsigned long long)w[WIRE_WIRE_BID_PX],
           (unsigned long long)w[WIRE_WIRE_ASK_PX],
           (unsigned long long)w[WIRE_WIRE_TIME],
           (unsigned long long)w[WIRE_WIRE_SYMBOL],
           (unsigned long long)w[WIRE_WIRE_PIP],
           (unsigned long long)w[WIRE_WIRE_COMMISSION],
           (unsigned long long)w[WIRE_WIRE_SEQ]);
}
