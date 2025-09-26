# Development roadmap

_Last updated: 2025-09-25_

This roadmap collects open TODO items from the source tree and highlights larger features that remain from the original vision. Items are grouped by feature area and ordered by priority.

## High priority

- **Interactive generation** – Implement the step-by-step completion flow in `py_fade.gui.widget_new_completion.NewCompletionFrame.generate_token_by_token` so users can accept or edit tokens as they stream in.
- **Dataset overview metrics** – Replace the placeholder "TBD" values in `WidgetDatasetTop` with real counts for samples, prompts, completions, and facets.

## Medium priority

- **Ranking and preference tooling** – Add UI to rank completions for DPO/PPO training and capture per-model "correct" flags for SFT scenarios.
- **Prompt/completion imports** – Support importing LM Eval JSONL exports to bootstrap new samples from evaluation failures.
- **Dataset curation improvements** – Introduce streamlined workflows for tagging, filtering, and batch-editing samples inside the GUI.

## Low priority / exploratory

- **Facet hierarchy & chaining** – Allow facets to inherit behaviour from parent facets (e.g., "Unrefuse" → "InfoSec Red Team").
- **Similarity graph & deduplication** – Use embeddings plus a vector store (Milvus or similar) to spot near-duplicate samples and visualise relationships.
- **Dataset split/merge tooling** – Provide guided flows to split datasets by facet/tag or merge multiple datasets together.
- **Export pipeline extensions** – Generate ready-to-train exports for frameworks such as Unsloth, Axolotl, DeepSpeed, and HF TRL directly from saved templates.
- **Curation assistant models** – Integrate judge/feedback models for automatic tagging, augmentation, or safety checks.
- **Encryption and locking** – Launcher now detects SQLCipher databases, gates access behind password checks, and surfaces missing SQLCipher support. Remaining work covers in-app lock screens and encrypted export archives.
- **Remote inference adapters** – Add remote llama.cpp/vLLM backends and Hugging Face Transformers support once a sustainable dependency story is in place.

Have an idea that is not listed? Open an issue or start a discussion so we can capture it here.