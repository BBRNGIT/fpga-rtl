# Gennet Build Plan — Phases 0–3
**Status:** Ready for dispatch  
**Last updated:** 2026-06-08  
**Owner:** User  

---

## Executive Summary

Three-phase acceleration strategy to complete the gennet flip-flop development pipeline:

- **Phase 0** (6 hrs): Build `gennet_lib.py` shared library + four agent skills
- **Phase 2** (3 hrs): Rebuild NIC from correct design (clock set + wire dependencies satisfied)
- **Phase 3** (5 hrs): Build FIFO_RX (MAC→pipeline CDC crossing)

**Total elapsed time:** ~14 hours. Each phase blocks on prerequisites, but within-phase tasks are parallelizable.

**Key assumption:** Phase 1 (clock set: taiosc, tai, mac, internal, tai_cdc) is GRADUATED to `.hft/` and buildable targets exist in `.hft_staging/`.

---

## Phase 0: Foundation — gennet_lib.py + Skills

### Goal
Extract reusable emit-function library from adapter's `gen_adapter_net.py` (232 lines). Reduce per-component emitter authoring from 100+ lines to 20–30 lines.

### Deliverables

#### 1. `gennet_lib.py` (new file)
**Location:** `.hft_staging/gennet_lib.py`  
**Size estimate:** 300–400 lines  
**Content:**

```python
# Core emit functions (extracted from adapter's gennet.py)
- emit_header(device, window_base, reg_count)
- emit_address_defines(order, prefix)
- emit_init(reg_count)
- emit_phase_header(phase)         # READ / COMPUTE / WRITE
- emit_run_loop(module)
- emit_footer()
- emit_cmp_le()                    # existing adapter pattern
- emit_display_ring(ring_spec)     # existing adapter pattern

# New compositional patterns (no new C cells, only Python emit)
- emit_gray_encode(name, width)    # XOR cascade: gray[i] = bin[i] XOR bin[i+1]
- emit_gray_decode(name, width)    # Reverse: bin[i] = gray[i] XOR bin[i+1]
- emit_2ff_sync(name, src, width)  # Two chained cell_dff nodes
- emit_gray_counter(name, width)   # cell_addsub + gray_encode
- emit_fifo_full(wgray, rq2_gray, width)
- emit_fifo_empty(wq2_gray, rgray)
- emit_ram_nodes(name, depth, width)
- emit_strobe_latch(name, src, strobe)
- emit_dedup(seq_new, seq_last, valid_in)
- emit_free_counter(name, power, speed)
```

Each function returns a list of strings (lines of generated C code).

**Test:** Verify adapter's `gen_adapter_net.py` can be rewritten as:
```python
import gennet_lib as g
lines = []
lines += g.emit_header("adapter", "0x1800000", reg_count)
lines += g.emit_free_counter(...)
lines += g.emit_display_ring(...)
lines += g.emit_run_loop("adapter")
lines += g.emit_footer()
```
Must produce byte-identical `adapter_gen.h` output.

#### 2. Four Agent Skills (new directory: `.claude/agents/AGNT/skills/`)

**Skill 1: `/gennet-component-picker`**
- **Input:** English spec (e.g., "64-bit TAI counter, gray-encode, 2-FF CDC to MAC")
- **Output:** Ordered list of gennet_lib.py emit functions + parameters + node count estimate
- **Implementation:** 2–3 hours. Decision tree over 20 component patterns. No code generation.
- **Enforces:** DESIGN_GUIDE.md + cells.h constraints

**Skill 2: `/gennet-netlist-builder` (enhanced)**
- **Input:** Emit plan (from component-picker) + module spec from ARCHITECTURE.md
- **Output:** `gen_<mod>_net.py` (thin emitter, 20–30 lines) + `<mod>.net.json` + node count
- **Enhancement:** Call gennet_lib.py functions instead of hand-writing emit code
- **Implementation:** Enhance existing netlist-builder.md (2–3 hours)

**Skill 3: `/gennet-device-integrator`**
- **Input:** Generated `*_gen.h` + module spec
- **Output:** `<mod>.c/.h` starter, `test_<mod>.c` (thin test), `display.c/.h`, `Makefile`
- **Implementation:** 2–3 hours. Parametrize adapter files (90% reusable).

**Skill 4: `/gennet-rtl-auditor`**
- **Input:** All files in `.hft_staging/<module>/`
- **Output:** Pass/fail + violation report (line numbers, category)
- **Checks:** gate.sh 2b (gate-level arith), 2c (no hand-written device), validate.py (single-writer/no-overlap), drift-guard (no floats/heap/poc)
- **Implementation:** 1–2 hours. Wrapper over existing gates with better diagnostics.

### Acceptance Criteria

- [ ] `gennet_lib.py` imports cleanly and all emit functions execute
- [ ] Adapter rewritten using gennet_lib.py produces byte-identical `adapter_gen.h`
- [ ] Four skills added to `.claude/agents/AGNT/skills/` with README examples
- [ ] Phase 0 complete when: Phase 1 clocks can be rebuilt using gennet_lib.py + skills in 1 build cycle (validate by replicating tai_cdc emitter)

### Risk / Mitigation

| Risk | Mitigation |
|------|-----------|
| gennet_lib.py abstraction leaks implementation detail | Write from adapter (concrete example); test against 3 different components before Phase 2 |
| Skills drift from real codebase requirements | Component-picker reads DESIGN_GUIDE.md + ARCHITECTURE.md at skill execution; updated every 6 months |
| emit_* functions don't compose well for complex modules | Phase 2 (nic) will expose composition limits; feedback loop built in |

---

## Phase 2: NIC Rebuild

### Context

**Current state:** NIC marked for delete-and-rebuild (pre-taiosc framing error; raw TAI counter read across domain boundary violated CDC law). Adapter ✅ + Wire ✅ + Clock set ✅ are graduated; NIC now has correct dependencies.

**Inputs:**
- Wire (addressed-memory bus for SOP data from adapter)
- TAI_MAC (TAI value from tai_cdc, already in MAC domain)
- Write seam from adapter (1-cycle strobe)

**Outputs:**
- Dedup-by-seq filter (reject duplicate packets within a bar)
- Re-stamp with TAI_MAC
- Write strobe to FIFO_RX seam (1-cycle pulse)

### Specifications

**Module:** `nic`  
**Address window:** `0x1600000` (defined in BACKPLANE_MAP.md)  
**Clock domain:** MAC (125 MHz)  
**Registers:**
- `NIC_SEQ_LAST` (seq from prior packet)
- `NIC_TAI_MAC` (sampled TAI_MAC from tai_cdc)
- `NIC_OUT_VALID` (output strobe to FIFO_RX)
- `NIC_OUT_DATA_*` (re-stamped packet lanes)

**Netlist content:**
- 1× dedup comparator: `cell_eqmask(new_seq, nic_seq_last)`
- 1× dedup gate: `cell_and(valid_in, cell_not(dup))`
- 1× strobe latch: `cell_dff(q, dedup_gate, clock)`
- 1× TAI register: `cell_dff(tai_hold, tai_mac_in, strobe)`
- Data passthrough: wire→nic→fifo (no transform)

**Emitter size:** ~35 lines using gennet_lib.py (emit_dedup, emit_strobe_latch, emit_2ff_sync if synchronizing TAI)

### Build Sequence

**Step 1: Component picker** (30 min)
```
/gennet-component-picker
input: "NIC: MAC-domain dedup by seq, resample TAI_MAC from tai_cdc, write strobe to FIFO_RX seam. Inputs: wire bus, TAI_MAC (in-domain), adapter strobe. Outputs: valid strobe, re-stamped packet."
output: [emit_dedup, emit_strobe_latch], [emit_2ff_sync TAI_MAC], node count ~40
```

**Step 2: Netlist builder** (1 hr)
```
/gennet-netlist-builder
input: emit plan + ARCHITECTURE.md §9 (NIC spec)
output: gen_nic_net.py + nic.net.json (validated, node count matches)
```

**Step 3: Device integrator** (45 min)
```
/gennet-device-integrator
input: nic_gen.h (from gennet)
output: nic.c, nic.h, test_nic.c (thin), display.c, Makefile
```

**Step 4: Gate** (1 hr)
```
.hft_staging/gate.sh .hft_staging/nic
  Validate netlist (single-writer, no-overlap, no-floating)
  Build: gcc nic.c -o nic
  2b: gate-level arith check (no native +/-/*)
  2c: no hand-written device logic (no cell_* in .c, only in _gen.h)
  Clean-room: rebuild adapter + wire + nic, link together
```

**Step 5: End-to-end test** (1 hr)
```
Test: adapter (source) → wire (passive bus) → nic (dedup+restamp) → FIFO_RX seam
  Inject tick sequence: packet A, seq=1 → nic reads, writes strobe
                       packet B, seq=1 (dup) → nic dedup filters
                       packet C, seq=2 → nic reads, writes strobe
  Verify: strobe fires on 0, 2 (not 1); TAI_MAC latched on fire
  Verify: wire reads don't affect adapter state (passive bus law)
```

**Step 6: Graduate** (15 min)
```
.hft_staging/graduate.sh nic
  Copy nic/ → .hft/nic/
  Immutability guard on .hft/.githooks/pre-commit
```

**Total Phase 2 time:** 3–4 hours

### Acceptance Criteria

- [ ] `gen_nic_net.py` ≤ 40 lines (emit_dedup, emit_strobe_latch, emit_2ff_sync)
- [ ] `nic.net.json` validates: node count, single-writer, no-overlap, no-floating
- [ ] gate.sh 2b + 2c passes (no native arith, no hand-written device logic)
- [ ] Clean-room build succeeds (adapter+wire+nic linked, no unresolved refs)
- [ ] E2E test: dedup filters seq=1 duplicate, restamp with TAI_MAC, strobe fires on 0 and 2
- [ ] `nic/` graduated to `.hft/nic/` (immutable)

### Risk / Mitigation

| Risk | Mitigation |
|------|-----------|
| TAI_MAC is multi-bit; raw read from MAC domain tears | gennet_lib.py emit_2ff_sync ensures gray-code CDC; validator checks sync_nodes |
| Dedup comparator misses a duplicate | Thin test: inject seq_1, seq_1 (dup), seq_2 and verify strobe count = 2 |
| Adapter writes to wire during nic's read (module barrier violation) | Module barrier law: adapter sole writer to wire; nic only samples; validate.py enforces single-writer |
| TAI_MAC not yet synchronized into MAC domain | Depends on Phase 1 graduation (tai_cdc must be live); gate.sh clean-room build will fail if tai_cdc missing |

---

## Phase 3: FIFO_RX Build

### Context

**Goal:** CDC FIFO bridge between MAC domain (NIC, 125 MHz) and pipeline domain (250 MHz). Implements Cummings async FIFO pattern: gray-coded pointers + dual 2-FF synchronizers + dual-port SRAM + full/empty flags.

**Inputs:**
- NIC write strobe + data lanes (from nic seam, MAC domain)
- Read pointer from pipeline (250 MHz domain, gray-coded)

**Outputs:**
- Packet storage (512 slots, one per packet)
- Read interface to pipeline (synchronized write pointers, full/empty flags)

### Specifications

**Module:** `fifo_rx`  
**Address window:** `0x1700000` (defined in BACKPLANE_MAP.md)  
**Clock domains:** MAC (write), internal/pipeline (read)  
**Registers:**
- `FIFO_WR_GRAY` (write pointer in gray code, gray_counter, MAC domain)
- `FIFO_RD_GRAY` (read pointer in gray code, gray_counter, pipeline domain)
- `FIFO_WQ2_RGRAY` (synchronized read pointer, MAC domain, 2-FF)
- `FIFO_RQ2_WGRAY` (synchronized write pointer, pipeline domain, 2-FF)
- `FIFO_FULL` (MSB + lower bits XOR'd against wq2_rgray)
- `FIFO_EMPTY` (eqmask(rq2_wgray, rgray))
- `FIFO_SLOT[512]` (dual-port RAM, width=8, one entry per re-stamped packet)

**Netlist content:**
- 2× gray_counter (emit_gray_counter, width=10 for 512 slots): WR_GRAY, RD_GRAY
- 4× 2-FF sync (emit_2ff_sync, width=10): WQ2_RGRAY (write→read), RQ2_WGRAY (read→write)
- 2× gray_decode (emit_gray_decode, width=10): RQ2_WGRAY decoded, WQ2_RGRAY decoded
- 1× FIFO_FULL logic (emit_fifo_full): MSBs XOR'd, lower bits eqmask
- 1× FIFO_EMPTY logic (emit_fifo_empty): eqmask
- 1× RAM array (emit_ram_nodes, depth=512, width=8): dual-port storage

**Node count:** ~120–150 (including all 2-FF sync chains and RAM)  
**Emitter size:** ~45–60 lines using gennet_lib.py

### Build Sequence

**Step 1: Schema extension** (1 hr, do first)
Add `sync_nodes` and `ram_nodes` to `.hft_staging/validate.py`:
```python
# sync_nodes: list of 2-FF synchronizer chains, each with source, dest_clk, comment
# ram_nodes: list of dual-port RAM blocks, with depth, width, addr_in, wr_en, rd_addr

# Validation additions:
# - sync_nodes[i].src must be a valid node name (no cross-domain read)
# - ram_nodes[i] must have single writer (wr_en deduplicated per clock domain)
# - No overlap between window addresses
```

**Step 2: Component picker** (30 min)
```
/gennet-component-picker
input: "FIFO_RX: MAC→pipeline async CDC FIFO. 512 slots, 1 entry/packet. Gray pointers, dual 2-FF sync, full/empty flags. Inputs: nic write strobe + data (MAC), pipeline read addr + gray pointer (pipeline). Outputs: synchronized write pointer, read pointer, full, empty."
output: [emit_gray_counter×2, emit_2ff_sync×4, emit_fifo_full, emit_fifo_empty, emit_ram_nodes], node count ~150
```

**Step 3: Netlist builder** (1.5 hrs)
```
/gennet-netlist-builder
input: emit plan + ARCHITECTURE.md §10 (FIFO_RX spec) + validated schema
output: gen_fifo_rx_net.py + fifo_rx.net.json
```

**Step 4: Device integrator** (45 min)
```
/gennet-device-integrator
input: fifo_rx_gen.h
output: fifo_rx.c, fifo_rx.h, test_fifo_rx.c (thin), display.c, Makefile
```

**Step 5: Gate** (1.5 hrs)
```
.hft_staging/gate.sh .hft_staging/fifo_rx
  Validate (sync_nodes single-writer, ram_nodes no-overlap, no-floating)
  Build
  2b + 2c
  Clean-room: adapter + wire + nic + fifo_rx
```

**Step 6: End-to-end test** (1.5 hrs)
```
Test: full MAC→pipeline crossing
  MAC domain: nic writes strobe every 4 cycles, re-stamped packet deposited to wire
  Pipeline domain: fifo_rx latches from nic seam, writes to FIFO_SLOT, updates WR_GRAY
  Cross-domain: WQ2_RGRAY synchronized in MAC, RQ2_WGRAY synchronized in pipeline
  Verify:
    - No metastability violations (2-FF always used for cross-domain read)
    - Full/empty flags correct as FIFO fills and drains
    - Data integrity: packet read back matches packet written
    - Gray pointer transition safe (only 1 bit changes per cycle)
```

**Step 7: Graduate** (15 min)
```
.hft_staging/graduate.sh fifo_rx
```

**Total Phase 3 time:** 5–6 hours

### Acceptance Criteria

- [ ] `validate.py` extended for `sync_nodes` + `ram_nodes` (no new validation gaps)
- [ ] `gen_fifo_rx_net.py` ≤ 60 lines
- [ ] `fifo_rx.net.json` validates (node count, single-writer, no-overlap, no-floating, sync_nodes all in-domain)
- [ ] gate.sh 2b + 2c passes
- [ ] Clean-room build succeeds (adapter+wire+nic+fifo_rx linked)
- [ ] E2E test: packets flow MAC→pipeline without corruption; full/empty flags track state correctly
- [ ] `fifo_rx/` graduated to `.hft/fifo_rx/`

### Risk / Mitigation

| Risk | Mitigation |
|------|-----------|
| Gray pointer encoding error (not 1-bit delta) | emit_gray_encode + emit_gray_decode tested in isolation before FIFO; validator checks encoding correctness |
| 2-FF sync metastability | Cummings 2-FF pattern (two chained cell_dff, no combinational logic between them); emit_2ff_sync is copy-paste from zipcpu reference |
| Full/empty flags race condition | Full/empty use synchronized pointers from opposite domain (2-FF stable); no combinational feedback between domains |
| Dual-port RAM collision (same slot read+written simultaneously) | nic writes, pipeline reads different slots; FIFO is flow-controlled (no read until full=0); RAM single-writer law enforced by validator |

---

## Overall Dependencies

```
Phase 0 (gennet_lib.py + skills) ← must complete before Phase 2, 3
  │
  ├─→ Phase 2 (NIC) ← depends on: Phase 1 clocks graduated, gennet_lib.py complete
  │     │
  │     └─→ Phase 3 (FIFO_RX) ← depends on: Phase 2 NIC graduated, schema extended
  │
  └─→ (parallel) Phase 0 skills can be tested on Phase 1 clocks while Phase 2 progresses
```

**Critical path:** Phase 0 → Phase 2 → Phase 3 (sequential)  
**Parallelizable:** Within-phase steps (component-picker, netlist-builder, integrator run in sequence per module, but multiple emitter enhancements can be batched)

---

## Effort Summary

| Phase | Task | Hours | Owner | Depends On |
|-------|------|-------|-------|-----------|
| 0 | Extract gennet_lib.py from adapter | 3 | (agent) | — |
| 0 | Write 4 skills (picker, builder, integrator, auditor) | 3 | (agent) | gennet_lib.py |
| 0 | Test gennet_lib.py by re-emitting adapter | 0.5 | (human, verify) | Skills complete |
| **0 subtotal** | | **6.5** | | |
| 2 | Component picker (NIC spec) | 0.5 | (agent) | Phase 0 |
| 2 | Netlist builder (gen_nic_net.py + nic.net.json) | 1 | (agent) | Picker |
| 2 | Device integrator (nic.c/.h/test/display) | 0.75 | (agent) | Builder |
| 2 | Gate (validate, build, 2b/2c, clean-room) | 1 | gate.sh | Integrator |
| 2 | E2E test (adapter→wire→nic) | 1 | (human, run) | Gate passes |
| 2 | Graduate | 0.25 | graduate.sh | E2E passes |
| **2 subtotal** | | **4.5** | | |
| 3 | Schema extension (sync_nodes, ram_nodes) | 1 | (agent) | — |
| 3 | Component picker (FIFO_RX spec) | 0.5 | (agent) | Phase 0 + Schema |
| 3 | Netlist builder (gen_fifo_rx_net.py) | 1.5 | (agent) | Picker |
| 3 | Device integrator (fifo_rx.c/.h/test/display) | 0.75 | (agent) | Builder |
| 3 | Gate | 1.5 | gate.sh | Integrator |
| 3 | E2E test (MAC→pipeline crossing) | 1.5 | (human, run) | Gate passes |
| 3 | Graduate | 0.25 | graduate.sh | E2E passes |
| **3 subtotal** | | **6.5** | | |
| **TOTAL** | | **17.5** | | Phase 0 → 2 → 3 |

**Actual elapsed time:** ~15 hours (parallelism + overlap). Phase 0 is the pacing item (6.5 hrs), then 2+3 proceed sequentially with agent + gate running in parallel.

---

## Execution Checklist

### Pre-Phase 0
- [ ] Confirm Phase 1 clocks are GRADUATED (not just staged)
- [ ] Confirm `taiosc` is the canonical spelling (vocabulary alignment)
- [ ] Review ARCHITECTURE.md §9 (NIC spec) and §10 (FIFO_RX spec)

### Phase 0
- [ ] Extract gennet_lib.py from adapter (3 hrs)
- [ ] Write `/gennet-component-picker` skill (1 hr)
- [ ] Enhance `/gennet-netlist-builder` to use gennet_lib.py (1 hr)
- [ ] Write `/gennet-device-integrator` skill (1 hr)
- [ ] Write `/gennet-rtl-auditor` skill (0.5 hrs)
- [ ] Test gennet_lib.py by re-emitting adapter (human verify, 30 min)
- [ ] Phase 0 COMPLETE when: adapter re-emits byte-identical, all skills pass examples

### Phase 2
- [ ] Dispatch `/gennet-component-picker` for NIC spec (30 min)
- [ ] Dispatch `/gennet-netlist-builder` with emit plan (1 hr)
- [ ] Dispatch `/gennet-device-integrator` (45 min)
- [ ] Run `gate.sh nic` (1 hr, watch output)
- [ ] Run E2E test (adapter→wire→nic) (1 hr)
- [ ] Run `graduate.sh nic` (15 min)
- [ ] Phase 2 COMPLETE when: nic/ is in .hft/ and immutable

### Phase 3
- [ ] Extend validate.py for sync_nodes + ram_nodes (1 hr, agent)
- [ ] Dispatch `/gennet-component-picker` for FIFO_RX spec (30 min)
- [ ] Dispatch `/gennet-netlist-builder` with emit plan (1.5 hrs)
- [ ] Dispatch `/gennet-device-integrator` (45 min)
- [ ] Run `gate.sh fifo_rx` (1.5 hrs, watch output)
- [ ] Run E2E test (MAC→pipeline crossing) (1.5 hrs)
- [ ] Run `graduate.sh fifo_rx` (15 min)
- [ ] Phase 3 COMPLETE when: fifo_rx/ is in .hft/ and immutable

---

## Success Criteria (End of Plan)

- [ ] `.hft/adapter/`, `.hft/wire/`, `.hft/nic/`, `.hft/fifo_rx/` all exist and are immutable
- [ ] All components pass gate.sh 2b (gate-level arith), 2c (no hand-written device logic), clean-room
- [ ] Full end-to-end flow: source (adapter) → wire (bus) → nic (dedup+restamp) → fifo_rx (CDC) → pipeline reads
- [ ] gennet_lib.py is production-ready and consumed by all per-component emitters
- [ ] All four `/gennet-*` skills are documented and tested

---

## Notes for Future Maintenance

- **gennet_lib.py** is the single source of truth for emit patterns. If a new pattern is needed (e.g., barrel shifter, divider), add it here once, and all future modules benefit.
- **Phase 0 is the ROI inflection point.** Every hour spent on gennet_lib.py saves 2–3 hours on future modules. Recommend re-use across hft_pipeline migration if that work proceeds.
- **Vocabulary consistency:** All new `#define` names in .net.json and generated code must follow existing patterns (e.g., `FIFO_WR_GRAY`, not `fifo_wr_ptr_gray`). gennet_lib.py enforces via templates.
- **Skill library is composable but independent.** Each skill can be invoked standalone; the linear pipeline (picker → netlist-builder → integrator → auditor) is the recommended flow, but a human can run any skill manually if needed.

---

## Appendix: gennet_lib.py Function Reference

### Core Emit Functions (Already Exist)
```
emit_header(device, window_base, reg_count)
  Returns: list of lines defining the C module header, reg array, init function signature

emit_address_defines(order, prefix)
  Returns: list of #define lines for register addresses

emit_init(reg_count)
  Returns: list of lines for initialization loop (zeroing registers)

emit_phase_header(phase)
  Returns: list of lines for CLOCK_PHASE_READ / CLOCK_PHASE_COMPUTE / CLOCK_PHASE_WRITE

emit_run_loop(module)
  Returns: list of lines for the clock_tick_* dispatch loop and tick function

emit_footer()
  Returns: list of lines closing the main() function and module

emit_cmp_le()
  Returns: comparison logic (from adapter pattern)

emit_display_ring(ring_spec)
  Returns: list of display register lines for a ring buffer
```

### New Compositional Patterns
```
emit_gray_encode(name, width)
  Binary → gray: gray[i] = bin[i] XOR bin[i+1] (MSB-down)
  Returns: N-1 cell_xor calls

emit_gray_decode(name, width)
  Gray → binary: bin[i] = gray[i] XOR bin[i+1] (MSB-down)
  Returns: N-1 cell_xor calls

emit_2ff_sync(name, src, width)
  2-FF synchronizer: FF1 = cell_dff(src); FF2 = cell_dff(FF1)
  Returns: 2 cell_dff calls per bit

emit_gray_counter(name, width)
  Self-incrementing counter in gray code
  Returns: cell_addsub (inc by 1) + emit_gray_encode

emit_fifo_full(wgray, rq2_gray, width)
  Full flag: MSBs XOR'd (different), lower bits eqmask (same)
  Returns: cell_xor, cell_eqmask, cell_or logic

emit_fifo_empty(wq2_gray, rgray)
  Empty flag: wq2_gray == rgray (all bits equal)
  Returns: cell_eqmask

emit_ram_nodes(name, depth, width)
  Dual-port RAM: array of cell_dff, addressed by wr_addr and rd_addr
  Returns: list of node definitions for validate.py (ram_nodes section)

emit_strobe_latch(name, src, strobe)
  1-cycle strobe → hold value in register
  Returns: single cell_dff with enable

emit_dedup(seq_new, seq_last, valid_in)
  Deduplication: cell_eqmask(new, last) + cell_not + cell_and(valid, not_dup)
  Returns: 3-cell composition logic

emit_free_counter(name, power, speed)
  Self-running counter gated by power bit
  Returns: cell_addsub(+speed) + cell_gate(power)
```

All functions return `list[str]` (lines of generated C code).

---

**End of BUILD_PLAN.md**
