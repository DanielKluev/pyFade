"""ORM models for storing token log probability traces alongside completions."""

import datetime
from typing import TYPE_CHECKING, Any
import zstandard
import msgpack

from sqlalchemy import Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, DateTime, LargeBinary

from py_fade.dataset.dataset_base import dataset_base

from py_fade.data_formats.base_data_classes import CommonCompletionLogprobs, CompletionTokenLogprobs, CompletionTopLogprobs

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.providers.llm_response import LLMResponse


class PromptCompletionLogprobs(dataset_base, CommonCompletionLogprobs):
    """
    Per-model logprobs for a specific sampled completion.

    Implements `CommonCompletionLogprobsProtocol` for interoperability with LLMResponse and logprobs handling.

    Note: `sampled_logprobs_json` and `alternative_logprobs_bin` are the actual mapped columns.
    `alternative_logprobs` and `sampled_logprobs` are cached properties to convert to/from in-memory structures.

    `alternative_logprobs_bin` stores bz2-compressed JSON to save space in the database. 
    Still, it's eating up space aggressively, so we need pruning strategies:
    - Strip `alternative_logprobs` from archived completions.
    - Manual sample finalization? Once we got desired data, we can drop alternative logprobs from all completions.
    """

    __tablename__ = "prompt_completion_logprobs"
    __allow_unmapped__ = True  # _sampled_logprobs and _alternative_logprobs are not mapped

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_completion_id: Mapped[int] = mapped_column(ForeignKey("prompt_completions.id"), nullable=False)
    prompt_completion: Mapped["PromptCompletion"] = relationship("PromptCompletion", back_populates="logprobs")
    logprobs_model_id: Mapped[str] = mapped_column(nullable=False)  # Completion and logprobs can be from different models when we evaluate
    # completion across models
    sampled_logprobs_json: Mapped[list] = mapped_column(JSON, nullable=False)  # Sampled token logprobs matching completion text
    alternative_logprobs_bin: Mapped[bytes] = mapped_column(LargeBinary,
                                                            nullable=False)  # Alternative token logprobs per position, bz2-compressed JSON
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)
    min_logprob: Mapped[float] = mapped_column(Float, nullable=False)  # Minimum logprob of sampled tokens
    avg_logprob: Mapped[float] = mapped_column(Float, nullable=False)  # Average logprob of sampled tokens

    # Cache
    _sampled_logprobs: CompletionTokenLogprobs | None = None
    _alternative_logprobs: CompletionTopLogprobs | None = None

    @property
    def sampled_logprobs(self) -> CompletionTokenLogprobs:
        """
        Logprobs of sampled tokens, matching completion text.

        Cached after first access. Should be modified only through `sampled_logprobs` setter.
        """
        if self._sampled_logprobs is None:
            self._sampled_logprobs = CompletionTokenLogprobs.from_list_of_dicts(self.sampled_logprobs_json)
        return self._sampled_logprobs

    @sampled_logprobs.setter
    def sampled_logprobs(self, value: CompletionTokenLogprobs | None) -> None:
        if value is None:
            return  # Hack to have both sampled_logprobs and sampled_logprobs_json in constructor
        self._sampled_logprobs = value
        self.sampled_logprobs_json = value.to_list_of_dicts()

    @property
    def alternative_logprobs(self) -> CompletionTopLogprobs:
        """
        List of top alternative tokens and their logprobs.
        
        Cached after first access. Should be modified only through `alternative_logprobs` setter.
        """
        if self._alternative_logprobs is None:
            raw_msgpack = zstandard.decompress(self.alternative_logprobs_bin)
            self._alternative_logprobs = CompletionTopLogprobs.from_dict_of_lists(msgpack.unpackb(raw_msgpack))
        return self._alternative_logprobs

    @staticmethod
    def compress_alternative_logprobs(alternative_logprobs: CompletionTopLogprobs) -> bytes:
        """Compress alternative_logprobs to store in database."""
        raw_msgpack: bytes = msgpack.packb(alternative_logprobs.to_dict_of_lists(), use_bin_type=True)  # type: ignore
        compressed = zstandard.compress(raw_msgpack, level=22)
        return compressed

    @alternative_logprobs.setter
    def alternative_logprobs(self, value: CompletionTopLogprobs | None) -> None:
        if value is None:
            return  # Hack to have both alternative_logprobs and alternative_logprobs_json in constructor
        self._alternative_logprobs = value
        self.alternative_logprobs_bin = self.compress_alternative_logprobs(value)

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
                                                 logprobs: "CommonCompletionLogprobs") -> "PromptCompletionLogprobs":
        """
        Get or create PromptCompletionLogprobs from LLMResponse logprobs.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        instance = (dataset.session.query(cls).filter_by(prompt_completion_id=completion.id, logprobs_model_id=model_id).first())
        if not instance:
            if not logprobs:
                raise ValueError("LLMResponse does not contain logprobs.")

            # sampled_logprobs serialization
            sampled_logprobs_list = logprobs.sampled_logprobs.to_list_of_dicts()

            # alternative_logprobs serialization
            alternative_logprobs_bin = cls.compress_alternative_logprobs(logprobs.alternative_logprobs)

            min_logprob = logprobs.min_logprob
            avg_logprob = logprobs.avg_logprob

            # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
            # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
            instance = cls(
                prompt_completion_id=completion.id,
                logprobs_model_id=model_id,
                sampled_logprobs=None,
                sampled_logprobs_json=sampled_logprobs_list,
                alternative_logprobs=None,
                alternative_logprobs_bin=alternative_logprobs_bin,
                min_logprob=min_logprob,
                avg_logprob=avg_logprob,
            )
            # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
            dataset.session.add(instance)
            dataset.session.commit()
        return instance
