"""
Test module for FacetSummaryController.
"""
from __future__ import annotations

import datetime
import pytest

from py_fade.controllers.facet_summary_controller import FacetSummaryController
from py_fade.data_formats.base_data_classes import CompletionTopLogprobs
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from tests.helpers.data_helpers import create_test_single_position_token


def create_test_sample(temp_dataset, title="Test Sample", notes="Test sample", prompt_text="Test prompt"):
    """
    Helper to create a sample with a prompt revision for testing.
    """
    sample = Sample(title=title, notes=notes, date_created=datetime.datetime.now())
    temp_dataset.session.add(sample)
    prompt = PromptRevision.new_from_text(prompt_text, context_length=2048, max_tokens=100)
    temp_dataset.session.add(prompt)
    sample.prompt_revision = prompt
    temp_dataset.session.flush()
    return sample, prompt


def create_test_logprobs(temp_dataset, completion_id: int, model_id: str, min_logprob: float, avg_logprob: float):
    """
    Helper to create test logprobs for a completion.
    """
    # Create simple sampled logprobs
    sampled_logprobs_list = [
        create_test_single_position_token("Test", min_logprob).to_dict(),
        create_test_single_position_token(" completion", avg_logprob).to_dict()
    ]

    # Create empty alternative logprobs for simplicity
    alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())

    # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
    # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
    logprobs = PromptCompletionLogprobs(
        prompt_completion_id=completion_id,
        logprobs_model_id=model_id,
        sampled_logprobs=None,
        sampled_logprobs_json=sampled_logprobs_list,
        alternative_logprobs=None,
        alternative_logprobs_bin=alternative_logprobs_bin,
        min_logprob=min_logprob,
        avg_logprob=avg_logprob,
    )
    # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
    temp_dataset.session.add(logprobs)
    return logprobs


def test_empty_facet_report(app_with_dataset, temp_dataset):
    """
    Test generating report for facet with no samples.
    """
    facet = Facet.create(temp_dataset, "Empty Facet", "No samples")
    temp_dataset.commit()

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, "test-model")
    report = controller.generate_report()

    assert report.facet_name == "Empty Facet"
    assert report.target_model_id == "test-model"
    assert report.sft_total_samples == 0
    assert report.sft_finished_samples == 0
    assert report.sft_unfinished_samples == 0
    assert report.dpo_total_samples == 0
    assert report.dpo_finished_samples == 0
    assert report.dpo_unfinished_samples == 0


def test_sample_with_no_ratings(app_with_dataset, temp_dataset):
    """
    Test sample without any completion ratings.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description")
    temp_dataset.commit()

    # Create sample with completion but no rating
    _, prompt = create_test_sample(temp_dataset)
    completion = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, "test-model")
    report = controller.generate_report()

    # Sample has no ratings, so it shouldn't appear in the report
    assert report.sft_total_samples == 0
    assert report.dpo_total_samples == 0


def test_sample_with_low_rating(app_with_dataset, temp_dataset):
    """
    Test sample with completion rating below threshold.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7)
    temp_dataset.commit()

    # Create sample with low-rated completion
    _, prompt = create_test_sample(temp_dataset)
    completion = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="b" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    # Add low rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 5)

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, "test-model")
    report = controller.generate_report()

    assert report.sft_total_samples == 1
    assert report.sft_finished_samples == 0
    assert report.sft_unfinished_samples == 1
    assert len(report.sft_unfinished_details) == 1
    assert "rating >= 7" in report.sft_unfinished_details[0].reasons[0]

    assert report.dpo_total_samples == 1
    assert report.dpo_finished_samples == 0
    assert report.dpo_unfinished_samples == 1


def test_sample_with_high_rating_no_logprobs(app_with_dataset, temp_dataset):
    """
    Test sample with high rating but no logprobs for target model.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7)
    temp_dataset.commit()

    # Create sample with high-rated completion but no logprobs
    _, prompt = create_test_sample(temp_dataset)
    completion = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="c" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    # Add high rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, "test-model")
    report = controller.generate_report()

    assert report.sft_total_samples == 1
    assert report.sft_finished_samples == 0
    assert report.sft_unfinished_samples == 1
    assert len(report.sft_unfinished_details) == 1
    assert "No logprobs for target model" in report.sft_unfinished_details[0].reasons[1]


def test_sample_with_high_rating_bad_logprobs(app_with_dataset, temp_dataset):
    """
    Test sample with high rating but logprobs below threshold.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-1.0,
                         avg_logprob_threshold=-0.4)
    temp_dataset.commit()

    # Create sample with high-rated completion but bad logprobs
    _, prompt = create_test_sample(temp_dataset)
    completion = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="d" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    # Add high rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    # Add logprobs that don't meet thresholds
    create_test_logprobs(temp_dataset, completion.id, "test-model", min_logprob=-2.0, avg_logprob=-1.75)
    temp_dataset.commit()

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, "test-model")
    report = controller.generate_report()

    assert report.sft_total_samples == 1
    assert report.sft_finished_samples == 0
    assert report.sft_unfinished_samples == 1
    assert len(report.sft_unfinished_details) == 1
    # Check that the failure reasons mention the threshold violations
    reasons_text = " ".join(report.sft_unfinished_details[0].reasons)
    assert "min_logprob" in reasons_text or "avg_logprob" in reasons_text


def test_sample_ready_for_sft(app_with_dataset, temp_dataset):
    """
    Test sample that is ready for SFT training.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-1.0,
                         avg_logprob_threshold=-0.4)
    temp_dataset.commit()

    # Create sample with high-rated completion and good logprobs
    _, prompt = create_test_sample(temp_dataset)
    completion = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="e" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    # Add high rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    # Add good logprobs
    create_test_logprobs(temp_dataset, completion.id, "test-model", min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, "test-model")
    report = controller.generate_report()

    assert report.sft_total_samples == 1
    assert report.sft_finished_samples == 1
    assert report.sft_unfinished_samples == 0
    assert len(report.sft_unfinished_details) == 0
    assert report.sft_total_loss == pytest.approx(0.15, abs=0.01)


def test_sample_ready_for_dpo(app_with_dataset, temp_dataset):
    """
    Test sample that is ready for DPO training.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-1.0,
                         avg_logprob_threshold=-0.4)
    temp_dataset.commit()

    # Create sample with two completions: one high-rated with good logprobs, one low-rated
    _, prompt = create_test_sample(temp_dataset)

    # High-rated completion
    completion1 = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="f" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Good completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion1)
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)

    create_test_logprobs(temp_dataset, completion1.id, "test-model", min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    # Low-rated completion (for rejected in DPO)
    completion2 = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="g" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Bad completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion2)
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 4)

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, "test-model")
    report = controller.generate_report()

    assert report.dpo_total_samples == 1
    assert report.dpo_finished_samples == 1
    assert report.dpo_unfinished_samples == 0
    assert len(report.dpo_unfinished_details) == 0
    assert report.dpo_total_loss == pytest.approx(0.15, abs=0.01)


def test_sample_ready_for_sft_not_dpo(app_with_dataset, temp_dataset):
    """
    Test sample ready for SFT but not DPO (only one completion).
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-1.0,
                         avg_logprob_threshold=-0.4)
    temp_dataset.commit()

    # Create sample with one high-rated completion
    _, prompt = create_test_sample(temp_dataset)
    completion = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="h" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Good completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion)
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 9)

    create_test_logprobs(temp_dataset, completion.id, "test-model", min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, "test-model")
    report = controller.generate_report()

    # Should be ready for SFT
    assert report.sft_total_samples == 1
    assert report.sft_finished_samples == 1
    assert report.sft_unfinished_samples == 0

    # Should NOT be ready for DPO (no rejected completion)
    assert report.dpo_total_samples == 1
    assert report.dpo_finished_samples == 0
    assert report.dpo_unfinished_samples == 1
    assert "No completion with rating < 9" in report.dpo_unfinished_details[0].reasons[0]
