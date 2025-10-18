"""
Direct Preference Optimization (DPO) data builder.

Unlike SFT, DPO may yield multiple training samples from a single dataset sample.

For each dataset sample, we follow these rules:
- "Chosen" completion must have rating above specified threshold, we don't pair low-rated samples together.
- For "Rejected", check if there any non-top-rated completion that passes logprobs thresholds:
    - If yes, we apply strict logprobs filtering for all pairs.
    - If no, we choose one highest logprobs completion which isn't top-rated and use it as
      "Rejected" without further filtering.
- If PromptCompletionPairwiseRanking exists for the pair, it's treated as preferential, but if
  ratings contradict that (winner has LESSER rating than loser), inform about error.
- Then we use above criteria to create all possible pairs, for every acceptable "Chosen" picking
  every completion with lesser rating as "Rejected".
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.data_formats.dpo_data_format import DPOPair

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.completion_pairwise_ranks import PromptCompletionPairwiseRanking
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.dataset.sample import Sample


@dataclass
class DPOPairGenerationResult:
    """
    Result from generating DPO pairs for a sample.
    """

    pairs: list[DPOPair] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    pairwise_ranking_conflicts: list[str] = field(default_factory=list)


class DPOController:
    """
    Controller for generating DPO training pairs from rated completions.

    Implements the logic for pairing chosen and rejected completions according to
    rating and logprobs thresholds, with support for explicit pairwise rankings.
    """

    def __init__(self, dataset: "DatasetDatabase", facet: "Facet", target_model_id: str):
        """
        Initialize DPO controller.

        Args:
            dataset: Dataset database to work with
            facet: Facet to filter completions by
            target_model_id: Model ID to check logprobs against
        """
        self.log = logging.getLogger("DPOController")
        self.dataset = dataset
        self.facet = facet
        self.target_model_id = target_model_id

    def generate_pairs_for_sample(self, sample: "Sample") -> DPOPairGenerationResult:  # pylint: disable=too-many-return-statements
        """
        Generate all valid DPO pairs for a sample according to the specification.

        Args:
            sample: Sample to generate pairs from

        Returns:
            DPOPairGenerationResult with pairs and any failure reasons or conflicts
        """
        result = DPOPairGenerationResult()

        # Get completions with ratings for this facet
        rated_completions = self._get_rated_completions(sample)
        if not rated_completions:
            result.failure_reasons.append("No rated completions found")
            return result

        # Find completions that meet minimum rating threshold (potential "chosen" completions)
        high_rated = [(comp, rating) for comp, rating in rated_completions if rating >= self.facet.min_rating]

        if not high_rated:
            max_rating = max(rating for _, rating in rated_completions)
            result.failure_reasons.append(f"No completion with rating >= {self.facet.min_rating} (max rating: {max_rating})")
            return result

        # Check logprob thresholds for high-rated completions
        valid_chosen = []
        for completion, rating in high_rated:
            logprobs = completion.get_logprobs_for_model_id(self.target_model_id)
            if (logprobs and logprobs.min_logprob >= self.facet.min_logprob_threshold and
                    logprobs.avg_logprob >= self.facet.avg_logprob_threshold):
                valid_chosen.append((completion, rating, logprobs))

        if not valid_chosen:
            result.failure_reasons.append("No high-rated completion meets logprob thresholds")
            return result

        # Now we have valid "chosen" completions. Find potential "rejected" completions.
        # Rejected must have lower rating than the specific chosen completion being paired.
        # Determine if we should apply strict logprobs filtering for rejected completions.

        # Get the highest rating among valid chosen (for checking if ANY lower-rated exists)
        max_chosen_rating = max(rating for _, rating, _ in valid_chosen)

        # Find all completions with lower rating than the highest chosen rating
        # (We'll filter per-pair later to ensure rejected < chosen for that specific pair)
        all_lower_rated = [(comp, rating) for comp, rating in rated_completions if rating < max_chosen_rating]

        if not all_lower_rated:
            result.failure_reasons.append(f"No completion with rating < {max_chosen_rating} (best chosen rating)")
            return result

        # Check if any lower-rated completion passes logprobs thresholds
        lower_rated_with_good_logprobs = []
        for completion, rating in all_lower_rated:
            logprobs = completion.get_logprobs_for_model_id(self.target_model_id)
            if (logprobs and logprobs.min_logprob >= self.facet.min_logprob_threshold and
                    logprobs.avg_logprob >= self.facet.avg_logprob_threshold):
                lower_rated_with_good_logprobs.append((completion, rating, logprobs))

        # Determine filtering strategy per specification
        use_strict_filtering = len(lower_rated_with_good_logprobs) > 0
        if use_strict_filtering:
            # Apply strict filtering: only use rejected completions that pass logprobs thresholds
            candidate_rejected = lower_rated_with_good_logprobs
            self.log.debug("Sample %d: Using strict logprobs filtering for rejected completions", sample.id)
        else:
            # No lower-rated completion passes thresholds, pick the one with highest logprobs
            # Find completion with highest scored_logprob among lower-rated
            best_rejected = None
            best_scored_logprob = float('-inf')
            for completion, rating in all_lower_rated:
                logprobs = completion.get_logprobs_for_model_id(self.target_model_id)
                if logprobs and logprobs.scored_logprob is not None:
                    if logprobs.scored_logprob > best_scored_logprob:
                        best_scored_logprob = logprobs.scored_logprob
                        best_rejected = (completion, rating, logprobs)

            if best_rejected:
                candidate_rejected = [best_rejected]
                self.log.debug("Sample %d: Using best logprobs rejected completion (scored: %.3f)", sample.id, best_scored_logprob)
            else:
                result.failure_reasons.append("No lower-rated completion has logprobs data")
                return result

        # Generate all pairs: for each valid chosen, pair with all candidate rejected that have LOWER rating
        prompt_conv = self._sample_to_prompt_conversation(sample)
        if not prompt_conv:
            result.failure_reasons.append("Could not create prompt conversation")
            return result

        for chosen_tuple in valid_chosen:
            chosen_comp, chosen_rating = chosen_tuple[0], chosen_tuple[1]
            # For this specific chosen, find rejected completions with STRICTLY lower rating
            valid_rejected_for_this_chosen = [(comp, rating, lp) for comp, rating, lp in candidate_rejected if rating < chosen_rating]

            for rejected_tuple in valid_rejected_for_this_chosen:
                rejected_comp, rejected_rating = rejected_tuple[0], rejected_tuple[1]
                # Check for pairwise ranking conflicts
                # We're saying chosen > rejected (by rating).
                # Check if there's a pairwise ranking saying rejected > chosen, which would conflict.
                conflicting_ranking = self._get_pairwise_ranking(rejected_comp, chosen_comp)
                if conflicting_ranking:
                    conflict_msg = (f"Pairwise ranking conflict: {rejected_comp.id} marked as better than "
                                    f"{chosen_comp.id}, but has lower rating ({rejected_rating} < {chosen_rating})")
                    result.pairwise_ranking_conflicts.append(conflict_msg)
                    self.log.warning("Sample %d: %s", sample.id, conflict_msg)

                # Create DPO pair
                pair = DPOPair(prompt=prompt_conv, chosen=chosen_comp.completion_text, rejected=rejected_comp.completion_text)
                result.pairs.append(pair)

        self.log.debug("Sample %d: Generated %d DPO pairs", sample.id, len(result.pairs))
        return result

    def _get_rated_completions(self, sample: "Sample") -> list[tuple["PromptCompletion", int]]:
        """
        Get all completions with ratings for the current facet.

        Args:
            sample: Sample to get completions from

        Returns:
            List of (completion, rating) tuples
        """
        rated_completions = []
        for completion in sample.completions:
            rating_obj = completion.rating_for_facet(self.facet)
            if rating_obj:
                rated_completions.append((completion, rating_obj.rating))
        return rated_completions

    def _sample_to_prompt_conversation(self, sample: "Sample") -> CommonConversation | None:
        """
        Convert sample prompt to CommonConversation.

        Args:
            sample: Sample to convert

        Returns:
            CommonConversation or None if not possible
        """
        if not sample.prompt_revision:
            return None

        # For DPO, we only need the prompt (user message)
        messages = [CommonMessage(role="user", content=sample.prompt_revision.prompt_text)]
        return CommonConversation(messages=messages)

    def _get_pairwise_ranking(self, better_comp: "PromptCompletion",
                              worse_comp: "PromptCompletion") -> "PromptCompletionPairwiseRanking | None":
        """
        Get explicit pairwise ranking if it exists.

        Args:
            better_comp: Completion that should be better
            worse_comp: Completion that should be worse

        Returns:
            PromptCompletionPairwiseRanking or None
        """
        from py_fade.dataset.completion_pairwise_ranks import PromptCompletionPairwiseRanking  # pylint: disable=import-outside-toplevel
        return PromptCompletionPairwiseRanking.get(self.dataset, better_comp, worse_comp, self.facet)
