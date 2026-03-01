"""
Modal dialog for selecting tags to associate with a sample or completion.

This module provides a dialog that allows users to add and remove tags from a sample
or completion. Tags are displayed with checkboxes, and users can check/uncheck tags
to add or remove them. The dialog filters available tags by scope appropriate to the
target type.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Union

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.sample import Sample
    from py_fade.dataset.tag import Tag


class SampleTagsDialog(QDialog):
    """
    Modal dialog for managing tags on a sample or completion.

    Displays all available tags with checkboxes, allowing users to add or remove
    tags from a sample or completion. Tags are filtered by scope:
    - For samples: only tags with scope 'samples' or 'both' are shown.
    - For completions: only tags with scope 'completions' or 'both' are shown.
    Changes are committed when the user clicks OK.
    """

    def __init__(self, dataset: "DatasetDatabase", target: "Union[Sample, PromptCompletion]", *, parent: QWidget | None = None) -> None:
        """
        Initialize the tags dialog.

        Args:
            dataset: Dataset database instance
            target: Sample or PromptCompletion to manage tags for
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.dataset = dataset
        self.target = target
        # Keep 'sample' attribute for backward compatibility with existing code that accesses dialog.sample
        self.sample = target
        self.tag_checkboxes: dict[int, QCheckBox] = {}  # tag_id -> QCheckBox
        self.initial_tag_ids: set[int] = set()  # Tag IDs initially associated with target

        # Detect target type to configure dialog appropriately
        from py_fade.dataset.completion import PromptCompletion  # pylint: disable=import-outside-toplevel
        self._is_completion = isinstance(target, PromptCompletion)

        if self._is_completion:
            self.setWindowTitle(f"Edit Tags for Completion #{getattr(target, 'id', '?')}")
        else:
            self.setWindowTitle(f"Edit Tags for Sample: {getattr(target, 'title', str(target))}")

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
        if self._is_completion:
            header_label = QLabel("<h3>Select Tags for Completion</h3>")
        else:
            header_label = QLabel("<h3>Select Tags for Sample</h3>")
        layout.addWidget(header_label)

        # Target info
        if self._is_completion:
            target_info = QLabel(f"<b>Completion:</b> #{getattr(self.target, 'id', '?')}")
        else:
            target_info = QLabel(f"<b>Sample:</b> {getattr(self.target, 'title', str(self.target))}")
        target_info.setWordWrap(True)
        layout.addWidget(target_info)

        # Instructions
        target_word = "completion" if self._is_completion else "sample"
        instructions = QLabel(f"Check tags to add to this {target_word}, uncheck to remove:")
        layout.addWidget(instructions)

        # Scrollable tag list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.tags_container = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(10, 10, 10, 10)
        self.tags_layout.setSpacing(2)

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

        For samples: only tags with scope 'samples' or 'both' are shown.
        For completions: only tags with scope 'completions' or 'both' are shown.
        Tags currently associated with the target are checked.
        Tags are sorted alphabetically by name.
        """
        from py_fade.dataset.tag import Tag  # pylint: disable=import-outside-toplevel

        # Get all tags with appropriate scope
        all_tags = Tag.get_all(self.dataset, order_by_date=False)
        current_tags = self.target.get_tags(self.dataset)
        current_tag_ids = {tag.id for tag in current_tags}
        self.initial_tag_ids = current_tag_ids.copy()

        # Filter tags by scope based on target type
        if self._is_completion:
            relevant_tags = [tag for tag in all_tags if tag.scope in ("completions", "both")]
        else:
            relevant_tags = [tag for tag in all_tags if tag.scope in ("samples", "both")]

        if not relevant_tags:
            no_tags_label = QLabel("<i>No tags available. Create tags in the Tags section first.</i>")
            self.tags_layout.addWidget(no_tags_label)
            return

        # Sort tags alphabetically by name
        relevant_tags.sort(key=lambda t: t.name.lower())

        # Create checkboxes for each tag with compact layout
        for tag in relevant_tags:
            # Create checkbox with tag name
            checkbox = QCheckBox(tag.name)
            checkbox.setChecked(tag.id in current_tag_ids)
            self.tag_checkboxes[tag.id] = checkbox

            # Create description label with compact styling
            description_label = QLabel(f"<i>{tag.description}</i>")
            description_label.setWordWrap(True)
            description_label.setStyleSheet("color: #666; font-size: 10px; margin-left: 20px; margin-bottom: 4px;")
            description_label.setIndent(0)

            # Add widgets directly to layout for compact appearance
            self.tags_layout.addWidget(checkbox)
            self.tags_layout.addWidget(description_label)

        # Add stretch to push tags to the top
        self.tags_layout.addStretch()

    def accept(self) -> None:
        """
        Apply tag changes and close the dialog.

        Adds and removes tags based on checkbox states, commits changes,
        and (for samples) updates tag sample counts.
        """
        from py_fade.dataset.tag import Tag  # pylint: disable=import-outside-toplevel

        try:
            # Determine which tags to add and remove
            checked_tag_ids = {tag_id for tag_id, checkbox in self.tag_checkboxes.items() if checkbox.isChecked()}
            tags_to_add = checked_tag_ids - self.initial_tag_ids
            tags_to_remove = self.initial_tag_ids - checked_tag_ids

            # Add tags
            for tag_id in tags_to_add:
                tag = Tag.get_by_id(self.dataset, tag_id)
                if tag:
                    self.target.add_tag(self.dataset, tag)
                    self.log.debug("Added tag '%s' to target %s", tag.name, getattr(self.target, 'id', '?'))

            # Remove tags
            for tag_id in tags_to_remove:
                tag = Tag.get_by_id(self.dataset, tag_id)
                if tag:
                    self.target.remove_tag(self.dataset, tag)
                    self.log.debug("Removed tag '%s' from target %s", tag.name, getattr(self.target, 'id', '?'))

            # Commit changes
            self.dataset.session.commit()  # type: ignore[union-attr]

            # Update tag sample counts (only for sample targets)
            if not self._is_completion:
                all_modified_tag_ids = tags_to_add | tags_to_remove
                for tag_id in all_modified_tag_ids:
                    tag = Tag.get_by_id(self.dataset, tag_id)
                    if tag:
                        tag.update_sample_count(self.dataset)

                self.dataset.session.commit()  # type: ignore[union-attr]

            target_id = getattr(self.target, 'id', '?')
            self.log.info("Successfully updated tags for target %s: added %d, removed %d", target_id, len(tags_to_add), len(tags_to_remove))

            super().accept()

        except (SQLAlchemyError, ValueError) as exc:
            self.log.exception("Failed to update tags", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to update tags: {exc}")
