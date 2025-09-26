"""
Single sampled completion of single specific prompt under specific parameters.
"""

import hashlib
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.prompt import PromptRevision
    from py_fade.providers.llm_response import LLMResponse
    from py_fade.dataset.facet import Facet


class PromptCompletion(dataset_base):
    """
    Represents a single sampled completion of a specific prompt under specific parameters.
    """

    __tablename__ = "prompt_completions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_revision_id: Mapped[int] = mapped_column(
        ForeignKey("prompt_revisions.id"), nullable=False
    )
    prompt_revision: Mapped["PromptRevision"] = relationship(
        "PromptRevision", back_populates="completions"
    )
    logprobs: Mapped[list["PromptCompletionLogprobs"]] = relationship(
        "PromptCompletionLogprobs",
        back_populates="prompt_completion",
        cascade="all, delete-orphan",
        lazy="select",
    )
    ratings: Mapped[list["PromptCompletionRating"]] = relationship(
        "PromptCompletionRating",
        back_populates="prompt_completion",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sha256: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA256 hash of completion_text for deduplication.
    # Allow different (prompt_revision_id, sha256) pairs.
    model_id: Mapped[str] = mapped_column(nullable=False)
    temperature: Mapped[float] = mapped_column(nullable=False)
    top_k: Mapped[int] = mapped_column(nullable=False)
    prefill: Mapped[str | None] = mapped_column(nullable=True)
    beam_token: Mapped[str | None] = mapped_column(nullable=True)
    # Token at which beam tree was forked, if any.
    completion_text: Mapped[str] = mapped_column(nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    context_length: Mapped[int] = mapped_column(nullable=False)
    max_tokens: Mapped[int] = mapped_column(nullable=False)
    is_truncated: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(nullable=False, default=False)

    @classmethod
    def get_or_create_from_llm_response(
        cls, dataset: "DatasetDatabase", prompt_revision: "PromptRevision", response: "LLMResponse"
    ) -> "PromptCompletion":
        """
        Get or create a PromptCompletion from LLMResponse.
        """
        if not dataset.session:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )
        sha256 = hashlib.sha256(response.full_response_text.encode("utf-8")).hexdigest()
        instance = (
            dataset.session.query(cls)
            .filter_by(prompt_revision_id=prompt_revision.id, sha256=sha256)
            .first()
        )
        if not instance:
            instance = cls(
                sha256=sha256,
                prompt_revision_id=prompt_revision.id,
                model_id=response.model_id,
                temperature=response.temperature,
                top_k=response.top_k,
                completion_text=response.full_response_text,
                tags=[],
                prefill=response.prefill,
                beam_token=response.beam_token,
                is_truncated=response.is_truncated,
                context_length=response.context_length,
                max_tokens=response.max_tokens,
            )
            dataset.session.add(instance)
            dataset.session.commit()

        # Also create associated logprobs entry if logprobs are present
        if (
            response.logprobs
            and len(response.logprobs) > 0
            and response.check_full_response_logprobs()
        ):
            # Create associated logprobs entry if logprobs are present. The helper
            # handles persistence and returns the instance if needed; we don't use
            # the return value here.
            PromptCompletionLogprobs.get_or_create_from_llm_response(dataset, instance, response)
        else:
            print(
                "LLMResponse does not contain valid logprobs for PromptCompletionLogprobs creation."
            )
        return instance

    def rating_for_facet(self, facet: "Facet | None") -> "PromptCompletionRating | None":
        """Return the cached rating for *facet* if it has been loaded."""

        if not facet:
            return None
        return next((rating for rating in self.ratings if rating.facet_id == facet.id), None)
