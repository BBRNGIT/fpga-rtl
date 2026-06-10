/* display.h — EXTERNAL display. Reads the wire bus lanes RAW and prints them.
 * It carries NO logic: no compute, no reformat, no reshape — it shows what the
 * addressed memory holds. Off-clock, non-blocking. Not a device, not a netlist.
 * (feedback_hft_display_rule) */
#ifndef WIRE_DISPLAY_H
#define WIRE_DISPLAY_H

#include "wire_gen.h"

/* display_show: scan the wire bus lanes and print the current price-only packet
 * exactly as the addressed memory holds it (VALID, bid, ask, source time,
 * symbol, pip, commission, seq) — the value the NIC samples. Pure read + print. */
void display_show(const wire_word_t *w);

#endif /* WIRE_DISPLAY_H */
