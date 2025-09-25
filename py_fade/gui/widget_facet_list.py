from py_fade.gui.gui_helpers import *
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon
from py_fade.gui.widget_facet import WidgetFacet

from PyQt6.QtWidgets import QDialog

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.app import pyFadeApp

class WidgetFacetList(QWidget):
    """
    Widget to display and manage a list of facets. 
    Provides full CRUD functionality for facet management.
    """
    app: "pyFadeApp"
    dataset: "DatasetDatabase"
    
    # Signals
    facet_selected = pyqtSignal(object)  # Signal emitted when a facet is selected

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: "DatasetDatabase"):
        super().__init__(parent)
        self.app = app
        self.dataset = dataset
        
        self.setup_ui()
        self.refresh_facet_list()

    def setup_ui(self):
        """Create and arrange UI components."""
        self.setMinimumSize(600, 400)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Header section
        header_layout = QHBoxLayout()
        
        self.header_label = QLabelWithIcon("view_list", "Facet Management")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1976D2;")
        header_layout.addWidget(self.header_label)
        header_layout.addStretch()
        
        # Action buttons
        self.new_button = QPushButtonWithIcon("add", "New Facet")
        self.new_button.setStyleSheet("QPushButton { background-color: #1976D2; color: white; padding: 8px 16px; }")
        self.new_button.clicked.connect(self.create_new_facet)
        
        self.refresh_button = QPushButtonWithIcon("refresh", "Refresh")
        self.refresh_button.setStyleSheet("QPushButton { background-color: #757575; color: white; padding: 8px 16px; }")
        self.refresh_button.clicked.connect(self.refresh_facet_list)
        
        header_layout.addWidget(self.new_button)
        header_layout.addWidget(self.refresh_button)
        
        main_layout.addLayout(header_layout)
        
        # Search section
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-weight: bold;")
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search facets by name or description...")
        self.search_field.textChanged.connect(self.filter_facets)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_field)
        
        main_layout.addLayout(search_layout)
        
        # Facet list section
        list_frame = QGroupBox("Facets")
        list_layout = QVBoxLayout(list_frame)
        
        # Create scrollable area for facet list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.facet_list_widget = QWidget()
        self.facet_list_layout = QVBoxLayout(self.facet_list_widget)
        self.facet_list_layout.setSpacing(8)
        
        scroll_area.setWidget(self.facet_list_widget)
        list_layout.addWidget(scroll_area)
        
        main_layout.addWidget(list_frame)
        
        # Status section
        self.status_label = QLabel("Loading facets...")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        main_layout.addWidget(self.status_label)

    def refresh_facet_list(self):
        """Refresh the list of facets from the database."""
        if not self.dataset.session:
            self.status_label.setText("Error: Dataset session not initialized")
            return
        
        try:
            self.facets = Facet.get_all(self.dataset)
            self.display_facets(self.facets)
            
            count = len(self.facets)
            self.status_label.setText(f"{count} facet{'s' if count != 1 else ''} found")
            
        except Exception as e:
            self.status_label.setText(f"Error loading facets: {str(e)}")

    def display_facets(self, facets):
        """Display the given list of facets in the UI."""
        # Clear existing widgets
        while self.facet_list_layout.count():
            child = self.facet_list_layout.takeAt(0)
            if child and child.widget():
                child.widget().deleteLater()
        
        # Add facet items
        if not facets:
            no_facets_label = QLabel("No facets found. Click 'New Facet' to create one.")
            no_facets_label.setStyleSheet("color: #666; font-style: italic; padding: 20px; text-align: center;")
            no_facets_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.facet_list_layout.addWidget(no_facets_label)
        else:
            for facet in facets:
                facet_item = self.create_facet_item(facet)
                self.facet_list_layout.addWidget(facet_item)
        
        # Add stretch at the end
        self.facet_list_layout.addStretch()

    def create_facet_item(self, facet: Facet) -> QWidget:
        """Create a widget for a single facet item."""
        item_frame = QFrame()
        item_frame.setFrameStyle(QFrame.Shape.Box)
        item_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                margin: 2px;
            }
            QFrame:hover {
                border-color: #1976D2;
                background-color: #f5f5f5;
            }
        """)
        
        layout = QHBoxLayout(item_frame)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Facet info section
        info_layout = QVBoxLayout()
        
        # Name and date
        name_layout = QHBoxLayout()
        name_label = QLabel(facet.name)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1976D2;")
        
        date_label = QLabel(facet.date_created.strftime("%Y-%m-%d %H:%M"))
        date_label.setStyleSheet("font-size: 11px; color: #666;")
        
        name_layout.addWidget(name_label)
        name_layout.addStretch()
        name_layout.addWidget(date_label)
        
        info_layout.addLayout(name_layout)
        
        # Description
        description_label = QLabel(facet.description[:100] + ("..." if len(facet.description) > 100 else ""))
        description_label.setStyleSheet("color: #666; font-size: 12px;")
        description_label.setWordWrap(True)
        info_layout.addWidget(description_label)
        
        # Stats
        stats_label = QLabel(f"Samples: {facet.total_samples}")
        stats_label.setStyleSheet("font-size: 11px; color: #666; margin-top: 4px;")
        info_layout.addWidget(stats_label)
        
        layout.addLayout(info_layout)
        
        # Action buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(4)
        
        edit_button = QPushButtonWithIcon("edit", "Edit")
        edit_button.setStyleSheet("QPushButton { background-color: #1976D2; color: white; padding: 6px 12px; }")
        edit_button.clicked.connect(lambda: self.edit_facet(facet))
        
        delete_button = QPushButtonWithIcon("delete", "Delete")
        delete_button.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; padding: 6px 12px; }")
        delete_button.clicked.connect(lambda: self.delete_facet(facet))
        
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return item_frame

    def filter_facets(self):
        """Filter facets based on search text."""
        search_text = self.search_field.text().lower().strip()
        
        if not search_text:
            # Show all facets
            filtered_facets = self.facets if hasattr(self, 'facets') else []
        else:
            # Filter by name or description
            filtered_facets = [
                facet for facet in (self.facets if hasattr(self, 'facets') else [])
                if search_text in facet.name.lower() or search_text in facet.description.lower()
            ]
        
        self.display_facets(filtered_facets)
        
        count = len(filtered_facets)
        total = len(self.facets) if hasattr(self, 'facets') else 0
        if search_text:
            self.status_label.setText(f"Showing {count} of {total} facet{'s' if total != 1 else ''}")
        else:
            self.status_label.setText(f"{total} facet{'s' if total != 1 else ''} found")

    def create_new_facet(self):
        """Open the facet creation dialog."""
        self.show_facet_dialog(None)

    def edit_facet(self, facet: Facet):
        """Open the facet editing dialog."""
        self.show_facet_dialog(facet)

    def delete_facet(self, facet: Facet):
        """Delete the specified facet after confirmation."""
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            f"Are you sure you want to delete the facet '{facet.name}'?\n\n"
            f"This action cannot be undone and will affect {facet.total_samples} sample{'s' if facet.total_samples != 1 else ''}.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                facet_name = facet.name
                if self.dataset.session:
                    self.dataset.session.delete(facet)
                    self.dataset.session.commit()
                
                QMessageBox.information(
                    self, 
                    "Success", 
                    f"Facet '{facet_name}' deleted successfully!"
                )
                
                self.refresh_facet_list()
                
            except Exception as e:
                if self.dataset.session:
                    self.dataset.session.rollback()
                QMessageBox.critical(
                    self, 
                    "Error", 
                    f"Failed to delete facet: {str(e)}"
                )

    def show_facet_dialog(self, facet: Facet | None):
        """Show the facet creation/editing dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("New Facet" if facet is None else f"Edit Facet: {facet.name}")
        dialog.setMinimumSize(500, 400)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        # Create facet widget
        facet_widget = WidgetFacet(dialog, self.app, self.dataset, facet)
        
        # Connect signals
        facet_widget.facet_saved.connect(lambda: self.on_facet_saved(dialog))
        facet_widget.facet_cancelled.connect(dialog.reject)
        facet_widget.facet_deleted.connect(lambda: self.on_facet_deleted(dialog))
        
        layout.addWidget(facet_widget)
        
        dialog.exec()

    def on_facet_saved(self, dialog: QDialog):
        """Handle facet saved event."""
        dialog.accept()
        self.refresh_facet_list()

    def on_facet_deleted(self, dialog: QDialog):
        """Handle facet deleted event.""" 
        dialog.accept()
        self.refresh_facet_list()