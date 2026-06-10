/* display.h — external display for fifo_rx: scan the pointer/flag/head-slot lanes
 * RAW and print them. NO logic, NO compute (feedback_hft_display_rule). */
#ifndef FIFO_RX_DISPLAY_H
#define FIFO_RX_DISPLAY_H

#include <stdint.h>

/* display_show: print the FIFO pointers (binary + gray), the synchronized
 * opposite-domain pointers, FULL/EMPTY, the fire flags, and the head slot the
 * pipeline consumer would sample next (the lanes at the read pointer). Reads the
 * register window raw — no compute. */
void display_show(const uint64_t *r);

#endif /* FIFO_RX_DISPLAY_H */
