"""
Fundamental language model data classes.
"""
import logging
import base64
from dataclasses import dataclass, field
import struct
from typing import Iterable, Protocol, runtime_checkable

from py_fade.data_formats.utils import is_equal_utf_8, try_decode_utf_8


@dataclass(frozen=True, slots=True)
class MessageImage:
    """
    Reference to an image attached to a message.

    Stores file path reference to image file. Images are not embedded in the message,
    only the file path is stored. For API calls, the actual image data would be loaded
    from the file path when needed.
    """
    file_path: str
    filename: str

    @classmethod
    def from_file_path(cls, file_path: str) -> "MessageImage":
        """
        Create a MessageImage from a file path.

        Args:
            file_path: Path to the image file

        Returns:
            MessageImage instance with file_path and extracted filename
        """
        import pathlib  # pylint: disable=import-outside-toplevel
        path = pathlib.Path(file_path)
        return cls(file_path=str(path), filename=path.name)

    def as_dict(self) -> dict[str, str]:
        """
        Return image reference as dict with 'file_path' and 'filename'.
        """
        return {"file_path": self.file_path, "filename": self.filename}

    def file_exists(self) -> bool:
        """
        Check if the image file exists at the stored file path.

        Returns:
            True if the file exists, False otherwise
        """
        import pathlib  # pylint: disable=import-outside-toplevel
        return pathlib.Path(self.file_path).exists()


@dataclass(frozen=True, slots=True)
class CommonMessage:
    """
    Single message in Message API format.

    Role: "user", "assistant", or "system".
    Optionally includes image references for multimodal content.
    Images are only applicable for "user" role messages.
    """
    role: str
    content: str
    images: tuple[MessageImage, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, str | list[dict[str, str]]]:
        """
        Return message as dict with 'role', 'content', and optionally 'images'.
        """
        result: dict[str, str | list[dict[str, str]]] = {"role": self.role, "content": self.content}
        if self.images:
            result["images"] = [img.as_dict() for img in self.images]
        return result

    def __eq__(self, value: object) -> bool:
        if isinstance(value, CommonMessage):
            return self.role == value.role and self.content == value.content and self.images == value.images
        if isinstance(value, dict):
            # For backward compatibility, compare without images if dict doesn't have images
            role_match = self.role == value.get("role")
            content_match = self.content == value.get("content")
            if "images" in value:
                images_match = list(self.images) == [MessageImage(**img) for img in value.get("images", [])]
                return role_match and content_match and images_match
            return role_match and content_match and not self.images
        return False

    def has_images(self) -> bool:
        """
        Check if this message has any attached images.

        Returns:
            True if the message has at least one image, False otherwise
        """
        return len(self.images) > 0


@dataclass(frozen=True, slots=True)
class CommonConversation:
    """
    Message API conversation format.

    Supports multimodal conversations with images attached to user messages.
    """
    messages: list[CommonMessage]

    @classmethod
    def from_single_user(cls, user_message: str, images: tuple[MessageImage, ...] | None = None) -> "CommonConversation":
        """
        Create CommonConversation from a single user message string.

        Args:
            user_message: The user message content
            images: Optional tuple of MessageImage references to attach to the message
        """
        return cls(messages=[CommonMessage(role="user", content=user_message, images=images or ())])

    def append(self, message: CommonMessage | dict) -> None:
        """
        Append a message to the conversation.

        Accepts either CommonMessage or dict with 'role' and 'content'.
        Images can be included in dict with 'images' key.
        """
        if isinstance(message, dict):
            if "role" in message and "content" in message:
                images = ()
                if "images" in message:
                    images = tuple(MessageImage(**img) if isinstance(img, dict) else img for img in message.get("images", []))
                message = CommonMessage(role=message["role"], content=message["content"], images=images)
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

    def as_list(self) -> list[dict[str, str | list[dict[str, str]]]]:
        """
        Return conversation as list of dicts with 'role', 'content', and optionally 'images'.
        """
        return [msg.as_dict() for msg in self.messages]

    def has_images(self) -> bool:
        """
        Check if any message in this conversation has images.

        Returns:
            True if any message has at least one image, False otherwise
        """
        return any(msg.has_images() for msg in self.messages)

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

    `span` is to reconcile multi-token strings.
    If complex emoji or other multi-token string is originally sampled as multiple sub-UTF-8 tokens,
    we want to record beginning of this multi-token string as a single token with span=N,
    and the following N-1 tokens as continuation tokens with span=0.
    For normal one to one tokenization, span=1.
    """

    token_id: int
    token_str: str
    token_bytes: bytes  # Serialize bytes as base64 string in JSON
    logprob: float
    span: int  # Handle split UTF-8 tokens. Normally 1. If multi-token string, first token has span=N, rest 0.

    @staticmethod
    def eos_span() -> int:
        """
        Special span value for EOS token.
        """
        return -10

    @property
    def is_eos(self) -> bool:
        """
        Whether this token is EOS token.
        """
        return self.span == self.eos_span()

    def to_dict(self) -> dict[str, object]:
        """
        Serialize to dict with abbreviated keys: 'i', 'st', 'b', 'l', 'sp'.
        """
        return {
            "i": self.token_id,
            "st": self.token_str,
            "b": base64.b64encode(self.token_bytes).decode("utf-8"),
            "l": self.logprob,
            "sp": self.span,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SinglePositionToken":
        """
        Create SinglePositionToken from dict with 'i', 'st', 'b', 'l', 'sp'.
        """
        return cls(
            token_id=data["i"],
            token_str=data["st"],
            token_bytes=base64.b64decode(data["b"]),
            logprob=data["l"],
            span=data["sp"],
        )


class SinglePositionTopLogprobs(list[SinglePositionToken]):
    """
    List of possible alternative tokens and their logprobs for a single token position, sorted by logprob descending.
    """

    @classmethod
    def from_list_of_dicts(cls, data: list[dict]) -> "SinglePositionTopLogprobs":
        """
        Create SinglePositionTopLogprobs from list of dicts.
        """
        result = cls()
        for entry in data:
            result.append(SinglePositionToken.from_dict(entry))
        return result

    def to_list_of_dicts(self) -> list[dict]:
        """
        Serialize each SinglePositionToken to a dict.
        """
        return [lp.to_dict() for lp in self]


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
        """
        Create CompletionTopLogprobs from list of lists of dicts.
        """
        result = cls()
        for position_list in data:
            top_logprobs = SinglePositionTopLogprobs.from_list_of_dicts(position_list)
            result.append(top_logprobs)
        return result

    def to_list_of_lists(self) -> list[list]:
        """
        Serialize each position's top logprobs to a list of lists of dicts.
        """
        return [position.to_list_of_dicts() for position in self]

    def to_dict_of_lists(self) -> dict[str, list[list]]:
        """
        Serialize to a dictionary of 2D lists for each attribute.

        For efficient compression and storage in database.
        """
        result = {
            "token_id": [],
            "token_str": [],
            "token_bytes": [],
            "logprob_f16": [],
            "span": [],
        }
        for position in self:
            token_ids = []
            token_strs = []
            token_bytes = []
            logprobs = []
            spans = []
            for token in position:
                token_ids.append(token.token_id)
                if is_equal_utf_8(token.token_bytes, token.token_str):
                    token_strs.append(None)  # Save space by not storing redundant string
                else:
                    token_strs.append(token.token_str)
                token_bytes.append(token.token_bytes)  # Expecting bytes-supporting storage
                logprobs.append(struct.pack("e", token.logprob))  # Store as float16 for space efficiency
                spans.append(token.span)
            result["token_id"].append(token_ids)
            result["token_str"].append(token_strs)
            result["token_bytes"].append(token_bytes)
            result["logprob_f16"].append(logprobs)
            result["span"].append(spans)
        return result

    @classmethod
    def from_dict_of_lists(cls, data: dict[str, list[list]]) -> "CompletionTopLogprobs":
        """
        Create CompletionTopLogprobs from a dictionary of 2D lists for each attribute.

        For efficient compression and storage in database.
        """
        result = cls()
        num_positions = len(data["token_id"])
        for pos_idx in range(num_positions):
            position = SinglePositionTopLogprobs()
            token_ids = data["token_id"][pos_idx]
            token_strs = data["token_str"][pos_idx]
            token_bytes_list = data["token_bytes"][pos_idx]
            logprobs = data["logprob_f16"][pos_idx]
            spans = data["span"][pos_idx]
            for i, token_id in enumerate(token_ids):
                # Decode token bytes to string if necessary
                token_str = token_strs[i] if token_strs[i] is not None else token_bytes_list[i].decode("utf-8", errors="replace")
                token = SinglePositionToken(
                    token_id=token_id,
                    token_str=token_str,
                    token_bytes=token_bytes_list[i],
                    logprob=struct.unpack("e", logprobs[i])[0],  # Unpack float16 to float32
                    span=spans[i],
                )
                position.append(token)
            result.append(position)
        return result


class CompletionTokenLogprobs(list[SinglePositionToken]):
    """
    List of all token positions, each with sampled token and its logprob.
    Each element represents the actual token sampled at that position with it's logprob.
    """

    @classmethod
    def from_list_of_dicts(cls, data: list[dict]) -> "CompletionTokenLogprobs":
        """
        Create SinglePositionToken list from dicts.
        """
        result = cls()
        for entry in data:
            result.append(SinglePositionToken.from_dict(entry))
        return result

    @classmethod
    def from_stitched_tokens(cls, all_tokens: list[SinglePositionToken]) -> "CompletionTokenLogprobs":
        """
        Create CompletionTokenLogprobs from list of stitched together different sequences of SinglePositionToken.

        Since we are stitching together multiple parts, we have to reconstruct spans and token_strs correctly.
        """
        result = cls()
        # Amount of tokens stay same, we just reconstruct spans and token_strs
        i = 0
        while i < len(all_tokens):
            token = all_tokens[i]
            if token.is_eos:
                result.append(token)
                break  # We should never have any tokens after EOS, it's last sampled token
            if is_equal_utf_8(token.token_bytes, token.token_str):
                result.append(token)  # No need to reconstruct, already valid
                i += 1
                continue

            joined_bytes = token.token_bytes
            token_str = None
            span = None
            for j in range(1, 4):  # Check up to 4 bytes for multibyte sequence
                if i + j >= len(all_tokens):
                    break  # No more tokens to check
                joined_bytes += all_tokens[i + j].token_bytes
                token_str = try_decode_utf_8(joined_bytes)
                if token_str is not None:
                    span = j + 1
                    break
            if token_str is None or span is None:
                # Failed to reconstruct valid UTF-8 sequence, fallback to original token
                logging.getLogger("CompletionTokenLogprobs").error(
                    "Failed to reconstruct valid UTF-8 sequence starting with token ID %d, using original token_str.",
                    token.token_id,
                )
                result.append(token)
                i += 1
                continue
            # Reconstructed valid UTF-8 sequence
            # Create new SinglePositionToken with reconstructed token_str and span
            reconstructed_token = SinglePositionToken(
                token_id=token.token_id,
                token_str=token_str,
                token_bytes=token.token_bytes,
                logprob=token.logprob,
                span=span,
            )
            result.append(reconstructed_token)

            # Skip continuation tokens
            for k in range(1, span):
                if i + k < len(all_tokens):
                    cont_token = all_tokens[i + k]
                    if cont_token.is_eos:
                        logging.getLogger("CompletionTokenLogprobs").error(
                            "Unexpected EOS token in continuation of multi-byte sequence at token ID %d.",
                            cont_token.token_id,
                        )
                        break
                    # Add continuation token with span=0
                    continuation = SinglePositionToken(
                        token_id=cont_token.token_id,
                        token_str="",
                        token_bytes=cont_token.token_bytes,
                        logprob=cont_token.logprob,
                        span=0,
                    )
                    result.append(continuation)
                i += span
                continue
        return result

    def to_list_of_dicts(self) -> list[dict]:
        """
        Serialize each SinglePositionToken to a dict.
        """
        return [lp.to_dict() for lp in self]

    def to_token_id_list(self) -> list[int]:
        """
        Convert to list of token IDs.
        """
        return [lp.token_id for lp in self]

    def build_full_text(self) -> str:
        """
        Reconstruct full text from token_strs, taking spans into account.
        """
        text_parts = []
        for token in self:
            if token.span > 0:
                text_parts.append(token.token_str)
        return "".join(text_parts)


class CommonCompletionLogprobs:
    """
    Protocol for logprobs associated with a completion and specific model_id.
    """
    logprobs_model_id: str  # Model ID for which these logprobs were generated.
    sampled_logprobs: CompletionTokenLogprobs  # Logprobs of sampled tokens, matching completion text.
    alternative_logprobs: CompletionTopLogprobs  # List of top alternative tokens and their logprobs.
    min_logprob: float | None = None  # min(sampled_logprobs), minimal logprob of any token in response
    avg_logprob: float | None = None  # average(sampled_logprobs), average logprob of all tokens in response

    def __init__(self, logprobs_model_id: str, sampled_logprobs: CompletionTokenLogprobs, alternative_logprobs: CompletionTopLogprobs):
        self.logprobs_model_id = logprobs_model_id
        self.sampled_logprobs = sampled_logprobs
        self.alternative_logprobs = alternative_logprobs
        if sampled_logprobs:
            logprob_values = [lp.logprob for lp in sampled_logprobs if lp.logprob is not None]
            if logprob_values:
                self.min_logprob = min(logprob_values)
                self.avg_logprob = sum(logprob_values) / len(logprob_values)
            else:
                self.min_logprob = None
                self.avg_logprob = None
        else:
            self.min_logprob = None
            self.avg_logprob = None

    @property
    def scored_logprob(self) -> float | None:
        """
        Return a single score for the logprobs, for ranking purposes.

        Formula: min_logprob + avg_logprob * 2
        """
        if self.min_logprob is None or self.avg_logprob is None:
            return None
        return self.min_logprob + self.avg_logprob * 2

    def is_valid(self) -> bool:
        return self.min_logprob is not None


@dataclass(frozen=True, slots=True)
class CompletionPrefill:
    """
    Unified representation of pre-generated completion text.

    Key issue is that we may have native "model-generated" tokenization or not.
    So this class unifies both cases, plain string and tokenized with logprobs.
    """
    prefill_text: str  # Full prefill text.
    prefill_tokenized: CompletionTokenLogprobs | None = None  # Tokenized prefill with logprobs, if available.

    @classmethod
    def from_tokens(cls, *tokens: Iterable[SinglePositionToken]) -> "CompletionPrefill":
        """
        Create CompletionPrefill from a sequence of iterables of SinglePositionToken.
        """
        token_strs = []
        prefill_tokenized = CompletionTokenLogprobs()
        for iterable in tokens:
            for token in iterable:
                if not isinstance(token, SinglePositionToken):
                    raise ValueError("All items must be SinglePositionToken instances.")
                token_strs.append(token.token_str)
                prefill_tokenized.append(token)

        prefill_text = "".join(token_strs)
        return cls(prefill_text=prefill_text, prefill_tokenized=prefill_tokenized)


@runtime_checkable
class CommonCompletionProtocol(Protocol):
    """
    Protocol for AI completion result, for shared use between low-level provider code and DB persistent classes.
    """
    model_id: str  # Model ID used to generate this completion originally.
    prompt_conversation: CommonConversation  # converation leading to this response (excluding prefill and response itself)
    completion_text: str  # Full text of the completion.
    parent_completion_id: int | None  # ID of parent completion if this is a derivative, else None
    prefill: str | None  # Part of completion that wasn't generated, but artificially inserted manually or during beam expansion.
    beam_token: str | None  # Token at which beam tree was forked, if any.
    temperature: float
    top_k: int
    is_truncated: bool  # Whether the completion was truncated due to max tokens limit.
    is_archived: bool  # Whether this completion is archived and hidden by default.
    is_manual: bool  # Whether this completion was manually edited.

    def get_logprobs_for_model_id(self, model_id: str) -> CommonCompletionLogprobs | None:
        """
        Get logprobs for the given model ID, if available.
        Returns `CommonCompletionLogprobs` compatible result or None if logprobs for the target model_id are not available.
        """
        raise NotImplementedError

    def check_full_response_logprobs(self, target_model_id: str | None = None) -> bool:
        """
        Check if available token logprobs fully match the completion text.

        Go through logprobs and match tokens to completion_text.
        True if all tokens match and cover full text, False otherwise.

        Take in account span semantics for multi-token strings.
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

            if lp.span < 1:
                continue  # Continuation token of multi-token string or special EOS token, skip

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
