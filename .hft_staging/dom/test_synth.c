/* test_synth.c — THIN test: power on DOM (via the starter), display its best/
 * derived/relay/counter lanes. Nothing else. No clock loop, no stepping, no
 * orchestration, no data-path injection, no wire-read. The device's own clock
 * self-runs on its edge from the power bit (inside the starter); the display reads
 * the lanes raw. (test_harness_law)
 *
 * The starter presents three market packets on the fifo_rx head slot (the sibling
 * window DOM samples), each with the FIFO read-fire asserted; DOM self-runs one
 * edge per packet, consuming the head and updating the book. The display shows the
 * resulting best-of-book, derived spread/mid, and the relay ladder — proving the
 * packets flowed fifo_rx-head -> DOM and built the book. */
#include <stdio.h>
#include "dom.h"
#include "display.h"

/* a market packet: {bid, ask, time(TAI), src_time, sym, pip, com, seq} */
#define MK(bid, ask, tai, seq) { (bid), (ask), (tai), 7777ULL, 1ULL, 1ULL, 0ULL, (seq) }
#define SESSION_BASE 19000ULL
#define PIP_RES      1ULL

int main(void) {
    const dom_packet_t pkts[3] = {
        MK(19500ULL, 19510ULL, 0x1000ULL, 42ULL),   /* first quote */
        MK(19501ULL, 19511ULL, 0x1001ULL, 43ULL),   /* bid+ask move up */
        MK(19502ULL, 19512ULL, 0x1002ULL, 44ULL),   /* move up again */
    };

    printf("=== dom: feed 3 quotes (fifo_rx head -> DOM), build the book ===\n");
    printf("    (expect: BEST_BID=19502 BEST_ASK=19512 SPREAD=10 MID=19507) \n");
    display_show(dom_start_feed(pkts, 3ULL, SESSION_BASE, PIP_RES));
    return 0;
}
