import logging, pathlib
from PyQt6.QtGui import QFontDatabase, QFont, QRawFont, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

common_icons_map = {
    "send": "\ue163", # run / send icon
    "edit_note": "\ue745", # edit icon
    "delete": "\ue872", # trash bin icon
    "close": "\ue5cd", # close icon
    "check": "\ue5ca", # check icon
    "keep": "\ue6aa", # Pin icon
    "keep_off": "\ue6f9", # Pin off icon
    "inventory_2": "\ue1a1", # archive icon
    "label": "\ue892", # label / tag icon
    "new_label": "\ue609", # new label / tag icon
    "diamond": "\ue19c", # diamond / facet icon
    "search_insights": "\uf4bc", # build metrics / insights icon
    "finance": "\ue6bf", # metrics / chart icon
    "graph_2": "\uf39f", # branching / beaming icon
    "robot": "\uf882", # robot / ai icon
    "auto_read_pause": "\uf219",
    "transition_push": "\uf50b", 
    "device_thermostat": "\ue1ff", # temperature / thermostat icon
    "add": "\ue145", # plus / add icon
    "no_encryption": "\ue641", # no encryption / lock open icon
    "shield_locked": "\uf592", # shield with lock icon, encrypted
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
}

class GoogleIconFontWrapper:
    """
    Loads and provides access to Google Material Symbols font.
    """
    def __init__(self, font_path: str | pathlib.Path):
        self.log = logging.getLogger("GoogleIconFontWrapper")
        self.font_path = pathlib.Path(font_path)
        if not self.font_path.exists():
            self.log.error(f"Google Material Symbols font file does not exist: {self.font_path}")
            raise FileNotFoundError(f"Google Material Symbols font file does not exist: {self.font_path}")
        
    def load(self):
        self.font_id = QFontDatabase.addApplicationFont(str(self.font_path))
        if self.font_id == -1:
            self.log.error(f"Failed to load Google Material Symbols font from: {self.font_path}")
            raise RuntimeError(f"Failed to load Google Material Symbols font from: {self.font_path}")
        self.font_family = QFontDatabase.applicationFontFamilies(self.font_id)
        if not self.font_family:
            self.log.error(f"No font families found in Google Material Symbols font: {self.font_path}")
            raise RuntimeError(f"No font families found in Google Material Symbols font: {self.font_path}")
        self.font_family = self.font_family[0]
        self.log.info(f"Loaded Google Material Symbols font '{self.font_family}' from: {self.font_path}")

        self.icon_font = QFont(self.font_family)
        self.icon_font.setPointSize(24)  # Default size, can be changed later
        #self.icon_font.setWeight(QFont.Weight.Thin)
        #self.icon_font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.icon_font.setVariableAxis(QFont.Tag("wght"), 400.0)
        self.icon_font.setVariableAxis(QFont.Tag("FILL"), 0.0)  # 0 for outlined, 1 for filled
        self.icon_font.setVariableAxis(QFont.Tag("GRAD"), 0.0)  # Default; adjust for emphasis
        self.icon_font.setVariableAxis(QFont.Tag("opsz"), 24.0)  # Matches font size; use 48 for larger icons

    def codepoint(self, name: str) -> str:
        """
        Get the icon character for the given name.
        """
        if name in icons_aliases:
            name = icons_aliases[name]
        return common_icons_map.get(name, name)

    def pixmap(self, name: str, size: int = 32, color: str|QColor = "black") -> QPixmap:
        char = self.codepoint(name)
        if not char:
            self.log.warning(f"Icon name '{name}' not found.")
            char = "?"

        if isinstance(color, QColor):
            color = color.name()

        label = QLabel(char)
        label.setFont(self.icon_font)
        label.setStyleSheet(f"color: {color}; font-family: 'Material Symbols Outlined'; font-size: {size}px;")
        label.setFixedSize(size, size)

        pixmap = QPixmap(label.size())
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        label.render(painter)
        painter.end()

        return pixmap

    def as_icon(self, name: str) -> QIcon:
        """
        Get the icon as a QIcon for the given name.
        """
        return QIcon(self.pixmap(name))

font_path = pathlib.Path(__file__).parent.parent.parent.parent / "assets" / "fonts" / "MaterialSymbolsOutlined-VariableFont_FILL,GRAD,opsz,wght.ttf"
#font_path = pathlib.Path(__file__).parent.parent.parent / "assets" / "fonts" / "MaterialSymbolsOutlined-Light.ttf"

google_icon_font = GoogleIconFontWrapper(font_path)