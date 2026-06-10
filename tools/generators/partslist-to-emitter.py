#!/usr/bin/env python3
"""partslist-to-emitter.py — Convert PARTS_LIST.md to gen_*_net.py.

This tool parses a PARTS_LIST.md file and generates a Python emitter script
(gen_<device>_net.py) that outputs <device>.net.json (the declarative netlist).

The generated emitter follows the flip-flop-level architecture: every signal is an
addressed register, operations are branchless boolean functions (cells), and the
netlist is validated for single-writer / no-overlap / no-floating.

Usage:
    python3 partslist-to-emitter.py <PARTS_LIST.md> <output_dir> [device_name]

Example:
    python3 partslist-to-emitter.py DOM_PARTS_LIST.md .hft_staging/dom dom
    → Generates .hft_staging/dom/gen_dom_net.py
"""

import sys
import re
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound
except ImportError:
    print("ERROR: Jinja2 not installed. Install with: pip install jinja2", file=sys.stderr)
    sys.exit(1)


class PartsListParser:
    """Parse a PARTS_LIST.md and extract hardware specification."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        with open(filepath, 'r') as f:
            self.content = f.read()
        self.device_name = None
        self.spec = {}

    def parse(self) -> Dict[str, Any]:
        """Extract the complete hardware specification."""
        spec = {
            'device': self._extract_device_name(),
            'window_base': self._extract_window_base(),
            'kind': self._extract_kind(),
            'comment': self._extract_comment(),
            'config_nodes': self._extract_config_nodes(),
            'dff_nodes': self._extract_dff_nodes(),
            'tables': self._extract_tables(),
            'comb_nodes': self._extract_comb_nodes(),
            'relay_nodes': self._extract_relay_nodes(),
            'wire_inputs': self._extract_wire_inputs(),
            'power_control': self._extract_power_control(),
            'counters': self._extract_counters(),
            'meta': self._extract_metadata(),
        }
        return spec

    def _extract_device_name(self) -> str:
        """Extract device name from title or header."""
        match = re.search(r'#\s+(\w+)\s+Architectural', self.content, re.IGNORECASE)
        if match:
            name = match.group(1).lower()
            self.device_name = name
            return name
        raise ValueError("Could not extract device name from PARTS_LIST.md")

    def _extract_window_base(self) -> str:
        """Extract the address window base (e.g. 0x0C00000)."""
        match = re.search(r'(\w+)\s+Base\s+Address:\s*(0x[0-9A-Fa-f]+)', self.content)
        if match:
            return match.group(2)
        # Try alternate format
        match = re.search(r'Base[^\n]*:\s*(0x[0-9A-Fa-f]+)', self.content)
        if match:
            return match.group(1)
        return "0x00000000"

    def _extract_kind(self) -> str:
        """Infer device kind from description."""
        if 'gateway' in self.content.lower():
            return 'gateway'
        if 'oscillator' in self.content.lower():
            return 'oscillator'
        if 'depth' in self.content.lower() or 'market' in self.content.lower():
            return 'market-data'
        return 'module'

    def _extract_comment(self) -> str:
        """Extract the purpose/comment from section 1 or preamble."""
        match = re.search(r'\*\*Purpose:\*\*\s*(.+?)(?:\n\n|\n\*\*)', self.content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return "Auto-generated from PARTS_LIST.md"

    def _extract_config_nodes(self) -> List[Dict[str, str]]:
        """Extract input lanes / config nodes."""
        nodes = []
        # Look for "INPUT INTERFACE" or "CONFIG" sections with bullet lists
        pattern = r'##\s+(?:1\.|INPUT|CONFIG)[^\n]*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if not match:
            return nodes

        section = match.group(1)
        # Find bullet-list items: `- NAME` — description
        items = re.findall(r'^-\s+`([A-Z_]+)`\s*(?:—|:)?\s*(.+?)$', section, re.MULTILINE)

        for name, desc in items:
            # Infer type from description
            node_type = 'u64'
            # Only mark as 'bit' if explicitly a single-bit flag (not a price or other multi-bit value)
            if any(w in desc.lower() for w in ['strobe', 'flag', 'empty', 'valid', 'enable', '1-bit', 'single-bit']):
                node_type = 'bit'

            nodes.append({
                'name': name,
                'type': node_type,
                'comment': desc.strip()
            })

        return nodes

    def _extract_dff_nodes(self) -> List[Dict[str, str]]:
        """Extract registered state (DFFs)."""
        nodes = []

        # Extract best-price registers (section 3)
        pattern = r'##\s+3\.\s+BEST-PRICE[^\n]*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if match:
            section = match.group(1)
            items = re.findall(r'^-+\s*`?([A-Z_]+(?:_REG|_PRICE|_QTY))`?\s*(?:—|:)?\s*(.+?)$', section, re.MULTILINE)
            for name, desc in items:
                node_type = 'u64'
                if 'bit' in desc.lower():
                    node_type = 'bit'
                nodes.append({
                    'name': name,
                    'type': node_type,
                    'comment': desc.strip()[:80]
                })

        # Extract running totals (section 4)
        pattern = r'##\s+4\.\s+RUNNING\s+TOTALS[^\n]*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if match:
            section = match.group(1)
            items = re.findall(r'^-+\s*`?([A-Z_]+_REG)`?\s*(?:—|:)?\s*(.+?)$', section, re.MULTILINE)
            for name, desc in items:
                nodes.append({
                    'name': name,
                    'type': 'u64',
                    'comment': desc.strip()[:80]
                })

        # Extract metadata / last feed (section 7)
        pattern = r'##\s+7\.\s+METADATA[^\n]*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if match:
            section = match.group(1)
            items = re.findall(r'^-+\s*`?([A-Z_]+_REG)`?\s*(?:—|:)?\s*(.+?)$', section, re.MULTILINE)
            for name, desc in items:
                nodes.append({
                    'name': name,
                    'type': 'u64',
                    'comment': desc.strip()[:80]
                })

        # Extract internal state (section 9)
        pattern = r'##\s+9\.\s+INTERNAL\s+STATE[^\n]*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if match:
            section = match.group(1)
            items = re.findall(r'^-+\s*`?([A-Z_]+)`?\s*(?:—|:)?\s*(.+?)$', section, re.MULTILINE)
            for name, desc in items:
                nodes.append({
                    'name': name,
                    'type': 'u64',
                    'comment': desc.strip()[:80]
                })

        return nodes

    def _extract_tables(self) -> List[Dict[str, Any]]:
        """Extract array registers (price-indexed tables, ring buffers, etc)."""
        tables = []

        # Extract price-indexed memory tables (section 2)
        pattern = r'##\s+2\.\s+PRICE-INDEXED[^\n]*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if match:
            section = match.group(1)
            # Pattern: `TABLE_NAME[SIZE]` — description
            items = re.findall(r'`([A-Z_]+)\[([^\]]+)\]`\s*(?:—|:)?\s*(.+?)(?=\n\n|\n`|\Z)', section, re.DOTALL)
            for name, index_spec, desc in items:
                # Clean multiline desc to first line
                first_line = desc.split('\n')[0].strip()
                table = {
                    'name': name,
                    'index_spec': index_spec,
                    'comment': first_line[:100],
                    'type': 'u64',
                    'kind': 'indexed'
                }
                # Extract depth if numeric
                if index_spec.isdigit():
                    table['depth'] = int(index_spec)
                elif '16384' in index_spec or '16384' in first_line:
                    table['depth'] = 16384
                tables.append(table)

        return tables

    def _extract_comb_nodes(self) -> List[Dict[str, Any]]:
        """Extract combinational logic (derived registers, computed values)."""
        nodes = []

        # Look for "DERIVED" sections with cell descriptions
        pattern = r'(?:DERIVED|COMBINATIONAL)[^\n]*\n.*?(?=\n##|$)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if not match:
            return nodes

        section = match.group(0)
        items = re.findall(r'^-\s+`?([A-Z_]+)`?\s*(?:—|:)?\s*(.+?)$', section, re.MULTILINE)

        for name, desc in items:
            node = {
                'name': name,
                'type': 'u64',
                'comment': desc[:80]
            }

            # Infer cell type from description
            if 'mux' in desc.lower():
                node['cell'] = 'cell_mux'
            elif 'addsub' in desc.lower() or 'subtract' in desc.lower():
                node['cell'] = 'cell_addsub'
            elif 'shift' in desc.lower():
                node['cell'] = 'cell_shift'
            elif 'eqmask' in desc.lower():
                node['cell'] = 'cell_eqmask'

            nodes.append(node)

        return nodes

    def _extract_relay_nodes(self) -> List[Dict[str, Any]]:
        """Extract relay / output lanes for downstream consumers."""
        nodes = []

        # Extract relay outputs (section 8)
        pattern = r'##\s+8\.\s+RELAY[^\n]*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if not match:
            return nodes

        section = match.group(1)
        # Pattern: `TABLE_NAME[RANGE]` — description
        items = re.findall(r'`([A-Z_]+)\[([^\]]+)\]`\s*(?:—|:)?\s*(.+?)(?=\n\n|\n`|\Z)', section, re.DOTALL)

        for name, index_range, desc in items:
            first_line = desc.split('\n')[0].strip()
            node = {
                'name': name,
                'index_range': index_range,
                'type': 'u64',
                'comment': first_line[:80]
            }
            nodes.append(node)

        return nodes

    def _extract_wire_inputs(self) -> List[str]:
        """Extract external wire/bus inputs."""
        inputs = []

        # Pattern: list like WIRE_BID, WIRE_ASK, etc under "wire_inputs" section
        pattern = r'"wire_inputs":\s*\[(.*?)\]'
        match = re.search(pattern, self.content, re.DOTALL)
        if match:
            items = re.findall(r'"([A-Z_]+)"', match.group(1))
            inputs.extend(items)

        # Fallback: search for explicit wire lanes
        if not inputs:
            pattern = r'`(WIRE_[A-Z_]+)`'
            inputs = list(set(re.findall(pattern, self.content)))

        return inputs

    def _extract_power_control(self) -> Dict[str, Any]:
        """Extract power/enable control signals."""
        power_ctrl = {
            'power_bit': None,
            'run_bound': None
        }

        # Look for power bit definition
        match = re.search(r'`([A-Z_]*POWER[A-Z_]*)`', self.content)
        if match:
            power_ctrl['power_bit'] = match.group(1)

        # Look for run/bound conditions
        if 'RUN_UNTIL' in self.content or 'run_bound' in self.content:
            power_ctrl['run_bound'] = True

        return power_ctrl

    def _extract_counters(self) -> List[Dict[str, Any]]:
        """Extract event/diagnostic counters."""
        counters = []

        # Extract event counters (section 6)
        pattern = r'##\s+6\.\s+EVENT\s+COUNTERS[^\n]*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
        if not match:
            return counters

        section = match.group(1)
        items = re.findall(r'^-+\s*`?([A-Z_]+(?:_COUNT|_REG))`?\s*(?:—|:)?\s*(.+?)$', section, re.MULTILINE)

        for name, desc in items:
            if not name or name in [ctr['name'] for ctr in counters]:
                continue
            counters.append({
                'name': name,
                'type': 'u64',
                'comment': desc.strip()[:80]
            })

        return counters

    def _extract_metadata(self) -> Dict[str, str]:
        """Extract metadata (status, date, etc)."""
        meta = {}

        # Extract date
        match = re.search(r'\*\*Date:\*\*\s*(.+?)(?:\n|$)', self.content)
        if match:
            meta['date'] = match.group(1).strip()

        # Extract status
        match = re.search(r'\*\*Status:\*\*\s*(.+?)(?:\n|$)', self.content)
        if match:
            meta['status'] = match.group(1).strip()

        return meta


class EmitterGenerator:
    """Generate a Python emitter script from a parsed PARTS_LIST spec."""

    def __init__(self, spec: Dict[str, Any], template_dir: Optional[str] = None):
        self.spec = spec
        if template_dir is None:
            template_dir = os.path.dirname(__file__)

        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate(self) -> str:
        """Generate the emitter script as a string."""
        try:
            template = self.env.get_template('emitter-template.jinja2')
        except TemplateNotFound:
            raise RuntimeError(
                f"Template 'emitter-template.jinja2' not found. "
                f"Expected in: {self.env.loader.searchpath}"
            )

        return template.render(spec=self.spec)

    def validate_spec(self) -> List[str]:
        """Validate the parsed spec for critical fields."""
        errors = []

        if not self.spec.get('device'):
            errors.append("Missing device name")
        if not self.spec.get('window_base'):
            errors.append("Missing window_base address")

        return errors


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    partslist_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(partslist_file)
    device_override = sys.argv[3] if len(sys.argv) > 3 else None

    # Ensure input exists
    if not os.path.exists(partslist_file):
        print(f"ERROR: PARTS_LIST.md not found: {partslist_file}", file=sys.stderr)
        sys.exit(1)

    # Parse the PARTS_LIST
    print(f"Parsing {partslist_file}...", file=sys.stderr)
    parser = PartsListParser(partslist_file)
    spec = parser.parse()

    # Override device name if provided
    if device_override:
        spec['device'] = device_override

    # Validate the spec
    gen = EmitterGenerator(spec)
    errors = gen.validate_spec()
    if errors:
        print(f"ERROR: Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Generate the emitter script
    print(f"Generating emitter for device: {spec['device']}", file=sys.stderr)
    emitter_code = gen.generate()

    # Write to output file
    output_file = os.path.join(output_dir, f"gen_{spec['device']}_net.py")
    os.makedirs(output_dir, exist_ok=True)

    with open(output_file, 'w') as f:
        f.write(emitter_code)

    # Make executable
    os.chmod(output_file, 0o755)

    print(f"✓ Generated {output_file}", file=sys.stderr)
    print(f"✓ Next: cd {output_dir} && python3 gen_{spec['device']}_net.py", file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main())
