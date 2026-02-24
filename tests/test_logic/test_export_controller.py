"""
Test export functionality with rating and logprob thresholds.

Tests the new export controller logic that applies facet thresholds during export.
"""

from __future__ import annotations

import hashlib
import json
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
from py_fade.providers.flat_prefix_template import FLAT_PREFIX_USER, FLAT_PREFIX_ASSISTANT, FLAT_PREFIX_SYSTEM
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
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=8, facet_min_logprob=-0.5,
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
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=5, facet_min_logprob=-1.0,
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
        facet, _prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=7)

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
        facet, _prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=5, facet_min_logprob=-0.6,
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
        facet, _prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=5)

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

    def test_export_controller_uses_target_model_id(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that ExportController uses the provided target_model_id for logprobs validation.
        """
        # Get mock model
        mapped_model = app_with_dataset.providers_manager.get_mock_model()

        # Create facet with sample
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=7, facet_min_logprob=-0.5,
                                                              facet_avg_logprob=-0.3)

        # Create completion with good logprobs for mock-echo-model
        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Test completion", mapped_model.model_id, facet, rating=8,
                                                   min_logprob=-0.4, avg_logprob=-0.2)

        # Create export template
        template = create_simple_export_template(temp_dataset, facet)

        # Export with target_model_id specified
        export_controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template,
                                                                  target_model_id=mapped_model.model_id)

        try:
            exported_count = export_controller.run_export()

            # Should successfully export with specified model
            assert exported_count == 1
            assert export_controller.target_model_id == mapped_model.model_id

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_controller_fallback_without_target_model(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that ExportController falls back to first available model when target_model_id is None.
        """
        # Get mock model
        mapped_model = app_with_dataset.providers_manager.get_mock_model()

        # Create facet with sample
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=7)

        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Test completion", mapped_model.model_id, facet, rating=8,
                                                   min_logprob=-0.4, avg_logprob=-0.2)

        # Create export template
        template = create_simple_export_template(temp_dataset, facet)

        # Export without target_model_id (should fall back)
        export_controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template, target_model_id=None)

        try:
            exported_count = export_controller.run_export()

            # Should successfully export with fallback model
            assert exported_count == 1
            # target_model_id should remain None (fallback is used internally)
            assert export_controller.target_model_id is None

        finally:
            temp_path.unlink(missing_ok=True)


class TestMultiTurnExport:
    """
    Tests that multi-turn conversations stored using flat prefix markers are
    correctly expanded into multiple turns when exported as SFT / ShareGPT JSONL.
    """

    def _create_sample_with_completion(self, dataset, facet, mapped_model, prompt_text: str, completion_text: str) -> PromptRevision:
        """
        Helper: create a sample with the given prompt_text, attach a rated completion, and commit to the database.
        """
        prompt_rev = PromptRevision.get_or_create(dataset, prompt_text, 2048, 512)
        Sample.create_if_unique(dataset, "Multi-Turn Sample", prompt_rev, "test_group")
        dataset.commit()

        sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()
        completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=mapped_model.model_id, temperature=0.7,
                                      top_k=40, completion_text=completion_text, tags={}, prefill=None, beam_token=None, is_truncated=False,
                                      context_length=2048, max_tokens=512)
        dataset.session.add(completion)
        dataset.commit()

        PromptCompletionRating.set_rating(dataset, completion, facet, 9)
        dataset.commit()

        alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())
        # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
        # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
        logprobs = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id=mapped_model.model_id,
                                            sampled_logprobs=None, sampled_logprobs_json=[], alternative_logprobs=None,
                                            alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=-0.3, avg_logprob=-0.2)
        # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
        dataset.session.add(logprobs)
        dataset.commit()

        return prompt_rev

    def test_multi_turn_prompt_exported_as_multiple_turns(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that a multi-turn prompt (containing <|user|>/<|assistant|> markers) is
        exported as multiple conversation turns, not as a single verbatim user message.
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet description", min_rating=7)
        temp_dataset.commit()

        # Build a two-turn prompt: first question + first answer + follow-up
        multi_turn_prompt = (f"{FLAT_PREFIX_USER} First question\n"
                             f"{FLAT_PREFIX_ASSISTANT} First answer\n"
                             f"{FLAT_PREFIX_USER} Follow-up question")
        completion_text = "Final answer"

        self._create_sample_with_completion(temp_dataset, facet, mapped_model, multi_turn_prompt, completion_text)

        template = create_simple_export_template(temp_dataset, facet)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            assert exported_count == 1

            # Parse the exported JSONL line
            with open(temp_path, encoding="utf-8") as fh:
                line = fh.readline()
            record = json.loads(line)

            # ShareGPT format stores conversations under "conversations" key
            conversations = record.get("conversations", [])

            # Expect four turns: user, assistant, user (from prompt) + assistant (completion)
            assert len(conversations) == 4, f"Expected 4 turns, got {len(conversations)}: {conversations}"

            assert conversations[0]["from"] == "human"
            assert conversations[0]["value"] == "First question"

            assert conversations[1]["from"] == "gpt"
            assert conversations[1]["value"] == "First answer"

            assert conversations[2]["from"] == "human"
            assert conversations[2]["value"] == "Follow-up question"

            assert conversations[3]["from"] == "gpt"
            assert conversations[3]["value"] == completion_text

        finally:
            temp_path.unlink(missing_ok=True)

    def test_single_turn_prompt_still_works(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that a plain single-turn prompt (no markers) is still exported correctly
        as a two-turn conversation (user prompt + assistant completion).
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet = Facet.create(temp_dataset, "Test Facet Single", "Single turn facet", min_rating=7)
        temp_dataset.commit()

        single_turn_prompt = "What is the capital of France?"
        completion_text = "The capital of France is Paris."

        self._create_sample_with_completion(temp_dataset, facet, mapped_model, single_turn_prompt, completion_text)

        template = create_simple_export_template(temp_dataset, facet, name="Single Turn Template")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            assert exported_count == 1

            with open(temp_path, encoding="utf-8") as fh:
                line = fh.readline()
            record = json.loads(line)

            conversations = record.get("conversations", [])

            # Expect exactly two turns: user question + assistant answer
            assert len(conversations) == 2, f"Expected 2 turns, got {len(conversations)}: {conversations}"

            assert conversations[0]["from"] == "human"
            assert conversations[0]["value"] == single_turn_prompt

            assert conversations[1]["from"] == "gpt"
            assert conversations[1]["value"] == completion_text

        finally:
            temp_path.unlink(missing_ok=True)

    def test_prompt_with_system_turn_exported_correctly(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that a prompt containing a system message plus user/assistant turns is
        exported with all turns including the system message.
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet = Facet.create(temp_dataset, "Test Facet System", "System turn facet", min_rating=7)
        temp_dataset.commit()

        multi_turn_prompt = (f"{FLAT_PREFIX_SYSTEM} You are a helpful assistant.\n"
                             f"{FLAT_PREFIX_USER} What is 2+2?")
        completion_text = "4"

        self._create_sample_with_completion(temp_dataset, facet, mapped_model, multi_turn_prompt, completion_text)

        template = create_simple_export_template(temp_dataset, facet, name="System Turn Template")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            assert exported_count == 1

            with open(temp_path, encoding="utf-8") as fh:
                line = fh.readline()
            record = json.loads(line)

            conversations = record.get("conversations", [])

            # Expect three turns: system, user, assistant
            assert len(conversations) == 3, f"Expected 3 turns, got {len(conversations)}: {conversations}"

            assert conversations[0]["from"] == "system"
            assert conversations[0]["value"] == "You are a helpful assistant."

            assert conversations[1]["from"] == "human"
            assert conversations[1]["value"] == "What is 2+2?"

            assert conversations[2]["from"] == "gpt"
            assert conversations[2]["value"] == completion_text

        finally:
            temp_path.unlink(missing_ok=True)

    def test_empty_prompt_recorded_as_failure_not_exception(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that a sample whose prompt text is empty or whitespace-only is recorded as
        a per-sample failure reason and does not abort the entire export run.
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet = Facet.create(temp_dataset, "Test Facet Empty", "Empty prompt facet", min_rating=7)
        temp_dataset.commit()

        # Create a bad sample with an empty prompt (whitespace only)
        self._create_sample_with_completion(temp_dataset, facet, mapped_model, "   ", "some completion")

        # Create a valid sample so the export doesn't raise "no eligible samples"
        self._create_sample_with_completion(temp_dataset, facet, mapped_model, "Valid prompt", "valid answer")

        template = create_simple_export_template(temp_dataset, facet, name="Empty Prompt Template")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController(app_with_dataset, temp_dataset, template)
            export_controller.set_output_path(temp_path)
            exported_count = export_controller.run_export()

            # Only the valid sample should be exported; the bad one is skipped with a failure reason
            assert exported_count == 1

            facet_summary = export_controller.export_results.facet_summaries[0]
            assert len(facet_summary.exported_samples) == 1
            assert len(facet_summary.failed_samples) == 1

            _failed_info, reasons = facet_summary.failed_samples[0]
            assert any("Failed to parse prompt text" in r for r in reasons)

        finally:
            temp_path.unlink(missing_ok=True)
