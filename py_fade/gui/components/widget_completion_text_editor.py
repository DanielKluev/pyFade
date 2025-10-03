"""
Widget for editing completion text with formatting and highlighting capabilities.

This module provides a custom QTextEdit widget that properly handles text highlighting
for emoji and multi-byte Unicode characters by using Qt's native UTF-16 text positioning
instead of Python string indexing.
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

    This widget properly handles emoji and multi-byte Unicode characters by using
    Qt's document.find() and QTextCursor methods for text positioning, which work
    with UTF-16 code units instead of Python's Unicode code points.
    """
    _completion: CommonCompletionProtocol | None = None
    _logprobs: CommonCompletionLogprobs | None = None
    is_heatmap_mode: bool = False  # Whether to show logprob heatmap or prefill/beam highlights

    def __init__(self, completion_frame: 'CompletionFrame', parent: QWidget | None = None):
        super().__init__(parent)
        self.log = logging.getLogger("CompletionTextEdit")
        self.completion_frame = completion_frame
        self._token_positions_cache: list[tuple[int, int, SinglePositionToken]] = []

    def update_heatmap_cache(self, logprobs_data: CommonCompletionLogprobs, text: str) -> None:  # pylint: disable=unused-argument
        """
        Update cached token positions for tooltip lookups.

        Uses Qt document to properly handle UTF-16 positioning for emoji and multi-byte characters.
        The `text` parameter is kept for API compatibility but not used since we use Qt's document directly.
        """
        self._token_positions_cache = []

        # Use Qt's document to search for tokens, which handles UTF-16 properly
        search_start_pos = 0

        for token_data in logprobs_data.sampled_logprobs:
            token = token_data.token_str
            logprob = token_data.logprob

            if not token or logprob is None:
                continue

            # Use Qt's find method which handles UTF-16 properly
            cursor = self.document().find(token, search_start_pos)

            if not cursor.isNull():
                # Found the token
                start_pos = cursor.selectionStart()
                end_pos = cursor.selectionEnd()
                self._token_positions_cache.append((start_pos, end_pos, token_data))
                search_start_pos = end_pos
            else:
                # Token not found, try searching a bit ahead
                # This handles cases where tokens don't perfectly match the text
                cursor = self.document().find(token, search_start_pos)
                if not cursor.isNull():
                    start_pos = cursor.selectionStart()
                    end_pos = cursor.selectionEnd()
                    # Only accept if within reasonable distance
                    if start_pos <= search_start_pos + 20:  # Allow some leeway
                        self._token_positions_cache.append((start_pos, end_pos, token_data))
                        search_start_pos = end_pos
                    else:
                        # Skip this token and advance by 1
                        search_start_pos += 1
                else:
                    # Skip character if token not found
                    search_start_pos += 1

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

        The beam token should overlap and be at the end of the prefill.
        Only the non-overlapping part of prefill is highlighted as PREFILL_COLOR,
        while the overlapping part (beam token) is highlighted as BEAM_TOKEN_COLOR.

        Uses Qt's text search to properly handle UTF-16 positioning for emoji and multi-byte characters.
        """
        if not self._completion:
            return

        def apply_highlight_by_search(search_text: str, color: QColor, start_pos: int = 0) -> int:
            """
            Find and highlight text using Qt's search, returning the end position or -1 if not found.

            Returns the UTF-16 position after the found text, or -1 if not found.
            """
            # Use Qt's document find method which handles UTF-16 properly
            cursor = self.document().find(search_text, start_pos)
            if cursor.isNull():
                return -1

            # Apply highlighting
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(color)
            cursor.mergeCharFormat(highlight_format)

            # Return position after the found text
            return cursor.position()

        prefill = self._completion.prefill
        beam_token = self._completion.beam_token

        if prefill and beam_token:
            # Beam token should be at the end of prefill, overlapping with it
            # Check if beam_token is at the end of prefill
            if prefill.endswith(beam_token):
                # Split highlighting: non-overlapping prefill part + beam token part
                # Calculate the non-overlapping part of prefill
                prefill_only_part = prefill[:-len(beam_token)] if len(beam_token) < len(prefill) else ""

                if prefill_only_part:
                    # Highlight the non-overlapping part of prefill
                    prefill_only_end = apply_highlight_by_search(prefill_only_part, PREFILL_COLOR)
                    if prefill_only_end < 0:
                        self.log.debug("Non-overlapping prefill part '%s' not found in completion text.", prefill_only_part)
                        return

                    # Highlight beam token starting from the end of non-overlapping part
                    beam_end = apply_highlight_by_search(beam_token, BEAM_TOKEN_COLOR, prefill_only_end)
                    if beam_end < 0:
                        self.log.debug("Beam token '%s' not found after prefill in completion text.", beam_token)
                else:
                    # Entire prefill is the beam token (no non-overlapping part)
                    beam_end = apply_highlight_by_search(beam_token, BEAM_TOKEN_COLOR)
                    if beam_end < 0:
                        self.log.debug("Beam token '%s' not found in completion text.", beam_token)
            else:
                # Beam token not at end of prefill - this shouldn't happen in normal usage
                self.log.warning("Beam token '%s' is not at the end of prefill '%s'. Highlighting separately.", beam_token, prefill)
                # Fallback: highlight prefill and beam token separately
                prefill_end = apply_highlight_by_search(prefill, PREFILL_COLOR)
                if prefill_end >= 0 and beam_token:
                    beam_end = apply_highlight_by_search(beam_token, BEAM_TOKEN_COLOR)
                    if beam_end < 0:
                        self.log.debug("Beam token '%s' not found in completion text.", beam_token)
        elif prefill:
            # Only prefill, no beam token
            prefill_end = apply_highlight_by_search(prefill, PREFILL_COLOR)
            if prefill_end < 0:
                self.log.debug("Prefill '%s' not found in completion text.", prefill)
        elif beam_token:
            # Only beam token, no prefill
            beam_end = apply_highlight_by_search(beam_token, BEAM_TOKEN_COLOR)
            if beam_end < 0:
                self.log.debug("Beam token '%s' not found in completion text.", beam_token)

    def _highlight_logprob_heatmap(self) -> None:
        """
        Apply logprob-based color highlighting to tokens.

        Uses Qt document search to properly handle UTF-16 positioning for emoji and multi-byte characters.
        """
        if not self._completion or not self._logprobs:
            return

        text = self._completion.completion_text
        logprobs_data = self._logprobs
        self.update_heatmap_cache(logprobs_data, text)

        # Use the cache to apply highlighting
        for start_pos, end_pos, token_data in self._token_positions_cache:
            logprob = token_data.logprob

            # Apply color based on logprob
            color = logprob_to_qcolor(logprob)

            # Create highlight format
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(color)

            # Apply highlight using Qt cursor
            cursor = self.textCursor()
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(highlight_format)
