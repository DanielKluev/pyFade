"""
Test suite for sample facets functionality.

Tests the get_facets() method on Sample class which returns all facets
that have ratings for completions in the sample.
"""

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from tests.helpers.data_helpers import create_test_completion_with_params


def test_sample_get_facets_no_completions(temp_dataset) -> None:
    """
    Test that get_facets returns empty list when sample has no completions.

    Verifies behavior when prompt revision exists but has no completions.
    """
    # Create sample with no completions
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Get facets - should be empty
    facets = sample.get_facets(temp_dataset)
    assert not facets


def test_sample_get_facets_no_ratings(temp_dataset) -> None:
    """
    Test that get_facets returns empty list when completions have no ratings.

    Verifies behavior when sample has completions but no ratings.
    """
    # Create sample with completion but no rating
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)

    # Add completion without rating
    _completion = create_test_completion_with_params(temp_dataset, prompt_revision, completion_text="Test completion", is_truncated=False)
    temp_dataset.commit()

    # Get facets - should be empty
    facets = sample.get_facets(temp_dataset)
    assert not facets


def test_sample_get_facets_single_facet(temp_dataset) -> None:
    """
    Test that get_facets returns single facet when one completion is rated for one facet.

    Verifies basic functionality of getting facets from ratings.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create sample with rated completion
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)

    # Add completion with rating
    completion = create_test_completion_with_params(temp_dataset, prompt_revision, completion_text="Test completion", is_truncated=False)
    temp_dataset.commit()

    # Add rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)

    # Get facets - should contain one facet
    facets = sample.get_facets(temp_dataset)
    assert len(facets) == 1
    assert facets[0].id == facet.id
    assert facets[0].name == "Quality"


def test_sample_get_facets_multiple_facets(temp_dataset) -> None:
    """
    Test that get_facets returns multiple facets when completions are rated for multiple facets.

    Verifies that all facets with ratings are returned, ordered by name.
    """
    # Create facets (intentionally out of alphabetical order)
    facet_quality = Facet.create(temp_dataset, "Quality", "Quality facet")
    facet_accuracy = Facet.create(temp_dataset, "Accuracy", "Accuracy facet")
    facet_relevance = Facet.create(temp_dataset, "Relevance", "Relevance facet")
    temp_dataset.commit()

    # Create sample with multiple rated completions
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)

    # Add completions with ratings for different facets
    completion1 = create_test_completion_with_params(temp_dataset, prompt_revision, sha256="a" * 64, completion_text="Test completion 1",
                                                     is_truncated=False)
    completion2 = create_test_completion_with_params(temp_dataset, prompt_revision, sha256="b" * 64, completion_text="Test completion 2",
                                                     is_truncated=False)
    temp_dataset.commit()

    # Add ratings for different facets
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet_quality, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet_relevance, 7)
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet_accuracy, 9)

    # Get facets - should contain all three facets ordered by name
    facets = sample.get_facets(temp_dataset)
    assert len(facets) == 3
    assert facets[0].name == "Accuracy"
    assert facets[1].name == "Quality"
    assert facets[2].name == "Relevance"


def test_sample_get_facets_no_duplicates(temp_dataset) -> None:
    """
    Test that get_facets returns each facet only once even with multiple ratings.

    Verifies that duplicate facets are not returned when multiple completions
    are rated for the same facet.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Quality", "Quality facet")
    temp_dataset.commit()

    # Create sample with multiple rated completions
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)

    # Add multiple completions with ratings for same facet
    completion1 = create_test_completion_with_params(temp_dataset, prompt_revision, sha256="a" * 64, completion_text="Test completion 1",
                                                     is_truncated=False)
    completion2 = create_test_completion_with_params(temp_dataset, prompt_revision, sha256="b" * 64, completion_text="Test completion 2",
                                                     is_truncated=False)
    temp_dataset.commit()

    # Add ratings for same facet
    PromptCompletionRating.set_rating(temp_dataset, completion1, facet, 8)
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 7)

    # Get facets - should contain facet only once
    facets = sample.get_facets(temp_dataset)
    assert len(facets) == 1
    assert facets[0].id == facet.id


def test_sample_get_facets_no_prompt_revision(temp_dataset) -> None:
    """
    Test that get_facets returns empty list when sample has no prompt revision.

    Edge case: sample without prompt revision should return empty list.
    """
    # Create sample without prompt revision (set to None)
    sample = Sample(
        title="Test Sample",
        group_path=None,
        notes=None,
        prompt_revision=None,
    )
    temp_dataset.session.add(sample)
    temp_dataset.commit()

    # Get facets - should be empty
    facets = sample.get_facets(temp_dataset)
    assert not facets
