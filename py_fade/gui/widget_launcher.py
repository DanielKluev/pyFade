"""Launcher window for opening or creating datasets with encryption awareness.

The launcher highlights pyFADE branding, lists the user's recent datasets with
icons indicating encryption state, and provides affordances to open or create
datasets. When an encrypted dataset is selected the widget reveals a password
entry field, validates the password via :meth:`DatasetDatabase.check_password`,
and blocks access entirely if SQLCipher support is unavailable in the running
environment.
"""

from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, cast

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.features_checker import SUPPORTED_FEATURES
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font

if TYPE_CHECKING:
    from py_fade.app import PyFadeApp


@dataclass(slots=True)
class RecentDatasetInfo:
    """Metadata describing a dataset entry in the launcher."""

    path: pathlib.Path
    db_type: str
    exists: bool
    icon_name: str
    tooltip: str


class LauncherWidget(QWidget):
    """Startup launcher listing recents, surfacing encryption status, and creating datasets."""

    open_dataset_requested = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None, app: "PyFadeApp"):
        super().__init__(parent)
        self.log = logging.getLogger("LauncherWidget")
        self.app = app
        self.setObjectName("launcher-widget")
        self.setWindowTitle("pyFADE Launcher")
        self.resize(800, 900)

        self.setup_ui()
        self.connect_signals()
        self.set_recent_datasets()

    # ------------------------------------------------------------------ UI --
    def setup_ui(self) -> None:
        """Construct the widget layout following pyFADE's UI conventions."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header_frame = QFrame(self)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.logo_label = QLabel(header_frame)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(self.logo_label)
        self._apply_logo_pixmap()

        self.title_label = QLabel("Curate your faceted datasets", header_frame)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setStyleSheet("font-weight: 600; font-size: 20px;")
        header_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(
            "Open a recent workspace or start a fresh dataset to begin annotating.",
            header_frame,
        )
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.subtitle_label.setStyleSheet("color: #666; font-size: 13px;")
        header_layout.addWidget(self.subtitle_label)

        layout.addWidget(header_frame)

        list_frame = QFrame(self)
        list_frame.setObjectName("launcher-recents-frame")
        list_frame.setStyleSheet("#launcher-recents-frame {"
                                 "    border: 1px solid #d0d5dd;"
                                 "    border-radius: 12px;"
                                 "    background-color: #f8fafc;"
                                 "}")

        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        header_icon = QLabel(list_frame)
        header_icon.setPixmap(google_icon_font.pixmap("inventory_2", size=20, color="#344054"))
        header_row.addWidget(header_icon)

        header_label = QLabel("Recent datasets", list_frame)
        header_label.setStyleSheet("font-weight: 600; font-size: 14px; color: #1d2939;")
        header_row.addWidget(header_label)
        header_row.addStretch()
        list_layout.addLayout(header_row)

        self.list_widget = QListWidget(list_frame)
        self.list_widget.setObjectName("launcher-recents-list")
        self.list_widget.setAlternatingRowColors(False)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.setUniformItemSizes(False)
        self.list_widget.setSpacing(4)
        self.list_widget.setStyleSheet("QListWidget#launcher-recents-list {"
                                       "    background: transparent;"
                                       "    border: none;"
                                       "    font-size: 12px;"
                                       "}"
                                       "QListWidget#launcher-recents-list::item {"
                                       "    padding: 10px 12px;"
                                       "    margin: 2px 0;"
                                       "    border-radius: 8px;"
                                       "}"
                                       "QListWidget#launcher-recents-list::item:selected {"
                                       "    background: #e0f2fe;"
                                       "}")
        list_layout.addWidget(self.list_widget)
        ## Set a minimum height to avoid looking too empty
        self.list_widget.setMinimumHeight(400)

        layout.addWidget(list_frame)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(12)

        self.open_btn = QPushButton("Open selected", self)
        self.open_btn.setEnabled(False)
        controls_row.addWidget(self.open_btn)

        self.new_btn = QPushButton("Create new dataset", self)
        controls_row.addWidget(self.new_btn)

        controls_row.addItem(QSpacerItem(24, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        layout.addLayout(controls_row)

        password_frame = QFrame(self)
        password_frame.setObjectName("launcher-password-frame")
        password_layout = QVBoxLayout(password_frame)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(6)

        self.pw_label = QLabel("Dataset password", password_frame)
        self.pw_label.setStyleSheet("font-weight: 500; color: #1d2939;")
        password_layout.addWidget(self.pw_label)

        self.pw_input = QLineEdit(password_frame)
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Enter password to unlock this dataset")
        password_layout.addWidget(self.pw_input)

        self.password_hint_label = QLabel(
            "Encrypted datasets require SQLCipher support.",
            password_frame,
        )
        self.password_hint_label.setStyleSheet("color: #475467; font-size: 11px;")
        password_layout.addWidget(self.password_hint_label)

        layout.addWidget(password_frame)

        #layout.addStretch()

        password_frame.hide()
        self.password_frame = password_frame

    def connect_signals(self) -> None:
        """Wire widget signals to their handlers."""

        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)
        self.open_btn.clicked.connect(self.open_selected)
        self.new_btn.clicked.connect(self.create_new_dataset)

    # --------------------------------------------------------------- Data --
    def set_recent_datasets(self, dataset_paths: Iterable[str] | None = None) -> None:
        """Populate the recent datasets list using the provided or configured paths."""

        if dataset_paths is None:
            configured = getattr(self.app.config, "recent_datasets", [])
            if configured is None:
                configured = []
            dataset_paths = configured

        paths: Iterable[str] = cast(Iterable[str], dataset_paths)

        normalized_paths: list[str] = []
        for raw_path in paths:
            try:
                real_path = str(pathlib.Path(raw_path).expanduser().resolve())
            except (OSError, RuntimeError):
                self.log.warning("Skipping invalid recent dataset entry: %s", raw_path)
                continue
            if real_path not in normalized_paths:
                normalized_paths.append(real_path)
        normalized_paths = normalized_paths[:10]

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for path_str in normalized_paths:
            info = self._build_dataset_info(pathlib.Path(path_str))
            item = self._create_list_item(info)
            self.list_widget.addItem(item)

        self.list_widget.blockSignals(False)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self._update_password_section(self._selected_dataset_info())
        else:
            self._update_password_section(None)
            self.open_btn.setEnabled(False)

    # ---------------------------------------------------------- Helpers --
    def _create_list_item(self, info: RecentDatasetInfo) -> QListWidgetItem:
        item = QListWidgetItem()
        icon: QIcon = google_icon_font.as_icon(info.icon_name)
        item.setIcon(icon)

        display_name = info.path.name or str(info.path)
        item.setText(f"{display_name}\n{info.path}")
        item.setToolTip(info.tooltip)
        item.setData(Qt.ItemDataRole.UserRole, info)
        return item

    def _build_dataset_info(self, path: pathlib.Path) -> RecentDatasetInfo:
        exists = path.exists()
        if not exists:
            tooltip = f"{path}\nFile not found."
            return RecentDatasetInfo(path=path, db_type="missing", exists=False, icon_name="inventory_2", tooltip=tooltip)

        db_type = DatasetDatabase.check_db_type(path)
        if db_type == "sqlcipher":
            icon_name = "shield_locked"
            tooltip = f"{path}\nEncrypted SQLCipher dataset."
        elif db_type == "sqlite":
            icon_name = "no_encryption"
            tooltip = f"{path}\nUnencrypted SQLite dataset."
        else:
            icon_name = "inventory_2"
            tooltip = f"{path}\nUnknown database format."

        return RecentDatasetInfo(path=path, db_type=db_type, exists=True, icon_name=icon_name, tooltip=tooltip)

    def _apply_logo_pixmap(self) -> None:
        root_dir = pathlib.Path(__file__).resolve().parents[2]
        logo_path = root_dir / "assets" / "images" / "pyFADE-logo-300_800_text.png"
        pixmap = QPixmap(str(logo_path)) if logo_path.exists() else QPixmap()
        if pixmap.isNull():
            self.log.warning("pyFADE logo not found at %s", logo_path)
            self.logo_label.setText("pyFADE")
            self.logo_label.setStyleSheet("font-weight: 700; font-size: 24px;")
            return
        scaled = pixmap.scaledToWidth(360, Qt.TransformationMode.SmoothTransformation)
        self.logo_label.setPixmap(scaled)
        self.logo_label.setMinimumHeight(scaled.height())

    def _selected_dataset_info(self) -> RecentDatasetInfo | None:
        item = self.list_widget.currentItem()
        if not item:
            return None
        info = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(info, RecentDatasetInfo):
            return info
        if isinstance(info, dict) and "path" in info:
            return RecentDatasetInfo(**info)
        return None

    def _update_password_section(self, info: RecentDatasetInfo | None) -> None:
        is_encrypted = bool(info and info.db_type == "sqlcipher")
        self.password_frame.setVisible(is_encrypted)
        if not is_encrypted:
            self.pw_input.clear()
        self._update_open_button_state(info)

    def _update_open_button_state(self, info: RecentDatasetInfo | None) -> None:
        if not info:
            self.open_btn.setEnabled(False)
            self.open_btn.setToolTip("Select a dataset to enable opening.")
            return
        if not info.exists:
            self.open_btn.setEnabled(False)
            self.open_btn.setToolTip("Dataset file is missing.")
            return
        if info.db_type == "sqlcipher" and not SUPPORTED_FEATURES.get("sqlcipher3", False):
            self.open_btn.setEnabled(False)
            self.open_btn.setToolTip("sqlcipher3 is required to open encrypted datasets.")
            return
        self.open_btn.setEnabled(True)
        self.open_btn.setToolTip("")

    # ----------------------------------------------------------- Slots --
    def create_new_dataset(self) -> None:
        """Open a file dialog to create a new dataset and refresh the recents list."""

        file_path, _ = QFileDialog.getSaveFileName(self, "Create New Dataset", "", "SQLite DB (*.db)")
        if not file_path:
            self.log.info("Create new dataset cancelled by user.")
            return
        dataset_path = pathlib.Path(file_path)
        try:
            created_path = self.app.create_new_dataset(dataset_path)
        except (OSError, SQLAlchemyError, RuntimeError, ValueError) as exc:
            self.log.exception("Failed to create dataset at %s", dataset_path)
            QMessageBox.critical(self, "Create dataset", f"Failed to create dataset:\n{exc}")
            return
        if not created_path:
            QMessageBox.warning(self, "Create dataset", "Dataset was not created. Please pick a new location.")
            return
        self.set_recent_datasets()
        self.open_dataset(pathlib.Path(created_path), "")

    def open_selected(self) -> None:
        """Open the dataset currently selected in the recents list."""

        info = self._selected_dataset_info()
        if not info:
            QMessageBox.warning(self, "Select dataset", "Please select a dataset from the list.")
            return
        if not info.exists:
            QMessageBox.warning(self, "Dataset missing", "The dataset file no longer exists on disk.")
            return
        if info.db_type == "sqlcipher" and not SUPPORTED_FEATURES.get("sqlcipher3", False):
            self._show_sqlcipher_missing_warning(info.path)
            return

        password = ""
        if info.db_type == "sqlcipher":
            password = self.pw_input.text()
            if not password:
                QMessageBox.warning(self, "Password required", "Enter the password to unlock this dataset.")
                self.pw_input.setFocus()
                return
            if not DatasetDatabase.check_password(info.path, password):
                QMessageBox.critical(
                    self,
                    "Incorrect password",
                    "The provided password is not valid for this dataset.",
                )
                self.pw_input.selectAll()
                return

        self.open_dataset(info.path, password)

    def open_dataset(self, path: pathlib.Path, password: str) -> None:
        """Delegate dataset opening to the application and refresh recents afterwards."""

        self.log.info("Opening dataset %s (encrypted=%s)", path, bool(password))
        self.open_dataset_requested.emit(str(path), password)
        try:
            self.app.open_dataset(path, password)
        except (OSError, SQLAlchemyError, RuntimeError, ValueError) as exc:
            self.log.exception("Failed to open dataset at %s", path)
            QMessageBox.critical(self, "Open dataset", f"Failed to open dataset:\n{exc}")
            return
        self.set_recent_datasets()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        if not item:
            return
        self.open_selected()

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        info = current.data(Qt.ItemDataRole.UserRole) if current else None
        if isinstance(info, RecentDatasetInfo):
            dataset_info = info
        elif isinstance(info, dict) and "path" in info:
            dataset_info = RecentDatasetInfo(**info)
        else:
            dataset_info = None
        self._update_password_section(dataset_info)

    def _show_sqlcipher_missing_warning(self, path: pathlib.Path) -> None:
        QMessageBox.warning(
            self,
            "SQLCipher support required",
            ("The dataset at\n"
             f"{path}\n"
             "is encrypted with SQLCipher, but the sqlcipher3 package is not installed."
             "\nInstall sqlcipher3 to unlock encrypted datasets."),
        )


def show_launcher(app: "PyFadeApp") -> LauncherWidget:
    """Convenience helper that instantiates and shows the launcher widget."""

    widget = LauncherWidget(parent=None, app=app)
    widget.show()
    return widget
