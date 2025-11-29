"""
Test suite for SampleImage model operations.

Tests core functionality of sample image attachments including:
- Creating image attachments for samples
- Preventing duplicate image attachments
- Deleting image attachments
- Sample image management methods (add_image, remove_image, get_images, has_images)

Edge cases covered:
- Duplicate image attachments
- Empty file paths
- Removing images not attached to sample
- Multiple images per sample
- Cascade delete when sample is deleted
"""
from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.sample import Sample
from py_fade.dataset.sample_image import SampleImage
from py_fade.dataset.prompt import PromptRevision
# Import all models to ensure proper table creation
from py_fade.dataset.facet import Facet  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.completion import PromptCompletion  # noqa: F401 pylint: disable=unused-import

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def test_create_sample_image(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test creating a sample-image attachment.

    Verifies that image attachments can be created for samples.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a test image file path
    test_image = tmp_path / "test_image.png"
    test_image.touch()

    # Create image attachment
    sample_image = SampleImage.create(temp_dataset, sample, str(test_image))
    temp_dataset.commit()

    assert sample_image.id is not None
    assert sample_image.sample_id == sample.id
    assert sample_image.file_path == str(test_image)
    assert sample_image.filename == "test_image.png"
    assert sample_image.date_created is not None


def test_create_duplicate_image_raises_error(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test that creating a duplicate sample-image attachment raises ValueError.

    Edge case: attempting to attach the same image twice should fail.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a test image file path
    test_image = tmp_path / "test_image.png"
    test_image.touch()

    # Create first image attachment
    SampleImage.create(temp_dataset, sample, str(test_image))
    temp_dataset.commit()

    # Attempt to create duplicate image attachment
    with pytest.raises(ValueError, match="already attached"):
        SampleImage.create(temp_dataset, sample, str(test_image))


def test_create_image_empty_path_raises_error(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that creating an image with empty path raises ValueError.

    Edge case: empty file paths should be rejected.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Attempt to create image with empty path
    with pytest.raises(ValueError, match="cannot be empty"):
        SampleImage.create(temp_dataset, sample, "")


def test_delete_sample_image(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test deleting a sample-image attachment.

    Verifies that image attachments can be deleted.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a test image file path
    test_image = tmp_path / "test_image.png"
    test_image.touch()

    # Create image attachment
    sample_image = SampleImage.create(temp_dataset, sample, str(test_image))
    temp_dataset.commit()
    image_id = sample_image.id

    # Delete the image attachment
    sample_image.delete(temp_dataset)
    temp_dataset.commit()

    # Verify image is deleted
    deleted = SampleImage.get_by_id(temp_dataset, image_id)
    assert deleted is None


def test_get_images_for_sample(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test getting all images for a sample.

    Verifies that all images attached to a sample can be retrieved.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create test image files
    test_image1 = tmp_path / "image1.png"
    test_image2 = tmp_path / "image2.jpg"
    test_image3 = tmp_path / "image3.gif"
    test_image1.touch()
    test_image2.touch()
    test_image3.touch()

    # Create image attachments
    SampleImage.create(temp_dataset, sample, str(test_image1))
    SampleImage.create(temp_dataset, sample, str(test_image2))
    SampleImage.create(temp_dataset, sample, str(test_image3))
    temp_dataset.commit()

    # Get all images for sample
    images = SampleImage.get_for_sample(temp_dataset, sample)

    assert len(images) == 3
    filenames = [img.filename for img in images]
    assert "image1.png" in filenames
    assert "image2.jpg" in filenames
    assert "image3.gif" in filenames


def test_get_images_empty(temp_dataset: "DatasetDatabase") -> None:
    """
    Test getting images for a sample with no images.

    Edge case: sample without images should return empty list.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Get images (should be empty)
    images = SampleImage.get_for_sample(temp_dataset, sample)

    assert len(images) == 0


def test_sample_add_image(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test adding an image to a sample using Sample.add_image method.

    Verifies that images can be added through the Sample model.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a test image file path
    test_image = tmp_path / "test_image.png"
    test_image.touch()

    # Add image to sample
    sample_image = sample.add_image(temp_dataset, str(test_image))
    temp_dataset.commit()

    assert sample_image.sample_id == sample.id
    assert sample_image.filename == "test_image.png"


def test_sample_remove_image(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test removing an image from a sample using Sample.remove_image method.

    Verifies that images can be removed through the Sample model.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a test image file path
    test_image = tmp_path / "test_image.png"
    test_image.touch()

    # Add image to sample
    sample_image = sample.add_image(temp_dataset, str(test_image))
    temp_dataset.commit()
    image_id = sample_image.id

    # Remove image from sample
    sample.remove_image(temp_dataset, sample_image)
    temp_dataset.commit()

    # Verify image is deleted
    deleted = SampleImage.get_by_id(temp_dataset, image_id)
    assert deleted is None


def test_sample_remove_image_wrong_sample_raises_error(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test that removing an image attached to a different sample raises ValueError.

    Edge case: attempting to remove an image from a sample it's not attached to should fail.
    """
    # Create two samples
    prompt_revision1 = PromptRevision.get_or_create(temp_dataset, "Test prompt 1", 2048, 512)
    sample1 = Sample.create_if_unique(temp_dataset, "Sample 1", prompt_revision1)

    prompt_revision2 = PromptRevision.get_or_create(temp_dataset, "Test prompt 2", 2048, 512)
    sample2 = Sample.create_if_unique(temp_dataset, "Sample 2", prompt_revision2)
    temp_dataset.commit()

    # Create a test image file and attach to sample1
    test_image = tmp_path / "test_image.png"
    test_image.touch()
    sample_image = sample1.add_image(temp_dataset, str(test_image))
    temp_dataset.commit()

    # Attempt to remove image from sample2 (wrong sample)
    with pytest.raises(ValueError, match="not attached"):
        sample2.remove_image(temp_dataset, sample_image)


def test_sample_get_images(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test retrieving all images for a sample using Sample.get_images method.

    Verifies that all images can be retrieved through the Sample model.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create test image files and attach them
    test_image1 = tmp_path / "image1.png"
    test_image2 = tmp_path / "image2.jpg"
    test_image1.touch()
    test_image2.touch()

    sample.add_image(temp_dataset, str(test_image1))
    sample.add_image(temp_dataset, str(test_image2))
    temp_dataset.commit()

    # Get images through Sample method
    images = sample.get_images(temp_dataset)

    assert len(images) == 2


def test_sample_has_images(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test checking if a sample has images using Sample.has_images method.

    Verifies that has_images correctly reports image attachment status.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Initially no images
    assert sample.has_images() is False

    # Create a test image file and attach it
    test_image = tmp_path / "test_image.png"
    test_image.touch()
    sample.add_image(temp_dataset, str(test_image))
    temp_dataset.commit()

    # Now has images
    assert sample.has_images() is True


def test_image_file_exists(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test checking if image file exists at the stored path.

    Verifies that file_exists correctly reports whether the file exists.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a test image file
    test_image = tmp_path / "test_image.png"
    test_image.touch()

    # Attach the image
    sample_image = SampleImage.create(temp_dataset, sample, str(test_image))
    temp_dataset.commit()

    # File exists
    assert sample_image.file_exists() is True

    # Delete the file
    test_image.unlink()

    # File no longer exists
    assert sample_image.file_exists() is False


def test_cascade_delete_sample_deletes_images(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test that deleting a sample cascades to delete its image attachments.

    Verifies cascade behavior for sample deletion.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create test image files and attach them
    test_image1 = tmp_path / "image1.png"
    test_image2 = tmp_path / "image2.jpg"
    test_image1.touch()
    test_image2.touch()

    image1 = sample.add_image(temp_dataset, str(test_image1))
    image2 = sample.add_image(temp_dataset, str(test_image2))
    temp_dataset.commit()

    image1_id = image1.id
    image2_id = image2.id

    # Verify images exist
    assert SampleImage.get_by_id(temp_dataset, image1_id) is not None
    assert SampleImage.get_by_id(temp_dataset, image2_id) is not None

    # Delete sample
    session = temp_dataset.get_session()
    session.delete(sample)
    temp_dataset.commit()

    # Verify images are deleted (cascade)
    assert SampleImage.get_by_id(temp_dataset, image1_id) is None
    assert SampleImage.get_by_id(temp_dataset, image2_id) is None


def test_multiple_images_per_sample(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test that a sample can have multiple image attachments.

    Verifies one-to-many relationship allows multiple images per sample.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create multiple test image files
    for i in range(5):
        test_image = tmp_path / f"image{i}.png"
        test_image.touch()
        sample.add_image(temp_dataset, str(test_image))

    temp_dataset.commit()

    # Verify all images are attached
    images = sample.get_images(temp_dataset)
    assert len(images) == 5


def test_image_preserves_original_path(temp_dataset: "DatasetDatabase", tmp_path: pathlib.Path) -> None:
    """
    Test that the original file path is preserved.

    Verifies that file paths with subdirectories are stored correctly.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a test image in a subdirectory
    subdir = tmp_path / "subdir" / "nested"
    subdir.mkdir(parents=True)
    test_image = subdir / "test_image.png"
    test_image.touch()

    # Attach the image
    sample_image = sample.add_image(temp_dataset, str(test_image))
    temp_dataset.commit()

    # Verify path and filename
    assert test_image.name in sample_image.file_path
    assert sample_image.filename == "test_image.png"
    assert "subdir" in sample_image.file_path
