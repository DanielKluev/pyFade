# Faceted Alignment Datasets Editor

pyFADE is tool designed to assist in creation of highly personalized, biased, multi-faceted datasets for local LLM fine-tuning.
Conveniently manage facet-dependent completions preference rankings for each sample.
From unified UI and database, maintain and export faceted datasets for SFT or DPO tuning of ensemble of facet-specific LLMs.

# What's facet?

Style, boundaries, risks, knowledge and skills - every human expresses all of it differently depending on context.
Notes to self, communicating with your spouse, family, friends, colleagues, boss, clients, authorities, filling tax reports - what is acceptable and good for one *facet*, could be hazardous for other. 

Just like humans, AI must adapt its behavior to context. To serve you best, it must be explicitly trained — not just prompted — for each facet you rely on.
And keeping facets separated and isolated by fine-tuning each facet separately gives us much more confidence that no catastrophic routing mistake happens and your legal papers aren't ending up with creative and novel ideas.

So goal is to have one LLM to engage with ideas exploration, another to help with communications, third to deal with high stakes, sensitive areas, fourth highly specialized on your professional domain and so on.

Tight control and decoupling of facets gives us assisants who are more efficient at each facet, keeping assistants accessible with commodity hardware, and at same time there's clear separation of concerns and risk management, as each facet has explicit purpose and safety profile.

At same time, some personal preferences and biases are cross-domain, implying facets should be inheritable and chainable, getting most out of each sample in the dataset.

# Key features
 - top_k = 1 generations by different models
 - high temperature generations by different models
 - prefilling generations by different models. Prefilled prefix must be stored separately and displayed in highlighted fashion.
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

# Export

Production-ready files for Unsloth/Axolotl/DeepSpeed/TRL.
Mix facets as needed.
Selective sampling across facets/groups for smaller datasets.

# Data encryption

All databases, files, and indexes stay encrypted at rest. 
UI timeout and lock mode, with encryption-based unlock PIN.
Exports are saved as encrypted .zip files by default.

