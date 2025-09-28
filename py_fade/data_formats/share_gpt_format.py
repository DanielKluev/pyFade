"""
Read and write ShareGPT-formatted conversation samples.

ShareGPT datasets:
    - Each sample is a JSON object with a "conversations" list.
    - Each conversation entry provides a "from" field (system/human/gpt) and a text payload.

ShareGPT data can be stored as JSON, JSONL, or Parquet files. JSON files may contain an array of
objects or newline-separated JSON objects. JSONL files contain one ShareGPT object per line.
"""

# pylint: disable=trailing-newlines

from __future__ import annotations

import json
import logging
import pathlib
from collections.abc import Mapping
from typing import Any, Iterable

import pandas as pd

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.data_formats.base_data_format import BaseDataFormat


class ShareGPTFormat(BaseDataFormat):
    """ShareGPT data format loader for JSON, JSONL, and Parquet sources."""

    def __init__(self, serialized_file_path: pathlib.Path | str) -> None:
        """Construct a ``ShareGPTFormat`` helper and record the input path."""

        self.log = logging.getLogger(self.__class__.__name__)
        self._samples: list[CommonConversation] = []
        self.set_path(serialized_file_path)
        self._loaded = False

    def set_path(self, path: pathlib.Path | str) -> None:
        """Set the base path for this data format instance."""
        self.serialized_file_path = pathlib.Path(path)
        suffix = self.serialized_file_path.suffix.lower()
        if suffix == ".jsonl":
            self.format = "jsonl"
        elif suffix == ".json":
            self.format = "json"
        elif suffix == ".parquet":
            self.format = "parquet"
        else:
            raise ValueError(
                f"Unsupported file extension '{self.serialized_file_path.suffix}'. "
                "Use .json, .jsonl, or .parquet for ShareGPT format."
            )

    def load(self, file_path: str|pathlib.Path|None = None) -> int:
        """
        Load samples from the ShareGPT formatted file.
        """
        if file_path:
            self.set_path(file_path)

        if not self.serialized_file_path.exists():
            raise FileNotFoundError(f"File does not exist: {self.serialized_file_path}")

        self._samples = []  # Clear cached samples before loading new data

        if self.format == "jsonl":
            self._load_jsonl()
        elif self.format == "json":
            self._load_json()
        elif self.format == "parquet":
            self._load_parquet()
        else:
            raise ValueError(f"Unsupported format '{self.format}'")

        if not self._samples:
            raise ValueError(
                f"No valid ShareGPT conversations found in {self.serialized_file_path}."
            )

        self._loaded = True
        return len(self._samples)

    @property
    def samples(self) -> list[CommonConversation]:
        """Return the loaded ShareGPT samples."""
        return self._samples

    def set_samples(self, value: list[CommonConversation]) -> None:
        """Set the ShareGPT samples."""
        self._samples = value

    def save(self, file_path: str | pathlib.Path | None = None) -> int:
        """Persist the currently loaded ShareGPT samples to ``file_path``.

        Parameters
        ----------
        file_path:
            Destination path. When ``None`` the instance's configured path is used.

        Returns
        -------
        int
            Number of samples written to disk.

        Raises
        ------
        ValueError
            If no samples are loaded or the destination format is unsupported.
        """

        if file_path is not None:
            self.set_path(file_path)

        if not self._samples:
            raise ValueError("No ShareGPT samples available to save. Call load() first.")

        destination = self.serialized_file_path
        destination.parent.mkdir(parents=True, exist_ok=True)

        if self.format == "jsonl":
            self._save_jsonl(destination)
        elif self.format == "json":
            self._save_json(destination)
        elif self.format == "parquet":
            self._save_parquet(destination)
        else:
            raise ValueError(f"Unsupported format '{self.format}' for saving.")

        return len(self._samples)

    def _load_json(self) -> None:
        """Load ShareGPT samples from a JSON document."""
        raw_text = self.serialized_file_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            self.log.warning("ShareGPT JSON file %s is empty", self.serialized_file_path)
            self._samples = []
            return

        records: list[dict[str, Any]] = []
        try:
            decoded = json.loads(raw_text)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            cursor = 0
            length = len(raw_text)
            while cursor < length:
                cursor = self._skip_whitespace(raw_text, cursor)
                if cursor >= length:
                    break
                record, cursor = decoder.raw_decode(raw_text, cursor)
                if isinstance(record, dict):
                    records.append(record)
                else:
                    self.log.debug("Skipping non-dict JSON entry of type %s", type(record))
        else:
            if isinstance(decoded, list):
                records = [item for item in decoded if isinstance(item, dict)]
            elif isinstance(decoded, dict):
                records = [decoded]
            else:
                self.log.warning(
                    "Unexpected JSON root type %s in %s", type(decoded).__name__, self.serialized_file_path
                )

        self._populate_samples(records)

    def _load_jsonl(self) -> None:
        """Load ShareGPT samples from a JSON Lines file."""
        records: list[dict[str, Any]] = []
        with self.serialized_file_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    self.log.warning(
                        "Skipping invalid JSON at %s:%d due to %s", self.serialized_file_path, line_number, exc
                    )
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
                else:
                    self.log.debug(
                        "Skipping JSONL entry at %s:%d because it is not a dict", self.serialized_file_path, line_number
                    )

        self._populate_samples(records)

    def _load_parquet(self) -> None:
        """Load ShareGPT samples from a Parquet file."""
        records: list[dict[str, Any]]

        dataframe = pd.read_parquet(self.serialized_file_path)
        self.log.debug(
            "Loaded Parquet via pandas with %d rows and columns %s",
            len(dataframe),
            list(dataframe.columns),
        )
        records = []
        for row in dataframe.to_dict(orient="records"):
            normalized = self._row_to_dict(row)
            if normalized is not None:
                if not records:
                    self.log.debug("First pandas Parquet row: %s", normalized)
                records.append(normalized)

        self._populate_samples(records)
        self.log.debug("Populated %d ShareGPT samples from Parquet", len(self._samples))

    def _populate_samples(self, records: Iterable[dict[str, Any]]) -> None:
        """Convert raw ShareGPT records to CommonConversation samples."""
        samples: list[CommonConversation] = []
        for record_index, record in enumerate(records):
            conversations = self._normalize_conversations(record.get("conversations"))
            if conversations is None:
                self.log.debug(
                    "Record %d in %s missing 'conversations' list; skipping", record_index, self.serialized_file_path
                )
                continue

            messages: list[CommonMessage] = []
            for message_index, message_obj in enumerate(conversations):
                if not isinstance(message_obj, dict):
                    self.log.debug(
                        "Record %d message %d is not a dict; skipping",
                        record_index,
                        message_index,
                    )
                    continue

                raw_role = message_obj.get("from") or message_obj.get("role")
                role = self._normalize_role(str(raw_role) if raw_role is not None else "")
                value = message_obj.get("value")
                if value is None:
                    value = message_obj.get("content", "")
                if not isinstance(value, str):
                    value = str(value)

                messages.append(CommonMessage(role=role, content=value))

            if messages:
                samples.append(CommonConversation(messages=messages))
            else:
                self.log.debug(
                    "Record %d in %s produced no valid messages and was skipped",
                    record_index,
                    self.serialized_file_path,
                )

        self._samples = samples

    def _normalize_role(self, sharegpt_role: str) -> str:
        """Map ShareGPT role identifiers to the common schema roles."""
        normalized = sharegpt_role.lower().strip()
        role_map = {
            "system": "system",
            "human": "user",
            "user": "user",
            "assistant": "assistant",
            "gpt": "assistant",
        }
        if normalized not in role_map:
            self.log.debug("Encountered unknown ShareGPT role '%s'; defaulting to 'assistant'", sharegpt_role)
        return role_map.get(normalized, "assistant")

    def _serialize_samples(self) -> list[dict[str, Any]]:
        """Convert loaded samples back to ShareGPT-compatible dictionaries."""

        serialized: list[dict[str, Any]] = []
        for index, conversation in enumerate(self._samples):
            messages: list[dict[str, Any]] = []
            for message in conversation.messages:
                payload = {
                    "from": self._denormalize_role(message.role),
                    "value": message.content,
                    "content": message.content,
                }
                messages.append(payload)

            serialized.append({"id": index, "conversations": messages})
        return serialized

    def _save_json(self, path: pathlib.Path) -> None:
        """Write samples to a JSON file."""

        records = self._serialize_samples()
        payload = json.dumps(records, ensure_ascii=False, indent=2)
        path.write_text(payload + "\n", encoding="utf-8")

    def _save_jsonl(self, path: pathlib.Path) -> None:
        """Write samples to a JSON Lines file."""

        records = self._serialize_samples()
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")

    def _save_parquet(self, path: pathlib.Path) -> None:
        """Write samples to a Parquet file."""

        records = self._serialize_samples()
        parquet_ready = []
        for record in records:
            parquet_ready.append(
                {
                    "id": record.get("id"),
                    "conversations": json.dumps(record.get("conversations"), ensure_ascii=False),
                }
            )
        dataframe = pd.DataFrame(parquet_ready)
        dataframe.to_parquet(path, index=False)

    def _denormalize_role(self, normalized_role: str) -> str:
        """Convert the internal role notation back to ShareGPT identifiers."""

        role_map = {
            "system": "system",
            "user": "human",
            "assistant": "gpt",
        }
        key = normalized_role.lower().strip()
        return role_map.get(key, normalized_role)

    @staticmethod
    def _skip_whitespace(payload: str, index: int) -> int:
        """Advance the cursor beyond any whitespace characters in the payload."""
        length = len(payload)
        while index < length and payload[index].isspace():
            index += 1
        return index

    def _normalize_conversations(self, raw_conversations: Any) -> list[dict[str, Any]] | None:
        """Convert stored conversation payloads into a list of message dictionaries."""

        candidate = raw_conversations

        if isinstance(candidate, tuple):
            candidate = list(candidate)

        if isinstance(candidate, bytes):
            try:
                candidate = candidate.decode("utf-8")
            except UnicodeDecodeError:
                self.log.debug("Unable to decode conversation bytes; skipping record")
                return None

        tolist_method = getattr(candidate, "tolist", None)
        if callable(tolist_method) and not isinstance(candidate, (str, bytes, bytearray)):
            try:
                candidate = tolist_method()
            except TypeError:
                self.log.debug("Failed to convert conversation payload with tolist(); skipping record")
                return None

        if isinstance(candidate, str):
            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError:
                self.log.debug("Conversation string payload is not valid JSON; skipping record")
                return None
            if not isinstance(candidate, list):
                self.log.debug(
                    "Conversation string payload decoded to %s instead of list; skipping record",
                    type(candidate).__name__,
                )
                return None

        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]

        return None

    def _row_to_dict(self, row: Any) -> dict[str, Any] | None:
        """Convert arbitrary row representations into plain dictionaries with string keys."""

        if isinstance(row, Mapping):
            items = row.items()
        else:
            try:
                items = dict(row).items()
            except (TypeError, ValueError):
                self.log.debug("Unable to convert row of type %s to dict; skipping", type(row).__name__)
                return None
        return {str(key): value for key, value in items}
