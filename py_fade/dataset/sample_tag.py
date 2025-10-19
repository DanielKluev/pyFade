"""
Association table for many-to-many relationship between samples and tags.

This module defines the SampleTag model that associates samples with tags,
allowing samples to be tagged with multiple tags and tags to be associated
with multiple samples.

Key classes: `SampleTag`
"""

import datetime
import logging
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.sample import Sample
    from py_fade.dataset.tag import Tag


class SampleTag(dataset_base):
    """
    Association table linking samples to tags.

    This model represents a many-to-many relationship between samples and tags,
    allowing each sample to have multiple tags and each tag to be associated
    with multiple samples.
    """

    __tablename__ = "sample_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=False)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)

    # Relationships
    sample: Mapped["Sample"] = relationship("Sample", back_populates="sample_tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="sample_tags")

    log = logging.getLogger("SampleTag")

    @classmethod
    def create(cls, dataset: "DatasetDatabase", sample: "Sample", tag: "Tag") -> "SampleTag":
        """
        Create a new sample-tag association.

        Returns the created SampleTag instance. If the association already exists,
        raises ValueError.

        Args:
            dataset: The dataset database instance
            sample: The sample to associate with the tag
            tag: The tag to associate with the sample

        Returns:
            The created SampleTag instance

        Raises:
            ValueError: If the association already exists
        """
        session = dataset.get_session()

        # Check if association already exists
        existing = session.query(cls).filter_by(sample_id=sample.id, tag_id=tag.id).first()
        if existing:
            raise ValueError(f"Sample {sample.id} is already tagged with '{tag.name}'.")

        sample_tag = cls(
            sample_id=sample.id,
            tag_id=tag.id,
            date_created=datetime.datetime.now(),
        )

        session.add(sample_tag)
        cls.log.debug("Created sample-tag association: sample_id=%s, tag_id=%s", sample.id, tag.id)
        return sample_tag

    @classmethod
    def delete_association(cls, dataset: "DatasetDatabase", sample: "Sample", tag: "Tag") -> None:
        """
        Delete an existing sample-tag association.

        Args:
            dataset: The dataset database instance
            sample: The sample to dissociate from the tag
            tag: The tag to dissociate from the sample

        Raises:
            ValueError: If the association does not exist
        """
        session = dataset.get_session()

        existing = session.query(cls).filter_by(sample_id=sample.id, tag_id=tag.id).first()
        if not existing:
            raise ValueError(f"Sample {sample.id} is not tagged with '{tag.name}'.")

        session.delete(existing)
        cls.log.debug("Deleted sample-tag association: sample_id=%s, tag_id=%s", sample.id, tag.id)

    def __repr__(self) -> str:
        return f"SampleTag(id={self.id}, sample_id={self.sample_id}, tag_id={self.tag_id}, date_created={self.date_created})"
