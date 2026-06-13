#!/usr/bin/env python3
"""check_display_layering.py — the display layering law (monitor boundary).

Enforces, structurally:
  1. The TUI sees ONLY frames — tui.* must not reference the fabric, the
     framebuffer, the display pin, or any synth_* symbol. (A React/web/OpenGL UI
     obeys the same contract.)
  2. The display adapter is the SOLE reader of the framebuffer — fb_pin_read is
     called only inside display_adapter.h (defined in fb.h).
  3. The driver reads display state ONLY through the adapter — it must not call
     fb_pin_read directly (no reaching past the adapter into the framebuffer).

Mirrors the barrier-bus law: each stage talks only to its own neighbour, never
reaching past it (as the fabric reads `wire`, never back to `adapter`).

Exit 0 = PASS, 1 = FAIL. Run: python3 display/check_display_layering.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE = re.compile(r"//[^\n]*")


def read(name):
    """Return file text with C comments stripped (the law constrains CODE, not docs)."""
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return ""
    return _LINE.sub("", _BLOCK.sub("", open(p).read()))


def main():
    errs = []

    # 1. TUI sees only frames.
    tui_forbidden = ["fpga_bram", "fpga_gty", "fb_pin_read", "fb_write", "fb_bind_pin",
                     "synth_", "fpga_device", "FB_TILE", "DISPLAY_PIN", "dom_synth",
                     'fpga_device_gen.h', '"fb.h"', '"display_adapter.h"']
    for tf in ("tui.c", "tui.h"):
        txt = read(tf)
        for tok in tui_forbidden:
            if tok in txt:
                errs.append(f"{tf}: references '{tok}' — the TUI must see ONLY frames "
                            f"(no fabric / framebuffer / pin / adapter / synth_)")

    # 2 & 3. fb_pin_read (framebuffer read via the pin) is allowed ONLY in the
    # display adapter (sole reader). Its definition lives in fb.h.
    for fn in sorted(os.listdir(HERE)):
        if not (fn.endswith(".c") or fn.endswith(".h")):
            continue
        if fn in ("fb.h", "display_adapter.h"):
            continue
        if "fb_pin_read" in read(fn):
            errs.append(f"{fn}: calls fb_pin_read — only the display adapter may read the "
                        f"framebuffer/pin (reaching past the adapter is forbidden)")

    if errs:
        print("DISPLAY-LAYERING: FAIL")
        for e in errs:
            print("  ERROR:", e)
        sys.exit(1)
    print("check_display_layering: PASS — TUI sees only frames; adapter is the sole framebuffer reader")
    sys.exit(0)


if __name__ == "__main__":
    main()
