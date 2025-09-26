"""Dataset model helpers for export templates used during dataset exports.

The :class:`ExportTemplate` entity describes how samples should be filtered and
rendered when exporting a dataset. Besides the SQLAlchemy mapping this module
provides convenience helpers for CRUD operations, validation of facet
parameters, and duplication utilities that are consumed by the GUI widgets.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import String, desc
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, DateTime

from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


FacetConfig = dict[str, Any]


class ExportTemplate(dataset_base):
    """Represents a single export template stored inside a dataset."""

    __tablename__ = "export_templates"

    SUPPORTED_MODEL_FAMILIES: ClassVar[tuple[str, ...]] = ("Gemma3", "Llama3", "Qwen3-Instruct")
    TRAINING_TYPES: ClassVar[tuple[str, ...]] = ("SFT", "DPO")
    OUTPUT_FORMATS: ClassVar[dict[str, tuple[str, ...]]] = {
        "SFT": ("JSON", "JSONL (ShareGPT)"),
        "DPO": ("JSONL (Anthropic)",),
    }

    DEFAULT_FILENAME_TEMPLATE: ClassVar[str] = "export-{name}-{timestamp}.jsonl"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    date_created: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.now
    )
    model_family: Mapped[str] = mapped_column(String, nullable=False)
    filename_template: Mapped[str] = mapped_column(String, nullable=False)
    output_format: Mapped[str] = mapped_column(String, nullable=False)
    training_type: Mapped[str] = mapped_column(String, nullable=False)
    facets_json: Mapped[list[FacetConfig]] = mapped_column(JSON, nullable=False, default=list)
    normalize_style: Mapped[bool] = mapped_column(nullable=False, default=False)
    encrypt: Mapped[bool] = mapped_column(nullable=False, default=False)
    encryption_password: Mapped[str | None] = mapped_column(String, nullable=True)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    @classmethod
    def get_by_id(cls, dataset: "DatasetDatabase", template_id: int) -> "ExportTemplate | None":
        """Return the export template with *template_id* or ``None`` if missing."""

        session = dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )
        return session.query(cls).filter_by(id=template_id).first()

    @classmethod
    def get_by_name(cls, dataset: "DatasetDatabase", name: str) -> "ExportTemplate | None":
        """Return the export template with the provided *name* or ``None``."""

        session = dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )
        trimmed = name.strip()
        return session.query(cls).filter_by(name=trimmed).first()

    @classmethod
    def get_all(cls, dataset: "DatasetDatabase") -> list["ExportTemplate"]:
        """Return all export templates ordered by creation date descending."""

        session = dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )
        return list(session.query(cls).order_by(desc(cls.date_created)).all())

    # ------------------------------------------------------------------
    # Creation/update helpers
    # ------------------------------------------------------------------
    @classmethod
    def create(
        cls,
        dataset: "DatasetDatabase",
        *,
        name: str,
        description: str,
        training_type: str,
        output_format: str,
        model_families: Iterable[str],
        filename_template: str | None = None,
        normalize_style: bool = False,
        encrypt: bool = False,
        encryption_password: str | None = None,
        facets: Iterable[FacetConfig] | None = None,
    ) -> "ExportTemplate":
        """Create a new export template and attach it to *dataset*.

        Raises:
            ValueError: if validation fails or a template with ``name`` already exists.
        """

        session = dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

        trimmed_name = name.strip()
        if not trimmed_name:
            raise ValueError("Template name is required.")
        existing = cls.get_by_name(dataset, trimmed_name)
        if existing is not None:
            raise ValueError(f"An export template named '{trimmed_name}' already exists.")

        normalized_training = cls._normalize_training_type(training_type)
        normalized_format = cls._normalize_output_format(normalized_training, output_format)
        normalized_models = cls._normalize_models(model_families)
        normalized_facets = cls._normalize_facets(facets or [])

        encrypted = bool(encrypt)
        password = cls._normalize_password(encrypted, encryption_password)

        template = cls(
            name=trimmed_name,
            description=description.strip(),
            model_family=",".join(normalized_models),
            filename_template=(filename_template or cls.DEFAULT_FILENAME_TEMPLATE).strip(),
            output_format=normalized_format,
            training_type=normalized_training,
            facets_json=normalized_facets,
            normalize_style=bool(normalize_style),
            encrypt=encrypted,
            encryption_password=password,
        )
        session.add(template)
        return template

    def update(
        self,
        dataset: "DatasetDatabase",
        *,
        name: str | None = None,
        description: str | None = None,
        training_type: str | None = None,
        output_format: str | None = None,
        model_families: Iterable[str] | None = None,
        filename_template: str | None = None,
        normalize_style: bool | None = None,
        encrypt: bool | None = None,
        encryption_password: str | None = None,
        facets: Iterable[FacetConfig] | None = None,
    ) -> None:
        """Update the template with the provided values after validation."""

        session = dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

        if name is not None:
            trimmed = name.strip()
            if not trimmed:
                raise ValueError("Template name is required.")
            other = self.get_by_name(dataset, trimmed)
            if other and other.id != self.id:
                raise ValueError(f"An export template named '{trimmed}' already exists.")
            self.name = trimmed

        if description is not None:
            self.description = description.strip()

        if training_type is not None:
            normalized_training = self._normalize_training_type(training_type)
        else:
            normalized_training = self.training_type

        if output_format is not None:
            self.output_format = self._normalize_output_format(normalized_training, output_format)
        elif training_type is not None:
            # Ensure existing format is still compatible with new training type
            self.output_format = self._normalize_output_format(
                normalized_training, self.output_format
            )
        self.training_type = normalized_training

        if model_families is not None:
            self.model_family = ",".join(self._normalize_models(model_families))

        if filename_template is not None:
            trimmed_filename = filename_template.strip() or self.DEFAULT_FILENAME_TEMPLATE
            self.filename_template = trimmed_filename

        if normalize_style is not None:
            self.normalize_style = bool(normalize_style)

        if encrypt is not None:
            self.encrypt = bool(encrypt)

        if facets is not None:
            self.facets_json = self._normalize_facets(facets)

        if encrypt is not None or encryption_password is not None:
            self.encryption_password = self._normalize_password(self.encrypt, encryption_password)

    def delete(self, dataset: "DatasetDatabase") -> None:
        """Remove this template from *dataset*."""

        session = dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )
        session.delete(self)

    def duplicate(self, dataset: "DatasetDatabase", *, name: str | None = None) -> "ExportTemplate":
        """Return a detached copy of this template stored in *dataset*.

        If *name* is provided it is used after validation; otherwise an
        automatically generated unique name is chosen.
        """

        base_name = name.strip() if name else f"{self.name} Copy"
        unique_name = self._generate_unique_name(dataset, base_name)
        return self.create(
            dataset,
            name=unique_name,
            description=self.description,
            training_type=self.training_type,
            output_format=self.output_format,
            model_families=self.model_family.split(",") if self.model_family else [],
            filename_template=self.filename_template,
            normalize_style=self.normalize_style,
            encrypt=self.encrypt,
            encryption_password=self.encryption_password,
            facets=self.facets_json,
        )

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------
    @classmethod
    def _normalize_training_type(cls, value: str) -> str:
        normalized = value.strip().upper()
        for option in cls.TRAINING_TYPES:
            if normalized == option.upper():
                return option
        raise ValueError(f"Unsupported training type: {value!r}")

    @classmethod
    def _normalize_output_format(cls, training_type: str, value: str) -> str:
        choices = cls.OUTPUT_FORMATS.get(training_type, ())
        normalized_value = value.strip()
        for option in choices:
            if normalized_value.lower() == option.lower():
                return option
        if not choices:
            raise ValueError(f"No output formats available for training type '{training_type}'.")
        raise ValueError(
            f"Unsupported output format '{value}' for training type '{training_type}'. Valid options: {choices}."
        )

    @classmethod
    def _normalize_models(cls, models: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for model in models:
            trimmed = model.strip()
            if not trimmed:
                continue
            for candidate in cls.SUPPORTED_MODEL_FAMILIES:
                if trimmed.lower() == candidate.lower():
                    normalized.append(candidate)
                    break
            else:
                raise ValueError(
                    f"Model family '{model}' is not supported. Supported families: {cls.SUPPORTED_MODEL_FAMILIES}."
                )
        if not normalized:
            raise ValueError("At least one model family must be selected.")
        return sorted(set(normalized), key=cls.SUPPORTED_MODEL_FAMILIES.index)

    @classmethod
    def _normalize_facets(cls, facets: Iterable[FacetConfig]) -> list[FacetConfig]:
        normalized: list[FacetConfig] = []
        seen_ids: set[int] = set()
        for facet in facets:
            facet_id_value = facet.get("facet_id")
            if facet_id_value is None:
                raise ValueError("Facet configuration must include a facet_id.")
            try:
                facet_id = int(facet_id_value)
            except (TypeError, ValueError) as exc:  # noqa: PERF203 - keep explicit exception
                raise ValueError("Facet configuration facet_id must be an integer.") from exc
            if facet_id in seen_ids:
                raise ValueError("Duplicate facet selections are not allowed in a template.")
            seen_ids.add(facet_id)

            limit_type = str(facet.get("limit_type", "count")).lower()
            if limit_type not in {"count", "percentage"}:
                raise ValueError("Facet limit_type must be either 'count' or 'percentage'.")

            limit_value = float(facet.get("limit_value", 0))
            if limit_type == "count":
                if limit_value <= 0:
                    raise ValueError("Facet count limit must be greater than zero.")
                limit_value = int(limit_value)
            else:
                if not 0 < limit_value <= 100:
                    raise ValueError("Facet percentage limit must be between 0 and 100.")

            order = str(facet.get("order", "random")).lower()
            if order not in {"random", "newest", "oldest"}:
                raise ValueError("Facet order must be one of: random, newest, oldest.")

            min_logprob = facet.get("min_logprob")
            avg_logprob = facet.get("avg_logprob")
            normalized.append(
                {
                    "facet_id": facet_id,
                    "limit_type": limit_type,
                    "limit_value": limit_value,
                    "order": order,
                    "min_logprob": None if min_logprob in (None, "") else float(min_logprob),
                    "avg_logprob": None if avg_logprob in (None, "") else float(avg_logprob),
                }
            )
        return normalized

    @staticmethod
    def _normalize_password(encrypt: bool, password: str | None) -> str | None:
        if not encrypt:
            return None
        if password is None:
            return None
        trimmed = password.strip()
        return trimmed or None

    @classmethod
    def _generate_unique_name(cls, dataset: "DatasetDatabase", desired_name: str) -> str:
        base = desired_name.strip() or "Export Template Copy"
        existing_names = {template.name for template in cls.get_all(dataset)}
        if base not in existing_names:
            return base
        suffix = 2
        while f"{base} ({suffix})" in existing_names:
            suffix += 1
        return f"{base} ({suffix})"
