"""
Blockwise Generation Window — non-modal, independent window for paragraph-by-paragraph generation.

Three-pane layout:
1. Left: Current Completion (editable text with gutter showing block annotations)
2. Top-Right: Generation Settings (prompt, instructions, controls)
3. Bottom-Right: Block Candidates (responsive grid with action buttons)

Key classes: `BlockCandidateWidget`, `WindowBlockwiseGeneration`
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from py_fade.controllers.blockwise_generation_controller import BlockCandidate, BlockwiseGenerationController
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.gui.widget_sample import WidgetSample
    from py_fade.providers.providers_manager import MappedModel


class BlockCandidateWidget(QFrame):
    """
    Widget displaying a single block candidate with action buttons.

    Shows block text, word count, token count, and provides buttons
    for accept, edit, rewrite, make shorter, and make longer.
    """

    def __init__(self, candidate: BlockCandidate, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log = logging.getLogger("BlockCandidateWidget")
        self.candidate = candidate
        self.setup_ui()

    def setup_ui(self) -> None:
        """Create and arrange UI components."""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(250)
        self.setMaximumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Block text display
        self.text_display = QPlainTextEdit(self)
        self.text_display.setPlainText(self.candidate.text)
        self.text_display.setReadOnly(True)
        self.text_display.setMaximumHeight(150)
        layout.addWidget(self.text_display)

        # Stats row
        stats_layout = QHBoxLayout()
        self.word_count_label = QLabel(f"Words: {self.candidate.word_count}", self)
        self.token_count_label = QLabel(f"Tokens: {self.candidate.token_count}", self)
        stats_layout.addWidget(self.word_count_label)
        stats_layout.addWidget(self.token_count_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Action buttons row
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(4)

        self.accept_button = QPushButtonWithIcon("check", "Accept", icon_size=16)
        self.accept_button.setToolTip("Accept this block and append to Current Completion")

        self.edit_button = QPushButtonWithIcon("edit", "Edit", icon_size=16)
        self.edit_button.setToolTip("Edit this block (creates a new candidate)")

        self.rewrite_button = QPushButtonWithIcon("refresh", "Rewrite", icon_size=16)
        self.rewrite_button.setToolTip("Rewrite with custom instructions")

        self.shorter_button = QPushButtonWithIcon("compress", "Shorter", icon_size=16)
        self.shorter_button.setToolTip("Make this block more concise")

        self.longer_button = QPushButtonWithIcon("expand", "Longer", icon_size=16)
        self.longer_button.setToolTip("Expand this block with more detail")

        buttons_layout.addWidget(self.accept_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.rewrite_button)
        buttons_layout.addWidget(self.shorter_button)
        buttons_layout.addWidget(self.longer_button)
        layout.addLayout(buttons_layout)


class WindowBlockwiseGeneration(QWidget):
    """
    Non-modal, independent window for blockwise (paragraph-by-paragraph) generation.

    Three-pane layout with Current Completion, Generation Settings, and Block Candidates.
    Multiple instances can be open simultaneously for different samples.

    All blockwise generation state is transient (in-memory only). Closing the window
    discards all unsaved state. Saving a completion creates a standard PromptCompletion
    record via the parent WidgetSample.
    """

    min_candidate_width = 280  # Minimum width for each candidate widget in the grid

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", prompt: str, sample_widget: "WidgetSample",
                 mapped_model: "MappedModel") -> None:
        super().__init__(parent)
        self.log = logging.getLogger("WindowBlockwiseGeneration")
        self.app = app
        self.prompt = prompt
        self.sample_widget = sample_widget
        self.mapped_model = mapped_model
        self.candidate_widgets: list[BlockCandidateWidget] = []
        self.is_saved = False
        self.grid_width = 3
        self.is_edit_enabled = False

        # Initialize the controller
        self.controller = BlockwiseGenerationController(
            mapped_model=mapped_model,
            original_prompt=prompt,
            temperature=app.config.default_temperature,
            top_k=app.config.default_top_k,
            context_length=app.config.default_context_length,
            max_tokens=app.config.default_max_tokens,
        )

        self.setWindowTitle("Blockwise Generation")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setup_ui()
        self.set_prompt(prompt)

    def setup_ui(self) -> None:
        """Create and arrange UI components for the three-pane layout."""
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Blockwise Generation")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Main horizontal splitter: Left (Current Completion) | Right (Settings + Candidates)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # === Left Pane: Current Completion ===
        self.left_pane = self._build_current_completion_pane()
        self.main_splitter.addWidget(self.left_pane)

        # === Right area: vertical splitter for Settings (top) and Candidates (bottom) ===
        self.right_splitter = QSplitter(Qt.Orientation.Vertical, self)

        # Top-Right: Generation Settings
        self.settings_pane = self._build_generation_settings_pane()
        self.right_splitter.addWidget(self.settings_pane)

        # Bottom-Right: Block Candidates
        self.candidates_pane = self._build_block_candidates_pane()
        self.right_splitter.addWidget(self.candidates_pane)

        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 2)

        self.main_splitter.addWidget(self.right_splitter)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)

        layout.addWidget(self.main_splitter)

    def _build_current_completion_pane(self) -> QFrame:
        """Build the Current Completion pane (left side)."""
        pane = QFrame(self)
        pane.setFrameShape(QFrame.Shape.StyledPanel)
        pane_layout = QVBoxLayout(pane)

        # Action buttons row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(4)

        self.save_completion_button = QPushButtonWithIcon("save", "Save", icon_size=18)
        self.save_completion_button.setToolTip("Save current completion as a new PromptCompletion")
        self.save_completion_button.clicked.connect(self.save_completion)
        actions_layout.addWidget(self.save_completion_button)

        self.edit_toggle_button = QPushButtonWithIcon("edit", "Edit", icon_size=18)
        self.edit_toggle_button.setToolTip("Toggle editing of the completion text")
        self.edit_toggle_button.setCheckable(True)
        self.edit_toggle_button.toggled.connect(self._on_edit_toggled)
        actions_layout.addWidget(self.edit_toggle_button)

        self.copy_completion_button = QPushButtonWithIcon("content_copy", "Copy", icon_size=18)
        self.copy_completion_button.setToolTip("Copy completion to clipboard")
        self.copy_completion_button.clicked.connect(self._copy_completion)
        actions_layout.addWidget(self.copy_completion_button)

        actions_layout.addStretch()
        pane_layout.addLayout(actions_layout)

        # Completion text display (read-only by default)
        self.completion_text = QPlainTextEdit(self)
        self.completion_text.setReadOnly(True)
        self.completion_text.setPlaceholderText("Accepted blocks will appear here...")
        self.completion_text.textChanged.connect(self._on_completion_text_changed)
        pane_layout.addWidget(self.completion_text)

        # Block gutter / stats panel
        self.gutter_label = QLabel("Blocks: 0 | Words: 0 | Tokens: 0", self)
        pane_layout.addWidget(self.gutter_label)

        return pane

    def _build_generation_settings_pane(self) -> QFrame:
        """Build the Generation Settings pane (top-right)."""
        pane = QFrame(self)
        pane.setFrameShape(QFrame.Shape.StyledPanel)
        pane_layout = QVBoxLayout(pane)

        # Prompt display (read-only)
        pane_layout.addWidget(QLabel("Prompt:"))
        self.prompt_display = QPlainTextEdit(self)
        self.prompt_display.setReadOnly(True)
        self.prompt_display.setMaximumHeight(80)
        pane_layout.addWidget(self.prompt_display)

        # Global Instructions
        pane_layout.addWidget(QLabel("Global Instructions (shadow addendum to user message):"))
        self.global_instructions_field = QPlainTextEdit(self)
        self.global_instructions_field.setMaximumHeight(60)
        self.global_instructions_field.setPlaceholderText("Optional: additional context appended to the user prompt during generation...")
        pane_layout.addWidget(self.global_instructions_field)

        # Block Instructions
        pane_layout.addWidget(QLabel("Block Instructions (shadow scratchpad in assistant prefill):"))
        self.block_instructions_field = QPlainTextEdit(self)
        self.block_instructions_field.setMaximumHeight(60)
        self.block_instructions_field.setPlaceholderText(
            "Optional: injected into assistant prefill between accepted blocks and manual prefix...")
        pane_layout.addWidget(self.block_instructions_field)

        # Manual Prefix
        pane_layout.addWidget(QLabel("Manual Prefix (start of block in assistant prefill):"))
        self.manual_prefix_field = QPlainTextEdit(self)
        self.manual_prefix_field.setMaximumHeight(40)
        self.manual_prefix_field.setPlaceholderText("Optional: text to start the next block with...")
        pane_layout.addWidget(self.manual_prefix_field)

        # Generation controls row
        controls_layout = QHBoxLayout()

        # Width spinner
        controls_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox(self)
        self.width_spin.setRange(1, 20)
        self.width_spin.setValue(4)
        self.width_spin.setToolTip("Number of candidate blocks to generate per run")
        controls_layout.addWidget(self.width_spin)

        # Temperature spinner
        controls_layout.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QSpinBox(self)
        self.temperature_spin.setRange(0, 200)
        self.temperature_spin.setValue(70)
        self.temperature_spin.setSuffix(" / 100")
        self.temperature_spin.setToolTip("Temperature × 100 (e.g. 70 = 0.7)")
        controls_layout.addWidget(self.temperature_spin)

        # Top-K spinner
        controls_layout.addWidget(QLabel("Top-K:"))
        self.top_k_spin = QSpinBox(self)
        self.top_k_spin.setRange(1, 200)
        self.top_k_spin.setValue(40)
        self.top_k_spin.setToolTip("Top-K sampling parameter")
        controls_layout.addWidget(self.top_k_spin)

        controls_layout.addStretch()
        pane_layout.addLayout(controls_layout)

        # Generate button
        button_layout = QHBoxLayout()
        self.generate_button = QPushButtonWithIcon("play_arrow", "Generate", icon_size=20)
        self.generate_button.setToolTip("Generate candidate blocks with current settings")
        self.generate_button.clicked.connect(self.generate_blocks)
        button_layout.addWidget(self.generate_button)

        # Status label
        self.status_label = QLabel("Ready")
        button_layout.addWidget(self.status_label)
        button_layout.addStretch()
        pane_layout.addLayout(button_layout)

        return pane

    def _build_block_candidates_pane(self) -> QFrame:
        """Build the Block Candidates pane (bottom-right)."""
        pane = QFrame(self)
        pane.setFrameShape(QFrame.Shape.StyledPanel)
        pane_layout = QVBoxLayout(pane)

        candidates_header = QLabel("Block Candidates")
        candidates_header_font = QFont()
        candidates_header_font.setBold(True)
        candidates_header.setFont(candidates_header_font)
        pane_layout.addWidget(candidates_header)

        # Scrollable area for candidates
        self.candidates_scroll = QScrollArea(self)
        self.candidates_scroll.setWidgetResizable(True)
        self.candidates_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.candidates_container = QWidget(self)
        self.candidates_grid = QGridLayout(self.candidates_container)
        self.candidates_grid.setSpacing(8)
        self.candidates_scroll.setWidget(self.candidates_container)

        pane_layout.addWidget(self.candidates_scroll)

        return pane

    def set_prompt(self, prompt: str) -> None:
        """Set the prompt text in the display."""
        self.prompt = prompt
        self.prompt_display.setPlainText(prompt)

    def _sync_controller_settings(self) -> None:
        """Synchronize UI field values to the controller."""
        self.controller.global_instructions = self.global_instructions_field.toPlainText()
        self.controller.block_instructions = self.block_instructions_field.toPlainText()
        self.controller.manual_prefix = self.manual_prefix_field.toPlainText()
        self.controller.temperature = self.temperature_spin.value() / 100.0
        self.controller.top_k = self.top_k_spin.value()

    @pyqtSlot()
    def generate_blocks(self) -> None:
        """Trigger generation of candidate blocks."""
        self._sync_controller_settings()
        width = self.width_spin.value()

        self.status_label.setText(f"Generating {width} candidates...")
        self.generate_button.setEnabled(False)

        try:
            new_candidates = self.controller.generate_candidates(
                width=width,
                on_candidate=self._on_candidate_generated,
            )
            self.status_label.setText(f"Generated {len(new_candidates)} new candidates (total: {len(self.controller.candidates)})")
        except Exception as exc:  # pylint: disable=broad-except
            self.log.exception("Block generation failed.")
            self.status_label.setText(f"Generation error: {exc}")
        finally:
            self.generate_button.setEnabled(True)

    def _on_candidate_generated(self, candidate: BlockCandidate) -> None:
        """Handle a newly generated candidate — add to the grid."""
        self._add_candidate_widget(candidate)

    def _add_candidate_widget(self, candidate: BlockCandidate) -> None:
        """Create and add a BlockCandidateWidget to the grid."""
        widget = BlockCandidateWidget(candidate, parent=self.candidates_container)

        # Connect signals
        widget.accept_button.clicked.connect(lambda checked=False, c=candidate: self._on_accept_candidate(c))
        widget.edit_button.clicked.connect(lambda checked=False, c=candidate, w=widget: self._on_edit_candidate(c, w))
        widget.rewrite_button.clicked.connect(lambda checked=False, c=candidate: self._on_rewrite_candidate(c))
        widget.shorter_button.clicked.connect(lambda checked=False, c=candidate: self._on_shorter_candidate(c))
        widget.longer_button.clicked.connect(lambda checked=False, c=candidate: self._on_longer_candidate(c))

        self.candidate_widgets.append(widget)
        self._rearrange_candidates_grid()

    def _rearrange_candidates_grid(self) -> None:
        """Rearrange all candidate widgets in the grid based on current width."""
        # Remove all widgets from grid
        while self.candidates_grid.count():
            item = self.candidates_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Re-add in grid layout
        for i, widget in enumerate(self.candidate_widgets):
            row = i // self.grid_width
            col = i % self.grid_width
            self.candidates_grid.addWidget(widget, row, col)

    def _clear_candidate_widgets(self) -> None:
        """Remove all candidate widgets from the grid."""
        for widget in self.candidate_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.candidate_widgets.clear()

    @pyqtSlot()
    def _on_accept_candidate(self, candidate: BlockCandidate) -> None:
        """Accept a candidate block — append to completion, clear candidates."""
        self.controller.accept_candidate(candidate)
        self._clear_candidate_widgets()
        self._update_completion_display()
        self.is_saved = False
        self.status_label.setText(f"Block accepted. Total blocks: {len(self.controller.accepted_blocks)}")

    def _on_edit_candidate(self, candidate: BlockCandidate, widget: BlockCandidateWidget) -> None:
        """Edit a candidate — create new candidate with edited text."""
        text, ok = QInputDialog.getMultiLineText(self, "Edit Block", "Edit the block text:", candidate.text)
        if ok and text:
            new_candidate = self.controller.create_edited_candidate(candidate, text)
            self._add_candidate_widget(new_candidate)

    def _on_rewrite_candidate(self, candidate: BlockCandidate) -> None:
        """Rewrite a candidate with custom instructions."""
        instruction, ok = QInputDialog.getText(self, "Rewrite Instructions", "Enter rewriting instructions:")
        if ok and instruction:
            self.status_label.setText("Rewriting block...")
            new_candidate = self.controller.rewrite_block(candidate, instruction)
            if new_candidate:
                self._add_candidate_widget(new_candidate)
                self.status_label.setText("Rewrite complete.")
            else:
                self.status_label.setText("Rewrite failed.")

    def _on_shorter_candidate(self, candidate: BlockCandidate) -> None:
        """Make a candidate shorter."""
        self.status_label.setText("Making block shorter...")
        new_candidate = self.controller.make_shorter(candidate)
        if new_candidate:
            self._add_candidate_widget(new_candidate)
            self.status_label.setText("Shorter version generated.")
        else:
            self.status_label.setText("Make shorter failed.")

    def _on_longer_candidate(self, candidate: BlockCandidate) -> None:
        """Make a candidate longer."""
        self.status_label.setText("Making block longer...")
        new_candidate = self.controller.make_longer(candidate)
        if new_candidate:
            self._add_candidate_widget(new_candidate)
            self.status_label.setText("Longer version generated.")
        else:
            self.status_label.setText("Make longer failed.")

    def _update_completion_display(self) -> None:
        """Update the completion text display and gutter stats."""
        accepted_text = self.controller.accepted_text
        self.completion_text.setPlainText(accepted_text)

        # Update gutter stats
        blocks = len(self.controller.accepted_blocks)
        words = len(accepted_text.split()) if accepted_text else 0
        self.gutter_label.setText(f"Blocks: {blocks} | Words: {words}")

    @pyqtSlot(bool)
    def _on_edit_toggled(self, checked: bool) -> None:
        """Toggle edit mode for the completion text."""
        self.is_edit_enabled = checked
        self.completion_text.setReadOnly(not checked)
        if checked:
            self.is_saved = False

    def _on_completion_text_changed(self) -> None:
        """Handle manual text changes — mark as unsaved."""
        if self.is_edit_enabled:
            self.is_saved = False

    def _copy_completion(self) -> None:
        """Copy completion text to clipboard."""
        clipboard = self.app.clipboard() if hasattr(self.app, 'clipboard') else None
        if clipboard:
            clipboard.setText(self.completion_text.toPlainText())
        self.status_label.setText("Copied to clipboard.")

    @pyqtSlot()
    def save_completion(self) -> None:
        """Save the current completion text as a new PromptCompletion."""
        # Update accepted text from potentially edited completion
        current_text = self.completion_text.toPlainText()
        if not current_text.strip():
            QMessageBox.warning(self, "Warning", "Cannot save an empty completion.")
            return

        # Rebuild accepted_blocks from current text if it was manually edited
        if self.is_edit_enabled:
            self.controller.accepted_blocks = [current_text]

        if self.sample_widget:
            response = self.controller.build_save_response()
            self.sample_widget.add_completion(response)
            self.is_saved = True
            self.status_label.setText("Completion saved.")
        else:
            QMessageBox.warning(self, "Warning", "No sample widget connected. Cannot save.")

    def resizeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Handle window resize to adjust candidate grid width."""
        super().resizeEvent(event)
        available_width = self.candidates_scroll.viewport().width() - 20
        new_grid_width = max(1, available_width // self.min_candidate_width)
        if new_grid_width != self.grid_width:
            self.grid_width = new_grid_width
            self._rearrange_candidates_grid()
