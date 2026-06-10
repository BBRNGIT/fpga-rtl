/* probe.c — EXTERNAL DIAGNOSTIC (a logic-analyzer / waveform view).
 *
 * NOT the device. NOT a test. NOT part of the system. It single-steps the
 * adapter one clock edge at a time and prints the internal registers each tick,
 * so a human can WATCH the clock advance, the buffer present records[POS], the
 * pacer decide DUE, the cursor (POS) consume on emit, and the wire latch.
 *
 * IMPORTANT — this is an observation tool, not how the device runs:
 *   The device's REAL operation is the self-running clock (`adapter_run`): power
 *   on, it oscillates on its own, nothing external advances it. This probe
 *   deliberately steps the clock FROM OUTSIDE *only* to capture a per-tick
 *   waveform for inspection. Like the external display, it reads registers raw;
 *   it writes nothing into the data path beyond the power/config the starter
 *   would set. Conditionals here are host observation logic (legal, like the
 *   buffer), never device data-path logic.
 *
 * Usage:  ./probe <records.bin> [speed] [max_ticks]
 *   records.bin : a prepped binary record file (from prep.py; e.g. data_synth.bin)
 *   speed       : SPEED register value (clock units per tick). default 1
 *   max_ticks   : cap on ticks printed (the waveform window). default 40
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "adapter_gen.h"   /* device address map + adapter_init/tick (pulls in buffer.h) */

static word_t regs[ADP_REG_COUNT];
/* the wire bus the device drives — observed here exactly as the NIC would. */
static wire_word_t probe_bus[WIRE_REG_COUNT];

int main(int argc, char **argv) {
    const char  *path      = (argc > 1) ? argv[1] : "data_synth.bin";
    const uint64_t speed   = (argc > 2) ? strtoull(argv[2], NULL, 10) : 1ULL;
    const long   max_ticks = (argc > 3) ? strtol(argv[3], NULL, 10) : 40L;

    adapter_init(regs);                         /* synchronous reset: all zero */
    const uint64_t n = buffer_load(path);       /* buffer holds the records */
    regs[ADP_SPEED]     = speed ? speed : 1ULL; /* clock rate scale */
    regs[ADP_ADP_POWER] = 1ULL;                 /* power on */

    printf("probe: %s — %llu records, SPEED=%llu, window=%ld ticks\n",
           path, (unsigned long long)n, (unsigned long long)regs[ADP_SPEED], max_ticks);
    printf("tick |   now(clk) | POS | in_range | rx_ts | DUE | emit | WIRE_VALID |    wire_bid | seq\n");

    long t = 0;
    while ((regs[ADP_ADP_POWER] & 1ULL) && buffer_in_range(regs[ADP_POS]) && t < max_ticks) {
        const word_t now = regs[ADP_ADP_CLK];
        const word_t pos = regs[ADP_POS];
        buffer_present(regs, pos);                            /* observe presented record */
        const word_t rx  = regs[ADP_RX_TS];
        const word_t inr = regs[ADP_IN_RANGE] & 1ULL;
        const word_t due = ((rx <= now) && inr) ? 1ULL : 0ULL;   /* mirrors device pacer */
        adapter_tick(regs, probe_bus);                       /* one clock edge */
        const word_t emit = (regs[ADP_POS] > pos) ? 1ULL : 0ULL;
        printf("%4ld | %10llu | %3llu | %8llu | %5llu | %3llu | %4llu | %10llu | %11llu | %3llu\n",
               t, (unsigned long long)now, (unsigned long long)pos, (unsigned long long)inr,
               (unsigned long long)rx, (unsigned long long)due, (unsigned long long)emit,
               (unsigned long long)(regs[ADP_WIRE_VALID] & 1ULL),
               (unsigned long long)regs[ADP_WIRE_BID_PX], (unsigned long long)regs[ADP_WIRE_SEQ]);
        t++;
    }

    const uint64_t live = buffer_in_range(regs[ADP_POS]);
    printf("stop: POS=%llu of %llu, in_range=%llu, power=%llu",
           (unsigned long long)regs[ADP_POS], (unsigned long long)n,
           (unsigned long long)live, (unsigned long long)(regs[ADP_ADP_POWER] & 1ULL));
    if (t >= max_ticks && live)
        printf("  (window truncated at %ld-tick cap — raise max_ticks to see more)\n", max_ticks);
    else
        printf("  (buffer exhausted — the self-running clock would stop here)\n");
    return 0;
}
