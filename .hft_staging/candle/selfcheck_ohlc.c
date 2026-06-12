/* selfcheck_ohlc.c — SEMANTIC self-verification (NOT the thin test).
 *
 * Drives the generated candle device through synthetic ticks across a bar
 * boundary and asserts the OHLC / volume / delta / completed-bar / history-ring
 * behaviour is REAL (the WAVE-1 failure was a green gate over stub logic). This
 * file is a host testbench: it sets DOM_* input lanes (conditioning lives here,
 * outside the device) and calls candle_tick — the device logic itself is pure
 * generated cells. Build:  cc -std=c11 -Wall -Wextra -Werror selfcheck_ohlc.c
 */
#include <stdio.h>
#include "candle_gen.h"

static word_t R[CANDLE_REG_COUNT];

/* push one quote into the device input lanes, then run one clock edge. */
static void quote(word_t bid, word_t ask, word_t bidq, word_t askq,
                  word_t tf_seq, word_t tai) {
    R[CANDLE_IN_BID_PRICE]  = bid;
    R[CANDLE_IN_ASK_PRICE]  = ask;
    R[CANDLE_IN_BID_QTY]    = bidq;
    R[CANDLE_IN_ASK_QTY]    = askq;
    R[CANDLE_IN_BAR_SEQ] = tf_seq;
    R[CANDLE_IN_BAR_TIME]        = tai;
    candle_tick(R);
}

static int fails = 0;
static void chk(const char *what, word_t got, word_t want) {
    if (got != want) {
        printf("  FAIL %-26s got=%llu want=%llu\n", what,
               (unsigned long long)got, (unsigned long long)want);
        fails++;
    } else {
        printf("  ok   %-26s = %llu\n", what, (unsigned long long)got);
    }
}

int main(void) {
    candle_init(R);

    printf("== Bar 0 (tf_seq=1): quotes 100, 105, 98, 103 ==\n");
    /* bid prices: 100 (open/seed), 105 (new high), 98 (new low), 103 (close) */
    quote(100, 110, 5, 7, 1, 1000);   /* first tick: seeds O=H=L=C=100 */
    quote(105, 112, 4, 9, 1, 1001);   /* new high 105 */
    quote(98,  108, 6, 6, 1, 1002);   /* new low 98 */
    quote(103, 109, 3, 8, 1, 1003);   /* close 103 */

    chk("BID_OPEN",  R[CANDLE_CANDLE_BID_OPEN],  100);
    chk("BID_HIGH",  R[CANDLE_CANDLE_BID_HIGH],  105);
    chk("BID_LOW",   R[CANDLE_CANDLE_BID_LOW],   98);
    chk("BID_CLOSE", R[CANDLE_CANDLE_BID_CLOSE], 103);
    /* true range = high - low = 105 - 98 = 7 */
    chk("TRUE_RANGE_BID", R[CANDLE_CANDLE_TRUE_RANGE_BID], 7);
    /* every tick changed the bid price -> 4 bid ticks */
    chk("VOLUME_BID", R[CANDLE_CANDLE_VOLUME_BID], 4);
    /* ask OPEN should be the first ask 110 */
    chk("ASK_OPEN",  R[CANDLE_CANDLE_ASK_OPEN],  110);
    chk("ASK_HIGH",  R[CANDLE_CANDLE_ASK_HIGH],  112);
    chk("ASK_LOW",   R[CANDLE_CANDLE_ASK_LOW],   108);
    chk("ASK_CLOSE", R[CANDLE_CANDLE_ASK_CLOSE], 109);
    /* bar still open: bar_seq 0, no completed bar yet */
    chk("BAR_SEQ(pre-boundary)", R[CANDLE_CANDLE_BAR_SEQ], 0);
    chk("COMP_BID_OPEN(pre)",    R[CANDLE_CANDLE_COMP_BID_OPEN], 0);

    printf("== Boundary tick (tf_seq=2): new bar opens at 200 ==\n");
    /* The boundary tick latches the COMPLETED bar 0 from the live values read at
     * the start of this tick, then seeds bar 1 with this tick's price (200). */
    quote(200, 210, 2, 4, 2, 2000);

    /* completed bar 0 captured the finished live values */
    chk("COMP_BID_OPEN",  R[CANDLE_CANDLE_COMP_BID_OPEN],  100);
    chk("COMP_BID_HIGH",  R[CANDLE_CANDLE_COMP_BID_HIGH],  105);
    chk("COMP_BID_LOW",   R[CANDLE_CANDLE_COMP_BID_LOW],   98);
    chk("COMP_BID_CLOSE", R[CANDLE_CANDLE_COMP_BID_CLOSE], 103);
    chk("COMP_VOLUME_BID",R[CANDLE_CANDLE_COMP_VOLUME_BID],4);
    chk("COMP_TAI",       R[CANDLE_CANDLE_COMP_TAI],       2000);
    chk("BAR_SEQ",        R[CANDLE_CANDLE_BAR_SEQ],        1);
    /* new (live) bar 1 reseeded to 200 on the boundary tick */
    chk("BID_OPEN(bar1)",  R[CANDLE_CANDLE_BID_OPEN],  200);
    chk("BID_HIGH(bar1)",  R[CANDLE_CANDLE_BID_HIGH],  200);
    chk("BID_LOW(bar1)",   R[CANDLE_CANDLE_BID_LOW],   200);
    chk("BID_CLOSE(bar1)", R[CANDLE_CANDLE_BID_CLOSE], 200);
    /* volume reset then +1 for this tick */
    chk("VOLUME_BID(bar1)", R[CANDLE_CANDLE_VOLUME_BID], 1);

    printf("== Bar 1 continues (tf_seq=2): NOT double-seeded ==\n");
    quote(205, 215, 1, 1, 2, 2001);   /* new high 205; must NOT reset to 205-open */
    chk("BID_OPEN(still 200)", R[CANDLE_CANDLE_BID_OPEN], 200);
    chk("BID_HIGH(bar1)",      R[CANDLE_CANDLE_BID_HIGH], 205);
    chk("BID_LOW(bar1)",       R[CANDLE_CANDLE_BID_LOW],  200);
    chk("BAR_SEQ(still 1)",    R[CANDLE_CANDLE_BAR_SEQ],  1);

    printf("== History ring slot 0 holds completed bar 0 ==\n");
    chk("HIST_0_BID_HIGH", R[CANDLE_CANDLE_HIST_0_BID_HIGH], 105);
    chk("HIST_0_BID_LOW",  R[CANDLE_CANDLE_HIST_0_BID_LOW],  98);
    /* record store: newest at slot 0, identified by its committed TIME (no counter) */
    chk("HIST_0_TAI",      R[CANDLE_CANDLE_HIST_0_TAI],      2000);

    printf(fails ? "\nRESULT: %d FAILURES\n" : "\nRESULT: ALL OHLC CHECKS PASS\n", fails);
    return fails ? 1 : 0;
}
