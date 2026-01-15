"""
Unit tests for FacetSwitchController.

Tests cover all three main operations:
- Remove facet from sample
- Change facet for sample
- Copy facet for sample
"""

import logging

import pytest

from py_fade.controllers.facet_switch_controller import FacetSwitchController
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_pairwise_ranks import PromptCompletionPairwiseRanking
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from tests.helpers.data_helpers import create_test_completion_pair, create_facet_pair_and_sample


def test_remove_facet_from_sample_with_ratings(
    temp_dataset,
    caplog: pytest.LogCaptureFixture,
):
    """
    Test removing a facet with ratings from a sample.

    Verifies that all ratings for the specified facet are deleted.
    """
    caplog.set_level(logging.DEBUG)

    # Create facets and sample
    facet1, facet2, sample = create_facet_pair_and_sample(temp_dataset)

    # Add completions
    completion1, completion2 = create_test_completion_pair(temp_dataset, sample.prompt_revision)

    # Add ratings for both facets
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet1, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet1, 7)
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet2, 9)

    # Verify ratings exist
    assert PromptCompletionRating.get(temp_dataset, completion1, facet1) is not None
    assert PromptCompletionRating.get(temp_dataset, completion2, facet1) is not None
    assert PromptCompletionRating.get(temp_dataset, completion1, facet2) is not None

    # Remove facet1
    controller = FacetSwitchController(temp_dataset)
    count = controller.remove_facet_from_sample(sample, facet1)

    # Verify ratings removed
    assert count == 2
    assert PromptCompletionRating.get(temp_dataset, completion1, facet1) is None
    assert PromptCompletionRating.get(temp_dataset, completion2, facet1) is None
    # facet2 rating should still exist
    assert PromptCompletionRating.get(temp_dataset, completion1, facet2) is not None


def test_remove_facet_from_sample_with_rankings(
    temp_dataset,
    caplog: pytest.LogCaptureFixture,
):
    """
    Test removing a facet with pairwise rankings from a sample.

    Verifies that all pairwise rankings for the specified facet are deleted.
    """
    caplog.set_level(logging.DEBUG)

    # Create facets and sample
    facet1, _, sample = create_facet_pair_and_sample(temp_dataset)

    # Add completions
    completion1, completion2 = create_test_completion_pair(temp_dataset, sample.prompt_revision)

    # Add pairwise ranking
    ranking = PromptCompletionPairwiseRanking.get_or_create(temp_dataset, completion1, completion2, facet1)
    assert ranking is not None

    # Remove facet1
    controller = FacetSwitchController(temp_dataset)
    count = controller.remove_facet_from_sample(sample, facet1)

    # Verify ranking removed
    assert count == 1
    assert PromptCompletionPairwiseRanking.get(temp_dataset, completion1, completion2, facet1) is None


def test_change_facet_for_sample(
    temp_dataset,
    caplog: pytest.LogCaptureFixture,
):
    """
    Test changing facet for sample ratings.

    Verifies that ratings are moved from source to target facet,
    and source facet data is removed.
    """
    caplog.set_level(logging.DEBUG)

    # Create facets and sample
    source_facet, target_facet, sample = create_facet_pair_and_sample(temp_dataset, facet1_name="Source", facet1_desc="Source facet",
                                                                       facet2_name="Target", facet2_desc="Target facet")

    # Add completions
    completion1, completion2 = create_test_completion_pair(temp_dataset, sample.prompt_revision)

    # Add ratings to source facet
    PromptCompletionRating.set_rating(temp_dataset, completion1, source_facet, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion2, source_facet, 7)

    # Change facet
    controller = FacetSwitchController(temp_dataset)
    transferred, skipped = controller.change_facet_for_sample(sample, source_facet, target_facet)

    # Verify ratings moved
    assert transferred == 2
    assert skipped == 0
    # Source ratings should be gone
    assert PromptCompletionRating.get(temp_dataset, completion1, source_facet) is None
    assert PromptCompletionRating.get(temp_dataset, completion2, source_facet) is None
    # Target ratings should exist
    target_rating1 = PromptCompletionRating.get(temp_dataset, completion1, target_facet)
    target_rating2 = PromptCompletionRating.get(temp_dataset, completion2, target_facet)
    assert target_rating1 is not None
    assert target_rating1.rating == 8
    assert target_rating2 is not None
    assert target_rating2.rating == 7


def test_change_facet_with_existing_target_ratings(
    temp_dataset,
    caplog: pytest.LogCaptureFixture,
):
    """
    Test changing facet when target already has some ratings.

    Verifies that existing target ratings are not overwritten.
    """
    caplog.set_level(logging.DEBUG)

    # Create facets and sample
    source_facet, target_facet, sample = create_facet_pair_and_sample(temp_dataset, facet1_name="Source", facet1_desc="Source facet",
                                                                       facet2_name="Target", facet2_desc="Target facet")

    # Add completions
    completion1, completion2 = create_test_completion_pair(temp_dataset, sample.prompt_revision)

    # Add ratings to source facet
    PromptCompletionRating.set_rating(temp_dataset, completion1, source_facet, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion2, source_facet, 7)

    # Add rating to target facet for completion1 (should not be overwritten)
    PromptCompletionRating.set_rating(temp_dataset, completion1, target_facet, 5)

    # Change facet
    controller = FacetSwitchController(temp_dataset)
    transferred, skipped = controller.change_facet_for_sample(sample, source_facet, target_facet)

    # Verify only completion2 was transferred, completion1 was skipped
    assert transferred == 1
    assert skipped == 1
    # Source ratings should be gone
    assert PromptCompletionRating.get(temp_dataset, completion1, source_facet) is None
    assert PromptCompletionRating.get(temp_dataset, completion2, source_facet) is None
    # Target rating for completion1 should still have original value
    target_rating1 = PromptCompletionRating.get(temp_dataset, completion1, target_facet)
    assert target_rating1 is not None
    assert target_rating1.rating == 5  # Original value, not overwritten
    # Target rating for completion2 should be transferred
    target_rating2 = PromptCompletionRating.get(temp_dataset, completion2, target_facet)
    assert target_rating2 is not None
    assert target_rating2.rating == 7


def test_copy_facet_for_sample(
    temp_dataset,
    caplog: pytest.LogCaptureFixture,
):
    """
    Test copying facet for sample ratings.

    Verifies that ratings are duplicated to target facet,
    and source facet data remains intact.
    """
    caplog.set_level(logging.DEBUG)

    # Create facets and sample
    source_facet, target_facet, sample = create_facet_pair_and_sample(temp_dataset, facet1_name="Source", facet1_desc="Source facet",
                                                                       facet2_name="Target", facet2_desc="Target facet")

    # Add completions
    completion1, completion2 = create_test_completion_pair(temp_dataset, sample.prompt_revision)

    # Add ratings to source facet
    PromptCompletionRating.set_rating(temp_dataset, completion1, source_facet, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion2, source_facet, 7)

    # Copy facet
    controller = FacetSwitchController(temp_dataset)
    copied, skipped = controller.copy_facet_for_sample(sample, source_facet, target_facet)

    # Verify ratings copied
    assert copied == 2
    assert skipped == 0
    # Source ratings should still exist
    source_rating1 = PromptCompletionRating.get(temp_dataset, completion1, source_facet)
    source_rating2 = PromptCompletionRating.get(temp_dataset, completion2, source_facet)
    assert source_rating1 is not None
    assert source_rating1.rating == 8
    assert source_rating2 is not None
    assert source_rating2.rating == 7
    # Target ratings should exist
    target_rating1 = PromptCompletionRating.get(temp_dataset, completion1, target_facet)
    target_rating2 = PromptCompletionRating.get(temp_dataset, completion2, target_facet)
    assert target_rating1 is not None
    assert target_rating1.rating == 8
    assert target_rating2 is not None
    assert target_rating2.rating == 7


def test_copy_facet_with_pairwise_rankings(
    temp_dataset,
    caplog: pytest.LogCaptureFixture,
):
    """
    Test copying facet with pairwise rankings.

    Verifies that pairwise rankings are duplicated correctly.
    """
    caplog.set_level(logging.DEBUG)

    # Create facets and sample
    source_facet, target_facet, sample = create_facet_pair_and_sample(temp_dataset, facet1_name="Source", facet1_desc="Source facet",
                                                                       facet2_name="Target", facet2_desc="Target facet")

    # Add completions
    completion1, completion2 = create_test_completion_pair(temp_dataset, sample.prompt_revision)
    completion3 = PromptCompletion(
        prompt_revision_id=sample.prompt_revision.id,
        sha256="c" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion 3",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    temp_dataset.session.add(completion3)
    temp_dataset.commit()

    # Add pairwise rankings to source facet
    PromptCompletionPairwiseRanking.get_or_create(temp_dataset, completion1, completion2, source_facet)
    PromptCompletionPairwiseRanking.get_or_create(temp_dataset, completion2, completion3, source_facet)

    # Copy facet
    controller = FacetSwitchController(temp_dataset)
    copied, skipped = controller.copy_facet_for_sample(sample, source_facet, target_facet)

    # Verify rankings copied
    assert copied == 2
    assert skipped == 0
    # Source rankings should still exist
    assert PromptCompletionPairwiseRanking.get(temp_dataset, completion1, completion2, source_facet) is not None
    assert PromptCompletionPairwiseRanking.get(temp_dataset, completion2, completion3, source_facet) is not None
    # Target rankings should exist
    assert PromptCompletionPairwiseRanking.get(temp_dataset, completion1, completion2, target_facet) is not None
    assert PromptCompletionPairwiseRanking.get(temp_dataset, completion2, completion3, target_facet) is not None


def test_copy_facet_with_existing_target_rankings(
    temp_dataset,
    caplog: pytest.LogCaptureFixture,
):
    """
    Test copying facet when target already has some rankings.

    Verifies that existing target rankings are not overwritten.
    """
    caplog.set_level(logging.DEBUG)

    # Create facets and sample
    source_facet, target_facet, sample = create_facet_pair_and_sample(temp_dataset, facet1_name="Source", facet1_desc="Source facet",
                                                                       facet2_name="Target", facet2_desc="Target facet")

    # Add completions
    completion1, completion2 = create_test_completion_pair(temp_dataset, sample.prompt_revision)

    # Add pairwise ranking to source facet
    PromptCompletionPairwiseRanking.get_or_create(temp_dataset, completion1, completion2, source_facet)

    # Add same ranking to target facet (should not be overwritten)
    PromptCompletionPairwiseRanking.get_or_create(temp_dataset, completion1, completion2, target_facet)

    # Copy facet
    controller = FacetSwitchController(temp_dataset)
    copied, skipped = controller.copy_facet_for_sample(sample, source_facet, target_facet)

    # Verify ranking was skipped
    assert copied == 0
    assert skipped == 1
    # Both rankings should still exist
    assert PromptCompletionPairwiseRanking.get(temp_dataset, completion1, completion2, source_facet) is not None
    assert PromptCompletionPairwiseRanking.get(temp_dataset, completion1, completion2, target_facet) is not None
