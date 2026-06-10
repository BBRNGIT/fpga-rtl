/* display.c — external display: scan the NIC seam + status lanes RAW and print
 * them. NO logic, NO compute (feedback_hft_display_rule). */
#include <stdio.h>
#include "nic_gen.h"
#include "display.h"

void display_show(const uint64_t *r) {
    printf("nic  (wire->fifo gateway — sample wire, dedup by seq, TAI-stamp, strobe seam)\n");
    printf("  --- nic->fifo seam (latest re-stamped packet) ---\n");
    printf("  SEAM_VALID=%llu  SEAM_STROBE=%llu  SEAM_DEDUP_MARK=%llu\n",
           (unsigned long long)r[NIC_SEAM_VALID],
           (unsigned long long)r[NIC_SEAM_STROBE],
           (unsigned long long)r[NIC_SEAM_DEDUP_MARK]);
    printf("  SEAM_SEQ=%llu  SEAM_TIME(TAI)=%llu  SEAM_SRC_TIME=%llu\n",
           (unsigned long long)r[NIC_SEAM_SEQ],
           (unsigned long long)r[NIC_SEAM_TIME],
           (unsigned long long)r[NIC_SEAM_SRC_TIME]);
    printf("  SEAM_BID_PX=%llu  SEAM_ASK_PX=%llu  SEAM_SYMBOL=%llu  SEAM_PIP=%llu  SEAM_COMMISSION=%llu\n",
           (unsigned long long)r[NIC_SEAM_BID_PX],
           (unsigned long long)r[NIC_SEAM_ASK_PX],
           (unsigned long long)r[NIC_SEAM_SYMBOL],
           (unsigned long long)r[NIC_SEAM_PIP],
           (unsigned long long)r[NIC_SEAM_COMMISSION]);
    printf("  NIC_TICKS=%llu  RING_DEPTH=%u\n",
           (unsigned long long)r[NIC_NIC_TICKS], NIC_RING_DEPTH);
}
