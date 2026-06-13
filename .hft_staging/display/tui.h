/* tui.h — the terminal UI. Pure renderer: it knows ONLY a frame (an array of
 * display words handed to it by the display adapter). It must NOT include the
 * fabric, the framebuffer, the pin, or any synth_* symbol — the layering law.
 * A React/web/OpenGL UI would implement the same contract: render(frame). */
#ifndef DISPLAY_TUI_H
#define DISPLAY_TUI_H
#include <stdint.h>

/* render one coherent dom frame (layout = dom display_outputs: 12 live words then
 * 8 x {bid,ask,tai}). `home` repaints in place (flicker-free); `tag` is a caption. */
void tui_render_dom(const uint64_t *frame, unsigned long tag, int home);

/* ingress frame: [0..9] adapter latest packet, [10..17] wire lanes.
 * Renders both panels + a live adapter==wire ingress-integrity check. */
void tui_render_ingress(const uint64_t *frame, int home);

#endif /* DISPLAY_TUI_H */
