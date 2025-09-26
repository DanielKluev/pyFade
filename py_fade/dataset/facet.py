import datetime
from sqlalchemy import Integer, String, desc
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime
from py_fade.dataset.dataset_base import dataset_base

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase

class Facet(dataset_base):
    """
    Represents a single Facet item in the dataset.
    """
    __tablename__ = "facets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)

    @classmethod
    def get_by_name(cls, dataset: "DatasetDatabase", name: str) -> "Facet | None":
        """
        Retrieve a Facet by its name.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        return dataset.session.query(cls).filter_by(name=name).first()

    @classmethod
    def get_by_id(cls, dataset: "DatasetDatabase", facet_id: int) -> "Facet | None":
        """
        Retrieve a Facet by its ID.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        return dataset.session.query(cls).filter_by(id=facet_id).first()

    @classmethod
    def get_all(cls, dataset: "DatasetDatabase", order_by_date: bool = True):
        """
        Retrieve all facets from the dataset.
        
        Args:
            dataset: The dataset database instance
            order_by_date: If True, order by date_created descending (newest first)
        
        Returns:
            List of all facets
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        query = dataset.session.query(cls)
        if order_by_date:
            query = query.order_by(desc(cls.date_created))
        
        return query.all()

    @classmethod
    def create(cls, dataset: "DatasetDatabase", name: str, description: str) -> "Facet":
        """
        Create a new facet and add it to the database.
        
        Args:
            dataset: The dataset database instance
            name: The name of the facet (must be unique)
            description: The description of the facet
        
        Returns:
            The created facet
            
        Raises:
            ValueError: If a facet with the same name already exists
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        # Check if facet with this name already exists
        existing_facet = cls.get_by_name(dataset, name)
        if existing_facet:
            raise ValueError(f"A facet with the name '{name}' already exists.")
        
        facet = cls(
            name=name.strip(),
            description=description.strip(),
            total_samples=0,
            date_created=datetime.datetime.now()
        )
        
        dataset.session.add(facet)
        return facet

    def update(self, dataset: "DatasetDatabase", name: str | None = None, description: str | None = None):
        """
        Update the facet's properties.
        
        Args:
            dataset: The dataset database instance
            name: New name for the facet (optional)
            description: New description for the facet (optional)
            
        Raises:
            ValueError: If the new name already exists for another facet
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        if name is not None and name.strip() != self.name:
            # Check if another facet with this name exists
            existing_facet = self.get_by_name(dataset, name.strip())
            if existing_facet and existing_facet.id != self.id:
                raise ValueError(f"A facet with the name '{name}' already exists.")
            self.name = name.strip()
        
        if description is not None:
            self.description = description.strip()

    def delete(self, dataset: "DatasetDatabase"):
        """
        Delete this facet from the database.
        
        Args:
            dataset: The dataset database instance
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        dataset.session.delete(self)

    def __str__(self) -> str:
        """String representation of the facet."""
        return f"Facet(id={self.id}, name='{self.name}', samples={self.total_samples})"

    def __repr__(self) -> str:
        """Detailed string representation of the facet."""
        return f"Facet(id={self.id}, name='{self.name}', description='{self.description[:50]}...', total_samples={self.total_samples}, date_created={self.date_created})"