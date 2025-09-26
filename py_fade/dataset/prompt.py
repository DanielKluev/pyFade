"""Prompt revision ORM model and helpers."""

import datetime
import hashlib
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.sample import Sample


class PromptRevision(dataset_base):
    """
    Represents a single prompt revision in the dataset.
    """

    __tablename__ = "prompt_revisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sha256: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    prompt_text: Mapped[str] = mapped_column(String, nullable=False)
    context_length: Mapped[int] = mapped_column(Integer, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    samples: Mapped[list["Sample"]] = relationship(
        "Sample", back_populates="prompt_revision", lazy="select"
    )

    completions: Mapped[list["PromptCompletion"]] = relationship(
        "PromptCompletion",
        back_populates="prompt_revision",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @classmethod
    def hash_from_text(cls, prompt_text: str) -> str:
        """
        Compute SHA256 hash of prompt text.
        """
        return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    @classmethod
    def new_from_text(
        cls, prompt_text: str, context_length: int, max_tokens: int
    ) -> "PromptRevision":
        """
        Create new PromptRevision from prompt text.
        """
        sha256 = cls.hash_from_text(prompt_text)
        return cls(
            sha256=sha256,
            date_created=datetime.datetime.now(),
            prompt_text=prompt_text,
            context_length=context_length,
            max_tokens=max_tokens,
        )

    @classmethod
    def get_or_create(
        cls, dataset: "DatasetDatabase", prompt_text: str, context_length: int, max_tokens: int
    ) -> "PromptRevision":
        """
        Get existing PromptRevision by text hash or create a new one if not found.
        """
        if not dataset.session:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )
        prompt_text = prompt_text.strip()
        sha256 = cls.hash_from_text(prompt_text)
        instance = dataset.session.query(cls).filter_by(sha256=sha256).first()
        if instance:
            return instance
        instance = cls.new_from_text(prompt_text, context_length, max_tokens)
        dataset.session.add(instance)
        dataset.session.commit()
        return instance

    @classmethod
    def get_by_hash(cls, dataset: "DatasetDatabase", prompt_text: str) -> "PromptRevision | None":
        """
        Get existing PromptRevision by text hash.
        """
        if not dataset.session:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )
        sha256 = cls.hash_from_text(prompt_text.strip())
        return dataset.session.query(cls).filter_by(sha256=sha256).first()

    @property
    def prompt_text_oneliner(self) -> str:
        """
        Get a one-liner version of the prompt text for display purposes.
        """
        max_length = 50
        if len(self.prompt_text) <= max_length:
            prompt = self.prompt_text
        else:
            prompt = self.prompt_text[: max_length - 3] + "..."
        return prompt.replace("\n", " ").replace("\r", " ")
