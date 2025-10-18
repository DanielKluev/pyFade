"""
Test module for DPOController.

Tests DPO pair generation logic including rating thresholds, logprobs filtering,
and pairwise ranking conflict detection.
"""
from __future__ import annotations

from py_fade.controllers.dpo_controller import DPOController
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.completion_pairwise_ranks import PromptCompletionPairwiseRanking
from py_fade.dataset.facet import Facet
from tests.helpers.data_helpers import create_test_sample, create_test_logprobs, create_test_completion_with_params


def test_dpo_no_rated_completions(app_with_dataset, temp_dataset):
    """
    Test DPO pair generation when sample has no rated completions.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7)
    temp_dataset.commit()

    # Create sample with completion but no rating
    sample, _ = create_test_sample(temp_dataset)
    temp_dataset.commit()

    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    assert len(result.pairs) == 0
    assert len(result.failure_reasons) == 1
    assert "No rated completions found" in result.failure_reasons[0]


def test_dpo_no_high_rated_completions(app_with_dataset, temp_dataset):
    """
    Test DPO pair generation when no completion meets minimum rating threshold.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=8)
    temp_dataset.commit()

    # Create sample with low-rated completion
    sample, prompt = create_test_sample(temp_dataset)
    completion = create_test_completion_with_params(temp_dataset, prompt, sha256="a" * 64)
    temp_dataset.commit()

    # Add low rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 5)

    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    assert len(result.pairs) == 0
    assert len(result.failure_reasons) == 1
    assert "rating >= 8" in result.failure_reasons[0]
    assert "max rating: 5" in result.failure_reasons[0]


def test_dpo_high_rated_no_logprobs(app_with_dataset, temp_dataset):
    """
    Test DPO pair generation when high-rated completion has no logprobs.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7)
    temp_dataset.commit()

    # Create sample with high-rated completion but no logprobs
    sample, prompt = create_test_sample(temp_dataset)
    completion = create_test_completion_with_params(temp_dataset, prompt, sha256="b" * 64)
    temp_dataset.commit()

    # Add high rating but no logprobs
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    assert len(result.pairs) == 0
    assert len(result.failure_reasons) == 1
    assert "No high-rated completion meets logprob thresholds" in result.failure_reasons[0]


def test_dpo_only_one_high_rated_completion(app_with_dataset, temp_dataset):
    """
    Test DPO pair generation when only one completion meets rating threshold.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Create sample with one high-rated completion
    sample, prompt = create_test_sample(temp_dataset)
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    completion1 = create_test_completion_with_params(temp_dataset, prompt, sha256="c" * 64, model_id=mapped_model.model_id)
    # Add high rating and good logprobs
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)
    create_test_logprobs(temp_dataset, completion1.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)
    temp_dataset.commit()

    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    # Should fail: no lower-rated completion
    assert len(result.pairs) == 0
    assert len(result.failure_reasons) == 1
    assert "rating < 9" in result.failure_reasons[0]


def test_dpo_basic_pair_generation(app_with_dataset, temp_dataset):
    """
    Test basic DPO pair generation with one chosen and one rejected completion.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Create sample with two completions
    sample, prompt = create_test_sample(temp_dataset)
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # High-rated completion (chosen)
    completion1 = create_test_completion_with_params(temp_dataset, prompt, sha256="d" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Good answer")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)
    create_test_logprobs(temp_dataset, completion1.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)

    # Lower-rated completion (rejected)
    completion2 = create_test_completion_with_params(temp_dataset, prompt, sha256="e" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Bad answer")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 5)
    create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)

    temp_dataset.commit()

    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    # Should generate 1 pair
    assert len(result.pairs) == 1
    assert len(result.failure_reasons) == 0

    pair = result.pairs[0]
    assert pair.chosen == "Good answer"
    assert pair.rejected == "Bad answer"
    assert len(pair.prompt.messages) == 1
    assert pair.prompt.messages[0].role == "user"


def test_dpo_multiple_pairs_generation(app_with_dataset, temp_dataset):
    """
    Test DPO pair generation with multiple chosen and rejected completions.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Create sample with multiple completions
    sample, prompt = create_test_sample(temp_dataset)
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Two high-rated completions (chosen)
    completion1 = create_test_completion_with_params(temp_dataset, prompt, sha256="f" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Good answer 1")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)
    create_test_logprobs(temp_dataset, completion1.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)

    completion2 = create_test_completion_with_params(temp_dataset, prompt, sha256="g" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Good answer 2")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 8)
    create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)

    # Two lower-rated completions (rejected)
    completion3 = create_test_completion_with_params(temp_dataset, prompt, sha256="h" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Bad answer 1")
    PromptCompletionRating.set_rating(temp_dataset, completion3, facet, 5)
    create_test_logprobs(temp_dataset, completion3.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)

    completion4 = create_test_completion_with_params(temp_dataset, prompt, sha256="i" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Bad answer 2")
    PromptCompletionRating.set_rating(temp_dataset, completion4, facet, 6)
    create_test_logprobs(temp_dataset, completion4.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)

    temp_dataset.commit()

    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    # Should generate pairs:
    # - Good answer 1 (rating 9) pairs with Good answer 2 (rating 8), Bad answer 1 (5), Bad answer 2 (6) = 3 pairs
    # - Good answer 2 (rating 8) pairs with Bad answer 1 (5), Bad answer 2 (6) = 2 pairs
    # Total: 5 pairs
    assert len(result.pairs) == 5
    assert len(result.failure_reasons) == 0

    # Check that all expected combinations are present
    chosen_texts = {pair.chosen for pair in result.pairs}
    rejected_texts = {pair.rejected for pair in result.pairs}

    # Both high-rated should appear as chosen
    assert chosen_texts == {"Good answer 1", "Good answer 2"}
    # All three lower-rated should appear as rejected (including Good answer 2 when paired with Good answer 1)
    assert rejected_texts == {"Good answer 2", "Bad answer 1", "Bad answer 2"}


def test_dpo_strict_logprobs_filtering(app_with_dataset, temp_dataset):
    """
    Test DPO strict logprobs filtering when some rejected completions pass thresholds.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    sample, prompt = create_test_sample(temp_dataset)
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # High-rated completion (chosen)
    completion1 = create_test_completion_with_params(temp_dataset, prompt, sha256="j" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Good answer")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)
    create_test_logprobs(temp_dataset, completion1.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)

    # Lower-rated with good logprobs (should be included)
    completion2 = create_test_completion_with_params(temp_dataset, prompt, sha256="k" * 64, model_id=mapped_model.model_id,
                                                     completion_text="OK answer")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 6)
    create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)

    # Lower-rated with bad logprobs (should be excluded due to strict filtering)
    completion3 = create_test_completion_with_params(temp_dataset, prompt, sha256="l" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Bad answer")
    PromptCompletionRating.set_rating(temp_dataset, completion3, facet, 5)
    create_test_logprobs(temp_dataset, completion3.id, mapped_model.model_id, min_logprob=-0.8, avg_logprob=-0.6)

    temp_dataset.commit()

    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    # Should generate 1 pair with only the good logprobs rejected completion
    assert len(result.pairs) == 1
    assert result.pairs[0].rejected == "OK answer"


def test_dpo_best_logprobs_fallback(app_with_dataset, temp_dataset):
    """
    Test DPO fallback to best logprobs when no rejected completion passes thresholds.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    sample, prompt = create_test_sample(temp_dataset)
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # High-rated completion (chosen)
    completion1 = create_test_completion_with_params(temp_dataset, prompt, sha256="m" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Good answer")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)
    create_test_logprobs(temp_dataset, completion1.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)

    # Lower-rated with bad min_logprob but better avg
    completion2 = create_test_completion_with_params(temp_dataset, prompt, sha256="n" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Medium answer")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 5)
    create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.7, avg_logprob=-0.4)

    # Lower-rated with worse logprobs
    completion3 = create_test_completion_with_params(temp_dataset, prompt, sha256="o" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Bad answer")
    PromptCompletionRating.set_rating(temp_dataset, completion3, facet, 4)
    create_test_logprobs(temp_dataset, completion3.id, mapped_model.model_id, min_logprob=-0.9, avg_logprob=-0.7)

    temp_dataset.commit()

    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    # Should generate 1 pair with the best scored_logprob rejected completion
    assert len(result.pairs) == 1
    # Medium answer has better scored_logprob: -0.7 + (-0.4 * 2) = -1.5
    # Bad answer has worse scored_logprob: -0.9 + (-0.7 * 2) = -2.3
    assert result.pairs[0].rejected == "Medium answer"


def test_dpo_pairwise_ranking_conflict(app_with_dataset, temp_dataset):
    """
    Test DPO pairwise ranking conflict detection when ratings contradict explicit rankings.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    sample, prompt = create_test_sample(temp_dataset)
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Completion with rating 9 (will be chosen)
    completion1 = create_test_completion_with_params(temp_dataset, prompt, sha256="p" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Should be chosen")
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)
    create_test_logprobs(temp_dataset, completion1.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)

    # Completion with rating 8 (will be rejected)
    completion2 = create_test_completion_with_params(temp_dataset, prompt, sha256="q" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Should be rejected")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 8)
    create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)

    # Create explicit pairwise ranking that conflicts with ratings
    # Mark completion2 (rating 8) as better than completion1 (rating 9), which conflicts
    # with the actual ratings where completion1 is higher
    PromptCompletionPairwiseRanking.get_or_create(temp_dataset, completion2, completion1, facet)
    temp_dataset.commit()

    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    # Should still generate 1 pair: (completion1, completion2) = (rating 9, rating 8)
    # But there's a pairwise ranking saying completion2 > completion1, which conflicts
    assert len(result.pairs) == 1
    assert len(result.pairwise_ranking_conflicts) == 1
    assert "conflict" in result.pairwise_ranking_conflicts[0].lower()
    assert "8 < 9" in result.pairwise_ranking_conflicts[0]


def test_dpo_no_logprobs_for_rejected(app_with_dataset, temp_dataset):
    """
    Test DPO when no lower-rated completion has logprobs data.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    sample, prompt = create_test_sample(temp_dataset)
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # High-rated completion with logprobs (chosen)
    completion1 = create_test_completion_with_params(temp_dataset, prompt, sha256="r" * 64, model_id=mapped_model.model_id)
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 9)
    create_test_logprobs(temp_dataset, completion1.id, mapped_model.model_id, min_logprob=-0.4, avg_logprob=-0.2)

    # Lower-rated completion without logprobs (rejected)
    completion2 = create_test_completion_with_params(temp_dataset, prompt, sha256="s" * 64, model_id=mapped_model.model_id)
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 5)
    # No logprobs for completion2

    temp_dataset.commit()

    controller = DPOController(temp_dataset, facet, mapped_model.model_id)
    result = controller.generate_pairs_for_sample(sample)

    # Should fail: no lower-rated completion has logprobs
    assert len(result.pairs) == 0
    assert len(result.failure_reasons) == 1
    assert "No lower-rated completion has logprobs data" in result.failure_reasons[0]
