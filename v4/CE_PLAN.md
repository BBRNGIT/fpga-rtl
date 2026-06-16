# CE Plan: V4 UNISIM Cell Transcription (249 cells)

**Prepared:** 2026-06-16  
**Scope:** Transcribe all 249 UNISIM Verilog cells to C (faithful copy, no decomposition)  
**Success Criterion:** 249/249 cells compile + pass type checking + semantic fidelity 100%  
**Timeline:** 40–50 days at 5–6 cells/day (or parallel agents at 30+ cells/day)

---

## 1. Feature Requirements

### 1.1 Core Requirement
**Transcribe UNISIM Verilog specification (`.v`) to C (`.c`) such that:**
- C code IS the hardware specification (not simulation, not generator)
- Text matches Verilog exactly (names, ports, parameters, assignments)
- No interpretation, decomposition, or invented signals
- Type system enforced by C compiler (no hand-written hardware)

### 1.2 Input Specification
| Item | Source | Count | Status |
|------|--------|-------|--------|
| UNISIM cells | `/unisim_src/verilog/src/unisims/*.v` | 249 | ✓ Available |
| Verilog dictionary | `v4/lib/verilog.h` | 1 | ✓ Complete |
| Components library | `v4/lib/components.{h,c}` | 1 | ✓ Tested |
| Build harness | `v4/BUILD.sh` | 1 | ✓ Validated |
| Pre-commit enforcement | `.git/hooks/pre-commit` | 1 | ✓ Installed |

### 1.3 Output Specification
| Artifact | Location | Count | Entry Point |
|----------|----------|-------|-------------|
| Transcribed cells | `v4/clib/unisims/*.c` | 249 | `#include "../../lib/verilog.h"` |
| Object files | `/tmp/*.o` (temp) | 249 | Compiled during BUILD.sh |
| Git commits | `.git/objects` | 249 | One per cell (or batched by tier) |

### 1.4 Type System Mapping
| Verilog | C Type | Definition | Use Case |
|---------|--------|-----------|----------|
| `wire` | `net` (= `wire`) | `typedef wire net;` | Signal/connection |
| `reg` (procedural) | `var` (= `wire`) | `typedef wire var;` | Storage variable (simulation-only) |
| `reg` (component) | `reg` (struct) | components.h | Hardware flip-flop (separate) |
| `1'b0 / 1'b1 / 1'bx / 1'bz` | `_1b0 / _1b1 / _1bx / _1bz` | verilog.h macros | Net initializers |

### 1.5 Verilog.h Dictionary Coverage
| Construct | Status | Note |
|-----------|--------|------|
| `timescale, celldefine` | ✓ | Markers (no-op) |
| `module, endmodule` | ✓ | Maps to `void NAME(...)` |
| `parameter, localparam` | ✓ | `static const int` |
| `wire, reg, net, var` | ✓ | Type definitions |
| `input, output, inout` | ✓ | Direction (comment-only) |
| `tri, tri1, tri0` | ✓ | Tri-state nets with pull |
| `assign(s0,s1)` | ✓ | Drive strength notation |
| `initial begin...end` | ✓ | Procedural blocks |
| `DELAY(n)` | ✓ | Timing (#n) replacement |
| `not, buf, and, or, nand` | ✓ | Gate instantiation |
| `pullup, pulldown` | ✓ | Pull resistors |
| `begin, end` | ✓ | Block delimiters |
| `specify, endspecify` | ✓ | Timing spec (marker) |

---

## 2. Build Steps (Structured)

### Phase 1: Tier 1 Foundational Logic (24 cells)

**Objective:** Establish proof-of-concept with simplest + most critical cells  
**Scope:** Flip-flops, LUTs, carry, mux, latches, primitives

#### Step 1.1: Flip-Flop Family (FDRE, FDSE, FDCE, FDPE)
| Cell | Input (`.v`) | Output (`.c`) | Dependencies | Notes |
|------|--------------|---------------|-------------|-------|
| FDRE | `unisims/FDRE.v` | `clib/unisims/FDRE.c` | verilog.h, components.h | D+clk+reset |
| FDSE | `unisims/FDSE.v` | `clib/unisims/FDSE.c` | verilog.h, components.h | D+clk+set |
| FDCE | `unisims/FDCE.v` | `clib/unisims/FDCE.c` | verilog.h, components.h | D+clk+clear |
| FDPE | `unisims/FDPE.v` | `clib/unisims/FDPE.c` | verilog.h, components.h | D+clk+preset |

**Validation:**
- Compile: `cc -c clib/unisims/FDRE.c -o /tmp/FDRE.o -I v4`
- Type check: No `net_t`, no `_t` suffixes
- Semantic: All parameters, ports, delays from `.v` present in `.c`

#### Step 1.2: Lookup Tables (LUT1–LUT6, SRL variants)
| Cell | Pattern | Count | Complexity |
|------|---------|-------|-------------|
| LUT1–LUT6 | Basic lookup, no parameters | 6 | Low |
| SRL16E, SRLC16E, SRLC32E | Shift register + LUT | 3 | Medium |

**Validation:** Same as 1.1

#### Step 1.3: Carry Chain (CARRY8, CARRY4)
| Cell | Ports | Parameters | Notes |
|------|-------|-----------|-------|
| CARRY8 | 8×(CI, DI, S, CO) | None | 8-bit chain |
| CARRY4 | 4×(CI, DI, S, CO) | None | 4-bit chain (legacy) |

**Validation:** Same as 1.1

#### Step 1.4: Multiplexers (MUXF7, MUXF8, MUXF9)
| Cell | Inputs | Output | Notes |
|------|--------|--------|-------|
| MUXF7 | 2×6-bit LUT | 2-bit | Hierarchical mux |
| MUXF8 | 2×MUXF7 | 1-bit | — |
| MUXF9 | 2×MUXF8 | 1-bit | — |

#### Step 1.5: Latches & Logic Primitives
| Cell | Type | Complexity |
|------|------|-----------|
| LDCE, LDPE | Latch (clear/preset) | Low |
| AND2B1L, OR2L, INV, MUXCY | Logic gates | Low |
| GND, PULLUP, PULLDOWN | (reference only) | N/A |

**Completion Check:**
- [ ] All 24 cells compile to object files
- [ ] No type errors in any `.c` file
- [ ] `BUILD.sh` passes: components.c + test_vcc + all cells
- [ ] Pre-commit hook validates each commit
- [ ] Git history: 24 commits (1 per cell or batched by type)

---

### Phase 2: Storage & Block RAM (8 cells)

**Objective:** Add data storage capability  
**Complexity:** Medium → High (parameter-heavy)

#### Step 2.1: Block RAM Cells
| Cell | Ports | Parameters | Size | Notes |
|------|-------|-----------|------|-------|
| RAMB36E2 | addr, clk, din, dout, we | 10+ (init, width, depth) | 36 Kb | Dual-port |
| RAMB18E2 | addr, clk, din, dout, we | 10+ | 18 Kb | Dual-port |
| FIFO36E2 | din, dout, clk, we, re | 15+ (almost_full, depth) | 36 Kb | FIFO wrapper |
| FIFO18E2 | din, dout, clk, we, re | 15+ | 18 Kb | — |

**Risk:** Parameter-heavy; ensure all init values are hex strings, not computed

#### Step 2.2: Distributed RAM
| Cell | Architecture | Ports |
|------|--------------|-------|
| RAMD32 | 32×1 dual-port | addr, din, dout, clk, we |
| RAMS32 | 32×1 single-port | — |
| RAM64X1D, RAM128X1D | Larger distributed | — |

**Completion Check:**
- [ ] All 8 cells compile
- [ ] Parameter strings (init values) copy exactly from `.v`
- [ ] BUILD.sh passes
- [ ] Git: 8 commits (or 2 batches: BRAM + Distributed)

---

### Phase 3: Clock & Clocking (18 cells)

**Objective:** Enable synchronous designs  
**Complexity:** High (PLL/MMCM are specification-heavy)

#### Step 3.1: Clock Buffers (8 cells)
| Cell | Function | Ports | Parameters |
|------|----------|-------|------------|
| BUFG | Global clock | I, O | None or few |
| BUFGCE, BUFGCE_DIV | + clock enable / divide | — | Divide ratio |
| BUFR, BUFIO, BUFH, BUFMR | Regional variants | — | — |

**Validation:** Simple cells; should compile trivially

#### Step 3.2: Transceiver Clocks (2 cells)
| Cell | Purpose |
|------|---------|
| BUFG_GT | GTY clock buffer |
| BUFG_GT_SYNC | GTY sync buffer |

#### Step 3.3: PLL/MMCM (8 cells)
| Cell | Complexity | Parameters | Notes |
|------|-----------|-----------|-------|
| PLLE4_BASE | High | 20+ (Fin, Fout, dividers) | Base config |
| PLLE4_ADV | Very High | 30+ | Advanced (all settings) |
| MMCME4_BASE, MMCME4_ADV | High | Similar to PLL | — |
| PLLE2_*, MMCME2_* | High | 7-series legacy | — |

**Risk:** PLL parameter space is large; copy exactly from `.v`, do NOT interpret values

**Completion Check:**
- [ ] 18 cells compile
- [ ] All PLL/MMCM parameters are strings/values, not computed
- [ ] BUILD.sh passes
- [ ] Git: 18 commits (or batched: buffers/transceivers/PLLs)

---

### Phase 4: I/O Buffers (26 cells)

**Objective:** Connect to FPGA I/O banks  
**Complexity:** Medium (varied buffer types)

#### Step 4.1: Single-Ended I/O (10 cells)
| Cell | Type | Ports |
|------|------|-------|
| IBUF | Input | I, O |
| OBUF | Output | I, O |
| IOBUF | Bidirectional | I, O, T, IO |
| OBUFT | Tri-state out | I, T, O |
| IBUFCTRL, IBUFE3, etc. | Variants | Similar |

**Complexity:** Low

#### Step 4.2: Differential I/O (8 cells)
| Cell | Type | Ports |
|------|------|-------|
| IBUFDS | Differential in | P, N, O |
| OBUFDS | Differential out | I, P, N |
| IOBUFDS | Differential bidi | I, O, T, P, N |
| OBUFTDS | Tri-state diff | Similar |

#### Step 4.3: I/O Control (8 cells)
| Cell | Function | Complexity |
|------|----------|-----------|
| IDDR, ODDRE1, IDDRE1 | DDR I/O | Medium |
| IDELAYE3, ODELAYE3 | Delay elements | Medium |
| IDELAYCTRL | Delay control | Low |
| KEEPER, PULLDOWN | Pull resistors | Low |

**Completion Check:**
- [ ] 26 cells compile
- [ ] No invented ports/parameters
- [ ] BUILD.sh passes
- [ ] Git: 26 commits (or batched: single-ended / differential / control)

---

### Phase 5: Transceiver (GTY/GTX/etc.) (36 cells)

**Objective:** Enable high-speed serial I/O (optional for basic designs)  
**Complexity:** Very High (100+ parameters per cell)

#### Step 5.1: GTY Transceiver (6 cells XCZU19EG-specific)
| Cell | Scope | Parameters |
|------|-------|-----------|
| GTYE4_CHANNEL | TX/RX channel | 50+ (clock, width, equalization) |
| GTYE4_COMMON | Shared resources | 30+ |
| GTYE3_CHANNEL, GTYE3_COMMON | 3-series variants | — |
| IBUFDS_GTE4, OBUFDS_GTE4 | Input/output buffers | — |

**Risk:** Very large parameter set; risk of typos. Enforce line-by-line comparison.

#### Step 5.2: Other Transceiver Types (30 cells, lower priority)
- GTX (7-series): GTXE2_CHANNEL, GTXE2_COMMON (legacy)
- GTHE3/GTHE2, GTPE2 (other device families)

**Completion Check:**
- [ ] GTY cells (6) compile first
- [ ] Parameter count matches `.v` (machine-verified count)
- [ ] BUILD.sh passes
- [ ] Defer other transceiver variants to Phase 9

---

### Phase 6: DSP (5 cells)

**Objective:** Enable arithmetic acceleration (optional)  
**Complexity:** Very High (48-bit arithmetic, many sub-cells)

#### Step 6.1: DSP48E2 & Subcomponents
| Cell | Scope | Ports | Parameters |
|------|-------|-------|-----------|
| DSP48E2 | Complete DSP | 50+ | 100+ |
| DSP_ALU, DSP_MULTIPLIER | Subcells | — | Sub-configs |
| DSP_PREADD, DSP_OUTPUT | — | — | — |

**Risk:** Highest complexity after transceivers. Consider parallelizing with agents.

**Completion Check:**
- [ ] All 5 cells compile
- [ ] Parameter count verified against `.v`
- [ ] BUILD.sh passes
- [ ] Git: 5 commits

---

### Phase 7: Configuration (14 cells)

**Objective:** Support device programming & monitoring  
**Complexity:** Low → Medium

#### Step 7.1: JTAG & Config (6 cells)
| Cell | Purpose | Simulation-Only? |
|------|---------|-----------------|
| BSCANE2 | Boundary scan | No |
| ICAPE3 | Config port | No |
| STARTUPE3 | Startup sequence | No |
| DNA_PORTE2, MASTER_JTAG, JTAG_SIME2 | Device ID / JTAG sim | JTAG_SIME2 = yes |

**Note:** JTAG_SIME2 uses `var` type (simulation variable)

#### Step 7.2: Frame ECC (2 cells)
| Cell | Purpose |
|------|---------|
| FRAME_ECCE4 | Error correction (UltraScale) |
| FRAME_ECCE3 | Error correction (3-series) |

#### Step 7.3: Monitoring (6 cells)
| Cell | Purpose |
|------|---------|
| SYSMONE4, SYSMONE1 | Temperature, voltage |
| XADC | Analog-to-digital |
| HARD_SYNC, EFUSE_USR, USR_ACCESSE2 | Miscellaneous |

**Completion Check:**
- [ ] 14 cells compile
- [ ] Simulation-only cells properly use `var` type
- [ ] BUILD.sh passes
- [ ] Git: 14 commits (or batched by type)

---

### Phase 8: Miscellaneous (12 cells)

**Objective:** Fill remaining low-priority cells  
**Complexity:** Low

| Cell | Type | Ports | Notes |
|------|------|-------|-------|
| BUF | Buffer | I, O | May be no-op |
| AND2B1L, OR2L, XORCY | Logic | — | If not in Tier 1 |
| CFGLUT5, SIM_CONFIGE3 | Config/sim | — | Simulation-only |
| CAPTUREE2, RIU_OR, ZHOLD_DELAY | Misc | — | Rare use |
| DIFFINBUF, DPHY_DIFFINBUF | I/O | — | Specialized |
| HPIO_VREF, IN_FIFO, OUT_FIFO | System | — | System blocks |

**Completion Check:**
- [ ] 12 cells compile
- [ ] BUILD.sh passes
- [ ] Git: 12 commits

---

### Phase 9: Deferred / Out-of-Scope (60+ cells)

**Objective:** Catalog but do NOT transcribe (scope TBD)  
**Reason:** PS domain, HBM, codec engines, PCIe, Interlaken, UltraRAM

| Category | Cells | Status |
|----------|-------|--------|
| Processing System (PS) | PS7, PS8 | Deferred (UG1085) |
| High-Bandwidth Memory | HBM_* (10+) | Deferred |
| High-Speed ADC/DAC | HSADC, HSDAC, RFADC, RFDAC | Deferred |
| Serializers | ISERDESE3, OSERDESE3 | Deferred |
| PCIe | PCIE40E4, PCIE4CE4 | Deferred |
| Ethernet | CMAC, CMACE4 | Deferred |
| Codec | VCU | Deferred |
| Interlaken | ILKN, ILKNE4 | Deferred |
| UltraRAM | URAM288, URAM288_BASE | Deferred |

**Decision point:** Clarify scope before Phase 9

---

## 3. Risk Assessment

### 3.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Type mismatches (net_t vs net)** | Low | High | Pre-commit hook + cc validation |
| **Parameter copy errors** | Medium | Medium | Agent pair-review (line-by-line diff) |
| **Missing ports/signals** | Low | High | Semantic checker (agent verifies port count) |
| **Circular macro definitions** | Low | Medium | cc compile gate blocks this |
| **Verilog.h incomplete** | Low | Medium | Add missing constructs as cells fail |
| **Transceiver parameter space too large** | Medium | Medium | Parallelize with agents (batch validation) |
| **DSP arithmetic complexity** | High | Medium | Agent deep-dive + peer review |

### 3.2 Process Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Manual transcription errors** | High | High | Automated diff-check (BUILD.sh + git diff) |
| **Inconsistent type usage across cells** | Medium | High | Enforce verilog.h naming (var vs net) |
| **Git commit discipline lapses** | Low | Medium | Pre-commit hook is mandatory |
| **Scaling bottleneck (serial)** | High | High | Parallelize phases with agents |
| **Out-of-scope scope creep (PS/HBM)** | Medium | Low | Defer to Phase 9 (decision point) |

### 3.3 Dependency Risks

| Risk | Item | Status | Impact |
|------|------|--------|--------|
| verilog.h completeness | New constructs needed? | Unknown | Blocks cells using construct X |
| components.h completeness | Missing settle functions? | tri1/tri0 added; rest OK | Blocks port wiring |
| BUILD.sh robustness | Path issues, env vars? | Tested on macOS | May fail on different OS |
| Pre-commit hook | Git version compat? | Bash script (portable) | Low risk |

### 3.4 Mitigation Strategy

**For all phases:**
1. **Mechanical validation:** cc compile + type check (no hand-review of types)
2. **Semantic validation:** Agent compares port count, parameter count against `.v`
3. **Enforcement:** Pre-commit hook blocks invalid commits
4. **Parallelization:** At scale (50+ cells), spawn agents per phase

---

## 4. File Paths & Structure

### 4.1 Input Files
```
/Users/bbrn/fpga-rtl/
├── unisim_src/verilog/src/
│   ├── glbl.v                          (global signals, transcribed)
│   └── unisims/
│       ├── FDRE.v, FDSE.v, ...         (249 cells)
│       └── [all 249 cells live here]
└── [.git, CLAUDE.md, etc.]
```

### 4.2 Output Files
```
/Users/bbrn/fpga-rtl/v4/
├── lib/
│   ├── verilog.h                       (Verilog vocabulary, complete)
│   ├── components.h                    (C component types)
│   └── components.c                    (C implementations)
├── clib/unisims/
│   ├── glbl.c                          (✓ done)
│   ├── VCC.c                           (✓ done)
│   ├── FDRE.c, FDSE.c, ...             (249 cells, output)
│   └── [all 249 cells will live here]
├── test_vcc.c                          (reference test)
├── BUILD.sh                            (validation harness)
├── CELL_PLAN.md                        (prioritized cell list)
└── CE_PLAN.md                          (this document)
```

### 4.3 Git Structure
```
.git/
├── hooks/
│   └── pre-commit                      (enforces validation)
├── objects/
│   └── [249+ commits, one per cell or batched]
└── HEAD, refs/, config
```

### 4.4 Temporary/Build Artifacts
```
/tmp/
├── components.o                        (compiled library)
├── CELL_NAME.o                         (compiled cells)
├── test_vcc                            (VCC test executable)
└── [build logs, if errors]
```

---

## 5. Success Criteria & Metrics

### 5.1 Build Success
- [ ] **Compilation:** 249/249 cells compile with `cc -c ... -I v4`
- [ ] **Type Safety:** 0 type errors, 0 undefined symbols
- [ ] **Linking:** All .o files link against components.o without unresolved symbols
- [ ] **Test:** test_vcc passes (pre-commit gate)
- [ ] **Pre-commit:** Hook allows commits only if above pass

### 5.2 Semantic Fidelity
- [ ] **Port Count:** Every cell's C ports = Verilog ports (agent-verified)
- [ ] **Parameter Count:** Every cell's C parameters = Verilog parameters (agent-verified)
- [ ] **Assignments:** All `assign` statements present and syntax-correct
- [ ] **Initial Blocks:** All `initial begin...end` blocks present
- [ ] **Type Correctness:** No `net_t`, all `net` / `var` / `wire` usage correct

### 5.3 Deliverables
| Item | Count | Status |
|------|-------|--------|
| Transcribed .c files | 249 | Output |
| Git commits | 249+ | Output |
| Object files (temp) | 249 | Ephemeral |
| BUILD.sh runs | 249+ | Process metric |

---

## 6. Timeline & Milestones

| Phase | Cells | Effort | Critical Path |
|-------|-------|--------|----------------|
| Phase 1: Tier 1 | 24 | 2–3 days | FDRE, LUT1–LUT6 |
| Phase 2: RAM | 8 | 2–3 days | Depends on Phase 1 pass |
| Phase 3: Clock | 18 | 3–4 days | Depends on Phase 1 pass |
| Phase 4: I/O | 26 | 4–5 days | Depends on Phase 1 pass |
| Phase 5: GTY | 36 | 7–10 days | Can parallelize after Phase 1 |
| Phase 6: DSP | 5 | 2–3 days | Can parallelize after Phase 1 |
| Phase 7: Config | 14 | 2–3 days | Can parallelize after Phase 1 |
| Phase 8: Misc | 12 | 1–2 days | Can parallelize after Phase 1 |
| Phase 9: Deferred | 60+ | TBD | Decision point |
| **TOTAL (1–8)** | **176** | **25–35 days** | **Serial: 35d, Parallel: 15d** |
| **TOTAL (all)** | **249** | **40–50 days** | **Serial: 50d, Parallel: 20d** |

### Acceleration Paths

**Serial (conservative):**
- 1 dev, 5 cells/day → 50 days

**Parallel (aggressive):**
- Phase 1 (24): Agent A (3 days)
- Phase 2–8 (152): Agents B–F in parallel (15 days)
- Phase 9 (60): Decision point
- **Total: 15–20 days**

---

## 7. Enforcement & Quality Gates

### 7.1 Per-Cell Gate
```
Developer creates CELLNAME.c
                    ↓
Developer runs: v4/BUILD.sh
                    ↓
[Compile check]
[Type check]
[VCC test]
                    ↓
Pass? → Developer commits
        Pre-commit hook runs again (double-check)
        Commit accepted
        
Fail? → Errors logged
        Developer fixes
        Repeat
```

### 7.2 Pre-Commit Hook (`.git/hooks/pre-commit`)
**Runs on:** Every commit that touches `lib/components.{h,c}` or `test_vcc.c`

**Checks:**
1. Compile `components.c` → `components.o`
2. Link + run `test_vcc`
3. Report: PASS or FAIL (blocks commit on fail)

**Rationale:** No broken components get committed; test always passes

### 7.3 Per-Phase Gate (Proposed for Parallel Agents)
**After Phase 1 completes:**
- All 24 cells must compile + pass semantic check
- **Only then** can Phases 2–8 agents proceed

**After each subsequent phase:**
- Run combined `BUILD.sh` with all prior + current phase cells
- If any fail, rollback + debug

---

## 8. Risk Mitigation Specifics

### 8.1 Transceiver Parameter Risk (Phase 5)
**Problem:** GTY cells have 50–100 parameters; easy to mistype  
**Mitigation:**
1. Agent A: Transcribe GTYE4_CHANNEL (100% copy from `.v`)
2. Agent B: Independently transcribe same cell
3. Diff comparison: `diff GTYE4_CHANNEL_A.c GTYE4_CHANNEL_B.c`
4. If identical: Accept. If different: Human review.

### 8.2 Scope Creep Risk (Phase 9)
**Problem:** PS/HBM/PCIe cells are out-of-scope; risk of getting pulled in  
**Mitigation:**
1. Catalog Phase 9 cells but do NOT transcribe
2. Decision point: User approval required before Phase 9
3. Default: Defer (treat as separate project)

### 8.3 verilog.h Incompleteness Risk
**Problem:** New cell may use construct not in verilog.h  
**Mitigation:**
1. BUILD.sh fails if cell uses undefined macro
2. Developer extends verilog.h with new construct
3. Re-run BUILD.sh
4. New construct gets tested by all subsequent cells

---

## 9. Dependencies & Prerequisites

### 9.1 Already Complete
- ✓ `v4/lib/verilog.h` — Verilog vocabulary
- ✓ `v4/lib/components.{h,c}` — C digital components
- ✓ `v4/test_vcc.c` — Reference test
- ✓ `v4/BUILD.sh` — Build harness
- ✓ `.git/hooks/pre-commit` — Enforcement hook
- ✓ `glbl.c`, `VCC.c` — 2 cells done (proof-of-concept)

### 9.2 To-Do Before Starting Phase 1
- [ ] Verify `BUILD.sh` runs cleanly on target machine (test run)
- [ ] Verify pre-commit hook is executable and installed
- [ ] Clarify scope: Phase 9 cells (PS/HBM/PCIe) in or out?

### 9.3 Dependencies During Transcription
- **verilog.h:** Will grow as new constructs needed (no blocker)
- **components.h:** Will grow as new gates needed (no blocker)
- **BUILD.sh:** Will remain static (unless new validation needed)

---

## 10. Rollback & Recovery Plan

### 10.1 If Cell Fails Compilation
```
$ cc -c v4/clib/unisims/CELLNAME.c -o /tmp/CELLNAME.o -I v4
[error: undefined macro ...]

Action:
1. Identify missing construct in verilog.h
2. Add construct to verilog.h
3. Re-run BUILD.sh
4. Repeat
```

### 10.2 If Test Fails (test_vcc breaks)
```
$ BUILD.sh
[error: test_vcc failed]

Action:
1. Check what changed in components.c
2. Roll back change: git checkout components.c
3. Investigate root cause
4. Fix components.c
5. Re-run BUILD.sh
```

### 10.3 If Git Commit Fails (pre-commit hook blocks)
```
$ git commit -m "..."
[FAILED: components.c does not compile]

Action:
1. Fix components.c locally (not yet committed)
2. Re-run BUILD.sh
3. Retry commit
```

---

## 11. Acceptance Criteria

**The transcription is complete when:**

1. **All 176 cells (Phases 1–8) compile without error**
2. **Type checker confirms 0 undefined symbols**
3. **Pre-commit hook passes for all cells**
4. **VCC test always passes**
5. **Semantic verification agent confirms:**
   - Port count matches .v for all cells
   - Parameter count matches .v for all cells
   - No invented signals / ports
6. **Git history:** 176+ commits, one per cell (or batched by phase)
7. **Phase 9 cells cataloged but deferred** (decision point)

---

## 12. Sign-Off

| Role | Name | Date | Status |
|------|------|------|--------|
| Owner | User | 2026-06-16 | Pending approval |
| Tech Lead | Claude (main) | 2026-06-16 | Prepared |
| QA | Pre-commit hook | — | Enforced |

**Ready to proceed to Phase 1 on approval.**

