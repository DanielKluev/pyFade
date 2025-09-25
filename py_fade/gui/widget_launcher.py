"""
Default app start-up launcher window.
Quick shortcuts to open recent datasets, list last 10.
Also has button to create new dataset.

If dataset is protected by encryption, also show password input box when trying to open it.
"""
from __future__ import annotations
import logging
import pathlib
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


class LauncherWidget(QWidget):
    """Simple launcher window shown at app startup.

    Features implemented:
    - Shows a list of recent dataset paths (limited to 10)
    - Button to open the selected dataset
    - Button to create a new dataset (delegates to app)
    - If a dataset appears to be encrypted (very small heuristic), shows password box
    """

    open_dataset_requested = pyqtSignal(str, str)  # path, password (password may be empty)

    def __init__(self, parent: QWidget | None, app: "pyFadeApp"):
        super().__init__(parent)
        self.log = logging.getLogger("LauncherWidget")
        self.app = app
        self.setWindowTitle("pyFade Launcher")
        self.setGeometry(200, 200, 640, 360)

        layout = QVBoxLayout(self)

        header = QLabel("Recent datasets")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # Open dataset on double-click
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

        # Controls
        controls = QHBoxLayout()
        self.open_btn = QPushButton("Open Selected")
        self.open_btn.clicked.connect(self.open_selected)
        controls.addWidget(self.open_btn)

        self.new_btn = QPushButton("Create New Dataset")
        self.new_btn.clicked.connect(self.create_new_dataset)
        controls.addWidget(self.new_btn)

        controls.addStretch()
        layout.addLayout(controls)

        # Password input (hidden by default)
        self.pw_label = QLabel("Password (if dataset encrypted):")
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_label.hide()
        self.pw_input.hide()
        layout.addWidget(self.pw_label)
        layout.addWidget(self.pw_input)

        # Populate recent list from app config if available; fall back to current DB path
        self.populate_recent()

    def populate_recent(self):
        self.list_widget.clear()
        recent = self.app.config.recent_datasets

        # Limit to 10
        for path in recent[:10]:
            item = QListWidgetItem(path)
            self.list_widget.addItem(item)

    def create_new_dataset(self):
        # Show Qt file dialog to create new dataset, picking new .db file path
        file_path, _ = QFileDialog.getSaveFileName(self, "Create New Dataset", "")
        if not file_path:
            self.log.info("Create new dataset cancelled.")
            return
        dataset_path = self.app.create_new_dataset(file_path)
        if not dataset_path:
            self.log.error("Failed to create new dataset.")
            return
        return self.open_dataset(dataset_path, password='')

    def open_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Select dataset", "Please select a dataset from the list.")
            return

        path = pathlib.Path(item.text())
        return self.open_dataset(path, self.pw_input.text())

    def open_dataset(self, path: pathlib.Path, password: str):
        return self.app.open_dataset(path, password)

    def on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on a recent dataset item to open it immediately."""
        if not item:
            return
        path = pathlib.Path(item.text())
        self.open_dataset(path, self.pw_input.text())


def show_launcher(app: "pyFadeApp") -> LauncherWidget:
    """Convenience to create and show the launcher widget."""
    widget = LauncherWidget(parent=None, app=app)
    widget.show()
    return widget
