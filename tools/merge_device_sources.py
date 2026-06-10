#!/usr/bin/env python3
"""
merge_device_sources.py — Reconcile FPGA device specs from multiple sources.

This tool merges device specifications from datasheets, f4pga, and Project Trellis
into a canonical device model with source attribution and conflict detection.

Input sources:
  - device_specs.json (from parse_datasheets.py): datasheet specs
  - f4pga device database: f4pga JSON files (cached)
  - Project Trellis docs: ECP5 bitstream reference (static)

Output:
  - canonical_device_model.json: reconciled specs with:
    * source attribution for each spec field
    * confidence scores (high/medium/low)
    * conflict logs for manual review
    * validation summary (consistency score, conflicts, warnings)

Architecture:
  1. Load all source specs (datasheet primary, f4pga/Trellis cross-check)
  2. Normalize names and units across sources
  3. Merge specs, flagging conflicts and mismatches
  4. Validate consistency (CLB count vs. routing capacity, etc.)
  5. Output canonical model with audit trail

Design philosophy:
  - Datasheet is the primary source (authoritative)
  - f4pga/Trellis used for cross-validation and gaps
  - All conflicts logged with source and severity
  - Confidence score = agreement across sources + datasheet match
"""

import json
import sys
import os
import re
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from urllib.parse import urljoin
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


class Confidence(Enum):
    """Confidence level for a specification."""
    HIGH = "high"        # Datasheet + cross-validation agree
    MEDIUM = "medium"    # Datasheet only, or secondary sources agree but differ from datasheet
    LOW = "low"          # Conflicting sources or weak evidence
    UNKNOWN = "unknown"  # No source data


class SourceType(Enum):
    """Source identifier."""
    DATASHEET = "datasheet"
    F4PGA = "f4pga"
    TRELLIS = "trellis"
    INFERRED = "inferred"


@dataclass
class SpecValue:
    """A single specification value with source attribution."""
    value: Any
    source: SourceType
    confidence: Confidence
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source.value,
            "confidence": self.confidence.value,
            "notes": self.notes
        }


@dataclass
class Conflict:
    """A detected conflict between sources."""
    field: str
    sources: Dict[SourceType, Any]
    resolution: str  # chosen value/logic
    severity: str    # warning, error


class DeviceSpecMerger:
    """Merge FPGA device specs from multiple sources."""

    def __init__(self, output_dir: str = "."):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.conflicts: List[Conflict] = []
        self.warnings: List[str] = []
        self.datasheet_specs: Dict[str, Any] = {}
        self.f4pga_specs: Dict[str, Any] = {}
        self.trellis_specs: Dict[str, Any] = {}
        self.merged: Dict[str, Any] = {}

    def load_datasheet_specs(self, filepath: str) -> None:
        """Load device_specs.json from datasheet parser."""
        try:
            with open(filepath, 'r') as f:
                self.datasheet_specs = json.load(f)
            logger.info(f"Loaded datasheet specs from {filepath}")
        except FileNotFoundError:
            logger.warning(f"Datasheet specs not found at {filepath}")
            self.datasheet_specs = {}

    def load_f4pga_specs(self, filepath: str) -> None:
        """Load f4pga device database."""
        try:
            with open(filepath, 'r') as f:
                self.f4pga_specs = json.load(f)
            logger.info(f"Loaded f4pga specs from {filepath}")
        except FileNotFoundError:
            logger.warning(f"f4pga specs not found at {filepath}")
            self.f4pga_specs = {}

    def load_trellis_specs(self, filepath: str) -> None:
        """Load Project Trellis ECP5 reference specs."""
        try:
            with open(filepath, 'r') as f:
                self.trellis_specs = json.load(f)
            logger.info(f"Loaded Trellis specs from {filepath}")
        except FileNotFoundError:
            logger.warning(f"Trellis specs not found at {filepath}")
            self.trellis_specs = {}

    def download_f4pga_db(self, cache_dir: str = ".f4pga_cache") -> bool:
        """
        Download and cache f4pga device database.
        (Stub: in production, use requests or curl to fetch from f4pga repo)
        """
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)

        # Placeholder for production implementation
        logger.info(f"f4pga download would cache to {cache_dir}")
        return False

    def normalize_device_name(self, name: str) -> str:
        """Normalize device name across sources (remove spacing, case)."""
        # Remove hyphens, spaces; lowercase
        normalized = name.lower().replace("-", "").replace(" ", "").replace("_", "")
        return normalized

    def normalize_part_name(self, part_type: str) -> str:
        """Normalize part type names across sources."""
        normalization = {
            "clb": "CLB",
            "slc": "CLB",  # Lattice equivalent
            "lut": "LUT",
            "ff": "FF",
            "dff": "FF",
            "ram": "BRAM",
            "bram": "BRAM",
            "dspr": "DSP",
            "dsp": "DSP",
            "dsp48": "DSP",
            "io": "IOB",
            "iob": "IOB",
            "iob33": "IOB",
            "iob18": "IOB",
            "iob25": "IOB",
        }
        normalized = part_type.lower().strip()
        return normalization.get(normalized, part_type)

    def extract_numeric(self, value: Any) -> Optional[float]:
        """Extract numeric value from string or number."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r'[\d.]+', value)
            if match:
                return float(match.group())
        return None

    def compare_numeric(
        self,
        val1: Any,
        val2: Any,
        tolerance_pct: float = 5.0
    ) -> bool:
        """Check if two numeric values agree within tolerance."""
        num1 = self.extract_numeric(val1)
        num2 = self.extract_numeric(val2)
        if num1 is None or num2 is None:
            return False
        if num1 == 0:
            return num2 == 0
        pct_diff = abs(num1 - num2) / max(abs(num1), abs(num2)) * 100
        return pct_diff <= tolerance_pct

    def merge_parts_list(
        self,
        device_name: str
    ) -> List[Dict[str, Any]]:
        """Merge parts lists from all sources."""
        parts_by_type: Dict[str, Dict[str, Any]] = {}

        # Collect parts from datasheet
        if device_name in self.datasheet_specs.get("devices", {}):
            ds_device = self.datasheet_specs["devices"][device_name]
            for part in ds_device.get("parts", []):
                part_type = self.normalize_part_name(part.get("type", ""))
                if part_type not in parts_by_type:
                    parts_by_type[part_type] = {
                        "name": part.get("name", part_type),
                        "type": part_type,
                        "count": SpecValue(
                            part.get("count", 0),
                            SourceType.DATASHEET,
                            Confidence.HIGH
                        ),
                        "io_per_unit": SpecValue(
                            part.get("io_per_unit", 0),
                            SourceType.DATASHEET,
                            Confidence.HIGH
                        ),
                    }
                else:
                    # Update with datasheet values
                    parts_by_type[part_type]["count"] = SpecValue(
                        part.get("count", parts_by_type[part_type]["count"].value),
                        SourceType.DATASHEET,
                        Confidence.HIGH
                    )

        # Collect parts from f4pga (cross-check)
        if device_name in self.f4pga_specs.get("devices", {}):
            f4_device = self.f4pga_specs["devices"][device_name]
            for part in f4_device.get("parts", []):
                part_type = self.normalize_part_name(part.get("type", ""))
                if part_type in parts_by_type:
                    # Cross-validate count
                    ds_count = parts_by_type[part_type]["count"].value
                    f4_count = part.get("count", ds_count)
                    if self.compare_numeric(ds_count, f4_count, tolerance_pct=3.0):
                        # Confidence increased by agreement
                        parts_by_type[part_type]["count"].confidence = Confidence.HIGH
                    else:
                        # Log conflict
                        self._log_conflict(
                            f"parts.{part_type}.count",
                            {SourceType.DATASHEET: ds_count, SourceType.F4PGA: f4_count},
                            ds_count,
                            "warning"
                        )
                        logger.warning(
                            f"Part count mismatch for {part_type}: "
                            f"datasheet={ds_count}, f4pga={f4_count}"
                        )

        # Collect parts from Trellis (secondary)
        if device_name in self.trellis_specs.get("devices", {}):
            tr_device = self.trellis_specs["devices"][device_name]
            for part in tr_device.get("parts", []):
                part_type = self.normalize_part_name(part.get("type", ""))
                if part_type not in parts_by_type:
                    parts_by_type[part_type] = {
                        "name": part.get("name", part_type),
                        "type": part_type,
                        "count": SpecValue(
                            part.get("count", 0),
                            SourceType.TRELLIS,
                            Confidence.MEDIUM
                        ),
                        "io_per_unit": SpecValue(
                            part.get("io_per_unit", 0),
                            SourceType.TRELLIS,
                            Confidence.MEDIUM
                        ),
                    }

        # Convert to output format
        result = []
        for part_type, part_spec in parts_by_type.items():
            count_spec = part_spec["count"]
            io_per_unit_spec = part_spec.get("io_per_unit", SpecValue(0, SourceType.INFERRED, Confidence.UNKNOWN))

            result.append({
                "name": part_spec.get("name", part_type),
                "type": part_type,
                "count": count_spec.to_dict(),
                "io_per_unit": io_per_unit_spec.to_dict() if isinstance(io_per_unit_spec, SpecValue) else io_per_unit_spec,
                "total_io": {
                    "value": count_spec.value * (io_per_unit_spec.value if isinstance(io_per_unit_spec, SpecValue) else io_per_unit_spec),
                    "source": count_spec.source.value,
                    "confidence": count_spec.confidence.value,
                }
            })

        return result

    def infer_routing_capacity(self, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Infer routing resources based on parts count."""
        # Find CLB count
        clb_count = 0
        clb_source = SourceType.INFERRED
        for part in parts:
            if part["type"] == "CLB":
                clb_count = part["count"]["value"]
                clb_source = SourceType[part["count"]["source"].upper()]
                break

        if clb_count == 0:
            clb_count = 1  # Fallback

        # Estimate routing based on industry ratios
        # Typical FPGA: ~9 local wires per CLB, ~2.5M regional per 182K CLBs
        local_estimate = int(clb_count * 9)
        regional_estimate = int(clb_count * 13.7)  # ~2.5M per 182K CLBs

        return {
            "local": {
                "value": local_estimate,
                "source": clb_source.value,
                "confidence": "medium" if clb_source == SourceType.DATASHEET else "low",
                "note": f"Inferred from {clb_count} CLBs at ~9 local wires/CLB"
            },
            "regional": {
                "value": regional_estimate,
                "source": clb_source.value,
                "confidence": "medium" if clb_source == SourceType.DATASHEET else "low",
                "note": f"Inferred from {clb_count} CLBs at ~13.7 regional/CLB"
            }
        }

    def validate_consistency(
        self,
        device_name: str,
        parts: List[Dict[str, Any]],
        routing: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """Validate consistency of merged specs."""
        issues = []
        score = 1.0  # Start at perfect

        # Check for required parts
        part_types = {p["type"] for p in parts}
        if "CLB" not in part_types:
            issues.append("Missing CLB (required for any FPGA device)")
            score -= 0.1

        if "IOB" not in part_types:
            issues.append("Missing IOB (required for I/O)")
            score -= 0.05

        # Cross-check: total I/O from parts list should be reasonable
        total_io = sum(
            p["total_io"]["value"] for p in parts if "total_io" in p
        )
        if total_io == 0:
            issues.append("No I/O found in parts list (likely incomplete)")
            score -= 0.2

        # Check routing capacity sanity
        if "local" in routing:
            local_count = routing["local"]["value"]
            # Sanity: local routing should be 1-100x CLB count
            if total_io > 0:
                clb_count = next(
                    (p["count"]["value"] for p in parts if p["type"] == "CLB"),
                    1
                )
                if not (clb_count < local_count < clb_count * 100):
                    issues.append(
                        f"Local routing capacity ({local_count}) "
                        f"seems inconsistent with CLB count ({clb_count})"
                    )
                    score -= 0.1

        # Check source agreement (cross-sources boost confidence)
        datasheet_count = sum(
            1 for p in parts
            if p["count"]["source"] == "datasheet"
        )
        if len(parts) > 0 and datasheet_count < len(parts) * 0.7:
            issues.append(
                f"Only {datasheet_count}/{len(parts)} parts from datasheet; "
                "others inferred or from secondary sources"
            )
            score -= 0.1

        return max(0.0, min(1.0, score)), issues

    def _log_conflict(
        self,
        field: str,
        sources: Dict[SourceType, Any],
        resolution: Any,
        severity: str = "warning"
    ) -> None:
        """Log a conflict for audit trail."""
        conflict = Conflict(
            field=field,
            sources=sources,
            resolution=str(resolution),
            severity=severity
        )
        self.conflicts.append(conflict)

    def merge_device(self, device_name: str) -> Dict[str, Any]:
        """Merge all specs for a single device."""
        norm_name = self.normalize_device_name(device_name)
        logger.info(f"Merging specs for device: {device_name}")

        # Determine which source has this device
        has_datasheet = device_name in self.datasheet_specs.get("devices", {})
        has_f4pga = any(
            self.normalize_device_name(d) == norm_name
            for d in self.f4pga_specs.get("devices", {})
        )
        has_trellis = any(
            self.normalize_device_name(d) == norm_name
            for d in self.trellis_specs.get("devices", {})
        )

        sources = [s for s, has in [
            (SourceType.DATASHEET.value, has_datasheet),
            (SourceType.F4PGA.value, has_f4pga),
            (SourceType.TRELLIS.value, has_trellis),
        ] if has]

        if not sources:
            logger.error(f"Device {device_name} not found in any source")
            return {}

        # Merge parts list
        parts = self.merge_parts_list(device_name)

        # Infer routing
        routing = self.infer_routing_capacity(parts)

        # Validate consistency
        consistency_score, validation_issues = self.validate_consistency(
            device_name,
            parts,
            routing
        )

        return {
            "device": {
                "name": device_name,
                "sources": sources,
                "source_agreement": {
                    "all_agree": len(sources) > 1 and len(self.conflicts) == 0,
                    "source_count": len(sources),
                }
            },
            "parts": parts,
            "routing": routing,
            "validation": {
                "consistency_score": round(consistency_score, 2),
                "conflicts": len(self.conflicts),
                "warnings": len(self.warnings),
                "issues": validation_issues[:5],  # Top 5 issues
                "confidence": self._determine_overall_confidence(sources, consistency_score)
            },
            "audit": {
                "conflicts_log": [
                    {
                        "field": c.field,
                        "sources": {s.value: v for s, v in c.sources.items()},
                        "resolution": c.resolution,
                        "severity": c.severity,
                    }
                    for c in self.conflicts
                ],
                "warnings": self.warnings[:10],
            }
        }

    def _determine_overall_confidence(
        self,
        sources: List[str],
        consistency_score: float
    ) -> str:
        """Determine overall confidence level."""
        if consistency_score < 0.6 or len(self.conflicts) > 5:
            return "low"
        elif consistency_score < 0.8:
            return "medium"
        elif len(sources) > 2 and consistency_score > 0.95:
            return "high"
        elif len(sources) > 1:
            return "high"
        else:
            return "medium"

    def merge_all_devices(self) -> Dict[str, Any]:
        """Merge all available devices."""
        all_devices = set()
        all_devices.update(self.datasheet_specs.get("devices", {}).keys())
        all_devices.update(self.f4pga_specs.get("devices", {}).keys())
        all_devices.update(self.trellis_specs.get("devices", {}).keys())

        merged_devices = {}
        for device in sorted(all_devices):
            self.conflicts = []  # Reset for each device
            merged = self.merge_device(device)
            if merged:
                merged_devices[device] = merged

        return {
            "schema_version": "1.0",
            "generation_timestamp": self._iso_timestamp(),
            "source_summary": {
                "datasheet_devices": len(self.datasheet_specs.get("devices", {})),
                "f4pga_devices": len(self.f4pga_specs.get("devices", {})),
                "trellis_devices": len(self.trellis_specs.get("devices", {})),
                "merged_devices": len(merged_devices),
            },
            "devices": merged_devices,
            "global_validation": self._global_validation_report(merged_devices),
        }

    def _iso_timestamp(self) -> str:
        """Return current time in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

    def _global_validation_report(self, devices: Dict[str, Any]) -> Dict[str, Any]:
        """Generate global validation report."""
        total_devices = len(devices)
        high_confidence = sum(
            1 for d in devices.values()
            if d.get("validation", {}).get("confidence") == "high"
        )
        with_conflicts = sum(
            1 for d in devices.values()
            if d.get("validation", {}).get("conflicts", 0) > 0
        )

        return {
            "total_devices": total_devices,
            "high_confidence_devices": high_confidence,
            "devices_with_conflicts": with_conflicts,
            "overall_quality_score": round(high_confidence / total_devices, 2) if total_devices else 0.0,
        }

    def write_canonical_model(self, output_file: str = "canonical_device_model.json") -> str:
        """Write merged specs to canonical model file."""
        output_path = self.output_dir / output_file
        merged = self.merge_all_devices()

        with open(output_path, 'w') as f:
            json.dump(merged, f, indent=2)

        logger.info(f"Wrote canonical model to {output_path}")
        return str(output_path)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge FPGA device specs from multiple sources"
    )
    parser.add_argument(
        "--datasheet",
        type=str,
        default="device_specs.json",
        help="Datasheet specs JSON (default: device_specs.json)"
    )
    parser.add_argument(
        "--f4pga",
        type=str,
        default=".f4pga_cache/devices.json",
        help="f4pga device database JSON (default: .f4pga_cache/devices.json)"
    )
    parser.add_argument(
        "--trellis",
        type=str,
        default="trellis_ecp5.json",
        help="Trellis ECP5 specs JSON (default: trellis_ecp5.json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="canonical_device_model.json",
        help="Output canonical model JSON (default: canonical_device_model.json)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "--download-f4pga",
        action="store_true",
        help="Download f4pga device database (stub for production)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize merger
    merger = DeviceSpecMerger(output_dir=args.output_dir)

    # Load specs
    merger.load_datasheet_specs(args.datasheet)
    merger.load_f4pga_specs(args.f4pga)
    merger.load_trellis_specs(args.trellis)

    if args.download_f4pga:
        merger.download_f4pga_db()

    # Merge and write
    output_file = merger.write_canonical_model(args.output)
    print(output_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
