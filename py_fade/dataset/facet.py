"""
ORM model and helpers for dataset facets.

Pylint:
 - Intentional duplication of ORM model attributes. Easier when each model class is fully visible.
"""
# pylint: disable=duplicate-code

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, Integer, String, desc
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.completion_rating import PromptCompletionRating
    from py_fade.dataset.sample import Sample


class Facet(dataset_base):
    """
    Represents a single Facet item in the dataset.
    """

    __tablename__ = "facets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)
    min_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    min_logprob_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=-1.0)
    avg_logprob_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=-0.4)
    completion_ratings: Mapped[list["PromptCompletionRating"]] = relationship(
        "PromptCompletionRating",
        back_populates="facet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @classmethod
    def get_by_name(cls, dataset: "DatasetDatabase", name: str) -> "Facet | None":
        """
        Retrieve a Facet by its name.
        """
        session = dataset.get_session()
        return session.query(cls).filter_by(name=name).first()

    @classmethod
    def get_by_id(cls, dataset: "DatasetDatabase", facet_id: int) -> "Facet | None":
        """
        Retrieve a Facet by its ID.
        """
        session = dataset.get_session()
        return session.query(cls).filter_by(id=facet_id).first()

    @classmethod
    def get_all(cls, dataset: "DatasetDatabase", order_by_date: bool = True):
        """
        Retrieve all facets from the dataset.

        Args:
            dataset: The dataset database instance
            order_by_date: If True, order by date_created descending (newest first)
        """
        session = dataset.get_session()
        query = session.query(cls)
        if order_by_date:
            query = query.order_by(desc(cls.date_created))

        return query.all()

    @staticmethod
    def get_samples_without_facet(dataset: "DatasetDatabase") -> list["Sample"]:
        """
        Retrieve all samples that are not associated with any facet.

        A sample is not associated with any facet if none of its completions have ratings.

        Args:
            dataset: The dataset database instance

        Returns:
            List of Sample objects not associated with any facet
        """
        from py_fade.dataset.sample import Sample  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.prompt import PromptRevision  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.completion import PromptCompletion  # pylint: disable=import-outside-toplevel
        from sqlalchemy import select  # pylint: disable=import-outside-toplevel

        session = dataset.get_session()

        # Get all samples that have at least one rating
        samples_with_ratings = (select(Sample.id).join(Sample.prompt_revision).join(PromptRevision.completions).join(
            PromptCompletion.ratings).distinct())

        # Get all samples that are NOT in the above set
        samples_without_facet = session.query(Sample).filter(~Sample.id.in_(samples_with_ratings)).all()

        return samples_without_facet

    @classmethod
    def create(cls, dataset: "DatasetDatabase", name: str, description: str, min_rating: int = 7, min_logprob_threshold: float = -1.0,
               avg_logprob_threshold: float = -0.4) -> "Facet":
        """
        Create a new facet and add it to the database.

        Args:
            dataset: The dataset database instance
            name: The name of the facet (must be unique)
            description: The description of the facet
            min_rating: Minimum rating for completion to be considered valid (default 7)
            min_logprob_threshold: Minimum logprob threshold (default -1.0)
            avg_logprob_threshold: Average logprob threshold (default -0.4)

        Returns:
            The created facet

        Raises:
            ValueError: If a facet with the same name already exists
        """
        session = dataset.get_session()

        # Check if facet with this name already exists
        existing_facet = cls.get_by_name(dataset, name)
        if existing_facet:
            raise ValueError(f"A facet with the name '{name}' already exists.")

        facet = cls(
            name=name.strip(),
            description=description.strip(),
            total_samples=0,
            date_created=datetime.datetime.now(),
            min_rating=min_rating,
            min_logprob_threshold=min_logprob_threshold,
            avg_logprob_threshold=avg_logprob_threshold,
        )

        session.add(facet)
        return facet

    def update(self, dataset: "DatasetDatabase", name: str | None = None, description: str | None = None, min_rating: int | None = None,
               min_logprob_threshold: float | None = None, avg_logprob_threshold: float | None = None):
        """
        Update the facet's properties.

        Args:
            dataset: The dataset database instance
            name: New name for the facet (optional)
            description: New description for the facet (optional)
            min_rating: New minimum rating threshold (optional)
            min_logprob_threshold: New minimum logprob threshold (optional)
            avg_logprob_threshold: New average logprob threshold (optional)

        Raises:
            ValueError: If the new name already exists for another facet
        """

        if name is not None and name.strip() != self.name:
            # Check if another facet with this name exists
            existing_facet = self.get_by_name(dataset, name.strip())
            if existing_facet and existing_facet.id != self.id:
                raise ValueError(f"A facet with the name '{name}' already exists.")
            self.name = name.strip()

        if description is not None:
            self.description = description.strip()

        if min_rating is not None:
            self.min_rating = min_rating

        if min_logprob_threshold is not None:
            self.min_logprob_threshold = min_logprob_threshold

        if avg_logprob_threshold is not None:
            self.avg_logprob_threshold = avg_logprob_threshold

    def get_samples(self, dataset: "DatasetDatabase") -> list["Sample"]:
        """
        Retrieve all samples associated with this facet.

        A sample is associated with a facet if any of its completions have been rated for this facet.

        Args:
            dataset: The dataset database instance

        Returns:
            List of Sample objects associated with this facet
        """
        from py_fade.dataset.sample import Sample  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.prompt import PromptRevision  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.completion import PromptCompletion  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.completion_rating import PromptCompletionRating  # pylint: disable=import-outside-toplevel

        session = dataset.get_session()

        # Query to get all samples that have completions rated for this facet
        # Join: Sample -> PromptRevision -> PromptCompletion -> PromptCompletionRating (filtered by facet_id)
        samples = (session.query(Sample).join(Sample.prompt_revision).join(PromptRevision.completions).join(
            PromptCompletion.ratings).filter(PromptCompletionRating.facet_id == self.id).distinct().all())

        return samples

    def delete(self, dataset: "DatasetDatabase"):
        """
        Delete this facet from the database.

        Args:
            dataset: The dataset database instance
        """
        session = dataset.get_session()
        session.delete(self)

    def __str__(self) -> str:
        """
        String representation of the facet.
        """

        return f"Facet(id={self.id}, name='{self.name}', samples={self.total_samples})"

    def __repr__(self) -> str:
        """
        Detailed string representation of the facet.
        """

        return (f"Facet(id={self.id}, name='{self.name}', description='{self.description[:50]}...', "
                f"total_samples={self.total_samples}, date_created={self.date_created})")
