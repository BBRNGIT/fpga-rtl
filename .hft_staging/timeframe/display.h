/* display.h — EXTERNAL display. Reads the timeframe register lanes RAW and prints
 * them. NO logic. Off-clock, non-blocking. (feedback_hft_display_rule) */
#ifndef TIMEFRAME_DISPLAY_H
#define TIMEFRAME_DISPLAY_H

#include "timeframe_gen.h"

/* display_show: print the timeframe lanes exactly as the addressed memory holds them
 * (POWER, PERIOD_NS, TAI_IN, BAR_SEQ, BAR_CLOSED, BAR_START). Pure read + print. */
void display_show(const word_t *r);

#endif /* TIMEFRAME_DISPLAY_H */
