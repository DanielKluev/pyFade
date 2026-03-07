"""
Token Count Calculator window.

This module provides a non-modal dialog window for counting words and tokens
in a text selection. The window displays an editable text area and live statistics
(word count and token count) that update with a debounce delay.

Multiple independent instances can be opened simultaneously.

Key classes: ``WindowTokenCalculator``
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from py_fade.providers.providers_manager import InferenceProvidersManager

# Delay in milliseconds before stats are recalculated after text changes.
STATS_UPDATE_DELAY_MS = 400


def count_words(text: str) -> int:
    """
    Count the number of words in the given text.

    Words are defined as whitespace-separated tokens.

    Args:
        text: The text to count words in.

    Returns:
        Number of words found in the text.
    """
    return len(text.split()) if text.strip() else 0


class WindowTokenCalculator(QDialog):
    """
    Non-modal dialog window for counting words and tokens in text.

    Provides an editable text area and a read-only statistics area that
    displays the word count and token count (using the currently selected
    target model). Statistics are recalculated with a short debounce delay
    after each text change to avoid excessive computation while the user
    is typing.

    The window is resizable and multiple independent instances may coexist.
    """

    def __init__(self, providers_manager: "InferenceProvidersManager", initial_text: str = "", parent: QWidget | None = None) -> None:
        """
        Initialize the Token Count Calculator window.

        Args:
            providers_manager: Inference providers manager used for token counting.
            initial_text: Optional text to pre-populate the text area with.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.providers_manager = providers_manager

        # Window configuration
        self.setWindowTitle("Token Count Calculator")
        self.setMinimumSize(420, 280)
        self.resize(600, 400)
        self.setModal(False)

        # Debounce timer for stats updates
        self._stats_timer = QTimer(self)
        self._stats_timer.setSingleShot(True)
        self._stats_timer.setInterval(STATS_UPDATE_DELAY_MS)
        self._stats_timer.timeout.connect(self._update_stats)

        self.setup_ui()

        if initial_text:
            self.text_area.setPlainText(initial_text)
        # Compute initial stats immediately
        self._update_stats()

    def setup_ui(self) -> None:
        """
        Build the UI components.

        Creates the main layout with an editable text area and a statistics
        label that shows word and token counts.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header label
        header_label = QLabel("Enter or paste text to count words and tokens:", self)
        header_label.setStyleSheet("font-weight: 500;")
        layout.addWidget(header_label)

        # Editable text area
        self.text_area = QPlainTextEdit(self)
        self.text_area.setPlaceholderText("Type or paste text here…")
        self.text_area.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_area)

        # Statistics display row
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(8)

        self.stats_label = QLabel(self)
        self.stats_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.stats_label.setStyleSheet("font-size: 13px; padding: 4px; background-color: #f5f5f5; border-radius: 4px;")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

    # ------------------------------------------------------------------
    # Text change handling
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        """
        Handle text area content change.

        Restarts the debounce timer so that stats are only recalculated
        after the user stops typing for ``STATS_UPDATE_DELAY_MS`` ms.
        """
        self._stats_timer.start()

    # ------------------------------------------------------------------
    # Statistics computation
    # ------------------------------------------------------------------

    def _update_stats(self) -> None:
        """
        Recalculate and display word and token counts for the current text.

        Uses ``providers_manager.count_tokens`` for token counting and a simple
        whitespace-split heuristic for word counting.
        """
        text = self.text_area.toPlainText()
        words = count_words(text)
        tokens = self.providers_manager.count_tokens(text) if text.strip() else 0
        self.stats_label.setText(f"Words: {words}  |  Tokens: {tokens}")
        self.log.debug("Stats updated: words=%d, tokens=%d", words, tokens)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_text(self, text: str) -> None:
        """
        Replace the text area content and immediately update statistics.

        Bypasses the debounce timer so the stats label reflects the new
        content right away.  Useful when programmatically pre-filling text.

        Args:
            text: New text content.
        """
        self.text_area.setPlainText(text)
        # For programmatic updates, bypass the debounce and refresh stats immediately.
        self._stats_timer.stop()
        self._update_stats()

    def get_text(self) -> str:
        """
        Return the current text area content.

        Returns:
            The plain text currently displayed.
        """
        return self.text_area.toPlainText()
