# Changelog

## [Unreleased]

### Added
- **Expanded LM Eval Support**: Enhanced support for lm-evaluation-harness results with split subsets
  - Multiple samples files per results file now supported (e.g., MMLU with per-subset samples)
  - Improved model ID extraction from paths (extracts clean name from `/workspace/model-name`)
  - Full prompt text extraction with chat template token stripping (Gemma3, Qwen3, Llama3, Mistral)
  - Added template stripping functions: `strip_template_gemma3()`, `strip_template_qwen3()`, `strip_template_llama3()`, `strip_template_mistral()`
  - Auto-detection of template type from model ID or content markers via `strip_chat_template()`
  - Paired filtering correctly identifies regressions in tuned models vs base models
  - Comprehensive test coverage with 10 new unit tests for MMLU data and template stripping
  - All tests passing with zero failures
- **Sample Tags**: Implemented complete sample tagging functionality
  - Created many-to-many relationship between samples and tags via SampleTag association table
  - Added helper methods to Sample model: add_tag(), remove_tag(), get_tags(), has_tag()
  - Added helper methods to Tag model: get_samples(), update_sample_count()
  - Created modal dialog (SampleTagsDialog) for selecting tags to add/remove from samples
  - Added tags display and edit button to sample widget control panel
  - Implemented "Samples by Tag" navigation view in sidebar
  - Tags grouped hierarchically with samples organized by group_path under each tag
  - "No Tag" node for samples without any tags
  - Search filtering works across tags and samples
  - Comprehensive test coverage with 37 new unit tests (16 database, 21 UI)
  - All tests passing with zero failures
  - Pylint score: 10.00/10 for both py_fade and tests packages
- **Export Wizard Model Selection**: Added model selection step to export wizard for explicit target model choice
  - New model selection step in export wizard between template selection and output path
  - Model combobox populated with all available model IDs from providers manager
  - ExportController now accepts target_model_id parameter for logprobs validation
  - Export wizard passes selected model_id to export controller
  - Falls back to first available model if no model is explicitly selected
  - Export templates remain model-agnostic for reusability across model variants
  - Comprehensive test coverage with 9 new unit tests for model selection feature
  - Updated all existing export wizard tests to handle new step
- **Encrypted Export/Import**: Added AES-encrypted ZIP export/import functionality
  - Export templates can now encrypt exported datasets with a password using pyzipper library
  - Import wizard supports automatic detection and decryption of encrypted ZIP files
  - Plaintext data never touches disk when encryption is enabled
  - Password can be pre-configured in export template or prompted during export/import
  - Updated UI text to clarify encryption uses "encrypted ZIP" instead of SQLCipher
  - Comprehensive test coverage with 8 new unit tests for encrypted export/import

### Fixed
- **New Completion Frame Save Bug Fixes**: Fixed three critical bugs in the new completion frame save functionality
  - Bug 1: Manual mode now correctly saves edited text instead of reverting to original generated text
  - Bug 2: Token-by-token mode now properly saves accumulated tokens when save button is clicked
  - Bug 3: Token picker area expanded to 2x width of completion area for better visibility in token-by-token mode
  - Comprehensive test coverage with 2 new tests verifying all bug fixes

### Added
- **Role Tag Buttons Moved to Controls Panel**: Relocated system/user/assistant role tag buttons from prompt area to controls panel
  - Buttons (S, U, A) now appear in the controls panel on the right side of the sample widget
  - Maintains all existing functionality including keyboard shortcuts and insertion behavior
  - Better UI organization by grouping all controls together
  - Updated tests to verify new location while preserving functionality tests
  - Comprehensive test coverage with 2 new location verification tests
- **Facet Summary Report**: Added comprehensive facet summary report feature for tracking training readiness
  - Added `min_rating`, `min_logprob_threshold`, and `avg_logprob_threshold` fields to Facet model
  - Added UI controls in WidgetFacet for editing threshold values
  - New "Facet Summary" button in dataset context frame (enabled when facet and model are selected)
  - FacetSummaryController analyzes samples for SFT and DPO training readiness
  - Modal window displays statistics for finished/unfinished samples
  - Shows total loss calculations and detailed reasons for unfinished samples
  - For SFT: requires completion with rating >= min_rating and passing logprob thresholds
  - For DPO: requires high-rated completion plus at least one lower-rated completion
  - Comprehensive test coverage with 15 new unit tests and 5 UI tests
- **Beam Out from Heatmap**: Added ability to start beam search from any token position in heatmap mode
  - Click on any token in heatmap view to see alternatives for that position
  - Token picker shows up to 200 alternatives in multi-select mode
  - Automatically extracts prefix (all tokens before clicked position) as prefill
  - Starts beam generation with selected alternatives at clicked position
  - Maintains token fidelity by working with actual tokens rather than text
  - beam_token property is set on generated completions
  - Comprehensive test coverage with 8 new tests
- **Extended New Completion Widget**: Enhanced the new completion widget with four generation modes and comprehensive UI improvements
  - **Mode Selector**: Switch between Regular, Continue Truncated, Manual Input, and Token-by-Token generation modes
  - **Regular Mode**: Generate completions from prompt with optional prefill (existing behavior)
  - **Continuation Mode**: Continue truncated completions with high-fidelity token sequence preservation
  - **Manual Mode**: Manually input completion text with custom model ID for cloud provider completions
  - **Token-by-Token Mode**: Interactive token selection with real-time token picker showing next token candidates
    - Displays up to 100 token candidates sorted by logprob with color-coded probabilities
    - Manual token selection builds completion prefix step-by-step
    - "Continue" button allows switching from token-by-token to regular generation mid-sequence
  - Icon buttons with readable labels (Generate, Continue, Save) for clarity
  - Adaptive UI that shows/hides controls based on selected mode
  - Comprehensive test coverage with 16 new tests covering all modes and edge cases
- **Prompt Role Tag Insert**: Added UI controls for inserting multi-turn conversation role tags in prompts
  - Right-click context menu in prompt editor with options to insert system/user/assistant tags at cursor or end
  - Three buttons (S, U, A) in prompt control panel for quick tag insertion at end of prompt
  - System tag validation: only one system tag allowed and must be at beginning of prompt
  - User and assistant tags can be inserted multiple times at any position
  - Tags use flat prefix template format (`<|system|>`, `<|user|>`, `<|assistant|>`)
  - Comprehensive test coverage with 26 new tests for PlainTextEdit and WidgetSample
- **Beam search: truncated Completion continuation**: Both transient and persisted completions in beam search window now show continuation button if truncated. For persistent completions, the same 3-way editor flow is used as in WidgetSample. For transient completions, continuation is generated in place without additional user input, keeping current context size and replacing the completion frame with the expanded completion.

### Fixed
- **Multi-line and Emoji Highlighting Bug**: Fixed highlighting issues with multi-line text and emoji/multi-byte Unicode characters in completion text editor
  - Fixed multi-line prefill and beam token highlighting by replacing Qt's `document.find()` (which doesn't support newlines) with manual string search
  - Replaced Python string indexing with Qt's QTextCursor positioning for correct UTF-16 code unit handling
  - Fixed prefill, beam token, and heatmap highlighting to properly handle surrogate pairs, newlines, and multi-line text
  - Added comprehensive test coverage for multi-line and emoji highlighting scenarios
- **Beam Completion Widget Update Bug**: Fixed issue where CompletionFrame in beam search window was not updated after saving a beam
  - Modified `WidgetSample.add_completion()` to return the created `PromptCompletion`
  - Updated `WidgetCompletionBeams.on_beam_accepted()` to update frame with persisted completion
  - Frame now correctly shows saved state (archive button visible, save/pin buttons hidden)
  - Model info header now becomes visible for saved beams
  - Added 3 comprehensive unit tests to verify fix
- **Emoji Highlighting Bug**: Fixed highlighting issues with emoji and multi-byte Unicode characters in completion text editor
  - Replaced Python string indexing with Qt's UTF-16-aware text positioning methods
  - Fixed prefill, beam token, and heatmap highlighting to properly handle surrogate pairs
  - All text positioning now uses `QTextDocument.find()` and `QTextCursor` for correct UTF-16 code unit handling
  - Added comprehensive test coverage for emoji highlighting scenarios
- **Prompt Editor Rich Text Bug**: Fixed issue where prompt editor allowed rich markup from copy-paste operations. The prompt editor now enforces plain text only while preserving programmed formatting markers (flat prefix templates).
  - Created `PlainTextEdit` component that extends `QTextEdit` with plain text enforcement
  - Replaced `QTextEdit` with `PlainTextEdit` in `WidgetSample` prompt area
  - Added comprehensive tests for rich text rejection and plain text enforcement

### Added
- `PlainTextEdit` widget component for plain text only editing with rich text rejection
- **Samples By Facet Navigation**: Added new navigation view to browse samples grouped by their associated facets
  - Root nodes are facets with "No Facet" node for unassociated samples
  - Samples are organized hierarchically under each facet by their group path
  - Samples can appear under multiple facets if rated for multiple facets
  - Search filter works across facet names, descriptions, sample titles, and group paths
  - Added `Facet.get_samples()` and `Facet.get_samples_without_facet()` methods
  - Comprehensive test coverage with 9 new tests
- **Improved Logprob Coloring**: Enhanced visual distinction for token probability heatmaps with new Dark Green → Orange → Red → Purple spectrum
  - 18 precisely specified color thresholds for better visual discrimination
  - Clear distinction between high probabilities (p=0.95 vs p=0.9) and tail probabilities (-20 vs -25)
  - Smooth linear interpolation between all threshold points
  - Maintains full backwards compatibility with existing code
- **Rating Removal**: Added ability to remove completion ratings for facets
  - Clicking on an already-rated star now shows a dialog with options to remove the rating, change it, or cancel
  - New `_remove_rating()` method handles deletion and UI state reset
  - UI properly updates to unrated state after removal (stars reset, tooltips update)
  - Comprehensive test coverage for removal, cancellation, and change options

## Version 0.0.1 (to be released)

- Initial public release of pyFADE.
- Major: ⭐ **Per-facet completion ratings** – Completions now include a five-star control with half-star support for fine-grained quality ratings. Ratings are foundation for preparing and exporting datasets for actual fine-tuning.
- Major: ⭐ **Facet Backup** – Complete import/export functionality for facets with all associated data (samples, completions, ratings). Supports JSON-based backup format with version control, merge strategies, and round-trip consistency validation.
- Major: **Dataset database encryption** using SQLCipher with `sqlcipher3` package.
- Minor: Option to encrypt/decrypt/change password of dataset databases.
- Minor: CRUD UI for Tags, Facets, and Export Templates in the dataset workspace.
- QA: Basic unit tests for various parts of the GUI.
- QA: Comprehensive test coverage for Facet Backup functionality (36 tests covering serialization, import, export, and full-cycle workflows).
