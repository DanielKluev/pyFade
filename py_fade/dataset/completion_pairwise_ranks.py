"""
ORM model class that stores per-facet pairwise rankings for completions.
I.e. which completion is preferred over another for a specific facet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from py_fade.dataset.dataset_base import dataset_base, get_session_with_assertion

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet


class PromptCompletionPairwiseRanking(dataset_base):
    """Persistent pairwise ranking for two completions scoped to a specific facet."""

    __tablename__ = "prompt_completion_pairwise_rankings"
    __table_args__ = (UniqueConstraint(
        "better_completion_id",
        "worse_completion_id",
        "facet_id",
        name="uq_prompt_completion_pairwise_rankings_better_worse_facet",
    ),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    better_completion_id: Mapped[int] = mapped_column(ForeignKey("prompt_completions.id"), nullable=False)
    better_completion: Mapped["PromptCompletion"] = relationship("PromptCompletion", foreign_keys=[better_completion_id])
    worse_completion_id: Mapped[int] = mapped_column(ForeignKey("prompt_completions.id"), nullable=False)
    worse_completion: Mapped["PromptCompletion"] = relationship("PromptCompletion", foreign_keys=[worse_completion_id])
    facet_id: Mapped[int] = mapped_column(ForeignKey("facets.id"), nullable=False)
    facet: Mapped["Facet"] = relationship("Facet")

    @classmethod
    def get(cls, dataset: "DatasetDatabase", better_completion: "PromptCompletion", worse_completion: "PromptCompletion",
            facet: "Facet") -> "PromptCompletionPairwiseRanking | None":
        """
        Return the existing pairwise ranking for *better_completion*, *worse_completion* and *facet*, if any.
        """

        session = get_session_with_assertion(dataset)
        return (session.query(cls).filter_by(
            better_completion=better_completion,
            worse_completion=worse_completion,
            facet=facet,
        ).first())

    @classmethod
    def get_or_create(cls, dataset: "DatasetDatabase", better_completion: "PromptCompletion", worse_completion: "PromptCompletion",
                      facet: "Facet") -> "PromptCompletionPairwiseRanking":
        """
        Get or create the pairwise ranking for *better_completion*, *worse_completion* and *facet*.
        """

        session = get_session_with_assertion(dataset)
        instance = cls.get(dataset, better_completion, worse_completion, facet)
        if instance is None:
            instance = cls(
                better_completion=better_completion,
                worse_completion=worse_completion,
                facet=facet,
            )
            session.add(instance)
            session.commit()
        return instance
