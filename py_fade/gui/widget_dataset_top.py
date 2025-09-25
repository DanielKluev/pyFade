"""
Top widget for specific dataset with IDE-like interface.

Provides navigation sidebar, dataset context controls for active facet and
inference model, and a tabbed workspace where individual editors live. Tabs
can be closed from a context menu, and context selections propagate to sample
widgets as well as the navigation sidebar. The last selected facet and model
are persisted per dataset via the application configuration.
"""
import logging

from PyQt6.QtWidgets import (
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout,
    QTabWidget,
    QSplitter,
    QLabel,
    QComboBox,
    QFrame,
    QMenu
)
from PyQt6.QtCore import Qt, QPoint

# pyFADE widgets
from py_fade.gui.widget_navigation_sidebar import WidgetNavigationSidebar
from py_fade.gui.widget_sample import WidgetSample
from py_fade.gui.widget_facet import WidgetFacet
from py_fade.gui.widget_tag import WidgetTag
from py_fade.gui.widget_export_template import WidgetExportTemplate

# Dataset models
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.facet import Facet
from py_fade.dataset.tag import Tag
from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.export_template import ExportTemplate

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

class WidgetDatasetTop(QWidget):
    """
        Dataset workspace composed of navigation sidebar, context panel, and tabbed editors.
        Context panel defines active facet and target LLM model, which propagate to samples and sidebar.
            Active facet alters sorting order of completions, facet-specific completion preferences.
            Target model is the model used as logprobs evaluation reference, i.e. it's the model that will be trained, while completions may be generated with other models.
        Tabs are dashboards, samples, facets and so on, using type-specific widgets.
        By default, create dashboard tab and new sample tab.
    """

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: "DatasetDatabase"):
        super().__init__(parent)
        self.log = logging.getLogger("WidgetDatasetTop")
        self.app = app
        self.dataset = dataset
        self.tabs: dict[int, dict] = {}
        self.overview_widget: QWidget | None = None
        self.current_facet_id: int | None = None
        self.current_facet: Facet | None = None
        self.current_model_name: str | None = None
        self._facet_map: dict[int, Facet] = {}
        self._updating_context = False
        self._sidebar_previous_show_value: str | None = None
        self.facet_combo: QComboBox | None = None
        self.model_combo: QComboBox | None = None

        self.setWindowTitle(f"Dataset: {dataset.db_path.name}")
        self.setGeometry(200, 200, 1200, 800)

        self.setup_ui()
        self.populate_tabs()
        self.connect_signals()
        self.set_facets()
        self.set_models()
        self._propagate_context_to_samples()

    def setup_ui(self):
        """Setup the main UI layout with splitter."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.main_splitter)

        self.sidebar = WidgetNavigationSidebar(self, self.app)
        self.sidebar.set_dataset(self.dataset)
        self.main_splitter.addWidget(self.sidebar)

        self.main_content = QWidget()
        self.setup_main_content()
        self.main_splitter.addWidget(self.main_content)

        self.main_splitter.setSizes([300, 900])
        self.main_splitter.setCollapsible(0, False)

    def setup_main_content(self):
        """Setup the main content area with context controls and tab widget."""
        content_layout = QVBoxLayout(self.main_content)
        content_layout.setContentsMargins(5, 5, 5, 5)

        context_frame = QFrame()
        context_frame.setObjectName("dataset-context-frame")
        context_layout = QHBoxLayout(context_frame)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(12)

        facet_label = QLabel("Facet:")
        facet_label.setStyleSheet("font-weight: 500;")
        context_layout.addWidget(facet_label)

        self.log.info("Create facet combo")
        self.facet_combo = QComboBox()
        self.facet_combo.setObjectName("facet-selector")
        self.facet_combo.setEditable(False)
        self.facet_combo.setMinimumWidth(200)
        context_layout.addWidget(self.facet_combo)
        self.log.info(f"Facet combo created, {self.facet_combo}")

        model_label = QLabel("Model:")
        model_label.setStyleSheet("font-weight: 500;")
        context_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setObjectName("model-selector")
        self.model_combo.setEditable(False)
        self.model_combo.setMinimumWidth(220)
        context_layout.addWidget(self.model_combo)

        context_layout.addStretch()
        content_layout.addWidget(context_frame)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("dataset-tab-widget")
        self.tab_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_widget.customContextMenuRequested.connect(self._on_tab_context_menu)
        content_layout.addWidget(self.tab_widget)

    def connect_signals(self):
        """Connect signals between components."""
        self.sidebar.item_selected.connect(self._on_navigation_item_selected)
        self.sidebar.new_item_requested.connect(self._on_new_item_requested)
        if not self.facet_combo is None:
            self.facet_combo.currentIndexChanged.connect(self._on_facet_selection_changed)
        if not self.model_combo is None:
            self.model_combo.currentTextChanged.connect(self._on_model_selection_changed)

    def _dataset_pref_key(self) -> str:
        return str(self.dataset.db_path.resolve())
    
    def set_facets(self) -> None:
        """Populate facet selector based on current dataset state and preferences."""
        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        if self.facet_combo is None:
            raise RuntimeError("Facet combo box is not initialized.")
        
        available_facets = list(self.dataset.session.query(Facet).all())
        if not available_facets:
            self.log.warning("No facets available in dataset; facet selector will be empty.")
            self.current_facet_id = None
            return

        self.facet_combo.blockSignals(True)        
        self.facet_combo.clear()
        if not self.current_facet_id:
            self.current_facet_id = self.app.config.dataset_preferences.get(self._dataset_pref_key(), {}).get("facet_id", None) # type: ignore

        for facet in available_facets:
            self._facet_map[facet.id] = facet
            self.facet_combo.addItem(facet.name, facet.id)
        
        if self.current_facet_id and self.current_facet_id in self._facet_map:
            index = self.facet_combo.findData(self.current_facet_id)
            if index >= 0:
                self.facet_combo.setCurrentIndex(index)
        self.facet_combo.blockSignals(False)

    def set_models(self) -> None:
        """Populate model selector based on current dataset state and preferences."""
        if self.model_combo is None or not self.app.available_models:
            raise RuntimeError("Application is not fully initialized or no models are available.")
        
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        if not self.current_model_name:
            self.current_model_name = self.app.config.dataset_preferences.get(self._dataset_pref_key(), {}).get("model_name", None) # type: ignore
        
        for model in self.app.available_models:
            self.model_combo.addItem(model)
        
        if self.current_model_name:
            index = self.model_combo.findText(self.current_model_name)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)

    def _on_model_selection_changed(self, model_name: str) -> None:
        if self._updating_context:
            return
        normalized = model_name.strip()
        if normalized and normalized in self.app.available_models:
            self.current_model_name = normalized
        else:
            self.current_model_name = None
        self._persist_context()
        self._propagate_context_to_samples()

    def _on_facet_selection_changed(self, index: int) -> None:
        if self._updating_context or not self.facet_combo:
            return
        facet_id = self.facet_combo.itemData(index)
        if isinstance(facet_id, int) and facet_id in self._facet_map:
            self.current_facet = self._facet_map[facet_id]
            self.current_facet_id = facet_id
        else:
            self.current_facet = None
            self.current_facet_id = None
        self._persist_context()
        self._propagate_context_to_samples()

    def _persist_context(self) -> None:
        if not hasattr(self.app, "config"):
            raise RuntimeError("Application configuration is not available.")
        preferences = getattr(self.app.config, "dataset_preferences", {})
        if not isinstance(preferences, dict):
            preferences = {}
        dataset_key = self._dataset_pref_key()
        dataset_prefs = preferences.get(dataset_key, {})
        if not isinstance(dataset_prefs, dict):
            dataset_prefs = {}
        dataset_prefs["facet_id"] = self.current_facet.id if self.current_facet else None
        dataset_prefs["model_name"] = self.current_model_name
        preferences[dataset_key] = dataset_prefs
        self.app.config.dataset_preferences = preferences
        self.app.config.save()

    def _propagate_context_to_samples(self) -> None:
        for tab_info in self.tabs.values():
            widget = tab_info.get("widget")
            if isinstance(widget, WidgetSample):
                self._apply_context_to_sample(widget)
        self._update_sidebar_for_facet()

    def _apply_context_to_sample(self, sample_widget: WidgetSample) -> None:
        sample_widget.set_active_context(self.current_facet, self.current_model_name)

    def _update_sidebar_for_facet(self) -> None:
        if hasattr(self.sidebar, "set_current_facet"):
            self.sidebar.set_current_facet(self.current_facet)

    def populate_tabs(self) -> None:
        """Populate the main tab area with dataset content."""
        self.overview_widget = self.create_overview_tab()
        self._register_tab(self.overview_widget, "Overview", "overview", entity_id=0, closable=False, focus=False)
        sample_widget_id = self.create_sample_tab(None, focus=True)
        self._focus_widget(self.tabs[sample_widget_id]["widget"])

    def create_overview_tab(self) -> QWidget:
        """Create the overview tab showing dataset statistics."""
        overview_widget = QWidget()
        layout = QVBoxLayout(overview_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        info_label = QLabel(
            f"""
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
        """
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        layout.addStretch()
        return overview_widget

    def _register_tab(
        self,
        widget: QWidget,
        title: str,
        tab_type: str,
        entity_id: int,
        *,
        closable: bool = True,
        focus: bool = False,
    ) -> int:
        widget_id = id(widget)
        self.tabs[widget_id] = {
            "type": tab_type,
            "id": entity_id,
            "title": title,
            "widget": widget,
            "closable": closable,
        }
        index = self.tab_widget.addTab(widget, title)
        if focus:
            self.tab_widget.setCurrentIndex(index)
        return widget_id

    def _set_tab_title(self, widget_id: int, title: str) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        tab_info["title"] = title
        index = self._tab_index(widget_id)
        if index >= 0:
            self.tab_widget.setTabText(index, title)

    def create_sample_tab(self, sample: Sample | None, *, focus: bool = True) -> int:
        """Create a new tab for editing/viewing a sample."""
        sample_widget = WidgetSample(self, self.app, sample=sample)
        sample_id = sample.id if sample and getattr(sample, "id", None) else 0
        title = f"S: {sample.title}" if sample else "New Sample"
        widget_id = self._register_tab(sample_widget, title, "sample", sample_id, focus=focus)
        self._apply_context_to_sample(sample_widget)
        sample_widget.sample_saved.connect(lambda saved, wid=widget_id: self._on_sample_saved(wid, saved))
        sample_widget.sample_copied.connect(lambda original, wid=widget_id: self._on_sample_copied(wid, original))
        return widget_id

    def create_facet_tab(self, facet: Facet | None, *, focus: bool = True) -> int:
        """Create a new tab for editing/viewing a facet."""
        facet_widget = WidgetFacet(self, self.app, self.dataset, facet)
        facet_id = facet.id if facet else 0
        title = f"F: {facet.name}" if facet else "New Facet"
        return self._register_tab(facet_widget, title, "facet", facet_id, focus=focus)

    def create_tag_tab(self, tag: Tag | None, *, focus: bool = True) -> int:
        """Create a new tab for editing or creating a tag."""

        tag_widget = WidgetTag(self, self.app, self.dataset, tag)
        tag_id = tag.id if tag else 0
        title = f"T: {tag.name}" if tag else "New Tag"
        widget_id = self._register_tab(tag_widget, title, "tag", tag_id, focus=focus)
        tag_widget.tag_saved.connect(lambda saved, wid=widget_id: self._on_tag_saved(wid, saved))
        tag_widget.tag_deleted.connect(lambda deleted, wid=widget_id: self._on_tag_deleted(wid, deleted))
        tag_widget.tag_cancelled.connect(lambda wid=widget_id: self._on_tag_cancelled(wid))
        return widget_id

    def create_export_template_tab(
        self, template: ExportTemplate | None, *, focus: bool = True
    ) -> int:
        """Create a new tab for managing an export template."""

        template_widget = WidgetExportTemplate(self, self.app, self.dataset, template)
        template_id = template.id if template else 0
        title = f"X: {template.name}" if template else "New Export Template"
        widget_id = self._register_tab(template_widget, title, "export_template", template_id, focus=focus)
        template_widget.template_saved.connect(
            lambda saved, wid=widget_id: self._on_export_template_saved(wid, saved)
        )
        template_widget.template_deleted.connect(
            lambda deleted, wid=widget_id: self._on_export_template_deleted(wid, deleted)
        )
        template_widget.template_copied.connect(self._on_export_template_copied)
        return widget_id

    def _on_sample_saved(self, widget_id: int, sample: Sample) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info or not sample:
            return
        create_new_blank = tab_info["id"] == 0
        tab_info["id"] = sample.id
        self._set_tab_title(widget_id, f"S: {sample.title}")
        if create_new_blank:
            self.create_sample_tab(None, focus=False)

    def _on_sample_copied(self, widget_id: int, sample: Sample) -> None:
        new_sample = sample.new_copy()
        new_tab_id = self.create_sample_tab(new_sample, focus=True)
        self._focus_widget(self.tabs[new_tab_id]["widget"])

    def _on_tag_saved(self, widget_id: int, tag: Tag) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        tab_info["id"] = tag.id
        self._set_tab_title(widget_id, f"T: {tag.name}")
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()

    def _on_tag_deleted(self, widget_id: int, tag: Tag) -> None:
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()
        index = self._tab_index(widget_id)
        if index >= 0:
            self.close_tab(index)

    def _on_tag_cancelled(self, widget_id: int) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        if tab_info.get("id") == 0:
            index = self._tab_index(widget_id)
            if index >= 0:
                self.close_tab(index)

    def _on_export_template_saved(self, widget_id: int, template: ExportTemplate) -> None:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return
        tab_info["id"] = template.id
        self._set_tab_title(widget_id, f"X: {template.name}")
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()

    def _on_export_template_deleted(self, widget_id: int, template: ExportTemplate) -> None:
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()
        index = self._tab_index(widget_id)
        if index >= 0:
            self.close_tab(index)

    def _on_export_template_copied(self, template: ExportTemplate) -> None:
        widget_id = self.create_export_template_tab(template, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])
        if hasattr(self.sidebar, "refresh"):
            self.sidebar.refresh()

    def _focus_widget(self, widget: QWidget | None) -> None:
        if not widget:
            return
        index = self.tab_widget.indexOf(widget)
        if index >= 0:
            self.tab_widget.setCurrentIndex(index)

    def _tab_index(self, widget_id: int) -> int:
        tab_info = self.tabs.get(widget_id)
        if not tab_info:
            return -1
        return self.tab_widget.indexOf(tab_info["widget"])

    def _find_tab_by(self, tab_type: str, entity_id: int) -> int | None:
        for widget_id, tab_info in self.tabs.items():
            if tab_info["type"] == tab_type and tab_info["id"] == entity_id:
                return widget_id
        return None

    def _on_navigation_item_selected(self, item_type: str, item_id: int) -> None:
        if self.dataset.session is None:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        normalized_type = item_type.lower()
        existing_widget_id = self._find_tab_by(normalized_type, item_id)
        if existing_widget_id:
            self._focus_widget(self.tabs[existing_widget_id]["widget"])
            return

        if normalized_type == "completion":
            self.log.info("Navigation for %s is not implemented yet.", normalized_type)
            return

        if normalized_type == "export_template":
            template = ExportTemplate.get_by_id(self.dataset, item_id)
            if not template:
                return
            widget_id = self.create_export_template_tab(template, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return

        if normalized_type == "tag":
            tag = Tag.get_by_id(self.dataset, item_id)
            if not tag:
                return
            widget_id = self.create_tag_tab(tag, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return

        if normalized_type in {"sample", "prompt"}:
            if normalized_type == "sample":
                sample = self.dataset.session.query(Sample).get(item_id)
                if not sample:
                    return
            else:
                prompt = self.dataset.session.query(PromptRevision).get(item_id)
                if not prompt:
                    return
                sample = Sample.from_prompt_revision(self.dataset, prompt)
            widget_id = self.create_sample_tab(sample, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return

        if normalized_type == "facet":
            facet = self.dataset.session.query(Facet).get(item_id)
            if not facet:
                return
            widget_id = self.create_facet_tab(facet, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return

    def _on_new_item_requested(self, item_type: str) -> None:
        normalized_type = item_type.lower()
        self.log.info("Request to create new item of type: %s", normalized_type)
        if normalized_type == "sample":
            widget_id = self.create_sample_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return
        if normalized_type == "facet":
            widget_id = self.create_facet_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return
        if normalized_type == "tag":
            widget_id = self.create_tag_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return
        if normalized_type == "export_template":
            widget_id = self.create_export_template_tab(None, focus=True)
            self._focus_widget(self.tabs[widget_id]["widget"])
            return

        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        label = QLabel(f"Creation UI for new {normalized_type} will be implemented.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        tab_title = f"New {normalized_type.title()}"
        widget_id = self._register_tab(placeholder, tab_title, normalized_type, 0, focus=True)
        self._focus_widget(self.tabs[widget_id]["widget"])

    def _on_tab_context_menu(self, position: QPoint) -> None:
        tab_bar = self.tab_widget.tabBar()
        if tab_bar is None:
            return
        index = tab_bar.tabAt(position)
        if index < 0:
            return
        widget = self.tab_widget.widget(index)
        if widget is None:
            return
        widget_id = id(widget)
        tab_info = self.tabs.get(widget_id)
        if not tab_info or not tab_info.get("closable", True):
            return
        menu = QMenu(self)
        close_action = menu.addAction("Close Tab")
        action = menu.exec(tab_bar.mapToGlobal(position))
        if action == close_action:
            self.close_tab(index)

    def close_tab(self, index: int) -> None:
        if index < 0:
            return
        widget = self.tab_widget.widget(index)
        if widget is None:
            return
        widget_id = id(widget)
        tab_info = self.tabs.get(widget_id)
        if not tab_info or not tab_info.get("closable", True):
            return
        self.tab_widget.removeTab(index)
        widget.deleteLater()
        del self.tabs[widget_id]