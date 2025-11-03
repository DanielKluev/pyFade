![](assets/images/pyFADE-logo-300_800_text.png)

# Faceted Alignment Datasets Editor

**pyFADE** is a tool for creating highly personalized, preference-tailored, multi-faceted datasets for local LLM parameter-efficient fine-tuning (e.g., LoRA, QLoRA, DoRA) using SFT, DPO, KTO, PPO, and other methods — all derived from the same dataset.

Each prompt supports multiple completions and independent per-facet preference rankings, enabling the convenient construction of an ensemble of facet-specific LLMs, each fine-tuned for a distinct context or purpose.

In addition, pyFADE provides tools to extract targeted completions from the model’s own latent manifold — exploring more deeply than conventional sampling methods to reveal knowledge and reasoning embedded within the model but typically suppressed by its default behavior.

Token-level fidelity, along with rigorous log-probability tracking and filtering, reduces the number of samples required for effective fine-tuning while preserving the model’s original capabilities and preventing catastrophic forgetting or degradation of base-model performance.

## What's facet?

Style, boundaries, risks, knowledge and skills - every human expresses all of it differently depending on context.
Notes to self, communicating with your spouse, family, friends, colleagues, boss, clients, authorities, filling tax reports - what is acceptable and good for one *facet*, could be hazardous for other. 

Just like humans, AI must adapt its behavior to context. To serve you best, it must be explicitly trained — not just prompted — for each facet you rely on.
And keeping facets separated and isolated by fine-tuning each facet separately gives us much more confidence that no catastrophic routing mistake happens and your legal papers aren't ending up with creative and novel ideas.

So goal is to have one LLM to engage with ideas exploration, another to help with communications, third to deal with high stakes, sensitive areas, fourth highly specialized on your professional domain and so on.

Tight control and decoupling of facets gives us assisants who are more efficient at each facet, keeping assistants accessible with commodity hardware, and at same time there's clear separation of concerns and risk management, as each facet has explicit purpose and safety profile.

At same time, some personal preferences and biases are cross-domain, implying facets should be inheritable and chainable, getting most out of each sample in the dataset.

# Project roadmap

- [Development roadmap](docs/roadmap.md)

# Changelog

- [Changelog](Changelog.md)

# Key Features
- Many completions per prompt, from different models and sampling parameters, including assistant reply prefilling.
- [Encryption of datasets and exports at rest.](docs/encryption.md)

# Key features (Planned)
 - top_k = 1 generations by different models
 - high temperature generations by different models
 - manual edits, each edit is a new frame, keeping connections and history
 - ranking of various outputs for DPO/PPO
 - per-model "correct" marking for SFT, markings different for different datasets/facets.
 - remember and display how probable each output is for each model, with and without prefix prefill.
 - single prefill -> multiple generations, multiple models and samplings.
 - quick switch between different view modes - DPO with rankings, SFT with correct markings for selected model
 - token picker for manual edits, with masking templates and logprobs. Restart generation on next token, token by token generation for manual unroll.
 - token logprob display on hover, completion heatmap mode for quick identification of divergence points.
 - import of lm_eval JSONL files
 - support Unsloth, DeepSpeed, Axolotl, HF.trl compatible exports for SFT and DPO training.
 - facet hierarchy and chaining. Chaining example: "Unrefuse" => "InfoSec Red Team" => "InfoSec Red Team Web Pentest".
 - dataset curation assistant models: personalized "judge", tagging, augmentations, formatting.
 - “Zen mode” for distraction-free ranking

# Generation of on-policy complections for different models
 - Completion prefix prefilling to bypass roadblocks.
 - Token by token logprob exploration and manipulation for complex cases.
 - Rigorous tracking of each completion origins, conditions and probabilities, automatically marking whether completion is on-policy for specific model.

# Importing lm_eval JSONL logs

Single or paired files.

Can automatically identify new failures of tuned models and create samples for only these.

# Similarity graph and deduplication

Use embeddings and Milvus to quickly and effortlessly build relations graph and spot duplicates/near duplicates.

# Split and merge datasets

Save only certain facets/tags/groups as separate dataset.
Merge several datasets in one.

# Export

Production-ready files for Unsloth/Axolotl/DeepSpeed/TRL.
Mix facets as needed.
Selective sampling across facets/groups for smaller datasets.

# Data encryption

All databases, files, and indexes stay encrypted at rest. 
UI timeout and lock mode, with encryption-based unlock PIN.
Exports are saved as encrypted .zip files by default.

