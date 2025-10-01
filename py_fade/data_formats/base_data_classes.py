"""
Fundamental language model data classes.
"""
import logging
from dataclasses import dataclass
from typing import Iterator, Protocol, runtime_checkable, Generic


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


@dataclass(frozen=True, slots=True)
class SinglePositionToken:
    """
    Token ID and logprob for a single token position.
    """

    token_id: int
    token_str: str
    logprob: float


class SinglePositionTopLogprobs(list[SinglePositionToken]):
    """
    List of possible alternative tokens and their logprobs for a single token position, sorted by logprob descending.
    """

    @classmethod
    def from_list_of_dicts(cls, data: list[dict]) -> "SinglePositionTopLogprobs":
        result = cls()
        for entry in data:
            token_str = entry.get("token_str")
            logprob = entry.get("logprob")
            token_id = entry.get("token_id", -1)
            if token_str is None or logprob is None:
                raise ValueError("Each entry must have 'token_str' and 'logprob'.")
            result.append(SinglePositionToken(token_id=token_id, token_str=token_str, logprob=logprob))
        return result


@dataclass(frozen=True, slots=True)
class SinglePositionTokenWithAlternatives:
    """
    Token ID and logprob for a single token position, along with top alternative tokens and their logprobs.
    """
    token: SinglePositionToken
    top_logprobs: SinglePositionTopLogprobs


class CompletionTopLogprobs(list[SinglePositionTopLogprobs]):
    """
    List of all token positions, each with alternative tokens for that position.
    For i-th element, represents top alternative tokens and logprobs for i-th position in the completion.

    If no top logprobs were calculated, this is an empty list.
    """

    @classmethod
    def from_list_of_lists(cls, data: list[list]) -> "CompletionTopLogprobs":
        result = cls()
        for position_list in data:
            top_logprobs = SinglePositionTopLogprobs.from_list_of_dicts(position_list)
            result.append(top_logprobs)
        return result


class CompletionTokenLogprobs(list[SinglePositionToken]):
    """
    List of all token positions, each with sampled token and its logprob.
    Each element represents the actual token sampled at that position with it's logprob.
    """

    @classmethod
    def from_list_of_dicts(cls, data: list[dict]) -> "CompletionTokenLogprobs":
        """
        Create CompletionTokenLogprobs from list of dicts with 'token_str', 'token_id', 'logprob'.
        """
        result = cls()
        for entry in data:
            token_str = entry.get("token_str")
            logprob = entry.get("logprob")
            token_id = entry.get("token_id", -1)
            if token_str is None or logprob is None:
                raise ValueError("Each entry must have 'token_str' and 'logprob'.")
            result.append(SinglePositionToken(token_id=token_id, token_str=token_str, logprob=logprob))
        return result


class CommonCompletionLogprobs:
    """
    Protocol for logprobs associated with a completion and specific model_id.
    """
    logprobs_model_id: str  # Model ID for which these logprobs were generated.
    sampled_logprobs: CompletionTokenLogprobs  # Logprobs of sampled tokens, matching completion text.
    alternative_logprobs: CompletionTopLogprobs  # List of top alternative tokens and their logprobs.
    min_logprob: float | None = None  # min(sampled_logprobs), minimal logprob of any token in response
    avg_logprob: float | None = None  # average(sampled_logprobs), average logprob of all tokens in response


@dataclass(frozen=True, slots=True)
class CompletionPrefill:
    """
    Unified representation of pre-generated completion text.

    Key issue is that we may have native "model-generated" tokenization or not.
    So this class unifies both cases, plain string and tokenized with logprobs.
    """
    prefill_text: str  # Full prefill text.
    prefill_tokenized: CompletionTokenLogprobs | None = None  # Tokenized prefill with logprobs, if available.


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

    def get_logprobs_for_model_id(self, model_id: str) -> CommonCompletionLogprobs | None:
        """
        Get logprobs for the given model ID, if available.
        Returns `CommonCompletionLogprobs` compatible result or None if logprobs for the target model_id are not available.
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
        for lp in logprobs_entry.sampled_logprobs:
            if lp.logprob is None:
                logging.getLogger("CommonCompletionProtocol").warning("Logprob is None, cannot match full response logprobs.")
                return False
            # Check if token matches the response text at current position
            if self.completion_text[resp_pos:resp_pos + len(lp.token_str)] != lp.token_str:
                expected_text = self.completion_text[resp_pos:resp_pos + len(lp.token_str)]
                logging.getLogger("CommonCompletionProtocol").warning(
                    "Logprob token '%s' does not match response text at position %d, '%s'.",
                    lp.token_str,
                    resp_pos,
                    expected_text,
                )
                return False
            resp_pos += len(lp.token_str)
        return resp_pos == len(self.completion_text)
