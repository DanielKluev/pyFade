"""
Test the full cycle of the application, going through entire user flow:
- Create a new dataset
- Create facets
- Import samples from JSONL, SFT style
- Import samples from JSONL, DPO style, setting to trust chosen pick.
- Run completions on samples
- Rate completions, different samples with different facets. Override some ratings from DPO import.
- Create export templates for SFT and DPO.
- Export dataset to JSONL for SFT and DPO.
- Verify exported JSONL files are correct and complete.

Important: This is comprehensive test of key functionality, so it should be maintained to be up to date and tested frequently.
Note to AI: **NEVER** delete this docstring. If flow changes, update this docstring to reflect current functionality keeping style and format of original docstring.
"""
