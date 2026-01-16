"""
Controller for facet switching operations.

This module provides functions to remove, change, or copy facet associations
for a sample's completions, handling both ratings and pairwise rankings.
"""

import logging
from typing import TYPE_CHECKING

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.completion_pairwise_ranks import PromptCompletionPairwiseRanking

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.dataset.sample import Sample


class FacetSwitchController:
    """
    Controller for facet switching operations on samples.

    Handles operations to remove, change, or copy facet associations
    for all completions in a sample.
    """

    def __init__(self, dataset: "DatasetDatabase"):
        """
        Initialize the facet switch controller.

        Args:
            dataset: The dataset database instance
        """
        self.dataset = dataset
        self.log = logging.getLogger(self.__class__.__name__)

    def remove_facet_from_sample(self, sample: "Sample", facet: "Facet") -> int:
        """
        Remove all ratings and rankings for the specified facet from the sample.

        Deletes all completion ratings and pairwise rankings associated with
        the specified facet for all completions in the sample.

        Args:
            sample: Sample to remove facet from
            facet: Facet to remove

        Returns:
            Number of ratings and rankings removed
        """
        count = 0
        session = self.dataset.get_session()

        # Remove all ratings for this facet
        for completion in sample.completions:
            rating = PromptCompletionRating.get(self.dataset, completion, facet)
            if rating:
                session.delete(rating)
                count += 1
                self.log.debug("Removed rating for completion %d and facet %s", completion.id, facet.name)

        # Remove all pairwise rankings for this facet
        # We need to check all possible pairs of completions
        for i, comp1 in enumerate(sample.completions):
            for comp2 in sample.completions[i + 1:]:
                # Check both directions
                ranking1 = PromptCompletionPairwiseRanking.get(self.dataset, comp1, comp2, facet)
                if ranking1:
                    session.delete(ranking1)
                    count += 1
                    self.log.debug("Removed pairwise ranking between completions %d and %d for facet %s", comp1.id, comp2.id, facet.name)

                ranking2 = PromptCompletionPairwiseRanking.get(self.dataset, comp2, comp1, facet)
                if ranking2:
                    session.delete(ranking2)
                    count += 1
                    self.log.debug("Removed pairwise ranking between completions %d and %d for facet %s", comp2.id, comp1.id, facet.name)

        session.commit()
        self.log.info("Removed %d ratings/rankings for facet '%s' from sample %d", count, facet.name, sample.id)
        return count

    def change_facet_for_sample(self, sample: "Sample", source_facet: "Facet", target_facet: "Facet") -> tuple[int, int]:
        """
        Change all ratings and rankings from source facet to target facet.

        Moves all completion ratings and pairwise rankings from the source facet
        to the target facet for all completions in the sample. If a rating or ranking
        already exists for the target facet, it is skipped (not overwritten).

        Args:
            sample: Sample to change facet for
            source_facet: Facet to change from
            target_facet: Facet to change to

        Returns:
            Tuple of (transferred_count, skipped_count)
        """
        transferred, skipped = self._copy_facet_data(sample, source_facet, target_facet)

        # After copying, remove the source facet data
        self.remove_facet_from_sample(sample, source_facet)

        self.log.info("Changed facet '%s' to '%s' for sample %d: transferred %d, skipped %d", source_facet.name, target_facet.name,
                      sample.id, transferred, skipped)
        return transferred, skipped

    def copy_facet_for_sample(self, sample: "Sample", source_facet: "Facet", target_facet: "Facet") -> tuple[int, int]:
        """
        Copy all ratings and rankings from source facet to target facet.

        Duplicates all completion ratings and pairwise rankings from the source facet
        to the target facet for all completions in the sample. If a rating or ranking
        already exists for the target facet, it is skipped (not overwritten).

        Args:
            sample: Sample to copy facet for
            source_facet: Facet to copy from
            target_facet: Facet to copy to

        Returns:
            Tuple of (copied_count, skipped_count)
        """
        copied, skipped = self._copy_facet_data(sample, source_facet, target_facet)
        self.log.info("Copied facet '%s' to '%s' for sample %d: copied %d, skipped %d", source_facet.name, target_facet.name, sample.id,
                      copied, skipped)
        return copied, skipped

    def _copy_facet_data(self, sample: "Sample", source_facet: "Facet", target_facet: "Facet") -> tuple[int, int]:
        """
        Internal helper to copy ratings and rankings from source to target facet.

        Args:
            sample: Sample to copy data for
            source_facet: Source facet
            target_facet: Target facet

        Returns:
            Tuple of (copied_count, skipped_count)
        """
        copied = 0
        skipped = 0
        session = self.dataset.get_session()

        # Copy all ratings
        for completion in sample.completions:
            source_rating = PromptCompletionRating.get(self.dataset, completion, source_facet)
            if source_rating:
                # Check if target already has a rating
                target_rating = PromptCompletionRating.get(self.dataset, completion, target_facet)
                if target_rating:
                    skipped += 1
                    self.log.debug("Skipped existing rating for completion %d in target facet %s", completion.id, target_facet.name)
                else:
                    # Create new rating for target facet
                    new_rating = PromptCompletionRating(
                        prompt_completion=completion,
                        facet=target_facet,
                        rating=source_rating.rating,
                    )
                    session.add(new_rating)
                    copied += 1
                    self.log.debug("Copied rating %d for completion %d to target facet %s", source_rating.rating, completion.id,
                                   target_facet.name)

        # Copy all pairwise rankings
        for i, comp1 in enumerate(sample.completions):
            for comp2 in sample.completions[i + 1:]:
                # Check both directions
                for better, worse in [(comp1, comp2), (comp2, comp1)]:
                    source_ranking = PromptCompletionPairwiseRanking.get(self.dataset, better, worse, source_facet)
                    if source_ranking:
                        # Check if target already has this ranking
                        target_ranking = PromptCompletionPairwiseRanking.get(self.dataset, better, worse, target_facet)
                        if target_ranking:
                            skipped += 1
                            self.log.debug("Skipped existing ranking between completions %d and %d in target facet %s", better.id, worse.id,
                                           target_facet.name)
                        else:
                            # Create new ranking for target facet
                            new_ranking = PromptCompletionPairwiseRanking(
                                better_completion=better,
                                worse_completion=worse,
                                facet=target_facet,
                            )
                            session.add(new_ranking)
                            copied += 1
                            self.log.debug("Copied ranking between completions %d and %d to target facet %s", better.id, worse.id,
                                           target_facet.name)

        session.commit()
        return copied, skipped
