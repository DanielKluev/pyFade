"""ORM model class that stores per-facet ratings for completions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from py_fade.dataset.dataset_base import dataset_base, get_session_with_assertion

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet


class PromptCompletionRating(dataset_base):
    """Persistent rating (0-10) for a completion scoped to a specific facet."""

    __tablename__ = "prompt_completion_ratings"
    __table_args__ = (
        UniqueConstraint(
            "prompt_completion_id",
            "facet_id",
            name="uq_prompt_completion_ratings_completion_facet",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_completion_id: Mapped[int] = mapped_column(
        ForeignKey("prompt_completions.id"), nullable=False
    )
    prompt_completion: Mapped["PromptCompletion"] = relationship(
        "PromptCompletion", back_populates="ratings"
    )
    facet_id: Mapped[int] = mapped_column(ForeignKey("facets.id"), nullable=False)
    facet: Mapped["Facet"] = relationship("Facet", back_populates="completion_ratings")
    rating: Mapped[int] = mapped_column(nullable=False)

    @classmethod
    def get(
        cls,
        dataset: "DatasetDatabase",
        completion: "PromptCompletion",
        facet: "Facet",
    ) -> "PromptCompletionRating | None":
        """Return the existing rating for *completion* and *facet*, if any."""

        session = get_session_with_assertion(dataset)
        return (
            session.query(cls)
            .filter_by(prompt_completion_id=completion.id, facet_id=facet.id)
            .one_or_none()
        )

    @classmethod
    def set_rating(
        cls,
        dataset: "DatasetDatabase",
        completion: "PromptCompletion",
        facet: "Facet",
        rating: int,
    ) -> "PromptCompletionRating":
        """Create or update the rating for *completion*/*facet* to ``rating`` (0-10)."""

        session = get_session_with_assertion(dataset)
        if rating < 0 or rating > 10:
            raise ValueError("Rating must be between 0 and 10, inclusive.")

        instance = cls.get(dataset, completion, facet)
        if instance:
            instance.rating = rating
        else:
            instance = cls(
                prompt_completion=completion,
                facet=facet,
                rating=rating,
            )
            session.add(instance)

        session.commit()
        session.refresh(instance)
        return instance

    def delete(self, dataset: "DatasetDatabase") -> None:
        """Remove this rating from the dataset and commit the change."""

        if not dataset.session:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )
        session = dataset.session
        session.delete(self)
        session.commit()
