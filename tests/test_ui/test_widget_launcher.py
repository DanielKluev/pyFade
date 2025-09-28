"""
Test Widget Launcher test module.
"""
from __future__ import annotations

import os
import pathlib
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.features_checker import SUPPORTED_FEATURES
from py_fade.gui.widget_launcher import LauncherWidget, RecentDatasetInfo

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


@pytest.fixture
def launcher_app(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, qt_app) -> Generator[pyFadeApp, None, None]:
    """Create a pyFadeApp instance for launcher testing."""
    from py_fade.app import pyFadeApp

    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)

    config_path = fake_home / "config.yaml"
    app = pyFadeApp(config_path=config_path)
    try:
        yield app
    finally:
        if hasattr(app, "launcher") and app.launcher:
            app.launcher.deleteLater()
        if hasattr(app, "dataset_widget") and app.dataset_widget:
            app.dataset_widget.deleteLater()


def test_launcher_lists_sqlite_datasets_without_password(
    launcher_app: pyFadeApp,
    temp_dataset: DatasetDatabase,
    ensure_google_icon_font,
    qt_app,
) -> None:
    """Test that launcher correctly lists SQLite datasets without passwords."""
    launcher_app.config.recent_datasets = [str(temp_dataset.db_path)]

    launcher = LauncherWidget(None, launcher_app)
    qt_app.processEvents()

    assert launcher.list_widget.count() == 1

    item = launcher.list_widget.item(0)
    assert item is not None
    info = item.data(Qt.ItemDataRole.UserRole)
    assert isinstance(info, RecentDatasetInfo)
    assert info.db_type in {"sqlite", "unknown"}
    assert not launcher.password_frame.isVisible()

    launcher.deleteLater()


def test_launcher_warns_when_sqlcipher_missing(
    launcher_app: pyFadeApp,
    ensure_google_icon_font,
    qt_app,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Test that launcher shows appropriate warning when SQLCipher is missing for encrypted databases."""
    encrypted_path = tmp_path / "secure.db"
    encrypted_path.write_bytes(os.urandom(512))

    original_check = DatasetDatabase.check_db_type.__func__

    def fake_check(cls, db_path: str | pathlib.Path) -> str:
        if pathlib.Path(db_path) == encrypted_path:
            return "sqlcipher"
        return original_check(cls, db_path)

    monkeypatch.setattr(DatasetDatabase, "check_db_type", classmethod(fake_check))
    monkeypatch.setitem(SUPPORTED_FEATURES, "sqlcipher3", False)

    launcher_app.config.recent_datasets = [str(encrypted_path)]

    warning_calls: list[str] = []

    def fake_warning(parent, title: str, message: str) -> QMessageBox.StandardButton:
        warning_calls.append(message)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("py_fade.gui.widget_launcher.QMessageBox.warning", fake_warning)

    launcher = LauncherWidget(None, launcher_app)
    qt_app.processEvents()

    assert not launcher.password_frame.isHidden()
    assert not launcher.open_btn.isEnabled()

    launcher.open_selected()
    qt_app.processEvents()

    assert warning_calls, "Expected a warning when sqlcipher support is unavailable."

    launcher.deleteLater()


def test_launcher_validates_password_before_opening(
    launcher_app: pyFadeApp,
    ensure_google_icon_font,
    qt_app,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Test that launcher validates password before attempting to open encrypted databases."""
    encrypted_path = tmp_path / "secure.db"
    encrypted_path.write_bytes(os.urandom(1024))
    expected_password = "passw0rd"

    original_check = DatasetDatabase.check_db_type.__func__

    def fake_check(cls, db_path: str | pathlib.Path) -> str:
        if pathlib.Path(db_path) == encrypted_path:
            return "sqlcipher"
        return original_check(cls, db_path)

    monkeypatch.setattr(DatasetDatabase, "check_db_type", classmethod(fake_check))

    original_password = DatasetDatabase.check_password.__func__

    def fake_password_check(cls, db_path: str | pathlib.Path, password: str) -> bool:
        if pathlib.Path(db_path) == encrypted_path:
            return password == expected_password
        return original_password(cls, db_path, password)

    monkeypatch.setattr(DatasetDatabase, "check_password", classmethod(fake_password_check))
    monkeypatch.setitem(SUPPORTED_FEATURES, "sqlcipher3", True)

    launcher_app.config.recent_datasets = [str(encrypted_path)]

    open_calls: list[tuple[pathlib.Path, str]] = []

    def fake_open_dataset(path: pathlib.Path, password: str) -> None:
        open_calls.append((path, password))

    monkeypatch.setattr(launcher_app, "open_dataset", fake_open_dataset)

    critical_calls: list[str] = []

    def fake_critical(parent, title: str, message: str) -> QMessageBox.StandardButton:
        critical_calls.append(message)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("py_fade.gui.widget_launcher.QMessageBox.critical", fake_critical)

    launcher = LauncherWidget(None, launcher_app)
    qt_app.processEvents()

    assert not launcher.password_frame.isHidden()
    assert launcher.open_btn.isEnabled()

    launcher.pw_input.setText("wrong")
    launcher.open_selected()
    qt_app.processEvents()

    assert critical_calls, "Incorrect password should raise an error dialog."
    assert not open_calls

    launcher.pw_input.setText(expected_password)

    emitted: list[tuple[str, str]] = []
    launcher.open_dataset_requested.connect(lambda path, password: emitted.append((path, password)))

    launcher.open_selected()
    qt_app.processEvents()

    assert open_calls == [(encrypted_path, expected_password)]
    assert emitted and emitted[-1][1] == expected_password

    launcher.deleteLater()
