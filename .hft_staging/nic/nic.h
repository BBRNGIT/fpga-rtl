/* nic.h — the NIC gateway device (wire->fifo): starter interface.
 *
 * The device logic lives in the GENERATED nic_gen.h (netlist -> gennet); this
 * header is only the host starter glue — NO _tick, NO cell_*() here
 * (build-sequence law).
 *
 * The NIC samples the wire bus (WIRE_* lanes) and the MAC-domain TAI value
 * (TAI_MAC from tai_cdc), dedups by WIRE_SEQ, re-stamps the survivor with
 * TAI_MAC, and deposits the structured packet into its nic->fifo seam on a
 * 1-cycle write strobe. (INGRESS_FLOW.md s4, BLOCK_DIAGRAM #2) */
#ifndef NIC_H
#define NIC_H

#include "nic_gen.h"

/* A presented wire-bus packet (standalone demonstration of what the adapter would
 * have deposited on the wire). At integration the live wire-bus window is sampled
 * directly each mac edge; this struct is the starter's way to present one packet
 * to the standalone NIC for the thin test (NOT data-path injection — it sets the
 * sampled input lanes the device reads, same shape as the adapter->wire seam). */
typedef struct {
    uint64_t bid_px;
    uint64_t ask_px;
    uint64_t time;        /* source time */
    uint64_t symbol;
    uint64_t pip;
    uint64_t commission;
    uint64_t seq;
    uint64_t valid;       /* bit0 */
} nic_wire_packet_t;

/* nic_start_two: power on the NIC, present a first wire packet + TAI_MAC for a run
 * window, then present a SECOND packet + run again, and return the NIC register
 * window for an external display. The two-packet form lets the thin test observe
 * dedup (same seq dropped) vs. pass (different seq) + TAI stamp correctness, all
 * via the device's own self-running clock (no test-side stepping).
 *
 * tai_mac is the MAC-domain TAI value presented on the tai_cdc output lane the NIC
 * reads (standalone: a fixed representative value; at integration: the live
 * tai_cdc TAI_MAC each mac edge).
 *
 * Returns the device register window (seam + ring + status lanes) for display. */
const uint64_t *nic_start_two(const nic_wire_packet_t *p0,
                              const nic_wire_packet_t *p1,
                              uint64_t tai_mac,
                              uint64_t run_until_each);

/* nic_seam: the nic->fifo seam the NIC drove (the SEAM_* lanes in the NIC window).
 * The latest re-stamped packet — the value fifo_rx will sample. The NIC is the
 * seam's sole writer; this is the consumer's read-only view at the seam. */
const uint64_t *nic_seam(void);

#endif /* NIC_H */
