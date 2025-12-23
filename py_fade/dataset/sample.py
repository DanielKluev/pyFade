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
    from py_fade.dataset.sample_image import SampleImage
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

    # One-to-many relationship with images (file path references)
    images: Mapped[List["SampleImage"]] = relationship("SampleImage", back_populates="sample", cascade="all, delete-orphan", lazy="select")

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

        Args:
            dataset: The dataset database instance
            data_filter: Optional DataFilter to apply

        Returns:
            List of Sample objects matching the filter criteria
        """
        session = dataset.get_session()

        query = session.query(Sample)
        if data_filter:
            query = data_filter.apply_to_query(query)

        return query.all()

    @classmethod
    def fetch_with_complex_filter(cls, dataset: "DatasetDatabase", filter_rules: list) -> list["Sample"]:
        """
        Fetch samples that match all the provided filter rules (AND logic).

        Args:
            dataset: The dataset database instance
            filter_rules: List of FilterRule objects to evaluate

        Returns:
            List of Sample objects matching all filter rules
        """
        from py_fade.dataset.filter_rule import FilterRule  # pylint: disable=import-outside-toplevel

        # Get all samples first
        all_samples = cls.fetch_with_filter(dataset, None)

        # If no rules, return all samples
        if not filter_rules:
            return all_samples

        # Parse rules if they're dictionaries
        rules = []
        for rule in filter_rules:
            if isinstance(rule, dict):
                rules.append(FilterRule.from_dict(rule))
            else:
                rules.append(rule)

        # Filter samples by evaluating all rules with AND logic
        filtered_samples = []
        for sample in all_samples:
            if all(rule.evaluate(sample, dataset) for rule in rules):
                filtered_samples.append(sample)

        return filtered_samples

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

    def get_facets(self, dataset: "DatasetDatabase") -> list["Facet"]:
        """
        Get all facets that have ratings for this sample.

        Returns a list of Facet objects that have at least one rating for any completion
        in this sample's prompt revision, ordered by facet name.

        Args:
            dataset: The dataset database instance

        Returns:
            List of Facet objects that have ratings for this sample
        """
        from py_fade.dataset.facet import Facet  # pylint: disable=import-outside-toplevel

        if not self.prompt_revision:
            return []

        session = dataset.get_session()

        # Get all unique facet IDs from ratings of this sample's completions
        facet_ids = set()
        for completion in self.prompt_revision.completions:
            for rating in completion.ratings:
                facet_ids.add(rating.facet_id)

        if not facet_ids:
            return []

        # Query facets by IDs and order by name
        facets = session.query(Facet).filter(Facet.id.in_(facet_ids)).order_by(Facet.name).all()
        return list(facets)

    def get_highest_rating_for_facet(self, facet: "Facet") -> int | None:
        """
        Get the highest rating of any completion for this sample for the given facet.

        Iterates through all completions of this sample's prompt revision and returns
        the maximum rating found for the specified facet.

        Args:
            facet: The facet to check ratings for

        Returns:
            The highest rating (0-10) if any completions have ratings for this facet, None otherwise
        """
        from py_fade.dataset.facet import Facet  # pylint: disable=import-outside-toplevel,unused-import

        if not self.prompt_revision:
            return None

        max_rating = None
        for completion in self.prompt_revision.completions:
            for rating in completion.ratings:
                if rating.facet_id == facet.id:
                    if max_rating is None or rating.rating > max_rating:
                        max_rating = rating.rating
        return max_rating

    def get_images(self, dataset: "DatasetDatabase") -> List["SampleImage"]:
        """
        Get all images attached to this sample.

        Returns a list of SampleImage objects ordered by date created.

        Args:
            dataset: The dataset database instance

        Returns:
            List of SampleImage objects attached to this sample
        """
        from py_fade.dataset.sample_image import SampleImage  # pylint: disable=import-outside-toplevel
        return SampleImage.get_for_sample(dataset, self)

    def add_image(self, dataset: "DatasetDatabase", file_path: str) -> "SampleImage":
        """
        Add an image attachment to this sample.

        Creates a SampleImage association between this sample and the image file.
        The image file is not copied - only the file path reference is stored.

        Args:
            dataset: The dataset database instance
            file_path: The file path to the image

        Returns:
            The created SampleImage instance

        Raises:
            ValueError: If the file path is empty or the image is already attached
        """
        from py_fade.dataset.sample_image import SampleImage  # pylint: disable=import-outside-toplevel
        sample_image = SampleImage.create(dataset, self, file_path)
        self.log.debug("Added image '%s' to sample %s", sample_image.filename, self.id)
        return sample_image

    def remove_image(self, dataset: "DatasetDatabase", sample_image: "SampleImage") -> None:
        """
        Remove an image attachment from this sample.

        Deletes the SampleImage association.

        Args:
            dataset: The dataset database instance
            sample_image: The SampleImage to remove

        Raises:
            ValueError: If the image is not attached to this sample
        """
        if sample_image.sample_id != self.id:
            raise ValueError(f"Image {sample_image.id} is not attached to sample {self.id}.")
        sample_image.delete(dataset)
        self.log.debug("Removed image '%s' from sample %s", sample_image.filename, self.id)

    def has_images(self) -> bool:
        """
        Check if this sample has any attached images.

        Uses the lazy-loaded images relationship.

        Returns:
            True if the sample has at least one image, False otherwise
        """
        return len(self.images) > 0

    def delete(self, dataset: "DatasetDatabase") -> None:
        """
        Delete this sample from the database.

        Cascades to delete associated sample_tags and sample_images.
        Does NOT delete the prompt_revision or completions - those may be shared.

        Args:
            dataset: The dataset database instance
        """
        session = dataset.get_session()
        session.delete(self)
        session.commit()
        self.log.info("Deleted sample: id=%s, title=%s", self.id, self.title)
