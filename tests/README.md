# pyFADE Test Suite Documentation

## Overview

This test suite provides comprehensive coverage of the pyFADE application, organized into logical categories matching the codebase structure.

## Test Organization

Tests are organized into four main categories:

### `test_database/`
Tests for database models and ORM functionality:
- `test_dataset.py` - Dataset initialization and management
- `test_dataset_encryption.py` - SQLCipher encryption features
- `test_facet.py` - Facet CRUD operations
- `test_prompt.py` - Prompt revision management
- `test_sample_notes.py` - Sample notes functionality
- `test_tag.py` - Tag management

### `test_logic/`
Tests for business logic, controllers, and data formats:
- Controllers:
  - `test_facet_summary_controller.py` - Facet summary statistics
  - `test_import_controller.py` - Import workflow orchestration
  - `test_text_generation_controller.py` - Text generation coordination
- Data Formats:
  - `test_facet_backup.py` - Facet backup format serialization
  - `test_export_facet_backup.py` - Facet backup export functionality
  - `test_import_facet_backup.py` - Facet backup import functionality
  - `test_share_gpt_format.py` - ShareGPT format conversion
  - `test_lm_eval_results.py` - LM-Eval results import
  - `test_utils.py` - Data format utilities
- Export Logic:
  - `test_export_template.py` - Export template functionality
  - `test_export_with_thresholds.py` - Export with quality thresholds
  - `test_encrypted_export_import.py` - Encrypted export/import
- Providers:
  - `test_mock_provider.py` - Mock LLM provider
  - `test_llama_cpp.py` - Llama.cpp provider integration
  - `test_flat_prefix_template.py` - Flat prefix template conversion
- Application Logic:
  - `test_app_config.py` - Application configuration management

### `test_ui/`
Tests for GUI components and user interactions:
- Main Widgets:
  - `test_widget_sample_*.py` - Sample editor widget tests (multiple files)
  - `test_widget_completion*.py` - Completion display tests (multiple files)
  - `test_widget_facet.py` - Facet management widget
  - `test_widget_tag.py` - Tag management widget
  - `test_widget_launcher.py` - Application launcher
  - `test_widget_navigation_sidebar.py` - Navigation sidebar
  - `test_widget_export_template.py` - Export template editor
  - `test_widget_new_completion.py` - New completion generation
- Windows:
  - `test_window_import_wizard.py` - Import wizard flow
  - `test_window_export_wizard.py` - Export wizard flow
  - `test_window_facet_summary.py` - Facet summary window
  - `test_window_three_way_completion_editor.py` - Three-way comparison editor
- Components:
  - `test_widget_token_picker.py` - Token selection widget
  - `test_widget_plain_text_edit_role_tags.py` - Role tag editor
  - `test_widget_dataset_top_context.py` - Dataset context menu
- Features:
  - `test_beam_*.py` - Beam search mode tests (multiple files)
  - `test_emoji_highlighting.py` - Emoji syntax highlighting
  - `test_aux_logprobs_to_color.py` - Logprob visualization

### `test_integration/`
End-to-end integration tests:
- `test_full_cycle.py` - Complete user workflow (import → edit → export)
- `test_facet_backup_full_cycle.py` - Complete facet backup cycle
- `test_export_wizard_simple.py` - Export wizard integration
- `test_import_wizard_integration.py` - Import wizard integration

## Shared Test Utilities

### `tests/helpers/`
Reusable test helpers to reduce code duplication:

- **`data_helpers.py`** - Database and data setup helpers:
  - `ensure_test_facets()` - Create standard test facets
  - `create_test_completion()` - Create test completions with defaults
  - `build_sample_with_completion()` - Create sample + completion chain
  - `create_test_llm_response()` - Create LLMResponse for beam mode
  - `create_test_sample_with_completion()` - Complete sample creation with ratings and logprobs
  - And more specialized helpers for logprobs, tokens, etc.

- **`ui_helpers.py`** - UI testing utilities:
  - `patch_message_boxes()` - Replace modal dialogs with logging stubs
  - `setup_test_app_with_fake_home()` - Create app with temporary home directory
  - `setup_completion_frame_with_heatmap()` - Configure CompletionFrame for testing
  - `mock_three_way_editor()` - Mock three-way editor dialogs
  - `create_mock_mapped_model()` - Create mock MappedModel instances

- **`facet_backup_helpers.py`** - Facet backup test utilities:
  - `create_temp_database()` - Context manager for temporary databases
  - `create_test_facet_with_data()` - Create facet with samples and completions
  - `export_facet_to_backup()` - Helper for facet export operations
  - `import_facet_from_backup()` - Helper for facet import operations
  - `validate_backup_content()` - Validate backup file structure

- **`export_wizard_helpers.py`** - Export wizard test utilities

### `tests/conftest.py`
Pytest fixtures available to all tests:

- **`qt_app`** (session scope) - QApplication instance in offscreen mode
- **`temp_dataset`** - Temporary SQLite dataset for each test
- **`app_with_dataset`** - pyFadeApp instance with temporary dataset
- **`ensure_google_icon_font`** (session scope) - Load Google icon font once

## Test Best Practices

### Test Structure
- Each test module corresponds to a source module (e.g., `test_app_config.py` tests `app_config.py`)
- Tests are organized into classes by functionality (e.g., `TestAppConfigDefaults`, `TestAppConfigLoadSave`)
- Test names clearly describe what is being tested (e.g., `test_load_invalid_yaml_uses_defaults`)

### Test Documentation
Every test has a comprehensive docstring that:
1. Describes the flow being tested
2. Lists edge cases explicitly covered
3. Explains expected behavior

Example:
```python
def test_load_invalid_yaml_uses_defaults(self, ...) -> None:
    """
    Test that load() handles invalid YAML gracefully.
    
    Tests error handling and default values when YAML file is malformed.
    """
```

### Using Shared Helpers
Tests extensively use shared helpers to:
- Eliminate code duplication
- Provide consistent test data
- Make tests more readable
- Centralize common setup logic

Example:
```python
# Instead of manually creating sample + prompt + completion:
sample, completion = build_sample_with_completion(dataset, completion_text="Test")

# Instead of manually setting up completion frames:
frame, text_edit = setup_completion_frame_with_heatmap(dataset, beam, qt_app)
```

### GUI Testing
- All GUI tests run in Qt offscreen mode (`QT_QPA_PLATFORM=offscreen`)
- Modal dialogs are mocked to avoid blocking test execution
- Tests use `qt_app.processEvents()` to process Qt event queue
- Tests verify both state and UI element properties

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Specific Category
```bash
pytest tests/test_database/
pytest tests/test_logic/
pytest tests/test_ui/
pytest tests/test_integration/
```

### Run with Coverage
```bash
pytest tests/ --cov=py_fade --cov-report=term
pytest tests/ --cov=py_fade --cov-report=html  # HTML report
```

### Run with Debug Output
```bash
pytest tests/ --log-cli-level=DEBUG
pytest tests/test_logic/test_app_config.py -v --log-cli-level=DEBUG
```

### Run Specific Test
```bash
pytest tests/test_logic/test_app_config.py::TestAppConfigDefaults::test_default_values
```

## Coverage Report

**Current coverage: 77%** (9,835 statements total, 2,297 missed)

*Note: These numbers reflect the state after improvements in this PR, including the new test_app_config.py with 21 tests.*

### Well-Covered Modules (90%+)
- ✅ `app_config.py` - 100%
- ✅ `completion.py` - 96%
- ✅ `sample.py` - 96%
- ✅ `facet.py` - 96%
- ✅ `prompt.py` - 100%
- ✅ `completion_pairwise_ranks.py` - 100%
- ✅ `completion_rating.py` - 97%
- ✅ `utils.py` - 100%
- ✅ `widget_completion.py` - 97%
- ✅ `aux_logprobs_to_color.py` - 96%
- ✅ `facet_backup.py` - 96%
- ✅ `import_controller.py` - 95%
- ✅ `facet_summary_controller.py` - 95%
- ✅ `widget_token_picker.py` - 95%
- ✅ `flat_prefix_template.py` - 91%
- ✅ Multiple GUI components at 90%+

### Modules Requiring More Coverage
- ⚠️ `dataset.py` - 38% (complex database operations, many optional paths)
- ⚠️ `app.py` - 47% (GUI initialization, harder to test)
- ⚠️ `widget_dataset_top.py` - 64% (complex main widget)
- ⚠️ `widget_completion_beams.py` - 58% (beam search UI)
- ⚠️ `base_data_classes.py` - 58% (data class utilities)
- ⚠️ `text_generation_controller.py` - 54% (generation orchestration)
- ⚠️ External providers (ollama, llama_cpp) - 17-23% (require external dependencies)

### Coverage Improvement Strategies
To reach 90% coverage would require:
1. Testing GUI initialization paths in `app.py` and `widget_dataset_top.py`
2. Testing more edge cases in `dataset.py` (error handling, complex queries)
3. Adding tests for beam search UI interactions
4. Testing data class serialization edge cases
5. Testing text generation controller with various provider scenarios

Note: External provider modules (ollama, llama_cpp) are intentionally not fully tested as they require external dependencies and are covered by integration tests with mock providers.

## Quality Metrics

*As of this test suite maintenance PR:*

### Pytest Results
- ✅ **481 tests passed** (485 total, 4 skipped for optional dependencies)
- 🟡 **4 tests skipped** (require optional dependencies like sqlcipher, llama-cpp)
- ❌ **0 tests failed**

### Pylint Scores
- ✅ **py_fade/: 10.00/10**
- ✅ **tests/: 10.00/10**

### Test Execution Time
- Full suite: ~20 seconds
- Database tests: ~2 seconds
- Logic tests: ~5 seconds
- UI tests: ~10 seconds
- Integration tests: ~3 seconds

## Contributing to Tests

When adding new tests:
1. **Match structure**: Create `test_<module>.py` for each source module
2. **Use helpers**: Leverage shared helpers in `tests/helpers/`
3. **Document thoroughly**: Add comprehensive docstrings explaining what is tested
4. **Group logically**: Organize tests into classes by functionality
5. **Test edge cases**: Explicitly test error conditions and boundary cases
6. **Maintain pylint**: Ensure tests achieve 10.00/10 pylint score
7. **Keep tests fast**: Mock external dependencies, use temp databases

## Maintenance

### Regular Checks
```bash
# Ensure all tests pass
pytest tests/

# Check code quality
pylint py_fade tests

# Format code
yapf -i <changed_files>

# Check coverage
pytest tests/ --cov=py_fade --cov-report=term
```

### Before Committing
1. Run full test suite
2. Check pylint on changed files
3. Format code with yapf
4. Verify coverage hasn't decreased
