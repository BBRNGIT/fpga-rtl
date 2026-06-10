/* dom.h — the order-book device: starter interface.
 *
 * The device logic lives in the GENERATED dom_gen.h (netlist -> gennet); this
 * header is only the host starter glue — NO _tick, NO cell_*() here
 * (build-sequence law).
 *
 * DOM samples the fifo_rx published window (the head slot at the read pointer +
 * the FIFO read-fire / empty flags, from fifo_rx_gen.h): on a honoured FIFO read
 * (RD_FIRE & ~EMPTY) it consumes the head packet, detects bid/ask price change vs
 * its PREV registers, updates the price-indexed tables + best/totals/derived/relay
 * + counters. Single internal-clock domain (the MAC->internal CDC is upstream in
 * fifo_rx). (DOM_PARTS_LIST §1, §13.) */
#ifndef DOM_H
#define DOM_H

#include "dom_gen.h"

/* A presented market packet (standalone demonstration of what fifo_rx would have
 * at its head slot). At integration the live fifo_rx window is sampled directly
 * each edge; this struct is the starter's way to present one packet on the FIFO
 * head + assert the read-fire for the standalone DOM (NOT data-path injection —
 * it sets the sampled fifo_rx published lanes the device reads). Price-only data
 * law: bid/ask/time/symbol/pip/commission/seq (no qty/side ghost values). */
typedef struct {
    uint64_t bid_px;
    uint64_t ask_px;
    uint64_t time;        /* TAI stamp (head TIME lane) */
    uint64_t src_time;
    uint64_t symbol;
    uint64_t pip;
    uint64_t commission;
    uint64_t seq;
} dom_packet_t;

/* dom_start_feed: power on DOM, present `n` market packets on the fifo_rx head slot
 * (each with the FIFO read-fire asserted for one DOM self-run edge), and let the
 * device self-run from its power bit. Returns the DOM register window for an
 * external display.
 *
 * No test-side stepping of the device: every DOM clock edge is produced by the
 * device's own self-run loop (dom_run) from the power bit; the starter only sets
 * the sampled fifo_rx head lanes between self-run windows (the real head-cadence
 * presentation). `session_base` and `pip_res` are config (set once). */
const uint64_t *dom_start_feed(const dom_packet_t *pkts, uint64_t n,
                               uint64_t session_base, uint64_t pip_res);

/* dom_window: the register window DOM drove (read-only to the consumer; DOM is the
 * sole writer of its window). Indicators read the RELAY/BEST/derived lanes. */
const uint64_t *dom_window(void);

#endif /* DOM_H */
