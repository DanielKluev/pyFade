"""Base provider classes and utilities for LLM inference providers."""

import logging

from tiktoken import get_encoding

from py_fade.data_formats.base_data_classes import CommonConversation, CommonCompletionLogprobs, CommonCompletionProtocol, CompletionPrefill
from py_fade.providers.flat_prefix_template import parse_flat_prefix_string
from py_fade.providers.llm_response import LLMResponse

LOGGER = logging.getLogger("BasePrefillAwareProvider")

CL100K_BASE_ENCODING = None
try:
    LOGGER.debug("Loading tokenizer: cl100k_base...")
    CL100K_BASE_ENCODING = get_encoding("cl100k_base")
    LOGGER.debug("Tokenizer loaded successfully.")
except (ImportError, ValueError, RuntimeError) as exc:
    LOGGER.warning(
        "Failed to load cl100k_base encoding: %s. Token counting will use a heuristic.",
        exc,
    )

LOGPROB_LEVEL_NONE = 0  # No logprobs
LOGPROB_LEVEL_SAMPLED_TOKEN = 1  # Logprob of sampled token only
LOGPROB_LEVEL_TOP_LOGPROBS = 2  # For each position, give logprobs of top N tokens


class BasePrefillAwareProvider:
    """
    Base class for providers that support prefill functionality.
    """

    logprob_capability = LOGPROB_LEVEL_NONE
    id: str = "base"
    is_local_vram: bool = False  # Whether the model runs locally and uses VRAM

    def __init__(self, default_temperature: float = 0.7, default_top_k: int = 40, default_context_length: int = 1024,
                 default_max_tokens: int = 128):
        self.default_temperature = default_temperature
        self.default_top_k = default_top_k
        self.default_context_length = default_context_length
        self.default_max_tokens = default_max_tokens

    def flat_prefix_template_to_messages(self, prompt: str, prefill: str | None = None) -> CommonConversation:
        """
        Convert flat prefix template string to CommonConversation format.

        If prefill is provided, it is inserted as the start of the assistant message.
        """
        messages = parse_flat_prefix_string(prompt)
        if prefill:
            # Insert prefill as beginning of assistant message
            messages.append({"role": "assistant", "content": prefill})
        return messages

    def generate(self, model_id: str, prompt: CommonConversation, prefill: CompletionPrefill | None = None, **kwargs) -> LLMResponse:
        """
        Generate completion for the given prompt using the specified model.
        
        Returns an LLMResponse object containing the generated text and metadata.
        """
        raise NotImplementedError("Subclasses must implement the generate method.")

    def evaluate_completion(self, model_id: str, prompt: CommonConversation, completion: CompletionPrefill,
                            **kwargs) -> CommonCompletionLogprobs:
        """
        Evaluate a given completion for given prompt by bound model.

        Returns token logprobs and metadata as defined in CommonCompletionLogprobs.
        """
        raise NotImplementedError("Subclasses must implement the evaluate_completion method.")

    def count_tokens(self, text: str, model_id: str | None = None) -> int:  # pylint: disable=unused-argument
        """
        Count the number of tokens in the given text using tiktoken.
        """
        avg_chars_per_token = 4  # Rough average for English text
        encoding_name = "cl100k_base"  # Default to cl100k_base for now
        # Default to cl100k_base encoding
        if encoding_name == "cl100k_base" and CL100K_BASE_ENCODING:
            tokens = CL100K_BASE_ENCODING.encode(text)
            return len(tokens)
        return len(text) // avg_chars_per_token

    def check_high_fidelity_continuation_possible(self, model_id: str, completion: CommonCompletionProtocol) -> bool:  # pylint: disable=unused-argument
        """
        Check if high-fidelity continuation is possible for this completion, based on provider capabilities and completion data.

        Problem:
        Originally model may produce sequence of tokens, but greedy re-tokenization may merge them. It completely changes logprobs.
        So we need to work with tokens only, not decoded text.

        Requirements:
        - Provider must support running inference from tokens directly, not just text.
        - Completion must include original tokenization data with logprobs, ideally token IDs rather than token text.

        Returns True if high-fidelity continuation is possible, False otherwise.
        """
        # Providers should override if they support high-fidelity continuation
        return False
