"""
Read and write ShareGPT-formatted conversation samples.

ShareGPT:
 - Each sample is a JSON object with 'conversations' list.
 - Each conversation entry has 'from' (system/human/gpt) and 'value' (text).

Packed as parquet, JSON or JSONL files.
If JSON, root element is a list of samples.
"""

import logging
import pathlib

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.data_formats.base_data_format import BaseDataFormat

class ShareGPTFormat(BaseDataFormat):
    """
    ShareGPTFormat handles reading and writing datasets in ShareGPT format.
    Supports JSON, JSONL, and Parquet file formats.
    """
    samples: list[CommonConversation]
    def __init__(self, serialized_file_path: pathlib.Path | str) -> None:
        """
        Initialize with path to the ShareGPT formatted file.
        Infer format (JSON or JSONL) from file extension.

        File is allowed to not exist yet (for writing).
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.set_path(serialized_file_path)
        self._loaded = False

    def set_path(self, path: pathlib.Path | str) -> None:
        """Set the base path for this data format instance."""
        self.serialized_file_path = pathlib.Path(path)
        if self.serialized_file_path.suffix == ".jsonl":
            self.format = "jsonl"
        elif self.serialized_file_path.suffix == ".json":
            self.format = "json"
        elif self.serialized_file_path.suffix == ".parquet":
            self.format = "parquet"
        else:
            raise ValueError(
                f"Unsupported file extension '{self.serialized_file_path.suffix}'. "
                "Use .json or .jsonl for ShareGPT format."
            )

    def load(self, file_path: str|pathlib.Path|None = None) -> int:
        """
        Load samples from the ShareGPT formatted file.
        """
        if file_path:
            self.set_path(file_path)

        if not self.serialized_file_path.exists():
            raise FileNotFoundError(f"File does not exist: {self.serialized_file_path}")

        if self.format == "jsonl":
            self._load_jsonl()
        elif self.format == "json":
            self._load_json()
        elif self.format == "parquet":
            self._load_parquet()
        else:
            raise ValueError(f"Unsupported format '{self.format}'")

        self._loaded = True
        return len(self._samples)