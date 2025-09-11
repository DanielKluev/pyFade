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
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor

from py_fade.gui.widget_completion import CompletionFrame
from py_fade.gui.widget_new_completion import NewCompletionFrame

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.sample import Sample
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
    def __init__(self, parent: QWidget | None, app: "pyFadeApp", sample: Sample | None = None):
        super().__init__(parent)
        if not app.current_dataset:
            raise RuntimeError("App does not have a current dataset set. Should open a dataset first.")
        self.sample = sample
        self.app = app
        self.dataset = app.current_dataset
        self.setWindowTitle(f"Sample {self.sample.id if self.sample else 'New'}")
        self.setGeometry(100, 100, 1200, 1000)

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # Upper section with horizontal splitter for prompt and controls
        upper_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Prompt editor (read-only if sample provided)
        self.prompt_area = QTextEdit(self)
        self.prompt_area.setPlaceholderText("Enter your prompt here...")
        self.prompt_area.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.prompt_area.setMinimumHeight(160)

        # Sample controls panel
        controls_frame = QFrame(self)
        controls_layout = QVBoxLayout(controls_frame)
        
        # Sample ID (non-editable)
        id_label = QLabel("Sample ID:", self)
        self.id_field = QLineEdit(self)
        self.id_field.setReadOnly(True)
        self.id_field.setText(self.sample.id if self.sample.id != "new_sample" else "New Sample")

        # Sample title (editable)
        title_label = QLabel("Title:", self)
        self.title_field = QLineEdit(self)
        self.title_field.setPlaceholderText("Enter sample title...")
        if hasattr(self.sample, 'title') and self.sample.title:
            self.title_field.setText(self.sample.title)

        # Group path (editable)
        group_label = QLabel("Group Path:", self)
        self.group_field = QLineEdit(self)
        self.group_field.setPlaceholderText("Example: Big Bench Hard/Math")
        if self.sample.group_path:
            self.group_field.setText(self.sample.group_path)
        
        # Save button
        self.save_button = QPushButton("Save Sample", self)
        self.save_button.clicked.connect(self.save_sample)
        
        # Copy button
        self.copy_button = QPushButton("Copy Sample", self)
        self.copy_button.clicked.connect(self.copy_sample)
        
        controls_layout.addWidget(id_label)
        controls_layout.addWidget(self.id_field)
        controls_layout.addWidget(title_label)
        controls_layout.addWidget(self.title_field)
        controls_layout.addWidget(group_label)
        controls_layout.addWidget(self.group_field)        
        controls_layout.addWidget(self.save_button)
        controls_layout.addWidget(self.copy_button)
        controls_layout.addStretch()

        # Add prompt and controls to horizontal splitter
        upper_splitter.addWidget(self.prompt_area)
        upper_splitter.addWidget(controls_frame)
        # Set the prompt area to take more space (70% prompt, 30% controls)
        upper_splitter.setSizes([700, 300])

        # Populate prompt if sample provided and there's at least one revision
        if self.sample and getattr(self.sample, "prompts", None):
            last = self.sample.prompts[-1]
            try:
                self.prompt_area.setPlainText(str(last.prompt_text))
            except Exception:
                self.prompt_area.setPlainText(str(last))

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

        # Create new completion frame first
        self.new_completion_frame = NewCompletionFrame(parent=self.output_container, app=self.app)
        self.new_completion_frame.completion_accepted.connect(self.add_completion)
        # Force a fixed width so frames are displayed side-by-side
        self.new_completion_frame.setFixedWidth(500)

        # fill outputs from sample
        self.populate_outputs()

    def clear_outputs(self):
        while self.output_layout.count():
            item = self.output_layout.takeAt(0)
            if not item:
                break
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def populate_outputs(self):
        """Populate the scroll area with completion frames from the sample."""
        self.clear_outputs()
        
        # Always add the NewCompletionFrame first
        self.output_layout.addWidget(self.new_completion_frame)
        
        if not self.sample or not getattr(self.sample, "completions", None):
            # No existing completions, just show the NewCompletionFrame
            return

        for c in self.sample.completions:
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
        if not self.sample:
            return
        
        # Set the title if provided
        title = self.title_field.text().strip()
        if hasattr(self.sample, 'title'):
            self.sample.title = title
        
        # Generate new sample ID if this is a new sample
        if self.sample.sample_id == "new_sample":
            # Generate a new unique ID based on the dataset
            new_id = self.app.current_dataset.generate_sample_id()
            self.sample.sample_id = new_id
            self.id_field.setText(new_id)
            self.setWindowTitle(f"Sample {new_id}")
        
        # Save the sample to the dataset
        self.app.current_dataset.add_sample(self.sample)
        
        # Disable prompt editing after save
        self.prompt_area.setReadOnly(True)
        
        # Update button states
        self.save_button.setEnabled(False)
    
    def copy_sample(self):
        """Create a new sample with the same prompt but no completions."""
        if not self.sample:
            return
        
        # Create new sample with same prompt
        new_sample = Sample("new_sample", self.app.current_dataset)
        
        # Copy the prompt if it exists
        if self.sample and getattr(self.sample, "prompts", None):
            # Add the current prompt text to the new sample
            prompt_text = self.prompt_area.toPlainText()
            if prompt_text.strip():
                new_sample.add_prompt(prompt_text)
        
        # Open a new WidgetSample window with the copied sample
        from py_fade.gui.widget_launcher import launch_sample_widget
        launch_sample_widget(self.app, new_sample)
