#!/usr/bin/env bash
# fetch_docs.sh — reproducible source-PDF acquisition (the PDFs are large vendor binaries,
# NOT committed; the parsed cache/ IS committed and is what every parser reads). Only run
# this if you need to RE-extract (extract.py --force) or run figblocks (which reads PDFs
# directly for vector drawings). Normal builds read the committed cache and need no PDFs.
set -e
DEST="$(cd "$(dirname "$0")/../.." && pwd)"          # repo root
BASE="https://0x04.net/~mwk/xidocs"
declare -a DOCS=(
  "ug/ug570-ultrascale-configuration.pdf"
  "ug/ug571-ultrascale-selectio.pdf"
  "ug/ug572-ultrascale-clocking.pdf"            # note: clocking is also a 'ug' file upstream
  "ug/ug573-ultrascale-memory-resources.pdf"
  "ug/ug574-ultrascale-clb.pdf"
  "ug/ug576-ultrascale-gth-transceivers.pdf"
  "ug/ug578-ultrascale-gty-transceivers.pdf"
  "ug/ug579-ultrascale-dsp.pdf"
  "ug/ug1085-zynq-ultrascale-trm.pdf"
  "lib/ug974-vivado-ultrascale-libraries.pdf"
)
for rel in "${DOCS[@]}"; do
  fn="$(basename "$rel")"
  if [ -f "$DEST/$fn" ]; then echo "have $fn"; continue; fi
  echo "fetching $fn ..."
  curl -sS -o "$DEST/$fn" "$BASE/$rel" && echo "  -> $(wc -c < "$DEST/$fn") bytes"
done
echo "done. (DS891 + Z19 are obtained separately — vendor-gated.)"
