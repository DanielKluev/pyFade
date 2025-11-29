"""
Widget component for displaying and managing sample image attachments.

Displays list of attached images with:
- Filename display
- Thumbnail preview on hover
- Click to open preview dialog
- Remove button for unsaved samples

Key classes: `WidgetSampleImages`
"""

import logging
import pathlib
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon

if TYPE_CHECKING:
    from py_fade.dataset.sample_image import SampleImage


class ImagePreviewDialog(QDialog):
    """
    Dialog for previewing an attached image at full size.

    Shows the image in a scrollable area with the filename in the title.
    """

    def __init__(self, file_path: str, filename: str, parent: QWidget | None = None):
        """
        Initialize the image preview dialog.

        Args:
            file_path: Path to the image file
            filename: Name of the image file for display in title
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger("ImagePreviewDialog")
        self.file_path = file_path
        self.filename = filename

        self.setup_ui()
        self.load_image()

    def setup_ui(self) -> None:
        """
        Set up the dialog UI.
        """
        self.setWindowTitle(f"Image Preview: {self.filename}")
        self.setMinimumSize(400, 300)
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # Scroll area for image
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        # Image label
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)

        layout.addWidget(self.scroll_area)

        # File path label
        self.path_label = QLabel(f"Path: {self.file_path}", self)
        self.path_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.path_label)

    def load_image(self) -> None:
        """
        Load and display the image.
        """
        path = pathlib.Path(self.file_path)
        if not path.exists():
            self.image_label.setText(f"Image file not found:\n{self.file_path}")
            self.image_label.setStyleSheet("color: red;")
            self.log.warning("Image file not found: %s", self.file_path)
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_label.setText(f"Could not load image:\n{self.file_path}")
            self.image_label.setStyleSheet("color: red;")
            self.log.warning("Could not load image: %s", self.file_path)
            return

        # Scale image to fit dialog while maintaining aspect ratio
        max_size = QSize(self.width() - 40, self.height() - 80)
        scaled_pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)


class ImageAttachmentItem(QWidget):
    """
    Widget for a single image attachment in the list.

    Shows filename, provides thumbnail on hover, and has remove button.
    """

    remove_clicked = pyqtSignal(object)  # Emits the SampleImage or file_path when remove is clicked
    preview_clicked = pyqtSignal(str, str)  # Emits (file_path, filename) when clicked for preview

    def __init__(self, file_path: str, filename: str, removable: bool = True, sample_image: "SampleImage | None" = None,
                 parent: QWidget | None = None):
        """
        Initialize the image attachment item.

        Args:
            file_path: Path to the image file
            filename: Name of the image file
            removable: Whether the remove button should be shown
            sample_image: Optional SampleImage instance (for saved images)
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger("ImageAttachmentItem")
        self.file_path = file_path
        self.filename = filename
        self.removable = removable
        self.sample_image = sample_image
        self._thumbnail_pixmap: QPixmap | None = None

        self.setup_ui()

    def setup_ui(self) -> None:
        """
        Set up the item UI.
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Image icon
        self.icon_button = QPushButtonWithIcon("image", "", parent=self, icon_size=16, button_size=24)
        self.icon_button.setToolTip("Click to preview")
        self.icon_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_button.clicked.connect(self._on_preview_clicked)
        layout.addWidget(self.icon_button)

        # Filename label (clickable for preview)
        self.filename_label = QLabel(self.filename, self)
        self.filename_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filename_label.setStyleSheet("color: #007bff; text-decoration: underline;")
        self.filename_label.mousePressEvent = lambda _: self._on_preview_clicked()
        layout.addWidget(self.filename_label, stretch=1)

        # Remove button (only if removable)
        if self.removable:
            self.remove_button = QPushButtonWithIcon("close", "", parent=self, icon_size=14, button_size=20)
            self.remove_button.setToolTip("Remove image")
            self.remove_button.clicked.connect(self._on_remove_clicked)
            layout.addWidget(self.remove_button)

        # Set up hover for thumbnail preview
        self.setMouseTracking(True)

    def enterEvent(self, event) -> None:  # pylint: disable=invalid-name
        """
        Show thumbnail tooltip on mouse enter.
        """
        super().enterEvent(event)
        self._show_thumbnail_tooltip()

    def _show_thumbnail_tooltip(self) -> None:
        """
        Display a thumbnail preview as a tooltip.
        """
        if self._thumbnail_pixmap is None:
            self._load_thumbnail()

        if self._thumbnail_pixmap and not self._thumbnail_pixmap.isNull():
            # Show thumbnail in tooltip (simple HTML image approach won't work, so just show filename)
            # Instead, we rely on preview dialog for actual viewing
            QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), f"Click to preview: {self.filename}", self)

    def _load_thumbnail(self) -> None:
        """
        Load the thumbnail pixmap.
        """
        path = pathlib.Path(self.file_path)
        if not path.exists():
            self.log.debug("Image file not found for thumbnail: %s", self.file_path)
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.log.debug("Could not load thumbnail: %s", self.file_path)
            return

        # Scale to thumbnail size
        self._thumbnail_pixmap = pixmap.scaled(QSize(200, 200), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)

    def _on_preview_clicked(self) -> None:
        """
        Handle preview click.
        """
        self.preview_clicked.emit(self.file_path, self.filename)

    def _on_remove_clicked(self) -> None:
        """
        Handle remove button click.
        """
        if self.sample_image:
            self.remove_clicked.emit(self.sample_image)
        else:
            self.remove_clicked.emit(self.file_path)


class WidgetSampleImages(QWidget):
    """
    Widget for managing sample image attachments.

    Displays a list of attached images with options to add and remove images.
    The add button is only shown when the sample is not saved.
    """

    images_changed = pyqtSignal()  # Emitted when images are added or removed

    def __init__(self, parent: QWidget | None = None):
        """
        Initialize the sample images widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger("WidgetSampleImages")
        self._pending_images: list[str] = []  # File paths of images to be saved with sample
        self._saved_images: list["SampleImage"] = []  # SampleImage instances from database
        self._is_saved_sample: bool = False  # Whether the sample is saved

        self.setup_ui()

    def setup_ui(self) -> None:
        """
        Set up the widget UI.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header with label and add button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)

        self.images_label = QLabel("Images:", self)
        self.images_label.setMinimumWidth(80)
        header_layout.addWidget(self.images_label)

        self.add_image_button = QPushButtonWithIcon("add_image", "", parent=self, icon_size=20, button_size=32)
        self.add_image_button.setToolTip("Add Image")
        self.add_image_button.clicked.connect(self._on_add_image_clicked)
        header_layout.addWidget(self.add_image_button)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Images list container
        self.images_container = QWidget(self)
        self.images_layout = QVBoxLayout(self.images_container)
        self.images_layout.setContentsMargins(0, 0, 0, 0)
        self.images_layout.setSpacing(2)

        # Placeholder label
        self.placeholder_label = QLabel("<i>No images attached</i>", self)
        self.placeholder_label.setStyleSheet("color: #888; padding: 4px;")
        self.images_layout.addWidget(self.placeholder_label)

        layout.addWidget(self.images_container)

        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    def set_sample_saved(self, is_saved: bool) -> None:
        """
        Set whether the sample is saved.

        When sample is saved, remove buttons are hidden.

        Args:
            is_saved: Whether the sample is saved
        """
        self._is_saved_sample = is_saved
        self.add_image_button.setVisible(not is_saved)
        self._refresh_images_display()

    def set_saved_images(self, images: list["SampleImage"]) -> None:
        """
        Set the list of saved images to display.

        Args:
            images: List of SampleImage instances from database
        """
        self._saved_images = images.copy()
        self._refresh_images_display()

    def set_pending_images(self, file_paths: list[str]) -> None:
        """
        Set the list of pending images (for unsaved samples).

        Args:
            file_paths: List of file paths
        """
        self._pending_images = file_paths.copy()
        self._refresh_images_display()

    def get_pending_images(self) -> list[str]:
        """
        Get the list of pending image file paths.

        Returns:
            List of file paths that haven't been saved to database yet
        """
        return self._pending_images.copy()

    def clear(self) -> None:
        """
        Clear all images.
        """
        self._pending_images.clear()
        self._saved_images.clear()
        self._refresh_images_display()

    def _refresh_images_display(self) -> None:
        """
        Refresh the display of images.
        """
        # Remove all existing items except placeholder
        while self.images_layout.count() > 1:
            item = self.images_layout.takeAt(1)
            if item and item.widget():
                item.widget().deleteLater()

        # Check if we have any images
        has_images = bool(self._saved_images) or bool(self._pending_images)

        if not has_images:
            self.placeholder_label.setVisible(True)
            return

        self.placeholder_label.setVisible(False)

        # Add saved images
        for sample_image in self._saved_images:
            item = ImageAttachmentItem(
                file_path=sample_image.file_path,
                filename=sample_image.filename,
                removable=not self._is_saved_sample,
                sample_image=sample_image,
                parent=self,
            )
            item.remove_clicked.connect(self._on_saved_image_remove)
            item.preview_clicked.connect(self._on_image_preview)
            self.images_layout.addWidget(item)

        # Add pending images
        for file_path in self._pending_images:
            filename = pathlib.Path(file_path).name
            item = ImageAttachmentItem(
                file_path=file_path,
                filename=filename,
                removable=True,
                sample_image=None,
                parent=self,
            )
            item.remove_clicked.connect(self._on_pending_image_remove)
            item.preview_clicked.connect(self._on_image_preview)
            self.images_layout.addWidget(item)

    def _on_add_image_clicked(self) -> None:
        """
        Handle add image button click.
        """
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        file_dialog.setWindowTitle("Select Images to Attach")

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            for file_path in selected_files:
                if file_path not in self._pending_images:
                    self._pending_images.append(file_path)
                    self.log.debug("Added pending image: %s", file_path)

            self._refresh_images_display()
            self.images_changed.emit()

    def _on_pending_image_remove(self, file_path: str) -> None:
        """
        Handle removal of a pending image.

        Args:
            file_path: Path of the image to remove
        """
        if file_path in self._pending_images:
            self._pending_images.remove(file_path)
            self.log.debug("Removed pending image: %s", file_path)
            self._refresh_images_display()
            self.images_changed.emit()

    def _on_saved_image_remove(self, sample_image: "SampleImage") -> None:
        """
        Handle removal of a saved image.

        Note: This should only be called for unsaved samples that have
        images from a previous session (e.g., copied samples).

        Args:
            sample_image: SampleImage instance to remove
        """
        if sample_image in self._saved_images:
            self._saved_images.remove(sample_image)
            self.log.debug("Removed saved image from display: %s", sample_image.filename)
            self._refresh_images_display()
            self.images_changed.emit()

    def _on_image_preview(self, file_path: str, filename: str) -> None:
        """
        Handle image preview request.

        Args:
            file_path: Path to the image file
            filename: Name of the image file
        """
        dialog = ImagePreviewDialog(file_path, filename, parent=self)
        dialog.exec()

    def has_images(self) -> bool:
        """
        Check if there are any images (saved or pending).

        Returns:
            True if there are any images, False otherwise
        """
        return bool(self._saved_images) or bool(self._pending_images)
