# Changelog

## [Unreleased]

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
