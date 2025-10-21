"""Dataset sample ORM model and helpers."""

import datetime
import logging
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from py_fade.dataset.dataset_base import dataset_base
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample_tag import SampleTag

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.data_filter import DataFilter
    from py_fade.dataset.tag import Tag


class Sample(dataset_base):
    """
    Class to hold main sample object, which is a pinned prompt revision and it's completions.
    """

    __tablename__ = "samples"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    group_path: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)
    prompt_revision_id: Mapped[int] = mapped_column(ForeignKey("prompt_revisions.id"), nullable=True)
    prompt_revision: Mapped["PromptRevision"] = relationship("PromptRevision", back_populates="samples", lazy="joined")

    # Many-to-many relationship with tags
    sample_tags: Mapped[List["SampleTag"]] = relationship("SampleTag", back_populates="sample", cascade="all, delete-orphan", lazy="select")

    log = logging.getLogger("Sample")

    @classmethod
    def create_if_unique(cls, dataset: "DatasetDatabase", title: str, prompt_revision: PromptRevision, group_path: str | None = None,
                         notes: str | None = None) -> "Sample | None":
        """
        Create new Sample instance if there's no existing sample for same prompt.
        """
        session = dataset.get_session()

        existing = session.query(cls).filter_by(prompt_revision=prompt_revision).first()
        if existing:
            return None

        new_sample = cls(
            title=title,
            group_path=group_path,
            notes=notes,
            date_created=datetime.datetime.now(),
            prompt_revision=prompt_revision,
        )
        session.add(new_sample)
        session.commit()
        return new_sample

    @classmethod
    def fetch_with_filter(cls, dataset: "DatasetDatabase", data_filter: "DataFilter | None" = None) -> list["Sample"]:
        """
        Fetch samples from the database, optionally applying a DataFilter.
        """
        session = dataset.get_session()

        query = session.query(Sample)
        if data_filter:
            query = data_filter.apply_to_query(query)

        return query.all()

    def new_copy(self) -> "Sample":
        """
        Create a new unsaved copy of this sample with the same prompt revision
        and title appended with ' (Copy)'.
        """
        return self.__class__(
            title=f"{self.title} (Copy)",
            group_path=self.group_path,
            notes=self.notes,
            date_created=datetime.datetime.now(),
            prompt_revision=self.prompt_revision,
        )

    @classmethod
    def from_prompt_revision(cls, dataset: "DatasetDatabase", prompt_revision: PromptRevision) -> "Sample":
        """
        If there's sample for the given prompt revision, return it. Otherwise,
        Create a new unsaved Sample instance from a given PromptRevision.
        """
        session = dataset.get_session()
        existing = session.query(cls).filter_by(prompt_revision=prompt_revision).first()
        if existing:
            return existing
        return cls(
            title="New Sample",
            group_path=None,
            date_created=datetime.datetime.now(),
            prompt_revision=prompt_revision,
        )

    @property
    def completions(self):
        """
        Access completions through the associated prompt revision.
        """
        if self.prompt_revision:
            return self.prompt_revision.completions
        return []

    def get_tags(self, dataset: "DatasetDatabase") -> List["Tag"]:
        """
        Get all tags associated with this sample.

        Returns a list of Tag objects associated with this sample, ordered by tag name.
        """
        from py_fade.dataset.tag import Tag  # pylint: disable=import-outside-toplevel
        session = dataset.get_session()
        # Query tags through the sample_tags association
        tags = session.query(Tag).join(Tag.sample_tags).filter_by(sample_id=self.id).order_by(Tag.name).all()
        return list(tags)

    def add_tag(self, dataset: "DatasetDatabase", tag: "Tag") -> None:
        """
        Add a tag to this sample.

        Creates a SampleTag association between this sample and the specified tag.
        If the association already exists, raises ValueError.

        Args:
            dataset: The dataset database instance
            tag: The tag to add to this sample

        Raises:
            ValueError: If the sample is already tagged with this tag
        """
        from py_fade.dataset.sample_tag import SampleTag  # pylint: disable=import-outside-toplevel
        SampleTag.create(dataset, self, tag)
        self.log.debug("Added tag '%s' to sample %s", tag.name, self.id)

    def remove_tag(self, dataset: "DatasetDatabase", tag: "Tag") -> None:
        """
        Remove a tag from this sample.

        Deletes the SampleTag association between this sample and the specified tag.
        If the association does not exist, raises ValueError.

        Args:
            dataset: The dataset database instance
            tag: The tag to remove from this sample

        Raises:
            ValueError: If the sample is not tagged with this tag
        """
        from py_fade.dataset.sample_tag import SampleTag  # pylint: disable=import-outside-toplevel
        SampleTag.delete_association(dataset, self, tag)
        self.log.debug("Removed tag '%s' from sample %s", tag.name, self.id)

    def has_tag(self, dataset: "DatasetDatabase", tag: "Tag") -> bool:
        """
        Check if this sample has a specific tag.

        Args:
            dataset: The dataset database instance
            tag: The tag to check

        Returns:
            True if the sample has this tag, False otherwise
        """
        from py_fade.dataset.sample_tag import SampleTag  # pylint: disable=import-outside-toplevel
        session = dataset.get_session()
        exists = session.query(SampleTag).filter_by(sample_id=self.id, tag_id=tag.id).first() is not None
        return exists

    def is_unfinished(self, dataset: "DatasetDatabase") -> bool:
        """
        Check if the sample is unfinished.

        A sample is considered unfinished if:
        - It has no completions.
        - There are "Work In Progress" tags (currently just check if any tag starts with "WIP").
        """
        return len(self.completions) == 0 or any(tag.name.startswith("WIP") for tag in self.get_tags(dataset))
