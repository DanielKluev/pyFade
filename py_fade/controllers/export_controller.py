"""
Middle layer to control export operation.
Handles the logic of exporting data from pyFADE to various formats.
"""

import logging
import pathlib
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

        # Get eligible samples based on facet configuration
        eligible_samples = self._get_eligible_samples()

        if not eligible_samples:
            raise ValueError("No eligible samples found for export")

        # Convert to ShareGPT format
        conversations = []
        for sample in eligible_samples:
            conversation = self._sample_to_conversation(sample)
            if conversation:
                conversations.append(conversation)

        # Write using ShareGPTFormat
        sharegpt_format = ShareGPTFormat(self.output_path)
        sharegpt_format.set_samples(conversations)
        sharegpt_format.save()

        self.log.info("Export completed: %d samples written to %s", len(conversations), self.output_path)
        return len(conversations)

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
