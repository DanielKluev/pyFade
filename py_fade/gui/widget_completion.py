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
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.auxillary import logprob_to_qcolor
from py_fade.dataset.sample import Sample
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.completion import PromptCompletion

class CompletionFrame(QFrame):
    """UI frame representing a single completion."""
    icons_size = 24
    def __init__(self, completion: "PromptCompletion", parent=None):
        super().__init__(parent)
        self.completion = completion
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)

        header = QLabel(
            f"""<span style="font-family: 'Material Symbols Outlined';">{google_icon_font.codepoint('model')}</span> {completion.model_id} <span style="font-family: 'Material Symbols Outlined';">{google_icon_font.codepoint('temperature')}</span> {completion.temperature} | top_k={completion.top_k}"""
        )
        header.setFont(google_icon_font.icon_font)
        #header.setStyleSheet("font-family: 'Material Symbols Outlined'; font-size: 16px; font-weight: bold;")

        text = QTextEdit(self)
        text.setReadOnly(True)

        # Set the full text first
        text.setPlainText(str(completion.completion_text))

        status_layout = QHBoxLayout()
        if completion.is_truncated:
            self.truncated_label = QLabel()
            self.truncated_label.setPixmap(google_icon_font.pixmap("is_truncated", size=self.icons_size, color="red"))
            self.truncated_label.setToolTip("Completion was truncated due to max tokens limit.")
            status_layout.addWidget(self.truncated_label)

        self.metrics_label = QLabel()
        if completion.logprobs and completion.logprobs[0].min_logprob is not None:
            self.metrics_label.setPixmap(
                google_icon_font.pixmap("metrics", size=self.icons_size, color=logprob_to_qcolor(completion.logprobs[0].min_logprob))
                )
            self.metrics_label.setToolTip(f"Logprobs min: {completion.logprobs[0].min_logprob:.2f}, avg: {completion.logprobs[0].avg_logprob:.2f}")
        else:
            self.metrics_label.setPixmap(google_icon_font.pixmap("metrics", size=self.icons_size, color="gray"))
            self.metrics_label.setToolTip("No logprobs available.")

        # Prefill
        if completion.prefill:
            self.prefill_label = QLabel()
            self.prefill_label.setPixmap(google_icon_font.pixmap("prefill", size=self.icons_size))
            self.prefill_label.setToolTip(f"Prefill used: {completion.prefill}")
            status_layout.addWidget(self.prefill_label)

        # Beam token
        if completion.beam_token:
            self.beam_label = QLabel()
            self.beam_label.setPixmap(google_icon_font.pixmap("beaming", size=self.icons_size))
            self.beam_label.setToolTip(f"Beam token used: '{completion.beam_token}'")
            status_layout.addWidget(self.beam_label)

        status_layout.addWidget(self.metrics_label)
        status_layout.addStretch()

        # Highlight prefill in the completion text if present
        if not completion.prefill is None:
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

        layout.addWidget(header)
        layout.addLayout(status_layout)
        layout.addWidget(text)