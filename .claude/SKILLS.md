# Claude Development Skills for fpga-rtl

This directory contains 20 essential skills, workflows, and constraints that guide Claude's development of the C-as-RTL FPGA project. Each skill is a complete reference for implementing and validating a specific aspect of the architecture.

## Index of Skills

### Build & Validation Pipeline
1. **[emitter-first-pipeline](skills/emitter-first-pipeline.md)** — Three-stage build process: emitter → netlist → generator
2. **[gate-sh-validation](skills/gate-sh-validation.md)** — Three-stage acceptance gate with netlist, build, and clean-room checks
3. **[graduate-sh-promotion](skills/graduate-sh-promotion.md)** — Promote validated components to immutable vault
4. **[netlist-validation](skills/netlist-validation.md)** — Validate netlists for single-writer, no-overlap, no-floating
5. **[clean-room-rebuild](skills/clean-room-rebuild.md)** — Reproduce builds from committed HEAD alone

### Enforcement & Architecture
6. **[build-sequence-law-enforcement](skills/build-sequence-law-enforcement.md)** — Device logic is generated, never hand-written
7. **[gate-level-arithmetic-check](skills/gate-level-arithmetic-check.md)** — No native +/-/* in device ticks; use cells only
8. **[specification-completeness](skills/specification-completeness.md)** — Complete specs require all 5 components
9. **[single-writer-law](skills/single-writer-law.md)** — Each register written by exactly one node
10. **[read-compute-write-pattern](skills/read-compute-write-pattern.md)** — Device ticks follow strict READ→COMPUTE→WRITE

### Module & Hardware Design
11. **[immutability-enforcement](skills/immutability-enforcement.md)** — Graduated components are write-once vault
12. **[module-independence](skills/module-independence.md)** — Modules read only published interfaces
13. **[clock-hierarchy-modeling](skills/clock-hierarchy-modeling.md)** — Multiple independent clock domains with explicit CDC
14. **[tai-discipline-rule](skills/tai-discipline-rule.md)** — TAI is free-running timestamp, separate from MAC clock
15. **[cdc-slr-seam](skills/cdc-slr-seam.md)** — NIC-to-pipeline boundary with gray-code and async FIFO

### Data & Testing
16. **[data-law-bid-ask-only](skills/data-law-bid-ask-only.md)** — Bid/ask primitives only; derived metrics are read-only
17. **[no-floats-no-heap-no-pointers](skills/no-floats-no-heap-no-pointers.md)** — Data path uses fixed integers, static arrays only
18. **[thin-test-philosophy](skills/thin-test-philosophy.md)** — Power-on + display; no injection, stepping, or replay
19. **[cdc-slr-seam](skills/cdc-slr-seam.md)** — Clock domain crossing: NIC (125 MHz) ↔ Pipeline (250 MHz)

### Project Standards
20. **[no-ai-attribution](skills/no-ai-attribution.md)** — Commits carry user name only; no Co-Authored-By or AI markers

## How to Use These Skills

Each skill file contains:
- **Core rule** — The non-negotiable constraint
- **Why it matters** — The architectural reason
- **Examples** — Wrong and right implementations
- **Enforcement** — How gate.sh or pre-commit hooks validate it
- **Checklist** — Pre-graduation verification steps
- **References** — Links to FOUNDER_VISION.md and CLAUDE.md

**When working on a component:**

1. Read the relevant skills from this list (e.g., for building a new indicator, read: emitter-first, gate-sh-validation, specification-completeness, read-compute-write-pattern)
2. Follow the enforcement rules and checklists
3. Run gate.sh to validate
4. Graduate when all checks pass

## Skill Organization

Skills are grouped by function:

- **Pipeline** (1–5) — How to build and validate components
- **Enforcement** (6–10) — What makes valid components
- **Design** (11–15) — Module and hardware architecture
- **Data & Testing** (16–18) — What code is allowed
- **Standards** (19–20) — Project-wide policies

## Quick Reference

| Task | Skills |
|------|--------|
| Build a new component | emitter-first, gate-sh, specification-completeness, read-compute-write |
| Update a graduated component | immutability-enforcement, graduate-sh |
| Validate a netlist | netlist-validation, single-writer-law, specification-completeness |
| Debug a gate.sh failure | gate-sh-validation, build-sequence-law, gate-level-arithmetic |
| Design a clock-crossing module | clock-hierarchy, tai-discipline, cdc-slr-seam |
| Write a test | thin-test-philosophy |
| Commit work | no-ai-attribution |

## Relationship to Key Documents

- **FOUNDER_VISION.md** — Canonical system design (referenced in each skill's "source")
- **CLAUDE.md** — Quick commands and common operations
- **These skills** — Detailed implementation guidance for each architectural rule

All three work together: FOUNDER_VISION is the spec, CLAUDE.md is the quick reference, and these skills are the detailed implementation handbooks.
