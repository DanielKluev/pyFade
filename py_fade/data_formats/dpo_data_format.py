"""
Direct Preference Optimization (DPO) format support.

For DPO Transformers trainer expects data in the following format:
{
    "prompt": "<prompt text>",
    "chosen": "<chosen response>",
    "rejected": "<rejected response>",
}

For training, we must convert prompt to chat templated format for the target model.

Some available datasets have weird formats:
    https://huggingface.co/datasets/HuggingFaceH4/ultrafeedback_binarized - chosen and
    rejected include the prompt and are in ShareGPT format.
"""
import pathlib
import json
from dataclasses import dataclass
from typing import Callable

from py_fade.data_formats.base_data_classes import CommonConversation
from py_fade.data_formats.base_data_format import BaseDataFormat
from py_fade.providers.llm_templates import merged_plaintext


@dataclass
class DPOPair:
    """
    A single DPO training pair with prompt, chosen completion, and rejected completion.
    """
    prompt: CommonConversation
    chosen: str
    rejected: str


class DPODataFormat(BaseDataFormat):
    """
    Data format for Direct Preference Optimization (DPO) training.
    """

    def __init__(self, file_path: str | pathlib.Path):
        """
        Initialize DPO data format.

        Args:
            file_path: Path to save DPO data to
        """
        self.file_path = pathlib.Path(file_path)
        self._pairs: list[DPOPair] = []

    def set_pairs(self, pairs: list[DPOPair]) -> None:
        """
        Set the DPO pairs to be saved.

        Args:
            pairs: List of DPO pairs
        """
        self._pairs = pairs

    @property
    def pairs(self) -> list[DPOPair]:
        """
        Get the current DPO pairs.

        Returns:
            List of DPO pairs
        """
        return self._pairs

    def load(self, file_path: str | pathlib.Path | None = None) -> int:
        """
        Load DPO pairs from file (not implemented yet).

        Args:
            file_path: Path to load from

        Returns:
            Number of pairs loaded
        """
        raise NotImplementedError("DPO format loading is not yet implemented")

    def save(self, file_path: str | pathlib.Path | None = None, template_func: Callable[[CommonConversation], str] | None = None,
             output_format: str = "jsonl", is_vlm: bool = False) -> int:
        """
        Save all pairs in DPO format to the specified file as `output_format`.

        Each entry is a JSON object with "prompt", "chosen" and "rejected" fields.
        Prompt is a string, result of applying instruct chat template of the model,
        provided as `template_func`.
        Chosen and rejected are strings with the respective completion texts.

        Args:
            file_path: Path to save to (uses instance path if None)
            template_func: Function to convert CommonConversation to prompt string
            output_format: Output format, only "jsonl" is currently supported

        Returns:
            Number of pairs saved
        """
        if output_format != "jsonl":
            raise ValueError(f"DPODataFormat.save: Unsupported format '{output_format}', only 'jsonl' is supported.")

        if not self._pairs:
            raise ValueError("DPODataFormat.save: No pairs to save.")

        if not template_func:
            template_func = merged_plaintext

        save_path = pathlib.Path(file_path) if file_path else self.file_path

        with open(save_path, "w", encoding="utf-8") as f:
            for pair in self._pairs:
                prompt_text = template_func(pair.prompt)
                entry = {
                    "prompt": prompt_text,
                    "chosen": pair.chosen,
                    "rejected": pair.rejected,
                }
                if is_vlm:
                    entry["images"] = None
                f.write(json.dumps(entry, ensure_ascii=False, indent=None) + "\n")

        return len(self._pairs)
