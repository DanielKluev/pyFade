"""
Qt Widget for overall single sample display.
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
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor

from py_fade.gui.widget_completion import CompletionFrame
from py_fade.gui.widget_new_completion import NewCompletionFrame
from py_fade.gui.widget_completion_beams import WidgetCompletionBeams

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.sample import Sample
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.providers.llm_response import LLMResponse


class WidgetSample(QWidget):
    """
    Top-level widget showing prompt, sample controls and scrollable completion frames.
    Horizontal splitter with prompt and sample controls on top, completions below.
    Completions are `NewCompletionFrame` pinned to the left, existing completions `CompletionFrame` to the right.

    Sample controls are:
    - Non-editable input field showing sample ID or "New Sample" if new
    - Input field for sample title. 
    - Button to save sample, which disables prompt editing
    - Button to copy sample, which creates a new sample with same prompt but no completions
    """
    app: "pyFadeApp"
    sample: Sample | None = None
    dataset: "DatasetDatabase"
    last_prompt_revision: "PromptRevision | None" = None
    active_facet: Facet | None = None
    active_model_name: str | None = None
    
    sample_saved = pyqtSignal(object)  # Signal emitted when sample is saved
    sample_copied = pyqtSignal(object)  # Signal emitted when sample is copied
    def __init__(self, parent: QWidget | None, app: "pyFadeApp", sample: Sample | None = None):
        super().__init__(parent)
        if not app.current_dataset:
            raise RuntimeError("App does not have a current dataset set. Should open a dataset first.")
        
        self.app = app
        self.dataset = app.current_dataset
        
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
        
        self.prompt_area = QTextEdit(self)
        self.prompt_area.setPlaceholderText("Enter your prompt here...")
        self.prompt_area.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.prompt_area.setMinimumHeight(160)
        self.prompt_area.textChanged.connect(self.update_token_usage)
        
        # Token usage label
        self.token_usage_label = QLabel("Tokens: Prompt: 0 | Response: 0 | Total: 0 / 0", self)
        self.token_usage_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        
        prompt_layout.addWidget(self.prompt_area)
        prompt_layout.addWidget(self.token_usage_label)
        
        # Sample controls panel
        controls_frame = QFrame(self)
        controls_layout = QVBoxLayout(controls_frame)
        
        # Sample ID (non-editable)
        id_label = QLabel("Sample ID:", self)
        self.id_field = QLineEdit(self)
        self.id_field.setReadOnly(True)
        
        # Sample title (editable)
        title_label = QLabel("Title:", self)
        self.title_field = QLineEdit(self)
        self.title_field.setPlaceholderText("Enter sample title...")
        
        # Group path (editable combo box)
        group_label = QLabel("Group Path:", self)
        self.group_field = QComboBox(self)
        self.group_field.setEditable(True)
        self.group_field.lineEdit().setPlaceholderText("Example: Big Bench Hard/Math")  # type: ignore
        # Populate with existing group paths
        group_paths = self.dataset.list_unique_group_paths()
        self.group_field.addItems([""] + group_paths)
        
        # Context length (editable)
        context_label = QLabel("Context Length:", self)
        self.context_length_field = QSpinBox(self)
        self.context_length_field.setRange(1, 1000000)
        self.context_length_field.setValue(self.app.config.default_context_length)
        self.context_length_field.valueChanged.connect(self.update_token_usage)
        
        # Max tokens (editable)
        max_tokens_label = QLabel("Max Tokens:", self)
        self.max_tokens_field = QSpinBox(self)
        self.max_tokens_field.setRange(1, 100000)
        self.max_tokens_field.setValue(self.app.config.default_max_tokens)
        self.max_tokens_field.valueChanged.connect(self.update_token_usage)
        
        # Save button
        self.save_button = QPushButton("Save Sample", self)
        self.save_button.clicked.connect(self.save_sample)
        
        # Copy button
        self.copy_button = QPushButton("Copy Sample", self)
        self.copy_button.clicked.connect(self.copy_sample)
        
        # Beam search button
        self.beam_search_button = QPushButton("Beam Search", self)
        self.beam_search_button.clicked.connect(self.open_beam_search)
        
        controls_layout.addWidget(id_label)
        controls_layout.addWidget(self.id_field)
        controls_layout.addWidget(title_label)
        controls_layout.addWidget(self.title_field)
        controls_layout.addWidget(group_label)
        controls_layout.addWidget(self.group_field)
        controls_layout.addWidget(context_label)
        controls_layout.addWidget(self.context_length_field)
        controls_layout.addWidget(max_tokens_label)
        controls_layout.addWidget(self.max_tokens_field)
        controls_layout.addWidget(self.save_button)
        controls_layout.addWidget(self.copy_button)
        controls_layout.addWidget(self.beam_search_button)
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
        # Use a horizontal layout so completion frames are laid out side-by-side
        self.output_layout = QHBoxLayout(self.output_container)
        self.output_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
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
        label_text = f"Tokens: Prompt: {prompt_tokens} | Response: {max_tokens} | Total: {total_tokens} / {context_length}"
        self.token_usage_label.setText(label_text)
        
        # Highlight if total exceeds context length
        if total_tokens > context_length:
            self.token_usage_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 11px; padding: 4px; background-color: #ffe6e6;")
        else:
            self.token_usage_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")

    def set_sample(self, sample: Sample | None):
        """Set the sample and populate UI with sample data."""
        self.sample = sample
        
        if self.sample:
            # Existing sample - populate with actual data
            self.setWindowTitle(f"Sample {self.sample.id}")
            self.id_field.setText(str(self.sample.id))
            self.title_field.setText(self.sample.title or "")
            self.group_field.setCurrentText(self.sample.group_path or "")
            
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
        while self.output_layout.count():
            item = self.output_layout.takeAt(0)
            if not item:
                break
            widget = item.widget()
            if widget and widget is not self.new_completion_frame:
                widget.setParent(None)
                widget.deleteLater()

    def populate_outputs(self):
        """Populate the scroll area with completion frames from the sample."""
        self.clear_outputs()
        
        # Always add the NewCompletionFrame first
        self.output_layout.addWidget(self.new_completion_frame)
        
        if not self.sample or not self.sample.prompt_revision:
            # No existing completions, just show the NewCompletionFrame
            return

        for c in self.sample.prompt_revision.completions:
            frame = CompletionFrame(c, parent=self.output_container)
            # Keep completion frames a fixed width so they appear side-by-side
            frame.setFixedWidth(360)
            self.output_layout.addWidget(frame)

    def add_completion(self, response: "LLMResponse"):
        """
        Add new accepted response to sample and then add completion to the scroll area.
        """
        prompt_revision, completion = self.dataset.add_response_as_prompt_and_completion(self.prompt_area.toPlainText(), response)
        self.last_prompt_revision = prompt_revision
        # Create a new CompletionFrame for the saved completion
        frame = CompletionFrame(completion, parent=self.output_container)
        frame.setFixedWidth(360)
        # Insert it after the NewCompletionFrame (index 1)
        self.output_layout.insertWidget(1, frame)

    def save_sample(self):
        """
        Save the current sample with title and disable prompt editing.
        """
        if not self.app or not self.dataset or not self.dataset.session:
            raise RuntimeError("App or dataset not properly initialized.")
        
        # Existing samples can have only title and group path updated
        if self.sample and self.sample.id:
            self.sample.title = self.title_field.text().strip()
            self.sample.group_path = self.group_field.currentText().strip() or None
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
                self.max_tokens_field.value()
            )
            new_sample = Sample.create_if_unique(
                self.dataset, 
                self.title_field.text().strip() or "Untitled Sample", 
                prompt_revision, 
                self.group_field.currentText().strip() or None
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
            
        # Create and show beam search widget as new window
        self.beam_search_widget = WidgetCompletionBeams(
            parent=None,  # Independent window
            app=self.app,
            prompt=prompt_text,
            sample_widget=self
        )
        self.beam_search_widget.show()

    def set_active_context(self, facet: Facet | None, model_name: str | None) -> None:
        """Update widget state to reflect currently selected facet and model."""
        self.active_facet = facet
        self.active_model_name = model_name
        if hasattr(self, "new_completion_frame"):
            self.new_completion_frame.set_selected_model(model_name)
