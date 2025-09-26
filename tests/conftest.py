"""Pytest fixtures for GUI and dataset tests."""
# pylint: disable=redefined-outer-name,unused-argument,import-outside-toplevel
from __future__ import annotations

import logging
import os
import pathlib

from collections.abc import Generator
from typing import TYPE_CHECKING, cast

import pytest
from PyQt6.QtWidgets import QApplication

## MUST keep it before any other py_fade imports, as they may rely on path changes.
from py_fade.features_checker import SUPPORTED_FEATURES  # pylint: disable=unused-import # Handle fragile imports first.

from py_fade.dataset.dataset import DatasetDatabase

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


@pytest.fixture(scope="session", autouse=True)
def _configure_logging() -> None:
    """Ensure a predictable logging setup during the test session."""
    logging.basicConfig(level=logging.INFO)


@pytest.fixture(scope="session")
def qt_app() -> Generator[QApplication, None, None]:
    """Provide a single QApplication instance running in offscreen mode."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = cast(QApplication, QApplication.instance() or QApplication([]))
    try:
        yield app
    finally:
        # Make sure pending events are processed before shutdown.
        app.processEvents()
        app.quit()


@pytest.fixture
def temp_dataset(tmp_path: pathlib.Path) -> Generator[DatasetDatabase, None, None]:
    """Create a throwaway SQLite-backed dataset."""
    db_path = tmp_path / "test_dataset.db"
    dataset = DatasetDatabase(db_path)
    dataset.initialize()
    try:
        yield dataset
    finally:
        dataset.dispose()


@pytest.fixture
def app_with_dataset(
    temp_dataset: DatasetDatabase,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    qt_app: QApplication,
) -> Generator["pyFadeApp", None, None]:
    """Instantiate a ``pyFadeApp`` that points at the temporary dataset."""
    from py_fade.app import pyFadeApp

    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

    config_path = fake_home / "config.yaml"
    app = pyFadeApp(config_path=config_path)
    app.current_dataset = temp_dataset
    try:
        yield app
    finally:
        if hasattr(app, "dataset_widget") and app.dataset_widget:
            app.dataset_widget.deleteLater()
        if hasattr(app, "launcher") and app.launcher:
            app.launcher.deleteLater()


@pytest.fixture(scope="session")
def ensure_google_icon_font(qt_app: QApplication) -> None:
    """Load the Google icon font once for all GUI tests."""
    from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font

    google_icon_font.load()
