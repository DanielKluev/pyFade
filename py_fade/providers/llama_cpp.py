"""llama.cpp provider implementation with AMD GPU support and prefill awareness."""
# pylint: disable=wrong-import-position,invalid-name,duplicate-code,import-error

import logging
import os
import time
from typing import Optional

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
from py_fade.data_formats.base_data_classes import CommonCompletionLogprobs, CommonConversation, CompletionTokenLogprobs, SinglePositionToken
from py_fade.providers.llm_response import LLMResponseLogprobs, LLMResponse

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
        if self.current_model:
            self.log.info("Unloading current model: %s", self.current_model_id)
            del self.current_model
            self.current_model = None
            self.current_model_id = None
            self.current_model_gguf_file = None
            self.current_model_logits_all = False
            self.current_model_context_length = 0
            time.sleep(1)  # Give some time for memory to be freed

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

    def generate(self, model_id: str, prompt: CommonConversation, prefill: str | None = None, **kwargs) -> LLMResponse:
        """
        Generate a completion using the Llama.cpp backend, optionally with assistant message prefill.
        """
        if not IS_LLAMA_CPP_AVAILABLE or not llama_cpp:
            raise ImportError("llama_cpp is not available. Ensure llama-cpp-python is installed.")
        if not model_id:
            raise ValueError("model_id must be provided for Llama.cpp provider.")

        gguf_file = kwargs.get("gguf", None)
        if not gguf_file:
            raise ValueError("gguf parameter must be provided for Llama.cpp models.")

        temperature = kwargs.get("temperature", self.default_temperature)
        top_k = kwargs.get("top_k", self.default_top_k)
        context_length = kwargs.get("context_length", self.default_context_length)
        max_tokens = kwargs.get("max_tokens", self.default_max_tokens)
        top_logprobs = kwargs.get("top_logprobs", 1)  # Default to 1 to get logprobs of sampled token
        template_func = kwargs.get("template_func", None)

        model = self.load_model(
            model_id=model_id,
            gguf_file=gguf_file,
            n_gpu_layers=-1,
            verbose=True,
            logits_all=top_logprobs > 0,
            n_ctx=context_length,
        )
        if not model:
            raise RuntimeError(f"Failed to load Llama model from {gguf_file}")

        self.log.info("-" * 40)
        self.log.info(
            "[ > ] Generating with model %s, temperature=%s, top_k=%s, context_length=%s, "
            "max_tokens=%s, top_logprobs=%s, prefill=%s",
            model_id,
            temperature,
            top_k,
            context_length,
            max_tokens,
            top_logprobs,
            "<yes>" if prefill else "<no>",
        )
        prompt_with_prefill = prompt.copy_with_prefill(prefill)

        if template_func and callable(template_func):
            formatted_prompt: str = template_func(prompt_with_prefill)  # type: ignore
            self.log.info("Formatted prompt with template:\n%s\n%s", formatted_prompt, "-" * 40)

            # Simple completion has logprobs:int|None, chat completion has logprobs:bool, top_logprobs:int|None
            if top_logprobs > 0:
                logprobs_param = top_logprobs
            else:
                logprobs_param = None

            is_chat_completion = False
            response = model(
                formatted_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                logprobs=logprobs_param,
            )
        else:
            is_chat_completion = True
            response = model.create_chat_completion(
                messages=prompt_with_prefill.as_list(),  # type: ignore
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                logprobs=top_logprobs > 0,
                top_logprobs=top_logprobs,
            )

        # print(response)
        is_truncated = False
        last_choice = response.get("choices", [{}])[0]  # type: ignore
        termination_reason = last_choice.get("finish_reason", "unknown")
        if termination_reason == "length":
            is_truncated = True
        if is_chat_completion:
            response_content = str(last_choice.get("message", {}).get("content", ""))
        else:
            response_content = str(last_choice.get("text", ""))
        full_response_text = (prefill or "") + response_content if prefill else response_content

        # Extract logprobs if available. If logprobs disabled, 'logprobs': None is returned.
        #   Else it's a dict with 'content': list of per-token info
        response_logprobs = last_choice.get("logprobs", {})  # type: dict # type: ignore
        if is_chat_completion:
            logprobs = self._convert_chat_completion_logprobs(response_logprobs)
        else:
            logprobs = self._convert_simple_completion_logprobs(response_logprobs)

        return LLMResponse(
            model_id=model_id,
            prompt_conversation=prompt,
            completion_text=full_response_text,
            generated_part_text=response_content,
            temperature=temperature,
            top_k=top_k,
            prefill=prefill,
            context_length=context_length,
            max_tokens=max_tokens,
            logprobs=logprobs,
            is_truncated=is_truncated,
            is_archived=False,
            beam_token=kwargs.get("beam_token", None),
        )

    def evaluate_completion(self, model_id: str, prompt: CommonConversation, completion: str, **kwargs) -> LLMResponseLogprobs:
        """
        Evaluate a given completion for given prompt by bound model.
        Returns list of LLMPTokenLogProbs for each token in completion.
        """
        if not IS_LLAMA_CPP_AVAILABLE or not llama_cpp:
            raise ImportError("llama_cpp is not available. Ensure llama-cpp-python is installed.")
        if not model_id:
            raise ValueError("model_id must be provided for Llama.cpp provider.")

        gguf_file = kwargs.get("gguf", None)
        if not gguf_file:
            raise ValueError("gguf parameter must be provided for Llama.cpp models.")

        temperature = kwargs.get("temperature", self.default_temperature)
        top_k = kwargs.get("top_k", self.default_top_k)
        context_length = kwargs.get("context_length", self.default_context_length)
        max_tokens = 1
        top_logprobs = 1
        template_func = kwargs.get("template_func", None)

        if not template_func or not callable(template_func):
            raise ValueError("template_func must be provided and callable for evaluate_completion in Llama.cpp provider.")

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

        self.log.info("-" * 40)
        self.log.info(
            "[ > ] Evaluating completion with model %s, temperature=%s, top_k=%s, "
            "context_length=%s, max_tokens=%s, top_logprobs=%s",
            model_id,
            temperature,
            top_k,
            context_length,
            max_tokens,
            top_logprobs,
        )

        prompt_with_completion = prompt.copy_with_prefill(completion)
        formatted_prompt: str = template_func(prompt_with_completion)  # type: ignore
        self.log.info("Formatted prompt with template:\n%s\n%s", formatted_prompt, "-" * 40)
        prompt_tokens, completion_tokens = self._tokenize_prompt_and_completion(model, prompt, completion, template_func)
        result = self._evaluate_one_step(model, prompt_tokens, completion_tokens)
        return LLMResponseLogprobs(
            logprobs_model_id=model_id,
            logprobs=result,
        )

        response = model(
            formatted_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_k=top_k,
            logprobs=top_logprobs,
            echo=True,
        )
        all_logprobs = []
        last_choice: dict = response.get("choices", [{}])[-1]  # type: ignore
        logprobs_dict = last_choice.get("logprobs", {"tokens": [], "token_logprobs": [], "top_logprobs": []})
        logprobs_zipped = list(
            zip(
                logprobs_dict.get("tokens", []),
                logprobs_dict.get("token_logprobs", []),
                logprobs_dict.get("top_logprobs", []),
            ))

        for token, logprob, _ in logprobs_zipped:
            if logprob is None:
                logprob = -100.0
            all_logprobs.append(SinglePositionTokenLogprobs(token=token, logprob=float(logprob)))

        completion_logprobs = self.mask_logprobs_by_str(all_logprobs, completion, max_skip=max_tokens)
        if not completion_logprobs:
            raise ValueError("Failed to match completion tokens in logprobs. Completion may be too long or not match exactly.")
        return completion_logprobs

    def _convert_chat_completion_logprobs(self, logprobs_dict: dict) -> LLMResponseLogprobs | None:
        """
        Convert chat completion logprobs dict to list of LLMPTokenLogProbs.
        """
        logprobs = []
        if logprobs_dict:
            logprobs_dict = logprobs_dict.get("content", [])
        if logprobs_dict:
            for token_info in logprobs_dict:
                token = token_info.get("token", "")
                logprob = token_info.get("logprob", 0.0)
                response_top_logprobs = token_info.get("top_logprobs", [])
                top_logprobs_list = []
                if response_top_logprobs:  # List of dicts, token=>token, logprob=>logprob
                    for alternative in response_top_logprobs:
                        if not isinstance(alternative, dict):
                            continue
                        top_logprobs_list.append((alternative.get("token", ""), alternative.get("logprob", 0.0)))
                logprobs.append(SinglePositionTokenLogprobs(token=token, logprob=logprob, top_logprobs=top_logprobs_list))
        return LLMResponseLogprobs(
            logprobs_model_id=self.current_model_id or "",
            logprobs=logprobs,
        )

    def _convert_simple_completion_logprobs(self, logprobs_dict: dict) -> LLMResponseLogprobs | None:
        """
        Convert simple completion logprobs dict to list of LLMPTokenLogProbs.
        Example input: {'tokens': ['Okay'], 'text_offset': [59], 'token_logprobs':
            [np.float32(-0.0774431)], 'top_logprobs': [{'Okay': np.float32(-0.0774431), 'Ping': np.float32(-2.9264612),
            'You': np.float32(-4.4990206)}]}
        """
        logprobs_list = []
        tokens = logprobs_dict.get("tokens", [])
        token_logprobs = logprobs_dict.get("token_logprobs", [])
        top_logprobs = logprobs_dict.get("top_logprobs", [])
        for i, token in enumerate(tokens):
            logprob = float(token_logprobs[i]) if i < len(token_logprobs) else 0.0
            top_logprobs_list = []
            if i < len(top_logprobs):
                top_logprobs_dict = top_logprobs[i]
                if isinstance(top_logprobs_dict, dict):
                    for alt_token, alt_logprob in top_logprobs_dict.items():
                        top_logprobs_list.append((alt_token, float(alt_logprob)))
            logprobs_list.append(SinglePositionTokenLogprobs(token=token, logprob=logprob, top_logprobs=top_logprobs_list))
        return LLMResponseLogprobs(
            logprobs_model_id=self.current_model_id or "",
            logprobs=logprobs_list,
        )

    def mask_logprobs_by_str(self, logprobs: CompletionTokenLogprobs, mask_str: str, max_skip: int) -> LLMResponseLogprobs | None:
        """
        Given a list of LLMPTokenLogProbs and a mask string, return a new list where only tokens that are
            exact match over mask_str are kept.
        At most max_skip tokens can be skipped from the end of the logprobs list.
        If more than max_skip tokens would be skipped or not entire mask_str is matched, return None.
        """
        masked_logprobs = []

        # 1. Match ends, by skipping up to max_skip tokens from end
        skip_count = 0
        while True:
            current_token = logprobs[-(skip_count + 1)]
            if mask_str.endswith(current_token.token):
                break
            skip_count += 1
            if skip_count > max_skip:
                return None
        logprobs = logprobs[:len(logprobs) - skip_count]

        # 2. Now go backwards and match tokens to mask_str
        logprobs_pos = len(logprobs) - 1
        mask_pos = len(mask_str)
        while True:
            token_len = len(logprobs[logprobs_pos].token)
            if not mask_str[mask_pos - token_len:mask_pos] == logprobs[logprobs_pos].token:
                return None
            mask_pos -= token_len
            logprobs_pos -= 1
            if mask_pos == 0:
                break
            if logprobs_pos < 0:
                return None
        masked_logprobs = logprobs[logprobs_pos + 1:]
        # print("-"*40)
        # print("Mask:", repr(mask_str))
        # print("Input logprobs:", logprobs)
        # print("Masked logprobs:", masked_logprobs)
        return LLMResponseLogprobs(
            logprobs_model_id=self.current_model_id or "",
            logprobs=masked_logprobs,
        )

    def _tokenize_prompt_and_completion(self, model: "Llama", prompt: CommonConversation, completion: str,
                                        template_func) -> tuple[list[int], list[int]]:
        """
        Tokenize prompt and completion using model's tokenizer.

        Future: Ensure fidelity to original tokenization of completion, by using list[int] instead of just str for prefill/completion.
        Returns (prompt_tokens, completion_tokens).
        """
        formatted_prompt: str = template_func(prompt)  # type: ignore
        prompt_tokens = model.tokenize(formatted_prompt.encode("utf-8"), add_bos=False)
        completion_tokens = model.tokenize(completion.encode("utf-8"), add_bos=False)
        return prompt_tokens, completion_tokens

    def _evaluate_one_step(self, model: "Llama", prompt_tokens: list[int], completion_tokens: list[int]) -> CommonCompletionLogprobs:
        """
        Evaluate one step of completion after prompt, returning logprobs for each token in completion.
        """
        if not prompt_tokens:
            raise ValueError("Prompt tokens cannot be empty for evaluation.")

        all_tokens = prompt_tokens + completion_tokens
        completion_token_offset = len(prompt_tokens)

        model.reset()
        self.log.info("eval() on %d prompt tokens + %d completion tokens = %d total tokens", len(prompt_tokens), len(completion_tokens),
                      len(all_tokens))
        model.eval(all_tokens)
        self.log.info("eval() done, got %d logits. Converting to logprobs", len(model._scores))
        all_logprobs = model.logits_to_logprobs(model._scores)  # pylint: disable=protected-access

        ## Now the most tricky part: logprobs are predicted for next token, so we need to align them very carefully.
        self.log.info("eval() done, got logprobs. Lengths: all_tokens = %d, all_logprobs = %d, completion_token_offset = %d",
                      len(all_tokens), len(all_logprobs), completion_token_offset)

        result = []
        for i in range(len(all_tokens)):
            if i < completion_token_offset:
                continue  # Skip prompt tokens
            token = all_tokens[i]
            token_str = model.detokenize([token]).decode("utf-8", errors="ignore")  # pylint: disable=protected-access
            logprob = float(all_logprobs[i - 1][token])  # Logprobs are for next token, so offset by -1
            top_logprobs_list = []
            top_indices = all_logprobs[i - 1].argsort()[-5:][::-1]  # Top 5 tokens
            for idx in top_indices:
                alt_token_str = model.detokenize([idx]).decode("utf-8", errors="ignore")  # pylint: disable=protected-access
                alt_logprob = float(all_logprobs[i - 1][idx])
                top_logprobs_list.append((alt_token_str, alt_logprob))
            print(f"Idx {i}: Token '{repr(token_str)}' Logprob {logprob:.4f}\n\tTop5: {top_logprobs_list}")
            result.append(SinglePositionTokenLogprobs(token=token_str, logprob=logprob, top_logprobs=top_logprobs_list))

        return result
