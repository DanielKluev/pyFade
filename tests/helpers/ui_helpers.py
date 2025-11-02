"""
UI testing utilities and helpers for GUI components.
"""
from __future__ import annotations

import logging
import pathlib
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    import pytest
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def patch_message_boxes(monkeypatch: "pytest.MonkeyPatch", logger: logging.Logger) -> None:
    """
    Replace modal message boxes with logging stubs for deterministic tests.

    This helper patches QMessageBox methods to log their calls instead of showing
    modal dialogs, making GUI tests run deterministically in headless environments.
    """

    def _info(*args, **kwargs):
        logger.debug("QMessageBox.information args=%s kwargs=%s", args, kwargs)
        return QMessageBox.StandardButton.Ok

    def _critical(*args, **kwargs):
        logger.debug("QMessageBox.critical args=%s kwargs=%s", args, kwargs)
        return QMessageBox.StandardButton.Ok

    def _question(*args, **kwargs):
        logger.debug("QMessageBox.question args=%s kwargs=%s", args, kwargs)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "information", staticmethod(_info))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(_critical))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(_question))


def setup_test_app_with_fake_home(
    temp_dataset: "DatasetDatabase",
    tmp_path: pathlib.Path,
    monkeypatch: "pytest.MonkeyPatch",
) -> "pyFadeApp":
    """
    Create a pyFadeApp instance with a fake home directory for testing.

    This helper reduces duplication in test setup by providing a common way
    to create an app instance with a temporary home directory.
    """
    from py_fade.app import pyFadeApp  # pylint: disable=import-outside-toplevel

    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

    config_path = fake_home / "config.yaml"
    app = pyFadeApp(config_path=config_path)
    app.current_dataset = temp_dataset
    return app


def setup_test_app_without_dataset(
    tmp_path: pathlib.Path,
    monkeypatch: "pytest.MonkeyPatch",
) -> "pyFadeApp":
    """
    Create a minimal pyFadeApp instance without a dataset for testing.

    This helper reduces duplication in test setup by providing a common way
    to create an app instance with a temporary home directory but no dataset.
    """
    from py_fade.app import pyFadeApp  # pylint: disable=import-outside-toplevel

    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

    config_path = fake_home / "config.yaml"
    app = pyFadeApp(config_path=config_path)
    return app


def cleanup_app_widgets(app: "pyFadeApp") -> None:
    """
    Clean up app widgets after tests.

    This helper reduces duplication in test teardown by providing a common way
    to clean up app widgets.
    """
    if hasattr(app, "dataset_widget") and app.dataset_widget:
        app.dataset_widget.deleteLater()
    if hasattr(app, "launcher") and app.launcher:
        app.launcher.deleteLater()


def setup_dataset_session(dataset: "DatasetDatabase") -> None:
    """
    Set up and commit the dataset session for testing.

    This helper reduces duplication in test setup by providing a common way
    to prepare a dataset session for tests.
    """
    session = dataset.session
    assert session is not None
    session.flush()
    session.commit()


def setup_completion_frame_with_heatmap(dataset: "DatasetDatabase", beam, qt_app, display_mode: str = "beam"):
    """
    Create and configure a CompletionFrame with heatmap mode enabled.

    This helper reduces duplication in tests that need to verify heatmap
    and token position cache functionality.

    Args:
        dataset: The dataset database to use
        beam: The LLMResponse object to display
        qt_app: The Qt application instance for processing events
        display_mode: Display mode for the frame (default: "beam")

    Returns:
        tuple: (frame, text_edit) - The configured CompletionFrame and its text_edit widget
    """
    from py_fade.gui.components.widget_completion import CompletionFrame  # pylint: disable=import-outside-toplevel

    frame = CompletionFrame(dataset, beam, display_mode=display_mode)
    text_edit = frame.text_edit

    # Enable heatmap mode with logprobs
    text_edit.set_logprobs(beam.logprobs)
    text_edit.set_heatmap_mode(True)
    frame.show()
    qt_app.processEvents()

    return frame, text_edit


def mock_three_way_editor(monkeypatch: "pytest.MonkeyPatch"):
    """
    Mock ThreeWayCompletionEditorWindow to avoid showing modal dialogs in tests.

    This helper reduces code duplication in tests that need to verify behavior
    involving the three-way completion editor without actually showing the dialog.

    Args:
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        list: A list that will be populated with editor instances when the editor is instantiated
    """
    from py_fade.gui.window_three_way_completion_editor import ThreeWayCompletionEditorWindow  # pylint: disable=import-outside-toplevel

    editor_instances = []
    original_init = ThreeWayCompletionEditorWindow.__init__

    def mock_init(self, *args, **kwargs):
        editor_instances.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(ThreeWayCompletionEditorWindow, "__init__", mock_init)

    # Mock exec to avoid actual dialog showing
    monkeypatch.setattr(ThreeWayCompletionEditorWindow, "exec", lambda self: 0)

    return editor_instances


def create_mock_mapped_model(model_id: str = "test-model", path: str = "test-model"):
    """
    Create a mock MappedModel for testing.

    This helper reduces code duplication in tests that need a mock MappedModel
    with standard test values.

    Args:
        model_id: Model identifier (default: "test-model")
        path: Model path (default: "test-model")

    Returns:
        MagicMock: A mock MappedModel with model_id and path attributes set
    """
    from unittest.mock import MagicMock  # pylint: disable=import-outside-toplevel

    mapped_model = MagicMock()
    mapped_model.model_id = model_id
    mapped_model.path = path
    return mapped_model


def setup_completion_frame_basic(dataset: "DatasetDatabase", beam, qt_app, display_mode: str = "beam"):
    """
    Create and show a CompletionFrame with basic setup.

    This helper reduces duplication in tests that need to create a CompletionFrame
    and verify basic text display without additional configuration.

    Args:
        dataset: The dataset database to use
        beam: The LLMResponse object to display
        qt_app: The Qt application instance for processing events
        display_mode: Display mode for the frame (default: "beam")

    Returns:
        tuple: (frame, text_edit) - The CompletionFrame and its text_edit widget
    """
    from py_fade.gui.components.widget_completion import CompletionFrame  # pylint: disable=import-outside-toplevel

    frame = CompletionFrame(dataset, beam, display_mode=display_mode)
    text_edit = frame.text_edit
    frame.show()
    qt_app.processEvents()

    return frame, text_edit
