"""
Facet Backup JSON data format.

This module provides functionality to export and import complete facet data,
including the facet definition, associated tags, samples, completions, and ratings.

The JSON format includes:
- pyFADE version information
- Format version for future compatibility
- Complete facet data with metadata
- All tags referenced by samples/completions in this facet
- All samples associated with the selected facet (via ratings)
- All completions with ratings for the selected facet
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import pathlib
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from py_fade.data_formats.base_data_format import BaseDataFormat

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet

MODULE_LOGGER = logging.getLogger(__name__)

# Current format version - increment when making breaking changes
FACET_BACKUP_FORMAT_VERSION = 1

# pyFADE version from pyproject.toml
PYFADE_VERSION = "0.0.1"


@dataclasses.dataclass(slots=True)
class FacetBackupData:
    """
    Complete data structure for a facet backup.
    
    Contains all information needed to restore a facet with full fidelity,
    including metadata, tags, samples, completions, and ratings.
    """
    pyfade_version: str
    format_version: int
    facet: Dict[str, Any]
    tags: List[Dict[str, Any]]
    samples: List[Dict[str, Any]]
    completions: List[Dict[str, Any]]
    ratings: List[Dict[str, Any]]
    export_timestamp: str


class FacetBackupFormat(BaseDataFormat):
    """
    Data format handler for Facet Backup JSON files.
    
    Provides export functionality to create complete facet backups and import
    functionality to restore facets from backup files.
    """

    def __init__(self, json_file_path: pathlib.Path | str | None = None) -> None:
        """
        Initialize the Facet Backup format handler.
        
        Args:
            json_file_path: Path to the JSON file for import/export operations
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self._backup_data: Optional[FacetBackupData] = None
        self._loaded = False

        if json_file_path:
            self.set_path(json_file_path)
        else:
            self.json_file_path: Optional[pathlib.Path] = None

    def set_path(self, path: pathlib.Path | str) -> None:
        """Set the file path for this backup format instance."""
        self.json_file_path = pathlib.Path(path)

        if self.json_file_path.suffix.lower() != ".json":
            self.log.warning("Facet backup files should use .json extension, got: %s", self.json_file_path.suffix)

    def create_backup_from_facet(self, dataset: "DatasetDatabase", facet: "Facet") -> FacetBackupData:
        """
        Create a complete backup data structure from a facet in the database.
        
        Args:
            dataset: The dataset database instance
            facet: The facet to backup
            
        Returns:
            FacetBackupData containing all related information
        """
        self.log.info("Creating backup for facet: %s (ID: %d)", facet.name, facet.id)

        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        # Export facet data
        facet_data = {
            "id": facet.id,
            "name": facet.name,
            "description": facet.description,
            "total_samples": facet.total_samples,
            "date_created": facet.date_created.isoformat() if facet.date_created else None
        }

        # Get all samples that have ratings for this facet
        from py_fade.dataset.sample import Sample
        from py_fade.dataset.completion_rating import PromptCompletionRating
        from py_fade.dataset.completion import PromptCompletion
        from py_fade.dataset.tag import Tag

        # Find samples through completion ratings for this facet
        samples_query = (dataset.session.query(Sample).join(Sample.prompt_revision).join(
            PromptCompletion, Sample.prompt_revision_id == PromptCompletion.prompt_revision_id).join(
                PromptCompletionRating, PromptCompletion.id == PromptCompletionRating.prompt_completion_id).filter(
                    PromptCompletionRating.facet_id == facet.id).distinct())

        samples = samples_query.all()
        self.log.debug("Found %d samples for facet %s", len(samples), facet.name)

        # Export samples data
        samples_data = []
        prompt_revision_ids = set()

        for sample in samples:
            sample_data = {
                "id": sample.id,
                "title": sample.title,
                "group_path": sample.group_path,
                "date_created": sample.date_created.isoformat() if sample.date_created else None,
                "prompt_revision": {
                    "id": sample.prompt_revision.id,
                    "prompt_text": sample.prompt_revision.prompt_text,
                    "sha256": sample.prompt_revision.sha256,
                    "context_length": sample.prompt_revision.context_length,
                    "max_tokens": sample.prompt_revision.max_tokens,
                    "date_created": sample.prompt_revision.date_created.isoformat() if sample.prompt_revision.date_created else None
                } if sample.prompt_revision else None
            }
            samples_data.append(sample_data)
            if sample.prompt_revision:
                prompt_revision_ids.add(sample.prompt_revision.id)

        # Get all completions for the prompt revisions of our samples, that have ratings for this facet
        completions_query = (dataset.session.query(PromptCompletion).join(
            PromptCompletionRating,
            PromptCompletion.id == PromptCompletionRating.prompt_completion_id).filter(PromptCompletionRating.facet_id == facet.id).filter(
                PromptCompletion.prompt_revision_id.in_(prompt_revision_ids)))

        completions = completions_query.all()
        self.log.debug("Found %d completions for facet %s", len(completions), facet.name)

        # Export completions data
        completions_data = []
        for completion in completions:
            completion_data = {
                "id": completion.id,
                "prompt_revision_id": completion.prompt_revision_id,
                "parent_completion_id": completion.parent_completion_id,
                "sha256": completion.sha256,
                "completion_text": completion.completion_text,
                "model_id": completion.model_id,
                "temperature": completion.temperature,
                "top_k": completion.top_k,
                "prefill": completion.prefill,
                "beam_token": completion.beam_token,
                "tags": completion.tags,
                "context_length": completion.context_length,
                "max_tokens": completion.max_tokens,
                "is_truncated": completion.is_truncated,
                "is_archived": completion.is_archived
            }
            completions_data.append(completion_data)

        # Get all ratings for this facet
        ratings_query = dataset.session.query(PromptCompletionRating).filter(PromptCompletionRating.facet_id == facet.id)
        ratings = ratings_query.all()
        self.log.debug("Found %d ratings for facet %s", len(ratings), facet.name)

        # Export ratings data
        ratings_data = []
        for rating in ratings:
            rating_data = {
                "id": rating.id,
                "prompt_completion_id": rating.prompt_completion_id,
                "facet_id": rating.facet_id,
                "rating": rating.rating
            }
            ratings_data.append(rating_data)

        # For now, export empty tags list - we'll implement tag association later
        # TODO: Implement proper tag collection based on sample/completion associations
        tags_data = []

        # Create the backup data structure
        backup_data = FacetBackupData(pyfade_version=PYFADE_VERSION, format_version=FACET_BACKUP_FORMAT_VERSION, facet=facet_data,
                                      tags=tags_data, samples=samples_data, completions=completions_data, ratings=ratings_data,
                                      export_timestamp=datetime.datetime.now().isoformat())

        self._backup_data = backup_data
        self.log.info("Created backup with %d samples, %d completions, %d ratings", len(samples_data), len(completions_data),
                      len(ratings_data))

        return backup_data

    def load(self, file_path: str | pathlib.Path | None = None) -> int:
        """
        Load facet backup data from a JSON file.
        
        Args:
            file_path: Path to JSON file, or None to use configured path
            
        Returns:
            Number of records loaded (always 1 for facet backup)
        """
        if file_path:
            self.set_path(file_path)

        if not self.json_file_path:
            raise ValueError("No file path specified for loading")

        if not self.json_file_path.exists():
            raise FileNotFoundError(f"Facet backup file does not exist: {self.json_file_path}")

        self.log.info("Loading facet backup from: %s", self.json_file_path)

        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate required fields
            required_fields = ['pyfade_version', 'format_version', 'facet', 'tags', 'samples', 'completions', 'ratings']

            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field in backup: {field}")

            # Validate format version
            if data['format_version'] > FACET_BACKUP_FORMAT_VERSION:
                raise ValueError(f"Backup format version {data['format_version']} is newer than "
                                 f"supported version {FACET_BACKUP_FORMAT_VERSION}")

            # Create backup data structure
            self._backup_data = FacetBackupData(pyfade_version=data['pyfade_version'], format_version=data['format_version'],
                                                facet=data['facet'], tags=data['tags'], samples=data['samples'],
                                                completions=data['completions'], ratings=data['ratings'],
                                                export_timestamp=data.get('export_timestamp', ''))

            self._loaded = True
            self.log.info("Loaded facet backup: %s with %d samples, %d completions, %d ratings", data['facet']['name'],
                          len(data['samples']), len(data['completions']), len(data['ratings']))

            return 1

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in facet backup file: {e}") from e
        except Exception as e:
            raise ValueError(f"Error loading facet backup: {e}") from e

    def save(self, file_path: str | pathlib.Path | None = None) -> int:
        """
        Save the current backup data to a JSON file.
        
        Args:
            file_path: Path to save to, or None to use configured path
            
        Returns:
            Number of records saved (always 1 for facet backup)
        """
        if not self._backup_data:
            raise ValueError("No backup data to save. Call create_backup_from_facet first.")

        if file_path:
            self.set_path(file_path)

        if not self.json_file_path:
            raise ValueError("No file path specified for saving")

        self.log.info("Saving facet backup to: %s", self.json_file_path)

        # Ensure parent directory exists
        self.json_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert dataclass to dict for JSON serialization
        data = {
            "pyfade_version": self._backup_data.pyfade_version,
            "format_version": self._backup_data.format_version,
            "facet": self._backup_data.facet,
            "tags": self._backup_data.tags,
            "samples": self._backup_data.samples,
            "completions": self._backup_data.completions,
            "ratings": self._backup_data.ratings,
            "export_timestamp": self._backup_data.export_timestamp
        }

        try:
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.log.info("Successfully saved facet backup with %d samples, %d completions, %d ratings", len(self._backup_data.samples),
                          len(self._backup_data.completions), len(self._backup_data.ratings))

            return 1

        except Exception as e:
            raise ValueError(f"Error saving facet backup: {e}") from e

    @property
    def backup_data(self) -> Optional[FacetBackupData]:
        """Return the loaded backup data."""
        return self._backup_data

    @property
    def is_loaded(self) -> bool:
        """Return True if backup data has been loaded."""
        return self._loaded

    def get_facet_name(self) -> Optional[str]:
        """Get the name of the facet in the backup, if loaded."""
        if self._backup_data:
            return self._backup_data.facet.get('name')
        return None

    def get_sample_count(self) -> int:
        """Get the number of samples in the backup."""
        if self._backup_data:
            return len(self._backup_data.samples)
        return 0

    def get_completion_count(self) -> int:
        """Get the number of completions in the backup."""
        if self._backup_data:
            return len(self._backup_data.completions)
        return 0

    def get_rating_count(self) -> int:
        """Get the number of ratings in the backup."""
        if self._backup_data:
            return len(self._backup_data.ratings)
        return 0
