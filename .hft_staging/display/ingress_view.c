/* ingress_view.c — off-fabric display views for adapter + wire. Each reads ONLY
 * its own module's registers/lanes (a passive tap; no compute, no recompute). */
#include "ingress_view.h"
#include "adapter_gen.h"   /* ADP_DISP_*, ADP_WIRE_PIP/COMMISSION */
#include "wire_gen.h"      /* WIRE_WIRE_* lane indices */

/* lane offset within an adapter display-ring slot (derived from the macros). */
#define ADP_BASE   (ADP_DISP_0_WIRE_VALID)
#define ADP_STRIDE (ADP_DISP_1_WIRE_VALID - ADP_DISP_0_WIRE_VALID)
#define ADP_OFF(M) ((ADP_DISP_0_##M) - (ADP_DISP_0_WIRE_VALID))

void adapter_display_view(const uint64_t *r, uint64_t *out) {
    /* newest emitted packet = the last-written slot of the wrapping ring. */
    uint64_t emit = r[ADP_DISP_EMIT_COUNT];
    unsigned newest = emit ? (unsigned)((emit - 1u) % (uint64_t)ADP_DISP_DEPTH) : 0u;
    unsigned s = ADP_BASE + newest * ADP_STRIDE;
    out[0] = r[s + ADP_OFF(WIRE_VALID)];
    out[1] = r[s + ADP_OFF(WIRE_BID_PX)];
    out[2] = r[s + ADP_OFF(WIRE_ASK_PX)];
    out[3] = r[s + ADP_OFF(WIRE_TIME)];
    out[4] = r[s + ADP_OFF(WIRE_SEQ)];
    out[5] = r[s + ADP_OFF(ADP_CLK_AT_EMIT)];
    out[6] = r[ADP_WIRE_COMMISSION];          /* per-source config */
    out[7] = r[ADP_WIRE_PIP];
    out[8] = 0u;                              /* news payload — only if the source API provides */
    out[9] = 0u;                              /* news valid = 0 (absent; not invented, Law #13) */
}

void wire_display_view(const uint64_t *w, uint64_t *out) {
    out[0] = w[WIRE_WIRE_BID_PX];
    out[1] = w[WIRE_WIRE_ASK_PX];
    out[2] = w[WIRE_WIRE_TIME];
    out[3] = w[WIRE_WIRE_SYMBOL];
    out[4] = w[WIRE_WIRE_PIP];
    out[5] = w[WIRE_WIRE_COMMISSION];
    out[6] = w[WIRE_WIRE_SEQ];
    out[7] = w[WIRE_WIRE_VALID];
}
