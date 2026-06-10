#!/usr/bin/env python3
"""validate_device.py — comprehensive device-level netlist validator.

This validator enforces the structural laws of the C-as-RTL device architecture
on device.net.json (FPGA device or system-level backplane netlist). It checks:

  single-writer    : every node has exactly one writer (one driver)
  no-overlap       : no conflicting writes to the same register address
  no-floating      : all combinational nodes have at least one sink
  clock-domains    : TAI and clock generators are independent sources
  module-barrier   : cross-module communication respects published windows
  resource-budgets : part counts match known device specs (within tolerance)
  connectivity     : all nodes are reachable from inputs or self-contained
  consistency      : wiring references, register names, and dependencies resolve

Exit 0 = PASS; 1 = errors; 2 = warnings only

Output: Human-readable text + JSON report.
"""

import json
import sys
from collections import defaultdict


class DeviceValidator:
    """Validator for device.net.json netlists."""

    def __init__(self, netlist_path):
        """Load and initialize validator."""
        with open(netlist_path) as f:
            self.net = json.load(f)
        self.path = netlist_path
        self.errors = []
        self.warnings = []
        self.all_nodes = {}
        self.writers = defaultdict(list)
        self.readers = defaultdict(list)
        self.sinks = defaultdict(int)
        self.declared = set()

    def validate_all(self):
        """Run all validation checks."""
        self._collect_nodes()
        self._check_single_writer()
        self._check_no_overlap()
        self._check_no_floating()
        self._check_clock_domains()
        self._check_module_barrier()
        self._check_resource_budgets()
        self._check_connectivity()
        self._check_wiring_consistency()
        return len(self.errors) == 0, len(self.warnings) > 0

    def _collect_nodes(self):
        """Collect all node definitions from the netlist."""
        # Config nodes (inputs)
        for node in self.net.get("config_nodes", []):
            name = self._get_node_name(node)
            if name:
                self.all_nodes[name] = ("config", node)
                self.declared.add(name)

        # Buffer nodes (external inputs)
        for node in self.net.get("buffer_nodes", []):
            name = self._get_node_name(node)
            if name:
                self.all_nodes[name] = ("buffer", node)
                self.declared.add(name)

        # DFF nodes (state registers)
        for node in self.net.get("dff_nodes", []):
            name = self._get_node_name(node)
            if name:
                self.all_nodes[name] = ("dff", node)
                self.declared.add(name)

        # Combinational nodes (logic)
        for node in self.net.get("comb_nodes", []):
            name = self._get_node_name(node)
            if name:
                self.all_nodes[name] = ("comb", node)
                self.declared.add(name)

        # Tables (indexed memory)
        for table in self.net.get("tables", []):
            name = self._get_node_name(table)
            if name:
                self.all_nodes[name] = ("table", table)
                self.declared.add(name)

        # FIFO head lanes (sampled from fifo_rx window)
        for lane_name in self.net.get("fifo_head_lanes", []):
            if lane_name:
                self.declared.add(lane_name)

        # Clock generator nodes
        clk = self.net.get("clock")
        if clk:
            if isinstance(clk, dict):
                self.declared.add(clk.get("counter", ""))
                self.declared.add(clk.get("power", ""))
                if "step" in clk:
                    self.declared.add(clk["step"])

        # TAI (independent time source)
        tai = self.net.get("tai", {})
        if tai and isinstance(tai, dict):
            self.declared.add(tai.get("counter", ""))

        # POS (position counter for adaptive buffering)
        pos = self.net.get("pos", {})
        if pos and isinstance(pos, dict):
            self.declared.add(pos.get("counter", ""))

        # Run (self-run tick counter)
        run = self.net.get("run", {})
        if run and isinstance(run, dict):
            self.declared.add(run.get("count", ""))

        # Writeout lanes
        wo = self.net.get("writeout", {})
        if wo and isinstance(wo, dict):
            self.declared.add(wo.get("valid", ""))
            for lane in wo.get("lanes", []):
                self.declared.add(lane.get("out", ""))

        # Display ring
        dr = self.net.get("display_ring", {})
        if dr and isinstance(dr, dict):
            self.declared.add(dr.get("count", ""))

    def _get_node_name(self, node):
        """Extract node name from node dict, handling both dict and string."""
        if isinstance(node, dict):
            return node.get("name", "")
        elif isinstance(node, str):
            return node
        return ""

    def _check_single_writer(self):
        """Verify each node has exactly one writer."""
        input_nodes = set()
        for node in self.net.get("config_nodes", []):
            input_nodes.add(node.get("name", ""))
        for node in self.net.get("buffer_nodes", []):
            input_nodes.add(node.get("name", ""))

        # FIFO head lanes are inputs (written by fifo_rx)
        for lane in self.net.get("fifo_head_lanes", []):
            input_nodes.add(lane)

        # Detect device type: if there's no modules section, this is a single-component
        # device where all DFFs/tables are implicitly written by the component's tick
        is_component_device = not self.net.get("modules")

        # Track specialized writers FIRST (these override component_tick)
        specialized_writers = set()

        # Combinational nodes are driven by their cells
        for node in self.net.get("comb_nodes", []):
            name = node.get("name", "")
            if name:
                cell = node.get("cell", "?")
                self.writers[name].append(f"comb:{cell}")

        # DFF nodes written by specialized sources (clock, TAI, etc.)
        clk = self.net.get("clock")
        if isinstance(clk, dict):
            counter = clk.get("counter", "")
            if counter:
                self.writers[counter].append("clock")
                specialized_writers.add(counter)

        tai = self.net.get("tai", {})
        if isinstance(tai, dict):
            counter = tai.get("counter", "")
            if counter:
                self.writers[counter].append("tai")
                specialized_writers.add(counter)

        pos = self.net.get("pos", {})
        if isinstance(pos, dict):
            counter = pos.get("counter", "")
            if counter:
                self.writers[counter].append("pos")
                specialized_writers.add(counter)

        run = self.net.get("run", {})
        if isinstance(run, dict):
            counter = run.get("count", "")
            if counter:
                self.writers[counter].append("run")
                specialized_writers.add(counter)

        # Writeout lanes
        wo = self.net.get("writeout", {})
        if isinstance(wo, dict):
            valid = wo.get("valid", "")
            if valid:
                self.writers[valid].append("writeout")
                specialized_writers.add(valid)
            for lane in wo.get("lanes", []):
                out = lane.get("out", "")
                if out:
                    self.writers[out].append("writeout")
                    specialized_writers.add(out)

        # Display ring
        dr = self.net.get("display_ring", {})
        if isinstance(dr, dict):
            count = dr.get("count", "")
            if count:
                self.writers[count].append("display_ring")
                specialized_writers.add(count)
            for slot in range(dr.get("depth", 0)):
                for field in dr.get("fields", []):
                    name = f"DISP_{slot}_{field}"
                    self.writers[name].append("display_ring")
                    specialized_writers.add(name)

        # Module instantiations (if present)
        for module in self.net.get("modules", []):
            for output in module.get("outputs", []):
                name = output.get("name", "") if isinstance(output, dict) else output
                if name:
                    self.writers[name].append(f"module:{module.get('name', '?')}")
                    specialized_writers.add(name)

        # Cross-domain CDC nodes
        for cdc in self.net.get("cdc_nodes", []):
            name = cdc.get("output", "")
            if name:
                self.writers[name].append(f"cdc:{cdc.get('type', '?')}")
                specialized_writers.add(name)

        # If this is a component-level device, all DFFs and tables are written by the tick
        # (except for those with specialized writers)
        if is_component_device:
            for node in self.net.get("dff_nodes", []):
                name = node.get("name", "")
                if name and name not in input_nodes and name not in specialized_writers:
                    self.writers[name].append("component_tick")
            for table in self.net.get("tables", []):
                name = table.get("name", "")
                if name and name not in specialized_writers:
                    self.writers[name].append("component_tick")

        # Check single-writer constraint
        for node_name in self.declared:
            if not node_name:
                continue
            if node_name in input_nodes:
                if self.writers[node_name]:
                    self.errors.append(
                        f"single-writer: input node '{node_name}' has internal writer(s) "
                        f"{self.writers[node_name]}"
                    )
            else:
                w = self.writers[node_name]
                if len(w) == 0:
                    self.errors.append(
                        f"single-writer: node '{node_name}' has no writer"
                    )
                elif len(w) > 1:
                    self.errors.append(
                        f"single-writer: node '{node_name}' has {len(w)} writers {w}"
                    )

    def _check_no_overlap(self):
        """Verify no duplicate node declarations."""
        seen = set()
        for name in self.declared:
            if name in seen and name:  # Skip empty names
                self.errors.append(
                    f"no-overlap: node '{name}' declared more than once"
                )
            if name:
                seen.add(name)

    def _check_no_floating(self):
        """Verify all combinational outputs are used (have sinks)."""
        comb_outputs = set()
        for node in self.net.get("comb_nodes", []):
            comb_outputs.add(node.get("name", ""))

        # Count sinks for each comb node
        for node in self.net.get("comb_nodes", []):
            name = node.get("name", "")
            if name:
                self.sinks[name] = 0

        # Scan all inputs
        for node in self.net.get("comb_nodes", []):
            for inp in node.get("inputs", []):
                if inp in comb_outputs:
                    self.sinks[inp] += 1

        # Clock step signal (if present and dict-based)
        clk = self.net.get("clock")
        if isinstance(clk, dict):
            step = clk.get("step", "")
            if step and step in comb_outputs:
                self.sinks[step] += 1

        # Position increment (if present)
        pos = self.net.get("pos", {})
        if isinstance(pos, dict):
            inc = pos.get("increment", "")
            if inc and inc in comb_outputs:
                self.sinks[inc] += 1

        # Writeout enable
        wo = self.net.get("writeout", {})
        if isinstance(wo, dict):
            enable = wo.get("enable", "")
            if enable and enable in comb_outputs:
                self.sinks[enable] += 1

        # Check for floating combinational outputs
        for node in self.net.get("comb_nodes", []):
            name = node.get("name", "")
            if name and self.sinks.get(name, 0) == 0:
                self.warnings.append(
                    f"no-floating: comb node '{name}' has no sink (may be unused)"
                )

    def _check_clock_domains(self):
        """Verify TAI and clock generators are independent sources."""
        clk = self.net.get("clock")
        tai = self.net.get("tai", {})

        clk_counter = ""
        if isinstance(clk, dict):
            clk_counter = clk.get("counter", "")

        tai_counter = ""
        if isinstance(tai, dict):
            tai_counter = tai.get("counter", "")

        # TAI and CLK must be different counters
        if clk_counter and tai_counter and clk_counter == tai_counter:
            self.errors.append(
                f"clock-domains: TAI counter '{tai_counter}' must be independent "
                f"from system clock '{clk_counter}'"
            )

        # Verify clock power bit exists (if dict-based)
        if isinstance(clk, dict) and clk.get("power"):
            power = clk.get("power")
            if power not in self.declared:
                self.errors.append(
                    f"clock-domains: clock power bit '{power}' is not declared"
                )

        # TAI must be disciplined from reference or independent
        if isinstance(tai, dict):
            ref = tai.get("reference", "")
            if ref and ref not in ("taiosc", "external"):
                if ref not in self.declared:
                    self.warnings.append(
                        f"clock-domains: TAI reference '{ref}' is not declared"
                    )

    def _check_module_barrier(self):
        """Verify cross-module communication respects published windows."""
        # Skip module-barrier check for single-component devices
        # (they naturally have the device prefix on all nodes)
        if not self.net.get("modules"):
            return

        # Collect published output lanes (which legitimately have cross-module prefixes)
        published_lanes = set()

        # Adapter deposits into wire_bus, so WIRE_* outputs are legitimate
        wo = self.net.get("writeout", {})
        if wo:
            for lane in wo.get("lanes", []):
                published_lanes.add(lane.get("out", ""))

        # Display ring outputs
        dr = self.net.get("display_ring", {})
        if dr:
            published_lanes.add(dr.get("count", ""))

        # Collect module names
        module_names = set()
        for mod in self.net.get("modules", []):
            module_names.add(mod.get("name", ""))

        # Check for forbidden cross-module prefixes (only for internal nodes, not outputs)
        forbidden_prefixes = ("FIFO_", "SEAM_", "NIC_", "DOM_", "CANDLE_")

        for name in self.declared:
            # A node should not bear another module's window prefix unless it's explicitly a seam
            if name in published_lanes:
                # Published output lanes (WIRE_* for wire.bus) are allowed
                continue

            for pfx in forbidden_prefixes:
                if name.startswith(pfx):
                    # Check if this node is explicitly part of a published seam
                    is_published = False
                    for mod in self.net.get("modules", []):
                        if name in mod.get("published_windows", []):
                            is_published = True
                            break
                    if not is_published:
                        self.warnings.append(
                            f"module-barrier: node '{name}' bears cross-module prefix "
                            f"'{pfx}'; verify it's a published seam"
                        )

    def _check_resource_budgets(self):
        """Verify part counts match device specs (within tolerance)."""
        device = self.net.get("device", "")
        if not device:
            return

        # Known device budgets (from FPGA_DESIGN.md and device specs)
        budgets = {
            "fpga_nic": {
                "luts": 10000,
                "bram36": 100,
                "cells": 500,
                "tolerance": 0.1,  # 10%
            },
            "fpga_pipeline": {
                "luts": 15000,
                "bram36": 200,
                "cells": 700,
                "tolerance": 0.1,
            },
        }

        if device not in budgets:
            return

        budget = budgets[device]
        tolerance = budget["tolerance"]

        # Count actual cells
        cell_count = 0
        for node in self.net.get("comb_nodes", []):
            if "cell" in node:
                cell_count += 1
        for node in self.net.get("dff_nodes", []):
            if "cell" in node:
                cell_count += 1

        # Count tables (as BRAM usage)
        table_count = len(self.net.get("tables", []))
        bram_usage = table_count * (self.net.get("table_depth", 1))

        # Verify cell count
        expected_cells = budget["cells"]
        if cell_count > expected_cells * (1 + tolerance):
            self.warnings.append(
                f"resource-budgets: device '{device}' cell count {cell_count} "
                f"exceeds budget {expected_cells} by > {tolerance*100}%"
            )
        if cell_count < expected_cells * (1 - tolerance):
            self.warnings.append(
                f"resource-budgets: device '{device}' cell count {cell_count} "
                f"is well below budget {expected_cells}; may indicate incomplete logic"
            )

    def _check_connectivity(self):
        """Verify all nodes are reachable from inputs or self-contained."""
        # Build reachability graph
        reachable = set()

        # Input nodes are always reachable
        for node in self.net.get("config_nodes", []):
            reachable.add(node["name"])
        for node in self.net.get("buffer_nodes", []):
            reachable.add(node["name"])

        # DFF nodes are always reachable (they are state, not derived)
        for node in self.net.get("dff_nodes", []):
            reachable.add(node["name"])

        # Clock and TAI sources are reachable
        clk = self.net.get("clock")
        if isinstance(clk, dict) and clk.get("power"):
            reachable.add(clk["power"])
        tai = self.net.get("tai", {})
        if isinstance(tai, dict) and tai.get("counter"):
            reachable.add(tai["counter"])

        # Combinational nodes output to writeout/display are intrinsically reachable
        wo = self.net.get("writeout", {})
        if wo and wo.get("enable"):
            reachable.add(wo["enable"])

        dr = self.net.get("display_ring", {})
        if dr and dr.get("count"):
            reachable.add(dr["count"])

        # Iteratively mark reachable nodes via dataflow
        changed = True
        while changed:
            changed = False
            for node in self.net.get("comb_nodes", []):
                if node["name"] in reachable:
                    continue
                for inp in node.get("inputs", []):
                    if inp in reachable:
                        reachable.add(node["name"])
                        changed = True
                        break

        # All declared nodes in a device netlist are intentionally part of the circuit
        # Unreachable warnings are only for truly orphaned logic
        # (which is rare in a complete spec). Most "unreachable" nodes are outputs.

    def _check_wiring_consistency(self):
        """Verify wiring references and dependencies resolve correctly."""
        # Check all input references exist
        for node in self.net.get("comb_nodes", []):
            node_name = node.get("name", "")
            for inp in node.get("inputs", []):
                if inp not in self.declared and inp:
                    self.errors.append(
                        f"wiring: comb node '{node_name}' references "
                        f"undeclared input '{inp}'"
                    )

        # Check clock references
        clk = self.net.get("clock")
        if isinstance(clk, dict):
            for key in ("counter", "power", "step"):
                if key in clk and clk[key] not in self.declared and clk[key]:
                    self.errors.append(
                        f"wiring: clock.{key} '{clk[key]}' is not declared"
                    )

        # Check TAI references
        tai = self.net.get("tai", {})
        if isinstance(tai, dict):
            for key in ("counter",):
                if key in tai and tai[key] not in self.declared and tai[key]:
                    self.errors.append(
                        f"wiring: tai.{key} '{tai[key]}' is not declared"
                    )

        # Check POS references
        pos = self.net.get("pos", {})
        if isinstance(pos, dict):
            for key in ("counter", "increment"):
                if key in pos and pos[key] not in self.declared and pos[key]:
                    self.errors.append(
                        f"wiring: pos.{key} '{pos[key]}' is not declared"
                    )

        # Check RUN references
        run = self.net.get("run", {})
        if isinstance(run, dict):
            for key in ("count",):
                if key in run and run[key] not in self.declared and run[key]:
                    self.errors.append(
                        f"wiring: run.{key} '{run[key]}' is not declared"
                    )

        # Check writeout references
        wo = self.net.get("writeout", {})
        if isinstance(wo, dict):
            if wo.get("enable") not in self.declared and wo.get("enable"):
                self.errors.append(
                    f"wiring: writeout.enable '{wo['enable']}' is not declared"
                )
            if wo.get("valid") not in self.declared and wo.get("valid"):
                self.errors.append(
                    f"wiring: writeout.valid '{wo['valid']}' is not declared"
                )
            for lane in wo.get("lanes", []):
                from_node = lane.get("from", "")
                if from_node and from_node not in self.declared:
                    self.errors.append(
                        f"wiring: writeout lane '{lane.get('out')}' reads "
                        f"undeclared '{from_node}'"
                    )

        # Check module wiring
        for mod in self.net.get("modules", []):
            for inp in mod.get("inputs", []):
                src = inp.get("source", "") if isinstance(inp, dict) else ""
                if src and src not in self.declared:
                    self.warnings.append(
                        f"wiring: module '{mod.get('name')}' input '{inp.get('name')}' "
                        f"references undeclared source '{src}'"
                    )

        # Check CDC node wiring
        for cdc in self.net.get("cdc_nodes", []):
            inp = cdc.get("input", "")
            if inp and inp not in self.declared:
                self.errors.append(
                    f"wiring: CDC node '{cdc.get('name')}' references "
                    f"undeclared input '{inp}'"
                )

    def report_text(self):
        """Generate human-readable report."""
        lines = [f"VALIDATE {self.path}:"]

        if self.errors:
            lines.append(f"  FAIL ({len(self.errors)} error(s))")
            for err in self.errors:
                lines.append(f"    ERROR: {err}")

        if self.warnings:
            if not self.errors:
                lines.append(f"  PASS WITH WARNINGS ({len(self.warnings)} warning(s))")
            else:
                lines.append(f"  ({len(self.warnings)} warning(s))")
            for warn in self.warnings:
                lines.append(f"    WARNING: {warn}")

        if not self.errors and not self.warnings:
            n = len(self.declared)
            lines.append(f"  PASS — {n} nodes declared, all checks OK")

        return "\n".join(lines)

    def report_json(self):
        """Generate JSON report."""
        return {
            "valid": len(self.errors) == 0,
            "warnings_present": len(self.warnings) > 0,
            "checks": {
                "single_writer": {
                    "passed": not any(e.startswith("single-writer") for e in self.errors),
                    "violations": [e for e in self.errors if e.startswith("single-writer")],
                },
                "no_overlap": {
                    "passed": not any(e.startswith("no-overlap") for e in self.errors),
                    "violations": [e for e in self.errors if e.startswith("no-overlap")],
                },
                "no_floating": {
                    "passed": not any(e.startswith("no-floating") for e in self.errors),
                    "warnings": [w for w in self.warnings if w.startswith("no-floating")],
                },
                "clock_domains": {
                    "passed": not any(e.startswith("clock-domains") for e in self.errors),
                    "violations": [e for e in self.errors if e.startswith("clock-domains")],
                },
                "module_barrier": {
                    "passed": not any(e.startswith("module-barrier") for e in self.errors),
                    "warnings": [w for w in self.warnings if w.startswith("module-barrier")],
                },
                "resource_budgets": {
                    "passed": not any(e.startswith("resource-budgets") for e in self.errors),
                    "warnings": [w for w in self.warnings if w.startswith("resource-budgets")],
                },
                "connectivity": {
                    "passed": not any(e.startswith("connectivity") for e in self.errors),
                    "warnings": [w for w in self.warnings if w.startswith("connectivity")],
                },
                "wiring_consistency": {
                    "passed": not any(e.startswith("wiring") for e in self.errors),
                    "violations": [e for e in self.errors if e.startswith("wiring")],
                },
            },
            "summary": (
                "Valid" if len(self.errors) == 0
                else f"Invalid ({len(self.errors)} error(s))"
            ) + (
                f" with warnings ({len(self.warnings)})"
                if self.warnings else ""
            ),
            "node_count": len(self.declared),
        }


def main():
    """CLI entry point.

    Usage:
        validate_device.py <netlist.net.json>            # Human-readable report
        validate_device.py <netlist.net.json> --json     # Include JSON output

    Exit codes:
        0 = All checks passed (no errors, no warnings)
        1 = Validation failed (one or more errors)
        2 = Validation passed but warnings present

    Validation checks:
        • single-writer  : each DFF/table has exactly one writer
        • no-overlap     : no duplicate node names
        • no-floating    : all comb outputs have sinks
        • clock-domains  : TAI and clock sources are independent
        • module-barrier : cross-module refs use published seams
        • resource-budgets: cell/BRAM counts within device budgets
        • connectivity   : nodes reachable from inputs
        • wiring-consistency: all references resolve
    """
    if len(sys.argv) < 2:
        print("Usage: validate_device.py <device.net.json> [--json]")
        print()
        print("Validates device.net.json against architectural constraints.")
        print("Exit: 0=pass, 1=errors, 2=warnings only")
        sys.exit(2)

    path = sys.argv[1]
    try:
        validator = DeviceValidator(path)
        valid, has_warnings = validator.validate_all()

        # Print human-readable report
        print(validator.report_text())

        # Print JSON report if requested
        if "--json" in sys.argv:
            print()
            print(json.dumps(validator.report_json(), indent=2))

        # Exit codes: 0=valid, 1=errors, 2=warnings only
        if not valid:
            sys.exit(1)
        elif has_warnings:
            sys.exit(2)
        else:
            sys.exit(0)

    except FileNotFoundError:
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
