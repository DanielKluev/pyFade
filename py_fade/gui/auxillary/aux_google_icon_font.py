"""Utilities for rendering Google Material Symbols icons within Qt widgets."""

import logging
import pathlib

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel

common_icons_map = {
    "send": "\ue163",  # run / send icon
    "edit_note": "\ue745",  # edit icon
    "delete": "\ue872",  # trash bin icon
    "close": "\ue5cd",  # close icon
    "check": "\ue5ca",  # check icon
    "keep": "\ue6aa",  # Pin icon
    "keep_off": "\ue6f9",  # Pin off icon
    "inventory_2": "\ue1a1",  # archive icon
    "unarchive": "\ue169",  # unarchive icon
    "label": "\ue892",  # label / tag icon
    "new_label": "\ue609",  # new label / tag icon
    "diamond": "\ue19c",  # diamond / facet icon
    "search_insights": "\uf4bc",  # build metrics / insights icon
    "finance": "\ue6bf",  # metrics / chart icon
    "graph_2": "\uf39f",  # branching / beaming icon
    "robot": "\uf882",  # robot / ai icon
    "auto_read_pause": "\uf219",
    "transition_push": "\uf50b",
    "device_thermostat": "\ue1ff",  # temperature / thermostat icon
    "add": "\ue145",  # plus / add icon
    "no_encryption": "\ue641",  # no encryption / lock open icon
    "shield_locked": "\uf592",  # shield with lock icon, encrypted
    "mode_cool": "\uf166",  # snow flake icon, low temperature
    "star_rate": "\uf0ec",  # star / rating icon, if filled then filled star, else outlined
    "star_rate_half": "\uec45",  # half star icon
    "resume": "\uf7d0",  # resume / play icon
    "settings_alert": "\uf143",  # system with alert
    "person": "\ue7fd",  # user / person icon
}

# Important: icons_aliases holds higher priority than common_icons_map
icons_aliases = {
    "model": "robot",
    "tag": "label",
    "metrics": "finance",
    "beaming": "graph_2",
    "is_truncated": "auto_read_pause",
    "prefill": "transition_push",
    "temperature": "device_thermostat",
    "archive": "inventory_2",
    "system_role": "settings_alert",
    "user_role": "person",
    "assistant_role": "robot",
}


class GoogleIconFontWrapper:
    """Loads and provides access to Google Material Symbols font."""

    def __init__(self, font_path: str | pathlib.Path):
        self.log = logging.getLogger("GoogleIconFontWrapper")
        self.font_path = pathlib.Path(font_path)
        self.font_id: int | None = None
        self.font_family: str | None = None
        self.icon_font: QFont | None = None
        if not self.font_path.exists():
            self.log.error("Google Material Symbols font file does not exist: %s", self.font_path)
            raise FileNotFoundError(f"Google Material Symbols font file does not exist: {self.font_path}")

    def load(self):
        """Load the Material Symbols font into the application."""

        font_id = QFontDatabase.addApplicationFont(str(self.font_path))
        if font_id == -1:
            self.log.error("Failed to load Google Material Symbols font from: %s", self.font_path)
            raise RuntimeError(f"Failed to load Google Material Symbols font from: {self.font_path}")
        self.font_id = font_id

        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            self.log.error("No font families found in Google Material Symbols font: %s", self.font_path)
            raise RuntimeError(f"No font families found in Google Material Symbols font: {self.font_path}")
        self.font_family = families[0]
        self.log.info(
            "Loaded Google Material Symbols font '%s' from: %s",
            self.font_family,
            self.font_path,
        )

        icon_font = QFont(self.font_family)
        icon_font.setPointSize(24)  # Default size, can be changed later
        # self.icon_font.setWeight(QFont.Weight.Thin)
        # self.icon_font.setStyleHint(QFont.StyleHint.TypeWriter)
        icon_font.setVariableAxis(QFont.Tag("wght"), 400.0)
        icon_font.setVariableAxis(QFont.Tag("FILL"), 0.0)  # 0 for outlined, 1 for filled
        icon_font.setVariableAxis(QFont.Tag("GRAD"), 0.0)  # Default; adjust for emphasis
        icon_font.setVariableAxis(QFont.Tag("opsz"), 24.0)  # Matches font size; use 48 for larger icons
        self.icon_font = icon_font

    def codepoint(self, name: str) -> str:
        """
        Get the icon character for the given name.
        """
        alias = icons_aliases.get(name, name)
        return common_icons_map.get(alias, alias)

    def pixmap(
        self,
        name: str,
        size: int = 32,
        color: str | QColor = "black",
        *,
        fill: float | None = None,
    ) -> QPixmap:
        """Render an icon glyph to a pixmap."""

        char = self.codepoint(name)
        if not char:
            self.log.warning("Icon name '%s' not found.", name)
            char = "?"

        if isinstance(color, QColor):
            color = color.name()

        if self.icon_font is None:
            raise RuntimeError("Google icon font was not loaded. Call google_icon_font.load().")

        font = QFont(self.icon_font)
        font.setPointSizeF(float(size))
        font.setVariableAxis(QFont.Tag("opsz"), float(size))
        if fill is not None:
            font.setVariableAxis(QFont.Tag("FILL"), float(fill))

        label = QLabel(char)
        label.setFont(font)
        label.setStyleSheet(f"color: {color}; font-family: 'Material Symbols Outlined'; "
                            f"font-size: {size}px;")  ## **KEEP AS IS**
        label.setFixedSize(size, size)

        pixmap = QPixmap(label.size())
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        label.render(painter)
        painter.end()

        return pixmap

    def as_icon(self, name: str, size: int = 32) -> QIcon:
        """
        Get the icon as a QIcon for the given name.
        """
        return QIcon(self.pixmap(name, size=size))


MATERIAL_SYMBOLS_FONT_PATH = (pathlib.Path(__file__).parent.parent.parent.parent / "assets" / "fonts" /
                              "MaterialSymbolsOutlined-VariableFont_FILL,GRAD,opsz,wght.ttf")

google_icon_font = GoogleIconFontWrapper(MATERIAL_SYMBOLS_FONT_PATH)
