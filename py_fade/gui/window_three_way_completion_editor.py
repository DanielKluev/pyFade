"""Three-column editor window for comparing and revising completions.

The window presents the prompt, the frozen original completion, and an editable
column for a revised completion. Users can either hand-edit the completion or
request an automatic continuation from the same provider that produced the
original text. When saving, the dialog can archive the original completion and
optionally record a facet preference so downstream tooling understands which
variant should be preferred.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating

if TYPE_CHECKING:  # pragma: no cover - import hints only
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.providers.llm_response import LLMResponse
    from py_fade.providers.providers_manager import MappedModel


class ThreeWayCompletionEditorWindow(QDialog):
    """Modal dialog that offers manual and continued-edit flows for completions."""

    completion_saved = pyqtSignal(PromptCompletion)

    def __init__(
        self,
        app: "pyFadeApp",
        dataset: "DatasetDatabase",
        completion: PromptCompletion,
        *,
        facet: "Facet | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.app = app
        self.dataset = dataset
        self.original_completion: PromptCompletion | None = None
        self.active_facet: "Facet | None" = facet
        self.generated_response: "LLMResponse | None" = None
        self._generated_text_cache: str | None = None
        self._original_completion_text: str = ""

        self.prompt_edit: QPlainTextEdit | None = None
        self.original_edit: QPlainTextEdit | None = None
        self.new_edit: QPlainTextEdit | None = None
        self.manual_radio: QRadioButton | None = None
        self.generate_radio: QRadioButton | None = None
        self.archive_checkbox: QCheckBox | None = None
        self.pairwise_checkbox: QCheckBox | None = None
        self.generate_button: QPushButton | None = None
        self.save_button: QPushButton | None = None
        self.status_label: QLabel | None = None

        self.setWindowTitle("Three-way completion editor")
        self.setModal(True)
        self.resize(1200, 740)

        self.setup_ui()
        self.connect_signals()
        self.set_facet(self.active_facet)
        self.set_completion(completion)

    def setup_ui(self) -> None:
        """Build the three-column layout along with controls and actions."""

        monospace = QFont("Courier New")
        monospace.setPointSize(10)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(
            "Compare the prompt, original completion, and revised text side-by-side.",
            self,
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        self.prompt_edit = self._build_column(
            splitter,
            title="Prompt",
            background="#F5F5F5",
            font=monospace,
            read_only=True,
        )
        self.original_edit = self._build_column(
            splitter,
            title="Original completion",
            background="#FFF3E0",
            font=monospace,
            read_only=True,
        )
        self.new_edit = self._build_column(
            splitter,
            title="New completion",
            background="#E8F5E9",
            font=monospace,
            read_only=False,
        )
        splitter.setSizes([1, 1, 1])
        layout.addWidget(splitter, stretch=1)

        roles_layout = QHBoxLayout()
        roles_layout.setSpacing(10)
        roles_label = QLabel("Role:", self)
        roles_layout.addWidget(roles_label)

        button_group = QButtonGroup(self)
        self.manual_radio = QRadioButton("Manual edit", self)
        self.manual_radio.setChecked(True)
        button_group.addButton(self.manual_radio)
        roles_layout.addWidget(self.manual_radio)

        self.generate_radio = QRadioButton("Continue generation", self)
        button_group.addButton(self.generate_radio)
        roles_layout.addWidget(self.generate_radio)
        roles_layout.addStretch()
        layout.addLayout(roles_layout)

        options_layout = QHBoxLayout()
        options_layout.setSpacing(10)
        self.archive_checkbox = QCheckBox("Archive original on save", self)
        self.archive_checkbox.setChecked(True)
        options_layout.addWidget(self.archive_checkbox)

        self.pairwise_checkbox = QCheckBox(
            "Prefer new completion for active facet",
            self,
        )
        options_layout.addWidget(self.pairwise_checkbox)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        self.generate_button = QPushButton("Generate continuation", self)
        self.generate_button.setEnabled(False)
        actions_layout.addWidget(self.generate_button)

        self.save_button = QPushButton("Save", self)
        self.save_button.setEnabled(False)
        actions_layout.addWidget(self.save_button)

        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        actions_layout.addWidget(cancel_button)

        layout.addLayout(actions_layout)

        self.status_label = QLabel("", self)
        layout.addWidget(self.status_label)

    def connect_signals(self) -> None:
        """Wire UI widgets to handlers that maintain dialog state."""

        if not self.new_edit or not self.manual_radio or not self.generate_radio:
            raise RuntimeError("Editor was not initialised correctly before wiring signals.")

        self.manual_radio.toggled.connect(self._on_role_changed)
        self.generate_radio.toggled.connect(self._on_role_changed)
        self.new_edit.textChanged.connect(self._on_new_text_changed)

        if self.generate_button:
            self.generate_button.clicked.connect(self._on_generate_clicked)
        if self.save_button:
            self.save_button.clicked.connect(self._on_save_clicked)

    def set_completion(self, completion: PromptCompletion | None) -> None:
        """Populate editor columns with *completion* or clear them when ``None``."""

        if completion is None:
            self.original_completion = None
            for editor in (self.prompt_edit, self.original_edit, self.new_edit):
                if editor:
                    editor.clear()
            self._original_completion_text = ""
            self._generated_text_cache = None
            self.generated_response = None
            self._update_save_button_state()
            self._set_status("No completion selected.")
            return

        self.original_completion = completion
        prompt_text = (
            completion.prompt_revision.prompt_text if completion.prompt_revision is not None else ""
        )
        self._original_completion_text = completion.completion_text

        if self.prompt_edit:
            self.prompt_edit.setPlainText(prompt_text)
        if self.original_edit:
            self.original_edit.setPlainText(completion.completion_text)
        if self.new_edit:
            self.new_edit.setPlainText(completion.completion_text)

        self.generated_response = None
        self._generated_text_cache = None
        self._update_save_button_state()
        self._set_status("Ready to edit completion.")

    def set_facet(self, facet: "Facet | None") -> None:
        """Update the active facet and toggle pairwise preference appropriately."""

        self.active_facet = facet
        if not self.pairwise_checkbox:
            return
        if facet is None:
            self.pairwise_checkbox.setChecked(False)
            self.pairwise_checkbox.setEnabled(False)
            self.pairwise_checkbox.setToolTip(
                "Select a facet in the parent view to tag pairwise preference."
            )
        else:
            self.pairwise_checkbox.setEnabled(True)
            self.pairwise_checkbox.setChecked(True)
            self.pairwise_checkbox.setToolTip(
                f"Saving will prefer the new completion for facet '{facet.name}'."
            )

    def _build_column(
        self,
        parent: QWidget,
        *,
        title: str,
        background: str,
        font: QFont,
        read_only: bool,
    ) -> QPlainTextEdit:
        """Create a single column within the splitter and return its editor."""

        column = QWidget(parent)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(8, 0, 8, 0)
        column_layout.setSpacing(6)

        label = QLabel(title, column)
        column_layout.addWidget(label)

        editor = QPlainTextEdit(column)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setFont(font)
        editor.setReadOnly(read_only)
        editor.setStyleSheet(f"QPlainTextEdit {{ background-color: {background}; }}")
        column_layout.addWidget(editor, stretch=1)

        if isinstance(parent, QSplitter):
            parent.addWidget(column)

        return editor

    def _on_role_changed(self) -> None:
        """Enable generation only when the continue role is active."""

        role = "manual" if self.manual_radio and self.manual_radio.isChecked() else "continue"
        self.log.debug("Role switched to %s", role)
        enabled = bool(self.generate_radio and self.generate_radio.isChecked())
        if self.generate_button:
            self.generate_button.setEnabled(enabled)
        self._update_save_button_state()

    def _on_new_text_changed(self) -> None:
        """Refresh save button state when the editable column changes."""

        self._update_save_button_state()

    def _update_save_button_state(self) -> None:
        """Enable save when the new text contains a meaningful difference."""

        if not self.save_button or not self.new_edit:
            return

        text = self.new_edit.toPlainText()
        has_delta = bool(text.strip()) and text != self._original_completion_text
        self.save_button.setEnabled(has_delta)

    def _resolve_mapped_model(self) -> "MappedModel | None":
        """Find the provider mapping for the original completion's model id."""

        if not self.original_completion:
            return None
        if not getattr(self.app, "providers_manager", None):
            return None

        target_model_id = self.original_completion.model_id
        for mapped in self.app.providers_manager.model_provider_map.values():
            if mapped.model_id == target_model_id:
                return mapped
        self.log.debug("No mapped model found for id: %s", target_model_id)
        return None

    def _on_generate_clicked(self) -> None:
        """Ask the provider to continue the original completion."""

        if (
            not self.original_completion
            or not self.prompt_edit
            or not self.original_edit
            or not self.new_edit
        ):
            return

        mapped_model = self._resolve_mapped_model()
        if mapped_model is None:
            QMessageBox.warning(
                self,
                "Provider unavailable",
                (
                    "Cannot continue generation because the original provider "
                    "configuration is unavailable. Switch to manual editing instead."
                ),
            )
            self.log.warning(
                "Generation skipped: missing provider for model %s",
                self.original_completion.model_id,
            )
            return

        prompt_text = self.prompt_edit.toPlainText()
        original_text = self.original_edit.toPlainText()

        try:
            response = mapped_model.generate(
                prompt=prompt_text,
                prefill=original_text,
                temperature=self.original_completion.temperature,
                top_k=self.original_completion.top_k,
                context_length=self.original_completion.context_length,
                max_tokens=self.original_completion.max_tokens,
            )
        except (RuntimeError, ValueError, ImportError) as exc:  # pragma: no cover - defensive logging
            self.log.error("Continuation generation failed: %s", exc)
            self._set_status(f"Generation failed: {exc}", error=True)
            return

        combined_text = response.full_response_text or (
            (response.prefill or "") + response.response_text
        )
        self.generated_response = response
        self._generated_text_cache = combined_text
        self.new_edit.setPlainText(combined_text)
        self._set_status(f"Continuation generated with model {response.model_id}.")
        self._update_save_button_state()

    def _on_save_clicked(self) -> None:
        """Persist the new completion, archive lineage, and apply facet preferences."""

        if not self.original_completion or not self.new_edit:
            return

        session = self.dataset.session if self.dataset else None
        if session is None:
            QMessageBox.critical(
                self,
                "Dataset unavailable",
                "Cannot save completion because the dataset session is closed.",
            )
            self.log.error("Save aborted: dataset session is not initialised.")
            return

        new_text = self.new_edit.toPlainText()
        if not new_text.strip():
            self._set_status("New completion text cannot be empty.", error=True)
            return

        response = self.generated_response if self._generated_text_cache == new_text else None
        generation_role = bool(self.generate_radio and self.generate_radio.isChecked())
        if generation_role and response is None:
            self._set_status("Generated text was edited; saving as manual revision instead.")

        model_id = response.model_id if response else "manual"
        temperature = response.temperature if response else self.original_completion.temperature
        top_k = response.top_k if response else self.original_completion.top_k
        prefill = response.prefill if response else None
        beam_token = response.beam_token if response else None
        context_length = (
            response.context_length if response else self.original_completion.context_length
        )
        max_tokens = response.max_tokens if response else self.original_completion.max_tokens
        is_truncated = bool(response.is_truncated) if response else False

        new_completion = self._persist_new_completion(
            text=new_text,
            model_id=model_id,
            temperature=temperature,
            top_k=top_k,
            prefill=prefill,
            beam_token=beam_token,
            context_length=context_length,
            max_tokens=max_tokens,
            is_truncated=is_truncated,
        )

        if new_completion is None:
            return

        if self.archive_checkbox and self.archive_checkbox.isChecked():
            self.original_completion.is_archived = True
            session.commit()

        if self.pairwise_checkbox and self.pairwise_checkbox.isChecked():
            self._apply_pairwise_preference(new_completion)

        self.completion_saved.emit(new_completion)
        self._set_status("New completion saved.")
        self.accept()

    def _persist_new_completion(
        self,
        *,
        text: str,
        model_id: str,
        temperature: float,
        top_k: int,
        prefill: str | None,
        beam_token: str | None,
        context_length: int,
        max_tokens: int,
        is_truncated: bool,
    ) -> PromptCompletion | None:
        """Create and commit a new ``PromptCompletion`` record."""

        session = self.dataset.session if self.dataset else None
        if session is None or not self.original_completion:
            self._set_status("Dataset session is not available.", error=True)
            return None

        sha256_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        new_completion = PromptCompletion(
            prompt_revision=self.original_completion.prompt_revision,
            parent_completion_id=self.original_completion.id,
            sha256=sha256_hash,
            model_id=model_id,
            temperature=temperature,
            top_k=top_k,
            prefill=prefill,
            beam_token=beam_token,
            completion_text=text,
            tags=None,
            context_length=context_length,
            max_tokens=max_tokens,
            is_truncated=is_truncated,
            is_archived=False,
        )
        session.add(new_completion)
        session.commit()
        session.refresh(new_completion)
        if self.original_completion.prompt_revision is not None:
            session.refresh(self.original_completion.prompt_revision)
        self.log.debug(
            "Created completion %s as child of %s",
            new_completion.id,
            self.original_completion.id,
        )
        return new_completion

    def _apply_pairwise_preference(self, new_completion: PromptCompletion) -> None:
        """Tag the new completion as preferred over the original for the active facet."""

        if not self.active_facet or not self.dataset or not self.original_completion:
            return

        preferred_rating = 10
        discouraged_rating = 2
        PromptCompletionRating.set_rating(
            self.dataset,
            new_completion,
            self.active_facet,
            preferred_rating,
        )
        PromptCompletionRating.set_rating(
            self.dataset,
            self.original_completion,
            self.active_facet,
            discouraged_rating,
        )
        self.log.debug(
            "Facet '%s' preference recorded: new=%s original=%s",
            self.active_facet.name,
            preferred_rating,
            discouraged_rating,
        )

    def _set_status(self, message: str, *, error: bool = False) -> None:
        """Update the status label and mirror the message to logs."""

        if self.status_label:
            self.status_label.setText(message)
            self.status_label.setProperty("statusLevel", "error" if error else "info")
        if error:
            self.log.error("%s", message)
        else:
            self.log.debug("%s", message)


__all__ = ["ThreeWayCompletionEditorWindow"]
