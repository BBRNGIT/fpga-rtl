# NIC — the wire→fifo gateway device (samples the wire, dedups, TAI-stamps, strobes the seam)

Grounded in: `INGRESS_FLOW.md` §4 (NIC: reads wire at mac, dedup by seq, reads tai's value, stamps,
writes fifo), `BLOCK_DIAGRAM.md` (component #2: NIC device, clock=mac, reads wire+tai, writes the
seam), `hft_pipeline/ARCHITECTURE.md` §6 (wire→nic boundary — refined by the barrier law: the NIC
samples the **bus**, never the producer's private regs), `.hft/wire/WIRE.md`, `.hft/tai_cdc/TAI_CDC.md`,
`AGENTS.md` (module-barrier + single-writer). Template: `.hft_staging/adapter/` (structure) +
`.hft_staging/tai_cdc/` (clocked-device + self-run loop).

## What the NIC IS

A **clocked device** in its **own window (0x1A00000)**, running on the **`mac`** cadence. Each mac edge
it: samples the wire bus (gated by `WIRE_VALID`), drops a packet whose `WIRE_SEQ` was already seen
(dedup history ring), re-stamps the survivor with the MAC-domain TAI value, and deposits the structured
re-stamped packet into the **nic→fifo seam** (its own output lanes) on a **1-cycle write strobe**.

The wire→NIC hop is **same-domain (MAC)** — there is **no CDC inside the NIC**. The TAI value already
crossed into the MAC domain inside `tai_cdc` (the NIC reads `tai_cdc`'s stable `TAI_MAC` output, never a
raw cross-domain `tai` counter — that would tear). The FIFO CDC (mac→internal) is **downstream**, the
NEXT component (`fifo_rx`); it is not built here.

## Block diagram

```
══ MAC clock domain ════════════════════════════════════════════════════════════
  WIRE BUS (0x1800000, passive)          tai_cdc (0x1F00000, MAC-domain output)
    WIRE_BID_PX WIRE_ASK_PX WIRE_TIME       TAI_MAC  (gray-decoded stage-2 value;
    WIRE_SYMBOL WIRE_PIP WIRE_COMMISSION              the authoritative MAC-domain
    WIRE_SEQ  WIRE_VALID                              timestamp the NIC stamps with)
        │  (NIC SAMPLES the bus on mac;             │ (NIC reads TAI_MAC in-domain;
        │   barrier — never the adapter's regs)      │  never raw-reads tai — tears)
        ▼                                            ▼
  ┌─ NIC DEVICE (0x1A00000, clock = mac) ───────────────────────────────────────┐
  │ READ    : WIRE_* (gated by WIRE_VALID), TAI_MAC, dedup-ring slot[SEQ & MASK]  │
  │ COMPUTE : dup = VALID & slot_valid & (slot_seq == WIRE_SEQ)   (branchless)    │
  │           pass = VALID & ~dup                                                 │
  │           stamp: out_time = TAI_MAC ; src_time = WIRE_TIME (kept for latency) │
  │           strobe = pass (1-cycle); ring update on pass                        │
  │ WRITE    : seam lanes (en=pass dffs) + STROBE dff + ring slot dff             │
  └───────────────┬──────────────────────────────────────────────────────────────┘
        SEAM ▼  nic→fifo seam (the NIC's OWN output lanes — the NIC is the seam's sole writer;
                fifo_rx will SAMPLE these next). Same-domain now; CDC is downstream in fifo_rx.
```

## Register table — window 0x1A00000 (netlist-assigned offsets, all named)

### config / input (set once by the starter — module-barrier: NIC's own input lanes, not reaches-in)
| lane | type | meaning |
|---|---|---|
| `NIC_POWER`      | bit | power/enable: the NIC self-runs on the mac edge while bit0 = 1 |
| `NIC_RUN_UNTIL`  | u64 | configured self-run tick budget (set once by starter) |

The wire is sampled **directly from the wire bus window** (`WIRE_*` via `wire_gen.h`) and the timestamp
**directly from the tai_cdc window** (`TAI_MAC` via `tai_cdc_gen.h`) — these are the producers' own
windows the NIC reads as a consumer (the bus/output-lane is the legitimate cross-module surface). The
NIC does **not** keep private copies of those maps; the Makefile regenerates both seam headers from the
siblings' single sources.

### state (dff)
| lane | type | meaning |
|---|---|---|
| `NIC_TICKS`        | u64 | self-run tick counter (bounds the self-run) |
| `NIC_RING_SEQ(i)`  | u64 | dedup ring slot i: the last `WIRE_SEQ` seen at index i (i = 0..NIC_RING_DEPTH-1) |
| `NIC_RING_VALID(i)`| bit | dedup ring slot i: 1 once slot i has stored a seq (virtual-valid tag) |

### seam output lanes (dff, en = pass — the NIC's OWN window; sole writer)
| lane | type | meaning |
|---|---|---|
| `SEAM_BID_PX`     | u64 | re-stamped packet: bid price (passthrough) |
| `SEAM_ASK_PX`     | u64 | re-stamped packet: ask price (passthrough) |
| `SEAM_TIME`       | u64 | **TAI stamp = TAI_MAC** (authoritative downstream) |
| `SEAM_SRC_TIME`   | u64 | source time (`WIRE_TIME`) kept for sync/latency |
| `SEAM_SYMBOL`     | u64 | symbol id (passthrough) |
| `SEAM_PIP`        | u64 | pip value (passthrough) |
| `SEAM_COMMISSION` | u64 | commission (passthrough) |
| `SEAM_SEQ`        | u64 | source sequence number (passthrough; dedup key) |
| `SEAM_VALID`      | bit | a re-stamped packet is present on the seam this cycle |
| `SEAM_STROBE`     | bit | **1-cycle write strobe**: high iff a fresh deduped packet was emitted this mac cycle; low on dup-drop or no-valid-wire |
| `SEAM_DEDUP_MARK` | bit | 1 iff the sampled packet was a DUP (dropped) — diagnostic/display only |

## Behavior — one MAC clock edge (READ → COMPUTE → WRITE, branchless, gate-level arithmetic)

1. **READ:** `NIC_POWER`, the wire bus (`WIRE_BID_PX … WIRE_VALID`), `TAI_MAC`, and the dedup ring slot
   at `idx = WIRE_SEQ & NIC_RING_MASK` (`NIC_RING_SEQ(idx)`, `NIC_RING_VALID(idx)`).
2. **COMPUTE (branchless cells — NO native +/-/*):**
   - `seq_match = cell_eqmask(slot_seq, WIRE_SEQ)`  (zero-reduction equality, bit0).
   - `dup  = WIRE_VALID & NIC_RING_VALID(idx) & seq_match`.
   - `pass = WIRE_VALID & ~dup`  (= `cell_and(valid, cell_not(dup))`, masked to bit0).
   - re-stamp: `out_time = TAI_MAC`; `src_time = WIRE_TIME`; bid/ask/symbol/pip/commission/seq pass
     through unchanged.
   - seam flops latch on `en = pass` (gated dff): only a deduped survivor updates the seam.
   - `SEAM_STROBE <= pass` (1-cycle), `SEAM_VALID <= pass`, `SEAM_DEDUP_MARK <= dup`.
   - ring update on pass: the slot at `idx` latches `WIRE_SEQ` (en=pass) and its valid bit latches 1
     (en=pass). A per-slot select `cell_eqmask(idx, i) & pass` gates which slot updates — branchless,
     no `if`, mirrors the adapter's display-ring slot select.
3. **WRITE:** commit every dff: ticks, ring slots (seq + valid), seam lanes, strobe, valid, dedup-mark.
   Write-only WRITE phase (no read-after-write).

### Self-running (canonical clock primitive)

`while ((NIC_POWER & 1) && cmp_lt(NIC_TICKS, NIC_RUN_UNTIL)) { nic_tick(r, wire, tai); NIC_TICKS += 1; }`
— runs on the mac edge while powered, bounded by a configured tick budget (config, not external
stepping). Nothing external advances it.

## Dedup logic (why it is collision-free for the live window)

Ring depth `N` = `NIC_RING_DEPTH`, a **power of two** (generate-time assert); index = `WIRE_SEQ & (N-1)`.
Each slot stores the **last seq seen at that index** plus a **valid tag**. A packet is a DUP iff the slot
is valid **and** holds exactly this `WIRE_SEQ`. Because the slot stores the **full seq** (not just a
parity bit), a wrapped-around old seq at the same index never equals the new seq → no false DUP across
the wrap. The immediate-repeat case (same seq presented twice) lands on the same index, matches the
stored full seq → correctly dropped. This is the candle/footprint history-ring pattern with the seq
itself as the stored key (the strongest virtual-reset: identity, not parity).

## Single-writer / reader contract

- **Writer of all `NIC_*` / `SEAM_*` = `nic_tick()` (generated)** — sole writer of its own window. The
  run loop owns `NIC_TICKS`.
- **Reader of the seam = `fifo_rx`** (next component) — it will sample `SEAM_*` on its mac-side write
  port. Nothing reads the seam yet (built standalone, exactly as adapter→wire was proven first).
- **The NIC reads, never writes:** `WIRE_*` (the wire's window) and `TAI_MAC` (tai_cdc's window). It
  never writes a sibling's register; it never reaches into a sibling's internal state — it samples the
  published bus / output lane.

## Clock domain / CDC boundary

- **NIC clock = `mac`** (same domain as the wire and as `TAI_MAC`). The wire→NIC hop is same-domain;
  no CDC inside the NIC.
- The **CDC is downstream** (`fifo_rx`, mac→internal: gray-code pointers + 2-FF sync). The NIC's seam is
  the mac-side input the FIFO will latch.
- `TAI_MAC` is already MAC-domain (crossed inside `tai_cdc`). The NIC reads it in-domain — it never
  raw-reads the multi-bit `tai` counter across a boundary (that tears).

## Testbench ≠ device

No `replay`/`source-type`/`CSV`/`file` register; no buffer, no offline prep (the NIC ingests no data
file — it samples the wire). The thin test powers the NIC on (presenting wire-bus inputs via the
starter) and displays the seam lanes; it does not step, inject into the data path, clock, or read
device internals beyond the display lanes.

## Open decisions FLAGGED for the founder

1. **Vocabulary correction — `TAI_MAC`, not "TAI_MAC_SYNC2".** The build brief named the timestamp lane
   "TAI_MAC_SYNC2". The graduated immutable `tai_cdc` vault exposes the MAC-domain timestamp VALUE as
   **`TAI_MAC`** (the gray-decoded stage-2 output; `TAI_CDC.md` single-writer/reader: "Reader = the NIC
   (reads `TAI_MAC` in-domain to stamp packets)"). There is **no** register named `TAI_MAC_SYNC2`;
   `TAI_SYNC2_GRAY` is the raw gray FF (NOT a usable value — must be decoded). This build stamps with
   `TAI_MAC` per the vault contract. Flagged, not silently renamed.
2. **The "nic→fifo seam" is the NIC's own output window; `fifo_rx` is not built yet.** The seam lanes
   live in the NIC window (the NIC is their sole writer); the future `fifo_rx` samples them. Built
   standalone here (the proven order: prove the producer's seam before the consumer exists).
3. **`TAI_MAC` presentation at integration.** Standalone, the starter presents a fixed `TAI_MAC` sample
   (and fixed wire-bus inputs) to demonstrate stamp + dedup. At integration the live `tai_cdc` output
   and the live wire bus are presented each mac edge — same seam shape as adapter→wire. Confirm the
   integration wiring (how the wire bus and `tai_cdc` window reach the NIC's read ports) when the
   end-to-end adapter→wire→NIC→seam harness is wired.
4. **Ring depth.** Set to a power of two (`NIC_RING_DEPTH`); sized for the in-flight dedup window. The
   default (16) is the proven small power-of-two; production depth is a config bump, no core change.
