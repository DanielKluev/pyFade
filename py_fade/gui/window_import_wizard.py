"""
Blocking (modal) window that guides user through importing dataset from a file.

Important aspects:
 - Clearly establish completions source, is it human or model generated? Can we link to specific model_id?
 - Track origin of imported samples/completions (e.g. GSM8K, Anthropic HH dataset, etc).
 - Optionally, define target facet to assign to all imported samples/completions.
 - For benchmark evaluation results, support paired imports of logs, from base and tuned models to filter for regressions.
 - Filtering samples is essential, we don't want to import garbage data. Support filtering by:
    - Prompt text (substring match, regex)
    - Completion text (substring match, regex)
    - Evaluation result: pass/fail/new failure

Flow:
 1. Select file(s) to import from.
 2. Try to guess file format, if known format (e.g. JSONL with specific fields), parse it.
    If not, ask user to define format by mapping fields to known concepts (prompt, completion, model_id, evaluation result, etc).
 3. Preview samples/completions found in the file, with ability to filter out unwanted ones.
 4. Select source type (human/model/benchmark), model_id if applicable, and target facet if applicable.
 5. Define sample group paths to import into, creating new groups if needed.
 6. Confirm and run import, showing progress.
 7. Show summary of results.

TODO:
 - Start with implementing support of lm_eval benchmark JSONL files, with case of paired imports for base and tuned models.
 - For lm_eval, we expect JSON file with metadata, and JSONL file with individual samples. Paired by timestamp in the name.
 - Example files from lm_eval, for development and testing:
    - gemma3:12b-u1 (tuned), GSM8K 3 docs:
        `tests/data/results_2025-09-09T13-31-53.431753.json`
        `tests/data/samples_gsm8k_2025-09-09T13-31-53.431753.jsonl`
    - gemma3:12b-it-q4_K_M (base), GSM8K 3 docs:
        `tests/data/results_2025-09-09T13-42-42.857006.json`
        `tests/data/samples_gsm8k_2025-09-09T13-42-42.857006.jsonl`
    - Expected: 1 shared success, 1 shared failure, 1 new failure in tuned model.
  - Matching is done by `prompt_hash` field in the sample, which is SHA256 of the prompt text.
  - Comparison of results is done using fields defined in `metrics` field of the sample JSON object.
"""
