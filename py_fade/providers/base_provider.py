from tiktoken import get_encoding

from py_fade.providers.flat_prefix_template import parse_flat_prefix_string
from py_fade.providers.llm_response import LLMPTokenLogProbs, LLMResponse

cl100k_base_encoding = None
try:
    print("Loading tokenizer: cl100k_base...")
    cl100k_base_encoding = get_encoding("cl100k_base")
    print("Tokenizer loaded successfully.")
except Exception as e:
    print(
        f"Warning: Failed to load cl100k_base encoding: {e}. Token counting will use a heuristic."
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

    def __init__(
        self,
        default_temperature: float = 0.7,
        default_top_k: int = 40,
        default_context_length: int = 1024,
        default_max_tokens: int = 128,
    ):
        self.default_temperature = default_temperature
        self.default_top_k = default_top_k
        self.default_context_length = default_context_length
        self.default_max_tokens = default_max_tokens

    def flat_prefix_template_to_messages(
        self, prompt: str, prefill: str | None = None
    ) -> list[dict]:
        """
        Convert flat prefix template string to Messages API format.
        If prefill is provided, it is inserted as the start of the assistant message.
        """
        messages = parse_flat_prefix_string(prompt)
        if prefill:
            # Insert prefill as beginning of assistant message
            messages.append({"role": "assistant", "content": prefill})
        return messages

    def generate(
        self, model_id: str, prompt: str, prefill: str | None = None, **kwargs
    ) -> LLMResponse:
        raise NotImplementedError("Subclasses must implement the generate method.")

    def evaluate_completion(
        self, model_id: str, prompt: str, completion: str, **kwargs
    ) -> list[LLMPTokenLogProbs]:
        """
        Evaluate a given completion for given prompt by bound model.
        Returns list of LLMPTokenLogProbs for each token in completion.
        """
        raise NotImplementedError("Subclasses must implement the evaluate_completion method.")

    def count_tokens(self, text: str, model_id: str | None = None) -> int:
        """
        Count the number of tokens in the given text using tiktoken.
        """
        avg_chars_per_token = 4  # Rough average for English text
        encoding_name = "cl100k_base"  # Default to cl100k_base for now
        # Default to cl100k_base encoding
        if encoding_name == "cl100k_base" and cl100k_base_encoding:
            tokens = cl100k_base_encoding.encode(text)
            return len(tokens)
        else:
            return len(text) // avg_chars_per_token
