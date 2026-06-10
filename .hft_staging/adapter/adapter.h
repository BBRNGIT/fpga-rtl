/* adapter.h — starter entry point for the adapter device. */
#ifndef ADAPTER_H
#define ADAPTER_H

#include <stdint.h>

/* adapter_start: power on the adapter with the given binary record file and
 * per-source static config; run the free-running clock to buffer exhaustion;
 * return the device register window (display-out lanes) for an external display.
 * The starter powers on and steps away — it carries no data-path logic.
 *
 * speed scales the adapter's real-world clock rate (SPEED config, like pip):
 * ADP_CLK advances `speed` units per tick. Pass 1 for 1 real-world unit/tick
 * (unscaled real-world pacing); larger = faster playback. Local to the adapter;
 * never touches a system clock; never advanced by source timestamps. */
const uint64_t *adapter_start(const char *record_path,
                              uint64_t symbol, uint64_t pip, uint64_t commission,
                              uint64_t speed);

/* adapter_wire_bus: the passive wire bus the adapter drove (the WIRE_* lanes in
 * the wire window). 1-deep — the latest deposited price-only packet, the value
 * the NIC samples. The adapter is the bus's sole writer; this is the consumer's
 * read-only view at the seam. (INGRESS_FLOW.md s3, feedback_hft_wire_and_barrier) */
const uint64_t *adapter_wire_bus(void);

#endif /* ADAPTER_H */
