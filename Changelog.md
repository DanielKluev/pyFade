# Changelog

## [Unreleased]

### Fixed
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
