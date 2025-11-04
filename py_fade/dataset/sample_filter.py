"""
ORM model and helpers for complex sample filters.

Provides persistence and management of user-defined complex sample filters that allow
combining multiple filter rules (string search, tags, facets) with AND logic.
"""

import datetime
import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, desc
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


class SampleFilter(dataset_base):
    """
    Represents a user-defined complex filter for samples.

    A complex filter contains multiple filter rules that are evaluated with AND logic.
    Each rule can filter by string search, tag, or facet, and can optionally be negated.
    """

    __tablename__ = "sample_filters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    filter_rules: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON encoded list of rules
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)

    log = logging.getLogger("SampleFilter")

    @classmethod
    def get_by_name(cls, dataset: "DatasetDatabase", name: str) -> "SampleFilter | None":
        """
        Retrieve a SampleFilter by its name.

        Args:
            dataset: The dataset database instance
            name: The filter name to search for

        Returns:
            SampleFilter instance if found, None otherwise
        """
        session = dataset.get_session()
        normalized = name.strip()
        if not normalized:
            return None
        return session.query(cls).filter_by(name=normalized).first()

    @classmethod
    def get_by_id(cls, dataset: "DatasetDatabase", filter_id: int) -> "SampleFilter | None":
        """
        Retrieve a SampleFilter by its ID.

        Args:
            dataset: The dataset database instance
            filter_id: The filter ID to search for

        Returns:
            SampleFilter instance if found, None otherwise
        """
        session = dataset.get_session()
        return session.query(cls).filter_by(id=filter_id).first()

    @classmethod
    def get_all(cls, dataset: "DatasetDatabase", order_by_date: bool = True) -> list["SampleFilter"]:
        """
        Retrieve all sample filters from the dataset.

        Args:
            dataset: The dataset database instance
            order_by_date: If True, order by date_created descending (newest first)

        Returns:
            List of all SampleFilter instances
        """
        session = dataset.get_session()
        query = session.query(cls)
        if order_by_date:
            query = query.order_by(desc(cls.date_created))
        return list(query.all())

    @classmethod
    def create(cls, dataset: "DatasetDatabase", name: str, description: str = "", filter_rules: list[dict] | None = None) -> "SampleFilter":
        """
        Create a new sample filter ensuring the name is unique.

        Args:
            dataset: The dataset database instance
            name: Unique name for the filter
            description: Optional description of the filter
            filter_rules: Optional list of filter rule dictionaries

        Returns:
            The newly created SampleFilter instance

        Raises:
            ValueError: If the name is not unique or if any field is invalid
        """
        session = dataset.get_session()

        # Validate name is unique
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Filter name cannot be empty")

        existing = session.query(cls).filter_by(name=normalized_name).first()
        if existing:
            raise ValueError(f"A filter with name '{normalized_name}' already exists")

        # Create the new filter
        rules_json = json.dumps(filter_rules or [])
        new_filter = cls(
            name=normalized_name,
            description=description.strip(),
            filter_rules=rules_json,
            date_created=datetime.datetime.now(),
        )

        session.add(new_filter)
        session.commit()
        cls.log.info("Created new sample filter: %s", normalized_name)
        return new_filter

    def update(self, dataset: "DatasetDatabase", name: str | None = None, description: str | None = None,
               filter_rules: list[dict] | None = None) -> None:
        """
        Update the filter's properties.

        Args:
            dataset: The dataset database instance
            name: New name (must be unique if provided)
            description: New description
            filter_rules: New filter rules list

        Raises:
            ValueError: If the new name is not unique or if any field is invalid
        """
        session = dataset.get_session()

        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                raise ValueError("Filter name cannot be empty")

            # Check if new name conflicts with existing filters
            if normalized_name != self.name:
                existing = session.query(SampleFilter).filter_by(name=normalized_name).first()
                if existing:
                    raise ValueError(f"A filter with name '{normalized_name}' already exists")
                self.name = normalized_name

        if description is not None:
            self.description = description.strip()

        if filter_rules is not None:
            self.filter_rules = json.dumps(filter_rules)

        session.commit()
        self.log.info("Updated sample filter: %s", self.name)

    def delete(self, dataset: "DatasetDatabase") -> None:
        """
        Delete this filter from the database.

        Args:
            dataset: The dataset database instance
        """
        session = dataset.get_session()
        session.delete(self)
        session.commit()
        self.log.info("Deleted sample filter: %s", self.name)

    def get_rules(self) -> list[dict]:
        """
        Get the filter rules as a list of dictionaries.

        Returns:
            List of filter rule dictionaries
        """
        try:
            return json.loads(self.filter_rules)
        except json.JSONDecodeError:
            self.log.error("Failed to parse filter rules JSON for filter: %s", self.name)
            return []

    def set_rules(self, rules: list[dict]) -> None:
        """
        Set the filter rules from a list of dictionaries.

        This method does NOT commit the changes to the database.
        Call dataset.commit() after setting rules to persist changes.

        Args:
            rules: List of filter rule dictionaries
        """
        self.filter_rules = json.dumps(rules)
