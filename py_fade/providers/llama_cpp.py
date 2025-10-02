"""llama.cpp provider implementation with AMD GPU support and prefill awareness."""
# pylint: disable=wrong-import-position,invalid-name,duplicate-code,import-error

import logging
import os
import time
from typing import Callable, Optional
from numpy.typing import NDArray
import numpy as np

# Patch path for AMD if needed
# For Windows, if HIP_PATH is set and value is not in PATH, add it
# **IMPORTANT**: This must be done before importing llama_cpp. Do not move this block.
if os.name == "nt":
    hip_path = os.environ.get("HIP_PATH", None)
    if hip_path and hip_path not in os.environ.get("PATH", ""):
        HIP_PATHS = f"{hip_path}\\bin;{hip_path}\\lib"
        os.environ["PATH"] = HIP_PATHS + ";" + os.environ.get("PATH", "")

from py_fade.providers.base_provider import (
    LOGPROB_LEVEL_TOP_LOGPROBS,
    BasePrefillAwareProvider,
)
from py_fade.data_formats.base_data_classes import (CommonCompletionLogprobs, CommonCompletionProtocol, CommonConversation,
                                                    CompletionTokenLogprobs, CompletionTopLogprobs, SinglePositionToken,
                                                    SinglePositionTopLogprobs, CompletionPrefill)
from py_fade.providers.llm_response import LLMResponse

try:
    import llama_cpp  # pylint: disable=import-error
    from llama_cpp import Llama  # pylint: disable=import-error

    IS_LLAMA_CPP_AVAILABLE = True
except Exception as e:  # pylint: disable=broad-exception-caught
    print("Exception while importing llama_cpp:", e)
    print("Warning: Failed to import llama_cpp. Ensure llama-cpp-python is installed "
          "if you plan to use Llama.cpp models.")
    llama_cpp = None
    IS_LLAMA_CPP_AVAILABLE = False

# Backward compatibility alias for tests
is_llama_cpp_available = IS_LLAMA_CPP_AVAILABLE

DEFAULT_LLAMA_CPP_TOP_LOGPROBS = 200  # Force sampling up to 200 alternatives, it costs same so no reason not to.


def is_eog_token(model: "Llama", token_id: int) -> bool:
    """
    Check if token ID is end-of-generation (EOG) token for the model.
    """
    if not IS_LLAMA_CPP_AVAILABLE or not llama_cpp:
        raise ImportError("llama_cpp is not available. Ensure llama-cpp-python is installed.")
    return llama_cpp.llama_token_is_eog(model._model.vocab, token_id)  # pylint: disable=protected-access


def decode_logprobs_to_top_logprobs(model: "Llama", logprobs: NDArray, top_k: int) -> SinglePositionTopLogprobs:
    """
    Decode raw logprobs array to top-k logprobs list.
    """

    # Partition logprobs to get top_k indices
    top_indices = logprobs.argpartition(-top_k)[-top_k:]
    vals_part = np.take_along_axis(logprobs, top_indices, axis=0)
    sorted_order = np.argsort(-vals_part)
    # Sort top_k indices by logprob descending
    top_indices = top_indices[sorted_order]
    vals_part = vals_part[sorted_order]
    result = SinglePositionTopLogprobs()
    for token_id, logprob in zip(top_indices, vals_part):
        token_bytes = model.detokenize([token_id])  # bytes
        if is_eog_token(model, token_id):
            token_str = "<eos>"
            token_span = SinglePositionToken.eos_span()
        else:
            token_str = token_bytes.decode("utf-8", errors="ignore")
            token_span = 1
        result.append(
            SinglePositionToken(token_str=token_str, token_id=int(token_id), logprob=float(logprob), span=token_span,
                                token_bytes=token_bytes))
    return result


class ResponseBuilder:
    """
    Helper class to build LLMResponse from generation parameters and token scores.
    """

    def __init__(self, model_id: str, temperature: float, top_k: int, max_tokens: int, prompt: CommonConversation, tokens_prompt: list[int],
                 prefill: CompletionPrefill | None, tokens_prefill: list[int]):
        self.model_id = model_id
        self.temperature = temperature
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.prompt = prompt
        self.tokens_prompt = tokens_prompt
        self.prefill = prefill
        self.tokens_prefill = tokens_prefill
        self.keep_top_logprobs = DEFAULT_LLAMA_CPP_TOP_LOGPROBS
        self.sampled_logprobs: CompletionTokenLogprobs = CompletionTokenLogprobs()
        self.alternative_logprobs: CompletionTopLogprobs = CompletionTopLogprobs()
        self.scores: list[float] = []
        self.stop_reason: str = "unknown"
        self.previous_turn_score_offset: int | None = None
        self._sampled_tokens: list[int] = []

    def _make_sample_func_wrapper(self, model, original_sample):

        def wrapped_sample(_model_self, *args, **kwargs):
            #print(f"Sample called with _model_self={_model_self}, args={args}, kwargs={kwargs}")
            token_id = original_sample(*args, **kwargs)
            self._sampled_tokens.append(token_id)
            return token_id

        return wrapped_sample.__get__(model, model.__class__)

    def patch_sampler(self, model: "Llama"):
        """
        Patch model's sample function to capture sampled tokens.
        """

        class _PatchCtx:  # pylint: disable=too-few-public-methods

            def __enter__(ctx_self):  # pylint: disable=no-self-argument
                ctx_self.original = model.sample  # pylint: disable=attribute-defined-outside-init
                model.sample = self._make_sample_func_wrapper(model, ctx_self.original)
                return self

            def __exit__(ctx_self, exc_type, exc, tb):  # pylint: disable=no-self-argument
                model.sample = ctx_self.original

        return _PatchCtx()

    def process_scores_batch(self, model: "Llama", scores: NDArray, token_str: str, last_choice: dict):  # pylint: disable=unused-argument
        """
        Process a batch of token scores from the model and update internal state.
        """
        sampled_tokens = self._sampled_tokens
        self._sampled_tokens = []  # Clear for next batch
        print(f"Sampled tokens: {sampled_tokens}")
        if self.previous_turn_score_offset is None:
            self.previous_turn_score_offset = len(scores) - len(sampled_tokens)

        new_scores_count = len(scores) - self.previous_turn_score_offset
        if new_scores_count != len(sampled_tokens):
            raise ValueError(
                f"Unexpected mismatch in scores length: {self.previous_turn_score_offset} -> {len(scores)} vs tokens {len(sampled_tokens)}")

        current_span = len(sampled_tokens)
        # Go through new tokens, trying to find out Token ID and logprob for each
        # Additionally, record top alternatives for each position
        for i, token_id in enumerate(sampled_tokens):
            # Calculate logprobs from logits for this position
            position_logprobs = model.logits_to_logprobs(scores[self.previous_turn_score_offset + i])

            if i > 0:
                current_span = 0  # Continuation token of multi-token string
                token_str = ""  # Only first token has string, rest are continuation tokens with span=0
            if is_eog_token(model, token_id):
                token_str = "<eos>"
                current_span = SinglePositionToken.eos_span()
            token_logprob = position_logprobs[token_id]
            token_bytes = model.detokenize([token_id])  # bytes
            token = SinglePositionToken(token_str=token_str, token_id=int(token_id), logprob=float(token_logprob), span=current_span,
                                        token_bytes=token_bytes)
            self.sampled_logprobs.append(token)

            # Process alternatives for this position
            position_alternatives = decode_logprobs_to_top_logprobs(model, position_logprobs, self.keep_top_logprobs)
            self.alternative_logprobs.append(position_alternatives)
            print(f"Token '{token_str}' (ID {token_id}) logprob: {token_logprob:<.4f}, top alternatives: {position_alternatives[:5]}")

        self.previous_turn_score_offset = len(scores)

    def build_response(self, model: "Llama", stop_reason: str) -> LLMResponse:
        """
        Build final LLMResponse object from accumulated data.
        """
        print(f"Stop reason: {stop_reason} with {len(self.sampled_logprobs)} sampled tokens")
        # Concatenate all token strings except EOS
        generated_part_text = "".join([t.token_str for t in self.sampled_logprobs if not t.is_eos])
        completion_text = (self.prefill.prefill_text if self.prefill else "") + generated_part_text
        completion_logprobs = CommonCompletionLogprobs(
            logprobs_model_id=self.model_id,
            sampled_logprobs=self.sampled_logprobs,
            alternative_logprobs=self.alternative_logprobs,
        )
        return LLMResponse(
            model_id=self.model_id,
            prompt_conversation=self.prompt,
            completion_text=completion_text,
            generated_part_text=generated_part_text,
            temperature=self.temperature,
            top_k=self.top_k,
            max_tokens=self.max_tokens,
            context_length=model.n_ctx(),
            prefill=self.prefill.prefill_text if self.prefill else None,
            logprobs=completion_logprobs,
            is_truncated=stop_reason == "length",
        )


class PrefillAwareLlamaCppInternal(BasePrefillAwareProvider):
    """Internal llama.cpp provider with prefill awareness and GPU support."""

    logprob_capability = LOGPROB_LEVEL_TOP_LOGPROBS  # Llama.cpp can provide top logprobs
    id: str = "llama_cpp_internal"
    is_local_vram: bool = True  # Llama.cpp runs locally and uses VRAM
    current_model_id: str | None
    current_model: "Llama|None"
    current_model_gguf_file: str | None
    current_model_logits_all: bool
    current_model_context_length: int

    def __init__(self, default_temperature: float = 0.7, default_top_k: int = 40, default_context_length: int = 1024,
                 default_max_tokens: int = 128):
        if not IS_LLAMA_CPP_AVAILABLE:
            raise ImportError("llama_cpp is not available. Ensure llama-cpp-python is installed.")
        self.log = logging.getLogger("PrefillAwareLlamaCppInternal")
        super().__init__(default_temperature, default_top_k, default_context_length, default_max_tokens)
        self.current_model = None
        self.current_model_id = None
        self.current_model_gguf_file = None
        self.current_model_logits_all = False
        self.current_model_context_length = 0

    def unload_current_model(self):
        """Unload current model if any."""
        if self.current_model:
            self.log.info("Unloading current model: %s", self.current_model_id)
            del self.current_model
            self.current_model = None
            self.current_model_id = None
            self.current_model_gguf_file = None
            self.current_model_logits_all = False
            self.current_model_context_length = 0
            time.sleep(1)  # Give some time for memory to be freed

    def load_model(self, model_id: str, gguf_file: str, n_gpu_layers: int = -1, verbose: bool = False, logits_all: bool = False,
                   n_ctx: int = 1024) -> Optional["Llama"]:
        """
        If current loaded model is same as requested, return it.
        Else unload current model and load the new one.
        """
        if (self.current_model and self.current_model_id == model_id and self.current_model_gguf_file == gguf_file and
                self.current_model_logits_all == logits_all and n_ctx <= self.current_model_context_length):
            return self.current_model  # Model already loaded

        if not IS_LLAMA_CPP_AVAILABLE or not llama_cpp:
            raise ImportError("llama_cpp is not available. Ensure llama-cpp-python is installed.")

        # Unload current model if any
        self.unload_current_model()

        self.log.info(
            "Loading Llama model from %s with n_gpu_layers=%d, n_ctx=%d",
            gguf_file,
            n_gpu_layers,
            n_ctx,
        )
        try:
            model = llama_cpp.Llama(
                model_path=gguf_file,
                n_gpu_layers=n_gpu_layers,
                verbose=verbose,
                logits_all=logits_all,
                n_ctx=n_ctx,
            )
            self.current_model = model
            self.current_model_id = model_id
            self.current_model_gguf_file = gguf_file
            self.current_model_logits_all = logits_all
            self.current_model_context_length = n_ctx
            return model
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log.error("Failed to load Llama model from %s: %s", gguf_file, e)
            return None

    def get_model(self, model_id: str, **kwargs) -> "Llama":
        """
        Get ready to use model or raise exception.

        Helper for all checks and configuration to dedupe model loading code.
        """
        if not IS_LLAMA_CPP_AVAILABLE or not llama_cpp:
            raise ImportError("llama_cpp is not available. Ensure llama-cpp-python is installed.")
        if not model_id:
            raise ValueError("model_id must be provided for Llama.cpp provider.")

        gguf_file = kwargs.get("gguf", None)
        if not gguf_file:
            raise ValueError("gguf parameter must be provided for Llama.cpp models.")
        if not os.path.isfile(gguf_file):
            raise ValueError(f"gguf file does not exist: {gguf_file}")

        context_length = kwargs.get("context_length", self.default_context_length)
        model = self.load_model(
            model_id=model_id,
            gguf_file=gguf_file,
            n_gpu_layers=-1,
            verbose=True,
            logits_all=True,
            n_ctx=context_length,
        )
        if not model:
            raise RuntimeError(f"Failed to load Llama model from {gguf_file}")
        return model

    def generate(self, model_id: str, prompt: CommonConversation, prefill: CompletionPrefill | None = None, **kwargs) -> LLMResponse:
        """
        Generate a completion using the Llama.cpp backend, optionally with assistant message prefill.
        """
        model = self.get_model(model_id, **kwargs)

        temperature = kwargs.get("temperature", self.default_temperature)
        top_k = kwargs.get("top_k", self.default_top_k)
        max_tokens = kwargs.get("max_tokens", self.default_max_tokens)
        top_logprobs = kwargs.get("top_logprobs", DEFAULT_LLAMA_CPP_TOP_LOGPROBS)

        formatted_prompt, tokens_prompt, tokens_prefill = self._tokenize_prompt_and_completion(model, prompt, prefill, kwargs)
        template_func = kwargs.get("template_func")
        if not template_func or not callable(template_func):
            raise ValueError("template_func must be provided and callable for generate in Llama.cpp provider.")

        on_next_token = kwargs.get("on_next_token")
        if on_next_token and not callable(on_next_token):
            raise ValueError("on_next_token must be callable if provided.")

        self.log.info("-" * 40)
        self.log.info(
            "[ > ] Generating with model %s, temperature=%s, top_k=%s, context_length=%s, "
            "max_tokens=%s, top_logprobs=%s, prefill=%s",
            model_id,
            temperature,
            top_k,
            model.n_ctx(),
            max_tokens,
            top_logprobs,
            "<yes>" if prefill else "<no>",
        )

        tokens_all = tokens_prompt + tokens_prefill
        if prefill:
            self.log.info("Formatted prompt:\n%s\n%s\n%s", formatted_prompt, prefill.prefill_text, "-" * 40)
        else:
            self.log.info("Formatted prompt:\n%s\n%s", formatted_prompt, "-" * 40)
        self.log.info("Tokens:\n%s\n%s", tokens_all, "-" * 40)

        last_choice = {}
        response_builder = ResponseBuilder(model_id, temperature, top_k, max_tokens, prompt, tokens_prompt, prefill, tokens_prefill)
        with response_builder.patch_sampler(model):
            for response in model.create_completion(tokens_all, max_tokens=max_tokens, temperature=temperature, top_k=top_k, logprobs=None,
                                                    stream=True):
                last_choice = self._decode_response_last_choice(response)  # type: ignore
                token_str = last_choice.get("text", "")
                response_builder.process_scores_batch(model, model._scores, token_str, last_choice)  # pylint: disable=protected-access
                #print(f"Scores len = {len(model._scores)}, last score = {model._scores[-1]}")  # pylint: disable=protected-access
                #print(response)
            stop_reason = last_choice.get("finish_reason", "unknown")
            result = response_builder.build_response(model, stop_reason)
        return result

    def evaluate_completion(self, model_id: str, prompt: CommonConversation, completion: CompletionPrefill,
                            **kwargs) -> CommonCompletionLogprobs:
        """
        Evaluate a given completion for given prompt by bound model.
        Returns list of LLMPTokenLogProbs for each token in completion.
        """
        model = self.get_model(model_id, **kwargs)
        formatted_prompt, tokens_prompt, tokens_completion = self._tokenize_prompt_and_completion(model, prompt, completion, kwargs)

        self.log.info("-" * 40)
        self.log.info("[ > ] Evaluating completion with model %s, context_length=%s.", model_id, model.n_ctx())

        tokens_all = tokens_prompt + tokens_completion
        self.log.info("Formatted prompt:\n%s\n%s\n%s", formatted_prompt, completion.prefill_text, "-" * 40)
        self.log.info("Tokens:\n%s\n%s", tokens_all, "-" * 40)
        if not tokens_prompt:
            raise ValueError("Prompt tokens cannot be empty for evaluation.")

        all_tokens = tokens_prompt + tokens_completion
        completion_token_offset = len(tokens_prompt)

        model.reset()
        self.log.info("eval() on %d prompt tokens + %d completion tokens = %d total tokens", len(tokens_prompt), len(tokens_completion),
                      len(all_tokens))
        model.eval(all_tokens)
        self.log.info("eval() done, got %d logits. Converting to logprobs", len(model._scores))  # pylint: disable=protected-access
        all_logprobs = model.logits_to_logprobs(model._scores)  # pylint: disable=protected-access

        ## Now the most tricky part: logprobs are predicted for next token, so we need to align them very carefully.
        self.log.info("eval() done, got logprobs. Lengths: all_tokens = %d, all_logprobs = %d, completion_token_offset = %d",
                      len(all_tokens), len(all_logprobs), completion_token_offset)

        sampled_logprobs = CompletionTokenLogprobs()
        alternative_logprobs = CompletionTopLogprobs()
        has_extra_logprobs = True
        for i, token in enumerate(all_tokens):
            if i < completion_token_offset:
                continue  # Skip prompt tokens
            current_logprobs = all_logprobs[i - 1]
            token_bytes = model.detokenize([token])  # bytes
            if is_eog_token(model, token):
                token_str = "<eos>"
                token_span = SinglePositionToken.eos_span()
            else:
                token_str = token_bytes.decode("utf-8", errors="ignore")
                token_span = 1

            logprob = float(current_logprobs[token])
            sampled_logprobs.append(
                SinglePositionToken(token_str=token_str, token_id=int(token), logprob=logprob, span=token_span, token_bytes=token_bytes))

            # Get top alternatives for this position
            top_logprobs_list = decode_logprobs_to_top_logprobs(model, current_logprobs, DEFAULT_LLAMA_CPP_TOP_LOGPROBS)
            print(f"Idx {i}: Token {repr(token_str)} Logprob {logprob:.4f}\n\tTop5: {top_logprobs_list[:5]}")

            alternative_logprobs.append(top_logprobs_list)

        if has_extra_logprobs:
            top_logprobs_list = decode_logprobs_to_top_logprobs(model, all_logprobs[-1], DEFAULT_LLAMA_CPP_TOP_LOGPROBS)
            alternative_logprobs.append(top_logprobs_list)
            print(f"Extra position: Top5: {top_logprobs_list[:5]}")

        return CommonCompletionLogprobs(
            logprobs_model_id=model_id,
            sampled_logprobs=sampled_logprobs,
            alternative_logprobs=alternative_logprobs,
        )

    def _decode_response_last_choice(self, response: dict) -> dict:
        """
        Parse out last choice from response dict.
        """
        choices = response.get("choices", [])
        if not choices:
            raise ValueError("No choices found in response.")
        last_choice = choices[-1]
        return last_choice

    def _tokenize_prompt_and_completion(self, model: "Llama", prompt: CommonConversation, completion: CompletionPrefill | None,
                                        template_func: Callable[[CommonConversation], str] | dict) -> tuple[str, list[int], list[int]]:
        """
        Tokenize prompt and completion using model's tokenizer.

        Future: Ensure fidelity to original tokenization of completion, by using list[int] instead of just str for prefill/completion.
        Returns (prompt_tokens, completion_tokens).
        """
        if isinstance(template_func, dict):
            template_func = template_func.get("template_func")  # type: ignore
        if not template_func or not callable(template_func):
            raise ValueError("template_func must be provided and callable for _tokenize_prompt_and_completion in Llama.cpp provider.")

        formatted_prompt: str = template_func(prompt)
        prompt_tokens = model.tokenize(formatted_prompt.encode("utf-8"), add_bos=False, special=True)
        if model._model.add_bos_token():  # pylint: disable=protected-access
            self.log.info("Model uses BOS token %d, prepending it to prompt tokens.", model.token_bos())
            prompt_tokens = [model.token_bos()] + prompt_tokens
        if not completion:
            return formatted_prompt, prompt_tokens, []
        if not completion.prefill_tokenized and completion.prefill_text:
            completion_tokens = model.tokenize(completion.prefill_text.encode("utf-8"), add_bos=False)
        elif completion.prefill_tokenized:
            completion_tokens = completion.prefill_tokenized.to_token_id_list()
        else:
            raise ValueError("Completion must have either prefill_text or prefill_tokenized.")
        return formatted_prompt, prompt_tokens, completion_tokens

    def check_high_fidelity_continuation_possible(self, model_id: str, completion: CommonCompletionProtocol) -> bool:
        """
        Check if high-fidelity continuation is possible with current model.

        We need logprobs for all tokens, and token IDs for all sampled tokens in completion.
        """
        if not IS_LLAMA_CPP_AVAILABLE or not llama_cpp:
            return False
        logprobs = completion.get_logprobs_for_model_id(model_id)
        if not logprobs:
            return False
        if not logprobs.sampled_logprobs:
            return False
        if any(t.token_id is None for t in logprobs.sampled_logprobs):
            return False
        return True
