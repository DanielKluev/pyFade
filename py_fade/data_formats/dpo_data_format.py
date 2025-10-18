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
    https://huggingface.co/datasets/HuggingFaceH4/ultrafeedback_binarized - chosen and rejected include the prompt and are in ShareGPT format.
"""
import pathlib
import json
from dataclasses import dataclass
from typing import Callable

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.data_formats.base_data_format import BaseDataFormat


@dataclass
class DPOPair:
    prompt: CommonConversation
    chosen: str
    rejected: str


class DPODataFormat(BaseDataFormat):
    """
    Data format for Direct Preference Optimization (DPO) training.
    """
    _pairs: list[DPOPair]

    def save(self, file_path: str | pathlib.Path, template_func: Callable[[CommonConversation], str], format: str = "jsonl") -> None:
        """
        Save all pairs in DPO format to the specified file as `format`.

        Each entry is a JSON object with "prompt", "chosen" and "rejected" fields.
        Prompt is a string, result of applying instruct chat template of the model, provided as `template_func`.
        Chosen and rejected are strings with the respective completion texts.
        """
        if format != "jsonl":
            raise ValueError(f"DPODataFormat.save: Unsupported format '{format}', only 'jsonl' is supported.")
        if not self._pairs:
            raise ValueError("DPODataFormat.save: No samples to save.")

        with open(file_path, "w", encoding="utf-8") as f:
            for pair in self._pairs:
                prompt_text = template_func(pair.prompt)
                entry = {
                    "prompt": prompt_text,
                    "chosen": pair.chosen,
                    "rejected": pair.rejected,
                }
                f.write(json.dumps(entry, ensure_ascii=False, indent=None) + "\n")
