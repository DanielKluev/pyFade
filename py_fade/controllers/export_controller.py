"""
Middle layer to control export operation.
Handles the logic of exporting data from pyFADE to various formats.
"""

import logging
import pathlib
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import exists

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.sample import Sample
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.data_formats.base_data_classes import CommonMessage, CommonConversation
from py_fade.data_formats.share_gpt_format import ShareGPTFormat
from py_fade.data_formats.facet_backup import FacetBackupFormat

if TYPE_CHECKING:
    from py_fade.app import PyFadeApp
    from py_fade.dataset.export_template import ExportTemplate
    from py_fade.dataset.facet import Facet


@dataclass
class SampleExportInfo:
    """
    Information about a sample in export results.
    """

    sample_id: int
    sample_title: str
    group_path: str | None


@dataclass
class FacetExportSummary:
    """
    Summary of export results for a single facet.
    """

    facet_id: int
    facet_name: str
    exported_samples: list[SampleExportInfo] = field(default_factory=list)
    failed_samples: list[tuple[SampleExportInfo, list[str]]] = field(default_factory=list)  # (sample, reasons)


@dataclass
class ExportResults:
    """
    Comprehensive results from an export operation.
    """

    total_exported: int = 0
    facet_summaries: list[FacetExportSummary] = field(default_factory=list)


class ExportController:
    """
    ExportController manages the export of data from pyFADE into datasets of various formats.

    Export is done via templates, which define what samples and completions to include,
    and how to structure the output data. Also supports direct facet backup export.
    """

    def __init__(self, app: "PyFadeApp", dataset: "DatasetDatabase", export_template: "ExportTemplate | None" = None) -> None:
        """
        Initialize the controller, binding to the app, dataset, and optionally export template.
        
        Args:
            app: The main application instance
            dataset: Dataset database to export from
            export_template: Export template to use (required for template-based export, optional for facet backup)
        """
        self.log = logging.getLogger("ExportController")
        self.app = app
        self.dataset = dataset
        self.export_template = export_template
        self.output_path = None
        self.export_results: ExportResults | None = None

    def set_output_path(self, path: pathlib.Path) -> None:
        """
        Set the output path for export.
        """
        self.output_path = path
        self.log.info("Set export output path: %s", path)

    def run_export(self) -> int:
        """
        Run the export based on the template configuration.
        Returns the number of samples exported.
        """
        if not self.export_template:
            raise ValueError("Export template must be set for template-based export")

        if not self.output_path:
            raise ValueError("Output path must be set before running export")

        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        # Initialize export results
        self.export_results = ExportResults()

        # Process each facet in the template
        conversations = []
        exported_sample_ids = set()  # Track which samples have been exported

        for facet_config in self.export_template.facets_json:
            facet_id = facet_config["facet_id"]

            # Get the facet object
            from py_fade.dataset.facet import Facet  # pylint: disable=import-outside-toplevel
            facet = Facet.get_by_id(self.dataset, facet_id)
            if not facet:
                self.log.warning("Facet %d not found, skipping", facet_id)
                continue

            # Create facet summary
            facet_summary = FacetExportSummary(facet_id=facet.id, facet_name=facet.name)
            self.export_results.facet_summaries.append(facet_summary)

            # Get thresholds (use facet defaults if not overridden)
            min_rating = facet_config.get("min_rating")
            if min_rating is None:
                min_rating = facet.min_rating
            min_logprob = facet_config.get("min_logprob")
            if min_logprob is None:
                min_logprob = facet.min_logprob_threshold
            avg_logprob = facet_config.get("avg_logprob")
            if avg_logprob is None:
                avg_logprob = facet.avg_logprob_threshold

            # Get samples for this facet
            samples = facet.get_samples(self.dataset)

            # Apply ordering
            order = facet_config.get("order", "random")
            if order == "newest":
                samples = sorted(samples, key=lambda s: s.date_created, reverse=True)
            elif order == "oldest":
                samples = sorted(samples, key=lambda s: s.date_created)
            elif order == "random":
                samples = list(samples)
                random.shuffle(samples)

            # Apply limit
            limit_type = facet_config.get("limit_type", "percentage")
            limit_value = facet_config.get("limit_value", 100)
            if limit_type == "percentage":
                max_samples = max(1, int(len(samples) * limit_value / 100.0))
            else:
                max_samples = int(limit_value)

            # Process samples for this facet
            exported_count = 0
            for sample in samples:
                if exported_count >= max_samples:
                    break

                # Skip if already exported by another facet
                if sample.id in exported_sample_ids:
                    continue

                # Try to convert sample with threshold checking
                conversation, failure_reasons = self._sample_to_conversation_with_validation(sample, facet, min_rating, min_logprob,
                                                                                             avg_logprob)

                sample_info = SampleExportInfo(
                    sample_id=sample.id,
                    sample_title=sample.title,
                    group_path=sample.group_path,
                )

                if conversation:
                    conversations.append(conversation)
                    exported_sample_ids.add(sample.id)
                    facet_summary.exported_samples.append(sample_info)
                    exported_count += 1
                else:
                    facet_summary.failed_samples.append((sample_info, failure_reasons))

        # Write using ShareGPTFormat
        if not conversations:
            raise ValueError("No eligible samples found for export")

        sharegpt_format = ShareGPTFormat(self.output_path)
        sharegpt_format.set_samples(conversations)
        sharegpt_format.save()

        self.export_results.total_exported = len(conversations)
        self.log.info("Export completed: %d samples written to %s", len(conversations), self.output_path)
        return len(conversations)

    def _sample_to_conversation_with_validation(self, sample: Sample, facet: "Facet", min_rating: int, min_logprob: float,
                                                avg_logprob: float) -> tuple[CommonConversation | None, list[str]]:
        """
        Convert a Sample to a CommonConversation with threshold validation.
        
        Args:
            sample: Sample to convert
            facet: Facet for which to find rated completions
            min_rating: Minimum rating threshold
            min_logprob: Minimum logprob threshold
            avg_logprob: Average logprob threshold
            
        Returns:
            Tuple of (conversation or None, list of failure reasons)
        """
        if not sample.prompt_revision or not sample.prompt_revision.completions:
            return None, ["No prompt revision or completions"]

        # Get completions rated for this facet
        rated_completions = []
        for completion in sample.prompt_revision.completions:
            rating_obj = completion.rating_for_facet(facet)
            if rating_obj:
                rated_completions.append((completion, rating_obj.rating))

        if not rated_completions:
            return None, ["No rated completions found"]

        # Find completions that meet rating threshold
        high_rated = [comp for comp, rating in rated_completions if rating >= min_rating]

        if not high_rated:
            max_rating = max(rating for _, rating in rated_completions)
            return None, [f"No completion with rating >= {min_rating} (max rating: {max_rating})"]

        # For exports, we need to pick a model to check logprobs
        # Use the first available provider model
        target_model_id = None
        if hasattr(self.app, 'providers_manager') and self.app.providers_manager.model_provider_map:
            target_model_id = list(self.app.providers_manager.model_provider_map.keys())[0]

        # Check logprob thresholds for high-rated completions
        valid_completions = []
        for completion in high_rated:
            if target_model_id:
                logprobs = completion.get_logprobs_for_model_id(target_model_id)
                if logprobs and logprobs.min_logprob >= min_logprob and logprobs.avg_logprob >= avg_logprob:
                    valid_completions.append((completion, logprobs))
            else:
                # No model available, skip logprob check
                valid_completions.append((completion, None))

        if not valid_completions:
            reasons = ["No high-rated completion meets logprob thresholds"]
            for completion in high_rated:
                if target_model_id:
                    logprobs = completion.get_logprobs_for_model_id(target_model_id)
                    if not logprobs:
                        reasons.append(f"  Completion {completion.id}: No logprobs for target model")
                    else:
                        if logprobs.min_logprob < min_logprob:
                            reasons.append(f"  Completion {completion.id}: min_logprob {logprobs.min_logprob:.3f} < {min_logprob}")
                        if logprobs.avg_logprob < avg_logprob:
                            reasons.append(f"  Completion {completion.id}: avg_logprob {logprobs.avg_logprob:.3f} < {avg_logprob}")
            return None, reasons

        # Get best valid completion (highest rated among those that pass thresholds)
        best_completion = max(valid_completions, key=lambda x: self._get_completion_rating(x[0], facet))[0]

        # Create conversation messages
        messages = [
            CommonMessage(role="user", content=sample.prompt_revision.prompt_text),
            CommonMessage(role="assistant", content=best_completion.completion_text)
        ]

        return CommonConversation(messages=messages), []

    def _get_completion_rating(self, completion: PromptCompletion, facet: "Facet") -> int:
        """
        Get the rating for a completion in the given facet.
        
        Args:
            completion: Completion to get rating for
            facet: Facet to check rating for
            
        Returns:
            Rating value, or 0 if no rating found
        """
        rating_obj = completion.rating_for_facet(facet)
        return rating_obj.rating if rating_obj else 0

    def _get_eligible_samples(self) -> list[Sample]:
        """
        Get samples that have at least one completion with a rating for the chosen facet.
        """
        if not self.export_template:
            raise ValueError("Export template required for getting eligible samples")

        # Get facet IDs from template configuration
        facet_ids = [facet["facet_id"] for facet in self.export_template.facets_json]

        if not facet_ids:
            # If no facets specified, return all samples
            return self.dataset.session.query(Sample).all()

        # Query samples that have completions with ratings for specified facets
        samples_with_ratings = (self.dataset.session.query(Sample).filter(
            exists().where(PromptCompletion.prompt_revision_id == Sample.prompt_revision_id).where(
                exists().where(PromptCompletionRating.prompt_completion_id == PromptCompletion.id).where(
                    PromptCompletionRating.facet_id.in_(facet_ids)))).all())

        return samples_with_ratings

    def _sample_to_conversation(self, sample: Sample) -> CommonConversation | None:
        """
        Convert a Sample to a CommonConversation for ShareGPT format.
        For SFT, use the highest-rated completion in the specified facet.
        """
        if not self.export_template:
            raise ValueError("Export template required for sample conversion")

        if not sample.prompt_revision or not sample.prompt_revision.completions:
            return None

        # Get facet IDs from template
        facet_ids = [facet["facet_id"] for facet in self.export_template.facets_json]

        # Find the best completion
        best_completion = None
        best_rating = -1

        for completion in sample.prompt_revision.completions:
            for rating in completion.ratings:
                if rating.facet_id in facet_ids and rating.rating > best_rating:
                    best_rating = rating.rating
                    best_completion = completion

        if not best_completion:
            # No rated completion found
            return None

        # Create conversation messages
        messages = [
            CommonMessage(role="user", content=sample.prompt_revision.prompt_text),
            CommonMessage(role="assistant", content=best_completion.completion_text)
        ]

        return CommonConversation(messages=messages)

    def export_facet_backup(self, facet_id: int) -> int:
        """
        Export a complete facet backup to the configured output path.
        
        This method creates a complete backup of a facet including all associated
        data (samples, completions, ratings) rather than using export templates.
        
        Args:
            facet_id: ID of the facet to backup
            
        Returns:
            Number of items exported (always 1 for facet backup)
        """
        if not self.output_path:
            raise ValueError("Output path must be set before running facet backup export")

        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        # Get the facet - import here to avoid circular dependency
        from py_fade.dataset.facet import Facet  # pylint: disable=import-outside-toplevel
        facet = Facet.get_by_id(self.dataset, facet_id)
        if not facet:
            raise ValueError(f"Facet with ID {facet_id} not found")

        self.log.info("Starting facet backup export for facet: %s (ID: %d)", facet.name, facet.id)

        # Create backup format instance
        backup_format = FacetBackupFormat(self.output_path)
        backup_data = backup_format.create_backup_from_facet(self.dataset, facet)

        # Save the backup
        backup_format.save()

        self.log.info("Facet backup export completed: %s exported to %s", facet.name, self.output_path)
        self.log.info("Backup contains: %d samples, %d completions, %d ratings", len(backup_data.samples), len(backup_data.completions),
                      len(backup_data.ratings))

        return 1

    @classmethod
    def create_for_facet_backup(cls, app: "PyFadeApp", dataset: "DatasetDatabase") -> "ExportController":
        """
        Create an ExportController instance specifically for facet backup export.
        
        Args:
            app: The main application instance
            dataset: Dataset database to export from
            
        Returns:
            ExportController instance without an export template
        """
        return cls(app, dataset, export_template=None)
