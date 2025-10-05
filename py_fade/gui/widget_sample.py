"""
Qt Widget for overall single sample display.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.gui.components.widget_plain_text_edit import PlainTextEdit
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.widget_completion_beams import WidgetCompletionBeams
from py_fade.gui.widget_new_completion import NewCompletionFrame
from py_fade.gui.window_three_way_completion_editor import ThreeWayCompletionEditorWindow, EditorMode
from py_fade.providers.providers_manager import MappedModel
from py_fade.providers.flat_prefix_template import FLAT_PREFIX_SYSTEM, FLAT_PREFIX_USER, FLAT_PREFIX_ASSISTANT
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.providers.llm_response import LLMResponse


class WidgetSample(QWidget):
    """
    Top-level widget showing prompt, sample controls and scrollable completion frames.
    Horizontal splitter with prompt and sample controls on top, completions below.
    Completions are `NewCompletionFrame` pinned to the left,
    existing completions `CompletionFrame` to the right.

    Sample controls feature a compact layout with:
    - Label and field pairs arranged horizontally on the same row
    - Context Length and Max Tokens combined in a single row for space efficiency
    - Icon-only action buttons (Save, Copy, Beam Search) with tooltips in a horizontal row
    - Show archived completions checkbox integrated into the controls panel

    Control fields:
    - Non-editable Sample ID field
    - Editable sample title field
    - Editable group path combo box with autocomplete
    - Context length and max tokens numeric inputs (combined row)
    - Icon-only action buttons: Save (save icon), Copy (content_copy icon), Beam Search (search icon)
    - Show archived completions checkbox for filtering completions display
    """

    app: "pyFadeApp"
    sample: Sample | None = None
    dataset: "DatasetDatabase"
    last_prompt_revision: "PromptRevision | None" = None
    active_facet: Facet | None = None
    active_model: MappedModel | None = None
    completion_frames: list[tuple["PromptCompletion", CompletionFrame]] = []

    sample_saved = pyqtSignal(object)  # Signal emitted when sample is saved
    sample_copied = pyqtSignal(object)  # Signal emitted when sample is copied
    completion_archive_toggled = pyqtSignal(object, bool)
    completion_resume_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", sample: Sample | None = None, active_facet: Facet | None = None,
                 active_model: MappedModel | None = None):
        """
        Initialize the widget.
        """
        super().__init__(parent)
        if not app.current_dataset:
            raise RuntimeError("App does not have a current dataset set. Should open a dataset first.")
        self.log = logging.getLogger("WidgetSample")
        self.app = app
        self.dataset = app.current_dataset
        self.active_facet = active_facet
        self.active_model = active_model
        self.beam_search_widget: WidgetCompletionBeams | None = None
        self.completion_frames = []

        self.setup_ui()
        self.set_sample(sample)

    def setup_ui(self):
        """Create and arrange UI components."""
        self.setGeometry(100, 100, 1200, 1000)

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # Upper section with horizontal splitter for prompt and controls
        upper_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Prompt editor with token usage label
        prompt_frame = QFrame(self)
        prompt_layout = QVBoxLayout(prompt_frame)

        self.prompt_area = PlainTextEdit(self)
        self.prompt_area.setPlaceholderText("Enter your prompt here...")
        self.prompt_area.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.prompt_area.setMinimumHeight(160)
        self.prompt_area.textChanged.connect(self.update_token_usage)

        # Token usage label
        self.token_usage_label = QLabel("Tokens: Prompt: 0 | Response: 0 | Total: 0 / 0", self)
        self.token_usage_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")

        # Role tag buttons for inserting system/user/assistant tags
        role_tag_buttons_layout = QHBoxLayout()
        role_tag_buttons_layout.setSpacing(4)

        role_tag_label = QLabel("Insert Role Tag:", self)
        role_tag_buttons_layout.addWidget(role_tag_label)

        self.system_tag_button = QPushButtonWithIcon("", "S", parent=self, icon_size=0, button_size=32)
        self.system_tag_button.setToolTip("Insert System Tag at End (must be at beginning)")
        self.system_tag_button.clicked.connect(self.insert_system_tag)
        role_tag_buttons_layout.addWidget(self.system_tag_button)

        self.user_tag_button = QPushButtonWithIcon("", "U", parent=self, icon_size=0, button_size=32)
        self.user_tag_button.setToolTip("Insert User Tag at End")
        self.user_tag_button.clicked.connect(self.insert_user_tag)
        role_tag_buttons_layout.addWidget(self.user_tag_button)

        self.assistant_tag_button = QPushButtonWithIcon("", "A", parent=self, icon_size=0, button_size=32)
        self.assistant_tag_button.setToolTip("Insert Assistant Tag at End")
        self.assistant_tag_button.clicked.connect(self.insert_assistant_tag)
        role_tag_buttons_layout.addWidget(self.assistant_tag_button)

        role_tag_buttons_layout.addStretch()

        prompt_layout.addWidget(self.prompt_area)
        prompt_layout.addWidget(self.token_usage_label)
        prompt_layout.addLayout(role_tag_buttons_layout)

        # Sample controls panel
        controls_frame = QFrame(self)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setSpacing(4)  # Reduced spacing for compactness

        # Sample ID row (label and field on same line)
        id_row_layout = QHBoxLayout()
        id_label = QLabel("Sample ID:", self)
        id_label.setMinimumWidth(80)
        self.id_field = QLineEdit(self)
        self.id_field.setReadOnly(True)
        id_row_layout.addWidget(id_label)
        id_row_layout.addWidget(self.id_field)

        # Sample title row (label and field on same line)
        title_row_layout = QHBoxLayout()
        title_label = QLabel("Title:", self)
        title_label.setMinimumWidth(80)
        self.title_field = QLineEdit(self)
        self.title_field.setPlaceholderText("Enter sample title...")
        title_row_layout.addWidget(title_label)
        title_row_layout.addWidget(self.title_field)

        # Group path row (label and field on same line)
        group_row_layout = QHBoxLayout()
        group_label = QLabel("Group Path:", self)
        group_label.setMinimumWidth(80)
        self.group_field = QComboBox(self)
        self.group_field.setEditable(True)
        group_line_edit = self.group_field.lineEdit()
        if group_line_edit is not None:
            group_line_edit.setPlaceholderText("Example: Big Bench Hard/Math")
        # Populate with existing group paths
        group_paths = self.dataset.list_unique_group_paths()
        self.group_field.addItems([""] + group_paths)
        group_row_layout.addWidget(group_label)
        group_row_layout.addWidget(self.group_field)

        # Notes row (label and field on same line)
        notes_row_layout = QHBoxLayout()
        notes_label = QLabel("Notes:", self)
        notes_label.setMinimumWidth(80)
        notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.notes_field = QPlainTextEdit(self)
        self.notes_field.setPlaceholderText("Add notes for annotators (not visible to models)...")
        self.notes_field.setMaximumHeight(60)  # About 2 lines high
        notes_row_layout.addWidget(notes_label)
        notes_row_layout.addWidget(self.notes_field)

        # Context length and max tokens on same row
        tokens_row_layout = QHBoxLayout()
        context_label = QLabel("Context:", self)
        context_label.setMinimumWidth(50)
        self.context_length_field = QSpinBox(self)
        self.context_length_field.setRange(1, 1000000)
        self.context_length_field.setValue(self.app.config.default_context_length)
        self.context_length_field.valueChanged.connect(self.update_token_usage)

        max_tokens_label = QLabel("Max:", self)
        max_tokens_label.setMinimumWidth(35)
        self.max_tokens_field = QSpinBox(self)
        self.max_tokens_field.setRange(1, 100000)
        self.max_tokens_field.setValue(self.app.config.default_max_tokens)
        self.max_tokens_field.valueChanged.connect(self.update_token_usage)

        tokens_row_layout.addWidget(context_label)
        tokens_row_layout.addWidget(self.context_length_field)
        tokens_row_layout.addWidget(max_tokens_label)
        tokens_row_layout.addWidget(self.max_tokens_field)

        # Action buttons row (icon-only buttons with tooltips)
        buttons_row_layout = QHBoxLayout()

        self.save_button = QPushButtonWithIcon("save", "", parent=self, icon_size=20, button_size=32)
        self.save_button.setToolTip("Save Sample")
        self.save_button.clicked.connect(self.save_sample)

        self.copy_button = QPushButtonWithIcon("content_copy", "", parent=self, icon_size=20, button_size=32)
        self.copy_button.setToolTip("Copy Sample")
        self.copy_button.clicked.connect(self.copy_sample)

        self.beam_search_button = QPushButtonWithIcon("search", "", parent=self, icon_size=20, button_size=32)
        self.beam_search_button.setToolTip("Beam Search")
        self.beam_search_button.clicked.connect(self.open_beam_search)

        buttons_row_layout.addWidget(self.save_button)
        buttons_row_layout.addWidget(self.copy_button)
        buttons_row_layout.addWidget(self.beam_search_button)
        buttons_row_layout.addStretch()  # Push buttons to the left

        # Show archived checkbox (moved from completions panel)
        self.show_archived_checkbox = QCheckBox("Show archived completions", self)
        self.show_archived_checkbox.setChecked(False)

        # Add all rows to the main layout
        controls_layout.addLayout(id_row_layout)
        controls_layout.addLayout(title_row_layout)
        controls_layout.addLayout(group_row_layout)
        controls_layout.addLayout(notes_row_layout)
        controls_layout.addLayout(tokens_row_layout)
        controls_layout.addLayout(buttons_row_layout)
        controls_layout.addWidget(self.show_archived_checkbox)
        controls_layout.addStretch()

        # Add prompt and controls to horizontal splitter
        upper_splitter.addWidget(prompt_frame)
        upper_splitter.addWidget(controls_frame)
        # Set the prompt area to take more space (70% prompt, 30% controls)
        upper_splitter.setSizes([700, 300])

        # Scroll area for completions
        self.output_area = QScrollArea(self)
        self.output_area.setWidgetResizable(True)

        self.output_container = QWidget()
        self.output_container_layout = QVBoxLayout(self.output_container)
        self.output_container_layout.setContentsMargins(8, 8, 8, 8)
        self.output_container_layout.setSpacing(8)

        # Remove the completion controls layout since show_archived_checkbox is now in controls panel

        # Use a horizontal layout so completion frames are laid out side-by-side
        self.output_layout = QHBoxLayout()
        self.output_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.output_container_layout.addLayout(self.output_layout)

        # Make the scroll area scroll horizontally and avoid vertical scrolling
        self.output_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.output_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.output_area.setWidget(self.output_container)

        splitter.addWidget(upper_splitter)
        splitter.addWidget(self.output_area)

        # Set splitter to 60% prompt area (upper), 40% outputs (lower)
        splitter.setSizes([600, 400])

        layout.addWidget(splitter)
        self.setLayout(layout)

        # Create new completion frame
        self.new_completion_frame = NewCompletionFrame(parent=self.output_container, app=self.app)
        self.new_completion_frame.completion_accepted.connect(self.add_completion)
        # Force a fixed width so frames are displayed side-by-side
        self.new_completion_frame.setFixedWidth(500)
        self.show_archived_checkbox.toggled.connect(self._on_show_archived_toggled)

    def update_token_usage(self):
        """Update the token usage label with current prompt and settings."""
        if not self.app or not self.app.providers_manager:
            raise RuntimeError("App or app.providers_manager not properly initialized.")

        prompt_text = self.prompt_area.toPlainText()
        context_length = self.context_length_field.value()
        max_tokens = self.max_tokens_field.value()

        # Count tokens in prompt using app provider
        prompt_tokens = 0
        if prompt_text.strip():
            prompt_tokens = self.app.providers_manager.count_tokens(prompt_text)

        # Calculate total usage
        total_tokens = prompt_tokens + max_tokens

        # Update label text
        label_text = (f"Tokens: Prompt: {prompt_tokens} | Response: {max_tokens} | Total: "
                      f"{total_tokens} / {context_length}")
        self.token_usage_label.setText(label_text)

        # Highlight if total exceeds context length
        if total_tokens > context_length:
            self.token_usage_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 11px; padding: 4px; "
                                                 "background-color: #ffe6e6;")
        else:
            self.token_usage_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")

    def insert_system_tag(self):
        """
        Insert system role tag at the beginning of the prompt text.
        
        System tag must be at the beginning of the prompt and there must be only one system tag.
        If a system tag already exists, show a warning and don't insert.
        """
        current_text = self.prompt_area.toPlainText()

        # Check if system tag already exists
        if FLAT_PREFIX_SYSTEM in current_text:
            QMessageBox.warning(self, "System Tag Already Exists",
                                "A system tag already exists in the prompt. Only one system tag is allowed.")
            self.log.debug("Attempted to insert system tag but one already exists")
            return

        # Insert system tag at the beginning
        if current_text:
            new_text = f"{FLAT_PREFIX_SYSTEM}\n{current_text}"
        else:
            new_text = FLAT_PREFIX_SYSTEM

        self.prompt_area.setPlainText(new_text)
        self.log.debug("Inserted system tag at beginning of prompt")

    def insert_user_tag(self):
        """
        Insert user role tag at the end of the prompt text on a new line.
        """
        self.prompt_area.insert_role_tag_at_end(FLAT_PREFIX_USER)

    def insert_assistant_tag(self):
        """
        Insert assistant role tag at the end of the prompt text on a new line.
        """
        self.prompt_area.insert_role_tag_at_end(FLAT_PREFIX_ASSISTANT)

    def set_sample(self, sample: Sample | None):
        """Set the sample and populate UI with sample data."""
        self.sample: Sample | None = sample

        if self.sample:
            # Existing sample - populate with actual data
            self.setWindowTitle(f"Sample {self.sample.id}")
            self.id_field.setText(str(self.sample.id))
            self.title_field.setText(self.sample.title or "")
            self.group_field.setCurrentText(self.sample.group_path or "")
            self.notes_field.setPlainText(self.sample.notes or "")

            # Set prompt text from prompt_revision
            if self.sample.prompt_revision:
                self.prompt_area.setPlainText(self.sample.prompt_revision.prompt_text)
                self.context_length_field.setValue(self.sample.prompt_revision.context_length)
                self.max_tokens_field.setValue(self.sample.prompt_revision.max_tokens)
            else:
                self.prompt_area.clear()
                self.context_length_field.setValue(self.app.config.default_context_length)
                self.max_tokens_field.setValue(self.app.config.default_max_tokens)
        else:
            # New sample - set default/empty values
            self.setWindowTitle("Sample New")
            self.id_field.setText("New Sample")
            self.title_field.clear()
            self.group_field.setCurrentText("")
            self.notes_field.clear()
            self.prompt_area.clear()
            self.context_length_field.setValue(self.app.config.default_context_length)
            self.max_tokens_field.setValue(self.app.config.default_max_tokens)

        # Existing samples have read-only prompts
        if self.sample and self.sample.id:
            self.prompt_area.setReadOnly(True)
        else:
            self.prompt_area.setReadOnly(False)

        # Update token usage after setting sample data
        self.update_token_usage()

        # Populate outputs
        self.populate_outputs()

    def clear_outputs(self):
        """Remove all completion frames except the creation widget."""
        while self.output_layout.count():
            item = self.output_layout.takeAt(0)
            if not item:
                break
            widget = item.widget()
            if widget and widget is not self.new_completion_frame:
                widget.setParent(None)
                widget.deleteLater()

        # Clear the completion frames list
        self.completion_frames.clear()

    def _create_completion_frame(self, completion: "PromptCompletion") -> CompletionFrame:
        """Instantiate a completion frame wired with the current context."""

        frame = CompletionFrame(self.dataset, completion, parent=self.output_container)
        frame.setFixedWidth(360)
        frame.set_facet(self.active_facet)
        frame.set_target_model(self.active_model)

        # Connect existing signals
        frame.archive_toggled.connect(self._on_completion_archive_toggled)
        frame.resume_requested.connect(self._on_completion_resume_requested)
        frame.evaluate_requested.connect(self._on_completion_evaluate_requested)

        # Connect new signals
        frame.edit_requested.connect(self._on_completion_edit_requested)
        frame.discard_requested.connect(self._on_completion_discard_requested)

        # Connect rating_saved signal to trigger re-sorting
        if hasattr(frame, "rating_widget"):
            frame.rating_widget.rating_saved.connect(self._on_rating_changed)

        return frame

    def _sort_completions_by_rating_and_logprob(self, completions: list["PromptCompletion"]) -> list["PromptCompletion"]:
        """
        Sort completions by rating (descending) and scored_logprob (descending).
        
        Completions are sorted by:
        1. Rating for active facet (higher rated completions first, 0 rating is considered no rating)
        2. Within each rating group, by scored_logprob for active model (higher scores first)
        3. Completions without logprobs appear after those with logprobs
        """
        self.log.info("Sorting %d completions by rating and scored_logprob, active_facet=%s, active_model=%s", len(completions),
                      self.active_facet, self.active_model)

        def sort_key(completion: "PromptCompletion") -> tuple[int, float, float]:
            # Get rating for active facet (default to 0 if no rating or no facet)
            rating = 0
            if self.active_facet:
                rating_record = completion.rating_for_facet(self.active_facet)
                if rating_record:
                    rating = rating_record.rating

            # Get scored_logprob for active model (default to -inf if no logprobs or no model)
            scored_logprob = -float("inf")
            has_logprobs = 0.0  # Used to sort completions with logprobs before those without
            if self.active_model:
                logprobs = completion.get_logprobs_for_model_id(self.active_model.model_id)
                if logprobs and logprobs.scored_logprob is not None:
                    scored_logprob = logprobs.scored_logprob
                    has_logprobs = 1.0

            # Return tuple: (negative rating for descending, has_logprobs for descending, scored_logprob for descending)
            # Negative rating and scored_logprob because we want descending order but sort() is ascending
            return (-rating, -has_logprobs, -scored_logprob)

        return sorted(completions, key=sort_key)

    def sort_completion_frames(self):
        """
        Sort completion frames by rating and scored_logprob without recreating widgets.
        
        Frames are sorted by:
        1. Rating for active facet (higher rated completions first)
        2. Within each rating group, by scored_logprob for active model (higher scores first)
        3. Completions without logprobs appear after those with logprobs
        
        This method reorders existing widgets in the layout instead of recreating them,
        making it more efficient than populate_outputs().
        """
        self.log.debug("Sorting %d completion frames by rating and scored_logprob", len(self.completion_frames))

        if not self.completion_frames:
            return

        def sort_key(frame_tuple: tuple["PromptCompletion", CompletionFrame]) -> tuple[int, float, float]:
            completion, _frame = frame_tuple

            # Get rating for active facet (default to 0 if no rating or no facet)
            rating = 0
            if self.active_facet:
                rating_record = completion.rating_for_facet(self.active_facet)
                if rating_record:
                    rating = rating_record.rating

            # Get scored_logprob for active model (default to -inf if no logprobs or no model)
            scored_logprob = -float("inf")
            has_logprobs = 0.0  # Used to sort completions with logprobs before those without
            if self.active_model:
                logprobs = completion.get_logprobs_for_model_id(self.active_model.model_id)
                if logprobs and logprobs.scored_logprob is not None:
                    scored_logprob = logprobs.scored_logprob
                    has_logprobs = 1.0

            # Return tuple: (negative rating for descending, has_logprobs for descending, scored_logprob for descending)
            return (-rating, -has_logprobs, -scored_logprob)

        self.completion_frames.sort(key=sort_key)

        # Remove all widgets from layout except NewCompletionFrame
        for i in reversed(range(self.output_layout.count())):
            item = self.output_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget is not self.new_completion_frame:
                    self.output_layout.removeItem(item)

        # Re-add frames in sorted order (NewCompletionFrame should still be at index 0)
        for _completion, frame in self.completion_frames:
            self.output_layout.addWidget(frame)

    def populate_outputs(self):
        """
        Populate the scroll area with completion frames from the sample.
        
        Completions are sorted by:
        1. Rating for active facet (higher rated completions first)
        2. Within each rating group, by scored_logprob for active model (higher scores first)
        3. Completions without logprobs appear after those with logprobs
        """
        self.clear_outputs()

        # Always add the NewCompletionFrame first
        self.output_layout.addWidget(self.new_completion_frame)

        if not self.sample or not self.sample.prompt_revision:
            # No existing completions, just show the NewCompletionFrame
            return

        show_archived = self.show_archived_checkbox.isChecked()

        # Filter completions
        completions_to_display = [
            completion for completion in self.sample.prompt_revision.completions if not completion.is_archived or show_archived
        ]

        # Sort completions by rating and scored_logprob
        sorted_completions = self._sort_completions_by_rating_and_logprob(completions_to_display)

        for completion in sorted_completions:
            frame = self._create_completion_frame(completion)
            self.completion_frames.append((completion, frame))
            self.output_layout.addWidget(frame)

    def _on_show_archived_toggled(self, checked: bool) -> None:  # pylint: disable=unused-argument
        """
        Repopulate completions when the archived toggle changes.
        """

        self.populate_outputs()

    def _on_completion_archive_toggled(self, completion: "PromptCompletion", archived: bool) -> None:
        """Forward archive events and refresh visible completions."""

        self.completion_archive_toggled.emit(completion, archived)
        self.populate_outputs()

    def _on_completion_resume_requested(self, completion: "PromptCompletion") -> None:
        """Handle resume request for a completion - open ThreeWayCompletionEditorWindow."""
        if not self.app:
            return

        # Open the editor window in blocking mode
        editor = ThreeWayCompletionEditorWindow(self.app, self.dataset, completion, EditorMode.CONTINUATION, facet=self.active_facet,
                                                parent=self)

        # Show as modal dialog
        result = editor.exec()
        if result:
            # Refresh the outputs to reflect any changes made in the editor
            self.populate_outputs()

        # Also emit the signal for backward compatibility in case any code depends on it
        self.completion_resume_requested.emit(completion)

    def _on_completion_evaluate_requested(self, completion: "PromptCompletion", mapped_model: MappedModel,
                                          completion_frame: "CompletionFrame") -> None:
        """
        Emit an evaluate request for logprob generation.
        """
        if not self.app:
            return

        current_context_length = self.context_length_field.value()
        max_context_length = max(current_context_length, completion.prompt_revision.context_length)
        controller = self.app.get_or_create_text_generation_controller(
            mapped_model,
            completion.prompt_revision,
            context_length=max_context_length,
            max_tokens=completion.max_tokens,
        )
        controller.evaluate_completion_logprobs(completion, save=True)
        completion_frame._update_status_icons()  # pylint: disable=protected-access
        completion_frame._update_action_buttons()  # pylint: disable=protected-access

        # Re-sort after logprobs change
        self.sort_completion_frames()

    def _on_rating_changed(self, rating: int) -> None:  # pylint: disable=unused-argument
        """
        Handle rating change event - re-sort completion frames.
        """
        self.log.debug("Rating changed to %d, re-sorting completion frames", rating)
        self.sort_completion_frames()

    def _on_completion_edit_requested(self, completion: "PromptCompletion") -> None:
        """Handle edit request for a completion - open ThreeWayCompletionEditorWindow."""
        if not self.app:
            return

        # Open the editor window in blocking mode
        editor = ThreeWayCompletionEditorWindow(self.app, self.dataset, completion, EditorMode.MANUAL, facet=self.active_facet, parent=self)

        # Show as modal dialog
        result = editor.exec()
        if result:
            # Refresh the outputs to reflect any changes made in the editor
            self.populate_outputs()

    def _on_completion_discard_requested(self, completion: "PromptCompletion") -> None:
        """Handle discard request for a completion - remove from database and UI."""
        if not self.dataset.session:
            return

        try:
            # Remove from database
            self.dataset.session.delete(completion)
            self.dataset.session.commit()

            # Refresh the UI to remove the completion frame
            self.populate_outputs()

        except RuntimeError as e:
            self.log.error("Failed to discard completion: %s", e)
            # Rollback the transaction
            if self.dataset.session:
                self.dataset.session.rollback()

    def add_completion(self, response: "LLMResponse") -> "PromptCompletion":
        """
        Add new accepted response to sample and then add completion to the scroll area.

        Returns the created PromptCompletion for UI updates.
        """
        prompt_revision, completion = self.dataset.add_response_as_prompt_and_completion(self.prompt_area.toPlainText(), response)
        self.last_prompt_revision = prompt_revision
        # Create a new CompletionFrame for the saved completion
        frame = self._create_completion_frame(completion)
        if completion.is_archived and not self.show_archived_checkbox.isChecked():
            frame.deleteLater()
            return completion
        # Add to completion_frames list
        self.completion_frames.append((completion, frame))
        # Insert it after the NewCompletionFrame (index 1)
        self.output_layout.insertWidget(1, frame)
        # Re-sort to place it in the correct position
        self.sort_completion_frames()
        return completion

    def save_sample(self):
        """
        Save the current sample with title and disable prompt editing.
        """
        if not self.app or not self.dataset or not self.dataset.session:
            raise RuntimeError("App or dataset not properly initialized.")

        # Existing samples can have metadata updated, but not prompt
        if self.sample and self.sample.id:
            self.sample.title = self.title_field.text().strip()
            self.sample.group_path = self.group_field.currentText().strip() or None
            self.sample.notes = self.notes_field.toPlainText().strip() or None
            self.sample.prompt_revision.context_length = self.context_length_field.value()
            self.sample.prompt_revision.max_tokens = self.max_tokens_field.value()
            self.dataset.session.commit()
        else:
            # Create new sample with current prompt
            prompt_text = self.prompt_area.toPlainText().strip()
            if not prompt_text:
                # Cannot save a sample without a prompt
                return
            prompt_revision = PromptRevision.get_or_create(
                self.dataset,
                prompt_text,
                self.context_length_field.value(),
                self.max_tokens_field.value(),
            )
            new_sample = Sample.create_if_unique(
                self.dataset,
                self.title_field.text().strip() or "Untitled Sample",
                prompt_revision,
                self.group_field.currentText().strip() or None,
                self.notes_field.toPlainText().strip() or None,
            )
            if not new_sample:
                # Sample with this prompt already exists, do not create duplicate
                return
            self.sample = new_sample

        self.set_sample(self.sample)  # Refresh UI state
        self.sample_saved.emit(self.sample)  # Emit signal that sample was saved

    def copy_sample(self):
        """Create a new sample with the same prompt but no completions."""
        if not self.sample:
            return
        self.sample_copied.emit(self.sample)

    def open_beam_search(self):
        """Open the beam search window with current prompt."""
        prompt_text = self.prompt_area.toPlainText().strip()
        if not prompt_text:
            # Qt MessageBox
            QMessageBox.warning(self, "Warning", "Please enter a prompt before starting beam search.")
            return

        if not self.active_model:
            QMessageBox.warning(self, "Warning", "Please select a model before starting beam search.")
            return

        # Create and show beam search widget as new window
        self.beam_search_widget = WidgetCompletionBeams(
            parent=None,  # Independent window
            app=self.app,
            prompt=prompt_text,
            sample_widget=self,
            mapped_model=self.active_model,
        )
        self.beam_search_widget.show()

    def set_active_context(self, facet: Facet | None, model_path: str | None) -> None:
        """Update widget state to reflect currently selected facet and model."""
        # Track if facet or model changed
        facet_changed = self.active_facet != facet
        model_changed = False

        self.active_facet = facet
        if model_path:
            mapped_model = self.app.providers_manager.get_mapped_model(model_path)
        else:
            mapped_model = None

        # Check if model changed
        old_model_id = self.active_model.model_id if self.active_model else None
        new_model_id = mapped_model.model_id if mapped_model else None
        model_changed = old_model_id != new_model_id

        self.active_model = mapped_model
        if hasattr(self, "new_completion_frame"):
            self.new_completion_frame.set_selected_model(self.active_model)
        for index in range(self.output_layout.count()):
            item = self.output_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, CompletionFrame):
                widget.set_facet(self.active_facet)
                widget.set_target_model(self.active_model)

        # Re-sort if facet or model changed
        if facet_changed or model_changed:
            self.sort_completion_frames()
