"""Utilities for working with :mod:`lm-evaluation-harness` JSON exports.

The format combines an overall ``results_*.json`` summary file with a matching
``samples_*.jsonl`` file that contains per-sample metadata and metrics.  The
data shipped alongside the unit tests demonstrates the expected behaviour when
diffing two evaluation runs: one tuned model introduces a new regression while
keeping one shared success and one shared failure compared to the base model.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import math
import pathlib
from typing import Any, Dict, Iterable, List, Optional


MODULE_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class LMEvalSample:
    """Represents a single lm-eval sample with helper accessors.

    Parameters
    ----------
    prompt_hash:
        SHA256 hash that uniquely identifies the prompt within the dataset.
    prompt_text:
        Plain-text question or prompt shown to the model for this sample.
    target_text:
        Ground-truth answer string provided by the dataset.
    response_text:
        Model response returned by the evaluation harness.
    metrics:
        Mapping of metric names to numeric scores (e.g. ``{"exact_match": 1.0}``).
    raw_sample:
        Original JSON record for any additional downstream consumers.
    """

    prompt_hash: str
    prompt_text: str
    target_text: str
    response_text: str
    metrics: Dict[str, float]
    raw_sample: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def is_success(self) -> Optional[bool]:
        """Return ``True`` for a correct sample, ``False`` for incorrect, ``None`` if unknown."""

        numeric_metrics: List[float] = [
            score
            for score in self.metrics.values()
            if isinstance(score, (int, float))
        ]
        if numeric_metrics:
            return all(
                math.isclose(score, 1.0, rel_tol=1e-9, abs_tol=1e-9)
                for score in numeric_metrics
            )

        # Fallback to optional boolean flags produced by some harness versions.
        raw_flag = self.raw_sample.get("correct") or self.raw_sample.get("is_correct")
        if isinstance(raw_flag, bool):
            return raw_flag

        return None


class LMEvalResult:
    """Loader and comparator for lm-eval harness result archives."""

    def __init__(self, result_json_path: pathlib.Path | str) -> None:
        self.result_json_path = pathlib.Path(result_json_path)
        self.log = logging.getLogger(self.__class__.__name__)

        # Try to find samples JSONL file next to results JSON file.
        match_pattern = self.result_json_path.stem.replace("results_", "*") + ".jsonl"
        candidates = list(self.result_json_path.parent.glob(match_pattern))
        if not candidates:
            raise ValueError(
                f"Could not find matching samples JSONL file next to {self.result_json_path}"
            )
        if len(candidates) > 1:
            candidate_list = ", ".join(str(candidate) for candidate in candidates)
            raise ValueError(
                "Found multiple matching samples JSONL files next to "
                f"{self.result_json_path}: {candidate_list}"
            )
        self.samples_jsonl_path = candidates[0]

        self.model_id: Optional[str] = None
        self.origin_name: Optional[str] = None
        self.samples: List[LMEvalSample] = []
        self._samples_by_hash: Dict[str, LMEvalSample] = {}
        self._loaded = False

    def load(self) -> None:
        """Read the summary JSON and sample JSONL files into memory."""

        summary = self._read_json(self.result_json_path)
        self.model_id = self._infer_model_id(summary)
        self.origin_name = self._infer_origin_name(summary)

        raw_samples = list(self._read_samples())
        self.samples = [self._build_sample(record) for record in raw_samples]
        self._samples_by_hash = {sample.prompt_hash: sample for sample in self.samples}
        self._loaded = True

        self.log.debug(
            "Loaded %d lm-eval samples from %s (model=%s, origin=%s)",
            len(self.samples),
            self.result_json_path,
            self.model_id,
            self.origin_name,
        )

    def compare(self, other: "LMEvalResult") -> Dict[str, List[LMEvalSample]]:
        """Compare two loaded results and return grouped differences.

        The comparison operates on the intersection of ``prompt_hash`` values.  It
        classifies samples from the *current* instance (``self``) relative to the
        ``other`` baseline:

        - ``shared_success`` – identical prompts that both models answer correctly.
        - ``shared_failure`` – identical prompts that both models answer incorrectly.
        - ``new_failure`` – prompts that now fail but previously succeeded.
        - ``fixed`` – prompts that now succeed but previously failed.
        """

        self.ensure_loaded()
        other.ensure_loaded()

        current_samples = self.samples_by_hash
        baseline_samples = other.samples_by_hash
        shared_keys = set(current_samples).intersection(baseline_samples)

        result: Dict[str, List[LMEvalSample]] = {
            "shared_success": [],
            "shared_failure": [],
            "new_failure": [],
            "fixed": [],
        }

        for prompt_hash in sorted(shared_keys):
            current_sample = current_samples[prompt_hash]
            baseline_sample = baseline_samples[prompt_hash]

            current_success = current_sample.is_success()
            baseline_success = baseline_sample.is_success()
            if current_success is None or baseline_success is None:
                self.log.debug(
                    "Skipping prompt_hash %s due to unknown success state "
                    "(current=%s, baseline=%s)",
                    prompt_hash,
                    current_success,
                    baseline_success,
                )
                continue

            if current_success and baseline_success:
                result["shared_success"].append(current_sample)
            elif not current_success and not baseline_success:
                result["shared_failure"].append(current_sample)
            elif not current_success and baseline_success:
                result["new_failure"].append(current_sample)
            elif current_success and not baseline_success:
                result["fixed"].append(current_sample)

        return result

    def _build_sample(self, sample_record: Dict[str, Any]) -> LMEvalSample:
        """Transform a raw JSONL record into :class:`LMEvalSample`."""

        prompt_hash = sample_record.get("prompt_hash")
        if not prompt_hash:
            raise ValueError(
                f"Sample record missing 'prompt_hash': {sample_record}"
            )

        prompt_text = self._extract_prompt_text(sample_record)
        target_text = sample_record.get("target", "")
        response_text = self._extract_response_text(sample_record)
        metrics = self._extract_metrics(sample_record)

        return LMEvalSample(
            prompt_hash=prompt_hash,
            prompt_text=prompt_text,
            target_text=target_text,
            response_text=response_text,
            metrics=metrics,
            raw_sample=sample_record,
        )

    @staticmethod
    def _extract_prompt_text(sample_record: Dict[str, Any]) -> str:
        """Best-effort extraction of the human-readable prompt/question text."""

        arguments = sample_record.get("arguments", {})
        conversation_prompt = LMEvalResult._conversation_text(arguments)
        if conversation_prompt:
            return conversation_prompt

        doc = sample_record.get("doc")
        if isinstance(doc, dict):
            question = doc.get("question")
            if isinstance(question, str) and question.strip():
                return question

        MODULE_LOGGER.debug(
            "Falling back to raw prompt representation for sample %s",
            sample_record.get("prompt_hash"),
        )
        return sample_record.get("prompt", "")

    @staticmethod
    def _extract_response_text(sample_record: Dict[str, Any]) -> str:
        """Return the first model response stored in the record."""

        responses = sample_record.get("resps") or []
        if responses:
            first_resp = responses[0]
            if isinstance(first_resp, list) and first_resp:
                return str(first_resp[0])
            if isinstance(first_resp, str):
                return first_resp

        filtered = sample_record.get("filtered_resps") or []
        if filtered:
            return str(filtered[0])

        return ""

    @staticmethod
    def _extract_metrics(sample_record: Dict[str, Any]) -> Dict[str, float]:
        """Build a numeric metric mapping from the sample record."""

        metric_names: Iterable[str] = sample_record.get("metrics", []) or []
        metrics: Dict[str, float] = {}
        for name in metric_names:
            value = sample_record.get(name)
            if isinstance(value, (int, float)):
                metrics[name] = float(value)
        return metrics

    @staticmethod
    def _conversation_text(arguments: Dict[str, Any]) -> str:
        """Extract the full conversation string if present in harness arguments."""

        if not isinstance(arguments, dict):
            return ""

        for argument in arguments.values():
            conversation = argument.get("arg_0") if isinstance(argument, dict) else None
            if not isinstance(conversation, list) or not conversation:
                continue
            try:
                collected_parts: List[str] = []
                for turn in conversation:
                    if isinstance(turn, str):
                        normalised = LMEvalResult._normalise_prompt_segment(turn)
                        if normalised:
                            collected_parts.append(normalised)
                        continue
                    if isinstance(turn, dict):
                        content = turn.get("content")
                        if isinstance(content, str):
                            collected_parts.append(content)
                if collected_parts:
                    return "\n".join(collected_parts)
            except (KeyError, IndexError):  # pragma: no cover - defensive
                MODULE_LOGGER.debug("Failed extracting conversation text", exc_info=True)
        return ""

    @staticmethod
    def _normalise_prompt_segment(segment: str) -> Optional[str]:
        """Decode JSON-encoded conversation fragments into plain text."""

        stripped = segment.strip()
        if not stripped:
            return None

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped

        if isinstance(parsed, list):
            extracted: List[str] = []
            for item in parsed:
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, str):
                        extracted.append(content)
            if extracted:
                return "\n".join(extracted)

        if isinstance(parsed, dict):
            content = parsed.get("content")
            if isinstance(content, str):
                return content

        return stripped

    def _read_samples(self) -> Iterable[Dict[str, Any]]:
        """Yield raw sample dictionaries from the JSONL file."""

        with self.samples_jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    @staticmethod
    def _read_json(path: pathlib.Path) -> Dict[str, Any]:
        """Read a JSON file from disk."""

        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _infer_model_id(summary: Dict[str, Any]) -> Optional[str]:
        """Infer the model identifier from the summary JSON."""

        model_name = summary.get("model_name")
        if isinstance(model_name, str) and model_name:
            return model_name

        config = summary.get("config", {})
        if isinstance(config, dict):
            config_model = config.get("model")
            if isinstance(config_model, str) and config_model:
                # Avoid returning generic wrappers such as "local-chat-completions".
                if config_model.startswith("gemma") or config_model.startswith("llama"):
                    return config_model

            model_args = config.get("model_args")
            if isinstance(model_args, str) and model_args:
                for part in model_args.split(","):
                    if part.startswith("model="):
                        return part.split("=", maxsplit=1)[1]

        configs = summary.get("configs")
        if isinstance(configs, dict):
            for value in configs.values():
                metadata = value.get("metadata") if isinstance(value, dict) else None
                if isinstance(metadata, dict):
                    model = metadata.get("model")
                    if isinstance(model, str) and model:
                        return model

        return None

    @staticmethod
    def _infer_origin_name(summary: Dict[str, Any]) -> Optional[str]:
        """Infer the dataset/task name from the summary JSON."""

        results = summary.get("results")
        if isinstance(results, dict) and results:
            return next(iter(results.keys()))

        configs = summary.get("configs")
        if isinstance(configs, dict) and configs:
            return next(iter(configs.keys()))

        return None

    @property
    def samples_by_hash(self) -> Dict[str, LMEvalSample]:
        """Read-only mapping of ``prompt_hash`` to :class:`LMEvalSample`."""

        self._ensure_loaded()
        return self._samples_by_hash

    def ensure_loaded(self) -> None:
        """Public guard that ensures :meth:`load` has been executed."""

        self._ensure_loaded()

    def _ensure_loaded(self) -> None:
        """Raise if :meth:`load` has not been executed yet."""

        if not self._loaded:
            raise RuntimeError(
                f"LMEvalResult for {self.result_json_path} has not been loaded. "
                "Call load() before comparing."
            )
