"""
Test export functionality with rating and logprob thresholds.

Tests the new export controller logic that applies facet thresholds during export.
"""

from __future__ import annotations

import hashlib
import pathlib
import tempfile
from typing import TYPE_CHECKING

import pytest

from py_fade.controllers.export_controller import ExportController
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.data_formats.base_data_classes import CompletionTopLogprobs

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


def create_test_completion_with_logprobs(dataset: "DatasetDatabase", prompt_rev: PromptRevision, completion_text: str, model_id: str,
                                         facet: Facet, rating: int, min_logprob: float, avg_logprob: float) -> PromptCompletion:
    """
    Create a test completion with rating and logprobs.
    """
    sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()

    completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=model_id, temperature=0.7, top_k=40,
                                  completion_text=completion_text, tags={}, prefill=None, beam_token=None, is_truncated=False,
                                  context_length=2048, max_tokens=512)
    dataset.session.add(completion)
    dataset.commit()

    # Add rating
    PromptCompletionRating.set_rating(dataset, completion, facet, rating)
    dataset.commit()

    # Add logprobs - construct manually
    alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())
    logprobs = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id=model_id, sampled_logprobs=None,
                                        sampled_logprobs_json=None, alternative_logprobs=None,
                                        alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=min_logprob, avg_logprob=avg_logprob)
    dataset.session.add(logprobs)
    dataset.commit()

    return completion


class TestExportWithThresholds:
    """
    Test export controller with rating and logprob threshold filtering.
    """

    def test_export_template_default_thresholds(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export template uses facet default thresholds when min_rating is None.
        """
        # Create facet with specific thresholds
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=8, min_logprob_threshold=-0.5,
                             avg_logprob_threshold=-0.3)
        temp_dataset.commit()

        # Create sample with completions
        prompt_rev = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
        sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "test_group")
        temp_dataset.commit()

        # Create completion with rating=8 (meets threshold) and good logprobs
        completion = create_test_completion_with_logprobs(temp_dataset, prompt_rev, "Good completion", "test-model", facet, rating=8,
                                                          min_logprob=-0.4, avg_logprob=-0.2)

        # Create template with None for thresholds (should use facet defaults)
        template = ExportTemplate.create(
            temp_dataset,
            name="Test Template",
            description="Test template",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
                "min_rating": None,  # Should use facet.min_rating = 8
                "min_logprob": None,  # Should use facet.min_logprob_threshold = -0.5
                "avg_logprob": None,  # Should use facet.avg_logprob_threshold = -0.3
            }])
        temp_dataset.commit()

        # Export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            # Should export 1 sample since it meets all thresholds
            assert exported_count == 1
            assert export_controller.export_results is not None
            assert export_controller.export_results.total_exported == 1

            # Check facet summary
            assert len(export_controller.export_results.facet_summaries) == 1
            facet_summary = export_controller.export_results.facet_summaries[0]
            assert facet_summary.facet_name == "Test Facet"
            assert len(facet_summary.exported_samples) == 1
            assert len(facet_summary.failed_samples) == 0

            # Check exported sample info
            exported_sample = facet_summary.exported_samples[0]
            assert exported_sample.sample_title == "Test Sample"
            assert exported_sample.group_path == "test_group"

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_template_override_thresholds(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export template can override facet thresholds with specific values.
        """
        # Create facet with lenient thresholds
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=5, min_logprob_threshold=-1.0,
                             avg_logprob_threshold=-0.5)
        temp_dataset.commit()

        # Create sample with completions
        prompt_rev = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
        sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_rev, "test_group")
        temp_dataset.commit()

        # Create completion with rating=6 (meets facet threshold but not override)
        completion = PromptCompletion.create(temp_dataset, prompt_revision=prompt_rev, completion_text="Medium completion",
                                             model_id="test-model")
        temp_dataset.commit()

        # Add rating
        PromptCompletionRating.create(temp_dataset, completion, facet, 6, "")
        temp_dataset.commit()

        # Add logprobs
        PromptCompletionLogprobs.create(temp_dataset, completion, model_id="test-model", min_logprob=-0.8, avg_logprob=-0.4,
                                        sum_logprob=-1.0)
        temp_dataset.commit()

        # Create template with stricter override thresholds
        template = ExportTemplate.create(
            temp_dataset,
            name="Test Template",
            description="Test template",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
                "min_rating": 8,  # Override: stricter than facet's 5
                "min_logprob": -0.3,  # Override: stricter than facet's -1.0
                "avg_logprob": -0.2,  # Override: stricter than facet's -0.5
            }])
        temp_dataset.commit()

        # Export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)

            # Should fail because rating 6 < override threshold 8
            with pytest.raises(ValueError, match="No eligible samples found for export"):
                export_controller.run_export()

            # Check that export results show the failure
            assert export_controller.export_results is not None
            assert len(export_controller.export_results.facet_summaries) == 1
            facet_summary = export_controller.export_results.facet_summaries[0]
            assert len(facet_summary.exported_samples) == 0
            assert len(facet_summary.failed_samples) == 1

            # Check failure reason
            failed_sample, reasons = facet_summary.failed_samples[0]
            assert failed_sample.sample_title == "Test Sample"
            assert any("rating >= 8" in reason for reason in reasons)

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_filters_by_rating_threshold(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export correctly filters samples based on rating threshold.
        """
        # Create facet
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=7)
        temp_dataset.commit()

        # Create multiple samples with different ratings
        samples_data = [
            ("Sample High Rating", 9, True),  # Should be exported
            ("Sample Low Rating", 5, False),  # Should be filtered
            ("Sample Medium Rating", 7, True),  # Should be exported (meets threshold)
        ]

        for title, rating_value, _ in samples_data:
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Prompt for {title}")
            sample = Sample.create_if_unique(temp_dataset, title, prompt_rev, "test_group")
            temp_dataset.commit()

            completion = PromptCompletion.create(temp_dataset, prompt_revision=prompt_rev, completion_text=f"Completion for {title}",
                                                 model_id="test-model")
            temp_dataset.commit()

            PromptCompletionRating.create(temp_dataset, completion, facet, rating_value, "")
            temp_dataset.commit()

            # Add logprobs that pass thresholds
            PromptCompletionLogprobs.create(temp_dataset, completion, model_id="test-model", min_logprob=-0.5, avg_logprob=-0.3,
                                            sum_logprob=-1.0)
            temp_dataset.commit()

        # Create template
        template = ExportTemplate.create(
            temp_dataset,
            name="Test Template",
            description="Test template",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
                "min_rating": None,  # Use facet default (7)
                "min_logprob": None,
                "avg_logprob": None,
            }])
        temp_dataset.commit()

        # Export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            # Should export 2 samples (rating 9 and 7)
            assert exported_count == 2
            assert export_controller.export_results.total_exported == 2

            # Check facet summary
            facet_summary = export_controller.export_results.facet_summaries[0]
            assert len(facet_summary.exported_samples) == 2
            assert len(facet_summary.failed_samples) == 1

            # Verify which samples were exported
            exported_titles = {s.sample_title for s in facet_summary.exported_samples}
            assert "Sample High Rating" in exported_titles
            assert "Sample Medium Rating" in exported_titles

            # Verify which sample failed
            failed_sample, reasons = facet_summary.failed_samples[0]
            assert failed_sample.sample_title == "Sample Low Rating"
            assert any("rating >= 7" in reason for reason in reasons)

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_filters_by_logprob_thresholds(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export correctly filters samples based on logprob thresholds.
        """
        # Create facet
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=5, min_logprob_threshold=-0.6,
                             avg_logprob_threshold=-0.4)
        temp_dataset.commit()

        # Create samples with different logprobs
        samples_data = [
            ("Sample Good Logprobs", -0.5, -0.3, True),  # Should be exported
            ("Sample Bad Min Logprob", -0.8, -0.3, False),  # Should be filtered (min too low)
            ("Sample Bad Avg Logprob", -0.5, -0.5, False),  # Should be filtered (avg too low)
        ]

        for title, min_lp, avg_lp, _ in samples_data:
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Prompt for {title}")
            sample = Sample.create_if_unique(temp_dataset, title, prompt_rev, "test_group")
            temp_dataset.commit()

            completion = PromptCompletion.create(temp_dataset, prompt_revision=prompt_rev, completion_text=f"Completion for {title}",
                                                 model_id="test-model")
            temp_dataset.commit()

            # All have good ratings
            PromptCompletionRating.create(temp_dataset, completion, facet, 8, "")
            temp_dataset.commit()

            # Different logprobs
            PromptCompletionLogprobs.create(temp_dataset, completion, model_id="test-model", min_logprob=min_lp, avg_logprob=avg_lp,
                                            sum_logprob=-1.0)
            temp_dataset.commit()

        # Create template
        template = ExportTemplate.create(
            temp_dataset,
            name="Test Template",
            description="Test template",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
                "min_rating": None,
                "min_logprob": None,  # Use facet default (-0.6)
                "avg_logprob": None,  # Use facet default (-0.4)
            }])
        temp_dataset.commit()

        # Export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            # Should export 1 sample (only the one with good logprobs)
            assert exported_count == 1
            assert export_controller.export_results.total_exported == 1

            # Check facet summary
            facet_summary = export_controller.export_results.facet_summaries[0]
            assert len(facet_summary.exported_samples) == 1
            assert len(facet_summary.failed_samples) == 2

            # Verify which sample was exported
            exported_sample = facet_summary.exported_samples[0]
            assert exported_sample.sample_title == "Sample Good Logprobs"

            # Verify failure reasons for bad samples
            failed_titles = {s[0].sample_title: s[1] for s in facet_summary.failed_samples}
            assert "Sample Bad Min Logprob" in failed_titles
            assert "Sample Bad Avg Logprob" in failed_titles

            # Check specific failure reasons
            for sample_info, reasons in facet_summary.failed_samples:
                if sample_info.sample_title == "Sample Bad Min Logprob":
                    assert any("min_logprob" in reason and "-0.6" in reason for reason in reasons)
                elif sample_info.sample_title == "Sample Bad Avg Logprob":
                    assert any("avg_logprob" in reason and "-0.4" in reason for reason in reasons)

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_with_percentage_limit(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export respects percentage limit configuration.
        """
        # Create facet
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=5)
        temp_dataset.commit()

        # Create 10 samples, all meeting thresholds
        for i in range(10):
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Prompt {i}")
            sample = Sample.create_if_unique(temp_dataset, f"Sample {i}", prompt_rev, "test_group")
            temp_dataset.commit()

            completion = PromptCompletion.create(temp_dataset, prompt_revision=prompt_rev, completion_text=f"Completion {i}",
                                                 model_id="test-model")
            temp_dataset.commit()

            PromptCompletionRating.create(temp_dataset, completion, facet, 8, "")
            temp_dataset.commit()

            PromptCompletionLogprobs.create(temp_dataset, completion, model_id="test-model", min_logprob=-0.5, avg_logprob=-0.3,
                                            sum_logprob=-1.0)
            temp_dataset.commit()

        # Create template with 50% limit
        template = ExportTemplate.create(
            temp_dataset,
            name="Test Template",
            description="Test template",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 50,  # Only 50% = 5 samples
                "order": "random",
                "min_rating": None,
                "min_logprob": None,
                "avg_logprob": None,
            }])
        temp_dataset.commit()

        # Export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            # Should export exactly 5 samples (50% of 10)
            assert exported_count == 5
            assert export_controller.export_results.total_exported == 5

            # Check facet summary
            facet_summary = export_controller.export_results.facet_summaries[0]
            assert len(facet_summary.exported_samples) == 5
            # The other 5 are not failed, just not selected due to limit
            # They won't appear in failed_samples list

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_with_count_limit(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export respects count limit configuration.
        """
        # Create facet
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=5)
        temp_dataset.commit()

        mapped_model = app_with_dataset.providers_manager.get_mock_model()

        # Create 10 samples, all meeting thresholds
        for i in range(10):
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Prompt {i}")
            sample = Sample.create_if_unique(temp_dataset, f"Sample {i}", prompt_rev, "test_group")
            temp_dataset.commit()

            completion = PromptCompletion.create(temp_dataset, prompt_revision=prompt_rev, completion_text=f"Completion {i}",
                                                 model_id=mapped_model.model_id)
            temp_dataset.commit()

            PromptCompletionRating.create(temp_dataset, completion, facet, 8, "")
            temp_dataset.commit()

            PromptCompletionLogprobs.create(temp_dataset, completion, model_id=mapped_model.model_id, min_logprob=-0.5, avg_logprob=-0.3,
                                            sum_logprob=-1.0)
            temp_dataset.commit()

        # Create template with count limit of 3
        template = ExportTemplate.create(
            temp_dataset,
            name="Test Template",
            description="Test template",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "count",
                "limit_value": 3,  # Only 3 samples
                "order": "random",
                "min_rating": None,
                "min_logprob": None,
                "avg_logprob": None,
            }])
        temp_dataset.commit()

        # Export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            # Should export exactly 3 samples
            assert exported_count == 3
            assert export_controller.export_results.total_exported == 3

            # Check facet summary
            facet_summary = export_controller.export_results.facet_summaries[0]
            assert len(facet_summary.exported_samples) == 3

        finally:
            temp_path.unlink(missing_ok=True)
