"""ORM models for storing token log probability traces alongside completions."""

import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, DateTime

from py_fade.dataset.dataset_base import dataset_base

from py_fade.data_formats.base_data_classes import CommonCompletionLogprobsProtocol
from py_fade.providers.llm_response import LLMResponseLogprobs, SinglePositionTokenLogprobs

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.providers.llm_response import LLMResponse


class PromptCompletionLogprobs(dataset_base):
    """
    Per-model logprobs for a specific sampled completion.

    Implements `CommonCompletionLogprobsProtocol` for interoperability with LLMResponse and logprobs handling.
    """

    __tablename__ = "prompt_completion_logprobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_completion_id: Mapped[int] = mapped_column(ForeignKey("prompt_completions.id"), nullable=False)
    prompt_completion: Mapped["PromptCompletion"] = relationship("PromptCompletion", back_populates="logprobs")
    logprobs_model_id: Mapped[str] = mapped_column(nullable=False)  # Completion and logprobs can be from different models when we evaluate
    # completion across models
    logprobs: Mapped[list] = mapped_column(JSON, nullable=False)  # Store logprobs as JSON, list of dicts for each position
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)
    min_logprob: Mapped[float] = mapped_column(Float, nullable=False)  # Minimum logprob of sampled tokens
    avg_logprob: Mapped[float] = mapped_column(Float, nullable=False)  # Average logprob of sampled tokens

    def to_metadata_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the logprob metadata."""

        return {
            "id": self.id,
            "prompt_completion_id": self.prompt_completion_id,
            "logprobs_model_id": self.logprobs_model_id,
            "min_logprob": self.min_logprob,
            "avg_logprob": self.avg_logprob,
            "date_created": self.date_created.isoformat(),
        }

    def to_llm_response_logprobs(self) -> LLMResponseLogprobs:
        """
        Convert to LLMResponseLogprobs for interoperability with LLMResponse and logprobs handling.
        """
        converted_logprobs = []
        for lp in self.logprobs:
            converted_logprobs.append(
                SinglePositionTokenLogprobs(
                    token=lp["token"],
                    logprob=lp["logprob"],
                    top_logprobs=lp.get("top_logprobs"),
                ))
        return LLMResponseLogprobs(
            logprobs_model_id=self.logprobs_model_id,
            logprobs=converted_logprobs,
        )

    @classmethod
    def get_or_create_from_llm_response(cls, dataset: "DatasetDatabase", completion: "PromptCompletion",
                                        response: "LLMResponse") -> "PromptCompletionLogprobs":
        """
        Get or create a PromptCompletionLogprobs from LLMResponse.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        if not response.logprobs:
            raise ValueError("LLMResponse does not contain logprobs.")
        return cls.get_or_create_from_llm_response_logprobs(dataset, completion, response.model_id, response.logprobs)

    @classmethod
    def get_or_create_from_llm_response_logprobs(cls, dataset: "DatasetDatabase", completion: "PromptCompletion", model_id: str,
                                                 logprobs: "CommonCompletionLogprobsProtocol") -> "PromptCompletionLogprobs":
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        instance = (dataset.session.query(cls).filter_by(prompt_completion_id=completion.id, logprobs_model_id=model_id).first())
        if not instance:
            if not logprobs:
                raise ValueError("LLMResponse does not contain logprobs.")
            logprob_values = [lp.logprob for lp in logprobs if lp.logprob is not None]
            if not logprob_values:
                raise ValueError("LLMResponse logprobs do not contain any valid logprob values.")
            min_logprob = min(logprob_values)
            avg_logprob = sum(logprob_values) / len(logprob_values)
            instance = cls(
                prompt_completion_id=completion.id,
                logprobs_model_id=model_id,
                logprobs=[{
                    "token": lp.token,
                    "logprob": lp.logprob,
                    "top_logprobs": lp.top_logprobs
                } for lp in logprobs],
                min_logprob=min_logprob,
                avg_logprob=avg_logprob,
            )
            dataset.session.add(instance)
            dataset.session.commit()
        return instance

    def __iter__(self):
        return CommonCompletionLogprobsProtocol.iterable_over_dicts(self.logprobs)
