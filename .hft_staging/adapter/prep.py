#!/usr/bin/env python3
"""prep.py — OFFLINE connector/prep: source CSV -> binary records.

This runs OUTSIDE the system (like exporting wire data). It is the per-source
connector: it parses the source's NATIVE text format (CSV), masks/picks ONLY
what the system needs (bid, ask, source-timestamp, seq), converts decimal text
prices to fixed-point u64, and writes a flat BINARY record file the buffer reads.

The in-system path NEVER parses and NEVER sees CSV. Adding a source = adding its
prep here; the adapter netlist is unchanged. No replay/source-type token leaks
into the device — this is purely an offline format converter.

CSV format:  UTC,Ask,Bid,Ask Volume,Bid Volume
  e.g.       24.04.2026 12:00:00.050 UTC,4707.300,4706.800,0,0

Output record (matches adp_record_t in buffer.h): 4 x little-endian u64
  bid, ask, ts, seq

ts = milliseconds relative to the FIRST record (so the first record is ts=0),
derived from the HH:MM:SS.mmm field. This is the ONLY use of the source
timestamp at prep time; downstream the NIC re-stamps with TAI.
"""
import struct
import sys

PRICE_SCALE = 10000  # ×10000 fixed-point (BP_PRICE_SCALE, 4 decimal places)


def price_to_fixed(text):
    """Decimal price text -> integer ×PRICE_SCALE, no float round drift."""
    text = text.strip()
    neg = text.startswith("-")
    if neg:
        text = text[1:]
    if "." in text:
        whole, frac = text.split(".", 1)
    else:
        whole, frac = text, ""
    frac = (frac + "0000")[:4]            # pad/truncate to 4 dp
    val = int(whole or "0") * PRICE_SCALE + int(frac or "0")
    return -val if neg else val


def parse_ts_ms(utc_field):
    """'24.04.2026 12:00:00.050 UTC' -> milliseconds-since-midnight (int)."""
    # take the time token HH:MM:SS.mmm
    parts = utc_field.strip().split()
    time_tok = parts[1]                   # '12:00:00.050'
    hms, ms = (time_tok.split(".") + ["0"])[:2]
    h, m, s = hms.split(":")
    ms = (ms + "000")[:3]
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: prep.py <in.csv> <out.bin>\n")
        sys.exit(2)
    in_path, out_path = sys.argv[1], sys.argv[2]

    rows = []
    base_ms = None
    seq = 0
    with open(in_path) as f:
        header = f.readline()            # skip header line
        for line in f:
            line = line.strip()
            if not line:
                continue
            cols = line.split(",")
            if len(cols) < 3:
                continue
            utc, ask_s, bid_s = cols[0], cols[1], cols[2]
            ts_ms = parse_ts_ms(utc)
            if base_ms is None:
                base_ms = ts_ms
            ts = ts_ms - base_ms
            bid = price_to_fixed(bid_s)
            ask = price_to_fixed(ask_s)
            rows.append((bid, ask, ts, seq))
            seq += 1

    with open(out_path, "wb") as f:
        for (bid, ask, ts, sq) in rows:
            f.write(struct.pack("<QQQQ", bid, ask, ts, sq))

    sys.stderr.write(f"prep: {len(rows)} records -> {out_path} "
                     f"(ts 0..{rows[-1][2] if rows else 0})\n")


if __name__ == "__main__":
    main()
