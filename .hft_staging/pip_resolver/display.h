/* display.h — external display for the PIP_RESOLVER: scan the output/status lanes
 * RAW and print them. NO logic, NO compute (feedback_hft_display_rule). */
#ifndef PIP_RESOLVER_DISPLAY_H
#define PIP_RESOLVER_DISPLAY_H

#include <stdint.h>

/* display_show: print the PIP_RESOLVER output + status lanes (the resolved pip
 * value PIP_RESOLUTION_REG, the symbol it resolved, and the valid bit). Reads the
 * register window raw — no compute. */
void display_show(const uint64_t *r);

#endif /* PIP_RESOLVER_DISPLAY_H */
