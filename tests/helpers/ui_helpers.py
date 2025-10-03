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
