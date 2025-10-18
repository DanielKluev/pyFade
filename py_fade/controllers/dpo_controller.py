"""
Direct Preference Optimization (DPO) data builder.

Unlike SFT, DPO may yield multiple training samples from a single dataset sample.

For each dataset sample, we follow these rules:
- "Chosen" completion must have rating above specified threshold, we don't pair low-rated samples together.
- For "Rejected", check if there any non-top-rated completion that passes logprobs thresholds:
    - If yes, we apply strict logprobs filtering for all pairs.
    - If no, we choose one highest logprobs completion which isn't top-rated and use it as "Rejected" without further filtering.
- If PromptCompletionPairwiseRanking exists for the pair, it's treated as preferential, but if ratings contradict that (winner has LESSER rating than loser), inform about error.
- Then we use above criteria to create all possible pairs, for every acceptable "Chosen" picking every completion with lesser rating as "Rejected".
"""
