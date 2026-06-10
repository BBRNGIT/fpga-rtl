# Phase 0: gennet_lib.py + Skills

## Goal
Extract reusable emit-function library from existing gennet.py implementations (adapter, clock set, nic). Reduce per-component emitter from 100+ lines to 20–30 lines. Enable four agent skills for component-picking, netlist generation, device integration, and RTL audit.

## Deliverables

### 1. `gennet_lib.py` (Location: `.hft_staging/gennet_lib.py`)

**Size estimate:** 300–400 lines  

**Functions (extracted from existing gennet patterns):**
```python
# Core boilerplate (extracted from adapter/clock/nic)
emit_header(device, window_base, reg_count)
emit_address_defines(order, prefix)
emit_init(reg_count)
emit_phase_header(phase)         # CLOCK_PHASE_READ/COMPUTE/WRITE
emit_run_loop(module)
emit_footer()

# Patterns (used in adapter, clock set, nic, will be used in fifo_rx)
emit_cmp_le()
emit_display_ring(ring_spec)
emit_free_counter(name, power, step)
emit_strobe_latch(name, src, strobe)
emit_dedup(seq_new, seq_last, valid_in)

# New patterns (required for fifo_rx and beyond)
emit_gray_encode(name, width)       # XOR cascade: gray[i] = bin[i] XOR bin[i+1]
emit_gray_decode(name, width)       # Reverse XOR: bin[i] = gray[i] XOR bin[i+1]
emit_2ff_sync(name, src, width)     # 2-FF synchronizer: FF1 = dff(src); FF2 = dff(FF1)
emit_gray_counter(name, width)      # cell_addsub + emit_gray_encode
emit_fifo_full(wgray, rq2_gray, width)
emit_fifo_empty(wq2_gray, rgray)
emit_ram_nodes(name, depth, width)  # Dual-port SRAM (ram_nodes section in .net.json)
```

**Implementation pattern:** Each function returns `list[str]` (lines of C code).

**Test acceptance:** Rewrite adapter's `gen_adapter_net.py` using gennet_lib.py and verify output is byte-identical to original `adapter_gen.h`.

---

### 2. Four Agent Skills (Directory: `.claude/agents/AGNT/skills/`)

#### Skill 1: `/gennet-component-picker`
**Purpose:** Convert English module spec → list of gennet_lib.py emit functions + parameters  
**Input:** "Module description (e.g., 64-bit TAI counter, gray-encode, 2-FF CDC)"  
**Output:** Ordered list of emit calls with parameters + estimated node count  
**Implementation:** 2–3 hours. Decision tree over 20 component patterns. No code generation.  
**Enforces:** DESIGN_GUIDE.md + cells.h + RTL constraints

#### Skill 2: `/gennet-netlist-builder` (enhanced)
**Purpose:** Generate thin emitter + validated netlist  
**Input:** Emit plan (from component-picker) + module spec from ARCHITECTURE.md  
**Output:** `gen_<mod>_net.py` (20–30 lines) + `<mod>.net.json` (validated)  
**Enhancement:** Call gennet_lib.py emit functions instead of hand-writing boilerplate  
**Implementation:** 2–3 hours. Enhance existing netlist-builder.md

#### Skill 3: `/gennet-device-integrator`
**Purpose:** Generate starter files (non-device glue)  
**Input:** `*_gen.h` (from gennet) + module spec  
**Output:** `<mod>.c`, `<mod>.h`, `test_<mod>.c` (thin), `display.c`, `Makefile`  
**Implementation:** 2–3 hours. Parametrize adapter files (90% reusable)

#### Skill 4: `/gennet-rtl-auditor`
**Purpose:** Validate against RTL constraints with detailed diagnostics  
**Input:** All files in `.hft_staging/<module>/`  
**Output:** Pass/fail + violation report (line numbers, categories)  
**Checks:** gate.sh 2b (gate-level arith), 2c (no hand-written device), validate.py (single-writer/no-overlap), drift-guard (no floats/heap/poc)  
**Implementation:** 1–2 hours. Wrapper over existing gates with better error messages

---

## Acceptance Criteria

**gennet_lib.py:**
- [ ] All 18+ emit functions exist and return list[str]
- [ ] Adapter rewritten using gennet_lib.py produces byte-identical `adapter_gen.h`
- [ ] No hardcoded addresses; all from cells.h and parameter-driven

**Four Skills:**
- [ ] Each skill has `.claude/agents/AGNT/skills/<skill>.md` with README examples
- [ ] `/gennet-component-picker` tested on 2 modules (e.g., tai_cdc, nic)
- [ ] `/gennet-netlist-builder` generates valid `gen_<mod>_net.py` and `.net.json`
- [ ] `/gennet-device-integrator` produces compilable `<mod>.c` with no hand-written device logic
- [ ] `/gennet-rtl-auditor` catches and reports actual violations (test with a known bad emitter)

**Overall Phase 0 complete when:**
- gennet_lib.py + 4 skills exist and are tested
- Adapter can be re-emitted in 20 lines instead of 232
- All remaining components (fifo_rx, future) can use the same workflow

---

## Effort Breakdown

| Task | Hours | Depends On |
|------|-------|-----------|
| Extract gennet_lib.py from adapter/clock/nic | 3 | Read existing gennet.py files |
| Write emit_gray_*, emit_2ff_sync, emit_ram_nodes | 1.5 | gennet_lib.py structure |
| Test gennet_lib.py (byte-identical adapter re-emit) | 0.5 | All emit functions |
| Write `/gennet-component-picker` skill | 1 | gennet_lib.py complete |
| Enhance `/gennet-netlist-builder` skill | 1 | gennet_lib.py complete |
| Write `/gennet-device-integrator` skill | 1 | gennet_lib.py complete |
| Write `/gennet-rtl-auditor` skill | 0.5 | gennet_lib.py complete |
| Test all 4 skills (2 modules each) | 1 | All skills written |
| **TOTAL** | **9** | |

**Actual elapsed time:** ~7–8 hours (parallelism + overlap)

---

## Execution Checklist

- [ ] Read existing `gen_adapter_net.py`, `gen_tai_cdc_net.py`, `gen_nic_net.py` to identify patterns
- [ ] Extract boilerplate into gennet_lib.py (emit_header, emit_init, emit_phase_header, emit_run_loop, etc.)
- [ ] Add new patterns (emit_gray_encode, emit_gray_decode, emit_2ff_sync, emit_ram_nodes)
- [ ] Test gennet_lib.py by re-emitting adapter and diffing against original
- [ ] Write `/gennet-component-picker` (decision tree + examples)
- [ ] Enhance `/gennet-netlist-builder` to use gennet_lib.py
- [ ] Write `/gennet-device-integrator` (templating logic)
- [ ] Write `/gennet-rtl-auditor` (gate wrapper + diagnostics)
- [ ] Test all 4 skills on 2 existing modules (tai_cdc, nic) — should produce identical output to what exists
- [ ] Phase 0 COMPLETE when adapter + 2 other modules can be re-emitted using gennet_lib.py + skills

---

## Success Metrics

- gennet_lib.py is <400 lines and contains no hardcoded addresses
- Adapter emitter shrinks from 232 → 20 lines
- All 4 skills have working examples in their README
- Byte-identical re-emit of 3 modules (adapter, tai_cdc, nic) proves correctness
- Future modules (fifo_rx, others) can be built in 20–30 line emitters using the same library

