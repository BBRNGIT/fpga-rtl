/* display.c — external display: scan display-out lanes raw and print.
 * NO logic — it only reads register values and prints them verbatim. */
#include <stdio.h>
#include "adapter_gen.h"
#include "wire_gen.h"   /* the wire's canonical bus lane map (single source) */
#include "display.h"

void display_show(const uint64_t *r) {
    const uint64_t emitted = r[ADP_DISP_EMIT_COUNT];
    /* The device ring is a wrapping window of depth ADP_DISP_DEPTH; it retains
     * the most-recent `depth` emits. Show exactly min(emitted, depth) of them,
     * oldest->newest within the window. The window bound (min) and the wrap
     * index are the ONLY arithmetic here — values are read raw, never recomputed. */
    const uint64_t depth  = ADP_DISP_DEPTH;
    const uint64_t window = (emitted < depth) ? emitted : depth;
    printf("adapter display-out  (price-only wire; %llu emitted packet(s); "
           "showing most-recent %llu of %llu)\n",
           (unsigned long long)emitted,
           (unsigned long long)window, (unsigned long long)emitted);
    printf("  slot  VALID         bid           ask     src_time   now@emit    seq\n");
    /* oldest retained emit is at (emitted - window); wrap each into a ring slot.
     * slot field addresses are contiguous per the generated map — read raw. */
    for (uint64_t i = 0; i < window; i = i + 1ULL) {
        const uint64_t s = (emitted - window + i) & ADP_DISP_MASK;
        const uint64_t valid = r[ADP_DISP_0_WIRE_VALID + s * ADP_DISP_STRIDE];
        const uint64_t bid   = r[ADP_DISP_0_WIRE_BID_PX + s * ADP_DISP_STRIDE];
        const uint64_t ask   = r[ADP_DISP_0_WIRE_ASK_PX + s * ADP_DISP_STRIDE];
        const uint64_t tsrc  = r[ADP_DISP_0_WIRE_TIME   + s * ADP_DISP_STRIDE];
        const uint64_t now   = r[ADP_DISP_0_ADP_CLK_AT_EMIT + s * ADP_DISP_STRIDE];
        const uint64_t seq   = r[ADP_DISP_0_WIRE_SEQ    + s * ADP_DISP_STRIDE];
        printf("  %4llu  %5llu  %12llu  %12llu  %9llu  %9llu  %5llu\n",
               (unsigned long long)s, (unsigned long long)valid,
               (unsigned long long)bid, (unsigned long long)ask,
               (unsigned long long)tsrc, (unsigned long long)now,
               (unsigned long long)seq);
    }
}

void display_wire_bus(const uint64_t *bus) {
    /* the passive wire bus is 1-deep: the latest packet the adapter deposited,
     * exactly what the NIC samples. Read each lane raw; no compute, no reformat. */
    printf("\nwire bus  (adapter deposited -> passive addressed-memory; price-only; "
           "1-deep — the packet the NIC samples)\n");
    printf("  VALID         bid           ask     src_time    symbol      pip   "
           "commission    seq\n");
    printf("  %5llu  %12llu  %12llu  %9llu  %8llu  %7llu  %10llu  %5llu\n",
           (unsigned long long)bus[WIRE_WIRE_VALID],
           (unsigned long long)bus[WIRE_WIRE_BID_PX],
           (unsigned long long)bus[WIRE_WIRE_ASK_PX],
           (unsigned long long)bus[WIRE_WIRE_TIME],
           (unsigned long long)bus[WIRE_WIRE_SYMBOL],
           (unsigned long long)bus[WIRE_WIRE_PIP],
           (unsigned long long)bus[WIRE_WIRE_COMMISSION],
           (unsigned long long)bus[WIRE_WIRE_SEQ]);
}
