"""
Middle layer to control import operation.
Handles the logic of importing data from various sources into the dataset.
"""

import dataclasses
import json
import logging
import pathlib
from typing import TYPE_CHECKING

from py_fade.app import PyFadeApp
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.sample import Sample  
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.data_formats.lm_eval_results import LMEvalResult

if TYPE_CHECKING:
    from py_fade.data_formats.lm_eval_results import LMEvalSample

SUPPORTED_FORMATS = {
    "lm_eval_results": LMEvalResult,
}


@dataclasses.dataclass
class ImportSummary:
    """Summary of import operation results."""
    imported_samples: int = 0
    imported_completions: int = 0

class ImportController:
    """
    ImportController manages the import of data into the dataset.
    Handles format detection, samples extraction, filtering, validation, and insertion.
    """
    def __init__(self, app: "PyFadeApp", dataset: "DatasetDatabase") -> None:
        """
        Initialize the controller with references to the app and dataset.
        """
        self.log = logging.getLogger("ImportController")
        self.app = app
        self.dataset = dataset
        self.sources = []  # List of configured data parsers
        self.active_records = []  # Currently selected records for import
        self.filters = []  # Applied filters
        self.target_facet = None  # Facet for ratings
        self.rating_config = {}  # Rating configuration
        self.import_summary = ImportSummary()

    def add_source(self, source_path: pathlib.Path|str, format: str | None = None) -> LMEvalResult:
        """
        Add a new data source to the controller.
        Detects format if not provided, binds appropriate parser.
        Returns the parser instance so caller can inspect properties like model_id.
        """
        source_path = pathlib.Path(source_path)
        if not source_path or not source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        
        if not format:
            format = self.detect_format(source_path)
            if not format:
                raise ValueError(f"Could not detect format for source: {source_path}")
            
        if format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{format}' for source: {source_path}")
        
        parser_class = SUPPORTED_FORMATS[format]
        parser_instance = parser_class(source_path)
        self.sources.append(parser_instance)
        self.log.info("Added source %s with format %s", source_path, format)
        return parser_instance

    def detect_format(self, source_path: pathlib.Path) -> str | None:
        """
        Detect the format of the data source based on file extension or content.
        Currently supports detection for lm_eval_results format.
        """
        if source_path.suffix in {".json", ".jsonl"}:
            # Parse JSON to check for lm_eval_results structure
            try:
                import json
                with open(source_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Check for lm_eval_results structure: "results" and "configs" keys
                        if "results" in data and "configs" in data:
                            return "lm_eval_results"
            except Exception as e:
                self.log.warning("Failed to read source for format detection: %s", e)
        
        # Add more format detection logic here as needed
        
        return None
        
    def load_sources(self) -> None:
        """
        Load all added sources and cache their samples.
        """
        self.active_records = []
        for source in self.sources:
            source.load()
            self.active_records.extend(source.samples)
        self.log.info("Loaded %d total records from %d sources", len(self.active_records), len(self.sources))

    def total_active_records(self) -> int:
        """
        Return the count of currently selected/active sample records.
        """
        return len(self.active_records)

    def add_filter(self, filter_type: str, config: dict) -> None:
        """
        Configure a filter that compares sources.
        """
        filter_config = {"type": filter_type, "config": config}
        self.filters.append(filter_config)
        self.log.info("Added filter: %s with config: %s", filter_type, config)

    def apply_filters(self) -> None:
        """
        Apply configured filters to loaded records.
        """
        for filter_config in self.filters:
            if filter_config["type"] == "paired_comparison":
                self._apply_paired_comparison_filter(filter_config["config"])
        self.log.info("Applied filters, %d records remaining", len(self.active_records))

    def _apply_paired_comparison_filter(self, config: dict) -> None:
        """
        Apply paired comparison filter to reduce to chosen subset.
        For "new_failure" filter type, compare two sources and keep only the regressions.
        """
        if len(self.sources) != 2:
            raise ValueError("Paired comparison requires exactly 2 sources")
        
        filter_type = config.get("filter_type", "new_failure")
        source1, source2 = self.sources
        
        # Perform comparison - source1 is current (tuned), source2 is baseline
        comparison = source1.compare(source2)
        
        if filter_type == "new_failure":
            # Keep the new failures - these include both the current (incorrect) 
            # and baseline (correct) samples for the same prompt
            new_failures = comparison["new_failure"]
            self.active_records = []
            
            # For each new failure, add both the current and baseline samples
            for current_sample in new_failures:
                # Add the current (incorrect) sample
                self.active_records.append(current_sample)
                # Add the corresponding baseline (correct) sample
                baseline_sample = source2.samples_by_hash.get(current_sample.prompt_hash)
                if baseline_sample:
                    self.active_records.append(baseline_sample)
                    
        self.log.info("Paired comparison filter applied, reduced to %d records", len(self.active_records))

    def set_facet(self, facet: "Facet") -> None:
        """
        Mark the facet under which to record ratings.
        """
        self.target_facet = facet
        self.log.info("Set target facet: %s (id=%d)", facet.name, facet.id)

    def set_ratings(self, correct: int, incorrect: int, chosen: int, rejected: int) -> None:
        """
        Configure rating values for outcomes.
        """
        self.rating_config = {
            "correct": correct,
            "incorrect": incorrect, 
            "chosen": chosen,
            "rejected": rejected
        }
        self.log.info("Set ratings: correct=%d, incorrect=%d, chosen=%d, rejected=%d", 
                     correct, incorrect, chosen, rejected)

    def import_to_dataset(self) -> int:
        """
        Create Sample, PromptRevision, PromptCompletion and PromptCompletionRating rows 
        based on current active selection.
        Returns the number of imported records.
        """
        if not self.target_facet:
            raise ValueError("Target facet must be set before importing")
        
        if not self.rating_config:
            raise ValueError("Rating configuration must be set before importing")

        imported_count = 0
        samples_created = 0
        completions_created = 0
        
        # Group records by prompt hash to handle paired records
        records_by_hash = {}
        for record in self.active_records:
            prompt_hash = record.prompt_hash
            if prompt_hash not in records_by_hash:
                records_by_hash[prompt_hash] = []
            records_by_hash[prompt_hash].append(record)

        for prompt_hash, records in records_by_hash.items():
            # Create or get PromptRevision
            prompt_text = records[0].prompt_text
            prompt_revision = PromptRevision.get_or_create(
                self.dataset, 
                prompt_text,
                context_length=self.app.config.default_context_length,
                max_tokens=self.app.config.default_max_tokens
            )

            # Create Sample if it doesn't exist
            sample = Sample.create_if_unique(
                self.dataset,
                title=f"Import: {prompt_hash[:8]}",
                prompt_revision=prompt_revision,
                group_path="lm_eval_import"
            )
            if sample:
                samples_created += 1

            # Create completions for each record
            for record in records:
                # Create PromptCompletion
                completion = PromptCompletion(
                    prompt_revision=prompt_revision,
                    sha256=PromptCompletion._compute_sha256(record.response_text),
                    model_id=self._find_model_id_for_record(record),
                    temperature=0.0,
                    top_k=1,
                    prefill=None,
                    beam_token=None,
                    completion_text=record.response_text,
                    tags=None,
                    context_length=self.app.config.default_context_length,
                    max_tokens=self.app.config.default_max_tokens,
                    is_truncated=False,
                    is_archived=False
                )
                self.dataset.session.add(completion)
                self.dataset.session.flush()  # Get the ID
                completions_created += 1

                # Set rating based on success
                is_success = record.is_success()
                if is_success is not None:
                    rating = self.rating_config["correct"] if is_success else self.rating_config["incorrect"]
                    PromptCompletionRating.set_rating(
                        self.dataset, completion, self.target_facet, rating
                    )

                imported_count += 1

        self.dataset.session.commit()
        
        # Update summary
        self.import_summary = ImportSummary(
            imported_samples=samples_created,
            imported_completions=completions_created
        )
        
        self.log.info("Import completed: %d records imported, %d samples created, %d completions created",
                     imported_count, samples_created, completions_created)
        return imported_count

    def _find_model_id_for_record(self, record: "LMEvalSample") -> str:
        """
        Find the model ID for a specific record by checking which source it belongs to.
        """
        for source in self.sources:
            if record.prompt_hash in source.samples_by_hash:
                return source.model_id or "unknown"
        return "unknown"

    @staticmethod
    def _compute_sha256(text: str) -> str:
        """Compute SHA256 hash of text."""
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
        
