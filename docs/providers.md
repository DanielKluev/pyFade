# Provider integrations

pyFADE ships with a deterministic mock model so the GUI and automated tests run without external services. Additional backends are optional and can be enabled through the configuration file (`config.yaml`).

## Built-in mock provider

- Module: `py_fade.providers.mock_provider.MockLLMProvider`
- Dependency: included in the repository (no extra packages)
- Use cases: unit tests, UI demos, and offline experimentation
- Features: deterministic completions, top-*k* logprobs, beam search compatible

## Ollama (optional)

- Module: `py_fade.providers.ollama.PrefillAwareOllama`
- Install: `pip install ollama` and ensure the Ollama daemon is running
- Configuration: add entries under `models` in `config.yaml` with `provider: "ollama"` (see examples in the config file)
- Notes: Ollama does not expose token logprobs, so beam search visualisation is limited when this provider is selected.

## Local llama.cpp (optional)

- Module: `py_fade.providers.llama_cpp.PrefillAwareLlamaCppInternal`
- Install: `pip install llama-cpp-python` with the appropriate CPU/GPU build flags
- Configuration: models must supply a `gguf` path. When `USE_OLLAMA_REGISTRY` is specified, pyFADE will attempt to resolve the GGUF file from an Ollama models directory.
- Capabilities: exposes full logprob streams, making it the preferred backend for beam search and token-level tooling.

## Planned integrations

The following backends are on the roadmap but not yet implemented:

- Remote llama.cpp via REST APIs
- vLLM or other server-side generation services
- Hugging Face Transformers (skipped for now to avoid a hard dependency on PyTorch)

Watch the [roadmap](roadmap.md) for progress on these items.