/* buffer.h — the adapter's buffer primitive.
 *
 * The buffer is a CANONICAL PRIMITIVE: the ONE place conditionals and file
 * reading live (never in a generated component, never in a test). It holds the
 * records (the data exists, loaded at once from a BINARY file — the in-system
 * path never parses) and presents records[POS] into the device's input
 * registers each tick.
 *
 * Records are BINARY (produced by the offline prep, outside the system). No
 * float, no malloc — a fixed static array. No replay/CSV/source-type token
 * appears here: the buffer holds standardized records, nothing source-specific.
 */
#ifndef ADAPTER_BUFFER_H
#define ADAPTER_BUFFER_H

#include <stdint.h>
#include <stdio.h>

#define BUFFER_MAX_RECORDS 65536u

/* A standardized binary record. Prices are fixed-point u64 (×PRICE_SCALE);
 * ts is the source timestamp in the source's own integer unit; seq dedup. */
typedef struct {
    uint64_t bid;
    uint64_t ask;
    uint64_t ts;
    uint64_t seq;
} adp_record_t;

/* file-scope buffer state — single shared instance (defined in buffer.c).
 * Static fixed storage, no heap. Declared extern so every TU sees one copy. */
extern adp_record_t g_records[BUFFER_MAX_RECORDS];
extern uint64_t      g_record_count;

/* buffer_load: read the binary record file at once. Conditionals/IO live here.
 * Returns the count loaded. Called by the starter before power-on. */
uint64_t buffer_load(const char *path);

/* buffer_in_range: (POS < count). Used by the clock loop and as IN_RANGE. */
uint64_t buffer_in_range(uint64_t pos);

/* buffer_present: drive the buffer's output registers from records[POS].
 * Past the end it presents zeros with IN_RANGE=0 (quiet, no ghost record).
 * The conditional here is buffer logic (legal), not device data-path logic.
 * Defined in buffer.c (needs the generated ADP_* address map). */
void buffer_present(uint64_t *r, uint64_t pos);

#endif /* ADAPTER_BUFFER_H */
