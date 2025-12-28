"""
Custom widget for displaying clickable facets in a sample.

Each facet is displayed as a clickable label that can trigger facet switching actions.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

if TYPE_CHECKING:
    from py_fade.dataset.facet import Facet


class ClickableFacetLabel(QLabel):
    """
    A clickable label representing a single facet.

    Emits a signal when clicked, allowing the user to perform actions on the facet.
    """

    clicked = pyqtSignal(object)  # Signal emitted when facet is clicked, passes Facet object

    def __init__(self, facet: "Facet", is_active: bool = False, parent: QWidget | None = None):
        """
        Initialize the clickable facet label.

        Args:
            facet: The facet to display
            is_active: Whether this is the currently active facet
            parent: Parent widget
        """
        super().__init__(parent)
        self.facet = facet
        self.log = logging.getLogger(self.__class__.__name__)

        # Set cursor to pointing hand
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Style the label
        if is_active:
            # Highlight active facet with bold and background color
            self.setStyleSheet("background-color: #4CAF50; color: white; padding: 2px 6px; "
                               "border-radius: 3px; font-weight: bold;")
        else:
            # Normal facet - clickable with hover effect
            self.setStyleSheet("padding: 2px 6px; border-radius: 3px; color: #0066cc; text-decoration: underline;")

        self.setText(facet.name)
        self.setToolTip(f"Click to switch, copy, or remove facet '{facet.name}'")

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """
        Handle mouse press event.

        Emits the clicked signal with the facet object.
        """
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.log.debug("Facet label clicked: %s", self.facet.name)
            self.clicked.emit(self.facet)
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        """
        Handle mouse enter event for hover effect.
        """
        # Add hover effect
        current_style = self.styleSheet()
        if "background-color: #4CAF50" not in current_style:
            # Only add hover for non-active facets
            self.setStyleSheet(current_style + " background-color: #e3f2fd;")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """
        Handle mouse leave event to remove hover effect.
        """
        # Remove hover effect
        if "background-color: #4CAF50" in self.styleSheet():
            # Active facet - restore active styling
            self.setStyleSheet("background-color: #4CAF50; color: white; padding: 2px 6px; "
                               "border-radius: 3px; font-weight: bold;")
        else:
            # Normal facet - restore normal styling
            self.setStyleSheet("padding: 2px 6px; border-radius: 3px; color: #0066cc; text-decoration: underline;")
        super().leaveEvent(event)


class ClickableFacetsWidget(QWidget):
    """
    Widget that displays a list of clickable facets.

    Each facet is a clickable label that emits a signal when clicked.
    """

    facet_clicked = pyqtSignal(object)  # Signal emitted when a facet is clicked

    def __init__(self, parent: QWidget | None = None):
        """
        Initialize the clickable facets widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.facet_labels: list[ClickableFacetLabel] = []

        # Create layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Placeholder label
        self.placeholder_label = QLabel("<i>No facets</i>")
        self.layout.addWidget(self.placeholder_label)

        # Style the widget
        self.setStyleSheet("background-color: #f5f5f5; border-radius: 4px;")
        self.setMinimumHeight(30)

    def set_facets(self, facets: list["Facet"], active_facet: "Facet | None" = None) -> None:
        """
        Update the displayed facets.

        Args:
            facets: List of facets to display
            active_facet: The currently active facet (will be highlighted)
        """
        # Clear existing labels
        for label in self.facet_labels:
            # Only disconnect signal if it's a ClickableFacetLabel
            if isinstance(label, ClickableFacetLabel):
                label.clicked.disconnect()
            self.layout.removeWidget(label)
            label.deleteLater()
        self.facet_labels.clear()

        # Hide or show placeholder
        if not facets:
            self.placeholder_label.setVisible(True)
            return

        self.placeholder_label.setVisible(False)

        # Create labels for each facet
        for i, facet in enumerate(facets):
            is_active = active_facet is not None and facet.id == active_facet.id
            label = ClickableFacetLabel(facet, is_active, self)
            label.clicked.connect(self._on_facet_clicked)
            self.facet_labels.append(label)
            self.layout.addWidget(label)

            # Add comma separator if not the last facet
            if i < len(facets) - 1:
                separator = QLabel(", ")
                self.layout.addWidget(separator)
                self.facet_labels.append(separator)  # Store separator to clean up later

        # Add stretch to push facets to the left
        self.layout.addStretch()

    def _on_facet_clicked(self, facet: "Facet") -> None:
        """
        Handle facet click event.

        Args:
            facet: The facet that was clicked
        """
        self.log.debug("Facet clicked in widget: %s", facet.name)
        self.facet_clicked.emit(facet)

    def set_placeholder_text(self, text: str) -> None:
        """
        Set the placeholder text shown when there are no facets.

        Args:
            text: The placeholder text to display
        """
        self.placeholder_label.setText(text)
