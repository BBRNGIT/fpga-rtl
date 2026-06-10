/* nic.c — the STARTER. One job: power on the NIC gateway and step away. The
 * generated netlist (nic_gen.h) owns the data path; the canonical loop (nic_run)
 * self-runs on the MAC edge from the power bit until the configured tick budget.
 * Contains NO _tick and NO cell_*() (build-sequence law).
 *
 * The wire bus + TAI_MAC are presented on the NIC's read ports (the sibling
 * windows it samples) — not test-time injection into the data path. At integration
 * the live wire-bus window and live tai_cdc window are sampled directly; the
 * standalone starter presents fixed values to demonstrate dedup + TAI stamp. */
#include "nic_gen.h"
#include "nic.h"

/* the NIC device's register window (its address space). Single instance. */
static word_t g_nic_regs[NIC_REG_COUNT];

/* the wire bus window the NIC SAMPLES (the passive bus the adapter would drive).
 * Lane map = wire_gen.h (generated from ../wire/wire.net.json — single source).
 * The NIC is a read-only consumer of this window. */
static wire_word_t g_wire_bus[WIRE_REG_COUNT];

/* the tai_cdc output window the NIC reads TAI_MAC from (MAC-domain TAI value).
 * Lane map = tai_cdc_gen.h (generated from ../tai_cdc/tai_cdc.net.json). The NIC
 * is a read-only consumer; tai_cdc is the sole writer in the real system. */
static word_t g_tai_window[TAI_CDC_REG_COUNT];

/* present a wire packet onto the wire-bus window (what the adapter would deposit). */
static void present_wire_packet(const nic_wire_packet_t *p) {
    g_wire_bus[WIRE_WIRE_BID_PX]     = p->bid_px;
    g_wire_bus[WIRE_WIRE_ASK_PX]     = p->ask_px;
    g_wire_bus[WIRE_WIRE_TIME]       = p->time;
    g_wire_bus[WIRE_WIRE_SYMBOL]     = p->symbol;
    g_wire_bus[WIRE_WIRE_PIP]        = p->pip;
    g_wire_bus[WIRE_WIRE_COMMISSION] = p->commission;
    g_wire_bus[WIRE_WIRE_SEQ]        = p->seq;
    g_wire_bus[WIRE_WIRE_VALID]      = p->valid & 1ULL;
}

const uint64_t *nic_start_two(const nic_wire_packet_t *p0,
                              const nic_wire_packet_t *p1,
                              uint64_t tai_mac,
                              uint64_t run_until_each) {
    nic_init(g_nic_regs);                         /* synchronous reset: all zero */
    wire_init(g_wire_bus);                         /* zero the presented wire bus */
    tai_cdc_init(g_tai_window);                    /* zero the presented tai window */

    /* present the MAC-domain TAI value on the tai_cdc output lane the NIC reads. */
    g_tai_window[TAI_CDC_TAI_MAC] = tai_mac;

    /* power on once — the clock self-runs in its own loop. */
    g_nic_regs[NIC_NIC_POWER] = 1ULL;

    /* The NIC samples the wire ONCE per mac-cadence presentation (one slot = one
     * re-stamped packet; non-blocking sampler — no buffering of a static input).
     * We model each presentation as exactly ONE self-run tick by setting the tick
     * budget one above the current tick count. Re-running the SAME static input
     * for many ticks would self-trip the dedup ring (the device's own correct
     * behavior) and obscure the per-packet PASS/DUP signal under test. The
     * run_until_each argument is retained as the configured budget shape (>=1);
     * the per-presentation step is one tick, the real mac-cadence sample rate. */
    (void)run_until_each;

    /* presentation 1: packet 0. First sight of its seq PASSES (strobe high) and
     * updates the dedup ring at idx = seq & (depth-1). */
    present_wire_packet(p0);
    g_nic_regs[NIC_NIC_RUN_UNTIL] = g_nic_regs[NIC_NIC_TICKS] + 1ULL;
    nic_run(g_nic_regs, g_wire_bus, g_tai_window);

    /* presentation 2: packet 1 (one mac edge later). If p1.seq == p0.seq the ring
     * marks it a DUP (strobe low, dedup_mark 1); a different seq PASSES (strobe
     * high, dedup_mark 0). The final seam state reflects THIS presentation. */
    present_wire_packet(p1);
    g_nic_regs[NIC_NIC_RUN_UNTIL] = g_nic_regs[NIC_NIC_TICKS] + 1ULL;
    nic_run(g_nic_regs, g_wire_bus, g_tai_window);

    return g_nic_regs;
}

const uint64_t *nic_seam(void) {
    /* the nic->fifo seam the NIC drove (1-deep: the latest re-stamped packet — the
     * value fifo_rx would sample). Read-only to the consumer (the NIC is the sole
     * writer). The seam lanes live in the NIC window. */
    return g_nic_regs;
}
