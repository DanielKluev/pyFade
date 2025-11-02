"""
Test suite for Model Manager window UI component.

Tests model management dialog functionality including:
- Dialog initialization and display
- llama.cpp models tab
- Ollama models tab
- Remote API tab
- Model configuration save/load
- Model validation
- Provider reload on save
"""
# pylint: disable=unused-argument,redefined-outer-name
from __future__ import annotations

import logging
import pathlib
from typing import TYPE_CHECKING, Generator

import pytest
from PyQt6.QtWidgets import QMessageBox

from py_fade.app import pyFadeApp
from py_fade.gui.window_model_manager import ModelManagerWindow
from tests.helpers.ui_helpers import patch_message_boxes, setup_test_app_without_dataset, cleanup_app_widgets

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication


@pytest.fixture
def temp_app(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, qt_app: "QApplication") -> Generator[pyFadeApp, None, None]:
    """Create a minimal pyFadeApp instance for testing without a dataset."""
    app = setup_test_app_without_dataset(tmp_path, monkeypatch)
    try:
        yield app
    finally:
        cleanup_app_widgets(app)


def test_model_manager_window_initialization(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test initializing the Model Manager window.

    Verifies that the dialog is properly initialized with tabs for each model type.
    """
    caplog.set_level(logging.DEBUG, logger="ModelManagerWindow")
    test_logger = logging.getLogger("test_model_manager.initialization")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)

    assert dialog.windowTitle() == "Model Manager"
    assert dialog.isModal()
    assert dialog.tab_widget is not None
    assert dialog.tab_widget.count() == 3
    assert dialog.tab_widget.tabText(0) == "llama.cpp Models"
    assert dialog.tab_widget.tabText(1) == "Ollama Models"
    assert dialog.tab_widget.tabText(2) == "Remote API"


def test_model_manager_loads_existing_config(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that Model Manager loads existing model configurations.

    Verifies that models from app config are properly loaded.
    """
    test_logger = logging.getLogger("test_model_manager.load_config")
    patch_message_boxes(monkeypatch, test_logger)

    # Set up test models in config
    temp_app.config.models = [
        {
            "id": "test_gguf_model",
            "gguf": "/path/to/model.gguf"
        },
        {
            "id": "test_ollama_model",
            "ollama_id": "llama3:8b"
        },
    ]

    dialog = ModelManagerWindow(None, temp_app)

    # Check that models are loaded
    assert len(dialog.models_config) == 2
    assert dialog.models_config[0]["id"] == "test_gguf_model"
    assert dialog.models_config[1]["id"] == "test_ollama_model"


def test_llamacpp_tab_add_model(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test adding a new llama.cpp model.

    Verifies that a new model can be added to the list.
    """
    test_logger = logging.getLogger("test_model_manager.add_llamacpp")
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.llamacpp_tab

    initial_count = tab.model_list.count()
    tab.add_button.click()

    assert tab.model_list.count() == initial_count + 1
    assert len(tab.models) == initial_count + 1
    assert tab.models[-1]["id"] == "new_model"


def test_llamacpp_tab_remove_model(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test removing a llama.cpp model.

    Verifies that a model can be removed from the list.
    """
    test_logger = logging.getLogger("test_model_manager.remove_llamacpp")

    # Mock QMessageBox.question to return Yes
    def mock_question(*args, **kwargs):
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", mock_question)
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.llamacpp_tab

    # Add a model first
    tab.add_button.click()
    initial_count = tab.model_list.count()

    # Select and remove
    tab.model_list.setCurrentRow(initial_count - 1)
    tab.remove_button.click()

    assert tab.model_list.count() == initial_count - 1
    assert len(tab.models) == initial_count - 1


def test_llamacpp_tab_edit_model(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test editing a llama.cpp model.

    Verifies that model details can be edited and applied.
    """
    test_logger = logging.getLogger("test_model_manager.edit_llamacpp")
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.llamacpp_tab

    # Add a model
    tab.add_button.click()
    tab.model_list.setCurrentRow(0)

    # Edit fields
    tab.id_edit.setText("my_custom_model")
    tab.gguf_edit.setText("/path/to/custom.gguf")
    tab.lora_edit.setText("/path/to/lora.gguf")

    # Apply changes
    tab.apply_button.click()

    # Verify changes
    assert tab.models[0]["id"] == "my_custom_model"
    assert tab.models[0]["gguf"] == "/path/to/custom.gguf"
    assert tab.models[0]["lora"] == "/path/to/lora.gguf"
    assert tab.model_list.item(0).text() == "my_custom_model"


def test_llamacpp_tab_browse_gguf(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test browsing for GGUF file.

    Verifies that file dialog sets the GGUF path.
    """
    test_logger = logging.getLogger("test_model_manager.browse_gguf")
    patch_message_boxes(monkeypatch, test_logger)

    # Mock file dialog
    def mock_get_open_filename(*args, **kwargs):
        return ("/mock/path/to/model.gguf", "")

    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getOpenFileName", mock_get_open_filename)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.llamacpp_tab

    tab.add_button.click()
    tab.model_list.setCurrentRow(0)
    tab.gguf_browse_button.click()

    assert tab.gguf_edit.text() == "/mock/path/to/model.gguf"


def test_ollama_tab_add_model(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test adding a new Ollama model.

    Verifies that a new model can be added to the list.
    """
    test_logger = logging.getLogger("test_model_manager.add_ollama")
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.ollama_tab

    initial_count = tab.model_list.count()
    tab.add_button.click()

    assert tab.model_list.count() == initial_count + 1
    assert len(tab.models) == initial_count + 1
    assert tab.models[-1]["id"] == "new_ollama_model"
    assert tab.models[-1]["ollama_id"] == "MAIN_ID"


def test_ollama_tab_edit_model(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test editing an Ollama model.

    Verifies that model details can be edited and applied.
    """
    test_logger = logging.getLogger("test_model_manager.edit_ollama")
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.ollama_tab

    # Add a model
    tab.add_button.click()
    tab.model_list.setCurrentRow(0)

    # Edit fields
    tab.id_edit.setText("llama3:8b")
    tab.ollama_id_edit.setText("MAIN_ID")

    # Apply changes
    tab.apply_button.click()

    # Verify changes
    assert tab.models[0]["id"] == "llama3:8b"
    assert tab.models[0]["ollama_id"] == "MAIN_ID"


def test_ollama_tab_import_no_registry(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test importing from Ollama registry when registry is not available.

    Verifies that appropriate warning is shown.
    """
    test_logger = logging.getLogger("test_model_manager.import_no_registry")

    warning_shown = {"value": False}

    def mock_warning(*args, **kwargs):
        warning_shown["value"] = True
        test_logger.info("Warning shown: %s", args)

    monkeypatch.setattr(QMessageBox, "warning", mock_warning)

    # Ensure no registry is configured
    temp_app.providers_manager.ollama_registry = None

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.ollama_tab

    # Try to import
    tab._on_import_from_registry()  # pylint: disable=protected-access

    assert warning_shown["value"]


def test_model_manager_save_validates_empty_id(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that validation rejects models with empty IDs.

    Verifies that models must have an ID.
    """
    test_logger = logging.getLogger("test_model_manager.validate_empty_id")

    warning_shown = {"value": False}

    def mock_warning(*args, **kwargs):
        warning_shown["value"] = True
        test_logger.info("Warning shown: %s", args)

    monkeypatch.setattr(QMessageBox, "warning", mock_warning)

    dialog = ModelManagerWindow(None, temp_app)

    # Create invalid model (no id)
    invalid_models = [{"gguf": "/path/to/model.gguf"}]

    result = dialog._validate_models(invalid_models)  # pylint: disable=protected-access

    assert not result
    assert warning_shown["value"]


def test_model_manager_save_validates_duplicate_ids(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that validation rejects duplicate model IDs.

    Verifies that each model must have a unique ID.
    """
    test_logger = logging.getLogger("test_model_manager.validate_duplicate")

    warning_shown = {"value": False}

    def mock_warning(*args, **kwargs):
        warning_shown["value"] = True
        test_logger.info("Warning shown: %s", args)

    monkeypatch.setattr(QMessageBox, "warning", mock_warning)

    dialog = ModelManagerWindow(None, temp_app)

    # Create models with duplicate IDs
    duplicate_models = [
        {
            "id": "model1",
            "gguf": "/path/to/model1.gguf"
        },
        {
            "id": "model1",
            "gguf": "/path/to/model2.gguf"
        },
    ]

    result = dialog._validate_models(duplicate_models)  # pylint: disable=protected-access

    assert not result
    assert warning_shown["value"]


def test_model_manager_save_validates_no_backend(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that validation rejects models without a backend.

    Verifies that models must have either GGUF or Ollama ID.
    """
    test_logger = logging.getLogger("test_model_manager.validate_no_backend")

    warning_shown = {"value": False}

    def mock_warning(*args, **kwargs):
        warning_shown["value"] = True
        test_logger.info("Warning shown: %s", args)

    monkeypatch.setattr(QMessageBox, "warning", mock_warning)

    dialog = ModelManagerWindow(None, temp_app)

    # Create model without backend
    invalid_models = [{"id": "model1"}]

    result = dialog._validate_models(invalid_models)  # pylint: disable=protected-access

    assert not result
    assert warning_shown["value"]


def test_model_manager_save_valid_models(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that validation accepts valid model configurations.

    Verifies that valid models pass validation.
    """
    test_logger = logging.getLogger("test_model_manager.validate_valid")
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)

    # Create valid models
    valid_models = [
        {
            "id": "model1",
            "gguf": "/path/to/model1.gguf"
        },
        {
            "id": "model2",
            "ollama_id": "llama3:8b"
        },
    ]

    result = dialog._validate_models(valid_models)  # pylint: disable=protected-access

    assert result


def test_model_manager_save_updates_config(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that saving updates the app configuration.

    Verifies that model configurations are saved to app config.
    """
    test_logger = logging.getLogger("test_model_manager.save_config")

    # Mock message box to auto-confirm
    def mock_information(*args, **kwargs):
        test_logger.info("Information shown: %s", args)

    monkeypatch.setattr(QMessageBox, "information", mock_information)

    # Mock config save
    save_called = {"value": False}
    original_save = temp_app.config.save

    def mock_save():
        save_called["value"] = True
        original_save()

    monkeypatch.setattr(temp_app.config, "save", mock_save)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.llamacpp_tab

    # Add a model
    tab.add_button.click()
    tab.model_list.setCurrentRow(0)
    tab.id_edit.setText("test_model")
    tab.gguf_edit.setText("/path/to/test.gguf")
    tab.apply_button.click()

    # Save
    dialog._on_save()  # pylint: disable=protected-access

    assert save_called["value"]
    assert any(m.get("id") == "test_model" for m in temp_app.config.models)


def test_remote_api_tab_placeholder(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that Remote API tab is a placeholder.

    Verifies that the tab exists but is disabled.
    """
    test_logger = logging.getLogger("test_model_manager.remote_api_placeholder")
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.remote_api_tab

    assert tab.model_list.isEnabled() is False
    assert len(tab.models) == 0


def test_model_manager_form_change_enables_apply(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that editing form fields enables the Apply button.

    Verifies that changes trigger the Apply button to become enabled.
    """
    test_logger = logging.getLogger("test_model_manager.form_change")
    patch_message_boxes(monkeypatch, test_logger)

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.llamacpp_tab

    # Add and select a model
    tab.add_button.click()
    tab.model_list.setCurrentRow(0)

    # Apply button should be disabled initially after applying
    tab.apply_button.click()
    assert not tab.apply_button.isEnabled()

    # Edit a field
    tab.id_edit.setText("changed_model")

    # Apply button should now be enabled
    assert tab.apply_button.isEnabled()


def test_llamacpp_tab_loads_existing_models(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that llama.cpp tab loads existing models from config.

    Verifies that models with GGUF paths are loaded into the tab.
    """
    test_logger = logging.getLogger("test_model_manager.load_llamacpp")
    patch_message_boxes(monkeypatch, test_logger)

    # Set up test models
    test_models = [
        {
            "id": "gguf_model_1",
            "gguf": "/path/to/model1.gguf"
        },
        {
            "id": "gguf_model_2",
            "gguf": "/path/to/model2.gguf",
            "lora": "/path/to/lora.gguf"
        },
        {
            "id": "ollama_only",
            "ollama_id": "llama3:8b"
        },  # Should not be loaded in this tab
    ]

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.llamacpp_tab
    tab.load_models(test_models)

    # Should have 2 llama.cpp models
    assert len(tab.models) == 2
    assert tab.model_list.count() == 2
    assert tab.models[0]["id"] == "gguf_model_1"
    assert tab.models[1]["id"] == "gguf_model_2"


def test_ollama_tab_loads_existing_models(
    temp_app: pyFadeApp,
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that Ollama tab loads existing models from config.

    Verifies that Ollama-only models are loaded into the tab.
    """
    test_logger = logging.getLogger("test_model_manager.load_ollama")
    patch_message_boxes(monkeypatch, test_logger)

    # Set up test models
    test_models = [
        {
            "id": "ollama_model_1",
            "ollama_id": "llama3:8b"
        },
        {
            "id": "ollama_model_2",
            "ollama_id": "MAIN_ID"
        },
        {
            "id": "gguf_model",
            "gguf": "/path/to/model.gguf"
        },  # Should not be loaded in this tab
        {
            "id": "both",
            "gguf": "/path/to/model.gguf",
            "ollama_id": "llama3:8b"
        },  # Should not be loaded (has gguf)
    ]

    dialog = ModelManagerWindow(None, temp_app)
    tab = dialog.ollama_tab
    tab.load_models(test_models)

    # Should have 2 Ollama-only models
    assert len(tab.models) == 2
    assert tab.model_list.count() == 2
    assert tab.models[0]["id"] == "ollama_model_1"
    assert tab.models[1]["id"] == "ollama_model_2"
