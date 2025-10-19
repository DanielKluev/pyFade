"""
Test ImportController functionality.
"""
# pylint: disable=protected-access
import json
import pathlib
import tempfile
from unittest.mock import MagicMock

from py_fade.controllers.import_controller import ImportController, ImportSummary
from py_fade.data_formats.lm_eval_results import LMEvalResult


class TestImportController:
    """Tests for ImportController class."""

    def test_detect_format_lm_eval_results(self):
        """Test that detect_format correctly identifies lm_eval_results format."""
        controller = ImportController(MagicMock(), MagicMock())

        # Create temporary test file with lm_eval structure
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"results": {"gsm8k": {"exact_match": 0.75}}, "configs": {"gsm8k": {"task": "gsm8k"}}}, f)
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
            json.dump({"results": {"gsm8k": {"exact_match": 0.75}}, "configs": {"gsm8k": {"task": "gsm8k"}}}, f)
            f.flush()

            # Create matching samples file following the expected pattern
            # Pattern: samples_*{timestamp}.jsonl where timestamp comes from results_{timestamp}.json
            result_stem = pathlib.Path(f.name).stem  # e.g., "results_abc123"
            timestamp_part = result_stem.replace("results_", "")  # e.g., "abc123"
            # For simple case, use samples_{timestamp}.jsonl (subset name can be anything or omitted)
            sample_name = f"samples_{timestamp_part}.jsonl"
            samples_path = pathlib.Path(f.name).parent / sample_name
            with open(samples_path, 'w', encoding='utf-8') as samples_file:
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

    def test_set_group_path(self):
        """
        Test that set_group_path stores the group path.

        Flow:
        1. Create controller
        2. Set custom group path
        3. Verify path is stored

        Edge cases tested:
        - Custom path storage
        """
        controller = ImportController(MagicMock(), MagicMock())

        controller.set_group_path("custom_group")
        assert controller.group_path == "custom_group"

    def test_get_group_path_with_custom_path(self):
        """
        Test that _get_group_path returns custom path when set.

        Flow:
        1. Set custom group path
        2. Verify _get_group_path returns custom path

        Edge cases tested:
        - Custom path takes precedence over inference
        """
        controller = ImportController(MagicMock(), MagicMock())
        controller.set_group_path("my_custom_group")

        assert controller._get_group_path() == "my_custom_group"

    def test_get_group_path_infers_from_source_origin(self):
        """
        Test that _get_group_path infers from source origin name.

        Flow:
        1. Add source with origin name
        2. Verify _get_group_path uses origin name

        Edge cases tested:
        - Inference from source origin_name when custom path not set
        """
        controller = ImportController(MagicMock(), MagicMock())

        # Mock source with origin name
        mock_source = MagicMock()
        mock_source.origin_name = "gsm8k"
        controller.sources = [mock_source]

        assert controller._get_group_path() == "gsm8k"

    def test_get_group_path_fallback_to_filename(self):
        """
        Test that _get_group_path falls back to filename stem.

        Flow:
        1. Add source without origin name but with file path
        2. Verify _get_group_path uses filename stem

        Edge cases tested:
        - Fallback to filename when origin_name is None
        """
        controller = ImportController(MagicMock(), MagicMock())

        # Mock source without origin name but with result_json_path
        mock_source = MagicMock()
        mock_source.origin_name = None
        mock_source.result_json_path = MagicMock()
        mock_source.result_json_path.stem = "results_test_file"
        controller.sources = [mock_source]

        assert controller._get_group_path() == "results_test_file"

    def test_get_group_path_default_fallback(self):
        """
        Test that _get_group_path provides default fallback.

        Flow:
        1. Create controller with no sources
        2. Verify _get_group_path returns default "import"

        Edge cases tested:
        - Default fallback when no sources exist
        """
        controller = ImportController(MagicMock(), MagicMock())
        # No sources, should use default
        assert controller._get_group_path() == "import"

    def test_find_model_id_for_record_object_identity(self):
        """Test that _find_model_id_for_record uses object identity, not just prompt_hash matching."""
        controller = ImportController(MagicMock(), MagicMock())

        # Create mock sources with different model IDs
        source1 = MagicMock()
        source1.model_id = "model_a"
        record_a = MagicMock()
        record_a.prompt_hash = "hash123"
        source1.samples_by_hash = {"hash123": record_a}

        source2 = MagicMock()
        source2.model_id = "model_b"
        record_b = MagicMock()
        record_b.prompt_hash = "hash123"  # Same hash as record_a
        source2.samples_by_hash = {"hash123": record_b}

        controller.sources = [source1, source2]

        # Even though both records have the same hash, the method should use object identity
        assert controller._find_model_id_for_record(record_a) == "model_a"
        assert controller._find_model_id_for_record(record_b) == "model_b"

        # Test with a record that exists in neither source
        record_c = MagicMock()
        record_c.prompt_hash = "hash123"  # Same hash, different object
        assert controller._find_model_id_for_record(record_c) == "unknown"
