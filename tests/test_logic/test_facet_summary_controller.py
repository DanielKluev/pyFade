"""
Test module for FacetSummaryController.
"""
from __future__ import annotations

import pytest

from py_fade.controllers.facet_summary_controller import FacetSummaryController
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from tests.helpers.data_helpers import create_test_sample, create_test_logprobs, create_test_completion_with_params


def test_empty_facet_report(app_with_dataset, temp_dataset):
    """
    Test generating report for facet with no samples.
    """
    facet = Facet.create(temp_dataset, "Empty Facet", "No samples")
    temp_dataset.commit()

    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, mapped_model)
    report = controller.generate_report()

    assert report.facet_name == "Empty Facet"
    assert report.target_model_id == mapped_model.model_id
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
    create_test_completion_with_params(temp_dataset, prompt)
    temp_dataset.commit()

    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, mapped_model)
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
    completion = create_test_completion_with_params(temp_dataset, prompt, sha256="b" * 64)
    temp_dataset.commit()

    # Add low rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 5)

    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, mapped_model)
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
    completion = create_test_completion_with_params(temp_dataset, prompt, sha256="c" * 64)
    temp_dataset.commit()

    # Add high rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, mapped_model)
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

    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with high-rated completion but bad logprobs
    _, prompt = create_test_sample(temp_dataset)
    completion = create_test_completion_with_params(temp_dataset, prompt, sha256="d" * 64)
    temp_dataset.commit()

    # Add high rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    # Add logprobs that don't meet thresholds
    create_test_logprobs(temp_dataset, completion.id, mapped_model.model_id, min_logprob=-2.0, avg_logprob=-1.75)
    temp_dataset.commit()

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, mapped_model)
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

    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with high-rated completion and good logprobs
    _, prompt = create_test_sample(temp_dataset)
    completion = create_test_completion_with_params(temp_dataset, prompt, sha256="e" * 64)
    temp_dataset.commit()

    # Add high rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    # Add good logprobs
    create_test_logprobs(temp_dataset, completion.id, mapped_model.model_id, min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, mapped_model)
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

    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with two completions: one high-rated with good logprobs, one low-rated
    _, prompt = create_test_sample(temp_dataset)

    # High-rated completion
    completion1 = create_test_completion_with_params(temp_dataset, prompt, sha256="f" * 64, completion_text="Good completion")
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)

    create_test_logprobs(temp_dataset, completion1.id, mapped_model.model_id, min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    # Low-rated completion (for rejected in DPO)
    completion2 = create_test_completion_with_params(temp_dataset, prompt, sha256="g" * 64, completion_text="Bad completion")
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 4)

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, mapped_model)
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

    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with one high-rated completion
    _, prompt = create_test_sample(temp_dataset)
    completion = create_test_completion_with_params(temp_dataset, prompt, sha256="h" * 64, completion_text="Good completion")
    temp_dataset.commit()

    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 9)

    create_test_logprobs(temp_dataset, completion.id, mapped_model.model_id, min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    controller = FacetSummaryController(app_with_dataset, temp_dataset, facet, mapped_model)
    report = controller.generate_report()

    # Should be ready for SFT
    assert report.sft_total_samples == 1
    assert report.sft_finished_samples == 1
    assert report.sft_unfinished_samples == 0

    # Should NOT be ready for DPO (no rejected completion)
    assert report.dpo_total_samples == 1
    assert report.dpo_finished_samples == 0
    assert report.dpo_unfinished_samples == 1
    assert "No paired rejection completion" in report.dpo_unfinished_details[0].reasons[0]
