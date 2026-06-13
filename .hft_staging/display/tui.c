/* tui.c — terminal renderer. Reads ONLY the frame it is given. No fabric, no
 * framebuffer, no pin, no synth_*. (Enforced by check_display_layering.py.) */
#include "tui.h"
#include <stdio.h>
typedef unsigned long long ull;

#define LIVE     12u
#define MEM_ROWS 8u

void tui_render_dom(const uint64_t *f, unsigned long tag, int home) {
    if (home) printf("\033[H");
    printf("+-- DOM  Depth of Market -----------------------------------+\n");
    printf("|  BID %-10llu (q%llu)  ASK %-10llu (q%llu)  SPREAD %-4llu  MID %-10llu\n",
           (ull)f[0], (ull)f[1], (ull)f[2], (ull)f[3], (ull)f[4], (ull)f[5]);
    printf("|  total bid/ask %llu/%llu   pkts %llu  add %llu  cancel %llu   lastTAI %llu\n",
           (ull)f[6], (ull)f[7], (ull)f[8], (ull)f[9], (ull)f[10], (ull)f[11]);
    printf("+-- persistent memory (newest first) ----------------------+\n");
    printf("|   #     BID         ASK         TAI\n");
    for (unsigned r = 0; r < MEM_ROWS; r++)
        printf("|  %2u  %-10llu  %-10llu  %llu\n", r,
               (ull)f[LIVE+r*3+0], (ull)f[LIVE+r*3+1], (ull)f[LIVE+r*3+2]);
    printf("+-- frame %-3lu ---------------------------------------------+\n", tag);
    fflush(stdout);
}
