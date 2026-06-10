/* wire.c — the wire BUS instance: passive addressed memory, nothing more.
 *
 * The wire is PASSIVE: it owns the bus storage (its address window) and offers
 * power-on (zero) + an accessor. It runs NO clock, computes NOTHING, latches
 * NOTHING. The ADAPTER deposits the price-only packet into this memory (sole
 * writer); the NIC samples it. No replay/CSV/file token lives here — the wire
 * ingests no external data. (INGRESS_FLOW.md s3, feedback_hft_wire_and_barrier) */
#include "wire.h"

/* the wire's address window: the passive bus storage. Single instance. */
static wire_word_t g_wire_bus[WIRE_REG_COUNT];

wire_word_t *wire_bus(void) {
    return g_wire_bus;
}

const wire_word_t *wire_power_on(void) {
    wire_init(g_wire_bus);     /* power-off reset: every lane zero, no clock edge */
    return g_wire_bus;
}
