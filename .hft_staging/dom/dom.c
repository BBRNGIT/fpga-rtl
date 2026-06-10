/* dom.c — the STARTER. One job: power on the order book and step away. The
 * generated netlist (dom_gen.h) owns the data path; the canonical loop (dom_run)
 * self-runs on the device edge from the power bit until the configured tick budget.
 * Contains NO _tick and NO cell_*() (build-sequence law).
 *
 * DOM samples the fifo_rx published window (the head slot it reads via the
 * producer's generated fifo_rx_head_addr, gated by the FIFO read-fire). The
 * standalone starter presents fixed market packets on that window (the sibling
 * window DOM samples) — not test-time injection into the data path. At integration
 * the live fifo_rx window is sampled directly. */
#include "dom_gen.h"
#include "dom.h"

/* the DOM device's register window (its address space). Single instance. */
static word_t g_dom_regs[DOM_REG_COUNT];

/* the fifo_rx window DOM SAMPLES (the FIFO the upstream gateway would drive). Lane
 * map = fifo_rx_gen.h (generated from ../fifo_rx/fifo_rx.net.json — single source).
 * DOM is a read-only consumer of this window. */
static word_t g_fifo_regs[FIFO_REG_COUNT];

/* present one market packet on the fifo_rx head slot (at the FIFO read pointer)
 * with the read-fire asserted (what the FIFO would publish on a honoured read).
 * DOM samples these lanes via fifo_rx_head_addr. The head slot address is the
 * producer's generated address helper — no private copy of the FIFO map. */
static void present_head_packet(const dom_packet_t *p, uint64_t fire) {
    g_fifo_regs[fifo_rx_head_addr(g_fifo_regs, 0ULL)] = p->bid_px;
    g_fifo_regs[fifo_rx_head_addr(g_fifo_regs, 1ULL)] = p->ask_px;
    g_fifo_regs[fifo_rx_head_addr(g_fifo_regs, 2ULL)] = p->time;
    g_fifo_regs[fifo_rx_head_addr(g_fifo_regs, 3ULL)] = p->src_time;
    g_fifo_regs[fifo_rx_head_addr(g_fifo_regs, 4ULL)] = p->symbol;
    g_fifo_regs[fifo_rx_head_addr(g_fifo_regs, 5ULL)] = p->pip;
    g_fifo_regs[fifo_rx_head_addr(g_fifo_regs, 6ULL)] = p->commission;
    g_fifo_regs[fifo_rx_head_addr(g_fifo_regs, 7ULL)] = p->seq;
    g_fifo_regs[FIFO_FIFO_RD_FIRE] = fire & 1ULL;   /* honoured-read gate */
    g_fifo_regs[FIFO_FIFO_EMPTY]   = (fire & 1ULL) ^ 1ULL;  /* ~fire => empty */
}

/* run the device for one self-run edge from the current tick (config budget, not
 * external stepping — the device's own loop produces the edge). */
static void run_one_edge(void) {
    g_dom_regs[DOM_DOM_RUN_UNTIL] = g_dom_regs[DOM_DOM_TICKS] + 1ULL;
    dom_run(g_dom_regs, g_fifo_regs);
}

const uint64_t *dom_start_feed(const dom_packet_t *pkts, uint64_t n,
                               uint64_t session_base, uint64_t pip_res) {
    uint64_t i = 0ULL;

    dom_init(g_dom_regs);          /* synchronous reset: all zero */
    fifo_rx_init(g_fifo_regs);     /* zero the presented fifo_rx window */

    /* config (set once): session base price + relay pip step. */
    g_dom_regs[DOM_DOM_SESSION_BASE] = session_base;
    g_dom_regs[DOM_DOM_PIP_RES]      = pip_res;

    /* power on once — the clock self-runs in its own loop. */
    g_dom_regs[DOM_DOM_POWER] = 1ULL;

    /* present each packet on the FIFO head with the read-fire asserted; the device
     * self-runs one edge per packet, consuming the head and updating the book. The
     * FIFO read pointer is advanced between presentations so each packet lands in a
     * fresh head slot (the head-cadence the FIFO would publish). */
    for (i = 0ULL; i < n; i = i + 1ULL) {
        present_head_packet(&pkts[i], 1ULL);
        run_one_edge();                          /* one honoured-read edge */
        g_fifo_regs[FIFO_FIFO_RD_BIN] = g_fifo_regs[FIFO_FIFO_RD_BIN] + 1ULL;
    }

    return g_dom_regs;
}

const uint64_t *dom_window(void) {
    /* the DOM register window: best/totals/derived/relay/counters + the price
     * tables. Read-only to the consumer (DOM is the sole writer of its window). */
    return g_dom_regs;
}
