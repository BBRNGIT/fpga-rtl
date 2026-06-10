/* test_synth.c — THIN test: power on the passive wire bus, display it. Nothing
 * else. The wire has no clock, no logic, no buffer, no data file — it is just
 * addressed memory. Power-on zeroes the bus (its only operation); the display
 * reads the lanes raw. The adapter (the sole writer) deposits into this bus and
 * the NIC samples it — that end-to-end drive is demonstrated in the adapter
 * tree, where the writer lives. (test_harness_law) */
#include "wire.h"
#include "display.h"

int main(void) {
    const wire_word_t *bus = wire_power_on();   /* bring the passive bus up */
    display_show(bus);                           /* read the lanes raw */
    return 0;
}
