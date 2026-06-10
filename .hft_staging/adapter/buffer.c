/* buffer.c — the buffer primitive: storage + file load + present records[POS].
 *
 * This is the canonical primitive where the (legal) conditionals and binary
 * file IO live — never in the generated device data path, never in a test.
 * buffer_present needs the generated ADP_* address map, so it is defined here
 * (after including the generated header). */
#include "adapter_gen.h"

/* the single shared buffer instance (declared extern in buffer.h). */
adp_record_t g_records[BUFFER_MAX_RECORDS];
uint64_t     g_record_count = 0ULL;

uint64_t buffer_load(const char *path) {
    FILE *fp = fopen(path, "rb");
    if (fp == NULL) {
        g_record_count = 0ULL;
        return 0ULL;
    }
    size_t n = fread(g_records, sizeof(adp_record_t), BUFFER_MAX_RECORDS, fp);
    fclose(fp);
    g_record_count = (uint64_t)n;
    return g_record_count;
}

uint64_t buffer_in_range(uint64_t pos) {
    return (pos < g_record_count) ? 1ULL : 0ULL;
}

/* buffer_present: drive RAW_*, RX_*, IN_RANGE from records[POS]. Past the end
 * it presents zeros with IN_RANGE=0 — a quiet tick, no ghost record. */
void buffer_present(uint64_t *r, uint64_t pos) {
    const uint64_t live = buffer_in_range(pos);
    const uint64_t idx  = live ? pos : 0ULL;
    const adp_record_t rec = g_records[idx];
    r[ADP_RAW_BID]  = live ? rec.bid : 0ULL;
    r[ADP_RAW_ASK]  = live ? rec.ask : 0ULL;
    r[ADP_RX_TS]    = live ? rec.ts  : 0ULL;
    r[ADP_RX_SEQ]   = live ? rec.seq : 0ULL;
    r[ADP_IN_RANGE] = live;
}
