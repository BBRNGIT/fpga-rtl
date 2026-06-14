#!/usr/bin/env python3
"""
boardparse.py — Tool: extract the BOARD NETLIST from a board user-manual PDF (Z19).

Each pinout-table row is a CONNECTION: board-signal -> FPGA pin-function -> BGA ball,
grouped by interface (DDR4, PCIe, DisplayPort, USB, Ethernet, SFP, FMC, ...). The
FPGA pin-function name reveals the on-chip resource it lands on (transceiver / PL-IO /
PS-MIO / DDR / refclk). This is the source->destination backbone that, joined with the
chip-internal connections, makes the full block diagram self-assemble.

Output board_net.json: [{signal, pin, ball, iface, resource, dir}], + a summary.
Usage: boardparse.py <pdf> [--pages a-b] [--out board_net.json]
"""
import sys, os, re, json, argparse
try:
    import fitz
except Exception as e:
    print(f"boardparse: PyMuPDF required: {e}"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
BALL = re.compile(r'^[A-Z]{1,2}[0-9]{1,2}$')                       # BGA ball: BA30, N19, AG37
# an FPGA pin-FUNCTION (after normalizing spaces->_): bank-number suffix, or IO_L.., or MGT
PINF = re.compile(r'(_\d{2,3}$)|(^IO_?L)|(MGT)')
HDR  = re.compile(r'(pin assignment|pin assign|assignment of|interface|port)', re.I)

def norm(s):  return re.sub(r'\s+', '_', (s or '').strip()).strip('_')

def resource_of(pin):
    p = pin.upper()
    if 'MGTREFCLK' in p: return 'GT_refclk'
    if 'MGTR' in p or 'MGT' in p: return 'transceiver(GT/PS-GTR)'
    if 'PS_DDR' in p: return 'PS_DDR'
    if 'PS_MIO' in p or re.search(r'\bMIO\d', p): return 'PS_MIO'
    if p.startswith('IO_') or p.startswith('IO'): return 'PL_IO'
    if 'PS_' in p: return 'PS'
    return 'other'

def direction_of(sig):
    s = sig.upper()
    if re.search(r'(^|_)(TX|TXP|TXN|TXD|TXCK|MOSI|SSTX|DQ?S?_?P?_?OUT)', s): return 'out'
    if re.search(r'(^|_)(RX|RXP|RXN|RXD|RXCK|MISO|SSRX)', s): return 'in'
    return ''

def heading_above(page, tbl, carry):
    y0 = tbl.bbox[1]; best, bd = None, 1e9
    for b in page.get_text("blocks"):
        t = b[4].strip().replace("\n", " ")
        if b[3] <= y0 + 2 and 0 <= y0 - b[3] < bd and HDR.search(t):
            bd, best = y0 - b[3], t
    return (best or carry)

def iface_of(heading):
    if not heading: return 'unknown'
    h = heading.lower()
    for key, name in [("ddr4", "DDR4"), ("pcie", "PCIe"), ("displayport", "DisplayPort"),
                      ("usb", "USB3"), ("ethernet", "Ethernet"), ("sfp", "SFP"), ("fiber", "SFP"),
                      ("fmc", "FMC"), ("sata", "SATA"), ("sma", "SMA"), ("qspi", "QSPI"),
                      ("emmc", "eMMC"), ("sd", "SD"), ("uart", "UART"), ("can", "CAN"),
                      ("mipi", "MIPI"), ("clock", "Clock")]:
        if key in h: return name + (" (PS)" if " ps " in " " + h else (" (PL)" if " pl " in " " + h else ""))
    return heading[:24]

def parse_row(cells):
    cells = [c.replace("\n", " ").strip() for c in cells if c and c.strip()]
    seen, ded = set(), []                                  # dedup (tables repeat cells)
    for c in cells:
        if c not in seen: seen.add(c); ded.append(c)
    if len(ded) < 2: return None
    ball = next((norm(c) for c in ded if BALL.match(norm(c))), '')
    cand = [norm(c) for c in ded if norm(c) != ball]
    pin = next((c for c in cand if PINF.search(c)), None)  # the FPGA pin-function
    if not pin: return None
    sig = next((c for c in cand if c != pin), pin)         # the board net = the other cell
    rem = next((c for c in ded if len(c) > 16 and norm(c) not in (pin, sig)), '')
    return {"signal": sig, "pin": pin, "ball": ball,
            "resource": resource_of(pin), "dir": direction_of(sig), "remark": rem[:40]}

def run(pdf, pages, out):
    doc = fitz.open(pdf); rng = range(doc.page_count)
    if pages:
        a, b = pages.split("-"); rng = range(int(a) - 1, int(b))
    net, carry = [], None
    for i in rng:
        if i < 0 or i >= doc.page_count: continue
        page = doc[i]
        try: tabs = page.find_tables()
        except Exception: continue
        for t in tabs.tables:
            carry = heading_above(page, t, carry)
            iface = iface_of(carry)
            for r in t.extract():
                row = parse_row(r)
                if row and row["pin"]:
                    row["iface"] = iface; row["page"] = i + 1
                    net.append(row)
    # dedup by (pin,ball,signal)
    seen, uniq = set(), []
    for r in net:
        k = (r["pin"], r["ball"], r["signal"])
        if k not in seen: seen.add(k); uniq.append(r)
    json.dump(uniq, open(out, "w"), indent=2)
    # summary
    from collections import Counter
    by_if = Counter(r["iface"] for r in uniq); by_res = Counter(r["resource"] for r in uniq)
    print(f"boardparse: {len(uniq)} connections -> {out}")
    print("  by interface:", dict(by_if.most_common()))
    print("  by FPGA resource:", dict(by_res.most_common()))
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--pages", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "board_net.json"))
    a = ap.parse_args()
    sys.exit(run(a.pdf, a.pages, a.out))
