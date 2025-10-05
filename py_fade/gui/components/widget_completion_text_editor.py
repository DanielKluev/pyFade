"""
Widget for editing completion text with formatting and highlighting capabilities.

This module provides a custom QTextEdit widget that properly handles text highlighting
for emoji, multi-byte Unicode characters, and multi-line text (with newlines) by using
manual string search combined with Qt's QTextCursor for positioning.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt
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

    This widget properly handles emoji, multi-byte Unicode characters, and multi-line
    text (with newlines) by using manual string search with QTextCursor positioning.
    This approach works correctly with UTF-16 code units and multi-line strings.
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

        if not self.is_heatmap_mode or not self._token_positions_cache:
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

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Handle mouse press events to trigger beam-out from heatmap token clicks."""
        super().mousePressEvent(event)

        # Only handle left clicks in heatmap mode
        if not self.is_heatmap_mode or not self._token_positions_cache:
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Get cursor position at click location
        cursor = self.cursorForPosition(event.pos())
        cursor_pos = cursor.position()

        # Find which token was clicked
        for idx, (start_pos, end_pos, _token_data) in enumerate(self._token_positions_cache):
            if start_pos <= cursor_pos < end_pos:
                # Token clicked - emit signal with token index
                self.completion_frame.on_heatmap_token_clicked(idx)
                return

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

        Uses manual string search with QTextCursor positioning to handle multi-line text and UTF-16 properly.
        """
        if not self._completion:
            return

        def apply_highlight_by_search(search_text: str, color: QColor, start_pos: int = 0) -> int:
            """
            Find and highlight text using manual string search, returning the end position or -1 if not found.

            Args:
                search_text: The text to search for
                color: The background color to apply
                start_pos: Starting Qt UTF-16 position to search from (default 0)

            Returns:
                The Qt UTF-16 position after the found text, or -1 if not found.

            Uses manual string search instead of Qt's document.find() to support multi-line text (newlines).
            Handles UTF-16 surrogate pairs (emoji) correctly by converting between Python and Qt positions.
            """
            # Get the plain text for string searching
            plain_text = self.toPlainText()

            # Convert Qt UTF-16 start_pos to Python string position
            # We need to count how many Python characters correspond to start_pos UTF-16 code units
            py_start_pos = 0
            utf16_pos = 0
            for i, char in enumerate(plain_text):
                if utf16_pos >= start_pos:
                    py_start_pos = i
                    break
                # Count UTF-16 code units for this character
                char_utf16_len = len(char.encode('utf-16-le')) // 2
                utf16_pos += char_utf16_len
            else:
                # Reached end of text
                py_start_pos = len(plain_text)

            # Find the search text in the plain text (using Python string positions)
            py_search_pos = plain_text.find(search_text, py_start_pos)
            if py_search_pos == -1:
                return -1

            # Convert Python string position to Qt UTF-16 position
            # Count UTF-16 code units for characters before the search position
            text_before = plain_text[:py_search_pos]
            qt_search_pos = len(text_before.encode('utf-16-le')) // 2

            # Calculate UTF-16 length of the search text for Qt cursor positioning
            # Qt uses UTF-16 code units, where emoji and other characters outside BMP
            # are represented as surrogate pairs (2 code units)
            utf16_length = len(search_text.encode('utf-16-le')) // 2

            # Create cursor and select the found text using Qt positions
            cursor = self.textCursor()
            cursor.setPosition(qt_search_pos)
            cursor.setPosition(qt_search_pos + utf16_length, QTextCursor.MoveMode.KeepAnchor)

            # Apply highlighting
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(color)
            cursor.mergeCharFormat(highlight_format)

            # Return position after the found text (in UTF-16 code units)
            return qt_search_pos + utf16_length

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
