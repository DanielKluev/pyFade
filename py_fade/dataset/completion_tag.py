"""
Association table for many-to-many relationship between completions and tags.

This module defines the CompletionTag model that associates completions with tags,
allowing completions to be tagged with multiple tags and tags to be associated
with multiple completions.

Key classes: `CompletionTag`
"""
# pylint: disable=duplicate-code

import datetime
import logging
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.tag import Tag


class CompletionTag(dataset_base):
    """
    Association table linking completions to tags.

    This model represents a many-to-many relationship between completions and tags,
    allowing each completion to have multiple tags and each tag to be associated
    with multiple completions.
    """

    __tablename__ = "completion_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    completion_id: Mapped[int] = mapped_column(ForeignKey("prompt_completions.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=False)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)

    # Relationships
    completion: Mapped["PromptCompletion"] = relationship("PromptCompletion", back_populates="completion_tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="completion_tags")

    log = logging.getLogger("CompletionTag")

    @classmethod
    def create(cls, dataset: "DatasetDatabase", completion: "PromptCompletion", tag: "Tag") -> "CompletionTag":
        """
        Create a new completion-tag association.

        Returns the created CompletionTag instance. If the association already exists,
        raises ValueError.

        Args:
            dataset: The dataset database instance
            completion: The completion to associate with the tag
            tag: The tag to associate with the completion

        Returns:
            The created CompletionTag instance

        Raises:
            ValueError: If the association already exists
        """
        session = dataset.get_session()

        # Check if association already exists
        existing = session.query(cls).filter_by(completion_id=completion.id, tag_id=tag.id).first()
        if existing:
            raise ValueError(f"Completion {completion.id} is already tagged with '{tag.name}'.")

        completion_tag = cls(
            completion_id=completion.id,
            tag_id=tag.id,
            date_created=datetime.datetime.now(),
        )

        session.add(completion_tag)
        cls.log.debug("Created completion-tag association: completion_id=%s, tag_id=%s", completion.id, tag.id)
        return completion_tag

    @classmethod
    def delete_association(cls, dataset: "DatasetDatabase", completion: "PromptCompletion", tag: "Tag") -> None:
        """
        Delete an existing completion-tag association.

        Args:
            dataset: The dataset database instance
            completion: The completion to dissociate from the tag
            tag: The tag to dissociate from the completion

        Raises:
            ValueError: If the association does not exist
        """
        session = dataset.get_session()

        existing = session.query(cls).filter_by(completion_id=completion.id, tag_id=tag.id).first()
        if not existing:
            raise ValueError(f"Completion {completion.id} is not tagged with '{tag.name}'.")

        session.delete(existing)
        cls.log.debug("Deleted completion-tag association: completion_id=%s, tag_id=%s", completion.id, tag.id)

    def __repr__(self) -> str:
        """
        Return developer-friendly string representation.
        """
        return f"CompletionTag(id={self.id}, completion_id={self.completion_id}, tag_id={self.tag_id}, date_created={self.date_created})"
