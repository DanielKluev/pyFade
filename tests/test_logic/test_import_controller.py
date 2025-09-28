"""
Test ImportController functionality.
"""
import json
import pathlib
import tempfile
from unittest.mock import MagicMock

import pytest

from py_fade.controllers.import_controller import ImportController, ImportSummary
from py_fade.data_formats.lm_eval_results import LMEvalResult


class TestImportController:
    """Tests for ImportController class."""

    def test_detect_format_lm_eval_results(self):
        """Test that detect_format correctly identifies lm_eval_results format."""
        controller = ImportController(MagicMock(), MagicMock())
        
        # Create temporary test file with lm_eval structure
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "results": {"gsm8k": {"exact_match": 0.75}},
                "configs": {"gsm8k": {"task": "gsm8k"}}
            }, f)
            f.flush()
            
            result = controller.detect_format(pathlib.Path(f.name))
            assert result == "lm_eval_results"
            
        # Clean up
        pathlib.Path(f.name).unlink()

    def test_detect_format_unknown(self):
        """Test that detect_format returns None for unknown formats."""
        controller = ImportController(MagicMock(), MagicMock())
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"unknown": "format"}, f)
            f.flush()
            
            result = controller.detect_format(pathlib.Path(f.name))
            assert result is None
            
        # Clean up
        pathlib.Path(f.name).unlink()

    def test_import_summary_dataclass(self):
        """Test ImportSummary dataclass has correct default values."""
        summary = ImportSummary()
        assert summary.imported_samples == 0
        assert summary.imported_completions == 0
        
        summary = ImportSummary(imported_samples=5, imported_completions=10)
        assert summary.imported_samples == 5
        assert summary.imported_completions == 10

    def test_add_source_returns_parser(self):
        """Test that add_source returns the parser instance."""
        controller = ImportController(MagicMock(), MagicMock())
        
        # Create temporary test file with proper results_ naming
        with tempfile.NamedTemporaryFile(mode='w', prefix='results_', suffix='.json', delete=False) as f:
            json.dump({
                "results": {"gsm8k": {"exact_match": 0.75}},
                "configs": {"gsm8k": {"task": "gsm8k"}}
            }, f)
            f.flush()
            
            # Create matching samples file following the expected pattern
            result_stem = pathlib.Path(f.name).stem  # e.g., "results_abc123"
            sample_name = result_stem.replace("results_", "") + ".jsonl"  # e.g., "abc123.jsonl"
            samples_path = pathlib.Path(f.name).parent / sample_name
            with open(samples_path, 'w') as samples_file:
                json.dump({"prompt_hash": "test", "doc": {"question": "test"}, "target": "test"}, samples_file)
            
            parser = controller.add_source(pathlib.Path(f.name))
            assert isinstance(parser, LMEvalResult)
            assert len(controller.sources) == 1
            
        # Clean up
        pathlib.Path(f.name).unlink()
        samples_path.unlink()

    def test_total_active_records_initial_zero(self):
        """Test that total_active_records initially returns 0."""
        controller = ImportController(MagicMock(), MagicMock())
        assert controller.total_active_records() == 0

    def test_add_filter_stores_configuration(self):
        """Test that add_filter stores the filter configuration."""
        controller = ImportController(MagicMock(), MagicMock())
        
        config = {"filter_type": "new_failure", "set_facet_pairwise_ranking": True}
        controller.add_filter("paired_comparison", config)
        
        assert len(controller.filters) == 1
        assert controller.filters[0]["type"] == "paired_comparison"
        assert controller.filters[0]["config"] == config