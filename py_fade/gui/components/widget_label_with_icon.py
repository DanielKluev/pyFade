"""Composite label widget that pairs a Google icon with text."""

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)

from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font


class QLabelWithIcon(QWidget):
    """
    Two QLabel widgets side by side: one for an icon and one for text.
    """

    def __init__(self, icon_name: str, text: str, text_size: int = 12, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.text = text
        self.text_size = text_size
        self.icon_size = text_size  # Icon size matches text size

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.icon_label = QLabel(self)
        self.icon_label.setPixmap(google_icon_font.pixmap(icon_name, size=self.icon_size))
        layout.addWidget(self.icon_label)

        self.text_label = QLabel(text, self)
        layout.addWidget(self.text_label)

    def setText(self, text: str):  # pylint: disable=invalid-name
        """Replace the displayed text while keeping the icon unchanged."""

        self.text = text
        self.text_label.setText(text)

    def setIcon(self, icon_name: str):  # pylint: disable=invalid-name
        """Swap the leading icon to the Google symbol identified by *icon_name*."""

        self.icon_name = icon_name
        self.icon_label.setPixmap(google_icon_font.pixmap(icon_name, size=self.icon_size))
