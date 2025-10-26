"""
Model Manager window for configuring LLM inference models.

Provides GUI for managing three types of models:
- Local llama.cpp models with GGUF files
- Local Ollama models
- Remote Completions API endpoints
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


class ModelManagerWindow(QDialog):
    """
    Modal dialog for managing LLM inference models.

    Allows users to configure local llama.cpp models, Ollama models, and remote API endpoints.
    Changes are saved to the application configuration file and propagated to the providers manager.
    """

    def __init__(self, parent: QWidget | None, app: "pyFadeApp") -> None:
        """
        Initialize the Model Manager window.

        Args:
            parent: Parent widget
            app: Main application instance
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.app = app

        # Store model configurations
        self.models_config: list[dict] = []
        self._load_current_config()

        self.setWindowTitle("Model Manager")
        self.setMinimumSize(800, 600)
        self.setModal(True)

        self.setup_ui()

    def _load_current_config(self) -> None:
        """Load current model configurations from app config."""
        # Make a deep copy of the current models config
        self.models_config = [dict(model) for model in self.app.config.models]

    def setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header_label = QLabel("<h2>Model Manager</h2>")
        layout.addWidget(header_label)

        instructions = QLabel("Configure LLM inference models for use in pyFADE.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Tab widget for different model types
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("model-manager-tabs")

        # Create tabs for each model type
        self.llamacpp_tab = LlamaCppModelsTab(self)
        self.ollama_tab = OllamaModelsTab(self)
        self.remote_api_tab = RemoteAPIModelsTab(self)

        self.tab_widget.addTab(self.llamacpp_tab, "llama.cpp Models")
        self.tab_widget.addTab(self.ollama_tab, "Ollama Models")
        self.tab_widget.addTab(self.remote_api_tab, "Remote API")

        layout.addWidget(self.tab_widget)

        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Load data into tabs
        self._populate_tabs()

    def _populate_tabs(self) -> None:
        """Populate all tabs with current model configurations."""
        self.llamacpp_tab.load_models(self.models_config)
        self.ollama_tab.load_models(self.models_config)
        self.remote_api_tab.load_models(self.models_config)

    def _on_save(self) -> None:
        """Save model configurations and apply changes."""
        # Collect all model configurations from tabs
        new_models_config: list[dict] = []

        # Collect from llama.cpp tab
        new_models_config.extend(self.llamacpp_tab.get_models())

        # Collect from Ollama tab
        new_models_config.extend(self.ollama_tab.get_models())

        # Collect from Remote API tab
        new_models_config.extend(self.remote_api_tab.get_models())

        # Validate configurations
        if not self._validate_models(new_models_config):
            return

        # Save to app config
        self.app.config.models = new_models_config
        self.app.config.save()

        # Reload providers manager with new configurations
        self.app.providers_manager.reload_models(new_models_config)
        self.app.available_models = list(self.app.providers_manager.model_provider_map.keys())

        # Update GUI if dataset widget exists
        if self.app.dataset_widget is not None:
            self.app.dataset_widget._populate_model_selector()  # pylint: disable=protected-access

        self.log.info("Model configurations saved and applied.")
        QMessageBox.information(self, "Success", "Model configurations saved and applied successfully.")
        self.accept()

    def _validate_models(self, models: list[dict]) -> bool:
        """
        Validate model configurations before saving.

        Returns True if all models are valid, False otherwise.
        """
        model_ids = set()
        for model in models:
            model_id = model.get("id")
            if not model_id:
                QMessageBox.warning(self, "Validation Error", "All models must have an ID.")
                return False

            if model_id in model_ids:
                QMessageBox.warning(self, "Validation Error", f"Duplicate model ID found: {model_id}")
                return False
            model_ids.add(model_id)

            # Validate that model has at least one backend (gguf or ollama_id)
            has_gguf = bool(model.get("gguf"))
            has_ollama = bool(model.get("ollama_id"))
            if not has_gguf and not has_ollama:
                QMessageBox.warning(self, "Validation Error", f"Model '{model_id}' must have either GGUF path or Ollama ID.")
                return False

        return True


class LlamaCppModelsTab(QWidget):
    """Tab for managing local llama.cpp models."""

    def __init__(self, parent: ModelManagerWindow) -> None:
        super().__init__(parent)
        self.manager = parent
        self.log = logging.getLogger(self.__class__.__name__)
        self.models: list[dict] = []
        self.setup_ui()

    def setup_ui(self) -> None:
        """Setup the UI for llama.cpp models tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Instructions
        instructions = QLabel(
            "Configure local llama.cpp models. Each model requires a GGUF file path and can optionally include LoRA adapters.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Model list
        self.model_list = QListWidget()
        self.model_list.setObjectName("llamacpp-model-list")
        self.model_list.currentItemChanged.connect(self._on_model_selected)
        layout.addWidget(self.model_list)

        # Buttons for list management
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Model")
        self.add_button.clicked.connect(self._on_add_model)
        button_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("Remove Model")
        self.remove_button.clicked.connect(self._on_remove_model)
        self.remove_button.setEnabled(False)
        button_layout.addWidget(self.remove_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Model details form
        details_group = QGroupBox("Model Details")
        details_layout = QFormLayout(details_group)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g., gemma3:1b-it-q4_K_M")
        details_layout.addRow("Model ID:", self.id_edit)

        # GGUF file path
        gguf_layout = QHBoxLayout()
        self.gguf_edit = QLineEdit()
        self.gguf_edit.setPlaceholderText("Path to GGUF file")
        gguf_layout.addWidget(self.gguf_edit)

        self.gguf_browse_button = QPushButton("Browse...")
        self.gguf_browse_button.clicked.connect(self._on_browse_gguf)
        gguf_layout.addWidget(self.gguf_browse_button)

        details_layout.addRow("GGUF File:", gguf_layout)

        # LoRA file path (optional)
        lora_layout = QHBoxLayout()
        self.lora_edit = QLineEdit()
        self.lora_edit.setPlaceholderText("Path to LoRA file (optional)")
        lora_layout.addWidget(self.lora_edit)

        self.lora_browse_button = QPushButton("Browse...")
        self.lora_browse_button.clicked.connect(self._on_browse_lora)
        lora_layout.addWidget(self.lora_browse_button)

        details_layout.addRow("LoRA File:", lora_layout)

        # Apply changes button
        self.apply_button = QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self._on_apply_changes)
        self.apply_button.setEnabled(False)
        details_layout.addRow("", self.apply_button)

        layout.addWidget(details_group)

        # Connect change signals
        self.id_edit.textChanged.connect(self._on_form_changed)
        self.gguf_edit.textChanged.connect(self._on_form_changed)
        self.lora_edit.textChanged.connect(self._on_form_changed)

    def load_models(self, models_config: list[dict]) -> None:
        """Load llama.cpp models from configuration."""
        self.models = []
        self.model_list.clear()

        for model in models_config:
            if "gguf" in model:
                # This is a llama.cpp model
                self.models.append(dict(model))
                item = QListWidgetItem(model.get("id", "Unnamed"))
                self.model_list.addItem(item)

    def get_models(self) -> list[dict]:
        """Get all llama.cpp model configurations."""
        return self.models

    def _on_model_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        """Handle model selection in the list."""
        if current is None:
            self.remove_button.setEnabled(False)
            self._clear_form()
            return

        self.remove_button.setEnabled(True)
        index = self.model_list.row(current)
        if 0 <= index < len(self.models):
            self._populate_form(self.models[index])

    def _populate_form(self, model: dict) -> None:
        """Populate the form with model data."""
        self.id_edit.setText(model.get("id", ""))
        self.gguf_edit.setText(model.get("gguf", ""))
        self.lora_edit.setText(model.get("lora", ""))
        self.apply_button.setEnabled(False)

    def _clear_form(self) -> None:
        """Clear all form fields."""
        self.id_edit.clear()
        self.gguf_edit.clear()
        self.lora_edit.clear()
        self.apply_button.setEnabled(False)

    def _on_form_changed(self) -> None:
        """Handle form field changes."""
        current_item = self.model_list.currentItem()
        if current_item is not None:
            self.apply_button.setEnabled(True)

    def _on_add_model(self) -> None:
        """Add a new llama.cpp model."""
        new_model = {
            "id": "new_model",
            "gguf": "",
        }
        self.models.append(new_model)
        item = QListWidgetItem("new_model")
        self.model_list.addItem(item)
        self.model_list.setCurrentItem(item)

    def _on_remove_model(self) -> None:
        """Remove the selected model."""
        current_item = self.model_list.currentItem()
        if current_item is None:
            return

        index = self.model_list.row(current_item)
        if 0 <= index < len(self.models):
            model_id = self.models[index].get("id", "Unknown")
            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove model '{model_id}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                del self.models[index]
                self.model_list.takeItem(index)
                self._clear_form()

    def _on_apply_changes(self) -> None:
        """Apply form changes to the selected model."""
        current_item = self.model_list.currentItem()
        if current_item is None:
            return

        index = self.model_list.row(current_item)
        if 0 <= index < len(self.models):
            model = self.models[index]
            model["id"] = self.id_edit.text().strip()
            model["gguf"] = self.gguf_edit.text().strip()

            lora_path = self.lora_edit.text().strip()
            if lora_path:
                model["lora"] = lora_path
            elif "lora" in model:
                del model["lora"]

            # Update list item text
            current_item.setText(model["id"])
            self.apply_button.setEnabled(False)

    def _on_browse_gguf(self) -> None:
        """Browse for GGUF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GGUF File",
            "",
            "GGUF Files (*.gguf);;All Files (*)",
        )
        if file_path:
            self.gguf_edit.setText(file_path)

    def _on_browse_lora(self) -> None:
        """Browse for LoRA file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select LoRA File",
            "",
            "LoRA Files (*.gguf *.bin);;All Files (*)",
        )
        if file_path:
            self.lora_edit.setText(file_path)


class OllamaModelsTab(QWidget):
    """Tab for managing Ollama models."""

    def __init__(self, parent: ModelManagerWindow) -> None:
        super().__init__(parent)
        self.manager = parent
        self.log = logging.getLogger(self.__class__.__name__)
        self.models: list[dict] = []
        self.setup_ui()

    def setup_ui(self) -> None:
        """Setup the UI for Ollama models tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Instructions
        instructions = QLabel("Configure Ollama models. Models can be imported from local Ollama registry or added manually.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Import from registry button
        import_button = QPushButton("Import All Models from Ollama Registry")
        import_button.clicked.connect(self._on_import_from_registry)
        layout.addWidget(import_button)

        # Model list
        self.model_list = QListWidget()
        self.model_list.setObjectName("ollama-model-list")
        self.model_list.currentItemChanged.connect(self._on_model_selected)
        layout.addWidget(self.model_list)

        # Buttons for list management
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Model")
        self.add_button.clicked.connect(self._on_add_model)
        button_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("Remove Model")
        self.remove_button.clicked.connect(self._on_remove_model)
        self.remove_button.setEnabled(False)
        button_layout.addWidget(self.remove_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Model details form
        details_group = QGroupBox("Model Details")
        details_layout = QFormLayout(details_group)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g., llama3:8b")
        details_layout.addRow("Model ID:", self.id_edit)

        self.ollama_id_edit = QLineEdit()
        self.ollama_id_edit.setPlaceholderText("Ollama model ID (use MAIN_ID to use Model ID)")
        details_layout.addRow("Ollama ID:", self.ollama_id_edit)

        # Apply changes button
        self.apply_button = QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self._on_apply_changes)
        self.apply_button.setEnabled(False)
        details_layout.addRow("", self.apply_button)

        layout.addWidget(details_group)

        # Connect change signals
        self.id_edit.textChanged.connect(self._on_form_changed)
        self.ollama_id_edit.textChanged.connect(self._on_form_changed)

    def load_models(self, models_config: list[dict]) -> None:
        """Load Ollama models from configuration."""
        self.models = []
        self.model_list.clear()

        for model in models_config:
            if "ollama_id" in model and "gguf" not in model:
                # This is an Ollama-only model
                self.models.append(dict(model))
                item = QListWidgetItem(model.get("id", "Unnamed"))
                self.model_list.addItem(item)

    def get_models(self) -> list[dict]:
        """Get all Ollama model configurations."""
        return self.models

    def _on_model_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        """Handle model selection in the list."""
        if current is None:
            self.remove_button.setEnabled(False)
            self._clear_form()
            return

        self.remove_button.setEnabled(True)
        index = self.model_list.row(current)
        if 0 <= index < len(self.models):
            self._populate_form(self.models[index])

    def _populate_form(self, model: dict) -> None:
        """Populate the form with model data."""
        self.id_edit.setText(model.get("id", ""))
        self.ollama_id_edit.setText(model.get("ollama_id", ""))
        self.apply_button.setEnabled(False)

    def _clear_form(self) -> None:
        """Clear all form fields."""
        self.id_edit.clear()
        self.ollama_id_edit.clear()
        self.apply_button.setEnabled(False)

    def _on_form_changed(self) -> None:
        """Handle form field changes."""
        current_item = self.model_list.currentItem()
        if current_item is not None:
            self.apply_button.setEnabled(True)

    def _on_add_model(self) -> None:
        """Add a new Ollama model."""
        new_model = {
            "id": "new_ollama_model",
            "ollama_id": "MAIN_ID",
        }
        self.models.append(new_model)
        item = QListWidgetItem("new_ollama_model")
        self.model_list.addItem(item)
        self.model_list.setCurrentItem(item)

    def _on_remove_model(self) -> None:
        """Remove the selected model."""
        current_item = self.model_list.currentItem()
        if current_item is None:
            return

        index = self.model_list.row(current_item)
        if 0 <= index < len(self.models):
            model_id = self.models[index].get("id", "Unknown")
            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove model '{model_id}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                del self.models[index]
                self.model_list.takeItem(index)
                self._clear_form()

    def _on_apply_changes(self) -> None:
        """Apply form changes to the selected model."""
        current_item = self.model_list.currentItem()
        if current_item is None:
            return

        index = self.model_list.row(current_item)
        if 0 <= index < len(self.models):
            model = self.models[index]
            model["id"] = self.id_edit.text().strip()
            model["ollama_id"] = self.ollama_id_edit.text().strip()

            # Update list item text
            current_item.setText(model["id"])
            self.apply_button.setEnabled(False)

    def _on_import_from_registry(self) -> None:
        """Import all models from Ollama registry."""
        if self.manager.app.providers_manager.ollama_registry is None:
            QMessageBox.warning(
                self,
                "Registry Not Available",
                "Ollama registry is not configured. Please set the ollama_models_dir in your configuration.",
            )
            return

        try:
            imported_count = self._import_models_from_registry()
            QMessageBox.information(self, "Import Complete", f"Imported {imported_count} models from Ollama registry.")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.log.error("Failed to import from Ollama registry: %s", exc)
            QMessageBox.warning(self, "Import Failed", f"Failed to import models: {exc}")

    def _import_models_from_registry(self) -> int:
        """
        Import models from Ollama registry.

        Returns the number of imported models.
        """
        registry = self.manager.app.providers_manager.ollama_registry
        manifests_dir = registry.manifests_dir / "registry.ollama.ai"

        if not manifests_dir.exists():
            QMessageBox.warning(self, "Registry Empty", "No models found in Ollama registry.")
            return 0

        imported_count = 0
        for namespace_dir in manifests_dir.iterdir():
            if not namespace_dir.is_dir():
                continue

            imported_count += self._import_namespace_models(namespace_dir)

        return imported_count

    def _import_namespace_models(self, namespace_dir) -> int:
        """
        Import models from a specific namespace directory.

        Returns the number of imported models.
        """
        imported_count = 0
        namespace = namespace_dir.name

        for family_dir in namespace_dir.iterdir():
            if not family_dir.is_dir():
                continue

            family = family_dir.name
            for model_file in family_dir.iterdir():
                if not model_file.is_file():
                    continue

                subtype = model_file.name
                model_id = self._build_model_id(namespace, family, subtype)

                if self._add_model_if_not_exists(model_id):
                    imported_count += 1

        return imported_count

    def _build_model_id(self, namespace: str, family: str, subtype: str) -> str:
        """Build model ID from namespace, family, and subtype."""
        if namespace == "library":
            return f"{family}:{subtype}" if subtype != "latest" else family
        return f"{namespace}/{family}:{subtype}" if subtype != "latest" else f"{namespace}/{family}"

    def _add_model_if_not_exists(self, model_id: str) -> bool:
        """
        Add model if it doesn't already exist.

        Returns True if model was added, False otherwise.
        """
        existing = any(m.get("id") == model_id for m in self.models)
        if not existing:
            new_model = {
                "id": model_id,
                "ollama_id": "MAIN_ID",
            }
            self.models.append(new_model)
            item = QListWidgetItem(model_id)
            self.model_list.addItem(item)
            return True
        return False


class RemoteAPIModelsTab(QWidget):
    """Tab for managing remote API endpoints."""

    def __init__(self, parent: ModelManagerWindow) -> None:
        super().__init__(parent)
        self.manager = parent
        self.log = logging.getLogger(self.__class__.__name__)
        self.models: list[dict] = []
        self.setup_ui()

    def setup_ui(self) -> None:
        """Setup the UI for remote API models tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Instructions
        instructions = QLabel(
            "Configure remote Completions API endpoints. Currently for display purposes only - full implementation coming soon.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Note about future implementation
        note = QLabel("<i>Note: Remote API configuration is a placeholder for future implementation.</i>")
        note.setWordWrap(True)
        layout.addWidget(note)

        # Model list (disabled for now)
        self.model_list = QListWidget()
        self.model_list.setObjectName("remote-api-model-list")
        self.model_list.setEnabled(False)
        layout.addWidget(self.model_list)

        layout.addStretch()

    def load_models(self, models_config: list[dict]) -> None:  # pylint: disable=unused-argument
        """Load remote API models from configuration."""
        # Remote API not implemented yet
        self.models = []

    def get_models(self) -> list[dict]:
        """Get all remote API model configurations."""
        return self.models
