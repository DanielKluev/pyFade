"""
Kahneman-Tversky Optimization (KTO) format support.

For KTO, TRL library expects data in the following format:
{
    "prompt": [messages list],
    "completion": [messages list],
    "label": true/false  (true for good, false for bad)
}

This is used for binary preference optimization where samples are labeled as good or bad
rather than paired chosen/rejected comparisons.
"""
import pathlib
import json
from dataclasses import dataclass

from py_fade.data_formats.base_data_classes import CommonConversation
from py_fade.data_formats.base_data_format import BaseDataFormat


@dataclass
class KTOSample:
    """
    A single KTO training sample with prompt, completion, and label.
    """
    prompt: CommonConversation
    completion: str
    label: bool  # True for good, False for bad


class KTODataFormat(BaseDataFormat):
    """
    Data format for Kahneman-Tversky Optimization (KTO) training.
    """

    def __init__(self, file_path: str | pathlib.Path):
        """
        Initialize KTO data format.

        Args:
            file_path: Path to save KTO data to
        """
        self.file_path = pathlib.Path(file_path)
        self._samples: list[KTOSample] = []

    def set_samples(self, samples: list[KTOSample]) -> None:
        """
        Set the KTO samples to be saved.

        Args:
            samples: List of KTO samples
        """
        self._samples = samples

    @property
    def samples(self) -> list[KTOSample]:
        """
        Get the current KTO samples.

        Returns:
            List of KTO samples
        """
        return self._samples

    def load(self, file_path: str | pathlib.Path | None = None) -> int:
        """
        Load KTO samples from file (not implemented yet).

        Args:
            file_path: Path to load from

        Returns:
            Number of samples loaded
        """
        raise NotImplementedError("KTO format loading is not yet implemented")

    def save(self, file_path: str | pathlib.Path | None = None, output_format: str = "jsonl") -> int:
        """
        Save all samples in KTO format to the specified file as `output_format`.

        Each entry is a JSON object with "prompt", "completion" and "label" fields.
        Both prompt and completion are lists of message dicts in ShareGPT format.
        Label is a boolean (true for good, false for bad).

        Args:
            file_path: Path to save to (uses instance path if None)
            output_format: Output format, only "jsonl" is currently supported

        Returns:
            Number of samples saved
        """
        if output_format != "jsonl":
            raise ValueError(f"KTODataFormat.save: Unsupported format '{output_format}', only 'jsonl' is supported.")

        if not self._samples:
            raise ValueError("KTODataFormat.save: No samples to save.")

        save_path = pathlib.Path(file_path) if file_path else self.file_path

        with open(save_path, "w", encoding="utf-8") as f:
            for sample in self._samples:
                # Convert prompt conversation to messages list
                prompt_messages = [{"role": msg.role, "content": msg.content} for msg in sample.prompt.messages]

                # Create completion as a single assistant message
                completion_messages = [{"role": "assistant", "content": sample.completion}]

                entry = {
                    "prompt": prompt_messages,
                    "completion": completion_messages,
                    "label": sample.label,
                }
                f.write(json.dumps(entry, ensure_ascii=False, indent=None) + "\n")

        return len(self._samples)
