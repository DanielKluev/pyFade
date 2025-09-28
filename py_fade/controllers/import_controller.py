"""
Middle layer to control import operation.
Handles the logic of importing data from various sources into the dataset.
"""

import logging
import pathlib
from py_fade.app import PyFadeApp
from py_fade.dataset.dataset import DatasetDatabase

from py_fade.data_formats.lm_eval_results import LMEvalResult

SUPPORTED_FORMATS = {
    "lm_eval_results": LMEvalResult,
}

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

    def add_source(self, source_path: pathlib.Path|str, format: str | None = None) -> None:
        """
        Add a new data source to the controller.
        Detects format if not provided, binds appropriate parser.
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
        self.log.info(f"Added source {source_path} with format {format}")

    def detect_format(self, source_path: pathlib.Path) -> str | None:
        """
        Detect the format of the data source based on file extension or content.
        Currently supports detection for lm_eval_results format.
        """
        if source_path.suffix in {".json", ".jsonl"}:
            # Simple heuristic: check if file contains lm_eval_results structure
            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    first_line = f.readline()
                    if '"results"' in first_line and '"task"' in first_line:
                        return "lm_eval_results"
            except Exception as e:
                self.log.warning(f"Failed to read source for format detection: {e}")
        
        # Add more format detection logic here as needed
        
        return None
        
