"""
Widget navigation sidebar for the application.
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTextEdit,
    QScrollArea,
    QSizePolicy,
    QLabel,
    QFrame,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor

from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon

from py_fade.dataset.sample import Sample
from py_fade.dataset.facet import Facet
from py_fade.dataset.tag import Tag
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.data_filter import DataFilter

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

class WidgetNavigationFilterPanel(QWidget):
    """
    Filter panel for navigation sidebar.
    Lets switch between samples by groups, samples by facets, samples by tags, individual prompts, individual completions.
    Additionally lets filter by text search.
    """
    
    filter_changed = pyqtSignal()  # Signal emitted when filter criteria change
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
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
            "Facets", 
            "Tags", 
            "Prompts", 
            "Completions",
            "Export Templates"
        ])
        self.show_combo.currentTextChanged.connect(self.filter_changed.emit)
        
        # Text search
        search_label = QLabel("Search:")
        from PyQt6.QtWidgets import QLineEdit
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search text...")
        self.search_input.textChanged.connect(self.filter_changed.emit)
        
        # Add widgets to layout
        layout.addWidget(show_label)
        layout.addWidget(self.show_combo)
        layout.addWidget(search_label)
        layout.addWidget(self.search_input)
        # Do not add a stretch here so the panel only takes the space it needs.
        # Ensure the panel does not expand vertically.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        
    def _build_data_filter(self) -> DataFilter:
        """Build a DataFilter based on current filter criteria."""
        filters = []
        if self.search_input.text().strip():
            search_text = self.search_input.text().strip().lower()
            filters.append({'type': 'text_search', 'value': search_text})
        return DataFilter(filters)
    
    def get_filter_criteria(self) -> dict:
        """Get current filter criteria as a dictionary."""
        return {
            'show': self.show_combo.currentText(),
            'data_filter': self._build_data_filter()
        }

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
        
    def _on_item_clicked(self, item, column):
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

        show = filter_criteria.get('show', 'Samples by Group')
        data_filter: DataFilter = filter_criteria.get('data_filter')  # type: ignore
        self.current_item_type = None
        if show == "Samples by Group":
            self.current_item_type = "Sample"
            self._populate_samples(data_filter, dataset)
        elif show == "Facets":
            self.current_item_type = "Facet"
            self._populate_facets(data_filter, dataset)
        elif show == "Tags":
            self.current_item_type = "Tag"
            self._populate_tags(data_filter, dataset)
        elif show == "Prompts":
            self.current_item_type = None # Prompts created elsewhere
            self._populate_prompts(data_filter, dataset)
        elif show == "Completions":
            self.current_item_type = None # Completions created elsewhere
            self._populate_completions(data_filter, dataset)
        elif show == "Export Templates":
            self.current_item_type = "export_template"
            self._populate_export_templates(data_filter, dataset)

        if self.current_item_type is None:
            self.new_element_button.setVisible(False) # New elements of this type created elsewhere
        else:
            self.new_element_button.setVisible(True)
            pretty_label = self.current_item_type.replace("_", " ").title()
            self.new_element_button.setText(f"New {pretty_label}")
            self.new_element_button.setToolTip(f"Create new {pretty_label} element")

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
            group_parts = group_path.split('/')
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

    def _populate_facets(self, data_filter: DataFilter, dataset: "DatasetDatabase"):
        """Populate tree with facets."""
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        facets = dataset.session.query(Facet).all()

        if not facets:
            self.tree
    
        for facet in facets:
            item = QTreeWidgetItem(self.tree, [facet.name])
            item.setData(0, Qt.ItemDataRole.UserRole, "facet")
            item.setData(1, Qt.ItemDataRole.UserRole, facet.id)

    def _populate_tags(self, data_filter: DataFilter, dataset: "DatasetDatabase"):
        """Populate tree with tags."""
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        from py_fade.dataset.tag import Tag

        tags = Tag.get_all(dataset)

        search_value: str | None = None
        for criteria in getattr(data_filter, "filters", []):
            if criteria.get("type") == "text_search":
                value = str(criteria.get("value", "")).strip().lower()
                if value:
                    search_value = value
                    break

        if search_value:
            tags = [
                tag
                for tag in tags
                if search_value in tag.name.lower() or search_value in tag.description.lower()
            ]

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

    def _populate_completions(self, data_filter: DataFilter, dataset: "DatasetDatabase"):
        """Populate tree with completions."""
        
        completion_item = QTreeWidgetItem(self.tree, ["Completions"])
        # Mock completion data
        for i in range(4):
            completion_name = f"Completion {i+1}"
            item = QTreeWidgetItem(completion_item, [completion_name])
            item.setData(0, Qt.ItemDataRole.UserRole, "completion")
            item.setData(1, Qt.ItemDataRole.UserRole, f"completion_{i+1}")
        
        completion_item.setExpanded(True)

    def _populate_export_templates(self, data_filter: DataFilter, dataset: "DatasetDatabase") -> None:
        """Populate tree with export templates stored in the dataset."""

        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

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
                template
                for template in templates
                if search_value in template.name.lower() or search_value in template.description.lower()
            ]

        if not templates:
            placeholder = QTreeWidgetItem(self.tree, ["No export templates available"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        for template in templates:
            label = f"{template.name} — {template.training_type}" if template.training_type else template.name
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
            if (
                item.data(0, Qt.ItemDataRole.UserRole) == item_type
                and item.data(1, Qt.ItemDataRole.UserRole) == item_id
            ):
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
        """Connect internal signals."""
        self.filter_panel.filter_changed.connect(self._on_filter_changed)
        self.tree_view.item_selected.connect(self.item_selected.emit)
        self.tree_view.new_item_requested.connect(self.new_item_requested.emit)

    def set_dataset(self, dataset: "DatasetDatabase"):
        """Set the dataset to display in the navigation."""
        self.dataset = dataset
        self._refresh_content()
        
    def refresh(self) -> None:
        """Public helper to refresh the tree based on current filters."""

        self._refresh_content()

    def _on_filter_changed(self):
        """Handle filter criteria change."""
        self._refresh_content()
        
    def _refresh_content(self):
        """Refresh the tree content based on current filter criteria."""
        if self.dataset:
            filter_criteria = self.filter_panel.get_filter_criteria()
            self.tree_view.update_content(filter_criteria, self.dataset)

    def set_current_facet(self, facet: Facet | None):
        """Highlight the provided facet and switch view to facet listing."""
        target_id = facet.id if facet else None
        if target_id == self._current_facet_id:
            return
        self._current_facet_id = target_id