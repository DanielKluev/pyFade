"""Widgets for presenting model completions within the dataset view."""

from typing import TYPE_CHECKING

from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from py_fade.gui.auxillary import logprob_to_qcolor
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon, QLabelWithIconAndText

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion


class CompletionFrame(QFrame):
    """UI frame representing a single completion."""

    icons_size = 24

    def __init__(self, completion: "PromptCompletion", parent=None):
        super().__init__(parent)
        self.completion = completion
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()

        ## Model ID with icon
        self.model_label = QLabelWithIconAndText(
            "model", completion.model_id, size=14, parent=self
            )
        header_layout.addWidget(self.model_label)
        header_layout.addStretch()

        ## Temperature and top_k
        if completion.temperature is not None and completion.top_k is not None and completion.top_k == 1:
            self.temperature_label = QLabelWithIcon("mode_cool", size=14, parent=self, color="blue", tooltip=f"Temperature: {completion.temperature}, top_k: {completion.top_k}")
        else:
            self.temperature_label = QLabelWithIconAndText("temperature", f"{completion.temperature}, K: {completion.top_k}", size=14, parent=self, color="red", tooltip=f"Temperature: {completion.temperature}, top_k: {completion.top_k}")
        header_layout.addWidget(self.temperature_label)

        status_layout = QHBoxLayout()
        # Is truncated?
        if completion.is_truncated:
            self.truncated_label = QLabelWithIcon("is_truncated", size=self.icons_size, color="red", tooltip="Completion was truncated due to max tokens limit.")
            status_layout.addWidget(self.truncated_label)

       # Prefill
        if completion.prefill:
            self.prefill_label = QLabelWithIcon("prefill", size=self.icons_size, tooltip=f"Prefill used: {completion.prefill}")
            status_layout.addWidget(self.prefill_label)

        # Beam token
        if completion.beam_token:
            self.beam_label = QLabelWithIcon("beaming", size=self.icons_size, tooltip=f"Beam token used: '{completion.beam_token}'")
            status_layout.addWidget(self.beam_label)

        # Metrics (logprobs)
        if completion.logprobs and completion.logprobs[0].min_logprob is not None:
            self.metrics_label = QLabelWithIcon("metrics", size=self.icons_size, color="logprob", logprob=completion.logprobs[0].min_logprob, tooltip=f"Logprobs min: {completion.logprobs[0].min_logprob:.3f}, avg: {completion.logprobs[0].avg_logprob:.3f}")
        else:
            self.metrics_label = QLabelWithIcon("metrics", size=self.icons_size, color="gray", tooltip="No logprobs available.")
        status_layout.addWidget(self.metrics_label)

        status_layout.addStretch()

        text = QTextEdit(self)
        text.setReadOnly(True)

        # Set the full text first
        text.setPlainText(str(completion.completion_text))

        # Highlight prefill in the completion text if present
        if completion.prefill is not None:
            if completion.prefill != "" and completion.prefill in completion.completion_text:
                prefill_start = completion.completion_text.index(completion.prefill)
                prefill_end = prefill_start + len(completion.prefill)

                # Create a format for highlighting
                highlight_format = QTextCharFormat()
                highlight_format.setBackground(QColor("yellow"))

                # Apply the format to the prefill portion
                cursor = text.textCursor()
                cursor.setPosition(prefill_start)
                cursor.setPosition(prefill_end, QTextCursor.MoveMode.KeepAnchor)
                cursor.mergeCharFormat(highlight_format)

        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        text.setSizePolicy(policy)

        layout.addLayout(header_layout)
        layout.addLayout(status_layout)
        layout.addWidget(text)
