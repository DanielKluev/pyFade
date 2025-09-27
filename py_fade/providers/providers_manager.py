"""LLM inference providers management and model mapping utilities."""

import logging
import pathlib

from py_fade.providers.base_provider import BasePrefillAwareProvider
from py_fade.providers.llama_cpp import (
    PrefillAwareLlamaCppInternal,
    IS_LLAMA_CPP_AVAILABLE,
    is_llama_cpp_available,
)
from py_fade.providers.llm_response import LLMPTokenLogProbs, LLMResponse
from py_fade.providers.llm_templates import get_template_function
from py_fade.providers.mock_provider import MockLLMProvider
from py_fade.providers.ollama import OllamaRegistry, PrefillAwareOllama

providers_map = {
    "mock": MockLLMProvider,
    "llama_cpp_internal": PrefillAwareLlamaCppInternal if is_llama_cpp_available else None,
    "ollama": PrefillAwareOllama,
}


class MappedModel:
    """Represents a model mapped to a specific provider with associated parameters."""

    model_id: str
    provider: BasePrefillAwareProvider
    provider_params: dict

    def __init__(
        self, model_id: str, provider: BasePrefillAwareProvider, provider_params: dict | None = None
    ):
        self.model_id = model_id
        self.provider = provider
        self.provider_params = provider_params or {}

    @property
    def path(self) -> str:
        """Get the full path identifier for this mapped model."""
        return f"{self.model_id} ({self.provider.id})"

    def generate(self, prompt: str, prefill: str | None = None, **kwargs) -> LLMResponse:
        """Generate text using the mapped model and provider."""
        # Merge provider_params into kwargs, with kwargs taking precedence
        merged_kwargs = {**self.provider_params, **kwargs}
        return self.provider.generate(self.model_id, prompt, prefill, **merged_kwargs)

    def evaluate_completion(
        self, prompt: str, completion: str, **kwargs
    ) -> list[LLMPTokenLogProbs]:
        """
        Evaluate a given completion for given prompt by bound model.
        Returns list of LLMPTokenLogProbs for each token in completion.
        """
        merged_kwargs = {**self.provider_params, **kwargs}
        return self.provider.evaluate_completion(self.model_id, prompt, completion, **merged_kwargs)


class InferenceProvidersManager:
    """
    Manages multiple LLM providers and routes requests to the appropriate one.
    """

    ollama_registry: OllamaRegistry | None
    models: dict[str, dict]
    providers: dict[str, BasePrefillAwareProvider]
    model_provider_map: dict[str, MappedModel]
    current_local_model: (
        MappedModel | None
    )  # Track currently used local model from local providers (llama_cpp, ollama)

    def __init__(
        self,
        models_configs: list[dict],
        ollama_models_dir: str | pathlib.Path | None = None,
        default_temperature: float = 0.7,
        default_top_k: int = 40,
    ):
        self.log = logging.getLogger("InferenceProvidersManager")
        self.default_temperature = default_temperature
        self.default_top_k = default_top_k
        self.providers = {}
        self.models = {}
        self.model_provider_map = {}
        self.default_provider_key = None
        if ollama_models_dir:
            self.ollama_registry = OllamaRegistry(ollama_models_dir)
        else:
            self.ollama_registry = None
        self.current_local_model = None
        self.reload_models(models_configs)
        self._default_provider = self.providers["mock"]

    def reload_models(self, models_configs: list[dict]):
        # Add mock provider and mock model.
        self.add_model("mock-echo-model", "mock")

        # Iterate through models_config
        for model_params in models_configs:
            model_id: str = model_params.get("id")  # type: ignore
            template_func = get_template_function(model_id)
            ollama_id = None
            gguf_path = None
            if "ollama_id" in model_params:
                ollama_id = model_params["ollama_id"]
                if ollama_id == "MAIN_ID":
                    ollama_id = model_id
                # Add ollama provider for this model
                self.add_model(
                    model_id, "ollama", {"ollama_id": ollama_id, "template_func": template_func}
                )

            if "gguf" in model_params:
                gguf_path = model_params["gguf"]
                if gguf_path == "USE_OLLAMA_REGISTRY":
                    if not self.ollama_registry:
                        self.log.error(
                            f"Model {model_id} requires Ollama registry, but no registry path provided."
                        )
                        continue
                    if not ollama_id:
                        self.log.error(
                            f"Model {model_id} requires Ollama registry, but no ollama_id provided."
                        )
                        continue
                    model_metadata = self.ollama_registry.load_model_metadata(ollama_id)
                    gguf_path = model_metadata.get("weights_file")
                    if not gguf_path or not gguf_path.exists():
                        self.log.error(f"Model {model_id} weights file does not exist: {gguf_path}")
                        continue
                # Add GGUF path for this model
                # If llama_cpp is supported, add llama_cpp provider for this model
                if is_llama_cpp_available:
                    self.add_model(
                        model_id,
                        "llama_cpp_internal",
                        {"gguf": str(gguf_path), "template_func": template_func},
                    )
                else:
                    self.log.error(
                        f"Model {model_id} requires llama_cpp provider, but llama-cpp-python is not installed."
                    )

    def add_model(self, model_id: str, provider_key: str, provider_params: dict | None = None):
        if provider_key not in providers_map:
            self.log.error(f"Provider key {provider_key} not recognized for model {model_id}.")
            return
        if providers_map[provider_key] is None:
            self.log.error(
                f"Provider {provider_key} is not supported. Install required dependencies or configure correctly."
            )
            return
        if provider_key not in self.providers:
            provider_instance = providers_map[provider_key](
                default_temperature=self.default_temperature, default_top_k=self.default_top_k
            )
            self.providers[provider_key] = provider_instance
        else:
            provider_instance = self.providers[provider_key]

        if model_id not in self.models:
            self.models[model_id] = {}

        mapped_model = MappedModel(model_id, provider_instance, provider_params)
        self.models[model_id][provider_key] = mapped_model
        self.model_provider_map[mapped_model.path] = mapped_model
        self.log.info(f"Added model {model_id} with provider {provider_key}.")

    def count_tokens(self, text: str, model_id: str | None = None) -> int:
        return self._default_provider.count_tokens(text, model_id)

    def get_mapped_model(self, model_path: str) -> MappedModel | None:
        return self.model_provider_map.get(model_path, None)
