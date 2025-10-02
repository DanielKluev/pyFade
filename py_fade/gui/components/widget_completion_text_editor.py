"""
Widget for editing completion text with formatting and highlighting capabilities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor, QMouseEvent
from PyQt6.QtWidgets import QTextEdit, QToolTip, QWidget

from py_fade.gui.auxillary import logprob_to_qcolor
from py_fade.data_formats.base_data_classes import CommonCompletionProtocol, CommonCompletionLogprobs, SinglePositionToken

if TYPE_CHECKING:
    from py_fade.gui.components.widget_completion import CompletionFrame
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.providers.llm_response import LLMResponse

PREFILL_COLOR = QColor("#FFF9C4")
BEAM_TOKEN_COLOR = QColor("#C5E1A5")


class CompletionTextEdit(QTextEdit):
    """
    Custom QTextEdit that supports prefill, beam token and heatmap highlighting.
    """
    _completion: CommonCompletionProtocol | None = None
    _logprobs: CommonCompletionLogprobs | None = None
    is_heatmap_mode: bool = False  # Whether to show logprob heatmap or prefill/beam highlights

    def __init__(self, completion_frame: 'CompletionFrame', parent: QWidget | None = None):
        super().__init__(parent)
        self.log = logging.getLogger("CompletionTextEdit")
        self.completion_frame = completion_frame
        self._token_positions_cache: list[tuple[int, int, SinglePositionToken]] = []

    def update_heatmap_cache(self, logprobs_data: CommonCompletionLogprobs, text: str) -> None:
        """Update cached token positions for tooltip lookups."""
        self._token_positions_cache = []

        text_pos = 0
        for token_data in logprobs_data.sampled_logprobs:
            token = token_data.token_str
            logprob = token_data.logprob

            if not token or logprob is None:
                continue

            # Find token position in text
            token_len = len(token)
            if text_pos + token_len > len(text):
                break

            if text[text_pos:text_pos + token_len] == token:
                self._token_positions_cache.append((text_pos, text_pos + token_len, token_data))
                text_pos += token_len
            else:
                # Try to find token starting from current position
                found_pos = text.find(token, text_pos)
                if found_pos != -1 and found_pos <= text_pos + 10:  # Don't search too far ahead
                    self._token_positions_cache.append((found_pos, found_pos + token_len, token_data))
                    text_pos = found_pos + token_len
                else:
                    text_pos += 1  # Skip character if token not found nearby

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Handle mouse move events to show tooltips in heatmap mode."""
        super().mouseMoveEvent(event)

        if not self.completion_frame.is_heatmap_mode or not self._token_positions_cache:
            return

        # Get cursor position at mouse location
        cursor = self.cursorForPosition(event.pos())
        cursor_pos = cursor.position()

        # Find which token contains this position
        for start_pos, end_pos, token_data in self._token_positions_cache:
            if start_pos <= cursor_pos < end_pos:
                # Show tooltip with logprob value
                tooltip_text = f"Token: '{token_data.token_str}', logprob: {token_data.logprob:.4f}"
                QToolTip.showText(event.globalPosition().toPoint(), tooltip_text, self)
                return

        # Hide tooltip if not over a token
        QToolTip.hideText()

    def set_completion(self, completion: CommonCompletionProtocol) -> None:
        """
        Set the completion content and apply appropriate highlighting.
        """
        self._completion = completion
        self._logprobs = None
        self.is_heatmap_mode = False
        self._update_text_display()

    def set_logprobs(self, logprobs: CommonCompletionLogprobs | None) -> None:
        """
        Cache logprobs for heatmap highlighting.
        """
        self._logprobs = logprobs

    def set_heatmap_mode(self, enabled: bool) -> None:
        """
        Enable or disable heatmap mode and update display.
        """
        if not self._completion or not self._logprobs:
            self.is_heatmap_mode = False
            return
        if self.is_heatmap_mode != enabled:
            self.is_heatmap_mode = enabled
            self._update_text_display()

    def _update_text_display(self) -> None:
        """Update text display based on completion content."""
        if not self._completion:
            return

        text = self._completion.completion_text

        self.blockSignals(True)
        self.setPlainText(text)
        self._clear_highlights()

        if text:
            if self.is_heatmap_mode:
                self._highlight_logprob_heatmap()
            else:
                self._highlight_prefill_and_beam()
        self.blockSignals(False)

    def _clear_highlights(self) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.endEditBlock()

    def _highlight_prefill_and_beam(self) -> None:
        """
        Highlight prefill and beam token sections in the text.
        """
        if not self._completion:
            return
        document_cursor = self.textCursor()

        def apply_highlight(start: int, end: int, color: QColor) -> None:
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(color)
            cursor = QTextCursor(document_cursor)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(highlight_format)

        text = self._completion.completion_text
        prefill = self._completion.prefill
        beam_token = self._completion.beam_token

        if prefill:
            start = text.find(prefill)
            if start >= 0:
                end = start + len(prefill)
                apply_highlight(start, end, PREFILL_COLOR)
                if beam_token:
                    beam_start = text.find(beam_token, start)
                    if beam_start >= 0:
                        beam_end = beam_start + len(beam_token)
                        apply_highlight(beam_start, beam_end, BEAM_TOKEN_COLOR)
                    else:
                        self.log.debug("Beam token '%s' not found within completion text.", beam_token)
            else:
                self.log.debug("Prefill '%s' not found in completion text.", prefill)
        elif beam_token:
            beam_start = text.find(beam_token)
            if beam_start >= 0:
                apply_highlight(beam_start, beam_start + len(beam_token), BEAM_TOKEN_COLOR)

    def _highlight_logprob_heatmap(self) -> None:
        """
        Apply logprob-based color highlighting to tokens.
        """
        if not self._completion or not self._logprobs:
            return
        text = self._completion.completion_text
        logprobs_data = self._logprobs
        self.update_heatmap_cache(logprobs_data, text)

        document_cursor = self.textCursor()
        text_pos = 0

        for token_data in logprobs_data.sampled_logprobs:
            token = token_data.token_str
            logprob = token_data.logprob

            # Find token position in text
            token_len = len(token)
            if text_pos + token_len > len(text):
                break
            if text[text_pos:text_pos + token_len] != token:
                # Try to find token starting from current position
                found_pos = text.find(token, text_pos)
                if found_pos == -1 or found_pos > text_pos + 10:  # Don't search too far ahead
                    text_pos += 1  # Skip character if token not found nearby
                    continue
                text_pos = found_pos

            # Apply color based on logprob
            color = logprob_to_qcolor(logprob)

            # Create highlight format
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(color)

            # Apply highlight
            cursor = QTextCursor(document_cursor)
            cursor.setPosition(text_pos)
            cursor.setPosition(text_pos + token_len, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(highlight_format)

            text_pos += token_len
