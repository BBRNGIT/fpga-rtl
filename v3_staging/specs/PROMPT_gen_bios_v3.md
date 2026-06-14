# DOWNSTREAM DEV PROMPT — build `gen_bios.py`: a v3-native BIOS generator (disconnect from .bbhft)

## Role
You are a C-as-RTL hardware tooling engineer on the v3 XCZU19EG project. You build TOOLS that
emit hardware/boot artifacts — you never hand-write the artifacts. Re-read `CLAUDE.md` +
`engr.md` before starting; the immutable laws below are binding.

## Problem
`v3_staging/bios/` is the **legacy `.bbhft` BIOS** retargeted by a one-line path change. It still
boots the v3 device only in a degraded "bare fabric" mode and is structurally coupled to the
archived HFT/`.bbhft` system. Concretely, these legacy couplings exist and MUST be removed:

| File | Legacy coupling to delete |
|---|---|
| `bios/bios.sh` | banner `"============== .bbhft BIOS console"`; the `cmd_dashboard` path → `$ROOT/install/synth.py`, `$ROOT/rebuild/dom.net.json`, `$ROOT/display/*` (none exist in v3); `FAB` comment "`.bbhft clone`" |
| `bios/system.conf` | `[clocks]` keys `taisoc/timeframe/tai/mac/internal.run_until`; `[adapter] selected=xau_backtest`; `[timeframe]` section — all archived HFT modules |
| `bios/adapters.reg` | `xau_backtest` ingress feed, `monitor` display adapter (HFT) |
| `bios/engine.c` | comment "Phase D … `.bbhft` clone"; relies on a clock interface (`FPGA_MMCM_COUNT`, `fpga_mmcm[][]`, `MMCM_*` macros) that `unify.py` does NOT emit → boots `#else` bare-fabric path |

The v3 device (`device/fpga_device_gen.h`, emitted by `tools/unify.py`) currently exposes
`fpga_device_init/flipflops/luts/power_on/off/tick/display` but **no native clock interface**, so
the BIOS prints `(no native clocks on this image)`. The device DOES contain realized clock blocks
(`MMCME4_BASE/ADV`, `PLLE4_BASE/ADV`, `BUFG*` — 15 in `device/library.json`); `DS891` gives
**CMTs = 11** (→ 11 MMCM, 22 PLL on this part). They are simply not wired into the unified device.

## Objective (two deliverables)
**A. Extend `tools/unify.py`** to emit a v3 native-clock interface into `fpga_device_gen.h`, derived
faithfully from the realized clock blocks + DS891 counts (no invented numbers):
- `#define FPGA_MMCM_COUNT <CMTs>` and `#define FPGA_PLL_COUNT <2×CMTs>` (read CMTs from
  `ds_resources.json`; do NOT hardcode 11).
- An MMCM register enum + array exactly matching what `engine.c` already indexes:
  `enum { MMCM_DIV_0_D, MMCM_DIV_1_D, MMCM_DIV_CFG_EN, MMCM_CLK_POWER, MMCM_CLKOUT_0, MMCM_CLKOUT_1, MMCM_REGS };`
  `static uint64_t fpga_mmcm[FPGA_MMCM_COUNT][MMCM_REGS];`
- Extend `fpga_device_tick()` so that, when an MMCM has `MMCM_CLK_POWER`, it behaviorally divides a
  reference clock: `CLKOUT_0` toggles every `MMCM_DIV_0_D` reference ticks, `CLKOUT_1` every
  `MMCM_DIV_1_D` — the UG572 divider semantics already implemented in `templates.py:divider()`
  (reuse/port that divider behavior; do not invent a new clock model). This makes the engine's
  existing `#ifdef FPGA_MMCM_COUNT` branch activate and report live edges.

**B. Build `tools/gen_bios.py`** — a generator that EMITS the v3 BIOS from disk artifacts, replacing
the legacy files. It must produce:
- `bios/engine.c` — generated v3 boot engine: `init → power_on → configure MMCM divides → tick →
  report native clocks ticking → POST PASS`. Same CLI (`boot|shutdown|post|status`) the console drives.
  (You MAY keep the existing engine.c if it already matches the API once unify emits the clock
  interface — but it must be emitted/owned by the tool and carry no `.bbhft` text.)
- `bios/system.conf` — v3 config: `[fpga] target=xczu19eg`; `[clocks]` with the REAL CMT/MMCM domains
  (from the device, not HFT modules); no `taisoc/timeframe/xau_backtest`.
- `bios/adapters.reg` — emptied of HFT adapters (or a v3-appropriate registry; the off-fabric
  display path is out of scope — the dashboard command must degrade cleanly, not reference
  `install/synth.py`/`rebuild/`/`display/`).
- `bios/bios.sh` console — v3 banner (e.g. `XCZU19EG BIOS console`), `FAB=$ROOT/device`, and a
  `cmd_dashboard` that does NOT reference any archived path; everything else (boot/status/post/
  config) works offline.

`gen_bios.py` reads: `device/container.json`, `device/ps_realize.json`, `device/library.json`
(clock blocks), `tools/ds_resources.json` (CMTs). It writes into `bios/`.

## Binding constraints (laws — violations are rejected)
- **C IS the RTL.** The engine is generated C; no Verilog/TCL. Faithful clock behavior derived from
  UG572 (the divider), counts from DS891 — invent nothing (Law #7). Missing fact ⇒ STOP AND ASK.
- **Tools build, not hands.** `gen_bios.py` EMITS the BIOS files; do not hand-edit the generated
  `engine.c`/`system.conf`. Mark them GENERATED.
- **No `.bbhft` / HFT coupling.** Zero references to `.bbhft`, `vu9p`, `install/`, `rebuild/`,
  `display/`, `taisoc`, `timeframe`, `xau_backtest` in any `bios/` file after generation.
- **Bulletproof.** The change must leave the board green. Add an integrity check
  `bios_v3_clean` to `checks_lib.py` (+ a `jobs.json` entry via `jobgen.py`): `grep -riE
  'bbhft|vu9p|install/synth|rebuild/|/display|taisoc|timeframe|xau_backtest' bios/` returns nothing.

## Acceptance criteria (all must pass)
1. `cc -O0 -std=c11 -w -I device bios/engine.c -o bios/engine` builds clean.
2. `./bios/engine boot` prints `N MMCM, M PLL present` and `MMCM[0] ALIVE … CLKOUT/2=<n> edges,
   CLKOUT/4=<m> edges` (clocks tick on power) — NOT `(no native clocks on this image)`.
3. `grep -riE 'bbhft|vu9p|install/synth|rebuild/|/display|taisoc|timeframe|xau_backtest' bios/` → empty.
4. `python3 tools/unify.py` still compiles + POSTs the unified `fpga_device` (regression).
5. `python3 tools/runner.py` → board BULLETPROOF, with the new `bios_v3_clean` integrity job green.
6. `python3 tools/realize.py status` unchanged (P2–P6 DONE).

## Verification (run end-to-end)
```sh
cd v3_staging/tools
python3 unify.py                       # emits clock interface into device/fpga_device_gen.h
python3 gen_bios.py                    # emits the v3 BIOS into bios/
cc -O0 -std=c11 -w -I ../device ../bios/engine.c -o ../bios/engine && ../bios/engine boot
grep -riE 'bbhft|vu9p|install/synth|rebuild/|/display|taisoc|timeframe|xau_backtest' ../bios/  # expect empty
python3 jobgen.py && python3 runner.py # expect BULLETPROOF incl bios_v3_clean
```

## Notes for the implementer
- The MMCM divider already exists: `templates.py:divider()` builds the UG572 M/D/O counter
  decomposition (proven `ref/2→6 edges`, `ref/4→3` over 12 ref ticks). Reuse its semantics for the
  behavioral `fpga_device_tick` clock advance; keep it small.
- The engine's `#ifdef FPGA_MMCM_COUNT` branch is already written to the exact macro names above —
  emit those names verbatim so it lights up without touching engine logic.
- Do NOT re-extract or re-parse any doc (the cache is frozen). Read the committed artifacts only.
- Commit message: no AI attribution (commit-msg hook rejects it).
