/* ingress_view.h — display views for the OFF-fabric ingress modules (adapter,
 * wire). They are the off-fabric/passive analogue of synth_<mod>_display_view():
 * each reads ONLY its own module's published state into a frame slice. (The view
 * runs in the relay/compute side; the TUI never sees these — it sees frames.)
 */
#ifndef DISPLAY_INGRESS_VIEW_H
#define DISPLAY_INGRESS_VIEW_H
#include <stdint.h>

/* adapter raw data — the latest emitted packet (one row): per DISPLAY_SPEC.
 * out: [0]valid [1]bid [2]ask [3]time [4]seq [5]clk_at_emit
 *      [6]commission [7]pip [8]news [9]news_valid */
#define ADAPTER_VIEW_WORDS 10u
void adapter_display_view(const uint64_t *regs, uint64_t *out);

/* wire data — the 8 published bus lanes (price-only, Law #6).
 * out: [0]bid [1]ask [2]time [3]symbol [4]pip [5]commission [6]seq [7]valid */
#define WIRE_VIEW_WORDS 8u
void wire_display_view(const uint64_t *wire, uint64_t *out);

#endif /* DISPLAY_INGRESS_VIEW_H */
