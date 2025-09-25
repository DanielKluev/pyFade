"""
Top widget for specific dataset with IDE-like interface.

TODO:
 - Add right click menu to tabs, allowing to close tab.
 - Add panel above tabs for setting current facet and target module. 
    When changed, propagate to all sample tabs and to navigation sidebar.
    Remember last used facet and module per dataset, store in App Config.
"""
import uuid, datetime, logging

from PyQt6.QtWidgets import (
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout,
    QListWidget, 
    QTabWidget,
    QSplitter,
    QLabel
)
from PyQt6.QtCore import Qt

# pyFADE widgets
from py_fade.gui.widget_navigation_sidebar import WidgetNavigationSidebar
from py_fade.gui.widget_sample import WidgetSample
from py_fade.gui.widget_facet import WidgetFacet

# Dataset models
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.facet import Facet
from py_fade.dataset.data_filter import DataFilter

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

class WidgetDatasetTop(QWidget):
    """
        Top widget for specific dataset. 
        IDE-like interface with sidebar for navigation, main area for tabs.
        Tabs are dashboards, samples, facets and so on.
        Navigation sidebar and main tab area separated by vertical splitter.
        By default, open one tab with new sample editor.
    """
    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: "DatasetDatabase"):
        super().__init__(parent)
        self.log = logging.getLogger("WidgetDatasetTop")
        self.app = app
        self.dataset = dataset
        self.tabs = {}
        self.setWindowTitle(f"Dataset: {dataset.db_path.name}")
        self.setGeometry(200, 200, 1200, 800)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the main UI layout with splitter."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create main splitter (horizontal: sidebar | main content)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.main_splitter)
        
        # Create and add navigation sidebar
        self.sidebar = WidgetNavigationSidebar(self, self.app)
        self.sidebar.set_dataset(self.dataset)
        self.main_splitter.addWidget(self.sidebar)
        
        # Create main content area with tabs
        self.main_content = QWidget()
        self.setup_main_content()
        self.main_splitter.addWidget(self.main_content)
        
        # Set initial splitter sizes (sidebar: 300px, main content: rest)
        self.main_splitter.setSizes([300, 900])
        self.main_splitter.setCollapsible(0, False)  # Don't allow sidebar to be collapsed completely
        
    def setup_main_content(self):
        """Setup the main content area with tabs."""
        content_layout = QVBoxLayout(self.main_content)
        content_layout.setContentsMargins(5, 5, 5, 5)
        
        # Add title for main area
        title_label = QLabel("Dataset Content")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        content_layout.addWidget(title_label)
        
        # Main area for tabs
        self.tab_widget = QTabWidget()
        content_layout.addWidget(self.tab_widget)

        # Populate with initial tabs
        self.populate_tabs()

    def connect_signals(self):
        """Connect signals between components."""
        self.sidebar.item_selected.connect(self._on_navigation_item_selected)
        self.sidebar.new_item_requested.connect(self._on_new_item_requested)

    def create_tab(self, widget_id: int) -> int | None:
        """Create a new tab in the main tab area."""
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        
        widget = tab_info["widget"]
        title = tab_info["title"]
        index = self.tab_widget.addTab(widget, title)
        tab_info["tab_index"] = index
        return index

    def create_sample_tab(self, sample: Sample|None) -> dict:
        """
        Create a new tab for editing/viewing a sample.
        """
        sample_widget = WidgetSample(self, self.app, sample=sample)
        widget_id = id(sample_widget)
        if sample:
            tab_title = f"S: {sample.title}"
        else:
            tab_title = "New Sample"
        self.tabs[widget_id] = {
            "type": "sample",
            "id": sample.id if sample else 0,
            "title": tab_title,
            "widget": sample_widget,
        }
        self.create_tab(widget_id)
        sample_widget.sample_saved.connect(lambda sample: self._on_sample_saved(widget_id, sample))
        sample_widget.sample_copied.connect(lambda sample: self._on_sample_copied(widget_id, sample))
        return self.tabs[widget_id]
    
    def create_facet_tab(self, facet: Facet|None) -> dict:
        """
        Create a new tab for editing/viewing a facet.
        """
        facet_widget = WidgetFacet(self, self.app, self.dataset, facet)
        widget_id = id(facet_widget)
        if facet:
            tab_title = f"F: {facet.name}"
        else:
            tab_title = "New Facet"
        self.tabs[widget_id] = {
            "type": "facet",
            "id": facet.id if facet else 0,
            "title": tab_title,
            "widget": facet_widget,
        }
        self.create_tab(widget_id)
        # Connect signals as needed
        return self.tabs[widget_id]

    def populate_tabs(self):
        """Populate the main tab area with dataset content."""
        # Overview tab - shows general dataset info
        overview_widget = self.create_overview_tab()
        self.tab_widget.addTab(overview_widget, "Overview")
        
        # Default sample editor tab
        new_sample_tab = self.create_sample_tab(None)

        # Set the sample tab as active
        self.tab_widget.setCurrentIndex(new_sample_tab["tab_index"])
        
    def create_overview_tab(self) -> QWidget:
        """Create the overview tab showing dataset statistics."""
        overview_widget = QWidget()
        layout = QVBoxLayout(overview_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Dataset info
        info_label = QLabel(f"""
        <h2>Dataset Overview</h2>
        <p><b>Database Path:</b> {self.dataset.db_path}</p>
        <p><b>Status:</b> {'Connected' if self.dataset.session else 'Not Connected'}</p>
        <br>
        <h3>Statistics</h3>
        <p><i>Statistics will be implemented when database queries are available.</i></p>
        <ul>
        <li>Total Samples: TBD</li>
        <li>Total Prompts: TBD</li>
        <li>Total Completions: TBD</li>
        <li>Available Facets: TBD</li>
        </ul>
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        layout.addStretch()
        
        return overview_widget
    
    def _on_sample_saved(self, widget_id: int, sample: Sample):
        """Handle sample saved event."""
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        need_cecreate_new_sample_tab = False
        # Update tab title to reflect saved sample
        if sample:
            if tab_info["id"] == 0:  # New sample was created
                need_cecreate_new_sample_tab = True

            new_title = f"S: {sample.title}"
            tab_info["title"] = new_title
            index = tab_info.get("tab_index")
            if index is not None:
                self.tab_widget.setTabText(index, new_title)
            tab_info["id"] = sample.id

        if need_cecreate_new_sample_tab:
            self.create_sample_tab(None)  # Create a new empty sample tab

    def _on_sample_copied(self, widget_id: int, sample: Sample):
        """Handle sample copied event by opening it in a new tab."""
        new_tab = self.create_sample_tab(sample.new_copy())
        self.tab_widget.setCurrentIndex(new_tab["tab_index"])
    
    def _on_navigation_item_selected(self, item_type: str, item_id: int):
        """Handle navigation item selection."""
        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        for tab in self.tabs.values():
            if tab["type"] == item_type and tab["id"] == item_id:
                index = tab.get("tab_index")
                if index is not None:
                    self.tab_widget.setCurrentIndex(index)
                    return
                return # Tab exists but index missing, should not happen
        
        # Tab does not exist, create it
        if item_type in ["tag", "completion", "export_template"]:
            # Not implemented yet
            return
        
        # Sample or prompt selected - open in sample editor tab
        new_tab = None
        if item_type == "sample" or item_type == "prompt":
            if item_type == "sample":
                sample = self.dataset.session.query(Sample).get(item_id)
                if not sample:
                    return
            elif item_type == "prompt":
                prompt = self.dataset.session.query(PromptRevision).get(item_id)
                if not prompt:
                    return
                sample = Sample.from_prompt_revision(self.dataset, prompt)
            new_tab = self.create_sample_tab(sample)
        elif item_type == "facet":
            facet = self.dataset.session.query(Facet).get(item_id)
            if not facet:
                return
            new_tab = self.create_facet_tab(facet)

        if not new_tab:
            return

        self.tab_widget.setCurrentIndex(new_tab["tab_index"])
        return

    def _on_new_item_requested(self, item_type: str):
        """Handle request to create a new item of given type."""
        self.log.info(f"Request to create new item of type: {item_type}")
        item_type = item_type.lower()
        if item_type == "sample":
            new_tab = self.create_sample_tab(None)
            self.tab_widget.setCurrentIndex(new_tab["tab_index"])
            return
        if item_type == "facet":
            new_tab = self.create_facet_tab(None)
            self.tab_widget.setCurrentIndex(new_tab["tab_index"])
            return
        # For other types, creation logic can be added here
        # For now, just show a placeholder tab
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(f"Creation UI for new {item_type} will be implemented.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        tab_title = f"New {item_type.title()}"
        index = self.tab_widget.addTab(widget, tab_title)
        self.tab_widget.setCurrentIndex(index)