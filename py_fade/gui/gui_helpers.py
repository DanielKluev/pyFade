"""
Common imports, types, and utilities for GUI components.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTextEdit,
    QScrollArea,
    QSizePolicy,
    QLabel,
    QFrame,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QPlainTextEdit,
    QLineEdit,
    QGroupBox,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QTextCharFormat, QColor
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font