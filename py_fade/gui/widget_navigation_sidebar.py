"""
Widget navigation sidebar for the application.
"""

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QLineEdit,
    QLabel,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.tag import Tag
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_toggle_button import QPushButtonToggle
from py_fade.gui.gui_helpers import get_dataset_preferences, update_dataset_preferences
from py_fade.search_utils import parse_search_value_as_int

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


class WidgetNavigationFilterPanel(QWidget):
    """
    Filter panel for navigation sidebar.

    Lets switch between samples by groups, samples by facets, samples by tags, individual prompts, individual completions.
    Additionally lets filter by text search and toggle flat list view for tag/facet groupings.
    """

    filter_changed = pyqtSignal()  # Signal emitted when filter criteria change

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.flat_list_toggle = None  # Will be initialized in setup_ui
        self.group_by_rating_toggle = None  # Will be initialized in setup_ui
        self.filter_selector = None  # Will be initialized in setup_ui
        self.setup_ui()

    def setup_ui(self):
        """Setup the filter panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Show selector
        show_label = QLabel("Show:")
        self.show_combo = QComboBox()
        self.show_combo.addItems([
            "Samples by Group",
            "Samples by Facet",
            "Samples by Tag",
            "Samples by Filter",
            "Sample Filters",
            "Facets",
            "Tags",
            "Prompts",
            "Export Templates",
        ])
        self.show_combo.currentTextChanged.connect(self._on_show_changed)

        # Filter selector (shown only for "Samples by Filter")
        filter_selector_label = QLabel("Filter:")
        self.filter_selector = QComboBox()
        self.filter_selector.setVisible(False)
        self.filter_selector.currentIndexChanged.connect(self.filter_changed.emit)
        filter_selector_label.setVisible(False)
        self.filter_selector_label = filter_selector_label

        # Flat list toggle button (shown only for tag/facet/filter groupings)
        self.flat_list_toggle = QPushButtonToggle("view_list", "Toggle flat list view (no group hierarchy)", button_size=28)
        self.flat_list_toggle.toggled_state_changed.connect(self._on_flat_list_toggled)
        self.flat_list_toggle.setVisible(False)  # Hidden by default

        # Group by rating toggle button (shown only for facet grouping)
        self.group_by_rating_toggle = QPushButtonToggle("star", "Toggle sub-grouping by highest rating", button_size=28)
        self.group_by_rating_toggle.toggled_state_changed.connect(self._on_group_by_rating_toggled)
        self.group_by_rating_toggle.setVisible(False)  # Hidden by default

        # Text search
        search_label = QLabel("Search:")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search text...")
        self.search_input.textChanged.connect(self.filter_changed.emit)

        # Add widgets to layout
        layout.addWidget(show_label)
        layout.addWidget(self.show_combo)
        layout.addWidget(filter_selector_label)
        layout.addWidget(self.filter_selector)
        layout.addWidget(self.flat_list_toggle)
        layout.addWidget(self.group_by_rating_toggle)
        layout.addWidget(search_label)
        layout.addWidget(self.search_input)
        # Do not add a stretch here so the panel only takes the space it needs.
        # Ensure the panel does not expand vertically.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    def _on_show_changed(self):
        """Handle show combo box changes to update flat list toggle and filter selector visibility."""
        show = self.show_combo.currentText()

        # Show flat list toggle for "Samples by Tag", "Samples by Facet", and "Samples by Filter"
        if show in ("Samples by Tag", "Samples by Facet", "Samples by Filter"):
            self.flat_list_toggle.setVisible(True)
        else:
            self.flat_list_toggle.setVisible(False)

        # Show group by rating toggle only for "Samples by Facet"
        if show == "Samples by Facet":
            self.group_by_rating_toggle.setVisible(True)
        else:
            self.group_by_rating_toggle.setVisible(False)

        # Show filter selector only for "Samples by Filter"
        if show == "Samples by Filter":
            self.filter_selector.setVisible(True)
            self.filter_selector_label.setVisible(True)
        else:
            self.filter_selector.setVisible(False)
            self.filter_selector_label.setVisible(False)

        self.filter_changed.emit()

    def _on_flat_list_toggled(self, toggled: bool):
        """Handle flat list toggle changes."""
        # If flat list is enabled, disable group by rating
        if toggled and self.group_by_rating_toggle.is_toggled():
            self.group_by_rating_toggle.set_toggled(False)
        self.filter_changed.emit()

    def _on_group_by_rating_toggled(self, toggled: bool):
        """Handle group by rating toggle changes."""
        # If group by rating is enabled, disable flat list
        if toggled and self.flat_list_toggle.is_toggled():
            self.flat_list_toggle.set_toggled(False)
        self.filter_changed.emit()

    def _build_data_filter(self) -> DataFilter:
        """Build a DataFilter based on current filter criteria."""
        filters = []
        if self.search_input.text().strip():
            search_text = self.search_input.text().strip().lower()
            filters.append({"type": "text_search", "value": search_text})
        return DataFilter(filters)

    def get_filter_criteria(self) -> dict:
        """Get current filter criteria as a dictionary."""
        show = self.show_combo.currentText()
        return {
            "show": show,
            "data_filter": self._build_data_filter(),
            "flat_list_mode": self.flat_list_toggle.is_toggled() if self.flat_list_toggle else False,
            "group_by_rating_mode": self.group_by_rating_toggle.is_toggled() if self.group_by_rating_toggle else False,
            "selected_filter_id": self.filter_selector.currentData() if self.filter_selector and show == "Samples by Filter" else None,
        }

    def update_filter_list(self, dataset: "DatasetDatabase"):
        """
        Update the filter selector with available sample filters from the dataset.

        Args:
            dataset: The dataset database instance
        """
        from py_fade.dataset.sample_filter import SampleFilter  # pylint: disable=import-outside-toplevel

        self.filter_selector.clear()
        filters = SampleFilter.get_all(dataset, order_by_date=True)

        if not filters:
            self.filter_selector.addItem("(No filters defined)", None)
            return

        for sample_filter in filters:
            self.filter_selector.addItem(sample_filter.name, sample_filter.id)


class WidgetNavigationTree(QWidget):
    """
    Tree view for navigation sidebar.
    Shows the hierarchy of selected items (e.g. samples, prompts, completions) according to selected grouping and filtering.
    Also has "New <X>" button to create new samples, facets, tags, prompts, completions, export templates.
    """

    item_selected = pyqtSignal(str, int)  # Signal emitted when item is selected (item_type, item_id)
    new_item_requested = pyqtSignal(str)  # Signal emitted when new item of type is requested (item_type)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setup_ui()
        self.current_data = []
        self.current_item_type = None  # e.g. "sample", "facet", "tag", "prompt", "completion"

    def setup_ui(self):
        """Setup the tree view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.new_element_button = QPushButtonWithIcon("add", "New")
        self.new_element_button.setToolTip("Create new element of the selected type")
        self.new_element_button.setVisible(False)  # Hidden by default, shown when applicable
        self.new_element_button.clicked.connect(lambda: self.new_item_requested.emit(self.current_item_type))

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        # Let the tree expand to take available vertical space.
        self.tree.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        layout.addWidget(self.new_element_button)
        layout.addWidget(self.tree)

    def _on_item_clicked(self, item, _column):
        """Handle tree item click."""
        item_type = item.data(0, Qt.ItemDataRole.UserRole)
        item_id = item.data(1, Qt.ItemDataRole.UserRole)
        if item_type and item_id:
            self.item_selected.emit(item_type, item_id)

    def update_content(self, filter_criteria: dict, dataset: "DatasetDatabase"):
        """Update tree content based on filter criteria."""
        self.tree.clear()

        if not dataset:
            return

        show = filter_criteria.get("show", "Samples by Group")
        data_filter: DataFilter = filter_criteria.get("data_filter")  # type: ignore
        flat_list_mode = filter_criteria.get("flat_list_mode", False)
        group_by_rating_mode = filter_criteria.get("group_by_rating_mode", False)
        selected_filter_id = filter_criteria.get("selected_filter_id")

        self.current_item_type = None
        if show == "Samples by Group":
            self.current_item_type = "Sample"
            self._populate_samples(data_filter, dataset)
        elif show == "Samples by Facet":
            self.current_item_type = "Sample"
            self._populate_samples_by_facet(data_filter, dataset, flat_list_mode, group_by_rating_mode)
        elif show == "Samples by Tag":
            self.current_item_type = "Sample"
            self._populate_samples_by_tag(data_filter, dataset, flat_list_mode)
        elif show == "Samples by Filter":
            self.current_item_type = "Sample"
            self._populate_samples_by_filter(selected_filter_id, dataset, flat_list_mode)
        elif show == "Sample Filters":
            self.current_item_type = "Sample Filter"
            self._populate_sample_filters(data_filter, dataset)
        elif show == "Facets":
            self.current_item_type = "Facet"
            self._populate_facets(data_filter, dataset)
        elif show == "Tags":
            self.current_item_type = "Tag"
            self._populate_tags(data_filter, dataset)
        elif show == "Prompts":
            self.current_item_type = None  # Prompts created elsewhere
            self._populate_prompts(data_filter, dataset)
        elif show == "Export Templates":
            self.current_item_type = "export_template"
            self._populate_export_templates(data_filter, dataset)

        if self.current_item_type is None:
            self.new_element_button.setVisible(False)  # New elements of this type created elsewhere
        else:
            self.new_element_button.setVisible(True)
            pretty_label = self.current_item_type.replace("_", " ").title()
            self.new_element_button.setText(f"New {pretty_label}")
            self.new_element_button.setToolTip(f"Create new {pretty_label} element")

    def _set_sample_icon_if_has_images(self, item: QTreeWidgetItem, sample: Sample) -> None:
        """
        Set an image icon on the tree item if the sample has attached images.

        Args:
            item: The QTreeWidgetItem to update
            sample: The Sample to check for images
        """
        if sample.has_images():
            item.setIcon(0, google_icon_font.as_icon("image", size=16))

    def _populate_samples(self, data_filter: DataFilter, dataset: "DatasetDatabase"):
        """
        Populate tree with samples.
        """
        samples = Sample.fetch_with_filter(dataset, data_filter)
        # Populate tree with samples, respecting `group_path` if available.
        # Each node of `group_path` (split by '/') is a tree item, samples are nodes of the last group component.
        # For samples without group_path, put them under "Ungrouped" root.

        group_roots = {}
        for sample in samples:
            group_path = sample.group_path or "Ungrouped"
            group_parts = group_path.split("/")
            current_parent = self.tree
            current_path = ""
            for part in group_parts:
                current_path = f"{current_path}/{part}" if current_path else part
                if current_path not in group_roots:
                    group_roots[current_path] = QTreeWidgetItem(current_parent, [part])
                current_parent = group_roots[current_path]

            item = QTreeWidgetItem(current_parent, [sample.title])
            item.setData(0, Qt.ItemDataRole.UserRole, "sample")
            item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
            self._set_sample_icon_if_has_images(item, sample)

        # Sort all children at each level (both samples and subgroups) alphabetically
        self._sort_tree_children_recursively(self.tree)

    def _sort_tree_children_recursively(self, parent_item):
        """
        Recursively sort children of a tree item alphabetically (case-insensitive).

        This sorts both sample items and subgroup items together at each level.

        Args:
            parent_item: The parent QTreeWidget or QTreeWidgetItem whose children should be sorted
        """
        # Get child count
        if isinstance(parent_item, QTreeWidget):
            child_count = parent_item.topLevelItemCount()
        else:
            child_count = parent_item.childCount()

        if child_count == 0:
            return

        # Collect all children with their text (for sorting)
        children_with_text = []
        for i in range(child_count):
            if isinstance(parent_item, QTreeWidget):
                child = parent_item.topLevelItem(i)
            else:
                child = parent_item.child(i)
            children_with_text.append((child.text(0).lower(), child))

        # Sort by text (case-insensitive)
        children_with_text.sort(key=lambda x: x[0])

        # Remove all children from parent in reverse order to avoid array shifting overhead
        if isinstance(parent_item, QTreeWidget):
            for i in range(child_count - 1, -1, -1):
                parent_item.takeTopLevelItem(i)
        else:
            for i in range(child_count - 1, -1, -1):
                parent_item.takeChild(i)

        # Add children back in sorted order
        for _, child in children_with_text:
            if isinstance(parent_item, QTreeWidget):
                parent_item.addTopLevelItem(child)
            else:
                parent_item.addChild(child)
            # Recursively sort this child's children
            self._sort_tree_children_recursively(child)

    def _populate_samples_by_facet(self, data_filter: DataFilter, dataset: "DatasetDatabase", flat_list_mode: bool = False,
                                   group_by_rating_mode: bool = False):
        """
        Populate tree with samples grouped by facet.

        Root nodes are facets and "No Facet" node.
        Under each facet, samples can be grouped by rating (if group_by_rating_mode is True),
        or by their group_path (unless flat_list_mode is True).
        Samples without any facet ratings go under "No Facet" node.

        Args:
            data_filter: Filter to apply to samples
            dataset: Dataset database
            flat_list_mode: If True, samples are listed directly under facet without group_path hierarchy
            group_by_rating_mode: If True, samples are sub-grouped by highest rating (descending from 10 to 0.5)
        """

        # Get all facets
        session = dataset.get_session()
        facets = session.query(Facet).all()

        # Extract search value if present
        search_value: str | None = None
        for criteria in getattr(data_filter, "filters", []):
            if criteria.get("type") == "text_search":
                probe = str(criteria.get("value", "")).strip().lower()
                if probe:
                    search_value = probe
                    break

        # Create facet nodes and populate with samples
        for facet in facets:
            samples = facet.get_samples(dataset)

            # Apply search filter to samples if present
            if search_value:
                # Check if search value is a valid integer for ID filtering
                search_id, is_valid_id = parse_search_value_as_int(search_value)

                # Check if facet name or description matches
                facet_matches = search_value in facet.name.lower() or search_value in facet.description.lower()

                # Filter samples by search term (title, group_path, prompt_text, or ID)
                filtered_samples = [
                    sample for sample in samples
                    if search_value in sample.title.lower() or (sample.group_path and search_value in sample.group_path.lower()) or
                    (sample.prompt_revision and search_value in sample.prompt_revision.prompt_text.lower()) or
                    (is_valid_id and sample.id == search_id)
                ]

                # If facet name doesn't match, show only filtered samples
                if not facet_matches:
                    # Facet name doesn't match, show only matching samples
                    samples = filtered_samples

            if not samples:
                continue  # Skip facets with no matching samples

            # Create facet root node
            facet_item = QTreeWidgetItem(self.tree, [facet.name])
            facet_item.setExpanded(False)  # Collapse by default

            if group_by_rating_mode:
                # Rating sub-grouping mode: Group samples by highest rating (descending from 10 to 0.5)
                # First, organize samples by rating
                samples_by_rating = {}
                for sample in samples:
                    rating = sample.get_highest_rating_for_facet(facet)
                    if rating is not None:
                        if rating not in samples_by_rating:
                            samples_by_rating[rating] = []
                        samples_by_rating[rating].append(sample)

                # Create rating nodes in descending order (10, 9.5, 9, ..., 0.5)
                # Ratings are stored as integers 0-10, representing 0 to 10 in 0.5 increments
                for rating_value in sorted(samples_by_rating.keys(), reverse=True):
                    rating_label = f"Rating: {rating_value}"
                    rating_item = QTreeWidgetItem(facet_item, [rating_label])
                    rating_item.setExpanded(False)

                    # Sort samples by title within each rating group
                    sorted_samples = sorted(samples_by_rating[rating_value], key=lambda s: s.title.lower())
                    for sample in sorted_samples:
                        sample_item = QTreeWidgetItem(rating_item, [sample.title])
                        sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                        sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                        self._set_sample_icon_if_has_images(sample_item, sample)

            elif flat_list_mode:
                # Flat mode: Add samples directly under facet without group hierarchy
                # Sort samples by title
                sorted_samples = sorted(samples, key=lambda s: s.title.lower())
                for sample in sorted_samples:
                    sample_item = QTreeWidgetItem(facet_item, [sample.title])
                    sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                    sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                    self._set_sample_icon_if_has_images(sample_item, sample)
            else:
                # Hierarchical mode: Group samples by group_path under this facet
                # Sort samples by title for consistent ordering
                sorted_samples = sorted(samples, key=lambda s: s.title.lower())
                group_roots = {}
                for sample in sorted_samples:
                    group_path = sample.group_path or "Ungrouped"
                    group_parts = group_path.split("/")
                    current_parent = facet_item
                    current_path = ""
                    for part in group_parts:
                        current_path = f"{current_path}/{part}" if current_path else part
                        # Use facet_id prefix to ensure unique keys per facet
                        group_key = f"{facet.id}:{current_path}"
                        if group_key not in group_roots:
                            group_roots[group_key] = QTreeWidgetItem(current_parent, [part])
                        current_parent = group_roots[group_key]

                    # Add sample under the group
                    sample_item = QTreeWidgetItem(current_parent, [sample.title])
                    sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                    sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                    self._set_sample_icon_if_has_images(sample_item, sample)

        # Add "No Facet" node for samples without any ratings
        samples_without_facet = Facet.get_samples_without_facet(dataset)

        # Apply search filter to samples without facet
        if search_value:
            # Check if search value is a valid integer for ID filtering
            search_id, is_valid_id = parse_search_value_as_int(search_value)

            samples_without_facet = [
                sample for sample in samples_without_facet
                if search_value in sample.title.lower() or (sample.group_path and search_value in sample.group_path.lower()) or
                (sample.prompt_revision and search_value in sample.prompt_revision.prompt_text.lower()) or
                (is_valid_id and sample.id == search_id)
            ]

        if samples_without_facet:
            no_facet_item = QTreeWidgetItem(self.tree, ["No Facet"])
            no_facet_item.setExpanded(False)  # Collapse by default

            if flat_list_mode or group_by_rating_mode:
                # Flat mode or rating mode: Add samples directly under "No Facet" without group hierarchy
                # Sort samples by title
                sorted_samples = sorted(samples_without_facet, key=lambda s: s.title.lower())
                for sample in sorted_samples:
                    sample_item = QTreeWidgetItem(no_facet_item, [sample.title])
                    sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                    sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                    self._set_sample_icon_if_has_images(sample_item, sample)
            else:
                # Hierarchical mode: Group samples by group_path under "No Facet"
                # Sort samples by title for consistent ordering
                sorted_samples = sorted(samples_without_facet, key=lambda s: s.title.lower())
                group_roots = {}
                for sample in sorted_samples:
                    group_path = sample.group_path or "Ungrouped"
                    group_parts = group_path.split("/")
                    current_parent = no_facet_item
                    current_path = ""
                    for part in group_parts:
                        current_path = f"{current_path}/{part}" if current_path else part
                        # Use "no_facet" prefix for unique keys
                        group_key = f"no_facet:{current_path}"
                        if group_key not in group_roots:
                            group_roots[group_key] = QTreeWidgetItem(current_parent, [part])
                        current_parent = group_roots[group_key]

                    # Add sample under the group
                    sample_item = QTreeWidgetItem(current_parent, [sample.title])
                    sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                    sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                    self._set_sample_icon_if_has_images(sample_item, sample)

    def _populate_samples_by_tag(self, data_filter: DataFilter, dataset: "DatasetDatabase", flat_list_mode: bool = False):
        """
        Populate tree with samples grouped by tag.

        Root nodes are tags and "No Tag" node.
        Under each tag, samples are grouped by their group_path (unless flat_list_mode is True).
        Samples without any tags go under "No Tag" node.

        Args:
            data_filter: Filter to apply to samples
            dataset: Dataset database
            flat_list_mode: If True, samples are listed directly under tag without group_path hierarchy
        """

        # Get all tags
        session = dataset.get_session()
        tags = session.query(Tag).all()

        # Extract search value if present
        search_value: str | None = None
        for criteria in getattr(data_filter, "filters", []):
            if criteria.get("type") == "text_search":
                probe = str(criteria.get("value", "")).strip().lower()
                if probe:
                    search_value = probe
                    break

        # Create tag nodes and populate with samples
        for tag in tags:
            samples = tag.get_samples(dataset)

            # Apply search filter to samples if present
            if search_value:
                # Check if search value is a valid integer for ID filtering
                search_id, is_valid_id = parse_search_value_as_int(search_value)

                # Check if tag name or description matches
                tag_matches = search_value in tag.name.lower() or search_value in tag.description.lower()

                # Filter samples by search term (title, group_path, prompt_text, or ID)
                filtered_samples = [
                    sample for sample in samples
                    if search_value in sample.title.lower() or (sample.group_path and search_value in sample.group_path.lower()) or
                    (sample.prompt_revision and search_value in sample.prompt_revision.prompt_text.lower()) or
                    (is_valid_id and sample.id == search_id)
                ]

                # If tag name doesn't match, show only filtered samples
                if not tag_matches:
                    # Tag name doesn't match, show only matching samples
                    samples = filtered_samples

            if not samples:
                continue  # Skip tags with no matching samples

            # Create tag root node
            tag_item = QTreeWidgetItem(self.tree, [tag.name])
            tag_item.setExpanded(False)  # Collapse by default

            if flat_list_mode:
                # Flat mode: Add samples directly under tag without group hierarchy
                for sample in samples:
                    sample_item = QTreeWidgetItem(tag_item, [sample.title])
                    sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                    sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                    self._set_sample_icon_if_has_images(sample_item, sample)
            else:
                # Hierarchical mode: Group samples by group_path under this tag
                group_roots = {}
                for sample in samples:
                    group_path = sample.group_path or "Ungrouped"
                    group_parts = group_path.split("/")
                    current_parent = tag_item
                    current_path = ""
                    for part in group_parts:
                        current_path = f"{current_path}/{part}" if current_path else part
                        # Use tag_id prefix to ensure unique keys per tag
                        group_key = f"{tag.id}:{current_path}"
                        if group_key not in group_roots:
                            group_roots[group_key] = QTreeWidgetItem(current_parent, [part])
                        current_parent = group_roots[group_key]

                    # Add sample under the group
                    sample_item = QTreeWidgetItem(current_parent, [sample.title])
                    sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                    sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                    self._set_sample_icon_if_has_images(sample_item, sample)

        # Add "No Tag" node for samples without any tags
        # Get all samples
        all_samples = Sample.fetch_with_filter(dataset, data_filter)

        # Filter to only those without tags
        samples_without_tags = [sample for sample in all_samples if not sample.get_tags(dataset)]

        # Apply search filter to samples without tags
        if search_value:
            # Check if search value is a valid integer for ID filtering
            search_id, is_valid_id = parse_search_value_as_int(search_value)

            samples_without_tags = [
                sample for sample in samples_without_tags
                if search_value in sample.title.lower() or (sample.group_path and search_value in sample.group_path.lower()) or
                (sample.prompt_revision and search_value in sample.prompt_revision.prompt_text.lower()) or
                (is_valid_id and sample.id == search_id)
            ]

        if samples_without_tags:
            no_tag_item = QTreeWidgetItem(self.tree, ["No Tag"])
            no_tag_item.setExpanded(False)  # Collapse by default

            if flat_list_mode:
                # Flat mode: Add samples directly under "No Tag" without group hierarchy
                for sample in samples_without_tags:
                    sample_item = QTreeWidgetItem(no_tag_item, [sample.title])
                    sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                    sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                    self._set_sample_icon_if_has_images(sample_item, sample)
            else:
                # Hierarchical mode: Group samples by group_path under "No Tag"
                group_roots = {}
                for sample in samples_without_tags:
                    group_path = sample.group_path or "Ungrouped"
                    group_parts = group_path.split("/")
                    current_parent = no_tag_item
                    current_path = ""
                    for part in group_parts:
                        current_path = f"{current_path}/{part}" if current_path else part
                        # Use "no_tag" prefix for unique keys
                        group_key = f"no_tag:{current_path}"
                        if group_key not in group_roots:
                            group_roots[group_key] = QTreeWidgetItem(current_parent, [part])
                        current_parent = group_roots[group_key]

                    # Add sample under the group
                    sample_item = QTreeWidgetItem(current_parent, [sample.title])
                    sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                    sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                    self._set_sample_icon_if_has_images(sample_item, sample)

    def _populate_samples_by_filter(self, filter_id: int | None, dataset: "DatasetDatabase", flat_list_mode: bool = False):
        """
        Populate tree with samples filtered by a complex sample filter.

        Args:
            filter_id: ID of the SampleFilter to apply, or None if no filter selected
            dataset: Dataset database
            flat_list_mode: If True, samples are listed directly without group_path hierarchy
        """
        from py_fade.dataset.sample_filter import SampleFilter  # pylint: disable=import-outside-toplevel

        if filter_id is None:
            # No filter selected, show placeholder
            placeholder = QTreeWidgetItem(self.tree, ["No filter selected"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        # Get the filter
        sample_filter = SampleFilter.get_by_id(dataset, filter_id)
        if not sample_filter:
            placeholder = QTreeWidgetItem(self.tree, ["Filter not found"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        # Get filter rules and apply them
        rules = sample_filter.get_rules()
        samples = Sample.fetch_with_complex_filter(dataset, rules)

        if not samples:
            placeholder = QTreeWidgetItem(self.tree, ["No samples match this filter"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        if flat_list_mode:
            # Flat mode: Add samples directly without group hierarchy
            # Sort samples by title
            sorted_samples = sorted(samples, key=lambda s: s.title.lower())
            for sample in sorted_samples:
                sample_item = QTreeWidgetItem(self.tree, [sample.title])
                sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                self._set_sample_icon_if_has_images(sample_item, sample)
        else:
            # Hierarchical mode: Group samples by group_path
            group_roots = {}
            for sample in samples:
                group_path = sample.group_path or "Ungrouped"
                group_parts = group_path.split("/")
                current_parent = self.tree
                current_path = ""
                for part in group_parts:
                    current_path = f"{current_path}/{part}" if current_path else part
                    if current_path not in group_roots:
                        group_roots[current_path] = QTreeWidgetItem(current_parent, [part])
                    current_parent = group_roots[current_path]

                # Add sample under the group
                sample_item = QTreeWidgetItem(current_parent, [sample.title])
                sample_item.setData(0, Qt.ItemDataRole.UserRole, "sample")
                sample_item.setData(1, Qt.ItemDataRole.UserRole, sample.id)
                self._set_sample_icon_if_has_images(sample_item, sample)

    def _populate_facets(self, data_filter: DataFilter, dataset: "DatasetDatabase"):
        """Populate tree with facets."""

        session = dataset.get_session()
        facets = session.query(Facet).all()

        search_value: str | None = None
        for criteria in getattr(data_filter, "filters", []):
            if criteria.get("type") == "text_search":
                probe = str(criteria.get("value", "")).strip().lower()
                if probe:
                    search_value = probe
                    break

        if search_value:
            facets = [facet for facet in facets if search_value in facet.name.lower() or search_value in facet.description.lower()]

        if not facets:
            placeholder = QTreeWidgetItem(self.tree, ["No facets available"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        for facet in facets:
            item = QTreeWidgetItem(self.tree, [facet.name])
            item.setData(0, Qt.ItemDataRole.UserRole, "facet")
            item.setData(1, Qt.ItemDataRole.UserRole, facet.id)

    def _populate_tags(self, data_filter: DataFilter, dataset: "DatasetDatabase"):
        """Populate tree with tags."""

        tags = Tag.get_all(dataset)

        search_value: str | None = None
        for criteria in getattr(data_filter, "filters", []):
            if criteria.get("type") == "text_search":
                value = str(criteria.get("value", "")).strip().lower()
                if value:
                    search_value = value
                    break

        if search_value:
            tags = [tag for tag in tags if search_value in tag.name.lower() or search_value in tag.description.lower()]

        if not tags:
            placeholder = QTreeWidgetItem(self.tree, ["No tags available"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        for tag in tags:
            display_text = f"{tag.name} ({tag.total_samples})" if tag.total_samples else tag.name
            item = QTreeWidgetItem(self.tree, [display_text])
            item.setData(0, Qt.ItemDataRole.UserRole, "tag")
            item.setData(1, Qt.ItemDataRole.UserRole, tag.id)
            item.setToolTip(0, tag.description)

    def _populate_sample_filters(self, data_filter: DataFilter, dataset: "DatasetDatabase"):
        """
        Populate tree with sample filters.
        """
        from py_fade.dataset.sample_filter import SampleFilter  # pylint: disable=import-outside-toplevel

        sample_filters = SampleFilter.get_all(dataset, order_by_date=True)

        search_value: str | None = None
        for criteria in getattr(data_filter, "filters", []):
            if criteria.get("type") == "text_search":
                value = str(criteria.get("value", "")).strip().lower()
                if value:
                    search_value = value
                    break

        if search_value:
            sample_filters = [f for f in sample_filters if search_value in f.name.lower() or search_value in f.description.lower()]

        if not sample_filters:
            placeholder = QTreeWidgetItem(self.tree, ["No sample filters available"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        for sample_filter in sample_filters:
            rule_count = len(sample_filter.get_rules())
            display_text = f"{sample_filter.name} ({rule_count} rules)" if rule_count else sample_filter.name
            item = QTreeWidgetItem(self.tree, [display_text])
            item.setData(0, Qt.ItemDataRole.UserRole, "sample_filter")
            item.setData(1, Qt.ItemDataRole.UserRole, sample_filter.id)
            item.setToolTip(0, sample_filter.description)

    def _populate_prompts(self, data_filter: DataFilter, dataset: "DatasetDatabase"):
        """
        Populate tree with prompts.
        """
        prompts = dataset.get_prompts(data_filter)

        root_used = QTreeWidgetItem(self.tree, ["In Use"])
        root_orphaned = QTreeWidgetItem(self.tree, ["Orphaned"])
        for prompt in prompts:
            if prompt.samples:
                prompt_root_item = root_used
            else:
                prompt_root_item = root_orphaned
            item = QTreeWidgetItem(prompt_root_item, [prompt.prompt_text_oneliner])
            item.setData(0, Qt.ItemDataRole.UserRole, "prompt")
            item.setData(1, Qt.ItemDataRole.UserRole, prompt.id)

        root_used.setExpanded(False)
        root_orphaned.setExpanded(True)

    def _populate_export_templates(self, data_filter: DataFilter, dataset: "DatasetDatabase") -> None:
        """Populate tree with export templates stored in the dataset."""

        templates = ExportTemplate.get_all(dataset)

        search_value: str | None = None
        for criteria in getattr(data_filter, "filters", []):
            if criteria.get("type") == "text_search":
                probe = str(criteria.get("value", "")).strip().lower()
                if probe:
                    search_value = probe
                    break

        if search_value:
            templates = [
                template for template in templates if search_value in template.name.lower() or search_value in template.description.lower()
            ]

        if not templates:
            placeholder = QTreeWidgetItem(self.tree, ["No export templates available"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        for template in templates:
            label = (f"{template.name} — {template.training_type}" if template.training_type else template.name)
            item = QTreeWidgetItem(self.tree, [label])
            item.setData(0, Qt.ItemDataRole.UserRole, "export_template")
            item.setData(1, Qt.ItemDataRole.UserRole, template.id)
            item.setToolTip(0, template.description)

    def select_item(self, item_type: str, item_id: int) -> None:
        """Select and focus the first tree item matching the provided type and identifier."""
        iterator = QTreeWidgetItemIterator(self.tree)
        while True:
            item = iterator.value()
            if item is None:
                break
            if (item.data(0, Qt.ItemDataRole.UserRole) == item_type and item.data(1, Qt.ItemDataRole.UserRole) == item_id):
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                break
            iterator += 1


class WidgetNavigationSidebar(QWidget):
    """
    Widget navigation sidebar for the application.

    Contains vertical layout with:
    - Filter panel, that sets what kind of objects to show and how to filter them
    - Tree view of selected items (e.g. samples, facets, etc.)
    """

    item_selected = pyqtSignal(str, int)  # Signal emitted when item is selected (item_type, item_id)
    new_item_requested = pyqtSignal(str)  # Signal emitted when new item of type is requested (item_type)
    app: "pyFadeApp"
    dataset: "DatasetDatabase"

    def __init__(self, parent: QWidget | None, app: "pyFadeApp"):
        super().__init__(parent)
        self.app = app
        if not app.current_dataset:
            raise RuntimeError("App does not have a current dataset set. Should open a dataset first.")
        self.dataset = app.current_dataset
        self._current_facet_id = None
        self._previous_show_value = None
        self.setup_ui()
        self.connect_signals()
        self._load_preferences()
        # Initialize filter list
        self.filter_panel.update_filter_list(self.dataset)
        self._refresh_content()

    def setup_ui(self):
        """Setup the navigation sidebar UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Add title
        title_label = QLabel("Navigation")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Add filter panel
        self.filter_panel = WidgetNavigationFilterPanel(self)
        layout.addWidget(self.filter_panel)

        # Add another separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator2)

        # Add tree view
        self.tree_view = WidgetNavigationTree(self)
        layout.addWidget(self.tree_view)
        # Make the tree view take remaining vertical space, filter panel only takes what's needed.
        self.tree_view.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.setStretch(layout.indexOf(self.filter_panel), 0)
        layout.setStretch(layout.indexOf(self.tree_view), 1)

        # Set size policy to prefer minimum width
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(200)
        self.setMaximumWidth(400)

    def connect_signals(self):
        """
        Connect internal signals.
        """

        self.filter_panel.filter_changed.connect(self._on_filter_changed)
        self.filter_panel.flat_list_toggle.toggled_state_changed.connect(self._on_flat_list_mode_changed)
        self.filter_panel.group_by_rating_toggle.toggled_state_changed.connect(self._on_group_by_rating_mode_changed)
        self.tree_view.item_selected.connect(self.item_selected.emit)
        self.tree_view.new_item_requested.connect(self.new_item_requested.emit)

    def _dataset_pref_key(self) -> str:
        """Get the preference key for the current dataset."""
        return str(self.dataset.db_path.resolve())

    def _load_preferences(self):
        """Load persisted preferences for the current dataset."""
        if not hasattr(self.app, "config"):
            return
        dataset_prefs = get_dataset_preferences(self.app, self._dataset_pref_key())

        # Restore flat_list_mode preference
        flat_list_mode = dataset_prefs.get("nav_flat_list_mode")
        if isinstance(flat_list_mode, bool):
            self.filter_panel.flat_list_toggle.set_toggled(flat_list_mode)

        # Restore group_by_rating_mode preference
        group_by_rating_mode = dataset_prefs.get("nav_group_by_rating_mode")
        if isinstance(group_by_rating_mode, bool):
            self.filter_panel.group_by_rating_toggle.set_toggled(group_by_rating_mode)

    def _persist_preferences(self):
        """Persist preferences for the current dataset."""
        if not hasattr(self.app, "config"):
            return
        update_dataset_preferences(
            self.app, self._dataset_pref_key(), {
                "nav_flat_list_mode": self.filter_panel.flat_list_toggle.is_toggled(),
                "nav_group_by_rating_mode": self.filter_panel.group_by_rating_toggle.is_toggled(),
            })

    def _on_flat_list_mode_changed(self, _toggled: bool):
        """Handle flat list mode toggle changes by persisting the preference."""
        self._persist_preferences()

    def _on_group_by_rating_mode_changed(self, _toggled: bool):
        """Handle group by rating mode toggle changes by persisting the preference."""
        self._persist_preferences()

    def set_dataset(self, dataset: "DatasetDatabase"):
        """
        Set the dataset to display in the navigation.
        """

        self.dataset = dataset
        self.filter_panel.update_filter_list(dataset)
        self._refresh_content()

    def refresh(self) -> None:
        """
        Public helper to refresh the tree based on current filters.
        Also refreshes the filter list to pick up any newly created filters.
        """

        self.filter_panel.update_filter_list(self.dataset)
        self._refresh_content()

    def _on_filter_changed(self):
        """
        Handle filter criteria change.
        """

        self._refresh_content()

    def _refresh_content(self):
        """
        Refresh the tree content based on current filter criteria.
        """

        if self.dataset:
            filter_criteria = self.filter_panel.get_filter_criteria()
            self.tree_view.update_content(filter_criteria, self.dataset)

    def set_current_facet(self, facet: Facet | None):
        """
        Highlight the provided facet and switch view to facet listing.
        """

        target_id = facet.id if facet else None
        if target_id == self._current_facet_id:
            return
        self._current_facet_id = target_id
