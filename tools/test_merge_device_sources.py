#!/usr/bin/env python3
"""
test_merge_device_sources.py — Unit tests for the device spec merger.

Tests cover:
  - Loading specs from multiple sources
  - Normalizing names and values
  - Conflict detection and resolution
  - Consistency validation
  - Routing inference
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from merge_device_sources import (
    DeviceSpecMerger,
    SpecValue,
    Confidence,
    SourceType,
)


class TestDeviceSpecMerger(unittest.TestCase):
    """Test suite for DeviceSpecMerger."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.merger = DeviceSpecMerger(output_dir=self.temp_dir.name)

    def tearDown(self):
        """Clean up."""
        self.temp_dir.cleanup()

    def test_normalize_device_name(self):
        """Test device name normalization."""
        assert self.merger.normalize_device_name("XCVU9P-FLGA2104-2L") == "xcvu9pflga21042l"
        assert self.merger.normalize_device_name("xcvu_9p flga 2104") == "xcvu9pflga2104"
        assert self.merger.normalize_device_name("LFE5U85F") == "lfe5u85f"

    def test_normalize_part_name(self):
        """Test part type normalization."""
        assert self.merger.normalize_part_name("CLB") == "CLB"
        assert self.merger.normalize_part_name("clb") == "CLB"
        assert self.merger.normalize_part_name("BRAM") == "BRAM"
        assert self.merger.normalize_part_name("bram") == "BRAM"
        assert self.merger.normalize_part_name("DSP48") == "DSP"
        assert self.merger.normalize_part_name("iob") == "IOB"

    def test_extract_numeric(self):
        """Test numeric extraction from strings."""
        assert self.merger.extract_numeric(100) == 100.0
        assert self.merger.extract_numeric("100") == 100.0
        assert self.merger.extract_numeric("182400 CLBs") == 182400.0
        assert self.merger.extract_numeric("~1.5M") == 1.5
        assert self.merger.extract_numeric("no number here") is None

    def test_compare_numeric_exact(self):
        """Test numeric comparison with exact match."""
        assert self.merger.compare_numeric(100, 100)
        assert self.merger.compare_numeric("100", "100")
        assert self.merger.compare_numeric(182400, "182400 CLBs")

    def test_compare_numeric_tolerance(self):
        """Test numeric comparison with tolerance."""
        assert self.merger.compare_numeric(100, 102, tolerance_pct=5.0)  # 2% diff
        assert not self.merger.compare_numeric(100, 110, tolerance_pct=5.0)  # 10% diff
        assert self.merger.compare_numeric(1000, 1030, tolerance_pct=5.0)  # 3% diff

    def test_compare_numeric_zero(self):
        """Test numeric comparison with zero."""
        assert self.merger.compare_numeric(0, 0)
        assert not self.merger.compare_numeric(0, 1)

    def test_load_datasheet_specs(self):
        """Test loading datasheet specs."""
        specs = {
            "source": "datasheet",
            "devices": {
                "test_device": {"parts": []}
            }
        }
        spec_file = Path(self.temp_dir.name) / "specs.json"
        with open(spec_file, 'w') as f:
            json.dump(specs, f)

        self.merger.load_datasheet_specs(str(spec_file))
        assert "test_device" in self.merger.datasheet_specs.get("devices", {})

    def test_load_nonexistent_file(self):
        """Test loading nonexistent file (should not crash)."""
        self.merger.load_datasheet_specs("/nonexistent/path.json")
        assert self.merger.datasheet_specs == {}

    def test_spec_value_to_dict(self):
        """Test SpecValue serialization."""
        spec = SpecValue(
            value=182400,
            source=SourceType.DATASHEET,
            confidence=Confidence.HIGH,
            notes="From datasheet table 3"
        )
        result = spec.to_dict()
        assert result["value"] == 182400
        assert result["source"] == "datasheet"
        assert result["confidence"] == "high"
        assert result["notes"] == "From datasheet table 3"

    def test_merge_parts_empty_sources(self):
        """Test merging parts with no sources."""
        parts = self.merger.merge_parts_list("nonexistent_device")
        assert parts == []

    def test_infer_routing_capacity(self):
        """Test routing capacity inference."""
        parts = [
            {
                "name": "CLB",
                "type": "CLB",
                "count": {"value": 182400, "source": "datasheet", "confidence": "high"},
            }
        ]
        routing = self.merger.infer_routing_capacity(parts)
        assert "local" in routing
        assert "regional" in routing
        # 182400 * 9 = 1,641,600 local
        assert routing["local"]["value"] == 1641600
        # 182400 * 13.7 ≈ 2,498,880 regional
        assert routing["regional"]["value"] == int(182400 * 13.7)

    def test_validate_consistency_complete(self):
        """Test consistency validation on complete spec."""
        parts = [
            {
                "name": "CLB",
                "type": "CLB",
                "count": {"value": 182400, "source": "datasheet", "confidence": "high"},
                "total_io": {"value": 9120000},
            },
            {
                "name": "IOB",
                "type": "IOB",
                "count": {"value": 2104, "source": "datasheet", "confidence": "high"},
                "total_io": {"value": 2104},
            },
            {
                "name": "BRAM",
                "type": "BRAM",
                "count": {"value": 912, "source": "datasheet", "confidence": "high"},
                "total_io": {"value": 933888},
            },
        ]
        routing = {
            "local": {"value": 1641600},
            "regional": {"value": 2500000},
        }
        score, issues = self.merger.validate_consistency("test", parts, routing)
        assert score > 0.7  # Should have decent score
        assert len(issues) < 3  # Should have few issues

    def test_validate_consistency_incomplete(self):
        """Test consistency validation on incomplete spec."""
        parts = [
            {
                "name": "CLB",
                "type": "CLB",
                "count": {"value": 182400, "source": "datasheet", "confidence": "high"},
                "total_io": {"value": 0},
            },
        ]
        routing = {}
        score, issues = self.merger.validate_consistency("test", parts, routing)
        assert score < 0.9  # Should penalize missing I/O
        assert any("I/O" in issue for issue in issues)

    def test_merge_device_no_sources(self):
        """Test merging device not in any source."""
        result = self.merger.merge_device("nonexistent")
        assert result == {}

    def test_merge_all_devices_empty(self):
        """Test merging all devices with no sources."""
        result = self.merger.merge_all_devices()
        assert result["schema_version"] == "1.0"
        assert result["source_summary"]["merged_devices"] == 0
        assert result["global_validation"]["total_devices"] == 0

    def test_round_trip_canonical_model(self):
        """Test writing and reading canonical model."""
        # Create minimal specs
        self.merger.datasheet_specs = {
            "devices": {
                "test_device": {
                    "parts": [
                        {
                            "name": "CLB",
                            "type": "CLB",
                            "count": 1000,
                            "io_per_unit": 50,
                        }
                    ]
                }
            }
        }

        output_path = self.merger.write_canonical_model("test_model.json")
        assert Path(output_path).exists()

        # Read back
        with open(output_path, 'r') as f:
            model = json.load(f)

        assert "schema_version" in model
        assert "devices" in model
        assert "generation_timestamp" in model

    def test_confidence_determination(self):
        """Test overall confidence determination."""
        # Single source, high consistency -> medium confidence
        conf = self.merger._determine_overall_confidence(
            ["datasheet"], 0.95
        )
        assert conf == "medium"

        # Two sources, high consistency -> high confidence
        conf = self.merger._determine_overall_confidence(
            ["datasheet", "f4pga"], 0.95
        )
        assert conf == "high"

        # Low consistency -> low confidence
        conf = self.merger._determine_overall_confidence(
            ["datasheet", "f4pga"], 0.5
        )
        assert conf == "low"

    def test_global_validation_report(self):
        """Test global validation report generation."""
        devices = {
            "dev1": {
                "validation": {
                    "confidence": "high",
                    "conflicts": 0,
                }
            },
            "dev2": {
                "validation": {
                    "confidence": "medium",
                    "conflicts": 2,
                }
            },
            "dev3": {
                "validation": {
                    "confidence": "low",
                    "conflicts": 5,
                }
            },
        }
        report = self.merger._global_validation_report(devices)
        assert report["total_devices"] == 3
        assert report["high_confidence_devices"] == 1
        assert report["devices_with_conflicts"] == 2
        assert report["overall_quality_score"] == round(1/3, 2)

    def test_conflict_logging(self):
        """Test conflict logging."""
        self.merger._log_conflict(
            "parts.DSP.count",
            {SourceType.DATASHEET: 3456, SourceType.F4PGA: 3480},
            3456,
            "warning"
        )
        assert len(self.merger.conflicts) == 1
        conflict = self.merger.conflicts[0]
        assert conflict.field == "parts.DSP.count"
        assert conflict.severity == "warning"


class TestIntegrationWithSampleData(unittest.TestCase):
    """Integration tests using sample data."""

    def setUp(self):
        """Set up test with sample data."""
        # Generate sample specs
        from generate_sample_device_specs import (
            generate_datasheet_specs,
            generate_f4pga_specs,
            generate_trellis_specs,
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        output_dir = Path(self.temp_dir.name)

        # Write sample specs
        datasheet = generate_datasheet_specs()
        with open(output_dir / "device_specs.json", 'w') as f:
            json.dump(datasheet, f)

        f4pga = generate_f4pga_specs()
        with open(output_dir / "f4pga_devices.json", 'w') as f:
            json.dump(f4pga, f)

        trellis = generate_trellis_specs()
        with open(output_dir / "trellis_ecp5.json", 'w') as f:
            json.dump(trellis, f)

        # Create merger
        self.merger = DeviceSpecMerger(output_dir=str(output_dir))
        self.merger.load_datasheet_specs(str(output_dir / "device_specs.json"))
        self.merger.load_f4pga_specs(str(output_dir / "f4pga_devices.json"))
        self.merger.load_trellis_specs(str(output_dir / "trellis_ecp5.json"))

    def tearDown(self):
        """Clean up."""
        self.temp_dir.cleanup()

    def test_merge_vcvu9p(self):
        """Test merging XCVU9P specs from multiple sources."""
        # Use normalized name from datasheet
        merged = self.merger.merge_device("xcvu9p-flga2104-2L")
        assert "device" in merged
        assert merged["device"]["name"] == "xcvu9p-flga2104-2L"
        assert len(merged["device"]["sources"]) >= 1
        assert "parts" in merged
        assert len(merged["parts"]) > 0

    def test_routing_inference_xcvu9p(self):
        """Test routing inference for XCVU9P."""
        merged = self.merger.merge_device("xcvu9p-flga2104-2L")
        assert "routing" in merged
        routing = merged["routing"]
        assert routing["local"]["value"] > 0
        assert routing["regional"]["value"] > 0

    def test_merge_all_devices_with_samples(self):
        """Test merging all sample devices."""
        result = self.merger.merge_all_devices()
        assert result["source_summary"]["merged_devices"] >= 2
        assert result["global_validation"]["total_devices"] >= 2

    def test_canonical_model_completeness(self):
        """Test canonical model has all required fields."""
        result = self.merger.merge_all_devices()
        assert "schema_version" in result
        assert "generation_timestamp" in result
        assert "source_summary" in result
        assert "devices" in result
        assert "global_validation" in result


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDeviceSpecMerger))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationWithSampleData))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
