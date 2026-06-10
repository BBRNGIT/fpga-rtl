/* display.h — EXTERNAL display. Reads the tai register lanes RAW and prints them.
 * NO logic. Off-clock, non-blocking. (feedback_hft_display_rule) */
#ifndef TAI_DISPLAY_H
#define TAI_DISPLAY_H

#include "tai_gen.h"

/* display_show: print the tai lanes exactly as the addressed memory holds them
 * (POWER, RUN_UNTIL, TAI_NS). Pure read + print. */
void display_show(const word_t *r);

#endif /* TAI_DISPLAY_H */
