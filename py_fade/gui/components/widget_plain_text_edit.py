"""
Plain text only QTextEdit widget.

This module provides a QTextEdit subclass that enforces plain text input only,
rejecting rich formatting from copy-paste operations while preserving 
programmed formatting markers like flat prefix templates.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QMimeData
from PyQt6.QtWidgets import QTextEdit

if TYPE_CHECKING:
    pass


class PlainTextEdit(QTextEdit):
    """
    QTextEdit subclass that accepts only plain text input.
    
    This widget prevents rich text formatting from being pasted or inserted,
    ensuring that only plain text content is accepted. However, it preserves
    programmed formatting markers that are part of the application's template
    system (e.g., FLAT_PREFIX_SYSTEM, FLAT_PREFIX_USER, etc.).
    
    Key features:
    - Rejects rich HTML content from copy-paste operations
    - Forces all input to plain text only
    - Maintains compatibility with existing QTextEdit API
    - Preserves programmed formatting markers from application templates
    """

    def __init__(self, parent=None):
        """
        Initialize PlainTextEdit widget.
        
        Args:
            parent: Parent widget, passed to QTextEdit constructor
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)

        # Disable rich text acceptance - this is the key setting
        self.setAcceptRichText(False)

        # Log widget initialization for debugging
        self.log.debug("PlainTextEdit initialized with rich text disabled")

    def insertFromMimeData(self, source: QMimeData) -> None:  # pylint: disable=invalid-name
        """
        Override insertFromMimeData to ensure only plain text is inserted.
        
        This method is called when content is pasted or dropped into the editor.
        It ensures that only the plain text portion of the clipboard/drag data
        is inserted, ignoring any rich formatting.
        
        Args:
            source: QMimeData containing the content to be inserted
        """
        if source.hasText():
            # Get only the plain text portion, ignoring any HTML/rich content
            plain_text = source.text()

            # Log the operation for debugging
            self.log.debug("Inserting plain text only: %d characters", len(plain_text))

            # Create new QMimeData with only plain text
            plain_mime_data = QMimeData()
            plain_mime_data.setText(plain_text)

            # Call parent with plain text only
            super().insertFromMimeData(plain_mime_data)
        else:
            # If there's no text content, do nothing
            self.log.debug("No text content found in mime data, ignoring insertion")

    def setHtml(self, text: str) -> None:  # pylint: disable=invalid-name
        """
        Override setHtml to prevent rich text from being set programmatically.
        
        This ensures that even if code tries to set HTML content directly,
        only the plain text portion is actually set in the widget.
        
        Args:
            text: HTML text that would normally be set in the widget
        """
        # Convert HTML to plain text and set that instead
        # This is a safety net in case code tries to set HTML directly
        self.log.debug("setHtml called, converting to plain text only")
        temp_edit = QTextEdit()
        temp_edit.setHtml(text)
        plain_text = temp_edit.toPlainText()
        temp_edit.deleteLater()

        self.setPlainText(plain_text)
