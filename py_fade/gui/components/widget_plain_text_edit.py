"""
Plain text only QTextEdit widget.

This module provides a QTextEdit subclass that enforces plain text input only,
rejecting rich formatting from copy-paste operations while preserving 
programmed formatting markers like flat prefix templates.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QMimeData
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QTextEdit

from py_fade.providers.flat_prefix_template import FLAT_PREFIX_SYSTEM, FLAT_PREFIX_USER, FLAT_PREFIX_ASSISTANT

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

    def contextMenuEvent(self, event):  # pylint: disable=invalid-name
        """
        Override contextMenuEvent to add role tag insertion options.
        
        Creates a custom context menu with options to insert role tags
        at the cursor position or at the end of the text.
        
        Args:
            event: QContextMenuEvent with position information
        """
        # Create the default context menu
        menu = self.createStandardContextMenu()

        # Add separator before role tag options
        menu.addSeparator()

        # Add role tag insertion actions
        insert_system_action = QAction("Insert System Tag at Cursor", self)
        insert_system_action.triggered.connect(lambda: self.insert_role_tag_at_cursor(FLAT_PREFIX_SYSTEM))
        menu.addAction(insert_system_action)

        insert_user_action = QAction("Insert User Tag at Cursor", self)
        insert_user_action.triggered.connect(lambda: self.insert_role_tag_at_cursor(FLAT_PREFIX_USER))
        menu.addAction(insert_user_action)

        insert_assistant_action = QAction("Insert Assistant Tag at Cursor", self)
        insert_assistant_action.triggered.connect(lambda: self.insert_role_tag_at_cursor(FLAT_PREFIX_ASSISTANT))
        menu.addAction(insert_assistant_action)

        # Add separator before "at end" options
        menu.addSeparator()

        insert_system_end_action = QAction("Insert System Tag at End", self)
        insert_system_end_action.triggered.connect(lambda: self.insert_role_tag_at_end(FLAT_PREFIX_SYSTEM))
        menu.addAction(insert_system_end_action)

        insert_user_end_action = QAction("Insert User Tag at End", self)
        insert_user_end_action.triggered.connect(lambda: self.insert_role_tag_at_end(FLAT_PREFIX_USER))
        menu.addAction(insert_user_end_action)

        insert_assistant_end_action = QAction("Insert Assistant Tag at End", self)
        insert_assistant_end_action.triggered.connect(lambda: self.insert_role_tag_at_end(FLAT_PREFIX_ASSISTANT))
        menu.addAction(insert_assistant_end_action)

        # Show the menu at the event position
        menu.exec(event.globalPos())

    def insert_role_tag_at_cursor(self, tag: str) -> None:
        """
        Insert a role tag at the current cursor position.
        
        Args:
            tag: The role tag to insert (FLAT_PREFIX_SYSTEM, FLAT_PREFIX_USER, or FLAT_PREFIX_ASSISTANT)
        """
        cursor = self.textCursor()
        cursor.insertText(tag)
        self.log.debug("Inserted role tag %s at cursor position", tag)

    def insert_role_tag_at_end(self, tag: str) -> None:
        """
        Insert a role tag at the end of the text on a new line.
        
        Args:
            tag: The role tag to insert (FLAT_PREFIX_SYSTEM, FLAT_PREFIX_USER, or FLAT_PREFIX_ASSISTANT)
        """
        # Move cursor to end of document
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        # Add newline if text doesn't end with one
        text = self.toPlainText()
        if text and not text.endswith('\n'):
            cursor.insertText('\n')

        # Insert the tag
        cursor.insertText(tag)

        self.log.debug("Inserted role tag %s at end of text", tag)
