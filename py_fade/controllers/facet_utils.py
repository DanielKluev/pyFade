"""
Utility functions for working with facets in controllers.

This module provides common helper functions that are used by multiple
controller classes when working with facets, completions, and ratings.

Key functions: `get_rated_completions`
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.facet import Facet
    from py_fade.dataset.sample import Sample


def get_rated_completions(sample: "Sample", facet: "Facet") -> list[tuple["PromptCompletion", int]]:
    """
    Get all completions with ratings for the specified facet.

    Args:
        sample: Sample to get completions from
        facet: Facet to filter ratings by

    Returns:
        List of (completion, rating) tuples for completions that have ratings in the facet
    """
    rated_completions = []
    for completion in sample.completions:
        rating_obj = completion.rating_for_facet(facet)
        if rating_obj:
            rated_completions.append((completion, rating_obj.rating))
    return rated_completions
