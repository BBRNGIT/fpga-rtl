#!/usr/bin/env python3
"""
spec-to-partslist.py

Reads a simple YAML design spec and outputs a complete PARTS_LIST.md.

Input: YAML file with device, kind, comment, dff_nodes, tables, cross_module_inputs, seam_nodes
Output: Markdown parts list with all 9 sections (interface, registers, tables, relay, gates, layout, dataflow, constraints, commit expectations)

Usage:
    python3 spec-to-partslist.py <spec.yaml> > <DEVICE>_PARTS_LIST.md

Example:
    python3 spec-to-partslist.py footprint.yaml > FOOTPRINT_PARTS_LIST.md
"""

import sys
import yaml
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

def load_spec(spec_file):
    """Load and validate the YAML spec."""
    with open(spec_file, 'r') as f:
        spec = yaml.safe_load(f)

    # Validate required fields
    required = ['device', 'kind', 'comment']
    for field in required:
        if field not in spec:
            raise ValueError(f"Missing required field: {field}")

    # Set defaults
    spec.setdefault('dff_nodes', [])
    spec.setdefault('config_nodes', [])
    spec.setdefault('comb_nodes', [])
    spec.setdefault('tables', [])
    spec.setdefault('cross_module_inputs', [])
    spec.setdefault('seam_nodes', [])
    spec.setdefault('history_ring', None)

    return spec

def load_template(template_path):
    """Load the Jinja2 template from file."""
    if not Path(template_path).exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, 'r') as f:
        template_str = f.read()

    return Template(template_str)

def render_partslist(spec, template):
    """Render the parts list from spec using template."""

    context = {
        'device': spec['device'],
        'device_title': spec['device'].upper(),
        'device_title_caps': spec['device'].replace('_', ' ').title(),
        'kind': spec['kind'],
        'comment': spec['comment'],
        'date': datetime.now().strftime('%Y-%m-%d'),
        'dff_nodes': spec.get('dff_nodes', []),
        'config_nodes': spec.get('config_nodes', []),
        'comb_nodes': spec.get('comb_nodes', []),
        'tables': spec.get('tables', []),
        'cross_module_inputs': spec.get('cross_module_inputs', []),
        'seam_nodes': spec.get('seam_nodes', []),
        'history_ring': spec.get('history_ring', None),
    }

    return template.render(context)

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h', 'help'):
        print(f"Usage: {sys.argv[0]} <spec.yaml> [template.jinja2]")
        print()
        print("Read a design spec (YAML) and output a complete PARTS_LIST.md (hardware specification).")
        print()
        print("Arguments:")
        print("  <spec.yaml>          Input specification file (YAML format)")
        print("  [template.jinja2]    Template file (default: partslist-template.jinja2)")
        print()
        print("Required YAML fields:")
        print("  device   - module name (lowercase, e.g., footprint)")
        print("  kind     - module kind (indicator, accumulator, clock, gateway, etc.)")
        print("  comment  - module description")
        print()
        print("Optional YAML fields:")
        print("  dff_nodes              - sequential state registers")
        print("  config_nodes           - initialization constants")
        print("  tables                 - array registers (indexed by price level)")
        print("  cross_module_inputs    - reads from other modules")
        print("  seam_nodes             - published relay outputs")
        print("  history_ring           - snapshot ring for display")
        print()
        print("Output: 9-section markdown parts list to stdout")
        print()
        print("Example:")
        print(f"  {sys.argv[0]} footprint.yaml > FOOTPRINT_PARTS_LIST.md")
        sys.exit(0 if '--help' in sys.argv or '-h' in sys.argv else 1)

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <spec.yaml> [template.jinja2]", file=sys.stderr)
        print(f"\nDefault template: partslist-template.jinja2 (in same directory as this script)", file=sys.stderr)
        sys.exit(1)

    spec_file = sys.argv[1]

    # Default template is in same directory as this script
    script_dir = Path(__file__).parent
    template_file = sys.argv[2] if len(sys.argv) > 2 else str(script_dir / 'partslist-template.jinja2')

    try:
        # Load spec
        spec = load_spec(spec_file)

        # Load template
        template = load_template(template_file)

        # Render
        output = render_partslist(spec, template)

        # Write to stdout
        print(output)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"YAML parse error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
