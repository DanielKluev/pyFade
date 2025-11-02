"""
Detached window for editing sample notes.

This module provides a non-modal window for editing sample notes with expanded space.
The window synchronizes its content with the main widget's notes field.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.sample import Sample


class DetachedNotesWindow(QDialog):
    """
    Non-modal window for editing sample notes in expanded view.

    Provides a maximizable window with a full-size text editor for notes.
    Includes a save button to persist changes to the database.
    Content synchronizes with the main widget's notes field.
    """

    notes_saved = pyqtSignal(str)  # Signal emitted when notes are saved with new content

    def __init__(self, dataset: "DatasetDatabase", sample: "Sample | None", initial_notes: str = "", parent: QWidget | None = None) -> None:
        """
        Initialize the detached notes window.

        Args:
            dataset: Dataset database instance
            sample: Sample to edit notes for (can be None for new samples)
            initial_notes: Initial notes content to display
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.dataset = dataset
        self.sample = sample

        # Window configuration
        self.setWindowTitle("Sample Notes - Detached Editor")
        self.setMinimumSize(800, 600)
        self.setModal(False)  # Non-modal so user can switch between completions and notes

        # Track if notes have been modified
        self._notes_modified = False

        self.setup_ui()
        self.set_notes(initial_notes)

    def setup_ui(self) -> None:
        """
        Setup the UI components.

        Creates a full-window text editor with a save button at the bottom.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Notes text editor - fills entire space
        self.notes_editor = QPlainTextEdit(self)
        self.notes_editor.setPlaceholderText("Add detailed notes, completion drafts, or other information for this sample...\n\n"
                                             "Notes are for annotators only and are not visible to models.")
        self.notes_editor.textChanged.connect(self._on_notes_changed)
        layout.addWidget(self.notes_editor)

        # Button row at bottom
        button_row_layout = QHBoxLayout()
        button_row_layout.setSpacing(8)

        # Save button
        self.save_button = QPushButtonWithIcon("save", "Save Notes", parent=self, icon_size=20)
        self.save_button.setToolTip("Save notes to database")
        self.save_button.clicked.connect(self.save_notes)
        self.save_button.setEnabled(False)  # Disabled until notes are modified
        button_row_layout.addWidget(self.save_button)

        # Stretch to push buttons to the left
        button_row_layout.addStretch()

        layout.addLayout(button_row_layout)

    def set_notes(self, notes: str) -> None:
        """
        Set the notes content in the editor.

        Args:
            notes: Notes text to display
        """
        self.notes_editor.setPlainText(notes)
        self._notes_modified = False
        self.save_button.setEnabled(False)
        self.log.debug("Notes set to %d characters", len(notes))

    def get_notes(self) -> str:
        """
        Get the current notes content from the editor.

        Returns:
            Current notes text
        """
        return self.notes_editor.toPlainText()

    def _on_notes_changed(self) -> None:
        """
        Handle notes text change event.

        Marks notes as modified and enables save button.
        """
        self._notes_modified = True
        self.save_button.setEnabled(True)

    def save_notes(self) -> None:
        """
        Save the current notes to the database and emit signal.

        Persists notes to the sample in the database (if sample exists)
        and emits notes_saved signal with the new content.
        """
        notes_text = self.notes_editor.toPlainText().strip()

        # Save to database if sample exists
        if self.sample and self.sample.id:
            # Update sample notes
            self.sample.notes = notes_text or None
            if self.dataset.session:
                self.dataset.session.commit()
            self.log.info("Saved notes for sample %s (%d characters)", self.sample.id, len(notes_text))
        else:
            self.log.debug("Sample not saved yet, skipping database persist")

        # Emit signal with new content
        self.notes_saved.emit(notes_text)

        # Reset modified flag and disable save button
        self._notes_modified = False
        self.save_button.setEnabled(False)

    def closeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """
        Handle window close event.

        Emits notes_saved signal if notes were modified, ensuring synchronization.

        Args:
            event: QCloseEvent
        """
        if self._notes_modified:
            # Emit signal to synchronize with main widget even if not saved to DB
            self.notes_saved.emit(self.get_notes())
            self.log.debug("Closing window with unsaved modifications, emitting signal for synchronization")

        super().closeEvent(event)
