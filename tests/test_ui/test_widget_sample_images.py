"""
Test suite for WidgetSampleImages component.

Tests core functionality of the image attachment widget:
- Widget initialization and setup
- Adding pending images
- Displaying saved images
- Removing images
- Has images check
- Interaction with save state

Uses PyQt6 and pytest-qt for widget testing.

Pylint:
 - Intentional use of ensure_google_icon_font fixture to load icon font before tests.
"""
# pylint: disable=unused-argument
from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QApplication

from py_fade.gui.components.widget_sample_images import (
    ImageAttachmentItem,
    WidgetSampleImages,
)

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


class TestWidgetSampleImages:
    """
    Tests for WidgetSampleImages component.
    """

    def test_widget_initialization(self, qt_app: QApplication, ensure_google_icon_font: None) -> None:
        """
        Test that the widget initializes correctly.

        Verifies that initial state has no images and add button is visible.
        """
        widget = WidgetSampleImages()
        widget.show()
        qt_app.processEvents()

        assert not widget.has_images()
        assert widget.add_image_button.isVisible()

    def test_set_sample_saved_hides_add_button(self, qt_app: QApplication, ensure_google_icon_font: None) -> None:
        """
        Test that setting sample as saved hides the add button.

        Verifies that saved samples cannot have images added.
        """
        widget = WidgetSampleImages()
        widget.show()
        qt_app.processEvents()

        # Initially add button is visible
        assert widget.add_image_button.isVisible()

        # Mark as saved
        widget.set_sample_saved(True)
        qt_app.processEvents()

        # Add button should be hidden
        assert not widget.add_image_button.isVisible()

    def test_set_pending_images(self, qt_app: QApplication, tmp_path: pathlib.Path, ensure_google_icon_font: None) -> None:
        """
        Test setting pending images.

        Verifies that pending images are displayed correctly.
        """
        # Create test image files
        test_image1 = tmp_path / "image1.png"
        test_image2 = tmp_path / "image2.jpg"
        test_image1.touch()
        test_image2.touch()

        widget = WidgetSampleImages()
        widget.show()
        qt_app.processEvents()

        # Set pending images
        widget.set_pending_images([str(test_image1), str(test_image2)])
        qt_app.processEvents()

        assert widget.has_images()
        pending = widget.get_pending_images()
        assert len(pending) == 2
        assert str(test_image1) in pending
        assert str(test_image2) in pending

    def test_clear_images(self, qt_app: QApplication, tmp_path: pathlib.Path, ensure_google_icon_font: None) -> None:
        """
        Test clearing all images.

        Verifies that clear removes all pending images.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        widget = WidgetSampleImages()
        widget.set_pending_images([str(test_image)])
        qt_app.processEvents()

        assert widget.has_images()

        widget.clear()
        qt_app.processEvents()

        assert not widget.has_images()
        assert widget.get_pending_images() == []

    def test_get_pending_images_returns_copy(self, qt_app: QApplication, tmp_path: pathlib.Path, ensure_google_icon_font: None) -> None:
        """
        Test that get_pending_images returns a copy.

        Verifies that modifications to returned list don't affect widget state.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        widget = WidgetSampleImages()
        widget.set_pending_images([str(test_image)])
        qt_app.processEvents()

        # Get pending images and modify
        pending = widget.get_pending_images()
        pending.append("extra_image.png")

        # Widget should still have only original image
        assert len(widget.get_pending_images()) == 1


class TestImageAttachmentItem:
    """
    Tests for ImageAttachmentItem component.
    """

    def test_item_creation(self, qt_app: QApplication, tmp_path: pathlib.Path, ensure_google_icon_font: None) -> None:
        """
        Test that image attachment item initializes correctly.

        Verifies that filename and path are stored correctly.
        """
        test_image = tmp_path / "test_image.png"
        test_image.touch()

        item = ImageAttachmentItem(
            file_path=str(test_image),
            filename="test_image.png",
            removable=True,
        )
        item.show()
        qt_app.processEvents()

        assert item.file_path == str(test_image)
        assert item.filename == "test_image.png"
        assert item.removable is True

    def test_item_with_remove_button(self, qt_app: QApplication, tmp_path: pathlib.Path, ensure_google_icon_font: None) -> None:
        """
        Test that removable item has remove button.

        Verifies that remove button is present when removable is True.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        item = ImageAttachmentItem(
            file_path=str(test_image),
            filename="test.png",
            removable=True,
        )
        item.show()
        qt_app.processEvents()

        assert hasattr(item, "remove_button")

    def test_item_without_remove_button(self, qt_app: QApplication, tmp_path: pathlib.Path, ensure_google_icon_font: None) -> None:
        """
        Test that non-removable item has no remove button.

        Verifies that remove button is not present when removable is False.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        item = ImageAttachmentItem(
            file_path=str(test_image),
            filename="test.png",
            removable=False,
        )
        item.show()
        qt_app.processEvents()

        assert not hasattr(item, "remove_button")

    def test_remove_signal_emitted(self, qt_app: QApplication, tmp_path: pathlib.Path, ensure_google_icon_font: None) -> None:
        """
        Test that remove signal is emitted when remove button is clicked.

        Verifies signal emission with file_path.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        item = ImageAttachmentItem(
            file_path=str(test_image),
            filename="test.png",
            removable=True,
        )
        item.show()
        qt_app.processEvents()

        # Track signal emission
        received_path = []
        item.remove_clicked.connect(received_path.append)

        # Click remove button
        item.remove_button.click()
        qt_app.processEvents()

        assert len(received_path) == 1
        assert received_path[0] == str(test_image)

    def test_preview_signal_emitted(self, qt_app: QApplication, tmp_path: pathlib.Path, ensure_google_icon_font: None) -> None:
        """
        Test that preview signal is emitted when icon is clicked.

        Verifies signal emission with file_path and filename.
        """
        test_image = tmp_path / "test.png"
        test_image.touch()

        item = ImageAttachmentItem(
            file_path=str(test_image),
            filename="test.png",
            removable=True,
        )
        item.show()
        qt_app.processEvents()

        # Track signal emission
        received_params = []
        item.preview_clicked.connect(lambda p, f: received_params.append((p, f)))

        # Click icon button
        item.icon_button.click()
        qt_app.processEvents()

        assert len(received_params) == 1
        assert received_params[0] == (str(test_image), "test.png")
