# Changelog

## Version 0.0.1 (to be released)

- Initial public release of pyFADE.
- Major: ⭐ **Per-facet completion ratings** – Completions now include a five-star control with half-star support for fine-grained quality ratings. Ratings are foundation for preparing and exporting datasets for actual fine-tuning.
- Major: ⭐ **Facet Backup** – Complete import/export functionality for facets with all associated data (samples, completions, ratings). Supports JSON-based backup format with version control, merge strategies, and round-trip consistency validation.
- Major: **Dataset database encryption** using SQLCipher with `sqlcipher3` package.
- Minor: Option to encrypt/decrypt/change password of dataset databases.
- Minor: CRUD UI for Tags, Facets, and Export Templates in the dataset workspace.
- QA: Basic unit tests for various parts of the GUI.
- QA: Comprehensive test coverage for Facet Backup functionality (36 tests covering serialization, import, export, and full-cycle workflows).
