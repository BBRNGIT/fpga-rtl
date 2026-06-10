/* display.h — EXTERNAL display. Reads register (display-out) lanes RAW and
 * prints them. It carries NO logic: no compute, no reformat, no reshape — it
 * shows what the registers hold. Off-clock, non-blocking. Not a device, not a
 * netlist. (feedback_hft_display_rule) */
#ifndef ADAPTER_DISPLAY_H
#define ADAPTER_DISPLAY_H

#include <stdint.h>

/* display_show: scan the adapter's display-ring lanes and print each emitted
 * packet exactly as the registers hold it (WIRE_VALID, bid, ask, source time,
 * now-at-emit, seq). Pure register read + print. */
void display_show(const uint64_t *r);

/* display_wire_bus: scan the WIRE BUS lanes RAW and print the current price-only
 * packet the adapter deposited (the value the NIC samples). Pure read + print —
 * proves the adapter drove the passive bus. (feedback_hft_wire_and_barrier) */
void display_wire_bus(const uint64_t *bus);

#endif /* ADAPTER_DISPLAY_H */
