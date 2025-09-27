"""Ollama LLM provider implementation with local model registry support."""

import json
import logging
import pathlib

from ollama import ChatResponse, chat

from py_fade.providers.base_provider import LOGPROB_LEVEL_NONE, BasePrefillAwareProvider
from py_fade.providers.llm_response import LLMPTokenLogProbs, LLMResponse


class OllamaRegistry:
    """
    Ollama local models registry parser.
    Ollama keeps all model files (GGUF, template, params and so on) as `blobs`, 
    with file names in form of `sha256-<hash>`
    Manifests in `manifests` directory let us map model names to their blobs.
    """

    ollama_models_dir: pathlib.Path

    def __init__(self, ollama_models_dir: str | pathlib.Path):
        self.log = logging.getLogger("OllamaRegistry")
        self.ollama_models_dir = pathlib.Path(ollama_models_dir)
        if not self.ollama_models_dir.exists():
            self.log.error("Ollama models directory does not exist: %s", self.ollama_models_dir)
            raise FileNotFoundError(
                f"Ollama models directory does not exist: {self.ollama_models_dir}"
            )

        # Directory should have `blobs` and `manifests` subdirs
        self.blobs_dir = self.ollama_models_dir / "blobs"
        self.manifests_dir = self.ollama_models_dir / "manifests"
        if not self.blobs_dir.exists() or not self.manifests_dir.exists():
            self.log.error(
                "Ollama models directory structure is invalid: %s", self.ollama_models_dir
            )
            raise FileNotFoundError(
                f"Ollama models directory structure is invalid: {self.ollama_models_dir}"
            )

    def _find_layer(self, manifest: dict, media_type: str) -> dict:
        """
        Recursively find a layer with the given media type in the manifest.
        """
        if not isinstance(manifest, dict):
            return {}
        for layer in manifest.get("layers", []):
            if layer.get("mediaType") == media_type:
                return layer
        return {}

    def load_model_metadata(self, model_id: str) -> dict:
        """
        Load model metadata from manifests.
        """
        full_model_id = model_id
        namespace = "library"
        if "/" in model_id:
            namespace, model_id = model_id.split("/", 1)

        subtype = ""
        family = model_id
        if ":" in model_id:
            family, subtype = model_id.split(":", 1)

        manifest_file = (
            self.manifests_dir
            / "registry.ollama.ai"
            / namespace
            / family
            / f"{subtype or 'latest'}"
        )
        if not manifest_file.exists():
            self.log.error("Model manifest file does not exist: %s", manifest_file)
            raise FileNotFoundError(f"Model manifest file does not exist: {manifest_file}")

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        weights_dict = self._find_layer(manifest, "application/vnd.ollama.image.model")
        if not weights_dict:
            self.log.error("Model manifest does not contain weights information: %s", manifest_file)
            raise ValueError(
                f"Model manifest does not contain weights information: {manifest_file}"
            )
        template_dict = self._find_layer(manifest, "application/vnd.ollama.image.template")
        result = {
            "model_id": full_model_id,
            "family": family,
            "namespace": namespace,
            "subtype": subtype,
            "weights_file": self.blobs_dir / weights_dict.get("digest", "").replace(":", "-"),
            "template_file": (
                (self.blobs_dir / template_dict.get("digest", "").replace(":", "-"))
                if template_dict
                else None
            ),
        }
        return result


class PrefillAwareOllama(BasePrefillAwareProvider):
    """Ollama provider implementation with prefill awareness support."""
    logprob_capability = LOGPROB_LEVEL_NONE  # Ollama does not provide logprobs
    id: str = "ollama"
    is_local_vram: bool = True  # Ollama runs locally and uses VRAM

    def __init__(
        self,
        default_temperature: float = 0.7,
        default_top_k: int = 40,
        default_context_length: int = 1024,
        default_max_tokens: int = 128,
    ):
        self.log = logging.getLogger("PrefillAwareOllama")
        super().__init__(
            default_temperature, default_top_k, default_context_length, default_max_tokens
        )

    def generate(
        self, model_id: str, prompt: str, prefill: str | None = None, **kwargs
    ) -> LLMResponse:
        """
        We generate a completion using the Ollama API, optionally with a prefill.
        If prefill is provided, we insert it as a start of assistant response.
        """
        if not model_id:
            raise ValueError("model_id must be provided for Ollama provider.")

        temperature = kwargs.get("temperature", self.default_temperature)
        top_k = kwargs.get("top_k", self.default_top_k)
        context_length = kwargs.get("context_length", self.default_context_length)
        max_tokens = kwargs.get("max_tokens", self.default_max_tokens)

        messages = [{"role": "user", "content": prompt}]
        history = messages.copy()

        # Add prefill as beginning of assistant message if provided
        if prefill:
            messages.append({"role": "assistant", "content": prefill})

        prompt_preview = prompt[:50] + ('...' if len(prompt) > 50 else '')
        prefill_preview = (prefill[:50] + ('...' if len(prefill) > 50 else '') 
                          if prefill else 'None')
        self.log.info(
            "Sending request to Ollama model '%s' with prompt: '%s' and prefill: '%s'",
            model_id, prompt_preview, prefill_preview
        )

        response = chat(
            model=model_id,
            messages=messages,
            options={
                "temperature": temperature,
                "top_k": top_k,
                "num_ctx": context_length,
                "num_predict": max_tokens,
            },
        )
        if not isinstance(response, ChatResponse):
            self.log.error("Unexpected response type: %s. Expected ChatResponse.", type(response))
            raise TypeError(f"Expected ChatResponse, got {type(response)}")

        response_content = response.message.content
        if not isinstance(response_content, str):
            self.log.error(
                "Unexpected response content type: %s. Expected str.", type(response_content)
            )
            raise TypeError(f"Expected response content to be str, got {type(response_content)}")

        full_response_text = (prefill or "") + response_content if prefill else response_content
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
        )

    def evaluate_completion(self, model_id: str, prompt: str, completion: str, **kwargs) -> list[LLMPTokenLogProbs]:
        """
        Ollama does not provide token-level log probabilities, so we raise an exception.
        """
        self.log.error("Ollama does not support token-level log probabilities.")
        raise NotImplementedError("Ollama does not support token-level log probabilities.")
