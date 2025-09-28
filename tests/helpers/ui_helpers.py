"""
UI testing utilities and helpers for GUI components.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    import pytest


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
