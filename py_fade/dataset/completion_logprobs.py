import datetime, hashlib, json
from sqlalchemy import Column, Float, ForeignKey, Integer, String, BLOB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, DateTime
from py_fade.dataset.dataset_base import dataset_base

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.dataset.prompt import PromptRevision
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.sample import Sample
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.providers.llm_response import LLMResponse


class PromptCompletionLogprobs(dataset_base):
    """
    Per-model logprobs for a specific sampled completion.
    """
    __tablename__ = "prompt_completion_logprobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_completion_id: Mapped[int] = mapped_column(ForeignKey("prompt_completions.id"), nullable=False)
    prompt_completion: Mapped["PromptCompletion"] = relationship("PromptCompletion", back_populates="logprobs")
    logprobs_model_id: Mapped[str] = mapped_column(nullable=False) # Completion and logprobs can be from different models when we evaluate completion across models
    logprobs: Mapped[list] = mapped_column(JSON, nullable=False)  # Store logprobs as JSON, list of dicts for each position
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)
    min_logprob: Mapped[float] = mapped_column(Float, nullable=False)  # Minimum logprob of sampled tokens
    avg_logprob: Mapped[float] = mapped_column(Float, nullable=False)  # Average logprob of sampled tokens

    @classmethod
    def get_or_create_from_llm_response(cls, dataset: "DatasetDatabase", completion: "PromptCompletion", response: "LLMResponse") -> "PromptCompletionLogprobs":
        """
        Get or create a PromptCompletionLogprobs from LLMResponse.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        instance = dataset.session.query(cls).filter_by(prompt_completion_id=completion.id, logprobs_model_id=response.model_id).first()
        if not instance:
            if not response.logprobs or len(response.logprobs) == 0:
                raise ValueError("LLMResponse does not contain logprobs.")
            logprob_values = [lp.logprob for lp in response.logprobs if lp.logprob is not None]
            if not logprob_values:
                raise ValueError("LLMResponse logprobs do not contain any valid logprob values.")
            min_logprob = min(logprob_values)
            avg_logprob = sum(logprob_values) / len(logprob_values)
            instance = cls(
                prompt_completion_id=completion.id,
                logprobs_model_id=response.model_id,
                logprobs=[{"token": lp.token, "logprob": lp.logprob, "top_logprobs": lp.top_logprobs} for lp in response.logprobs],
                min_logprob=min_logprob,
                avg_logprob=avg_logprob
            )
            dataset.session.add(instance)
            dataset.session.commit()
        return instance