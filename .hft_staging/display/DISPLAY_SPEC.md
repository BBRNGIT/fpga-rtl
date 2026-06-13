# Display Subsystem — Founder Spec (2026-06-13)

The display path is the **monitor boundary** (NOT the trading egress, which is unbuilt).
Strict layering, no link skipped:

```
fabric module → [relay, compute domain] → framebuffer (dual-port BRAM, partitioned)
framebuffer    → [display pin (GTY)]     → display adapter (off-fabric: own clock + read bank, atomic decimated sample)
display adapter → [published frame]      → TUI (terminal first; React/web/OpenGL later)
```

- Compute writes the framebuffer **free-running** (MHz). The display adapter **samples** at the
  display/refresh rate (decimation on the READ side). Double-buffered = atomic, flicker-free.
- The **TUI talks ONLY to its display adapter** — never the framebuffer, pin, or fabric (mirrors
  how the fabric reads `wire` and never reaches back to `adapter`). The display adapter is the
  **sole** reader of the framebuffer.

## Per-module display outputs (dictated; do not invent — Law #13)

| Module | Published to its display |
|---|---|
| **adapter** | raw data: bid price, ask price, commission, pip value, time; **news** — ONLY if the data source provides it in the API (else omit; do not invent) |
| **wire** | wire data (the wire bus lanes) |
| **tai** | TAI time |
| **fifo_rx** | latest data (the latest FIFO entry) |
| **dom** | entire DOM output per update (live state) **+** DOM persistent memory (the record store) |
| **candle** | OHLC for bid and ask (8 values) |
| **footprint** | active snapshots (live) **+** footprint memory (history) |
| **tpo** | active snapshots (live) **+** tpo memory (history) |
| **fractal** | all detected up fractals + down fractals (the fractal record store) |

## TUI
- **Terminal-based first** (and should be). The display adapter exposes a clean readable interface so
  a terminal UI, a React/web UI, or an OpenGL/Metal renderer can all read it. Terminal is the reference.
- Adapter is the single source the UI reads.

## BIOS (after display)
- A simple FPGA BIOS powers the circuitry up/down.
- The BIOS **starts the system + the external adapters, and calls the TUI program as its UI.**
- Replaces the current "inject" test pattern (rightly held off until display exists).
