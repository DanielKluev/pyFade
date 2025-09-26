from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QScrollArea,
    QLabel,
    QFrame,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QPlainTextEdit,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp



class NewCompletionFrame(QFrame):
    """
    UI frame for creating a new completion.

    Should have model picker (combobox)
    Should let user set temperature, top_k
    Should let user type in multiline edit for prefill
    Should have a button to generate the completion
    """
    
    completion_accepted = pyqtSignal(object)  # Signal emitted when completion is accepted and should be saved
    app: "pyFadeApp"
    def __init__(self, parent: QWidget, app: "pyFadeApp"):
        super().__init__(parent)
        self.app = app
        self.generated_completion = None
        self.setFrameShape(QFrame.Shape.StyledPanel)
        #self.setStyleSheet("background-color: #f0f8ff; border: 2px dashed #4169e1;")
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Generate New Completion")
        #header.setStyleSheet("font-weight: bold; font-size: 14px; color: #4169e1;")
        layout.addWidget(header)
        
        # Controls layout
        controls_layout = QHBoxLayout()
        
        # Model picker
        controls_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.app.available_models)
        controls_layout.addWidget(self.model_combo)
        
        # Temperature
        controls_layout.addWidget(QLabel("Temperature:"))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self.app.providers_manager.default_temperature)
        controls_layout.addWidget(self.temp_spin)
        
        # Top-k
        controls_layout.addWidget(QLabel("Top-k:"))
        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 100)
        self.topk_spin.setValue(self.app.providers_manager.default_top_k)
        controls_layout.addWidget(self.topk_spin)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Prefill text area
        layout.addWidget(QLabel("Prefill (optional):"))
        self.prefill_edit = QPlainTextEdit()
        self.prefill_edit.setPlaceholderText("Enter prefill text here...")
        self.prefill_edit.setMaximumHeight(80)
        layout.addWidget(self.prefill_edit)
        
        # Generated completion area
        self.completion_area = QTextEdit()
        self.completion_area.setReadOnly(True)
        self.completion_area.setMinimumHeight(120)
        self.completion_area.setPlaceholderText("Generated completion text...")
        layout.addWidget(self.completion_area)

        # Token picker area
        self.token_picker_area = QScrollArea()
        self.token_picker_area.setWidgetResizable(True)
        self.token_picker_area.setVisible(False)  # Hidden by default; shown in step-by-step mode
        layout.addWidget(self.token_picker_area)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.clicked.connect(self.generate_completion)
        #self.generate_btn.setStyleSheet("QPushButton { background-color: #4169e1; color: white; font-weight: bold; padding: 8px; }")
        buttons_layout.addWidget(self.generate_btn)
        
        self.step_by_step_btn = QPushButton("Step-by-step")
        self.step_by_step_btn.setToolTip("Generate the completion token by token, allowing manual intervention at each token.")
        self.step_by_step_btn.clicked.connect(self.generate_token_by_token)  # TODO: Implement step-by-step generation
        buttons_layout.addWidget(self.step_by_step_btn)

        self.save_btn = QPushButton("Save Completion")
        self.save_btn.clicked.connect(self.save_completion)
        self.save_btn.setEnabled(False)
        #self.save_btn.setStyleSheet("QPushButton { background-color: #32cd32; color: white; font-weight: bold; padding: 8px; }")
        buttons_layout.addWidget(self.save_btn)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Status label
        self.status_label = QLabel("")
        #self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.status_label)
    
    def set_selected_model(self, model_name: str | None) -> None:
        """Select the provided model in the combo box when available."""
        if not model_name:
            return
        index = self.model_combo.findText(model_name)
        if index < 0:
            return
        self.model_combo.blockSignals(True)
        self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)

    def generate_completion(self):
        """Generate a new completion with current parameters."""
        if not self.app:
            self.status_label.setText("Error: No app provider available")
            return
            
        # Navigate up the widget hierarchy to find the WidgetSample
        widget_sample = self.parent()
        while widget_sample and not hasattr(widget_sample, 'prompt_area'):
            widget_sample = widget_sample.parent()
        
        if not widget_sample:
            self.status_label.setText("Error: Cannot find prompt area")
            self.generate_btn.setEnabled(True)
            return
        
        self.generate_btn.setEnabled(False)
        self.status_label.setText("Generating...")
        self.completion_area.show()
        self.completion_area.clear()
        self.app.q_app.processEvents()  # Force UI update

        mapped_model = self.app.providers_manager.get_mapped_model(self.model_combo.currentText())
        if not mapped_model:
            self.status_label.setText(f"Error: Model '{self.model_combo.currentText()}' not found")
            self.generate_btn.setEnabled(True)
            return
            
        self.generated_completion = mapped_model.generate(
            prompt=widget_sample.prompt_area.toPlainText().strip(),  # type: ignore
            prefill=self.prefill_edit.toPlainText() or None,
            temperature=self.temp_spin.value(),
            top_k=self.topk_spin.value(),
            context_length=widget_sample.context_length_field.value(),  # type: ignore
            max_tokens=widget_sample.max_tokens_field.value(),  # type: ignore
        )
        self.display_completion()

    def generate_token_by_token(self):
        """Generate the completion token by token, allowing manual intervention at each token."""
        self.status_label.setText("Step-by-step generation not implemented yet.")
    
    def display_completion(self):
        """Display the generated completion with prefill highlighting."""
        if not self.generated_completion:
            return
        
        self.completion_area.show()
        self.completion_area.clear()
        
        cursor = self.completion_area.textCursor()
        
        # Highlight prefill if present
        if self.generated_completion.prefill:
            # Prefill format - highlighted
            prefill_format = QTextCharFormat()
            prefill_format.setBackground(QColor("#fffacd"))  # Light yellow
            prefill_format.setForeground(QColor("#8b4513"))  # Brown text
            
            cursor.insertText(self.generated_completion.prefill, prefill_format)
        
        # Regular completion text
        normal_format = QTextCharFormat()
        cursor.insertText(self.generated_completion.response_text, normal_format)

        # Update UI state
        self.generate_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.status_label.setText(f"Generated by {self.generated_completion.model_id}")
    
    def save_completion(self):
        """Save the generated completion and emit signal."""
        if not self.generated_completion:
            return
        
        self.completion_accepted.emit(self.generated_completion)
        self.status_label.setText("Completion saved!")
        
        # Reset for next generation (but keep parameters)
        self.generated_completion = None
        self.completion_area.hide()
        self.save_btn.setEnabled(False)