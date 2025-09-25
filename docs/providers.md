# Supported LLM inference backends/providers

## Embedded Llama.cpp via llama-cpp-python

Preferred inference engine for local, resource-limited generation.
Supports full range of features (logprobs, beaming, etc).

### Requirements
- `llama-cpp-python` package installed. Make sure to install it with appropriate GPU flags.

### Configuration
- Will be added if model configuration has `gguf` field pointing to a valid GGUF model file.
- `gguf` field may have value `USE_OLLAMA_REGISTRY` to use Ollama model registry for GGUF models.

## Remote Llama.cpp

Run inference on remote server via REST API.
Requires server IP and port as config.

## Ollama

Very easy to set up and run.

Major downsides:
- Ollama doesn't provide logprobs, so beaming, metrics and a lot of other functionality is not available.
- Some models require template changes to make assistant reply prefill work correctly.

## vLLM

TBD.

## HuggingFace transformers

For now, intentionally not supported to avoid pytorch dependency.