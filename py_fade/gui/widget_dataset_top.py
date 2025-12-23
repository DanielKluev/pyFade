"""
Dataset workspace window with native menu-driven encryption controls.

This module provides ``WidgetDatasetTop``, the main dataset workspace window for
pyFADE.
"""

# pylint: disable=too-many-lines

import logging
import pathlib
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, Qt, QUrl
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QMessageBox,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision

# Dataset models
from py_fade.dataset.sample import Sample
from py_fade.dataset.sample_filter import SampleFilter
from py_fade.dataset.tag import Tag
from py_fade.gui.gui_helpers import get_dataset_preferences, update_dataset_preferences
from py_fade.gui.widget_export_template import WidgetExportTemplate
from py_fade.gui.widget_facet import WidgetFacet

# pyFADE widgets
from py_fade.gui.widget_navigation_sidebar import WidgetNavigationSidebar
from py_fade.gui.widget_sample import WidgetSample
from py_fade.gui.widget_sample_filter import WidgetSampleFilter
from py_fade.gui.widget_tag import WidgetTag
from py_fade.features_checker import SUPPORTED_FEATURES

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


class WidgetDatasetTop(QMainWindow):
    """Composite dataset workspace with sidebar, context panel, and tabbed editors.

    The context controls define the active facet and target LLM model, propagating to
    sample editors and the navigation sidebar. Facet selection adjusts completion
    ordering and preferences, while the target model acts as the logprob evaluation
    reference even when completions originate from other providers.

    Tabs cover dashboards, samples, facets, tags, and export templates. A native
    application menu bar exposes File, Export, and Help actions, including dataset
    encryption workflows. By default the workspace opens with a dashboard tab and a
    new sample tab ready for editing.
    """

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: DatasetDatabase):
        super().__init__(parent)
        self.log = logging.getLogger("WidgetDatasetTop")
        self.app = app
        self.dataset = dataset
        self.tabs: dict[int, dict] = {}
        self.overview_widget: QWidget | None = None
        self.current_facet_id: int | None = None
        self.current_facet: Facet | None = None
        self.current_model_path: str | None = None
        self._facet_map: dict[int, Facet] = {}
        self._updating_context = False
        self._sidebar_previous_show_value: str | None = None
        self.facet_combo: QComboBox | None = None
        self.model_combo: QComboBox | None = None
        self.menu_bar: QMenuBar | None = None
        self.file_menu: QMenu | None = None
        self.export_menu: QMenu | None = None
        self.preferences_menu: QMenu | None = None
        self.help_menu: QMenu | None = None
        self.action_encrypt_save_as: QAction | None = None
        self.action_change_password: QAction | None = None
        self.action_save_unencrypted_copy: QAction | None = None
        self.action_close_dataset: QAction | None = None
        self.action_exit_application: QAction | None = None
        self.action_import_wizard: QAction | None = None
        self.action_manage_export_templates: QAction | None = None
        self.action_export_wizard: QAction | None = None
        self.action_export_current_facet: QAction | None = None
        self.action_manage_models: QAction | None = None
        self.action_open_encryption_docs: QAction | None = None
        self.action_about: QAction | None = None
        self.facet_summary_button: QPushButton | None = None

        self.setWindowTitle(f"Dataset: {dataset.db_path.name}")
        self.setGeometry(200, 200, 1200, 800)

        self.setup_ui()
        self.populate_tabs()
        self.connect_signals()
        self.set_facets()
        self.set_models()
        self._propagate_context_to_samples()
        self._refresh_menu_state()

    def setup_ui(self) -> None:
        """Setup the QMainWindow structure with native menu bar and splitter."""

        self.menu_bar = self.menuBar()
        if self.menu_bar is None:
            self.menu_bar = QMenuBar(self)
            self.setMenuBar(self.menu_bar)
        self.menu_bar.setObjectName("dataset-menu-bar")
        if hasattr(self.menu_bar, "setNativeMenuBar"):
            self.menu_bar.setNativeMenuBar(True)
        self._build_menus()

        central_widget = QWidget(self)
        central_widget.setObjectName("dataset-central-widget")
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(5, 5, 5, 5)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, central_widget)
        self.main_splitter.setObjectName("dataset-main-splitter")
        central_layout.addWidget(self.main_splitter)

        self.sidebar = WidgetNavigationSidebar(self, self.app)
        self.sidebar.set_dataset(self.dataset)
        self.main_splitter.addWidget(self.sidebar)

        self.main_content = QWidget(self.main_splitter)
        self.main_content.setObjectName("dataset-main-content")
        self.setup_main_content()
        self.main_splitter.addWidget(self.main_content)

        self.main_splitter.setSizes([300, 900])
        self.main_splitter.setCollapsible(0, False)

        self.setCentralWidget(central_widget)

    def setup_main_content(self) -> None:
        """Setup the main content area with context controls and tab widget."""
        content_layout = QVBoxLayout(self.main_content)
        content_layout.setContentsMargins(5, 5, 5, 5)

        context_frame = QFrame(self.main_content)
        context_frame.setObjectName("dataset-context-frame")
        context_layout = QHBoxLayout(context_frame)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(12)

        facet_label = QLabel("Facet:")
        facet_label.setStyleSheet("font-weight: 500;")
        context_layout.addWidget(facet_label)

        self.log.info("Create facet combo")
        self.facet_combo = QComboBox()
        self.facet_combo.setObjectName("facet-selector")
        self.facet_combo.setEditable(False)
        self.facet_combo.setMinimumWidth(200)
        context_layout.addWidget(self.facet_combo)
        self.log.info("Facet combo created: %s", self.facet_combo)

        model_label = QLabel("Model:")
        model_label.setStyleSheet("font-weight: 500;")
        context_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setObjectName("model-selector")
        self.model_combo.setEditable(False)
        self.model_combo.setMinimumWidth(220)
        context_layout.addWidget(self.model_combo)

        # Facet Summary button
        self.facet_summary_button = QPushButton("Facet Summary")
        self.facet_summary_button.setObjectName("facet-summary-button")
        self.facet_summary_button.setEnabled(False)
        self.facet_summary_button.clicked.connect(self._on_facet_summary_clicked)
        context_layout.addWidget(self.facet_summary_button)

        context_layout.addStretch()
        content_layout.addWidget(context_frame)

        self.tab_widget = QTabWidget()  # pylint: disable=attribute-defined-outside-init
        self.tab_widget.setObjectName("dataset-tab-widget")
        self.tab_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_widget.customContextMenuRequested.connect(self._on_tab_context_menu)
        content_layout.addWidget(self.tab_widget)

    def _build_menus(self) -> None:
        """Create the File, Export, and Help menus."""

        menu_bar = self.menu_bar
        if menu_bar is None:
            return

        menu_bar.clear()

        file_menu = menu_bar.addMenu("&File")
        if file_menu is None:  # pragma: no cover - defensive guard
            return
        self.file_menu = file_menu
        self.action_import_wizard = file_menu.addAction("Import Data…")
        file_menu.addSeparator()
        self.action_encrypt_save_as = file_menu.addAction("Encrypt and Save As…")
        self.action_change_password = file_menu.addAction("Change Password…")
        self.action_save_unencrypted_copy = file_menu.addAction("Save Unencrypted Copy As…")
        file_menu.addSeparator()
        self.action_close_dataset = file_menu.addAction("Close Dataset")
        self.action_exit_application = file_menu.addAction("Exit")

        export_menu = menu_bar.addMenu("&Export")
        if export_menu is None:  # pragma: no cover - defensive guard
            return
        self.export_menu = export_menu
        self.action_manage_export_templates = export_menu.addAction("Manage Export Templates")
        self.action_export_wizard = export_menu.addAction("Export Wizard...")
        self.action_export_current_facet = export_menu.addAction("Open Current Facet in Export Editor")

        preferences_menu = menu_bar.addMenu("&Preferences")
        if preferences_menu is None:  # pragma: no cover - defensive guard
            return
        self.preferences_menu = preferences_menu
        self.action_manage_models = preferences_menu.addAction("Manage Models...")

        help_menu = menu_bar.addMenu("&Help")
        if help_menu is None:  # pragma: no cover - defensive guard
            return
        self.help_menu = help_menu
        self.action_open_encryption_docs = help_menu.addAction("Encryption Guide…")
        self.action_about = help_menu.addAction("About pyFADE")

    def _refresh_menu_state(self) -> None:
        """Update menu visibility and enabled state based on dataset context."""

        is_sqlcipher_available = SUPPORTED_FEATURES.get("sqlcipher3", False)
        is_encrypted = False
        try:
            is_encrypted = self.dataset.is_encrypted()
        except (OSError, RuntimeError) as exc:  # pragma: no cover - defensive guard
            self.log.warning("Failed to probe dataset encryption state: %s", exc)

        tooltip_sqlcipher_missing = "SQLCipher support is required. Install the sqlcipher3 package to enable this action."

        if self.action_encrypt_save_as is not None:
            self.action_encrypt_save_as.setVisible(not is_encrypted)
            self.action_encrypt_save_as.setEnabled(not is_encrypted and is_sqlcipher_available)
            self.action_encrypt_save_as.setToolTip(
                "Create an encrypted copy of this dataset." if is_sqlcipher_available else tooltip_sqlcipher_missing)

        if self.action_change_password is not None:
            self.action_change_password.setVisible(is_encrypted)
            self.action_change_password.setEnabled(is_encrypted and is_sqlcipher_available)
            self.action_change_password.setToolTip(
                "Update the SQLCipher password for this dataset." if is_sqlcipher_available else tooltip_sqlcipher_missing)

        if self.action_save_unencrypted_copy is not None:
            self.action_save_unencrypted_copy.setVisible(is_encrypted)
            self.action_save_unencrypted_copy.setEnabled(is_encrypted and is_sqlcipher_available)
            self.action_save_unencrypted_copy.setToolTip(
                "Export a plain SQLite copy of this encrypted dataset." if is_sqlcipher_available else tooltip_sqlcipher_missing)

        docs_path = pathlib.Path(__file__).resolve().parents[2] / "docs" / "encryption.md"
        if self.action_open_encryption_docs is not None:
            has_docs = docs_path.exists()
            self.action_open_encryption_docs.setEnabled(has_docs)
            tooltip = ("View the encryption guide in your browser." if has_docs else "Encryption guide file not found.")
            self.action_open_encryption_docs.setToolTip(tooltip)

        if self.action_manage_export_templates is not None:
            self.action_manage_export_templates.setEnabled(True)

        if self.action_export_wizard is not None:
            self.action_export_wizard.setEnabled(True)

        if self.action_export_current_facet is not None:
            self.action_export_current_facet.setEnabled(self.current_facet is not None)

        if self.action_close_dataset is not None:
            self.action_close_dataset.setEnabled(True)

        if self.action_exit_application is not None:
            self.action_exit_application.setEnabled(True)

        # Enable Facet Summary button only when both facet and model are selected
        if hasattr(self, "facet_summary_button") and self.facet_summary_button is not None:
            self.facet_summary_button.setEnabled(self.current_facet is not None and self.current_model_path is not None)

    def _handle_encrypt_save_as(self, _checked: bool = False) -> None:
        """Encrypt the dataset into a new SQLCipher database."""

        if not SUPPORTED_FEATURES.get("sqlcipher3", False):
            QMessageBox.warning(
                self,
                "Encryption unavailable",
                "The sqlcipher3 package is not installed. Install it to encrypt datasets.",
            )
            return

        suggested_name = f"{self.dataset.db_path.stem}-encrypted.db"
        destination = self._prompt_for_dataset_destination("Encrypt and Save As…", suggested_name)
        if destination is None:
            return

        password = self._prompt_for_new_password("Set Encryption Password")
        if password is None:
            return

        self.log.info("Encrypting dataset copy to %s", destination)
        try:
            self.dataset.encrypt_copy(destination, password)
        except (RuntimeError, ValueError, OSError) as exc:
            self.log.exception("Failed to encrypt dataset to %s", destination)
            QMessageBox.critical(
                self,
                "Encrypt dataset",
                f"Failed to create encrypted copy:\n{exc}",
            )
            self._refresh_menu_state()
            return

        QMessageBox.information(
            self,
            "Dataset encrypted",
            f"An encrypted copy was saved to:\n{destination}",
        )
        self._prompt_reopen_dataset(destination, password)

    def _handle_change_password(self, _checked: bool = False) -> None:
        """Change the password of the currently encrypted dataset."""

        if not SUPPORTED_FEATURES.get("sqlcipher3", False):
            QMessageBox.warning(
                self,
                "Encryption unavailable",
                "The sqlcipher3 package is not installed. Install it to change passwords.",
            )
            return

        new_password = self._prompt_for_new_password("Change Dataset Password")
        if new_password is None:
            return

        self.log.info("Changing dataset password for %s", self.dataset.db_path)
        try:
            self.dataset.change_password(new_password)
        except (RuntimeError, ValueError, OSError) as exc:
            self.log.exception("Failed to change dataset password for %s", self.dataset.db_path)
            QMessageBox.critical(
                self,
                "Change password",
                f"Failed to change dataset password:\n{exc}",
            )
            self._refresh_menu_state()
            return

        QMessageBox.information(
            self,
            "Password updated",
            "The dataset password was updated successfully.",
        )
        self._prompt_reopen_dataset(self.dataset.db_path, new_password)

    def _handle_save_unencrypted_copy(self, _checked: bool = False) -> None:
        """Write an unencrypted copy of the dataset to disk."""

        if not SUPPORTED_FEATURES.get("sqlcipher3", False):
            QMessageBox.warning(
                self,
                "Encryption unavailable",
                "The sqlcipher3 package is not installed. Install it to decrypt datasets.",
            )
            return

        suggested_name = f"{self.dataset.db_path.stem}-unencrypted.db"
        destination = self._prompt_for_dataset_destination("Save Unencrypted Copy As…", suggested_name)
        if destination is None:
            return

        self.log.info("Saving unencrypted dataset copy to %s", destination)
        try:
            self.dataset.save_unencrypted_copy(destination)
        except (RuntimeError, ValueError, OSError) as exc:
            self.log.exception("Failed to create unencrypted dataset copy at %s", destination)
            QMessageBox.critical(
                self,
                "Save unencrypted copy",
                f"Failed to create unencrypted copy:\n{exc}",
            )
            self._refresh_menu_state()
            return

        QMessageBox.information(
            self,
            "Unencrypted copy created",
            f"A plain SQLite copy was saved to:\n{destination}",
        )
        self._prompt_reopen_dataset(destination, "")

    def _handle_close_dataset(self, _checked: bool = False) -> None:
        """Close the current dataset and return to the launcher."""

        self.log.info("Closing dataset workspace at user request")
        self.app.close_current_dataset(show_launcher_window=True)

    def _handle_exit_application(self, _checked: bool = False) -> None:
        """Exit the application via the application menu."""

        self.log.info("Exiting application from dataset workspace menu")
        if self.app.q_app is not None:
            self.app.q_app.quit()

    def _handle_import_wizard(self, _checked: bool = False) -> None:
        """Open the Import Data Wizard."""

        # Import here to avoid circular dependency
        from py_fade.gui.window_import_wizard import ImportWizard  # pylint: disable=import-outside-toplevel

        self.log.info("Opening Import Data Wizard")
        wizard = ImportWizard(self, self.app, self.dataset)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            # Refresh the sidebar to show any newly imported data
            if hasattr(self.sidebar, "refresh"):
                self.sidebar.refresh()

    def _handle_manage_export_templates(self, _checked: bool = False) -> None:
        """Open an export template editor tab and highlight export templates in the sidebar."""

        widget_id = self.create_export_template_tab(None, focus=True)
        widget_info = self.tabs.get(widget_id, {})
        self._focus_widget(widget_info.get("widget"))
        if hasattr(self.sidebar, "filter_panel"):
            self.sidebar.filter_panel.show_combo.setCurrentText("Export Templates")
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()

    def _handle_export_wizard(self, _checked: bool = False) -> None:
        """Open the Export Data Wizard."""

        # Import here to avoid circular dependency
        from py_fade.gui.window_export_wizard import ExportWizard  # pylint: disable=import-outside-toplevel

        self.log.info("Opening Export Data Wizard")
        wizard = ExportWizard(self, self.app, self.dataset)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            # Refresh the sidebar in case export affected anything
            if hasattr(self.sidebar, "refresh"):
                self.sidebar.refresh()

    def _handle_export_current_facet(self, _checked: bool = False) -> None:
        """Bootstrap an export template scoped to the currently selected facet."""

        if not self.current_facet:
            QMessageBox.information(
                self,
                "Select a facet",
                "Choose a facet in the context selector to bootstrap an export template.",
            )
            return

        widget_id = self.create_export_template_tab(None, focus=True)
        widget = self.tabs.get(widget_id, {}).get("widget")
        self._focus_widget(widget)
        if isinstance(widget, WidgetExportTemplate):
            widget.name_input.setText(f"{self.current_facet.name} Export")
            widget.description_input.setText(f"Auto-generated template for facet '{self.current_facet.name}'.")
            index = widget.facet_selector.findData(self.current_facet.id)
            if index >= 0:
                widget.facet_selector.setCurrentIndex(index)
                widget.add_facet_button.click()

    def _handle_manage_models(self, _checked: bool = False) -> None:
        """Open the Model Manager window."""
        from py_fade.gui.window_model_manager import ModelManagerWindow  # pylint: disable=import-outside-toplevel

        dialog = ModelManagerWindow(self, self.app)
        dialog.exec()

    def _handle_open_encryption_docs(self, _checked: bool = False) -> None:
        """Open the encryption documentation in the user's default browser."""

        docs_path = pathlib.Path(__file__).resolve().parents[2] / "docs" / "encryption.md"
        if not docs_path.exists():
            QMessageBox.information(
                self,
                "Documentation missing",
                "The encryption guide could not be located in the repository.",
            )
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs_path)))

    def _handle_about_dialog(self, _checked: bool = False) -> None:
        """Show a lightweight about dialog for pyFADE."""

        message = ("pyFADE – Faceted Alignment Dataset Editor\n"
                   f"Dataset path: {self.dataset.db_path}\n"
                   "Visit https://github.com/DanielKluev/pyFade for project details.")
        QMessageBox.information(self, "About pyFADE", message)

    def _on_facet_summary_clicked(self) -> None:
        """Open the facet summary modal dialog."""

        if not self.current_facet:
            QMessageBox.information(
                self,
                "No Facet Selected",
                "Please select a facet from the dropdown to view its summary.",
            )
            return

        mapped_model = None
        if self.current_model_path:
            mapped_model = self.app.providers_manager.get_mapped_model(self.current_model_path)

        if not mapped_model:
            QMessageBox.information(
                self,
                "No Model Selected",
                "Please select a target model from the dropdown to view the facet summary.",
            )
            return

        # Import here to avoid circular dependency
        from py_fade.gui.window_facet_summary import FacetSummaryWindow  # pylint: disable=import-outside-toplevel

        self.log.info("Opening facet summary for facet '%s' and model '%s'", self.current_facet.name, mapped_model.path)
        dialog = FacetSummaryWindow(self.app, self.dataset, self.current_facet, mapped_model, parent=self)
        dialog.exec()

    def _prompt_for_dataset_destination(self, title: str, suggested_name: str) -> pathlib.Path | None:
        """Ask the user for a destination file path, returning ``None`` on cancel."""

        default_path = self.dataset.db_path.with_name(suggested_name)
        selected, _ = QFileDialog.getSaveFileName(
            self,
            title,
            str(default_path),
            "SQLite Databases (*.db);;All Files (*.*)",
        )
        if not selected:
            return None

        destination = pathlib.Path(selected)
        if destination.suffix.lower() != ".db":
            destination = destination.with_suffix(".db")
        return destination

    def _prompt_for_new_password(self, title: str) -> str | None:
        """Prompt the user to enter and confirm a new password."""

        while True:
            password, accepted = QInputDialog.getText(
                self,
                title,
                "Enter password:",
                QLineEdit.EchoMode.Password,
            )
            if not accepted:
                return None
            if not password:
                QMessageBox.warning(self, title, "Password cannot be empty.")
                continue

            confirm, confirm_ok = QInputDialog.getText(
                self,
                title,
                "Confirm password:",
                QLineEdit.EchoMode.Password,
            )
            if not confirm_ok:
                return None
            if password != confirm:
                QMessageBox.warning(self, title, "Passwords do not match.")
                continue
            return password

    def _prompt_reopen_dataset(self, path: pathlib.Path, password: str) -> None:
        """Ask the user whether to reopen the dataset after encryption changes."""

        response = QMessageBox.question(
            self,
            "Reopen dataset",
            ("Encryption settings have changed. Reopen the dataset from:\n"
             f"{path}\n"
             "now to refresh cached state?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if response == QMessageBox.StandardButton.Yes:
            self._reopen_dataset(path, password)
        else:
            self._refresh_menu_state()

    def _reopen_dataset(self, path: pathlib.Path, password: str) -> None:
        """Reload the dataset via the application to ensure clean caches."""

        self.log.info("Reloading dataset from %s", path)
        self.app.reload_dataset(path, password)

    def connect_signals(self):
        """Connect signals between components."""
        self.sidebar.item_selected.connect(self._on_navigation_item_selected)
        self.sidebar.new_item_requested.connect(self._on_new_item_requested)
        if self.facet_combo is not None:
            self.facet_combo.currentIndexChanged.connect(self._on_facet_selection_changed)
        if self.model_combo is not None:
            self.model_combo.currentTextChanged.connect(self._on_model_selection_changed)
        if self.action_import_wizard is not None:
            self.action_import_wizard.triggered.connect(self._handle_import_wizard)
        if self.action_encrypt_save_as is not None:
            self.action_encrypt_save_as.triggered.connect(self._handle_encrypt_save_as)
        if self.action_change_password is not None:
            self.action_change_password.triggered.connect(self._handle_change_password)
        if self.action_save_unencrypted_copy is not None:
            self.action_save_unencrypted_copy.triggered.connect(self._handle_save_unencrypted_copy)
        if self.action_close_dataset is not None:
            self.action_close_dataset.triggered.connect(self._handle_close_dataset)
        if self.action_exit_application is not None:
            self.action_exit_application.triggered.connect(self._handle_exit_application)
        if self.action_manage_export_templates is not None:
            self.action_manage_export_templates.triggered.connect(self._handle_manage_export_templates)
        if self.action_export_wizard is not None:
            self.action_export_wizard.triggered.connect(self._handle_export_wizard)
        if self.action_export_current_facet is not None:
            self.action_export_current_facet.triggered.connect(self._handle_export_current_facet)
        if self.action_manage_models is not None:
            self.action_manage_models.triggered.connect(self._handle_manage_models)
        if self.action_open_encryption_docs is not None:
            self.action_open_encryption_docs.triggered.connect(self._handle_open_encryption_docs)
        if self.action_about is not None:
            self.action_about.triggered.connect(self._handle_about_dialog)

    def _dataset_pref_key(self) -> str:
        return str(self.dataset.db_path.resolve())

    def set_facets(self) -> None:
        """Populate facet selector based on current dataset state and preferences."""
        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        if self.facet_combo is None:
            raise RuntimeError("Facet combo box is not initialized.")

        available_facets = list(self.dataset.session.query(Facet).all())
        if not available_facets:
            self.log.warning("No facets available in dataset; facet selector will be empty.")
            self.current_facet_id = None
            return

        self._facet_map.clear()
        self.facet_combo.blockSignals(True)
        self.facet_combo.clear()
        if not self.current_facet_id:
            dataset_prefs = get_dataset_preferences(self.app, self._dataset_pref_key())
            facet_pref = dataset_prefs.get("facet_id")
            if isinstance(facet_pref, int):
                self.current_facet_id = facet_pref

        for facet in available_facets:
            self._facet_map[facet.id] = facet
            self.facet_combo.addItem(facet.name, facet.id)

        selected_facet: Facet | None = None
        if self.current_facet_id and self.current_facet_id in self._facet_map:
            selected_facet = self._facet_map[self.current_facet_id]

        if selected_facet is None and available_facets:
            first_facet = available_facets[0]
            selected_facet = first_facet

        if selected_facet is not None:
            index = self.facet_combo.findData(selected_facet.id)
            if index >= 0:
                self.facet_combo.setCurrentIndex(index)
            self.current_facet = selected_facet
            self.current_facet_id = selected_facet.id
        else:
            self.current_facet = None
            self.current_facet_id = None

        self.facet_combo.blockSignals(False)

    def set_models(self) -> None:
        """Populate model selector based on current dataset state and preferences."""
        if self.model_combo is None or not self.app.available_models:
            raise RuntimeError("Application is not fully initialized or no models are available.")

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        if not self.current_model_path:
            dataset_prefs = get_dataset_preferences(self.app, self._dataset_pref_key())
            name = dataset_prefs.get("model_name")
            if isinstance(name, str):
                self.current_model_path = name

        for model in self.app.available_models:
            self.model_combo.addItem(model)

        if self.current_model_path:
            index = self.model_combo.findText(self.current_model_path)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)

    def _on_model_selection_changed(self, model_name: str) -> None:
        if self._updating_context:
            return
        normalized = model_name.strip()
        if normalized and normalized in self.app.available_models:
            self.current_model_path = normalized
        else:
            self.current_model_path = None
        self._persist_context()
        self._propagate_context_to_samples()
        self._refresh_menu_state()

    def _on_facet_selection_changed(self, index: int) -> None:
        if self._updating_context or not self.facet_combo:
            return
        facet_id = self.facet_combo.itemData(index)
        if isinstance(facet_id, int) and facet_id in self._facet_map:
            self.current_facet = self._facet_map[facet_id]
            self.current_facet_id = facet_id
        else:
            self.current_facet = None
            self.current_facet_id = None
        self._persist_context()
        self._propagate_context_to_samples()
        self._refresh_menu_state()

    def _persist_context(self) -> None:
        if not hasattr(self.app, "config"):
            raise RuntimeError("Application configuration is not available.")
        update_dataset_preferences(self.app, self._dataset_pref_key(), {
            "facet_id": self.current_facet.id if self.current_facet else None,
            "model_name": self.current_model_path,
        })

    def _propagate_context_to_samples(self) -> None:
        for tab_info in self.tabs.values():
            widget = tab_info.get("widget")
            if isinstance(widget, WidgetSample):
                self._apply_context_to_sample(widget)
        self._update_sidebar_for_facet()

    def _apply_context_to_sample(self, sample_widget: WidgetSample) -> None:
        sample_widget.set_active_context(self.current_facet, self.current_model_path)

    def _update_sidebar_for_facet(self) -> None:
        if hasattr(self.sidebar, "set_current_facet"):
            self.sidebar.set_current_facet(self.current_facet)

    def populate_tabs(self) -> None:
        """Populate the main tab area with dataset content."""
        self.overview_widget = self.create_overview_tab()
        self._register_tab(self.overview_widget, "Overview", "overview", entity_id=0, closable=False, focus=False)
        sample_widget_id = self.create_sample_tab(None, focus=True)
        self._focus_widget(self.tabs[sample_widget_id]["widget"])

    def create_overview_tab(self) -> QWidget:
        """Create the overview tab showing dataset statistics."""
        overview_widget = QWidget()
        layout = QVBoxLayout(overview_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        info_label = QLabel(f"""
        <h2>Dataset Overview</h2>
        <p><b>Database Path:</b> {self.dataset.db_path}</p>
        <p><b>Status:</b> {'Connected' if self.dataset.session else 'Not Connected'}</p>
        <br>
        <h3>Statistics</h3>
        <p><i>Statistics will be implemented when database queries are available.</i></p>
        <ul>
        <li>Total Samples: TBD</li>
        <li>Total Prompts: TBD</li>
        <li>Total Completions: TBD</li>
        <li>Available Facets: TBD</li>
        </ul>
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        layout.addStretch()
        return overview_widget

    def _register_tab(
        self,
        widget: QWidget,
        title: str,
        tab_type: str,
        entity_id: int,
        *,
        closable: bool = True,
        focus: bool = False,
    ) -> int:
        widget_id = id(widget)
        self.tabs[widget_id] = {
            "type": tab_type,
            "id": entity_id,
            "title": title,
            "widget": widget,
            "closable": closable,
        }
        index = self.tab_widget.addTab(widget, title)
        if focus:
            self.tab_widget.setCurrentIndex(index)
        return widget_id

    def _set_tab_title(self, widget_id: int, title: str) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        tab_info["title"] = title
        index = self._tab_index(widget_id)
        if index >= 0:
            self.tab_widget.setTabText(index, title)

    def create_sample_tab(self, sample: Sample | None, *, focus: bool = True) -> int:
        """Create a new tab for editing/viewing a sample."""
        mapped_model = None
        if self.current_model_path:
            mapped_model = self.app.providers_manager.get_mapped_model(self.current_model_path)
        sample_widget = WidgetSample(self, self.app, sample=sample, active_facet=self.current_facet, active_model=mapped_model)
        sample_id = sample.id if sample and getattr(sample, "id", None) else 0
        title = f"S: {sample.title}" if sample else "New Sample"
        widget_id = self._register_tab(sample_widget, title, "sample", sample_id, focus=focus)
        self._apply_context_to_sample(sample_widget)
        sample_widget.sample_saved.connect(lambda saved, wid=widget_id: self._on_sample_saved(wid, saved))
        sample_widget.sample_copied.connect(lambda original, wid=widget_id: self._on_sample_copied(wid, original))
        sample_widget.sample_deleted.connect(lambda deleted, wid=widget_id: self._on_sample_deleted(wid, deleted))
        return widget_id

    def create_facet_tab(self, facet: Facet | None, *, focus: bool = True) -> int:
        """Create a new tab for editing/viewing a facet."""
        facet_widget = WidgetFacet(self, self.app, self.dataset, facet)
        facet_id = facet.id if facet else 0
        title = f"F: {facet.name}" if facet else "New Facet"
        widget_id = self._register_tab(facet_widget, title, "facet", facet_id, focus=focus)
        facet_widget.facet_saved.connect(lambda saved, wid=widget_id: self._on_facet_saved(wid, saved))
        facet_widget.facet_deleted.connect(lambda deleted, wid=widget_id: self._on_facet_deleted(wid, deleted))
        facet_widget.facet_cancelled.connect(lambda wid=widget_id: self._on_facet_cancelled(wid))
        return widget_id

    def create_tag_tab(self, tag: Tag | None, *, focus: bool = True) -> int:
        """Create a new tab for editing or creating a tag."""

        tag_widget = WidgetTag(self, self.app, self.dataset, tag)
        tag_id = tag.id if tag else 0
        title = f"T: {tag.name}" if tag else "New Tag"
        widget_id = self._register_tab(tag_widget, title, "tag", tag_id, focus=focus)
        tag_widget.tag_saved.connect(lambda saved, wid=widget_id: self._on_tag_saved(wid, saved))
        tag_widget.tag_deleted.connect(lambda deleted, wid=widget_id: self._on_tag_deleted(wid, deleted))
        tag_widget.tag_cancelled.connect(lambda wid=widget_id: self._on_tag_cancelled(wid))
        return widget_id

    def create_sample_filter_tab(self, sample_filter: SampleFilter | None, *, focus: bool = True) -> int:
        """Create a new tab for editing or creating a sample filter."""

        filter_widget = WidgetSampleFilter(self, self.app, self.dataset, sample_filter)
        filter_id = sample_filter.id if sample_filter else 0
        title = f"SF: {sample_filter.name}" if sample_filter else "New Sample Filter"
        widget_id = self._register_tab(filter_widget, title, "sample_filter", filter_id, focus=focus)
        filter_widget.sample_filter_saved.connect(lambda saved, wid=widget_id: self._on_sample_filter_saved(wid, saved))
        filter_widget.sample_filter_deleted.connect(lambda deleted, wid=widget_id: self._on_sample_filter_deleted(wid, deleted))
        filter_widget.sample_filter_cancelled.connect(lambda wid=widget_id: self._on_sample_filter_cancelled(wid))
        return widget_id

    def create_export_template_tab(self, template: ExportTemplate | None, *, focus: bool = True) -> int:
        """Create a new tab for managing an export template."""

        template_widget = WidgetExportTemplate(self, self.app, self.dataset, template)
        template_id = template.id if template else 0
        title = f"X: {template.name}" if template else "New Export Template"
        widget_id = self._register_tab(template_widget, title, "export_template", template_id, focus=focus)
        template_widget.template_saved.connect(lambda saved, wid=widget_id: self._on_export_template_saved(wid, saved))
        template_widget.template_deleted.connect(lambda deleted, wid=widget_id: self._on_export_template_deleted(wid, deleted))
        template_widget.template_copied.connect(self._on_export_template_copied)
        return widget_id

    def _on_sample_saved(self, widget_id: int, sample: Sample) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info or not sample:
            return
        create_new_blank = tab_info["id"] == 0
        tab_info["id"] = sample.id
        self._set_tab_title(widget_id, f"S: {sample.title}")
        if create_new_blank:
            self.create_sample_tab(None, focus=False)

    def _on_sample_copied(self, _widget_id: int, sample: Sample) -> None:
        new_sample = sample.new_copy()
        new_tab_id = self.create_sample_tab(new_sample, focus=True)
        self._focus_widget(self.tabs[new_tab_id]["widget"])

    def _on_sample_deleted(self, widget_id: int, _sample: Sample | None) -> None:
        """
        Handle sample deletion: close the tab.

        Args:
            widget_id: The widget ID of the sample tab
            _sample: The deleted sample (may be None for partially saved samples)
        """
        # Close the sample tab
        index = self._tab_index(widget_id)
        if index >= 0:
            self.close_tab(index)

    def _on_facet_saved(self, widget_id: int, facet: Facet) -> None:
        """Handle facet save event: update tab, refresh sidebar and facet combobox."""
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        tab_info["id"] = facet.id
        self._set_tab_title(widget_id, f"F: {facet.name}")
        # Refresh navigation sidebar to show updated facet list
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()
        # Refresh facet combobox to include the new/updated facet
        self.set_facets()

    def _on_facet_deleted(self, widget_id: int, _facet: Facet) -> None:
        """Handle facet deletion: refresh sidebar and facet combobox, close tab."""
        # Refresh navigation sidebar to remove deleted facet
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()
        # Refresh facet combobox to remove deleted facet
        self.set_facets()
        # Close the facet tab
        index = self._tab_index(widget_id)
        if index >= 0:
            self.close_tab(index)

    def _on_facet_cancelled(self, widget_id: int) -> None:
        """Handle facet editing cancellation: close tab if it was a new unsaved facet."""
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        # Close the tab if it was for a new unsaved facet
        if tab_info.get("id") == 0:
            index = self._tab_index(widget_id)
            if index >= 0:
                self.close_tab(index)

    def _on_tag_saved(self, widget_id: int, tag: Tag) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        tab_info["id"] = tag.id
        self._set_tab_title(widget_id, f"T: {tag.name}")
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()

    def _on_tag_deleted(self, widget_id: int, _tag: Tag) -> None:
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()
        index = self._tab_index(widget_id)
        if index >= 0:
            self.close_tab(index)

    def _on_tag_cancelled(self, widget_id: int) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        if tab_info.get("id") == 0:
            index = self._tab_index(widget_id)
            if index >= 0:
                self.close_tab(index)

    def _on_sample_filter_saved(self, widget_id: int, sample_filter: SampleFilter) -> None:
        """Handle sample filter save event: update tab and refresh sidebar."""
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        tab_info["id"] = sample_filter.id
        self._set_tab_title(widget_id, f"SF: {sample_filter.name}")
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()

    def _on_sample_filter_deleted(self, widget_id: int, _sample_filter: SampleFilter) -> None:
        """Handle sample filter deletion: refresh sidebar and close tab."""
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()
        index = self._tab_index(widget_id)
        if index >= 0:
            self.close_tab(index)

    def _on_sample_filter_cancelled(self, widget_id: int) -> None:
        """Handle sample filter cancellation: close tab if new filter."""
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        if tab_info.get("id") == 0:
            index = self._tab_index(widget_id)
            if index >= 0:
                self.close_tab(index)

    def _on_export_template_saved(self, widget_id: int, template: ExportTemplate) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        tab_info["id"] = template.id
        self._set_tab_title(widget_id, f"X: {template.name}")
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()

    def _on_export_template_deleted(self, widget_id: int, _template: ExportTemplate) -> None:
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()
        index = self._tab_index(widget_id)
        if index >= 0:
            self.close_tab(index)

    def _on_export_template_copied(self, template: ExportTemplate) -> None:
        widget_id = self.create_export_template_tab(template, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()

    def _focus_widget(self, widget: QWidget | None) -> None:
        if not widget:
            return
        index = self.tab_widget.indexOf(widget)
        if index >= 0:
            self.tab_widget.setCurrentIndex(index)

    def _tab_index(self, widget_id: int) -> int:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return -1
        return self.tab_widget.indexOf(tab_info["widget"])

    def _find_tab_by(self, tab_type: str, entity_id: int) -> int | None:
        for widget_id, tab_info in self.tabs.items():
            if tab_info["type"] == tab_type and tab_info["id"] == entity_id:
                return widget_id
        return None

    def _open_export_template_by_id(self, template_id: int) -> None:
        """Open an export template tab for the given identifier if available."""

        template = ExportTemplate.get_by_id(self.dataset, template_id)
        if not template:
            return
        widget_id = self.create_export_template_tab(template, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])

    def _open_tag_by_id(self, tag_id: int) -> None:
        """Open a tag editing tab for the provided tag identifier."""

        tag = Tag.get_by_id(self.dataset, tag_id)
        if not tag:
            return
        widget_id = self.create_tag_tab(tag, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])

    def _open_sample_filter_by_id(self, filter_id: int) -> None:
        """Open a sample filter editing tab for the provided filter identifier."""

        sample_filter = SampleFilter.get_by_id(self.dataset, filter_id)
        if not sample_filter:
            return
        widget_id = self.create_sample_filter_tab(sample_filter, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])

    def _open_sample_by_id(self, sample_id: int) -> None:
        """Open a sample tab, retrieving data using the dataset session."""

        sample = None
        if self.dataset.session is not None:
            sample = self.dataset.session.get(Sample, sample_id)
        if not sample:
            return
        widget_id = self.create_sample_tab(sample, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])

    def _open_prompt_by_id(self, prompt_id: int) -> None:
        """Open a sample tab based on a prompt identifier."""

        if self.dataset.session is None:
            return
        prompt = self.dataset.session.get(PromptRevision, prompt_id)
        if not prompt:
            return
        sample = Sample.from_prompt_revision(self.dataset, prompt)
        widget_id = self.create_sample_tab(sample, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])

    def _open_facet_by_id(self, facet_id: int) -> None:
        """Open a facet tab for the given identifier."""

        if self.dataset.session is None:
            return
        facet = self.dataset.session.get(Facet, facet_id)
        if not facet:
            return
        widget_id = self.create_facet_tab(facet, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])

    def _on_navigation_item_selected(self, item_type: str, item_id: int) -> None:
        """Handle sidebar navigation selections by opening the relevant tab."""

        if self.dataset.session is None:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        normalized_type = item_type.lower()
        existing_widget_id = self._find_tab_by(normalized_type, item_id)
        if existing_widget_id:
            self._focus_widget(self.tabs[existing_widget_id]["widget"])
            return

        if normalized_type == "completion":
            self.log.info("Navigation for %s is not implemented yet.", normalized_type)
            return

        handler_map = {
            "export_template": self._open_export_template_by_id,
            "tag": self._open_tag_by_id,
            "sample": self._open_sample_by_id,
            "sample_filter": self._open_sample_filter_by_id,
            "prompt": self._open_prompt_by_id,
            "facet": self._open_facet_by_id,
        }
        handler = handler_map.get(normalized_type)
        if handler:
            handler(item_id)
        else:
            self.log.warning("Navigation for %s is not implemented.", normalized_type)

    def _on_new_item_requested(self, item_type: str) -> None:
        normalized_type = item_type.lower()
        self.log.info("Request to create new item of type: %s", normalized_type)
        if normalized_type == "sample":
            widget_id = self.create_sample_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return
        if normalized_type == "facet":
            widget_id = self.create_facet_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return
        if normalized_type == "tag":
            widget_id = self.create_tag_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return
        if normalized_type == "sample filter":
            widget_id = self.create_sample_filter_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return
        if normalized_type == "export_template":
            widget_id = self.create_export_template_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return

        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        label = QLabel(f"Creation UI for new {normalized_type} will be implemented.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        tab_title = f"New {normalized_type.title()}"
        widget_id = self._register_tab(placeholder, tab_title, normalized_type, 0, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])

    def _on_tab_context_menu(self, position: QPoint) -> None:
        tab_bar = self.tab_widget.tabBar()
        if tab_bar is None:
            return
        index = tab_bar.tabAt(position)
        if index < 0:
            return
        widget = self.tab_widget.widget(index)
        if widget is None:
            return
        widget_id = id(widget)
        tab_info = self.tabs.get(widget_id)
        if not tab_info or not tab_info.get("closable", True):
            return
        menu = QMenu(self)
        close_action = menu.addAction("Close Tab")
        action = menu.exec(tab_bar.mapToGlobal(position))
        if action == close_action:
            self.close_tab(index)

    def close_tab(self, index: int) -> None:
        """Close the tab at the provided index if it is allowed to close."""

        if index < 0:
            return
        widget = self.tab_widget.widget(index)
        if widget is None:
            return
        widget_id = id(widget)
        tab_info = self.tabs.get(widget_id)
        if not tab_info or not tab_info.get("closable", True):
            return
        self.tab_widget.removeTab(index)
        widget.deleteLater()
        del self.tabs[widget_id]
