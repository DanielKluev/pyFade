"""
Modal dialog for selecting tags to associate with a sample.

This module provides a dialog that allows users to add and remove tags from a sample.
Tags are displayed with checkboxes, and users can check/uncheck tags to add or remove them.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.sample import Sample
    from py_fade.dataset.tag import Tag


class SampleTagsDialog(QDialog):
    """
    Modal dialog for managing tags on a sample.

    Displays all available tags with checkboxes, allowing users to add or remove
    tags from a sample. Only tags with scope 'samples' or 'both' are shown.
    Changes are committed when the user clicks OK.
    """

    def __init__(self, dataset: "DatasetDatabase", sample: "Sample", *, parent: QWidget | None = None) -> None:
        """
        Initialize the sample tags dialog.

        Args:
            dataset: Dataset database instance
            sample: Sample to manage tags for
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.dataset = dataset
        self.sample = sample
        self.tag_checkboxes: dict[int, QCheckBox] = {}  # tag_id -> QCheckBox
        self.initial_tag_ids: set[int] = set()  # Tag IDs initially associated with sample

        self.setWindowTitle(f"Edit Tags for Sample: {sample.title}")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        self.setup_ui()
        self.load_tags()

    def setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header_label = QLabel("<h3>Select Tags for Sample</h3>")
        layout.addWidget(header_label)

        # Sample info
        sample_info = QLabel(f"<b>Sample:</b> {self.sample.title}")
        sample_info.setWordWrap(True)
        layout.addWidget(sample_info)

        # Instructions
        instructions = QLabel("Check tags to add to this sample, uncheck to remove:")
        layout.addWidget(instructions)

        # Scrollable tag list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.tags_container = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(10, 10, 10, 10)
        self.tags_layout.setSpacing(8)

        scroll_area.setWidget(self.tags_container)
        layout.addWidget(scroll_area)

        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def load_tags(self) -> None:
        """
        Load all available tags and display them with checkboxes.

        Only tags with scope 'samples' or 'both' are shown.
        Tags currently associated with the sample are checked.
        """
        from py_fade.dataset.tag import Tag  # pylint: disable=import-outside-toplevel

        # Get all tags with appropriate scope
        all_tags = Tag.get_all(self.dataset, order_by_date=False)
        sample_tags = self.sample.get_tags(self.dataset)
        sample_tag_ids = {tag.id for tag in sample_tags}
        self.initial_tag_ids = sample_tag_ids.copy()

        # Filter tags by scope (only 'samples' or 'both')
        relevant_tags = [tag for tag in all_tags if tag.scope in ("samples", "both")]

        if not relevant_tags:
            no_tags_label = QLabel("<i>No tags available. Create tags in the Tags section first.</i>")
            self.tags_layout.addWidget(no_tags_label)
            return

        # Create checkboxes for each tag
        for tag in relevant_tags:
            tag_group = QGroupBox()
            tag_group_layout = QVBoxLayout(tag_group)

            checkbox = QCheckBox(tag.name)
            checkbox.setChecked(tag.id in sample_tag_ids)
            self.tag_checkboxes[tag.id] = checkbox

            description_label = QLabel(f"<i>{tag.description}</i>")
            description_label.setWordWrap(True)
            description_label.setStyleSheet("color: #666; font-size: 11px;")

            tag_group_layout.addWidget(checkbox)
            tag_group_layout.addWidget(description_label)

            self.tags_layout.addWidget(tag_group)

        # Add stretch to push tags to the top
        self.tags_layout.addStretch()

    def accept(self) -> None:
        """
        Apply tag changes and close the dialog.

        Adds and removes tags based on checkbox states, commits changes,
        and updates tag sample counts.
        """
        from py_fade.dataset.tag import Tag  # pylint: disable=import-outside-toplevel

        try:
            # Determine which tags to add and remove
            current_tag_ids = {tag_id for tag_id, checkbox in self.tag_checkboxes.items() if checkbox.isChecked()}
            tags_to_add = current_tag_ids - self.initial_tag_ids
            tags_to_remove = self.initial_tag_ids - current_tag_ids

            # Add tags
            for tag_id in tags_to_add:
                tag = Tag.get_by_id(self.dataset, tag_id)
                if tag:
                    self.sample.add_tag(self.dataset, tag)
                    self.log.debug("Added tag '%s' to sample %s", tag.name, self.sample.id)

            # Remove tags
            for tag_id in tags_to_remove:
                tag = Tag.get_by_id(self.dataset, tag_id)
                if tag:
                    self.sample.remove_tag(self.dataset, tag)
                    self.log.debug("Removed tag '%s' from sample %s", tag.name, self.sample.id)

            # Commit changes
            self.dataset.session.commit()  # type: ignore[union-attr]

            # Update tag sample counts
            all_modified_tag_ids = tags_to_add | tags_to_remove
            for tag_id in all_modified_tag_ids:
                tag = Tag.get_by_id(self.dataset, tag_id)
                if tag:
                    tag.update_sample_count(self.dataset)

            self.dataset.session.commit()  # type: ignore[union-attr]

            self.log.info("Successfully updated tags for sample %s: added %d, removed %d", self.sample.id, len(tags_to_add),
                          len(tags_to_remove))

            super().accept()

        except (SQLAlchemyError, ValueError) as exc:
            self.log.exception("Failed to update sample tags", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to update tags: {exc}")
