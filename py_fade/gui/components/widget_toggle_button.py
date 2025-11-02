"""
Reusable toggle button component with icon support.

This module provides a QPushButtonToggle widget that can be used as a compact toggle button
with visual feedback through border styling when toggled on/off.
"""

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QPushButton, QWidget

from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font


class QPushButtonToggle(QPushButton):
    """
    A compact toggle button with icon support and visual border feedback.

    This button changes its border style when toggled on/off, providing visual feedback
    to the user. It uses Google Material Symbols icons for compact representation.
    """

    toggled_state_changed = pyqtSignal(bool)  # Signal emitted when toggle state changes

    def __init__(self, icon_name: str, tooltip: str = "", *, parent: QWidget | None = None, icon_size: int = 20, button_size: int = 32):
        """
        Initialize the toggle button with an icon.

        Args:
            icon_name: Name of the Google Material Symbol icon to display
            tooltip: Tooltip text to show on hover
            parent: Parent widget
            icon_size: Size of the icon in pixels
            button_size: Size of the button widget in pixels
        """
        super().__init__(parent)
        self.log = logging.getLogger("QPushButtonToggle")
        self.icon_name = icon_name
        self._is_toggled = False

        # Set up the button appearance
        self.setIcon(google_icon_font.as_icon(icon_name, size=icon_size))
        self.setFixedSize(button_size, button_size)
        if tooltip:
            self.setToolTip(tooltip)

        # Connect click to toggle
        self.clicked.connect(self._on_clicked)

        # Apply initial styling
        self._update_style()

    def _on_clicked(self):
        """Handle button click by toggling state."""
        self._is_toggled = not self._is_toggled
        self._update_style()
        self.toggled_state_changed.emit(self._is_toggled)
        self.log.debug("Toggle button '%s' state changed to: %s", self.icon_name, self._is_toggled)

    def _update_style(self):
        """Update button style based on toggle state."""
        if self._is_toggled:
            # Active state: visible border
            self.setStyleSheet("""
                QPushButton {
                    border: 2px solid palette(highlight);
                    border-radius: 4px;
                    background-color: palette(button);
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """)
        else:
            # Inactive state: subtle border
            self.setStyleSheet("""
                QPushButton {
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    background-color: palette(button);
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """)

    def is_toggled(self) -> bool:
        """
        Get the current toggle state.

        Returns:
            True if button is toggled on, False otherwise
        """
        return self._is_toggled

    def set_toggled(self, toggled: bool):
        """
        Set the toggle state programmatically without emitting signal.

        Args:
            toggled: New toggle state
        """
        if self._is_toggled != toggled:
            self._is_toggled = toggled
            self._update_style()
            self.log.debug("Toggle button '%s' state set to: %s", self.icon_name, self._is_toggled)
