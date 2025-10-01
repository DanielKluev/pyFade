"""
Single sampled completion of single specific prompt under specific parameters.
"""

import hashlib
import logging
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from py_fade.data_formats.base_data_classes import CommonCompletionLogprobsProtocol, CommonConversation, CommonCompletionProtocol
from py_fade.providers.flat_prefix_template import parse_flat_prefix_string
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

    Implements `CommonCompletionProtocol` for interoperability with LLMResponse and logprobs handling.
    """

    __tablename__ = "prompt_completions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_revision_id: Mapped[int] = mapped_column(ForeignKey("prompt_revisions.id"), nullable=False)
    prompt_revision: Mapped["PromptRevision"] = relationship("PromptRevision", back_populates="completions")
    parent_completion_id: Mapped[int | None] = mapped_column(ForeignKey("prompt_completions.id"), nullable=True)
    parent_completion: Mapped["PromptCompletion | None"] = relationship("PromptCompletion", remote_side=[id],
                                                                        back_populates="child_completions", lazy="select")
    child_completions: Mapped[list["PromptCompletion"]] = relationship("PromptCompletion", back_populates="parent_completion",
                                                                       lazy="select")

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
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hash of completion_text for deduplication.
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
    def get_or_create_from_llm_response(cls, dataset: "DatasetDatabase", prompt_revision: "PromptRevision", response: "LLMResponse",
                                        parent_completion_id: int | None = None) -> "PromptCompletion":
        """
        Get or create a PromptCompletion from LLMResponse.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        sha256 = hashlib.sha256(response.completion_text.encode("utf-8")).hexdigest()
        instance = (dataset.session.query(cls).filter_by(prompt_revision_id=prompt_revision.id, sha256=sha256).first())
        if not instance:
            instance = cls(
                sha256=sha256,
                prompt_revision_id=prompt_revision.id,
                parent_completion_id=parent_completion_id,
                model_id=response.model_id,
                temperature=response.temperature,
                top_k=response.top_k,
                completion_text=response.completion_text,
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
        if (response.logprobs and response.check_full_response_logprobs()):
            PromptCompletionLogprobs.get_or_create_from_llm_response(dataset, instance, response)
        else:
            logging.getLogger("PromptCompletion").warning(
                "LLMResponse does not contain valid logprobs for PromptCompletionLogprobs creation.")
        return instance

    def rating_for_facet(self, facet: "Facet | None") -> "PromptCompletionRating | None":
        """Return the cached rating for *facet* if it has been loaded."""

        if not facet:
            return None
        return next((rating for rating in self.ratings if rating.facet_id == facet.id), None)

    @staticmethod
    def _compute_sha256(text: str) -> str:
        """Compute SHA256 hash of text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get_logprobs_for_model_id(self, model_id: str) -> CommonCompletionLogprobsProtocol | None:
        """
        Get logprobs for the given model ID, if available.
        Returns `CommonCompletionLogprobsProtocol` compatible result or None if logprobs for the target model_id are not available.
        """
        if not self.logprobs:
            return None
        for lp in self.logprobs:
            if lp.logprobs_model_id == model_id:
                return lp
        return None

    @property
    def prompt_conversation(self) -> CommonConversation:
        """
        Reconstruct the prompt conversation from the associated PromptRevision text.
        """
        prompt_text = self.prompt_revision.prompt_text
        return parse_flat_prefix_string(prompt_text)

    def check_full_response_logprobs(self, target_model_id: str | None = None) -> bool:
        """
        Check if logprobs cover the entire completion text.
        Go through logprobs and match tokens to completion_text.
        True if all tokens match and cover full text, False otherwise.
        """
        return CommonCompletionProtocol.check_full_response_logprobs(self, target_model_id)
