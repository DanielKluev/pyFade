"""
Helper utilities for creating common form field layouts.

Provides reusable functions for building form fields with consistent styling
and layout patterns across CRUD widgets.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)


def create_name_field_layout(parent: QGroupBox, placeholder: str, on_change: Callable) -> tuple[QVBoxLayout, QLineEdit]:
    """
    Create a name input field with standard layout and styling.

    Returns tuple of (container layout, line edit widget).
    """
    name_container = QVBoxLayout()
    name_label = QLabel("Name:", parent=parent)
    name_label.setStyleSheet("font-weight: bold;")
    name_field = QLineEdit(parent=parent)
    name_field.setPlaceholderText(placeholder)
    name_field.textChanged.connect(on_change)  # type: ignore[arg-type]
    name_container.addWidget(name_label)
    name_container.addWidget(name_field)
    return name_container, name_field


def create_description_field_layout(parent: QGroupBox, placeholder: str, max_height: int,
                                    on_change: Callable) -> tuple[QVBoxLayout, QPlainTextEdit]:
    """
    Create a description text field with standard layout and styling.

    Returns tuple of (container layout, plain text edit widget).
    """
    description_container = QVBoxLayout()
    description_label = QLabel("Description:", parent=parent)
    description_label.setStyleSheet("font-weight: bold;")
    description_field = QPlainTextEdit(parent=parent)
    description_field.setPlaceholderText(placeholder)
    description_field.setMaximumHeight(max_height)
    description_field.textChanged.connect(on_change)  # type: ignore[arg-type]
    description_container.addWidget(description_label)
    description_container.addWidget(description_field)
    return description_container, description_field


def create_readonly_field_layout(parent: QGroupBox, label_text: str, field: QLineEdit) -> QHBoxLayout:
    """
    Create a horizontal layout for a readonly field with label.

    Returns the container layout. The field must be pre-created and configured.
    """
    layout = QHBoxLayout()
    label = QLabel(label_text, parent=parent)
    label.setStyleSheet("font-weight: bold;")
    layout.addWidget(label)
    layout.addWidget(field)
    layout.addStretch()
    return layout
