/* test_synth.c — THIN test: power on the NIC, display its seam. Nothing else. No
 * clock loop, no stepping, no orchestration, no data-path injection. The device's
 * own clock self-runs on the MAC edge from the power bit (inside the starter); the
 * display reads the seam lanes raw. (test_harness_law)
 *
 * Two scenarios prove the gateway:
 *   DUP : p1.seq == p0.seq  -> second sighting dropped (strobe low, dedup_mark 1).
 *   PASS: p1.seq != p0.seq  -> second sighting passed  (strobe high, dedup_mark 0).
 * Both stamp SEAM_TIME with the presented TAI_MAC (stamp correctness on display). */
#include <stdio.h>
#include "nic.h"
#include "display.h"

#define TAI_MAC_SAMPLE  0x00ABCDEF12345678ULL  /* MAC-domain TAI value (tai_cdc out) */
#define RUN_EACH        4ULL                    /* mac-edge budget per packet window */

/* a representative price-only wire packet (what the adapter would deposit). */
#define MK(seq)  { 19500ULL, 19510ULL, 7777ULL, 1ULL, 100ULL, 0ULL, (seq), 1ULL }

int main(void) {
    const nic_wire_packet_t p_a   = MK(42ULL);   /* first sighting of seq 42 */
    const nic_wire_packet_t p_dup = MK(42ULL);   /* same seq -> DUP (dropped)  */
    const nic_wire_packet_t p_new = MK(43ULL);   /* new seq  -> PASS (emitted) */

    printf("=== NIC dedup: same seq presented twice (expect DUP: strobe 0, dedup_mark 1) ===\n");
    display_show(nic_start_two(&p_a, &p_dup, TAI_MAC_SAMPLE, RUN_EACH));

    printf("\n=== NIC dedup: different seq (expect PASS: strobe 1, dedup_mark 0, TAI stamp) ===\n");
    display_show(nic_start_two(&p_a, &p_new, TAI_MAC_SAMPLE, RUN_EACH));
    return 0;
}
