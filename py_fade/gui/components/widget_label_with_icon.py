"""Composite label widget that pairs a Google icon with text."""

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)

from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.auxillary.aux_logprobs_to_color import logprob_to_qcolor

class QLabelWithIcon(QLabel):
    """
    A QLabel that displays a Google icon.

    The icon is specified by its name in the Google icon font.
    """

    def __init__(self, icon_name: str, size: int = 12, parent=None, color: str = "black", logprob: float | None = None, tooltip: str | None = None):
        """
        Create a QLabelWithIcon instance.

        `color` can be a named color like "red" or a hex string like "#ff0000" or "logprob" to color by logprob.
        """
        super().__init__(parent)
        self.icon_name = icon_name
        self.icon_size = size
        if color == "logprob":
            if logprob is not None:
                color = logprob_to_qcolor(logprob).name()
            else:
                color = "gray"
        self.setPixmap(google_icon_font.pixmap(icon_name, size=self.icon_size, color=color))
        if tooltip:
            self.setToolTip(tooltip)

    def setIcon(self, icon_name: str):  # pylint: disable=invalid-name
        """Swap the displayed icon to the Google symbol identified by *icon_name*."""
        self.icon_name = icon_name
        self.setPixmap(google_icon_font.pixmap(icon_name, size=self.icon_size))


class QLabelWithIconAndText(QWidget):
    """
    Two QLabel widgets side by side: one for an icon and one for text.
    """

    def __init__(self, icon_name: str, text: str, size: int = 12, parent=None, color: str = "black", tooltip: str | None = None):
        """Create a QLabelWithIconAndText instance."""
        super().__init__(parent)
        self.icon_name = icon_name
        self.text = text
        self.text_size = size
        self.icon_size = size  # Icon size matches text size

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.icon_label = QLabel(self)
        self.icon_label.setPixmap(google_icon_font.pixmap(icon_name, size=self.icon_size, color=color))        
        layout.addWidget(self.icon_label)

        self.text_label = QLabel(text, self)
        layout.addWidget(self.text_label)

        if tooltip:
            self.setToolTip(tooltip)

    def setText(self, text: str):  # pylint: disable=invalid-name
        """Replace the displayed text while keeping the icon unchanged."""

        self.text = text
        self.text_label.setText(text)

    def setIcon(self, icon_name: str):  # pylint: disable=invalid-name
        """Swap the leading icon to the Google symbol identified by *icon_name*."""

        self.icon_name = icon_name
        self.icon_label.setPixmap(google_icon_font.pixmap(icon_name, size=self.icon_size))
