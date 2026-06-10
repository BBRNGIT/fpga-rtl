/* display.c — external display: scan the fifo_rx pointer/flag/head-slot lanes RAW
 * and print them. NO logic, NO compute (feedback_hft_display_rule). The head-slot
 * addresses come from the GENERATED fifo_rx_head_addr (address math in the netlist
 * header, not display compute). */
#include <stdio.h>
#include "fifo_rx_gen.h"
#include "display.h"

void display_show(const uint64_t *r) {
    /* head slot lane register addresses (the packet the consumer samples next).
     * lane order matches the emitter PACKET_LANES: bid,ask,time,src_time,sym,pip,
     * commission,seq — offsets 0..7 within the slot. */
    const uint64_t a_bid  = fifo_rx_head_addr(r, 0ULL);
    const uint64_t a_ask  = fifo_rx_head_addr(r, 1ULL);
    const uint64_t a_time = fifo_rx_head_addr(r, 2ULL);
    const uint64_t a_srct = fifo_rx_head_addr(r, 3ULL);
    const uint64_t a_sym  = fifo_rx_head_addr(r, 4ULL);
    const uint64_t a_pip  = fifo_rx_head_addr(r, 5ULL);
    const uint64_t a_com  = fifo_rx_head_addr(r, 6ULL);
    const uint64_t a_seq  = fifo_rx_head_addr(r, 7ULL);

    printf("fifo_rx  (MAC->internal async CDC FIFO — gray pointers, dual 2-FF sync, depth %u)\n",
           FIFO_DEPTH);
    printf("  --- pointers (binary | gray) ---\n");
    printf("  WR_BIN=%llu WR_GRAY=0x%llx | RD_BIN=%llu RD_GRAY=0x%llx\n",
           (unsigned long long)r[FIFO_FIFO_WR_BIN], (unsigned long long)r[FIFO_FIFO_WR_GRAY],
           (unsigned long long)r[FIFO_FIFO_RD_BIN], (unsigned long long)r[FIFO_FIFO_RD_GRAY]);
    printf("  --- synced opposite-domain pointers (2-FF stable) ---\n");
    printf("  WQ2_RGRAY=0x%llx (read ptr in write domain) | RQ2_WGRAY=0x%llx (write ptr in read domain)\n",
           (unsigned long long)r[FIFO_FIFO_WQ2_RGRAY],
           (unsigned long long)r[FIFO_FIFO_RQ2_WGRAY]);
    printf("  --- flags ---\n");
    printf("  FULL=%llu EMPTY=%llu  WR_FIRE=%llu RD_FIRE=%llu  TICKS=%llu\n",
           (unsigned long long)r[FIFO_FIFO_FULL], (unsigned long long)r[FIFO_FIFO_EMPTY],
           (unsigned long long)r[FIFO_FIFO_WR_FIRE], (unsigned long long)r[FIFO_FIFO_RD_FIRE],
           (unsigned long long)r[FIFO_FIFO_TICKS]);
    printf("  --- head slot (packet the consumer samples next, at RD pointer) ---\n");
    printf("  SEQ=%llu TIME(TAI)=%llu SRC_TIME=%llu\n",
           (unsigned long long)r[a_seq], (unsigned long long)r[a_time],
           (unsigned long long)r[a_srct]);
    printf("  BID_PX=%llu ASK_PX=%llu SYMBOL=%llu PIP=%llu COMMISSION=%llu\n",
           (unsigned long long)r[a_bid], (unsigned long long)r[a_ask],
           (unsigned long long)r[a_sym], (unsigned long long)r[a_pip],
           (unsigned long long)r[a_com]);
}
