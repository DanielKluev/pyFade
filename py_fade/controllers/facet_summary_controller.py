"""
Controller for generating facet summary reports.

This module provides functionality to analyze facet samples and generate reports
showing which samples are ready for SFT and DPO training based on completion ratings
and logprob thresholds.
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from py_fade.controllers.dpo_controller import DPOController
from py_fade.controllers.facet_utils import get_rated_completions
from py_fade.dataset.completion import PromptCompletion
from py_fade.providers.providers_manager import MappedModel

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.dataset.sample import Sample


@dataclass
class UnfinishedSampleInfo:
    """
    Information about an unfinished sample that doesn't meet training criteria.
    """

    sample_id: int
    sample_name: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class FacetSummaryReport:
    """
    Summary report for a facet showing training readiness statistics.
    """

    facet_name: str
    target_model_id: str
    min_rating: int
    min_logprob_threshold: float
    avg_logprob_threshold: float

    # SFT statistics
    sft_total_samples: int = 0
    sft_finished_samples: int = 0
    sft_unfinished_samples: int = 0
    sft_total_loss: float = 0.0
    sft_unfinished_details: list[UnfinishedSampleInfo] = field(default_factory=list)

    # DPO statistics
    dpo_total_samples: int = 0
    dpo_finished_samples: int = 0
    dpo_unfinished_samples: int = 0
    dpo_total_loss: float = 0.0
    dpo_unfinished_details: list[UnfinishedSampleInfo] = field(default_factory=list)


class FacetSummaryController:
    """
    Controller for generating facet summary reports.

    Analyzes samples in a facet to determine their readiness for SFT and DPO training
    based on completion ratings and logprob thresholds.
    """
    target_model: MappedModel

    def __init__(self, app: "pyFadeApp", dataset: "DatasetDatabase", facet: "Facet", target_model: MappedModel):
        """
        Initialize the controller.

        Args:
            app: The main application instance
            dataset: Dataset database to analyze
            facet: Facet to generate report for
            target_model_id: Target model ID to check logprobs against
        """
        self.log = logging.getLogger("FacetSummaryController")
        self.app = app
        self.dataset = dataset
        self.facet = facet
        self.target_model = target_model

    def generate_report(self) -> FacetSummaryReport:
        """
        Generate a comprehensive summary report for the facet.

        Returns:
            FacetSummaryReport with statistics and details
        """
        self.log.info("Generating facet summary report for facet '%s' and model '%s'", self.facet.name, self.target_model.path)

        report = FacetSummaryReport(
            facet_name=self.facet.name,
            target_model_id=self.target_model.model_id,
            min_rating=self.facet.min_rating,
            min_logprob_threshold=self.facet.min_logprob_threshold,
            avg_logprob_threshold=self.facet.avg_logprob_threshold,
        )

        # Get all samples for this facet
        samples = self.facet.get_samples(self.dataset)

        # Analyze each sample for SFT and DPO readiness
        for sample in samples:
            if sample.is_unfinished(self.dataset):
                self.log.info("Skipping unfinished sample %s [%s]", sample.id, sample.title)
                continue  # Skip unfinished samples
            self._analyze_sample_for_sft(sample, report)
            self._analyze_sample_for_dpo(sample, report)

        self.log.info("Report generated: SFT %d/%d finished, DPO %d/%d finished", report.sft_finished_samples, report.sft_total_samples,
                      report.dpo_finished_samples, report.dpo_total_samples)

        return report

    def _analyze_sample_for_sft(self, sample: "Sample", report: FacetSummaryReport) -> None:
        """
        Analyze a sample for SFT training readiness.

        For SFT, there should be at least one completion with:
        - Rating >= min_rating
        - min_logprob >= min_logprob_threshold (for target model)
        - avg_logprob >= avg_logprob_threshold (for target model)

        Args:
            sample: Sample to analyze
            report: Report to update with results
        """
        report.sft_total_samples += 1

        # Get completions with ratings for this facet
        rated_completions = get_rated_completions(sample, self.facet)

        if not rated_completions:
            report.sft_unfinished_samples += 1
            report.sft_unfinished_details.append(
                UnfinishedSampleInfo(
                    sample_id=sample.id,
                    sample_name=f"Sample #{sample.id} {sample.title}",
                    reasons=["No rated completions found"],
                ))
            return

        # Find completions that meet rating threshold
        high_rated = [comp for comp, rating in rated_completions if rating >= self.facet.min_rating]

        if not high_rated:
            report.sft_unfinished_samples += 1
            max_rating = max(rating for _, rating in rated_completions)
            report.sft_unfinished_details.append(
                UnfinishedSampleInfo(
                    sample_id=sample.id,
                    sample_name=f"Sample #{sample.id} {sample.title}",
                    reasons=[f"No completion with rating >= {self.facet.min_rating} (max rating: {max_rating})"],
                ))
            return

        # Check logprob thresholds for high-rated completions
        valid_completions = []
        for completion in high_rated:
            logprobs = completion.get_logprobs_for_model_id(self.target_model.model_id)
            if (logprobs and logprobs.min_logprob >= self.facet.min_logprob_threshold and
                    logprobs.avg_logprob >= self.facet.avg_logprob_threshold):
                valid_completions.append((completion, logprobs))

        if not valid_completions:
            report.sft_unfinished_samples += 1
            reasons = ["No high-rated completion meets logprob thresholds"]
            # Add details about why completions failed
            for completion in high_rated:
                logprobs = completion.get_logprobs_for_model_id(self.target_model.model_id)
                if not logprobs:
                    reasons.append(f"  Completion {completion.id}: No logprobs for target model")
                else:
                    if logprobs.min_logprob < self.facet.min_logprob_threshold:
                        reasons.append(
                            f"  Completion {completion.id}: min_logprob {logprobs.min_logprob:.3f} < {self.facet.min_logprob_threshold}")
                    if logprobs.avg_logprob < self.facet.avg_logprob_threshold:
                        reasons.append(
                            f"  Completion {completion.id}: avg_logprob {logprobs.avg_logprob:.3f} < {self.facet.avg_logprob_threshold}")

            report.sft_unfinished_details.append(
                UnfinishedSampleInfo(
                    sample_id=sample.id,
                    sample_name=f"Sample #{sample.id} {sample.title}",
                    reasons=reasons,
                ))
            return

        # Sample is ready for SFT - find best completion
        # Best is highest rated among those that pass thresholds
        _, best_logprobs = max(valid_completions, key=lambda x: self._get_completion_rating(x[0]))

        report.sft_finished_samples += 1
        report.sft_total_loss += abs(best_logprobs.avg_logprob)

    def _analyze_sample_for_dpo(self, sample: "Sample", report: FacetSummaryReport) -> None:
        """
        Analyze a sample for DPO training readiness using DPOController.

        Uses the unified DPO pair generation logic to determine if sample can produce
        any valid DPO training pairs.

        Args:
            sample: Sample to analyze
            report: Report to update with results
        """
        report.dpo_total_samples += 1

        # Use DPO controller to check if sample can generate any pairs
        dpo_controller = DPOController(self.dataset, self.facet, self.target_model.model_id)
        result = dpo_controller.generate_pairs_for_sample(sample)

        if result.pairs:
            # Sample is ready for DPO - has at least one valid pair
            report.dpo_finished_samples += 1

            # Calculate average loss across all chosen completions in generated pairs
            # Get unique chosen completions and their logprobs
            chosen_completions = set()
            for pair in result.pairs:
                # Find the completion that matches this chosen text
                for comp in sample.completions:
                    if comp.completion_text == pair.chosen:
                        chosen_completions.add(comp)
                        break

            # Calculate total loss from unique chosen completions
            total_loss = 0.0
            for comp in chosen_completions:
                logprobs = comp.get_logprobs_for_model_id(self.target_model.model_id)
                if logprobs and logprobs.avg_logprob is not None:
                    total_loss += abs(logprobs.avg_logprob)

            report.dpo_total_loss += total_loss
        else:
            # Sample is not ready for DPO
            report.dpo_unfinished_samples += 1
            report.dpo_unfinished_details.append(
                UnfinishedSampleInfo(
                    sample_id=sample.id,
                    sample_name=f"Sample #{sample.id} {sample.title}",
                    reasons=result.failure_reasons,
                ))

    def _get_completion_rating(self, completion: PromptCompletion) -> int:
        """
        Get the rating for a completion in the current facet.

        Args:
            completion: Completion to get rating for

        Returns:
            Rating value, or 0 if no rating found
        """
        rating_obj = completion.rating_for_facet(self.facet)
        return rating_obj.rating if rating_obj else 0
