"""Common imports, types, and utilities for GUI components."""

from collections.abc import Callable
from typing import Any

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.gui.components.widget_crud_form_base import CrudButtonStyles


def build_crud_button_styles(*, save_color: str) -> CrudButtonStyles:
    """Return the Material-inspired button style set for CRUD forms."""

    base_style = (
        "QPushButton { background-color: %s; color: white; padding: 8px 16px; }"
    )
    return CrudButtonStyles(
        save=base_style % save_color,
        cancel=base_style % "#757575",
        delete=base_style % "#d32f2f",
    )


def validate_entity_name(
    *,
    dataset: DatasetDatabase,
    name: str,
    current_entity_id: int | None,
    fetch_existing: Callable[[DatasetDatabase, str], Any | None],
    min_length: int,
    max_length: int,
    duplicate_message: str,
) -> list[str]:
    """Validate an entity name for emptiness, length, and uniqueness."""

    normalized = name.strip()
    if not normalized:
        return ["Name is required"]
    if len(normalized) < min_length:
        return [f"Name must be at least {min_length} characters"]
    if len(normalized) > max_length:
        return [f"Name must be less than {max_length} characters"]

    try:
        existing = fetch_existing(dataset, normalized)
    except (RuntimeError, ValueError) as exc:
        return [str(exc)]

    existing_id = getattr(existing, "id", None) if existing is not None else None
    if existing_id is not None and existing_id != current_entity_id:
        return [duplicate_message]
    return []


def validate_description(
    description: str,
    *,
    min_length: int,
    max_length: int,
    empty_message: str,
    short_message: str,
    long_message: str,
) -> list[str]:
    """Validate a text description according to project length constraints."""

    normalized = description.strip()
    if not normalized:
        return [empty_message]
    if len(normalized) < min_length:
        return [short_message]
    if len(normalized) > max_length:
        return [long_message]
    return []
