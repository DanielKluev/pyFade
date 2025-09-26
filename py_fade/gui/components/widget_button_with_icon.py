from PyQt6.QtWidgets import (
    QPushButton,
)
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font

class QPushButtonWithIcon(QPushButton):
    """
    QPushButton with an icon from Google Icon Font.
    """
    def __init__(self, icon_name: str, text: str = "", parent=None):
        super().__init__(text, parent)
        self.icon_name = icon_name
        self.setIcon(google_icon_font.as_icon(icon_name))
        self.setIconSize(self.iconSize())  # Use default icon size