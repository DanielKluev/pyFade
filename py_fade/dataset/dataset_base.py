"""Shared declarative base for all dataset ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from sqlalchemy.orm import declarative_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase

dataset_base = declarative_base()

# Generic type for SQLAlchemy model classes
T = TypeVar('T', bound=dataset_base)


def ensure_dataset_session(dataset: DatasetDatabase) -> None:
    """
    Ensure that the dataset has an active session.

    Raises RuntimeError if the dataset session is not initialized.
    """
    if not dataset.session:
        raise RuntimeError(
            "Dataset session is not initialized. Call dataset.initialize() first."
        )


def get_session_with_assertion(dataset: DatasetDatabase):
    """
    Get the dataset session with proper assertion for type narrowing.

    Returns the session after ensuring it exists and asserting it's not None.
    This helper reduces duplicate session handling code across models.
    """
    ensure_dataset_session(dataset)
    session = dataset.session
    assert session is not None  # Narrow type for static analysis tools
    return session
