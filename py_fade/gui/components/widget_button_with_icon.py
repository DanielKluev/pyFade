"""Convenience button widget that renders icons via the Google icon font."""

from PyQt6.QtWidgets import (
    QPushButton,
)
from PyQt6.QtCore import QSize

from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font


class QPushButtonWithIcon(QPushButton):
    """
    QPushButton with an icon from Google Icon Font.
    """

    def __init__(
        self,
        icon_name: str,
        text: str = "",
        parent=None,
        icon_size: int = 16,
        button_size: int | None = None,
    ):
        """
        Initialize the button with an icon and optional text.
        """
        super().__init__(parent)
        if text:
            self.setText(text)
        self.icon_name = icon_name
        self.setIcon(google_icon_font.as_icon(icon_name, size=icon_size))
        self.setIconSize(QSize(icon_size, icon_size))
        if button_size:
            self.setFixedSize(QSize(button_size, button_size))
