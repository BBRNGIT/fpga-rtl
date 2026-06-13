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

## Declaration status (2026-06-13)

| Module | Mechanism | Status |
|---|---|---|
| dom | synth `display_outputs` (live + memory) | **declared** — view 36w, bit-exact |
| candle | synth `display_outputs` (OHLC bid/ask) | **declared** — view 8w, bit-exact |
| footprint | synth `display_outputs` (live + memory) | **declared** — view 88w, bit-exact |
| tpo | synth `display_outputs` (live + memory) | **declared** — view 80w, bit-exact |
| fractal | synth `display_outputs` (up/dn record store + high-water) | **declared** — view 34w, bit-exact |
| tai | synth `display_outputs` (TAI time) | **declared** — view 1w, bit-exact |
| **adapter** | OFF-fabric (plain C ingress) — NOT a synth module; its display view is its buffered raw record (bid/ask px, commission, pip, time; news only if the API provides it) | **pending** — needs an off-fabric adapter display descriptor (do NOT force synth `display_outputs`) |
| **wire** | passive bus — display = the wire lanes (bus data); a passive-bus lane tap, not a dff/history view | **pending** — needs a passive-bus display tap |
| **fifo_rx** | synth `display_outputs` (latest entry) once the rebuild lands | **pending** — blocked on the fifo_rx cell rebuild (addressed-RAM `ram` construct WIP) |

The six synth-path modules are declared through the formal pipeline (logic.yaml →
synth display view → guard). adapter/wire use a different layer (off-fabric / passive
bus) and fifo_rx waits on its rebuild — none are fake-declared (Law #13).

## BIOS (after display)
- A simple FPGA BIOS powers the circuitry up/down.
- The BIOS **starts the system + the external adapters, and calls the TUI program as its UI.**
- Replaces the current "inject" test pattern (rightly held off until display exists).
