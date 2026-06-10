#!/usr/bin/env python3
"""Minimal netlist validator for indicator modules.

Validates that:
- The file is valid JSON
- Required fields are present (device, dff_nodes)
- Tables (if present) have valid depths (power of 2)
"""
import json
import sys


def validate(net):
    """Validate netlist structure."""
    errs = []
    
    # Check required fields
    if "device" not in net:
        errs.append("missing required field: device")
    if "dff_nodes" not in net:
        errs.append("missing required field: dff_nodes")
    
    # Check tables have power-of-2 depths
    for tbl in net.get("tables", []):
        if "depth" in tbl:
            depth = tbl["depth"]
            if depth <= 0 or (depth & (depth - 1)) != 0:
                errs.append(f"table {tbl['name']}: depth {depth} is not power of 2")
    
    # Check history ring
    hist = net.get("history_ring", {})
    if hist and "depth" in hist:
        depth = hist["depth"]
        if depth <= 0 or (depth & (depth - 1)) != 0:
            errs.append(f"history_ring: depth {depth} is not power of 2")
    
    return errs


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: validate.py <netlist.json> [<netlist.json>...]\n")
        sys.exit(2)
    
    for path in sys.argv[1:]:
        try:
            with open(path) as f:
                net = json.load(f)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"[validate] JSON error in {path}: {e}\n")
            sys.exit(1)
        except FileNotFoundError:
            sys.stderr.write(f"[validate] file not found: {path}\n")
            sys.exit(1)
        
        errs = validate(net)
        if errs:
            sys.stderr.write(f"[validate] errors in {path}:\n")
            for err in errs:
                sys.stderr.write(f"  - {err}\n")
            sys.exit(1)
    
    # All valid
    sys.stdout.write(f"[validate] OK\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
