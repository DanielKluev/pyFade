"""
Dataset model helpers for tag entities.

Pylint:
 - Intentional duplication of ORM model attributes. Easier when each model class is fully visible.
"""
# pylint: disable=duplicate-code

import datetime
import logging
from typing import TYPE_CHECKING, List

from sqlalchemy import Integer, String, desc
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


class Tag(dataset_base):
    """
    Represents a user-defined tag applied to dataset objects.
    """

    DEFAULT_SCOPE = "both"
    ALLOWED_SCOPES = ("samples", "completions", DEFAULT_SCOPE)

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)
    scope: Mapped[str] = mapped_column(String, nullable=False, default=DEFAULT_SCOPE)

    log = logging.getLogger("Tag")

    @classmethod
    def normalize_scope(cls, scope: str | None) -> str:
        """
        Return a validated scope string, raising :class:`ValueError` if invalid.
        """

        candidate = (scope or cls.DEFAULT_SCOPE).strip().lower()
        if candidate not in cls.ALLOWED_SCOPES:
            raise ValueError(f"Tag scope must be one of {', '.join(cls.ALLOWED_SCOPES)} (received: {scope!r}).")
        return candidate

    @classmethod
    def get_by_name(cls, dataset: "DatasetDatabase", name: str) -> "Tag | None":
        """
        Return a tag matching *name* or ``None`` when not found.
        """

        session = dataset.get_session()
        normalized = name.strip()
        if not normalized:
            return None
        return session.query(cls).filter_by(name=normalized).first()

    @classmethod
    def get_by_id(cls, dataset: "DatasetDatabase", tag_id: int) -> "Tag | None":
        """
        Return the tag identified by *tag_id* or ``None`` when missing.
        """

        session = dataset.get_session()
        return session.query(cls).filter_by(id=tag_id).first()

    @classmethod
    def get_all(cls, dataset: "DatasetDatabase", order_by_date: bool = True) -> List["Tag"]:
        """
        Return the list of all tags in the dataset.
        """

        session = dataset.get_session()
        query = session.query(cls)
        if order_by_date:
            query = query.order_by(desc(cls.date_created))
        return list(query.all())

    @classmethod
    def create(cls, dataset: "DatasetDatabase", name: str, description: str, *, scope: str | None = None) -> "Tag":
        """
        Create a new tag ensuring the name is unique.

        Raises :class:`ValueError` if the name is not unique or if any field is invalid.
        """

        session = dataset.get_session()

        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Tag name cannot be empty.")

        normalized_description = description.strip()
        if not normalized_description:
            raise ValueError("Tag description cannot be empty.")

        existing = cls.get_by_name(dataset, normalized_name)
        if existing:
            raise ValueError(f"A tag with the name '{normalized_name}' already exists.")

        normalized_scope = cls.normalize_scope(scope)

        tag = cls(
            name=normalized_name,
            description=normalized_description,
            total_samples=0,
            date_created=datetime.datetime.now(),
            scope=normalized_scope,
        )

        session.add(tag)
        cls.log.debug("Created new tag candidate: %s", tag)
        return tag

    def update(self, dataset: "DatasetDatabase", *, name: str | None = None, description: str | None = None,
               scope: str | None = None) -> None:
        """
        Update the tag fields and keep the name unique across tags.
        """

        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                raise ValueError("Tag name cannot be empty.")
            if normalized_name != self.name:
                existing = self.get_by_name(dataset, normalized_name)
                if existing and existing.id != self.id:
                    raise ValueError(f"A tag with the name '{normalized_name}' already exists.")
                self.name = normalized_name

        if description is not None:
            normalized_description = description.strip()
            if not normalized_description:
                raise ValueError("Tag description cannot be empty.")
            self.description = normalized_description

        if scope is not None:
            normalized_scope = self.normalize_scope(scope)
            self.scope = normalized_scope

        self.log.debug("Updated tag %s", self)

    def delete(self, dataset: "DatasetDatabase") -> None:
        """
        Remove the tag from the dataset session.
        """

        session = dataset.get_session()
        session.delete(self)
        self.log.debug("Deleted tag %s", self)

    def __str__(self) -> str:
        return (f"Tag(id={self.id}, name='{self.name}', scope='{self.scope}', "
                f"samples={self.total_samples})")

    def __repr__(self) -> str:
        description_preview = self.description[:50]
        return (f"Tag(id={self.id}, name='{self.name}', description='{description_preview}', "
                f"scope='{self.scope}', total_samples={self.total_samples}, "
                f"date_created={self.date_created})")
