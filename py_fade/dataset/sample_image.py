"""
Association model for storing image file path references attached to samples.

This module defines the SampleImage model that stores image file paths associated
with samples. Images are not stored in the database, only their file paths are kept.

Key classes: `SampleImage`
"""

import datetime
import logging
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from py_fade.dataset.dataset_base import dataset_base

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.sample import Sample


class SampleImage(dataset_base):
    """
    Stores image file path references attached to samples.

    This model represents a one-to-many relationship between samples and images.
    Each sample can have multiple image attachments. Images are not stored
    in the database - only the file path reference is kept.
    """

    __tablename__ = "sample_images"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)

    # Relationships
    sample: Mapped["Sample"] = relationship("Sample", back_populates="images")

    log = logging.getLogger("SampleImage")

    @classmethod
    def create(cls, dataset: "DatasetDatabase", sample: "Sample", file_path: str) -> "SampleImage":
        """
        Create a new sample-image association.

        Returns the created SampleImage instance.

        Args:
            dataset: The dataset database instance
            sample: The sample to attach the image to
            file_path: The file path to the image file

        Returns:
            The created SampleImage instance

        Raises:
            ValueError: If the file path is empty or the image is already attached
        """
        import pathlib  # pylint: disable=import-outside-toplevel
        session = dataset.get_session()

        if not file_path or not file_path.strip():
            raise ValueError("Image file path cannot be empty.")

        path = pathlib.Path(file_path)
        filename = path.name

        # Check if this exact file path is already attached to this sample
        existing = session.query(cls).filter_by(sample_id=sample.id, file_path=str(path)).first()
        if existing:
            raise ValueError(f"Image '{filename}' is already attached to sample {sample.id}.")

        sample_image = cls(
            sample_id=sample.id,
            file_path=str(path),
            filename=filename,
            date_created=datetime.datetime.now(),
        )

        session.add(sample_image)
        cls.log.debug("Created sample-image association: sample_id=%s, file_path=%s", sample.id, file_path)
        return sample_image

    @classmethod
    def get_by_id(cls, dataset: "DatasetDatabase", image_id: int) -> "SampleImage | None":
        """
        Get a sample image by its ID.

        Args:
            dataset: The dataset database instance
            image_id: The ID of the sample image

        Returns:
            The SampleImage instance or None if not found
        """
        session = dataset.get_session()
        return session.query(cls).filter_by(id=image_id).first()

    @classmethod
    def get_for_sample(cls, dataset: "DatasetDatabase", sample: "Sample") -> List["SampleImage"]:
        """
        Get all images attached to a sample.

        Args:
            dataset: The dataset database instance
            sample: The sample to get images for

        Returns:
            List of SampleImage instances attached to the sample
        """
        session = dataset.get_session()
        return list(session.query(cls).filter_by(sample_id=sample.id).order_by(cls.date_created).all())

    def delete(self, dataset: "DatasetDatabase") -> None:
        """
        Remove the image attachment from the sample.

        Args:
            dataset: The dataset database instance
        """
        session = dataset.get_session()
        session.delete(self)
        self.log.debug("Deleted sample-image: id=%s, sample_id=%s, file_path=%s", self.id, self.sample_id, self.file_path)

    def file_exists(self) -> bool:
        """
        Check if the image file exists at the stored file path.

        Returns:
            True if the file exists, False otherwise
        """
        import pathlib  # pylint: disable=import-outside-toplevel
        return pathlib.Path(self.file_path).exists()

    def __repr__(self) -> str:
        return (f"SampleImage(id={self.id}, sample_id={self.sample_id}, "
                f"filename='{self.filename}', file_path='{self.file_path}')")
