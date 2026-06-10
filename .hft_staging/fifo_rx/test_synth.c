/* test_synth.c — THIN test: power on the FIFO (via the starter), display its
 * pointers + flags + head slot. Nothing else. No clock loop, no stepping, no
 * orchestration, no data-path injection, no wire-read. The device's own clock
 * self-runs on its edge from the power bit (inside the starter); the display reads
 * the lanes raw. (test_harness_law)
 *
 * The starter fills three distinct re-stamped packets on the MAC (write) side,
 * lets the gray write pointer cross into the read domain (2-FF settle), then drains
 * one packet on the internal (read) side. The display shows the head slot the
 * consumer would sample next + the cross-domain pointer state — proving a strobed
 * packet entered the MAC side and exited the internal side intact. */
#include <stdio.h>
#include "fifo_rx.h"
#include "display.h"

/* a re-stamped nic-seam packet: {bid, ask, time(TAI), src_time, sym, pip, com, seq} */
#define MK(seq, tai) { 19500ULL, 19510ULL, (tai), 7777ULL, 1ULL, 100ULL, 0ULL, (seq) }

int main(void) {
    const fifo_rx_packet_t pkts[3] = {
        MK(42ULL, 0x1000ULL),    /* first packet written  */
        MK(43ULL, 0x1001ULL),    /* second packet         */
        MK(44ULL, 0x1002ULL),    /* third packet          */
    };

    printf("=== fifo_rx: fill 3 packets (MAC side), settle CDC, then no drain ===\n");
    printf("    (expect: WR_BIN=3, EMPTY=0 after settle, head slot = seq 42) \n");
    display_show(fifo_rx_start_fill_drain(pkts, 3ULL, 0ULL));

    printf("\n=== fifo_rx: fill 3, settle, drain 1 (internal side pops head) ===\n");
    printf("    (expect: RD_BIN=1, head advances to seq 43) \n");
    display_show(fifo_rx_start_fill_drain(pkts, 3ULL, 1ULL));
    return 0;
}
