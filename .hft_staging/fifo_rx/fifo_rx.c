/* fifo_rx.c — the STARTER. One job: power on the CDC FIFO and step away. The
 * generated netlist (fifo_rx_gen.h) owns the data path; the canonical loop
 * (fifo_rx_run) self-runs on the device edge from the power bit until the
 * configured tick budget. Contains NO _tick and NO cell_*() (build-sequence law).
 *
 * The nic seam is presented on the FIFO's read port (the sibling window it
 * samples) — not test-time injection into the data path. At integration the live
 * nic seam window is sampled directly; the standalone starter presents fixed
 * re-stamped packets to demonstrate the MAC->internal crossing (fill then drain). */
#include "fifo_rx_gen.h"
#include "fifo_rx.h"

/* the FIFO device's register window (its address space). Single instance. */
static word_t g_fifo_regs[FIFO_REG_COUNT];

/* the nic seam window the FIFO SAMPLES (the seam the nic gateway would drive).
 * Lane map = nic_gen.h (generated from ../nic/nic.net.json — single source).
 * The FIFO is a read-only consumer of this window. */
static word_t g_nic_seam[NIC_REG_COUNT];

/* how many self-run edges to allow per presentation. The 2-FF synchronizers add a
 * 2-edge cross-domain latency before EMPTY/FULL reflect the opposite pointer, so a
 * presentation window must outlast the sync chain for the flag to settle. Four
 * edges (> the 2-FF depth) is the minimal settling budget. */
#define SETTLE_EDGES 4ULL

/* present one re-stamped packet on the nic seam window with the strobe asserted
 * (what the nic gateway would deposit). The FIFO samples these lanes. */
static void present_seam_packet(const fifo_rx_packet_t *p, uint64_t strobe) {
    g_nic_seam[NIC_SEAM_BID_PX]     = p->bid_px;
    g_nic_seam[NIC_SEAM_ASK_PX]     = p->ask_px;
    g_nic_seam[NIC_SEAM_TIME]       = p->time;
    g_nic_seam[NIC_SEAM_SRC_TIME]   = p->src_time;
    g_nic_seam[NIC_SEAM_SYMBOL]     = p->symbol;
    g_nic_seam[NIC_SEAM_PIP]        = p->pip;
    g_nic_seam[NIC_SEAM_COMMISSION] = p->commission;
    g_nic_seam[NIC_SEAM_SEQ]        = p->seq;
    g_nic_seam[NIC_SEAM_STROBE]     = strobe & 1ULL;
}

/* run the device for `edges` self-run edges from the current tick (config budget,
 * not external stepping — the device's own loop produces every edge). */
static void run_window(uint64_t edges) {
    g_fifo_regs[FIFO_FIFO_RUN_UNTIL] = g_fifo_regs[FIFO_FIFO_TICKS] + edges;
    fifo_rx_run(g_fifo_regs, g_nic_seam);
}

const uint64_t *fifo_rx_start_fill_drain(const fifo_rx_packet_t *pkts,
                                         uint64_t n_fill,
                                         uint64_t n_drain) {
    uint64_t i = 0ULL;

    fifo_rx_init(g_fifo_regs);     /* synchronous reset: all zero */
    nic_init(g_nic_seam);          /* zero the presented nic seam window */

    /* power on once — the clock self-runs in its own loop. */
    g_fifo_regs[FIFO_FIFO_POWER] = 1ULL;
    g_fifo_regs[FIFO_FIFO_RD_EN] = 0ULL;   /* read side idle during fill */

    /* FILL: present each packet with the strobe high; the device self-runs one
     * presentation window per packet, writing it to a slot and advancing the gray
     * write pointer (which then propagates through the read-domain 2-FF sync). */
    for (i = 0ULL; i < n_fill; i = i + 1ULL) {
        present_seam_packet(&pkts[i], 1ULL);
        run_window(1ULL);                  /* one honoured write edge */
    }

    /* let the write pointer fully cross into the read domain (2-FF settle) so the
     * read side sees ~EMPTY before draining. Strobe low: no further writes. */
    g_nic_seam[NIC_SEAM_STROBE] = 0ULL;
    run_window(SETTLE_EDGES);

    /* DRAIN: assert the read-enable; the device self-runs, popping one packet per
     * edge from the read pointer while ~EMPTY (the consumer's read side). */
    g_fifo_regs[FIFO_FIFO_RD_EN] = 1ULL;
    for (i = 0ULL; i < n_drain; i = i + 1ULL) {
        run_window(1ULL);                  /* one honoured read edge (if ~EMPTY) */
    }

    return g_fifo_regs;
}

const uint64_t *fifo_rx_window(void) {
    /* the FIFO register window: pointers, sync stages, FULL/EMPTY, fire flags, and
     * the packet-wide slot RAM. Read-only to the consumer (the FIFO is the sole
     * writer of its slots). */
    return g_fifo_regs;
}
