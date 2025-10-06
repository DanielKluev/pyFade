# Creating New Completions For Sample

## Intro

Every sample is bound to fixed prompt. Then, each sample may have multiple alternative completions.
These completions may range in style, length, reasoning, compliance (refusal vs compliance), different formatting, different base models and so on. 
What is correct and preferred completion may be chosen case by case, setting different preferences for different facets.
So under one facet completion A may be preferred, while under another facet completion B may be preferred.

New completions may be created by local or cloud models or manually.

Main supported ways to create new completions:
- Generate entire completion from the prompt and optional assistant reply prefill via some local or cloud model.
- Input completion manually, including case when you copy-paste from non-API cloud model like Grok. 
- Generate completion token-by-token, sourcing alternative tokens from local model, then guiding the generation towards preferred variant.
- Interactive beam search, described at [interactive beam search](./interactive_beam_search.md).
- Import from third-party source like dataset or benchmark, described at [datasets import](./datasets_import.md).

## Generating Entire Completion

Flow:
1. Select model, by default it's current target model.
2. Optionally prefill assistant reply to guide the generation.
3. Optionally adjust sampling parameters, but usually greedy sampling is preferred for deterministic results.
4. Click "Generate" button to generate completion.
5. Click "Save" button to save generated completion to the database.

## Manual Input

Flow:
1. Click "Edit" button to switch to manual editing mode.
2. Input or paste the completion text.
3. Optionally set model name if completion is sourced from some third-party source. Leave "manual" for manually created completions.
4. Click "Save" button to save generated completion to the database.

## Token-by-Token Generation

Flow:
1. Select model, by default it's current target model.
2. Optionally prefill assistant reply to guide the generation.
3. Optionally adjust sampling parameters, but usually greedy sampling is preferred for deterministic results.
4. Click "Token by Token" button to switch to token-by-token generation mode.
5. Keep clicking on token candidates to append them to the completion, filling it token by token.
6. Optionally use "Generate" button to finish the rest of the completion automatically.
7. Click "Save" button to save generated completion to the database.

## Truncation and Continuation

Unless <eos> token is sampled by model or chosen by user, completion is considered truncated, i.e. in the state when model wanted to continue generation, but was stopped by max tokens limit or user.
Such completions are marked with red "truncated" label.
For training samples, it's **HIGHLY** recommended to use only non-truncated completions, as truncated completions will force model to learn to stop generation early, which is usually not desired. 

Truncated completions may be continued by clicking "Continue" button, which will resume generation from the end of truncated completion.