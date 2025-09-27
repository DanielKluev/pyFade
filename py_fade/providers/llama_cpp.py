"""llama.cpp provider implementation with AMD GPU support and prefill awareness."""

import logging
import os
import time
from typing import Optional

# Patch path for AMD if needed
# For Windows, if HIP_PATH is set and value is not in PATH, add it
if os.name == "nt":
    hip_path = os.environ.get("HIP_PATH", None)
    if hip_path and hip_path not in os.environ.get("PATH", ""):
        HIP_PATHS = f"{hip_path}\\bin;{hip_path}\\lib"
        os.environ["PATH"] = HIP_PATHS + ";" + os.environ.get("PATH", "")

from py_fade.providers.base_provider import (
    LOGPROB_LEVEL_TOP_LOGPROBS,
    BasePrefillAwareProvider,
)
from py_fade.providers.llm_response import LLMPTokenLogProbs, LLMResponse

try:
    import llama_cpp
    from llama_cpp import Llama

    IS_LLAMA_CPP_AVAILABLE = True
except Exception as e:
    print("Exception while importing llama_cpp:", e)
    print(
        "Warning: Failed to import llama_cpp. Ensure llama-cpp-python is installed "
        "if you plan to use Llama.cpp models."
    )
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

    def __init__(
        self,
        default_temperature: float = 0.7,
        default_top_k: int = 40,
        default_context_length: int = 1024,
        default_max_tokens: int = 128,
    ):
        if not IS_LLAMA_CPP_AVAILABLE:
            raise ImportError("llama_cpp is not available. Ensure llama-cpp-python is installed.")
        self.log = logging.getLogger("PrefillAwareLlamaCppInternal")
        super().__init__(
            default_temperature, default_top_k, default_context_length, default_max_tokens
        )
        self.current_model = None
        self.current_model_id = None
        self.current_model_gguf_file = None
        self.current_model_logits_all = False

    def load_model(
        self,
        model_id: str,
        gguf_file: str,
        n_gpu_layers: int = -1,
        verbose: bool = False,
        logits_all: bool = False,
        n_ctx: int = 1024,
    ) -> Optional["Llama"]:
        """
        If current loaded model is same as requested, return it.
        Else unload current model and load the new one.
        """
        if (
            self.current_model
            and self.current_model_id == model_id
            and self.current_model_gguf_file == gguf_file
            and self.current_model_logits_all == logits_all
        ):
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
            return model
        except Exception as e:
            self.log.error("Failed to load Llama model from %s: %s", gguf_file, e)
            return None

    def generate(
        self, model_id: str, prompt: str, prefill: str | None = None, **kwargs
    ) -> LLMResponse:
        """
        Generate a completion using the Llama.cpp backend, optionally with a prefill.
        If prefill is provided, we insert it as a start of assistant response.
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
        top_logprobs = kwargs.get(
            "top_logprobs", 1
        )  # Default to 1 to get logprobs of sampled token
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
        messages = [{"role": "user", "content": prompt}]
        history = messages.copy()
        # Add prefill as beginning of assistant message if provided
        if prefill:
            messages.append({"role": "assistant", "content": prefill})

        if template_func and callable(template_func):
            formatted_prompt: str = template_func(messages)  # type: ignore
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
                messages=messages,  # type: ignore
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                logprobs=top_logprobs > 0,
                top_logprobs=top_logprobs,
            )

        # print(response)
        is_truncated = False
        logprobs = []
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
            logprobs = (
                self._convert_chat_completion_logprobs(response_logprobs)
                if response_logprobs
                else []
            )
        else:
            logprobs = (
                self._convert_simple_completion_logprobs(response_logprobs)
                if response_logprobs
                else []
            )

        return LLMResponse(
            model_id=model_id,
            full_history=history,
            full_response_text=full_response_text,
            response_text=response_content,
            temperature=temperature,
            top_k=top_k,
            prefill=prefill,
            context_length=context_length,
            max_tokens=max_tokens,
            logprobs=logprobs,
            is_truncated=is_truncated,
            beam_token=kwargs.get("beam_token", None),
        )

    def evaluate_completion(
        self, model_id: str, prompt: str, completion: str, **kwargs
    ) -> list[LLMPTokenLogProbs]:
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
            raise ValueError(
                "template_func must be provided and callable for evaluate_completion in Llama.cpp provider."
            )

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
            "[ > ] Evaluating completion with model %s, temperature=%s, top_k=%s, "
            "context_length=%s, max_tokens=%s, top_logprobs=%s",
            model_id,
            temperature,
            top_k,
            context_length,
            max_tokens,
            top_logprobs,
        )

        messages = [{"role": "user", "content": prompt}]
        messages.append({"role": "assistant", "content": completion})
        formatted_prompt: str = template_func(messages)  # type: ignore
        self.log.info("Formatted prompt with template:\n%s\n%s", formatted_prompt, "-" * 40)
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
        logprobs_dict = last_choice.get(
            "logprobs", {"tokens": [], "token_logprobs": [], "top_logprobs": []}
        )
        logprobs_zipped = list(
            zip(
                logprobs_dict.get("tokens", []),
                logprobs_dict.get("token_logprobs", []),
                logprobs_dict.get("top_logprobs", []),
            )
        )

        for token, logprob, _ in logprobs_zipped:
            if logprob is None:
                logprob = -100.0
            all_logprobs.append(LLMPTokenLogProbs(token=token, logprob=float(logprob)))

        completion_logprobs = self.mask_logprobs_by_str(
            all_logprobs, completion, max_skip=max_tokens
        )
        if not completion_logprobs:
            raise ValueError(
                "Failed to match completion tokens in logprobs. Completion may be too long or not match exactly."
            )
        return completion_logprobs

    def _convert_chat_completion_logprobs(self, logprobs_dict: dict) -> list[LLMPTokenLogProbs]:
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
                        top_logprobs_list.append(
                            (alternative.get("token", ""), alternative.get("logprob", 0.0))
                        )
                logprobs.append(
                    LLMPTokenLogProbs(token=token, logprob=logprob, top_logprobs=top_logprobs_list)
                )
        return logprobs

    def _convert_simple_completion_logprobs(self, logprobs_dict: dict) -> list[LLMPTokenLogProbs]:
        """
        Convert simple completion logprobs dict to list of LLMPTokenLogProbs.
        Example input: {'tokens': ['Okay'], 'text_offset': [59], 'token_logprobs': [np.float32(-0.0774431)], 'top_logprobs': [{'Okay': np.float32(-0.0774431), 'Ping': np.float32(-2.9264612), 'You': np.float32(-4.4990206)}]}
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
            logprobs_list.append(
                LLMPTokenLogProbs(token=token, logprob=logprob, top_logprobs=top_logprobs_list)
            )
        return logprobs_list

    def mask_logprobs_by_str(
        self, logprobs: list[LLMPTokenLogProbs], mask_str: str, max_skip: int
    ) -> list[LLMPTokenLogProbs] | None:
        """
        Given a list of LLMPTokenLogProbs and a mask string, return a new list where only tokens that are exact match over mask_str are kept.
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
        logprobs = logprobs[: len(logprobs) - skip_count]

        # 2. Now go backwards and match tokens to mask_str
        logprobs_pos = len(logprobs) - 1
        mask_pos = len(mask_str)
        while True:
            token_len = len(logprobs[logprobs_pos].token)
            if not mask_str[mask_pos - token_len : mask_pos] == logprobs[logprobs_pos].token:
                return None
            mask_pos -= token_len
            logprobs_pos -= 1
            if mask_pos == 0:
                break
            if logprobs_pos < 0:
                return None
        masked_logprobs = logprobs[logprobs_pos + 1 :]
        # print("-"*40)
        # print("Mask:", repr(mask_str))
        # print("Input logprobs:", logprobs)
        # print("Masked logprobs:", masked_logprobs)
        return masked_logprobs
