"""
Fundamental language model data classes.
"""
import logging
from dataclasses import dataclass
from typing import Iterator, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class CommonMessage:
    """
    Single message in Message API format.
    Role: "user", "assistant", or "system".
    """
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class CommonConversation:
    """
    Message API conversation format.
    """
    messages: list[CommonMessage]


@dataclass(slots=True)
class SinglePositionTokenLogprobs:
    """
    Token logprobs for a single token position.
    """

    token: str
    logprob: float
    top_logprobs: list[tuple[str, float]] | None = None  # top N token logprobs if available

    def find_logprob(self, search_token: str) -> float | None:
        """
        Find logprob for given token in top_logprobs if available.
        Returns logprob if found, None otherwise.
        """
        if self.top_logprobs:
            for tok, lp in self.top_logprobs:
                if tok == search_token:
                    return lp
        return None

    @classmethod
    def from_list_of_tuples(cls, data: list[tuple[str, float]]) -> list["SinglePositionTokenLogprobs"]:
        """
        Create list of LLMPTokenLogProbs from list of (token, logprob) tuples.
        """
        return [cls(token=t[0], logprob=t[1]) for t in data]

    @classmethod
    def to_list_of_tuples(cls, data: list["SinglePositionTokenLogprobs"]) -> list[tuple[str, float]]:
        """
        Convert list of LLMPTokenLogProbs to list of (token, logprob) tuples.
        """
        return [(t.token, t.logprob) for t in data]


@runtime_checkable
class CommonCompletionLogprobsProtocol(Protocol):
    """
    Protocol for logprobs associated with a completion and specific model_id.
    """
    logprobs_model_id: str  # Model ID for which these logprobs were generated.
    logprobs: list[SinglePositionTokenLogprobs]  # List of token information and logprobs for each position.
    min_logprob: float | None = None  # min(logprobs), minimal logprob of any token in response
    avg_logprob: float | None = None  # average(logprobs), average logprob of all tokens in response

    def __iter__(self) -> Iterator[SinglePositionTokenLogprobs]:
        """Iterate over logprobs."""
        return iter(self.logprobs)

    @staticmethod
    def iterable_over_dicts(data: list[dict]) -> Iterator[SinglePositionTokenLogprobs]:
        """
        Helper to iterate over list of dicts with keys 'token', 'logprob', 'top_logprobs' as SinglePositionTokenLogprobs.
        """
        for entry in data:
            yield SinglePositionTokenLogprobs(
                token=entry.get("token", ""),
                logprob=entry.get("logprob"),  # type: ignore
                top_logprobs=entry.get("top_logprobs"),
            )


@runtime_checkable
class CommonCompletionProtocol(Protocol):
    """
    Protocol for AI completion result, for shared use between low-level provider code and DB persistent classes.
    """
    model_id: str  # Model ID used to generate this completion originally.
    prompt_conversation: CommonConversation  # converation leading to this response (excluding prefill and response itself)
    completion_text: str  # Full text of the completion.
    prefill: str | None  # Part of completion that wasn't generated, but artificially inserted manually or during beam expansion.
    beam_token: str | None  # Token at which beam tree was forked, if any.
    is_truncated: bool  # Whether the completion was truncated due to max tokens limit.
    is_archived: bool  # Whether this completion is archived and hidden by default.

    def get_logprobs_for_model_id(self, model_id: str) -> CommonCompletionLogprobsProtocol | None:
        """
        Get logprobs for the given model ID, if available.
        Returns `CommonCompletionLogprobsProtocol` compatible result or None if logprobs for the target model_id are not available.
        """
        ...

    def check_full_response_logprobs(self, target_model_id: str | None = None) -> bool:
        """
        Check if logprobs cover the entire completion text.
        Go through logprobs and match tokens to completion_text.
        True if all tokens match and cover full text, False otherwise.
        """
        if not target_model_id:
            target_model_id = self.model_id
        logprobs_entry = self.get_logprobs_for_model_id(target_model_id)
        if not logprobs_entry:
            return False

        result = None
        resp_pos = 0
        for lp in logprobs_entry:
            if lp.logprob is None:
                logging.getLogger("LLMResponse").warning("Logprob is None, cannot match full response logprobs.")
                result = False
                break
            # Check if token matches the response text at current position
            if self.completion_text[resp_pos:resp_pos + len(lp.token)] != lp.token:
                expected_text = self.completion_text[resp_pos:resp_pos + len(lp.token)]
                logging.getLogger("LLMResponse").warning(
                    "Logprob token '%s' does not match response text at position %d, '%s'.",
                    lp.token,
                    resp_pos,
                    expected_text,
                )
                result = False
                break
            resp_pos += len(lp.token)
        if result is None:
            result = resp_pos == len(self.completion_text)
        return result
