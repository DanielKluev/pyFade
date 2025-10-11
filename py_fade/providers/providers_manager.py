"""LLM inference providers management and model mapping utilities."""

import logging
import pathlib

from py_fade.data_formats.base_data_classes import CommonConversation, CommonCompletionLogprobs, CompletionPrefill
from py_fade.providers.base_provider import BasePrefillAwareProvider
from py_fade.providers.llama_cpp import PrefillAwareLlamaCppInternal, IS_LLAMA_CPP_AVAILABLE
from py_fade.providers.llm_response import LLMResponse
from py_fade.providers.llm_templates import get_template_function
from py_fade.providers.mock_provider import MockLLMProvider
from py_fade.providers.ollama import OllamaRegistry, PrefillAwareOllama

providers_map = {
    "mock": MockLLMProvider,
    "llama_cpp_internal": PrefillAwareLlamaCppInternal if IS_LLAMA_CPP_AVAILABLE else None,
    "ollama": PrefillAwareOllama,
}


class MappedModel:
    """Represents a model mapped to a specific provider with associated parameters."""

    model_id: str
    provider: BasePrefillAwareProvider
    provider_params: dict

    def __init__(self, model_id: str, provider: BasePrefillAwareProvider, provider_params: dict | None = None):
        self.model_id = model_id
        self.provider = provider
        self.provider_params = provider_params or {}

    @property
    def path(self) -> str:
        """Get the full path identifier for this mapped model."""
        return f"{self.model_id} ({self.provider.id})"

    def generate(self, prompt: CommonConversation, prefill: CompletionPrefill | None = None, **kwargs) -> LLMResponse:
        """Generate text using the mapped model and provider."""
        # Merge provider_params into kwargs, with kwargs taking precedence
        merged_kwargs = {**self.provider_params, **kwargs}
        return self.provider.generate(self.model_id, prompt, prefill, **merged_kwargs)

    def evaluate_completion(self, prompt: CommonConversation, completion: CompletionPrefill, **kwargs) -> CommonCompletionLogprobs:
        """
        Evaluate a given completion for given prompt by bound model.

        Returns token logprobs and metadata as defined in CommonCompletionLogprobs.
        """
        merged_kwargs = {**self.provider_params, **kwargs}
        return self.provider.evaluate_completion(self.model_id, prompt, completion, **merged_kwargs)

    def __repr__(self) -> str:
        return f"MappedModel(model_id={self.model_id}, provider={self.provider})"


class InferenceProvidersManager:
    """
    Manages multiple LLM providers and routes requests to the appropriate one.
    """

    ollama_registry: OllamaRegistry | None
    models: dict[str, dict]
    providers: dict[str, BasePrefillAwareProvider]
    model_provider_map: dict[str, MappedModel]
    current_local_model: (MappedModel | None)  # Track currently used local model from local providers (llama_cpp, ollama)
    mock_model: MappedModel | None = None

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
        """
        Reload models mapped to providers from configuration.
        """
        # Add mock provider and mock model.
        self.mock_model = self.add_model("mock-echo-model", "mock")

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
                self.add_model(model_id, "ollama", {"ollama_id": ollama_id, "template_func": template_func})

            if "gguf" in model_params:
                gguf_path = model_params["gguf"]
                if gguf_path == "USE_OLLAMA_REGISTRY":
                    if not self.ollama_registry:
                        self.log.error(
                            "Model %s requires Ollama registry, but no registry path provided.",
                            model_id,
                        )
                        continue
                    if not ollama_id:
                        self.log.error(
                            "Model %s requires Ollama registry, but no ollama_id provided.",
                            model_id,
                        )
                        continue
                    model_metadata = self.ollama_registry.load_model_metadata(ollama_id)
                    gguf_path = model_metadata.get("weights_file")
                    if not gguf_path or not gguf_path.exists():
                        self.log.error("Model %s weights file does not exist: %s", model_id, gguf_path)
                        continue
                # Add GGUF path for this model
                # If llama_cpp is supported, add llama_cpp provider for this model
                if IS_LLAMA_CPP_AVAILABLE:
                    self.add_model(model_id, "llama_cpp_internal", {"gguf": str(gguf_path), "template_func": template_func})
                else:
                    self.log.error(
                        "Model %s requires llama_cpp provider, but llama-cpp-python is not installed.",
                        model_id,
                    )

    def add_model(self, model_id: str, provider_key: str, provider_params: dict | None = None) -> MappedModel | None:
        """
        Add a model with specified provider and parameters.
        Builds MappedModel and stores in models and model_provider_map.
        """
        if provider_key not in providers_map:
            self.log.error("Provider key %s not recognized for model %s.", provider_key, model_id)
            return
        if providers_map[provider_key] is None:
            self.log.error(
                "Provider %s is not supported. Install required dependencies or configure correctly.",
                provider_key,
            )
            return
        if provider_key not in self.providers:
            provider_instance = providers_map[provider_key](default_temperature=self.default_temperature, default_top_k=self.default_top_k)
            self.providers[provider_key] = provider_instance
        else:
            provider_instance = self.providers[provider_key]

        if model_id not in self.models:
            self.models[model_id] = {}

        mapped_model = MappedModel(model_id, provider_instance, provider_params)
        self.models[model_id][provider_key] = mapped_model
        self.model_provider_map[mapped_model.path] = mapped_model
        self.log.info("Added model %s with provider %s.", model_id, provider_key)
        return mapped_model

    def count_tokens(self, text: str, model_id: str | None = None) -> int:
        """
        Wrapper to call appropriate provider's count_tokens method.
        Returns token count as integer.
        """
        return self._default_provider.count_tokens(text, model_id)

    def get_mapped_model(self, model_path: str) -> MappedModel | None:
        """Get MappedModel by its full path identifier."""
        return self.model_provider_map.get(model_path, None)

    def get_mock_model(self) -> MappedModel:
        """Get the mock model instance."""
        assert self.mock_model is not None, "Mock model is not initialized."
        return self.mock_model
