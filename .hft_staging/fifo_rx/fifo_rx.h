/* fifo_rx.h — the MAC->internal CDC FIFO device: starter interface.
 *
 * The device logic lives in the GENERATED fifo_rx_gen.h (netlist -> gennet); this
 * header is only the host starter glue — NO _tick, NO cell_*() here
 * (build-sequence law).
 *
 * fifo_rx samples the nic seam (SEAM_* lanes from nic_gen.h): on the nic
 * SEAM_STROBE it stores the re-stamped packet into the slot at its write pointer
 * and advances the (gray) write pointer; the pipeline consumer pops a packet by
 * asserting the read-enable, advancing the (gray) read pointer. The pointers cross
 * the MAC<->internal boundary through dual 2-FF synchronizers; FULL/EMPTY are
 * derived from the synced opposite-domain pointer. (BLOCK_DIAGRAM #3; the OB TX
 * FIFO Cummings pattern, mirrored on RX.) */
#ifndef FIFO_RX_H
#define FIFO_RX_H

#include "fifo_rx_gen.h"

/* A presented nic-seam packet (standalone demonstration of what the nic gateway
 * would have deposited on its seam). At integration the live nic seam window is
 * sampled directly each edge; this struct is the starter's way to present one
 * re-stamped packet to the standalone FIFO for the thin test (NOT data-path
 * injection — it sets the sampled nic-seam input lanes the device reads). */
typedef struct {
    uint64_t bid_px;
    uint64_t ask_px;
    uint64_t time;        /* TAI stamp (SEAM_TIME) */
    uint64_t src_time;    /* source time (SEAM_SRC_TIME) */
    uint64_t symbol;
    uint64_t pip;
    uint64_t commission;
    uint64_t seq;
} fifo_rx_packet_t;

/* fifo_rx_start_fill_drain: power on the FIFO, present `n_fill` distinct packets on
 * the nic seam with the write strobe high (the device self-runs, writing each into
 * a slot and advancing the write pointer + 2-FF syncs), then assert the read-enable
 * for `n_drain` edges (the device self-runs, popping from the read pointer). Returns
 * the device register window for an external display.
 *
 * No test-side stepping: every clock edge is produced by the device's own self-run
 * loop (fifo_rx_run) from the power bit; the starter only sets the sampled input
 * lanes between self-run windows (the real seam-cadence presentation). */
const uint64_t *fifo_rx_start_fill_drain(const fifo_rx_packet_t *pkts,
                                         uint64_t n_fill,
                                         uint64_t n_drain);

/* fifo_rx_head: the register window the FIFO drove. The read-side head slot (the
 * packet the pipeline would sample next) is at fifo_rx_head_addr(); the display
 * reads these lanes raw. The FIFO is the sole writer of its slots; this is the
 * consumer's read-only view. */
const uint64_t *fifo_rx_window(void);

#endif /* FIFO_RX_H */
