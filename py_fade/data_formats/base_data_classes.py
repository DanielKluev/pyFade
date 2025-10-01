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

    def as_dict(self) -> dict[str, str]:
        """
        Return message as dict with 'role' and 'content'.
        """
        return {"role": self.role, "content": self.content}

    def __eq__(self, value: object) -> bool:
        if isinstance(value, CommonMessage):
            return self.role == value.role and self.content == value.content
        if isinstance(value, dict):
            return self.role == value.get("role") and self.content == value.get("content")
        return False


@dataclass(frozen=True, slots=True)
class CommonConversation:
    """
    Message API conversation format.
    """
    messages: list[CommonMessage]

    @classmethod
    def from_single_user(cls, user_message: str) -> "CommonConversation":
        """
        Create CommonConversation from a single user message string.
        """
        return cls(messages=[CommonMessage(role="user", content=user_message)])

    def append(self, message: CommonMessage | dict) -> None:
        """
        Append a message to the conversation.
        Accepts either CommonMessage or dict with 'role' and 'content'.
        """
        if isinstance(message, dict):
            if "role" in message and "content" in message:
                message = CommonMessage(role=message["role"], content=message["content"])
            else:
                raise ValueError("Dict message must have 'role' and 'content' keys.")

        if not isinstance(message, CommonMessage):
            raise ValueError("Message must be CommonMessage or dict with 'role' and 'content'.")

        if message.role not in ("user", "assistant", "system"):
            raise ValueError("Message role must be 'user', 'assistant', or 'system'.")

        if self.messages:
            if self.messages[-1].role == message.role:
                raise ValueError("Cannot append two consecutive messages with the same role.")
            if message.role == "system":
                raise ValueError("System messages can only appear at the start of the conversation.")
        self.messages.append(message)

    def copy_with_prefill(self, prefill: str | None) -> "CommonConversation":
        """
        Return a copy of the conversation with prefill inserted as the start of the assistant message.

        If previous turn is not user, raise ValueError, as prefill can only be start of assistant message.        
        If prefill is None or empty, returns a copy of the original conversation.
        """
        if not prefill:
            return CommonConversation(messages=self.messages.copy())

        if not self.messages or self.messages[-1].role != "user":
            raise ValueError("Prefill can only be added to the start of an assistant message.")

        new_messages = self.messages.copy()
        new_messages.append(CommonMessage(role="assistant", content=prefill))
        return CommonConversation(messages=new_messages)

    def as_list(self) -> list[dict[str, str]]:
        """
        Return conversation as list of dicts with 'role' and 'content'.
        """
        return [msg.as_dict() for msg in self.messages]

    def __eq__(self, value: object) -> bool:
        if isinstance(value, CommonConversation):
            return self.messages == value.messages
        if isinstance(value, list):
            return self.as_list() == value
        return False


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
    temperature: float
    top_k: int
    is_truncated: bool  # Whether the completion was truncated due to max tokens limit.
    is_archived: bool  # Whether this completion is archived and hidden by default.

    def get_logprobs_for_model_id(self, model_id: str) -> CommonCompletionLogprobsProtocol | None:
        """
        Get logprobs for the given model ID, if available.
        Returns `CommonCompletionLogprobsProtocol` compatible result or None if logprobs for the target model_id are not available.
        """
        raise NotImplementedError

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

        resp_pos = 0
        for lp in logprobs_entry:
            if lp.logprob is None:
                logging.getLogger("LLMResponse").warning("Logprob is None, cannot match full response logprobs.")
                return False
            # Check if token matches the response text at current position
            if self.completion_text[resp_pos:resp_pos + len(lp.token)] != lp.token:
                expected_text = self.completion_text[resp_pos:resp_pos + len(lp.token)]
                logging.getLogger("LLMResponse").warning(
                    "Logprob token '%s' does not match response text at position %d, '%s'.",
                    lp.token,
                    resp_pos,
                    expected_text,
                )
                return False
            resp_pos += len(lp.token)
        return resp_pos == len(self.completion_text)
