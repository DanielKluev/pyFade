"""Interactive widget for beam-search exploration of model completions."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from py_fade.controllers.text_generation_controller import TextGenerationController
from py_fade.gui.components.widget_token_picker import WidgetTokenPicker
from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.providers.llm_response import LLMResponse

if TYPE_CHECKING:
    from py_fade.app import PyFadeApp
    from py_fade.gui.widget_sample import WidgetSample


class BeamGenerationWorker(QThread):
    """Worker thread for beam generation to keep UI responsive."""

    beam_completed = pyqtSignal(object)  # LLMResponse
    generation_finished = pyqtSignal()
    generation_error = pyqtSignal(str)

    def __init__(
        self,
        app: "PyFadeApp",
        beam_controller: TextGenerationController,
        *,
        prefill: str = "",
        width: int = 3,
        depth: int = 20,
        beam_tokens: list[tuple[str, float]] | None = None,
        temperature: float = 0.7,
        top_k: int = 40,
        context_length: int = 1024,
        max_tokens: int = 128,
    ):
        super().__init__()
        self.app = app
        self.beam_controller = beam_controller
        self.prefill = prefill
        self.width = width
        self.depth = depth
        self.beam_tokens = beam_tokens
        self.temperature = temperature
        self.top_k = top_k
        self.context_length = context_length
        self.max_tokens = max_tokens

    def run(self):
        """Execute beam generation and emit progress signals."""
        try:
            # Generate beams
            # Call beam_out_on_token_one_level which uses callbacks to report
            # each completed beam. We don't need the return value here.
            self.beam_controller.beam_out_on_token_one_level(
                prefix=self.prefill,
                width=self.width,
                length=self.depth,
                beam_tokens=self.beam_tokens,
                on_beam_completed=self.beam_completed.emit,
                on_check_stop=self.is_stopped,
            )
        except (RuntimeError, ValueError) as exc:
            self.generation_error.emit(str(exc))
            return

        self.generation_finished.emit()

    def is_stopped(self) -> bool:
        """Check if the thread has been requested to stop."""
        return self.isInterruptionRequested()


class WidgetCompletionBeams(QWidget):
    """Widget for viewing and curating completion beams.

    Provides controls for model selection, width, depth, temperature, and
    top-k sampling. Generated beams render as ``NewCompletionFrame`` widgets in
    a scrollable grid sorted by minimum log probability.

    Beam generation delegates to
    ``app.providers_manager.make_beam_for_prompt()`` and consumes
    ``beam_out_on_token_one_level`` callbacks to stream results into the grid.
    """

    grid_width = 4  # Number of columns in the grid layout for beams

    def __init__(
        self, parent: QWidget | None, app: "PyFadeApp", prompt: str, sample_widget: "WidgetSample"
    ):
        super().__init__(parent)
        self.app = app
        self.prompt = prompt
        self.sample_widget = sample_widget
        self.beam_frames: list[tuple[LLMResponse, "CompletionFrame"]] = []
        self.worker_thread: BeamGenerationWorker | None = None
        self.beam_controller: TextGenerationController | None = None  # Reusable beam controller
        self.token_picker_window: QDialog | None = None  # Token picker window

        self.setWindowTitle("Beam Search Generation")
        self.setGeometry(200, 200, 1400, 900)

        self.setup_ui()
        self.set_prompt(prompt)

    def setup_ui(self):
        """Create and arrange UI components."""
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Beam Search Generation")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Controls section
        controls_frame = QFrame(self)
        controls_frame.setFrameShape(QFrame.Shape.StyledPanel)
        controls_layout = QVBoxLayout(controls_frame)

        # Prompt display (read-only)
        controls_layout.addWidget(QLabel("Prompt:"))
        self.prompt_display = QPlainTextEdit(self)
        self.prompt_display.setReadOnly(True)
        self.prompt_display.setMaximumHeight(100)
        controls_layout.addWidget(self.prompt_display)

        # Parameter controls in grid
        params_layout = QGridLayout()

        # Prefill
        params_layout.addWidget(QLabel("Prefill:"), 0, 0)
        self.prefill_edit = QPlainTextEdit(self)
        self.prefill_edit.setPlaceholderText("Optional prefill text...")
        self.prefill_edit.setMaximumHeight(60)
        params_layout.addWidget(self.prefill_edit, 0, 1)

        # Model picker
        params_layout.addWidget(QLabel("Model:"), 0, 2)
        self.model_combo = QComboBox(self)
        self.model_combo.addItems(self.app.available_models)
        params_layout.addWidget(self.model_combo, 0, 3)

        # Width (number of beams)
        params_layout.addWidget(QLabel("Width (beams):"), 1, 0)
        self.width_spin = QSpinBox(self)
        self.width_spin.setRange(1, 100)
        self.width_spin.setValue(3)
        params_layout.addWidget(self.width_spin, 1, 1)

        # Depth (tokens per beam)
        params_layout.addWidget(QLabel("Depth (tokens):"), 1, 2)
        self.depth_spin = QSpinBox(self)
        self.depth_spin.setRange(1, 2048)
        self.depth_spin.setValue(20)
        params_layout.addWidget(self.depth_spin, 1, 3)

        # Temperature
        params_layout.addWidget(QLabel("Temperature:"), 2, 0)
        self.temp_spin = QDoubleSpinBox(self)
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self.app.providers_manager.default_temperature)
        params_layout.addWidget(self.temp_spin, 2, 1)

        # Top-k
        params_layout.addWidget(QLabel("Top-k:"), 2, 2)
        self.topk_spin = QSpinBox(self)
        self.topk_spin.setRange(1, 100)
        self.topk_spin.setValue(self.app.providers_manager.default_top_k)
        params_layout.addWidget(self.topk_spin, 2, 3)

        controls_layout.addLayout(params_layout)

        # Generate button and progress
        button_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Generate Beams", self)
        self.generate_btn.clicked.connect(self.generate_beams)
        button_layout.addWidget(self.generate_btn)

        self.selective_beams_btn = QPushButton("Selective Beams", self)
        self.selective_beams_btn.clicked.connect(self.selective_beams)
        button_layout.addWidget(self.selective_beams_btn)

        self.stop_btn = QPushButton("Stop", self)
        self.stop_btn.clicked.connect(self.stop_generation)
        self.stop_btn.setVisible(False)
        button_layout.addWidget(self.stop_btn)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        button_layout.addWidget(self.progress_bar)

        button_layout.addStretch()
        controls_layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("Ready to generate beams")
        controls_layout.addWidget(self.status_label)

        layout.addWidget(controls_frame)

        # Scrollable area for beam results
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.beams_container = QWidget()
        self.beams_layout = QGridLayout(self.beams_container)
        self.beams_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setWidget(self.beams_container)

        layout.addWidget(self.scroll_area)

    def set_prompt(self, prompt: str):
        """Set the prompt text."""
        self.prompt = prompt
        self.prompt_display.setPlainText(prompt)

    def generate_beams(self):
        """Start beam generation in worker thread."""
        if not self.app.providers_manager:
            self.status_label.setText("Error: No provider available")
            return

        if not self.prompt.strip():
            self.status_label.setText("Error: No prompt provided")
            return

        if not self.app.current_dataset:
            self.status_label.setText("Error: No dataset loaded")
            return

        # Clear previous results
        self.clear_beam_results()

        # Disable controls during generation
        self.generate_btn.setEnabled(False)
        self.selective_beams_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText("Generating beams...")

        mapped_model = self.app.providers_manager.get_mapped_model(self.model_combo.currentText())
        if not mapped_model:
            self.status_label.setText(f"Error: Model {self.model_combo.currentText()} not found")
            self._reset_ui_after_generation()
            return

        beam_controller = self._get_or_create_beam_controller()

        # Start worker thread
        self.worker_thread = BeamGenerationWorker(
            app=self.app,
            beam_controller=beam_controller,
            prefill=self.prefill_edit.toPlainText(),
            width=self.width_spin.value(),
            depth=self.depth_spin.value(),
            temperature=self.temp_spin.value(),
            top_k=self.topk_spin.value(),
            context_length=self.app.config.default_context_length,
            max_tokens=self.app.config.default_max_tokens,
        )

        self.worker_thread.beam_completed.connect(self.on_beam_completed)
        self.worker_thread.generation_finished.connect(self.on_generation_finished)
        self.worker_thread.generation_error.connect(self.on_generation_error)

        self.worker_thread.start()

    def _get_or_create_beam_controller(self) -> TextGenerationController:
        """Get or create the beam controller for the current parameters."""
        model_path = self.model_combo.currentText()
        controller = self.app.get_or_create_text_generation_controller(
            mapped_model=model_path, prompt_revision=self.prompt
        )
        return controller

    def selective_beams(self):
        """Show token picker for selective beam generation."""
        # Get beam controller
        beam_controller = self._get_or_create_beam_controller()
        if not beam_controller:
            self.status_label.setText("Error: Unable to create beam controller")
            return

        try:
            # Fetch 200 token candidates for next position
            self.status_label.setText("Fetching token candidates...")
            prefill = self.prefill_edit.toPlainText()
            token_logprobs = beam_controller.fetch_next_token_logprobs_for_prefix(prefill, 200)

            # Show token picker window
            self._show_token_picker(token_logprobs)

        except (RuntimeError, ValueError) as exc:
            self.status_label.setText(f"Error: {exc}")

    def _show_token_picker(self, token_logprobs: list[tuple[str, float]]):
        """Show token picker window with given tokens."""
        # NOTE: consider extracting dialog creation into WidgetTokenPicker helper.
        # Create token picker dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Tokens for Beam Generation")
        dialog.setGeometry(300, 300, 800, 600)

        layout = QVBoxLayout(dialog)

        # Add instruction label
        instruction = QLabel("Select tokens to use for beam generation:")
        layout.addWidget(instruction)

        # Create token picker widget
        token_picker = WidgetTokenPicker(
            dialog,
            token_logprobs,  # type: ignore[arg-type]
            multi_select=True,
        )
        layout.addWidget(token_picker)

        # Connect token selection signal
        token_picker.tokens_selected.connect(partial(self._on_tokens_selected, dialog=dialog))

        # Store reference and show dialog
        self.token_picker_window = dialog
        dialog.exec()

    def _on_tokens_selected(
        self, selected_tokens: list[tuple[str, float]], *, dialog: QDialog
    ) -> None:
        """Handle token selection and start beam generation."""
        dialog.accept()  # Close the dialog

        if not selected_tokens:
            self.status_label.setText("No tokens selected")
            return

        # Start beam generation with selected tokens
        self._generate_beams_with_tokens(selected_tokens)

    def _generate_beams_with_tokens(self, beam_tokens: list[tuple[str, float]]):
        """Generate beams using the selected tokens."""
        # Clear previous results
        self.clear_beam_results()

        # Disable controls during generation
        self.generate_btn.setEnabled(False)
        self.selective_beams_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText(f"Generating beams with {len(beam_tokens)} selected tokens...")

        mapped_model = self.app.providers_manager.get_mapped_model(self.model_combo.currentText())
        if not mapped_model:
            self.status_label.setText(f"Error: Model {self.model_combo.currentText()} not found")
            self._reset_ui_after_generation()
            return
        beam_controller = self._get_or_create_beam_controller()

        # Start worker thread with selected tokens
        self.worker_thread = BeamGenerationWorker(
            app=self.app,
            beam_controller=beam_controller,
            prefill=self.prefill_edit.toPlainText(),
            width=len(beam_tokens),  # Use number of selected tokens as width
            depth=self.depth_spin.value(),
            beam_tokens=beam_tokens,
            temperature=self.temp_spin.value(),
            top_k=self.topk_spin.value(),
            context_length=self.app.config.default_context_length,
            max_tokens=self.app.config.default_max_tokens,
        )

        self.worker_thread.beam_completed.connect(self.on_beam_completed)
        self.worker_thread.generation_finished.connect(self.on_generation_finished)
        self.worker_thread.generation_error.connect(self.on_generation_error)

        self.worker_thread.start()

    def _reset_ui_after_generation(self):
        """Reset UI state after generation is complete or stopped."""
        self.generate_btn.setEnabled(True)
        self.selective_beams_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.progress_bar.setVisible(False)

    def stop_generation(self):
        """Stop the current beam generation."""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.requestInterruption()
            self.worker_thread.wait(30000)  # Wait up to 30 seconds for thread to stop

            # Reset UI state
            self._reset_ui_after_generation()
            self.status_label.setText("Generation stopped by user.")

    @pyqtSlot(object)
    def on_beam_completed(self, beam: LLMResponse):
        """Handle completion of a single beam."""
        self.add_beam_frame(beam)
        self.status_label.setText(f"Generated {len(self.beam_frames)} beam(s)...")

    @pyqtSlot()
    def on_generation_finished(self):
        """Handle completion of all beam generation."""
        self._reset_ui_after_generation()
        self.status_label.setText(f"Generation complete. {len(self.beam_frames)} beams generated.")

        # Sort beams by min_logprob (descending)
        self.sort_beam_frames()

    @pyqtSlot(str)
    def on_generation_error(self, error_msg: str):
        """Handle generation error."""
        self._reset_ui_after_generation()
        self.status_label.setText(f"Error: {error_msg}")

    def add_beam_frame(self, beam: LLMResponse):
        """Add a beam result to the display grid."""
        # Create CompletionFrame in beam mode to display the beam
        frame = CompletionFrame(
            dataset=self.app.current_dataset,
            completion=beam,
            parent=self.beams_container,
            display_mode="beam",
        )
        frame.setFixedWidth(400)
        frame.setFixedHeight(300)

        # Connect beam frame signals
        frame.discard_requested.connect(self.on_beam_discarded)
        frame.save_requested.connect(self.on_beam_accepted)
        frame.pin_toggled.connect(self.on_beam_pinned)

        self.beam_frames.append((beam, frame))

        # Add to grid layout (`self.grid_width` columns)
        row = (len(self.beam_frames) - 1) // self.grid_width
        col = (len(self.beam_frames) - 1) % self.grid_width
        self.beams_layout.addWidget(frame, row, col)

    def sort_beam_frames(self):
        """Sort beam frames by min_logprob descending."""
        # Sort by min_logprob if available, otherwise by response length
        self.beam_frames.sort(
            key=lambda x: getattr(x[0], "min_logprob", -float("inf")), reverse=True
        )

        # Clear and re-add frames in sorted order
        for i in reversed(range(self.beams_layout.count())):
            item = self.beams_layout.itemAt(i)
            if item:
                self.beams_layout.removeItem(item)

        for index, (_beam, frame) in enumerate(self.beam_frames):
            row = index // self.grid_width
            col = index % self.grid_width
            self.beams_layout.addWidget(frame, row, col)

    @pyqtSlot(object)
    def on_beam_discarded(self, completion):
        """Handle beam discard - remove from display and list."""
        # Find and remove the beam frame
        frame_to_remove = None
        for index, (_beam, beam_frame) in enumerate(self.beam_frames):
            if beam_frame.completion is completion:
                frame_to_remove = beam_frame
                self.beam_frames.pop(index)
                break

        # Remove from layout and delete the frame
        if frame_to_remove:
            frame_to_remove.setParent(None)
            frame_to_remove.deleteLater()

        # Re-arrange remaining frames in grid
        self.rearrange_beam_grid()

    @pyqtSlot(object)
    def on_beam_accepted(self, completion):
        """Handle beam acceptance - add as completion to sample."""
        if self.sample_widget:
            # Add to sample widget - completion here is LLMResponse from beam mode
            self.sample_widget.add_completion(completion)

    @pyqtSlot(object, bool)
    def on_beam_pinned(self, completion, is_pinned):
        """Handle beam pin/unpin - update visual state."""
        # Visual feedback is handled in the frame itself
        # We can add additional logic here if needed

    def rearrange_beam_grid(self):
        """Re-arrange beam frames in grid after removal."""
        # Remove all widgets from layout
        for i in reversed(range(self.beams_layout.count())):
            item = self.beams_layout.itemAt(i)
            if item:
                self.beams_layout.removeItem(item)

            # Re-add frames in grid layout
        for index, (_beam, frame) in enumerate(self.beam_frames):
            row = index // self.grid_width
            col = index % self.grid_width
            self.beams_layout.addWidget(frame, row, col)

    def clear_beam_results(self):
        """Clear all beam result frames except pinned ones."""
        # Separate pinned and unpinned frames
        pinned_frames = []
        unpinned_frames = []

        for beam, frame in self.beam_frames:
            if frame.is_pinned:
                pinned_frames.append((beam, frame))
            else:
                unpinned_frames.append((beam, frame))

        # Delete unpinned frames
        for beam, frame in unpinned_frames:
            frame.setParent(None)
            frame.deleteLater()

        # Keep only pinned frames
        self.beam_frames = pinned_frames

        # Re-arrange pinned frames in grid
        self.rearrange_beam_grid()
