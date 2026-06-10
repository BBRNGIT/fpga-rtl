/* display.h — external display for DOM: scan the best/derived/relay/counter lanes
 * RAW and print them. NO logic, NO compute (feedback_hft_display_rule). */
#ifndef DOM_DISPLAY_H
#define DOM_DISPLAY_H

#include <stdint.h>

/* display_show: print the DOM best bid/ask (price + qty), running totals, derived
 * spread/mid, the diagnostic counters, the feed time, and the top relay levels.
 * Reads the register window raw — no compute. */
void display_show(const uint64_t *r);

#endif /* DOM_DISPLAY_H */
