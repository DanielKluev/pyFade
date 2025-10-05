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
from enum import Enum
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_pairwise_ranks import PromptCompletionPairwiseRanking

if TYPE_CHECKING:  # pragma: no cover - import hints only
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.providers.llm_response import LLMResponse
    from py_fade.providers.providers_manager import MappedModel


class EditorMode(Enum):
    """Enum for Three Way Editor modes."""
    MANUAL = "manual"
    CONTINUATION = "continuation"


class ThreeWayCompletionEditorWindow(QDialog):
    """Modal dialog that offers manual and continued-edit flows for completions."""

    completion_saved = pyqtSignal(PromptCompletion)

    def __init__(self, app: "pyFadeApp", dataset: "DatasetDatabase", completion: PromptCompletion, mode: EditorMode, *,
                 facet: "Facet | None" = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.app = app
        self.dataset = dataset
        self.mode = mode
        self.original_completion: PromptCompletion | None = None
        self.active_facet: "Facet | None" = facet
        self.generated_response: "LLMResponse | None" = None
        self._generated_text_cache: str | None = None
        self._original_completion_text: str = ""
        self.mapped_model: "MappedModel | None" = None

        self.prompt_edit: QPlainTextEdit | None = None
        self.original_edit: QPlainTextEdit | None = None
        self.new_edit: QPlainTextEdit | None = None
        self.archive_checkbox: QCheckBox | None = None
        self.pairwise_checkbox: QCheckBox | None = None
        self.generate_button: QPushButton | None = None
        self.save_button: QPushButton | None = None
        self.status_label: QLabel | None = None

        # Continuation mode specific controls
        self.max_tokens_field: QSpinBox | None = None
        self.context_length_field: QSpinBox | None = None

        self._set_window_title(completion)
        self.setModal(True)
        self.resize(1200, 740)

        self.setup_ui()
        self.connect_signals()
        self.set_facet(self.active_facet)
        self.set_completion(completion)

    def _set_window_title(self, completion: PromptCompletion) -> None:
        """Set the window title based on mode and completion model info."""
        if self.mode == EditorMode.MANUAL:
            self.setWindowTitle("Three-way completion editor - Manual Edit")
        else:  # CONTINUATION
            title = "Three-way completion editor - Continuation"
            if completion:
                self.mapped_model = self._resolve_mapped_model(completion.model_id)
                if self.mapped_model:
                    title += f" ({self.mapped_model.path})"
                else:
                    title += f" (No provider for {completion.model_id})"
            self.setWindowTitle(title)

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

        # Add mode-specific controls
        if self.mode == EditorMode.CONTINUATION:
            self._add_continuation_controls(layout)

        # Common options layout
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

        # Actions layout
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        if self.mode == EditorMode.CONTINUATION:
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

    def _add_continuation_controls(self, layout: QVBoxLayout) -> None:
        """Add continuation-specific controls for max tokens and context length."""

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        # Max tokens control
        max_tokens_label = QLabel("Max Tokens:", self)
        controls_layout.addWidget(max_tokens_label)

        self.max_tokens_field = QSpinBox(self)
        self.max_tokens_field.setRange(1, 100000)
        self.max_tokens_field.setValue(self.app.config.default_max_tokens)
        controls_layout.addWidget(self.max_tokens_field)

        # Context length control
        context_label = QLabel("Context Length:", self)
        controls_layout.addWidget(context_label)

        self.context_length_field = QSpinBox(self)
        self.context_length_field.setRange(1, 1000000)
        self.context_length_field.setValue(self.app.config.default_context_length)
        controls_layout.addWidget(self.context_length_field)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

    def connect_signals(self) -> None:
        """Wire UI widgets to handlers that maintain dialog state."""

        if not self.new_edit:
            raise RuntimeError("Editor was not initialised correctly before wiring signals.")

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
        prompt_text = (completion.prompt_revision.prompt_text if completion.prompt_revision is not None else "")
        self._original_completion_text = completion.completion_text

        if self.prompt_edit:
            self.prompt_edit.setPlainText(prompt_text)
        if self.original_edit:
            self.original_edit.setPlainText(completion.completion_text)
        if self.new_edit:
            self.new_edit.setPlainText(completion.completion_text)

        # Set reasonable defaults for continuation mode
        if self.mode == EditorMode.CONTINUATION:
            self._configure_continuation_parameters(completion, prompt_text)

        self.generated_response = None
        self._generated_text_cache = None
        self._update_save_button_state()
        self._set_status("Ready to edit completion.")

    def _configure_continuation_parameters(self, completion: PromptCompletion, prompt_text: str) -> None:
        """Configure max tokens and context length for continuation mode."""

        if not self.max_tokens_field or not self.context_length_field:
            return

        # Calculate tokens in original completion
        completion_tokens = self.app.providers_manager.count_tokens(completion.completion_text)

        # Set max_tokens to max(1024, 2 * original completion tokens)
        suggested_max_tokens = max(1024, 2 * completion_tokens)
        self.max_tokens_field.setValue(suggested_max_tokens)

        # Calculate prompt tokens
        prompt_tokens = self.app.providers_manager.count_tokens(prompt_text)

        # Set context_length to prompt_tokens + max_tokens rounded up to nearest 1024 multiple
        suggested_context_length = prompt_tokens + suggested_max_tokens
        suggested_context_length = ((suggested_context_length + 1023) // 1024) * 1024
        self.context_length_field.setValue(suggested_context_length)

        # Update generate button state based on mapped model availability
        if self.mode == EditorMode.CONTINUATION:
            if self.generate_button:
                has_mapped_model = self.mapped_model is not None
                self.generate_button.setEnabled(has_mapped_model)
                if not has_mapped_model:
                    self._set_status("Cannot generate continuation: no provider available for this model", error=True)

    def set_facet(self, facet: "Facet | None") -> None:
        """Update the active facet and toggle pairwise preference appropriately."""

        self.active_facet = facet
        if not self.pairwise_checkbox:
            return
        if facet is None:
            self.pairwise_checkbox.setChecked(False)
            self.pairwise_checkbox.setEnabled(False)
            self.pairwise_checkbox.setToolTip("Select a facet in the parent view to tag pairwise preference.")
        else:
            self.pairwise_checkbox.setEnabled(True)
            self.pairwise_checkbox.setChecked(True)
            self.pairwise_checkbox.setToolTip(f"Saving will prefer the new completion for facet '{facet.name}'.")

    def _build_column(self, parent: QWidget, *, title: str, background: str, font: QFont, read_only: bool) -> QPlainTextEdit:
        """Create a single column within the splitter and return its editor."""

        column = QWidget(parent)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(8, 0, 8, 0)
        column_layout.setSpacing(6)

        label = QLabel(title, column)
        column_layout.addWidget(label)

        editor = QPlainTextEdit(column)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        editor.setFont(font)
        editor.setReadOnly(read_only)
        editor.setStyleSheet(f"QPlainTextEdit {{ background-color: {background}; }}")
        column_layout.addWidget(editor, stretch=1)

        if isinstance(parent, QSplitter):
            parent.addWidget(column)

        return editor

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

    def _resolve_mapped_model(self, model_id: str | None = None) -> "MappedModel | None":
        """Find the provider mapping for the given model id, prioritizing providers with highest logprobs capabilities."""

        target_model_id = model_id
        if not target_model_id:
            if not self.original_completion:
                return None
            target_model_id = self.original_completion.model_id

        if not getattr(self.app, "providers_manager", None):
            return None

        # Find all providers for this model_id and rank by logprobs capability
        candidates = []
        for mapped in self.app.providers_manager.model_provider_map.values():
            if mapped.model_id == target_model_id:
                capability = getattr(mapped.provider, 'logprob_capability', 0)
                candidates.append((mapped, capability))

        if not candidates:
            self.log.debug("No mapped model found for id: %s", target_model_id)
            return None

        # Sort by logprobs capability (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_mapped_model = candidates[0][0]

        self.log.debug("Resolved model %s to provider %s with logprob capability %d", target_model_id, best_mapped_model.provider.id,
                       candidates[0][1])
        return best_mapped_model

    def _on_generate_clicked(self) -> None:
        """
        Ask the provider to continue the original completion.
        """

        if (not self.original_completion or not self.prompt_edit or not self.original_edit or not self.new_edit):
            return

        # Use the already resolved mapped model
        if self.mapped_model is None:
            QMessageBox.warning(
                self,
                "Provider unavailable",
                ("Cannot continue generation because no provider "
                 "is available for this model."),
            )
            self.log.warning(
                "Generation skipped: missing provider for model %s",
                self.original_completion.model_id,
            )
            return

        # Get context length and max tokens from controls if available
        context_length = self.context_length_field.value() if self.context_length_field else self.original_completion.context_length
        max_tokens = self.max_tokens_field.value() if self.max_tokens_field else self.original_completion.max_tokens

        generation_controller = self.app.get_or_create_text_generation_controller(self.mapped_model,
                                                                                  self.original_completion.prompt_revision,
                                                                                  context_length=context_length, max_tokens=max_tokens)

        if generation_controller is None:
            self.log.error("Generation controller could not be created for model %s", self.mapped_model.model_id)
            return

        self._set_status("Generating continuation...")

        try:
            response = generation_controller.generate_continuation(original_completion=self.original_completion, max_tokens=max_tokens,
                                                                   context_length=context_length)
        except (RuntimeError, ValueError, ImportError) as exc:  # pragma: no cover - defensive logging
            self.log.error("Continuation generation failed: %s", exc)
            self._set_status(f"Generation failed: {exc}", error=True)
            return
        if response is None:
            self.log.error("Continuation generation returned no response for unknown reasons.")
            self._set_status("Generation failed: no response", error=True)
            return

        self.generated_response = response
        self._generated_text_cache = response.completion_text
        self.new_edit.setPlainText(response.completion_text)
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

        if new_text == self._original_completion_text:
            self._set_status("New completion text is identical to the original; no changes to save.", error=True)
            return

        generation_role = self.mode == EditorMode.CONTINUATION
        was_edited = self._generated_text_cache != new_text
        response = self.generated_response
        if response and not was_edited and generation_role:
            self.log.info("Saving generated continuation as-is.")
            new_completion = PromptCompletion.get_or_create_from_llm_response(self.dataset, self.original_completion.prompt_revision,
                                                                              response, parent_completion_id=self.original_completion.id)
        else:  # Manual edit or edited after generation
            if response and was_edited and generation_role:
                self.log.info("Saving manually edited continuation.")
            else:
                self.log.info("Saving manual edit of original completion.")

            new_completion = self._persist_new_completion(
                text=new_text,
                model_id=self.original_completion.model_id,
                temperature=0.0,
                top_k=1,
                prefill=None,
                beam_token=None,
                context_length=0,
                max_tokens=0,
                is_truncated=False,
                is_manual=True,
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

    def _persist_new_completion(self, *, text: str, model_id: str, temperature: float, top_k: int, prefill: str | None,
                                beam_token: str | None, context_length: int, max_tokens: int, is_truncated: bool,
                                is_manual: bool) -> PromptCompletion | None:
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
            is_manual=is_manual,
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

        # Create new PromptCompletionPairwiseRanking record if not already existing for this facet and pair
        PromptCompletionPairwiseRanking.get_or_create(self.dataset, new_completion, self.original_completion, self.active_facet)

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
