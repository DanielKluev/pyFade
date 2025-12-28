"""
Kahneman-Tversky Optimization (KTO) data builder.

KTO uses binary labels (good/bad) rather than preference pairs.
For each dataset sample, we:
- Mark completions with rating >= min_rating as "good" (label=true)
- Mark completions with rating <= max_rating as "bad" (label=false)
- Skip completions between max_rating and min_rating (neutral zone)
- Apply logprob thresholds to ensure quality
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from py_fade.controllers.facet_utils import get_rated_completions
from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.data_formats.kto_data_format import KTOSample

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.dataset.sample import Sample


@dataclass
class KTOSampleGenerationResult:
    """
    Result from generating KTO samples for a dataset sample.
    """

    samples: list[KTOSample] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)


class KTOController:
    """
    Controller for generating KTO training samples from rated completions.

    Implements the logic for labeling completions as good or bad according to
    rating thresholds and logprob filters.
    """

    def __init__(self, dataset: "DatasetDatabase", facet: "Facet", target_model_id: str):
        """
        Initialize KTO controller.

        Args:
            dataset: Dataset database to work with
            facet: Facet to filter completions by
            target_model_id: Model ID to check logprobs against
        """
        self.log = logging.getLogger("KTOController")
        self.dataset = dataset
        self.facet = facet
        self.target_model_id = target_model_id

    def generate_samples_for_sample(self, sample: "Sample") -> KTOSampleGenerationResult:
        """
        Generate all valid KTO samples for a dataset sample.

        For each rated completion, check if it qualifies as good or bad based on:
        - Good: rating >= min_rating AND passes logprob thresholds
        - Bad: rating <= max_rating AND passes logprob thresholds
        - Neutral: min_rating > rating > max_rating (not exported)

        Args:
            sample: Sample to generate KTO samples from

        Returns:
            KTOSampleGenerationResult with samples and any failure reasons
        """
        result = KTOSampleGenerationResult()

        # Get completions with ratings for this facet
        rated_completions = get_rated_completions(sample, self.facet)
        if not rated_completions:
            result.failure_reasons.append("No rated completions found")
            return result

        # Get prompt from sample
        if not sample.prompt_revision:
            result.failure_reasons.append("Sample has no prompt revision")
            return result

        prompt_conv = CommonConversation(messages=[CommonMessage(role="user", content=sample.prompt_revision.prompt_text)])

        # Process each rated completion
        good_count = 0
        bad_count = 0

        for completion, rating in rated_completions:
            # Check logprob thresholds
            logprobs = completion.get_logprobs_for_model_id(self.target_model_id)
            if not logprobs:
                self.log.debug("Completion %d has no logprobs for model %s, skipping", completion.id, self.target_model_id)
                continue

            if (logprobs.min_logprob < self.facet.min_logprob_threshold or logprobs.avg_logprob < self.facet.avg_logprob_threshold):
                self.log.debug("Completion %d fails logprob thresholds (min=%.3f/%.3f, avg=%.3f/%.3f), skipping", completion.id,
                               logprobs.min_logprob, self.facet.min_logprob_threshold, logprobs.avg_logprob,
                               self.facet.avg_logprob_threshold)
                continue

            # Determine label based on rating
            if rating >= self.facet.min_rating:
                # Good sample
                kto_sample = KTOSample(prompt=prompt_conv, completion=completion.completion_text, label=True)
                result.samples.append(kto_sample)
                good_count += 1
                self.log.debug("Completion %d rated %d >= %d: marked as good", completion.id, rating, self.facet.min_rating)
            elif rating <= self.facet.max_rating:
                # Bad sample
                kto_sample = KTOSample(prompt=prompt_conv, completion=completion.completion_text, label=False)
                result.samples.append(kto_sample)
                bad_count += 1
                self.log.debug("Completion %d rated %d <= %d: marked as bad", completion.id, rating, self.facet.max_rating)
            else:
                # Neutral zone - not exported
                self.log.debug("Completion %d rated %d is in neutral zone (%d < rating < %d), skipping", completion.id, rating,
                               self.facet.max_rating, self.facet.min_rating)

        if not result.samples:
            result.failure_reasons.append(
                f"No completions qualified (min_rating={self.facet.min_rating}, max_rating={self.facet.max_rating})")
        else:
            self.log.debug("Generated %d good and %d bad KTO samples for sample %d", good_count, bad_count, sample.id)

        return result
