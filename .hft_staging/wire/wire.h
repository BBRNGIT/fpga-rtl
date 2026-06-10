/* wire.h — the wire BUS: a passive addressed-memory boundary (adapter -> NIC).
 *
 * The wire is PASSIVE (INGRESS_FLOW.md s3, feedback_hft_wire_and_barrier): no
 * clock, no compute, no logic of its own. It is just addressed storage holding
 * the price-only packet — non-blocking, 1-deep (latest packet, overwritten
 * freely). The wire writes NOTHING itself.
 *
 *   - single writer = the ADAPTER, which DEPOSITS the packet into this memory
 *     (it drives the bus). The WIRE_* lanes live here, in the wire window —
 *     not in a private adapter copy.
 *   - reader = the NIC, which SAMPLES this memory on the mac cadence.
 *
 * The wire exists because a module may not read another module's registers
 * directly: it is the required barrier/medium both sides meet at. This header
 * is the bus interface; there is no _tick and no _run — a bus has no logic. */
#ifndef WIRE_H
#define WIRE_H

#include "wire_gen.h"   /* the bus address map (WIRE_* lane indices) + wire_init */

/* wire_power_on: bring the passive bus up = zero every lane (power-off reset
 * value). The wire owns no clock; this is the only state operation it has. */
const wire_word_t *wire_power_on(void);

/* wire_bus: the addressed-memory window the adapter deposits into and the NIC
 * samples. Returns the single bus instance (mutable: the adapter is the sole
 * writer; the NIC reads). A lane needs an address — this storage IS the wire. */
wire_word_t *wire_bus(void);

#endif /* WIRE_H */
