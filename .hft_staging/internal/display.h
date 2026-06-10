/* display.h — EXTERNAL display. Reads the internal register lanes RAW and prints
 * them. NO logic. Off-clock, non-blocking. (feedback_hft_display_rule) */
#ifndef INTERNAL_DISPLAY_H
#define INTERNAL_DISPLAY_H

#include "internal_gen.h"

/* display_show: print the internal lanes exactly as the addressed memory holds
 * them (POWER, CYCLE, EDGE, RUN_UNTIL). Pure read + print. */
void display_show(const word_t *r);

#endif /* INTERNAL_DISPLAY_H */
