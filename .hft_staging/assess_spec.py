#!/usr/bin/env python3
"""assess_spec.py — assess an FPGA spec sheet (PDF) into a device PARTS manifest.

Reads the AUTHENTIC datasheet PDF (e.g. the AMD Product Selection Guide), locates a
device's column in the resource table, and extracts that device's values EXACTLY as
printed — transcription only. ZERO design, ZERO materialization, ZERO invented values.
Output = the device's parts (what the spec states the device contains), each tagged
with its source line for provenance.

This is the "assess the spec sheet" step. It does NOT produce flip-flop parts and
does NOT materialize a circuit: the flip-flop-level netlist is a SEPARATE step driven
by a human-dictated materialization rule. A spec sheet contains device parts/counts;
flip-flops are derived later, not here.

Usage:
    python3 assess_spec.py <spec.pdf> <DEVICE> > <device>_parts.json
    e.g. python3 assess_spec.py spec/XMP103_...v2.8.pdf VU9P
"""
import json
import re
import subprocess
import sys

DEVCOL = re.compile(r"^[A-Z]{1,3}\d+[A-Z]?$")     # device-name token, e.g. VU9P


def die(m):
    sys.stderr.write("assess_spec: " + m + "\n"); sys.exit(2)


def toks(line):
    return [(m.group(), m.start()) for m in re.finditer(r"\S+", line)]


def main():
    if len(sys.argv) != 3:
        die("usage: assess_spec.py <spec.pdf> <DEVICE> > <device>_parts.json")
    pdf, device = sys.argv[1], sys.argv[2]
    r = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True)
    if r.returncode != 0:
        die("pdftotext failed (is poppler installed?): " + r.stderr.strip())
    lines = r.stdout.splitlines()

    # 1) find the resource-table header: a line where DEVICE sits among >=3 device cols
    hdr_i = dev_pos = None
    dev_cols = []
    for i, l in enumerate(lines):
        t = toks(l)
        devs = [(x, p) for x, p in t if DEVCOL.match(x)]
        if len(devs) >= 3 and any(x == device for x, _ in devs):
            hdr_i, dev_cols = i, devs
            dev_pos = next(p for x, p in devs if x == device)
            break
    if hdr_i is None:
        die(f"device '{device}' not found as a resource-table column header")

    positions = sorted(p for _, p in dev_cols)
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    tol = (min(gaps) // 2) if gaps else 8
    first_col = positions[0]

    # 2) extract each resource row's value in the DEVICE column, verbatim
    parts = []
    for j in range(hdr_i + 1, len(lines)):
        l = lines[j]
        if not l.strip():
            if parts:
                break                      # blank after data => table ended
            continue
        t = toks(l)
        # label = tokens left of the first device column; value = token nearest dev_pos
        label = " ".join(x for x, p in t if p < first_col - tol).strip(" .:")
        cands = [(abs(p - dev_pos), x) for x, p in t if p >= first_col - tol]
        val = next((x for d, x in sorted(cands) if d <= tol), None)
        if not label or val is None:
            # a footnote / section break / non-data row ends the table once we have rows
            if parts and (re.match(r"^\s*\d+\.", l) or "Device" in l):
                break
            continue
        parts.append({"resource": label, "value": val, "source_line": j + 1})

    if not parts:
        die("no resource rows extracted under the device column (layout parse miss)")

    out = {
        "spec": pdf,
        "device": device,
        "note": "VERBATIM device parts from the spec sheet — counts/values exactly as "
                "printed, each with source_line. No materialization, no flip-flops, no "
                "derived values. Flip-flop netlist is a separate, human-dictated step.",
        "parts": parts,
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
