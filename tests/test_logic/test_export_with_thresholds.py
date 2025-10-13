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
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.data_formats.base_data_classes import CompletionTopLogprobs
from tests.helpers.data_helpers import create_completion_with_rating_and_logprobs
from tests.helpers.export_wizard_helpers import setup_facet_sample_and_completion, create_and_run_export_test, create_simple_export_template

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


class TestExportWithThresholds:
    """
    Test export controller with rating and logprob threshold filtering.
    """

    def test_export_template_default_thresholds(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export template uses facet default thresholds when min_rating is None.
        """
        # Get mock model for proper model_id
        mapped_model = app_with_dataset.providers_manager.get_mock_model()

        # Create facet with sample
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, app_with_dataset, facet_min_rating=8, facet_min_logprob=-0.5,
                                                              facet_avg_logprob=-0.3)

        # Create completion with rating=8 (meets threshold) and good logprobs
        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Good completion", mapped_model.model_id, facet, rating=8,
                                                   min_logprob=-0.4, avg_logprob=-0.2)

        # Create template with None for thresholds (should use facet defaults)
        template = create_simple_export_template(temp_dataset, facet)

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
        # Get mock model for proper model_id
        mapped_model = app_with_dataset.providers_manager.get_mock_model()

        # Create facet with lenient thresholds and sample
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, app_with_dataset, facet_min_rating=5, facet_min_logprob=-1.0,
                                                              facet_avg_logprob=-0.5)

        # Create completion with rating=6 (meets facet threshold but not override)
        sha256 = hashlib.sha256("Medium completion".encode("utf-8")).hexdigest()
        completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=mapped_model.model_id, temperature=0.7,
                                      top_k=40, completion_text="Medium completion", tags={}, prefill=None, beam_token=None,
                                      is_truncated=False, context_length=2048, max_tokens=512)
        temp_dataset.session.add(completion)
        temp_dataset.commit()

        # Add rating
        PromptCompletionRating.set_rating(temp_dataset, completion, facet, 6)
        temp_dataset.commit()

        # Add logprobs
        alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())
        # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
        # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
        logprobs = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id=mapped_model.model_id,
                                            sampled_logprobs=None, sampled_logprobs_json=[], alternative_logprobs=None,
                                            alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=-0.8, avg_logprob=-0.4)
        # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
        temp_dataset.session.add(logprobs)
        temp_dataset.commit()

        # Create template with stricter override thresholds
        template = create_simple_export_template(temp_dataset, facet, min_rating=8, min_logprob=-0.3, avg_logprob=-0.2)

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
        # Get mock model for proper model_id
        mapped_model = app_with_dataset.providers_manager.get_mock_model()

        # Create facet
        facet, _prompt_rev = setup_facet_sample_and_completion(temp_dataset, app_with_dataset, facet_min_rating=7)

        # Create multiple samples with different ratings
        samples_data = [
            ("Sample High Rating", 9, True),  # Should be exported
            ("Sample Low Rating", 5, False),  # Should be filtered
            ("Sample Medium Rating", 7, True),  # Should be exported (meets threshold)
        ]

        for title, rating_value, _ in samples_data:
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Prompt for {title}", 2048, 512)
            Sample.create_if_unique(temp_dataset, title, prompt_rev, "test_group")
            temp_dataset.commit()

            sha256 = hashlib.sha256(f"Completion for {title}".encode("utf-8")).hexdigest()
            completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=mapped_model.model_id, temperature=0.7,
                                          top_k=40, completion_text=f"Completion for {title}", tags={}, prefill=None, beam_token=None,
                                          is_truncated=False, context_length=2048, max_tokens=512)
            temp_dataset.session.add(completion)
            temp_dataset.commit()

            PromptCompletionRating.set_rating(temp_dataset, completion, facet, rating_value)
            temp_dataset.commit()

            # Add logprobs that pass thresholds
            alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())
            # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
            # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
            logprobs = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id=mapped_model.model_id,
                                                sampled_logprobs=None, sampled_logprobs_json=[], alternative_logprobs=None,
                                                alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=-0.5, avg_logprob=-0.3)
            # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
            temp_dataset.session.add(logprobs)
            temp_dataset.commit()

        # Create template
        template = create_simple_export_template(temp_dataset, facet)

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
        # Get mock model for proper model_id
        mapped_model = app_with_dataset.providers_manager.get_mock_model()

        # Create facet
        facet, _prompt_rev = setup_facet_sample_and_completion(temp_dataset, app_with_dataset, facet_min_rating=5, facet_min_logprob=-0.6,
                                                               facet_avg_logprob=-0.4)

        # Create samples with different logprobs
        samples_data = [
            ("Sample Good Logprobs", -0.5, -0.3, True),  # Should be exported
            ("Sample Bad Min Logprob", -0.8, -0.3, False),  # Should be filtered (min too low)
            ("Sample Bad Avg Logprob", -0.5, -0.5, False),  # Should be filtered (avg too low)
        ]

        for title, min_lp, avg_lp, _ in samples_data:
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Prompt for {title}", 2048, 512)
            Sample.create_if_unique(temp_dataset, title, prompt_rev, "test_group")
            temp_dataset.commit()

            sha256 = hashlib.sha256(f"Completion for {title}".encode("utf-8")).hexdigest()
            completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=mapped_model.model_id, temperature=0.7,
                                          top_k=40, completion_text=f"Completion for {title}", tags={}, prefill=None, beam_token=None,
                                          is_truncated=False, context_length=2048, max_tokens=512)
            temp_dataset.session.add(completion)
            temp_dataset.commit()

            # All have good ratings
            PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)
            temp_dataset.commit()

            # Different logprobs
            alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())
            # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
            # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
            logprobs = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id=mapped_model.model_id,
                                                sampled_logprobs=None, sampled_logprobs_json=[], alternative_logprobs=None,
                                                alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=min_lp, avg_logprob=avg_lp)
            # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
            temp_dataset.session.add(logprobs)
            temp_dataset.commit()

        # Create template
        template = create_simple_export_template(temp_dataset, facet)

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
        # Get mock model for proper model_id
        mapped_model = app_with_dataset.providers_manager.get_mock_model()

        # Create facet
        facet, _prompt_rev = setup_facet_sample_and_completion(temp_dataset, app_with_dataset, facet_min_rating=5)

        # Create 10 samples, all meeting thresholds
        for i in range(10):
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Prompt {i}", 2048, 512)
            Sample.create_if_unique(temp_dataset, f"Sample {i}", prompt_rev, "test_group")
            temp_dataset.commit()

            sha256 = hashlib.sha256(f"Completion {i}".encode("utf-8")).hexdigest()
            completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=mapped_model.model_id, temperature=0.7,
                                          top_k=40, completion_text=f"Completion {i}", tags={}, prefill=None, beam_token=None,
                                          is_truncated=False, context_length=2048, max_tokens=512)
            temp_dataset.session.add(completion)
            temp_dataset.commit()

            PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)
            temp_dataset.commit()

            alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())
            # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
            # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
            logprobs = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id=mapped_model.model_id,
                                                sampled_logprobs=None, sampled_logprobs_json=[], alternative_logprobs=None,
                                                alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=-0.5, avg_logprob=-0.3)
            # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
            temp_dataset.session.add(logprobs)
            temp_dataset.commit()

        # Create template with 50% limit
        template = create_simple_export_template(temp_dataset, facet, limit_type="percentage", limit_value=50)

        # Export
        export_controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template)

        try:
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
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Prompt {i}", 2048, 512)
            Sample.create_if_unique(temp_dataset, f"Sample {i}", prompt_rev, "test_group")
            temp_dataset.commit()

            # Use shared helper to create completion with rating and logprobs
            create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, f"Completion {i}", mapped_model.model_id, facet, rating=8,
                                                       min_logprob=-0.5, avg_logprob=-0.3)

        # Create template with count limit of 3
        template = create_simple_export_template(temp_dataset, facet, limit_type="count", limit_value=3)

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
